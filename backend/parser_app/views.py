"""
API views для парсинга прайсов и работы с заказами.
"""

import os
import zipfile
import logging
import traceback
import threading
from collections import defaultdict
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Count
from django.http import FileResponse, JsonResponse
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, parser_classes, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from .models import (
    File, ParsedItem, FileMetadata, Order, Supplier,
    TapLocation, Tap, AvailableBeer, TapChangeHistory, UserProfile,
    ParseRun, ParsingFeedback, SupplierColumnMapping
)
from .validators import ParsedItemValidator
from .serializers import (
    FileSerializer, ParsedItemSerializer, FileMetadataSerializer,
    OrderSerializer, OrderCreateSerializer, SupplierSerializer,
    TapLocationSerializer, TapLocationListSerializer, TapSerializer, AvailableBeerSerializer,
    UserSerializer, UserCreateSerializer, UserUpdateSerializer,
    ParseRunSerializer, ParsingFeedbackSerializer, SupplierColumnMappingSerializer,
)
from .parsers.pdf_parser import PDFParser
from .parsers.excel_parser import ExcelParser
from .parsers.google_sheets_parser import GoogleSheetsParser
from .filters import ContactFilter
from .normalizers import DataNormalizer
from .exporters import OrderExporter, TapsExporter
from .utils import detect_file_type, extract_zip
from .untappd_client import UntappdClient
from .permissions import (
    get_user_role,
    IsAdmin,
    IsAdminOrBartender,
    CanEditTapsContent,
)
from .auth_views import SessionAuthenticationNoCSRF
from .services.autopilot_learning import promote_feedback_to_mapping

logger = logging.getLogger(__name__)


class FileViewSet(viewsets.ModelViewSet):
    """ViewSet для работы с файлами. Только админ."""
    
    authentication_classes = [SessionAuthenticationNoCSRF]
    permission_classes = [IsAuthenticated, IsAdmin]
    queryset = File.objects.all()
    serializer_class = FileSerializer

    def _infer_terminal_progress(self, file_obj):
        """Возвращает терминальный статус, если активный progress-ключ отсутствует."""
        latest_run = ParseRun.objects.filter(file=file_obj).order_by('-created_at').first()
        items_count = ParsedItem.objects.filter(file=file_obj).count()

        if latest_run and latest_run.status == 'failed':
            run_errors = ((latest_run.summary or {}).get('errors') or [])
            first_error = run_errors[0].get('message') if run_errors and isinstance(run_errors[0], dict) else None
            return {
                'status': 'error',
                'progress': 0,
                'message': first_error or 'Ошибка парсинга',
                'total_items': items_count,
                'processed_items': items_count,
                'is_running': False,
            }

        if items_count > 0 or (latest_run and latest_run.status in {'completed', 'partial'}):
            return {
                'status': 'completed',
                'progress': 100,
                'message': f'Парсинг завершен. Обработано {items_count} позиций',
                'total_items': items_count,
                'processed_items': items_count,
                'is_running': False,
            }

        return {
            'status': 'not_started',
            'progress': 0,
            'message': 'Парсинг не запущен',
            'total_items': 0,
            'processed_items': 0,
            'is_running': False,
        }
    
    @action(detail=True, methods=['post'])
    def parse(self, request, pk=None):
        """
        Запускает парсинг файла.

        POST /api/files/<id>/parse/
        Возвращает **202 Accepted** сразу; тяжёлая работа в фоне (прогресс — GET parse_progress/).
        Так Vercel rewrite не держит соединение до конца парса (иначе 502/HTML-заглушка по таймауту шлюза).

        Body (опционально): {
            "supplier_type": "distributor" | "brewery",
            "brewery_name": "Dieta"  # только для brewery
        }
        """
        file_obj = self.get_object()
        progress_key = f'parse_progress_{file_obj.id}'
        request_data = {k: request.data[k] for k in request.data}

        cache.set(progress_key, {
            'status': 'starting',
            'progress': 0,
            'message': 'Инициализация парсинга...',
            'total_items': 0,
            'processed_items': 0,
        }, timeout=600)

        if file_obj.file_type not in ('pdf', 'excel', 'google_sheets'):
            return Response(
                {'error': 'Неизвестный тип файла'},
                status=status.HTTP_400_BAD_REQUEST
            )

        lock_key = f'parse_running_{file_obj.id}'
        if not cache.add(lock_key, 1, timeout=1200):
            return Response(
                {'error': 'Парсинг этого файла уже выполняется. Дождитесь завершения или проверьте parse_progress.'},
                status=status.HTTP_409_CONFLICT,
            )

        def _run():
            from django.db import close_old_connections
            close_old_connections()
            try:
                from .parse_job import run_file_parse_job
                run_file_parse_job(file_obj.id, request.user.pk, request_data)
            except Exception:
                logger.exception('Фоновый парсинг: необработанное исключение')
                try:
                    cache.set(progress_key, {
                        'status': 'error',
                        'progress': 0,
                        'message': 'Внутренняя ошибка сервера при парсинге (см. логи Render).',
                        'total_items': 0,
                        'processed_items': 0,
                    }, timeout=600)
                except Exception:
                    pass
            finally:
                close_old_connections()

        threading.Thread(target=_run, daemon=True).start()
        return Response(
            {
                'status': 'accepted',
                'file_id': file_obj.id,
                'message': 'Парсинг запущен на сервере. Следите за GET /api/files/<id>/parse_progress/.',
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=['get'])
    def parse_progress(self, request, pk=None):
        """
        Получение прогресса парсинга файла.
        
        GET /api/files/<id>/parse_progress/
        """
        file_obj = self.get_object()
        progress_key = f'parse_progress_{file_obj.id}'
        lock_key = f'parse_running_{file_obj.id}'
        is_running = bool(cache.get(lock_key))

        progress = cache.get(progress_key)

        if not progress:
            if is_running:
                return Response({
                    'status': 'starting',
                    'progress': 0,
                    'message': 'Парсинг запущен, ожидаем первый прогресс...',
                    'total_items': 0,
                    'processed_items': 0,
                    'is_running': True,
                })
            return Response(self._infer_terminal_progress(file_obj))

        if isinstance(progress, dict):
            progress = {**progress, 'is_running': is_running}

        return Response(progress)
    
    @action(detail=True, methods=['get'])
    def items(self, request, pk=None):
        """
        Возвращает список позиций файла.
        
        GET /api/files/<id>/items/
        """
        file_obj = self.get_object()
        items = ParsedItem.objects.filter(file=file_obj).select_related('file')
        
        # Фильтрация по запросу
        brewery = request.query_params.get('brewery')
        if brewery:
            items = items.filter(brewery__icontains=brewery)
        
        beer_name = request.query_params.get('beer_name')
        if beer_name:
            items = items.filter(beer_name__icontains=beer_name)
        
        style = request.query_params.get('style')
        if style:
            items = items.filter(style__icontains=style)
        
        # Фильтрация по цене
        price_min = request.query_params.get('price_min')
        if price_min:
            try:
                items = items.filter(price__gte=float(price_min))
            except ValueError:
                pass
        
        price_max = request.query_params.get('price_max')
        if price_max:
            try:
                items = items.filter(price__lte=float(price_max))
            except ValueError:
                pass
        
        # Фильтрация по объёму
        volume_min = request.query_params.get('volume_min')
        if volume_min:
            try:
                items = items.filter(volume__gte=float(volume_min))
            except ValueError:
                pass
        
        volume_max = request.query_params.get('volume_max')
        if volume_max:
            try:
                items = items.filter(volume__lte=float(volume_max))
            except ValueError:
                pass
        
        # Фильтрация по крепости (ABV)
        abv_min = request.query_params.get('abv_min')
        if abv_min:
            try:
                items = items.filter(abv__gte=float(abv_min))
            except ValueError:
                pass
        
        abv_max = request.query_params.get('abv_max')
        if abv_max:
            try:
                items = items.filter(abv__lte=float(abv_max))
            except ValueError:
                pass
        
        # Фильтрация по листу
        sheet = request.query_params.get('sheet')
        if sheet:
            items = items.filter(raw_source_location__sheet=sheet)
        
        # Ограничиваем количество возвращаемых элементов для производительности
        limit = request.query_params.get('limit')
        if limit:
            try:
                limit = int(limit)
                items = items[:limit]
            except ValueError:
                pass
        else:
            # По умолчанию ограничиваем до 1000 элементов
            items = items[:1000]
        
        serializer = ParsedItemSerializer(items, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def sheets(self, request, pk=None):
        """
        Возвращает список листов файла с количеством позиций в каждом.
        
        GET /api/files/<id>/sheets/
        """
        file_obj = self.get_object()
        
        # Оптимизированный запрос - используем только нужные поля
        from django.db.models import Count
        
        try:
            # Используем values() для оптимизации запроса
            sheets_data = ParsedItem.objects.filter(
                file=file_obj
            ).select_related('file').exclude(
                raw_source_location__sheet__isnull=True
            ).exclude(
                raw_source_location__sheet=''
            ).values('raw_source_location__sheet').annotate(
                count=Count('id')
            ).order_by('raw_source_location__sheet')[:100]  # Ограничиваем до 100 листов
            
            sheets_list = [
                {
                    'name': item['raw_source_location__sheet'],
                    'count': item['count']
                }
                for item in sheets_data
            ]
            
            return Response({'sheets': sheets_list})
        except Exception as e:
            logger.error(f"Ошибка при получении списка листов: {str(e)}", exc_info=True)
            return Response({'sheets': []}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def metadata(self, request, pk=None):
        """
        Возвращает метаданные файла.
        
        GET /api/files/<id>/metadata/
        """
        file_obj = self.get_object()
        try:
            metadata = file_obj.metadata
            serializer = FileMetadataSerializer(metadata)
            return Response(serializer.data)
        except FileMetadata.DoesNotExist:
            return Response(
                {'error': 'Метаданные не найдены. Запустите парсинг файла.'},
                status=status.HTTP_404_NOT_FOUND
            )


class SupplierViewSet(viewsets.ModelViewSet):
    """ViewSet для настроек поставщиков (маппинг колонок). Только админ."""
    authentication_classes = [SessionAuthenticationNoCSRF]
    permission_classes = [IsAuthenticated, IsAdmin]
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer


class ParsedItemViewSet(viewsets.ModelViewSet):
    """ViewSet для работы с распарсенными позициями. Только админ."""
    authentication_classes = [SessionAuthenticationNoCSRF]
    permission_classes = [IsAuthenticated, IsAdmin]
    queryset = ParsedItem.objects.all()
    serializer_class = ParsedItemSerializer
    
    @action(detail=False, methods=['patch'])
    def bulk_update(self, request):
        """
        Массовое обновление позиций.
        
        PATCH /api/items/bulk_update/
        Body: {
            "item_ids": [1, 2, 3],
            "data": {"price": 100, "currency": "RUB"}
        }
        """
        item_ids = request.data.get('item_ids', [])
        update_data = request.data.get('data', {})
        
        if not item_ids:
            return Response(
                {'error': 'Не указаны ID позиций'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            updated_count = ParsedItem.objects.filter(id__in=item_ids).update(**update_data)
            return Response({
                'updated_count': updated_count,
                'message': f'Обновлено позиций: {updated_count}'
            })
        except Exception as e:
            logger.error(f"Ошибка массового обновления: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Ошибка обновления: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        """
        Массовое удаление позиций.
        
        POST /api/items/bulk_delete/
        Body: {
            "item_ids": [1, 2, 3]
        }
        """
        item_ids = request.data.get('item_ids', [])
        
        if not item_ids:
            return Response(
                {'error': 'Не указаны ID позиций'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            deleted_count, _ = ParsedItem.objects.filter(id__in=item_ids).delete()
            return Response({
                'deleted_count': deleted_count,
                'message': f'Удалено позиций: {deleted_count}'
            })
        except Exception as e:
            logger.error(f"Ошибка массового удаления: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Ошибка удаления: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class OrderViewSet(viewsets.ModelViewSet):
    """ViewSet для работы с заказами. Список/просмотр — админ и бармен; создание и экспорт — только админ."""
    
    authentication_classes = [SessionAuthenticationNoCSRF]
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'export'):
            return [IsAuthenticated(), IsAdminOrBartender()]
        return [IsAuthenticated(), IsAdmin()]

    def get_queryset(self):
        queryset = super().get_queryset()
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        return queryset

    @staticmethod
    def _collect_order_item_map(orders):
        item_ids = {
            row.get('item_id') or row.get('id')
            for order in orders
            for row in (order.items or [])
            if row.get('item_id') or row.get('id')
        }
        return ParsedItem.objects.in_bulk(item_ids) if item_ids else {}

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        orders = page if page is not None else queryset
        item_map = self._collect_order_item_map(orders)
        serializer = self.get_serializer(
            orders,
            many=True,
            context={**self.get_serializer_context(), 'parsed_item_map': item_map},
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        item_map = self._collect_order_item_map([instance])
        serializer = self.get_serializer(
            instance,
            context={**self.get_serializer_context(), 'parsed_item_map': item_map},
        )
        return Response(serializer.data)

    def create(self, request):
        """
        Создает новый заказ.
        
        POST /api/orders/
        Body: {
            "items": [{"item_id": 1, "quantity": 5}, ...],
            "export_format": "excel"
        }
        """
        serializer = OrderCreateSerializer(data=request.data)
        if serializer.is_valid():
            order = Order.objects.create(
                items=serializer.validated_data['items'],
                export_format=serializer.validated_data['export_format']
            )
            return Response(
                OrderSerializer(order).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Агрегированная статистика по заказам за период.

        GET /api/orders/statistics/?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD
        """
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        qs = self.get_queryset().order_by('created_at')
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        orders = list(qs)
        item_map = self._collect_order_item_map(orders)

        total_orders = len(orders)
        total_sum = 0.0
        total_positions = 0
        item_sum = defaultdict(lambda: {'name': '', 'quantity': 0, 'sum': 0.0})
        item_order_dates = defaultdict(list)
        item_prices_by_date = defaultdict(list)

        for order in orders:
            order_date = order.created_at.date().isoformat()
            for row in order.items or []:
                item_id = row.get('item_id') or row.get('id')
                if not item_id:
                    continue

                qty = int(row.get('quantity') or 1)
                cached_item = item_map.get(item_id)

                price_val = None
                if row.get('price') is not None:
                    try:
                        price_val = float(row['price'])
                    except (TypeError, ValueError):
                        price_val = None
                if price_val is None and cached_item and cached_item.price is not None:
                    try:
                        price_val = float(cached_item.price)
                    except (TypeError, ValueError):
                        price_val = None

                item_name = (row.get('beer_name') or '').strip()
                if not item_name and cached_item:
                    item_name = (cached_item.beer_name or '').strip()
                if not item_name:
                    item_name = f'ID {item_id}'

                total_positions += qty
                line_sum = (price_val * qty) if (price_val is not None and price_val > 0) else 0.0
                total_sum += line_sum

                item_sum[item_id]['name'] = item_name
                item_sum[item_id]['quantity'] += qty
                item_sum[item_id]['sum'] += line_sum
                item_order_dates[item_id].append({'date': order_date, 'quantity': qty, 'order_id': order.id})
                if price_val is not None:
                    item_prices_by_date[item_id].append({'date': order_date, 'price': price_val})

        ranking_with_dates = []
        for item_id, values in item_sum.items():
            ranking_with_dates.append({
                'item_id': item_id,
                'name': values['name'],
                'total_quantity': values['quantity'],
                'total_sum': round(values['sum'], 2),
                'by_date': sorted(item_order_dates.get(item_id, []), key=lambda x: x['date']),
            })
        ranking_with_dates.sort(key=lambda x: -x['total_quantity'])

        price_trend = []
        for item_id, prices_list in item_prices_by_date.items():
            if len(prices_list) < 2:
                continue
            prices_list.sort(key=lambda x: x['date'])
            first_p = prices_list[0]['price']
            last_p = prices_list[-1]['price']
            if first_p <= 0:
                continue
            change_pct = round((last_p - first_p) / first_p * 100, 1)
            price_trend.append({
                'item_id': item_id,
                'name': item_sum.get(item_id, {}).get('name') or f'ID {item_id}',
                'first_date': prices_list[0]['date'],
                'first_price': round(first_p, 2),
                'last_date': prices_list[-1]['date'],
                'last_price': round(last_p, 2),
                'change_percent': change_pct,
            })
        price_trend.sort(key=lambda x: -abs(x['change_percent']))

        return Response({
            'total_orders': total_orders,
            'total_sum': round(total_sum, 2),
            'total_positions': total_positions,
            'average_order_sum': round(total_sum / total_orders, 2) if total_orders else 0,
            'ranking_with_dates': ranking_with_dates[:100],
            'price_trend': price_trend[:50],
        })
    
    @action(detail=True, methods=['get'])
    def export(self, request, pk=None):
        """
        Экспортирует заказ и возвращает файл для скачивания.
        
        GET /api/orders/<id>/export/
        """
        order = self.get_object()

        try:
            exporter = OrderExporter(order)
            exporter.export()
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except FileNotFoundError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            logger.exception('Ошибка экспорта заказа #%s', order.id)
            return Response(
                {'error': f'Ошибка экспорта: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if not order.export_file_path:
            return Response(
                {'error': 'Файл экспорта не был создан'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        file_path = Path(settings.MEDIA_ROOT) / order.export_file_path

        if not file_path.exists():
            return Response(
                {'error': 'Экспортированный файл не найден на сервере'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return FileResponse(
            open(file_path, 'rb'),
            as_attachment=True,
            filename=file_path.name,
        )


@api_view(['POST'])
@authentication_classes([SessionAuthenticationNoCSRF])
@permission_classes([IsAuthenticated, IsAdmin])
@parser_classes([MultiPartParser, FormParser])
def upload_file(request):
    """
    Загружает файл на сервер. Только админ.
    
    POST /api/upload/
    Body: multipart/form-data с полем 'file'
    """
    if 'file' not in request.FILES:
        return Response(
            {'error': 'Файл не предоставлен'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    uploaded_file = request.FILES['file']
    
    # Определяем тип файла
    file_type = detect_file_type(uploaded_file.name)
    
    if file_type == 'unknown':
        return Response(
            {'error': 'Неподдерживаемый тип файла'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Сохраняем файл
    upload_dir = Path(settings.MEDIA_ROOT) / 'uploads'
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = upload_dir / uploaded_file.name
    with open(file_path, 'wb+') as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)
    
    # Сохраняем относительный путь от MEDIA_ROOT
    relative_path = file_path.relative_to(settings.MEDIA_ROOT)
    
    # Если это ZIP, распаковываем
    if file_type == 'zip':
        extract_dir = upload_dir / f"{uploaded_file.name}_extracted"
        extract_dir.mkdir(exist_ok=True)
        extracted_files = extract_zip(str(file_path), str(extract_dir))
        
        # Создаем записи для каждого файла
        files = []
        for extracted_file in extracted_files:
            extracted_type = detect_file_type(extracted_file)
            if extracted_type != 'unknown':
                extracted_relative = Path(extracted_file).relative_to(settings.MEDIA_ROOT)
                file_obj = File.objects.create(
                    original_filename=Path(extracted_file).name,
                    file_type=extracted_type,
                    file_path=str(extracted_relative)
                )
                files.append(file_obj)
        
        serializer = FileSerializer(files, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    # Создаем запись о файле
    file_obj = File.objects.create(
        original_filename=uploaded_file.name,
        file_type=file_type,
        file_path=str(relative_path)
    )
    
    serializer = FileSerializer(file_obj)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


class TapLocationViewSet(viewsets.ModelViewSet):
    """ViewSet для работы с локациями кранов. Просмотр — все авторизованные; создание/изменение/удаление/экспорт — админ.
    SessionAuthenticationNoCSRF — SPA с сессионной cookie не шлёт CSRF-заголовок (как у FileViewSet / users).
    """
    
    authentication_classes = [SessionAuthenticationNoCSRF]
    queryset = TapLocation.objects.prefetch_related('taps', 'available_beers')

    def get_queryset(self):
        """
        Список локаций не тянет краны в память: один запрос + COUNT, без SELECT по таблице кранов.
        Так страница кранов открывается даже если миграции кранов отстают (иначе prefetch падал бы на новых колонках).
        """
        base = TapLocation.objects.all()
        if getattr(self, 'action', None) == 'list':
            return base.annotate(taps_count=Count('taps'))
        return base.prefetch_related('taps', 'available_beers')

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        if self.action == 'taps':
            return [IsAuthenticated()] if self.request.method == 'GET' else [IsAuthenticated(), IsAdmin()]
        return [IsAuthenticated(), IsAdmin()]

    def get_serializer_class(self):
        if self.action == 'list':
            return TapLocationListSerializer
        return TapLocationSerializer

    @action(detail=True, methods=['get', 'post'])
    def taps(self, request, pk=None):
        """
        Получение или добавление кранов локации.
        
        GET /api/locations/<id>/taps/ - список кранов
        POST /api/locations/<id>/taps/ - добавить кран
        """
        location = self.get_object()
        
        if request.method == 'GET':
            taps = location.taps.select_related('location').order_by('position')
            serializer = TapSerializer(taps, many=True)
            return Response(serializer.data)
        
        elif request.method == 'POST':
            # Определяем следующий номер крана
            max_position = location.taps.aggregate(
                max_pos=models.Max('position')
            )['max_pos'] or 0
            
            data = request.data.copy()
            data['location'] = location.id
            data['position'] = data.get('position', max_position + 1)
            
            serializer = TapSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def add_from_parser(self, request, pk=None):
        """
        Добавить позицию из парсера на кран.
        
        POST /api/locations/<id>/add_from_parser/
        Body: {"item_id": 123, "position": 1}
        """
        location = self.get_object()
        item_id = request.data.get('item_id')
        position = request.data.get('position')
        
        if not item_id:
            return Response(
                {'error': 'item_id обязателен'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            parsed_item = ParsedItem.objects.get(id=item_id)
        except ParsedItem.DoesNotExist:
            return Response(
                {'error': 'Позиция не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Определяем позицию
        if position:
            # Обновляем существующий кран
            tap, created = Tap.objects.update_or_create(
                location=location,
                position=position,
                defaults={
                    'brewery': parsed_item.brewery or '',
                    'beer_name': parsed_item.beer_name or '',
                    'price_per_liter': parsed_item.price,
                    'description': parsed_item.description or '',
                }
            )
        else:
            # Создаем новый кран
            max_position = location.taps.aggregate(
                max_pos=models.Max('position')
            )['max_pos'] or 0
            
            tap = Tap.objects.create(
                location=location,
                position=max_position + 1,
                brewery=parsed_item.brewery or '',
                beer_name=parsed_item.beer_name or '',
                price_per_liter=parsed_item.price,
                description=parsed_item.description or '',
            )
        
        serializer = TapSerializer(tap)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'])
    def export(self, request, pk=None):
        """
        Экспорт кранов локации в Excel.
        
        GET /api/locations/<id>/export/
        """
        location = self.get_object()
        
        try:
            exporter = TapsExporter(location)
            relative_path = exporter.export_to_excel()
            file_path = Path(settings.MEDIA_ROOT) / relative_path
            
            if not file_path.exists():
                return Response(
                    {'error': 'Файл не найден'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            return FileResponse(
                open(file_path, 'rb'),
                as_attachment=True,
                filename=file_path.name,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        except Exception as e:
            logger.error(f"Ошибка экспорта кранов: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Ошибка экспорта: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TapViewSet(viewsets.ModelViewSet):
    """ViewSet для работы с кранами. Роль «пользователь» — только чтение; бармен и админ — изменение полей.
    SessionAuthenticationNoCSRF — см. TapLocationViewSet.
    """
    
    authentication_classes = [SessionAuthenticationNoCSRF]
    queryset = Tap.objects.select_related('location')
    serializer_class = TapSerializer

    def get_permissions(self):
        if self.action in ('create', 'destroy'):
            return [IsAuthenticated(), IsAdmin()]
        if self.action == 'reorder':
            return [IsAuthenticated(), CanEditTapsContent()]
        return [IsAuthenticated()]

    def update(self, request, *args, **kwargs):
        """Обновление крана. Роль user не может менять краны (видимость настраивает персонал)."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        role = get_user_role(request.user)
        if role == UserProfile.ROLE_USER:
            return Response(
                {'detail': 'Недостаточно прав для изменения кранов.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        data = request.data

        # Сохраняем старые значения для истории
        old_brewery = instance.brewery
        old_beer_name = instance.beer_name
        old_price = instance.price_per_liter
        old_next_1 = instance.next_beer_1
        old_next_2 = instance.next_beer_2

        serializer = self.get_serializer(
            instance, data=data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        # Обновляем instance после сохранения
        instance.refresh_from_db()
        
        # Определяем тип изменения и сохраняем в историю
        change_type = self._determine_change_type(
            old_brewery, old_beer_name, old_price,
            instance.brewery, instance.beer_name, instance.price_per_liter
        )
        
        if change_type:
            from .models import TapChangeHistory
            TapChangeHistory.objects.create(
                tap=instance,
                change_type=change_type,
                old_brewery=old_brewery or '',
                old_beer_name=old_beer_name or '',
                old_price_per_liter=old_price,
                old_next_beer_1=old_next_1 or '',
                old_next_beer_2=old_next_2 or '',
                new_brewery=instance.brewery or '',
                new_beer_name=instance.beer_name or '',
                new_price_per_liter=instance.price_per_liter,
                new_next_beer_1=instance.next_beer_1 or '',
                new_next_beer_2=instance.next_beer_2 or '',
            )
        
        return Response(serializer.data)
    
    def _determine_change_type(self, old_brewery, old_beer_name, old_price,
                               new_brewery, new_beer_name, new_price):
        """
        Определяет тип изменения крана.
        
        Returns:
            Строка с типом изменения или None если изменений нет
        """
        # Проверяем установку нового пива
        if not old_brewery and not old_beer_name and (new_brewery or new_beer_name):
            return 'installed'
        
        # Проверяем убирание пива
        if (old_brewery or old_beer_name) and not new_brewery and not new_beer_name:
            return 'removed'
        
        # Проверяем изменение цены (если пиво не поменялось)
        if (old_brewery == new_brewery and old_beer_name == new_beer_name and
            old_price != new_price and (old_price or new_price)):
            return 'price_changed'
        
        # Проверяем смену пива
        if ((old_brewery != new_brewery or old_beer_name != new_beer_name) and
            (old_brewery or old_beer_name) and (new_brewery or new_beer_name)):
            return 'installed'
        
        # Общее обновление (если были изменения в других полях)
        if (old_brewery != new_brewery or old_beer_name != new_beer_name or
            old_price != new_price):
            return 'updated'
        
        return None
    
    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """
        Изменение порядка кранов.
        
        POST /api/taps/reorder/
        Body: {"location_id": 1, "tap_ids": [3, 1, 2]}
        """
        location_id = request.data.get('location_id')
        tap_ids = request.data.get('tap_ids', [])
        
        if not location_id or not tap_ids:
            return Response(
                {'error': 'location_id и tap_ids обязательны'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        for position, tap_id in enumerate(tap_ids, 1):
            Tap.objects.filter(
                id=tap_id, location_id=location_id
            ).update(position=position)
        
        return Response({'status': 'ok'})
    
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """
        Получение истории изменений крана.
        
        GET /api/taps/<id>/history/
        Query params: ?limit=50 (по умолчанию 50)
        """
        tap = self.get_object()
        limit = int(request.query_params.get('limit', 50))
        
        history = tap.change_history.all()[:limit]
        
        # Формируем ответ вручную для простоты
        history_data = []
        for entry in history:
            history_data.append({
                'id': entry.id,
                'change_type': entry.change_type,
                'change_type_display': entry.get_change_type_display(),
                'old_beer': f"{entry.old_brewery} {entry.old_beer_name}".strip() if entry.old_brewery or entry.old_beer_name else None,
                'new_beer': f"{entry.new_brewery} {entry.new_beer_name}".strip() if entry.new_brewery or entry.new_beer_name else None,
                'old_price': float(entry.old_price_per_liter) if entry.old_price_per_liter else None,
                'new_price': float(entry.new_price_per_liter) if entry.new_price_per_liter else None,
                'old_next_1': entry.old_next_beer_1,
                'old_next_2': entry.old_next_beer_2,
                'new_next_1': entry.new_next_beer_1,
                'new_next_2': entry.new_next_beer_2,
                'created_at': entry.created_at.isoformat(),
                'notes': entry.notes,
            })
        
        return Response(history_data)

    @action(detail=True, methods=['post'], url_path='fetch_untappd_label')
    def fetch_untappd_label(self, request, pk=None):
        """
        Подставить URL обложки с Untappd (поиск по названию и пивоварне на странице пива).

        POST /api/taps/<id>/fetch_untappd_label/
        """
        role = get_user_role(request.user)
        if role == UserProfile.ROLE_USER:
            return Response(
                {'detail': 'Недостаточно прав для изменения кранов.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        tap = self.get_object()
        beer_name = (tap.beer_name or '').strip()
        if not beer_name:
            return Response(
                {'detail': 'Укажите название пива на кране, чтобы искать на Untappd.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        brewery = (tap.brewery or '').strip() or None
        try:
            client = UntappdClient()
            image_url = client.get_beer_label_image_url(beer_name, brewery)
        except Exception as e:
            logger.exception('fetch_untappd_label')
            return Response(
                {'detail': f'Ошибка при обращении к Untappd: {e}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        if not image_url:
            return Response(
                {'detail': 'Не удалось найти обложку: проверьте название и пивоварню или задайте ссылку вручную через API.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        tap.label_image_url = image_url[:600]
        tap.save(update_fields=['label_image_url'])
        return Response(TapSerializer(tap).data)


class AvailableBeerViewSet(viewsets.ModelViewSet):
    """ViewSet для работы с доступным пивом. Просмотр — все; создание/изменение — админ.
    SessionAuthenticationNoCSRF — см. TapLocationViewSet.
    """
    
    authentication_classes = [SessionAuthenticationNoCSRF]
    queryset = AvailableBeer.objects.select_related('location')
    serializer_class = AvailableBeerSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        # Бармены редактируют краны — им нужен тот же доступ к «доступным позициям», что и в UI.
        return [IsAuthenticated(), CanEditTapsContent()]

    @staticmethod
    def _looks_like_keg(format_type, volume):
        fmt = (format_type or '').strip().lower()
        if not fmt and volume is None:
            return False
        if any(token in fmt for token in ('кег', 'keg', 'draft', 'tap', 'розлив')):
            return True
        if any(token in fmt for token in ('бан', 'can', 'бут', 'bottle')):
            return False
        try:
            return float(volume or 0) >= 15
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _volume_price_from_parsed(si: ParsedItem) -> str:
        parts = []
        if si.volume is not None:
            try:
                v = float(si.volume)
                parts.append(f'{int(v)} л' if v == int(v) else f'{v:g} л')
            except (TypeError, ValueError):
                pass
        if si.price is not None:
            try:
                p = float(si.price)
                cur = (si.currency or 'RUB').upper()
                if cur in ('RUB', ''):
                    parts.append(f'{int(round(p))} ₽')
                else:
                    parts.append(f'{p:g} {cur}'.strip())
            except (TypeError, ValueError):
                pass
        fmt = (si.format_type or '').strip()
        if fmt:
            parts.append(fmt)
        return ' · '.join(parts) if parts else ''

    @staticmethod
    def _ibu_from_parsed(si: ParsedItem) -> str:
        return (si.ibu or '').strip()[:64]

    @staticmethod
    def _abv_text_from_parsed(si: ParsedItem) -> str:
        if si.abv is None:
            return ''
        try:
            a = float(si.abv)
            if abs(a - round(a)) < 1e-6:
                return f'{int(round(a))} %'
            return f'{a:g} %'
        except (TypeError, ValueError):
            return ''

    def get_queryset(self):
        """Фильтрация по локации если указана."""
        queryset = super().get_queryset()
        location_id = self.request.query_params.get('location')
        if location_id:
            queryset = queryset.filter(location_id=location_id)
        return queryset

    def perform_create(self, serializer):
        loc = serializer.validated_data['location']
        max_so = AvailableBeer.objects.filter(location=loc).aggregate(m=models.Max('sort_order'))['m']
        next_so = (max_so + 1) if max_so is not None else 0
        serializer.save(sort_order=next_so)

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """
        Сохранить порядок доступных позиций для локации.

        POST /api/available-beers/reorder/
        Body: {"location_id": 1, "beer_ids": [3, 1, 2, ...]} — все id позиций локации в нужном порядке.
        """
        location_id = request.data.get('location_id')
        beer_ids = request.data.get('beer_ids', [])
        if not location_id or not beer_ids:
            return Response(
                {'error': 'location_id и beer_ids обязательны'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            loc_id_int = int(location_id)
            ordered_ids = [int(x) for x in beer_ids]
        except (TypeError, ValueError):
            return Response(
                {'error': 'location_id и элементы beer_ids должны быть числами'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(ordered_ids) != len(set(ordered_ids)):
            return Response(
                {'error': 'beer_ids не должны содержать дубликатов'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        beers = list(AvailableBeer.objects.filter(location_id=loc_id_int))
        if len(beers) != len(ordered_ids):
            return Response(
                {'error': f'Ожидалось {len(beers)} id позиций локации, передано {len(ordered_ids)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        by_id = {b.id for b in beers}
        if set(ordered_ids) != by_id:
            return Response(
                {'error': 'beer_ids должны совпадать с позициями выбранной локации'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        pos = {bid: i for i, bid in enumerate(ordered_ids)}
        for b in beers:
            b.sort_order = pos[b.id]
        AvailableBeer.objects.bulk_update(beers, ['sort_order'], batch_size=200)
        return Response({'status': 'ok'})
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """
        Массовое создание позиций.
        
        POST /api/available-beers/bulk_create/
        Body: {"location_id": 1, "items": [{"brewery": "...", "beer_name": "..."}]}
        """
        try:
            location_id = request.data.get('location_id')
            items = request.data.get('items', [])
            
            if not location_id or not items:
                return Response(
                    {'error': 'location_id и items обязательны'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Проверяем, что локация существует
            try:
                location = TapLocation.objects.get(id=location_id)
            except TapLocation.DoesNotExist:
                return Response(
                    {'error': f'Локация с id={location_id} не найдена'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Если фронт передал source_item_id — фильтруем строго по ParsedItem
            source_ids = set()
            for item in items:
                raw_source_id = item.get('source_item_id')
                if raw_source_id is None:
                    continue
                try:
                    source_ids.add(int(raw_source_id))
                except (TypeError, ValueError):
                    continue
            source_map = ParsedItem.objects.in_bulk(source_ids) if source_ids else {}

            max_so = AvailableBeer.objects.filter(location_id=location_id).aggregate(
                m=models.Max('sort_order')
            )['m']
            next_sort = (max_so + 1) if max_so is not None else 0

            created = []
            for item in items:
                source_item_id = item.get('source_item_id')
                try:
                    source_item_key = int(source_item_id) if source_item_id is not None else None
                except (TypeError, ValueError):
                    source_item_key = None
                source_item = source_map.get(source_item_key) if source_item_key is not None else None
                if source_item is not None:
                    if not self._looks_like_keg(source_item.format_type, source_item.volume):
                        continue

                price = item.get('price_per_liter')
                # Преобразуем цену в Decimal или None
                if price is not None:
                    try:
                        from decimal import Decimal
                        price = Decimal(str(price))
                    except (ValueError, TypeError):
                        price = None

                vp = (item.get('volume_price_text') or '').strip()[:200]
                ibu = (item.get('bitterness_ibu') or '').strip()[:64]
                abv = (item.get('abv_text') or '').strip()[:32]
                if source_item is not None:
                    if not vp:
                        vp = self._volume_price_from_parsed(source_item)[:200]
                    if not ibu:
                        ibu = self._ibu_from_parsed(source_item)
                    if not abv:
                        abv = self._abv_text_from_parsed(source_item)[:32]

                beer = AvailableBeer.objects.create(
                    location_id=location_id,
                    brewery=item.get('brewery', ''),
                    beer_name=item.get('beer_name', ''),
                    price_per_liter=price,
                    description=item.get('description') or (source_item.description if source_item else ''),
                    volume_price_text=vp,
                    bitterness_ibu=ibu,
                    abv_text=abv,
                    sort_order=next_sort,
                )
                next_sort += 1
                created.append(beer)
            
            serializer = AvailableBeerSerializer(created, many=True)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f'Ошибка при создании доступных пива: {str(e)}', exc_info=True)
            return Response(
                {'error': f'Ошибка сервера: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    """Управление пользователями (админ-панель). Только для роли admin. SessionAuthenticationNoCSRF — SPA с другого origin не шлёт CSRF токен."""
    authentication_classes = [SessionAuthenticationNoCSRF]
    permission_classes = [IsAuthenticated, IsAdmin]
    queryset = User.objects.all().order_by('id')
    serializer_class = UserSerializer

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        if self.action in ('update', 'partial_update'):
            return UserUpdateSerializer
        return UserSerializer

    def create(self, request, *args, **kwargs):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = UserUpdateSerializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        role = serializer.validated_data.get('role')
        first_name = serializer.validated_data.get('first_name')
        last_name = serializer.validated_data.get('last_name')
        email = serializer.validated_data.get('email')
        password = serializer.validated_data.get('password')
        if first_name is not None:
            instance.first_name = first_name
        if last_name is not None:
            instance.last_name = last_name
        if email is not None:
            instance.email = email
        if password:
            instance.set_password(password)
        instance.save()
        if role is not None:
            profile, _ = UserProfile.objects.get_or_create(user=instance, defaults={'role': role})
            profile.role = role
            profile.save()
        return Response(UserSerializer(instance).data)

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance == request.user:
            return Response(
                {'error': 'Нельзя удалить самого себя.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ParseRunViewSet(viewsets.ReadOnlyModelViewSet):
    """История запусков парсинга. Только admin."""
    authentication_classes = [SessionAuthenticationNoCSRF]
    permission_classes = [IsAuthenticated, IsAdmin]
    queryset = ParseRun.objects.select_related('file', 'supplier', 'user').order_by('-created_at')
    serializer_class = ParseRunSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        file_id = self.request.query_params.get('file_id')
        supplier_id = self.request.query_params.get('supplier_id')
        if file_id:
            qs = qs.filter(file_id=file_id)
        if supplier_id:
            qs = qs.filter(supplier_id=supplier_id)
        return qs

    @action(detail=False, methods=['get'])
    def drift(self, request):
        """Сводка drift по shadow-замерам (delta item count)."""
        qs = self.get_queryset().filter(summary__shadow__isnull=False)[:200]
        total = qs.count()
        with_shadow = 0
        deltas = []
        for run in qs:
            shadow = (run.summary or {}).get('shadow') or {}
            if shadow:
                with_shadow += 1
                delta = shadow.get('delta')
                if isinstance(delta, (int, float)):
                    deltas.append(delta)
        avg_delta = (sum(deltas) / len(deltas)) if deltas else 0
        return Response({
            'total_runs': total,
            'runs_with_shadow': with_shadow,
            'avg_delta': avg_delta,
            'max_abs_delta': max((abs(d) for d in deltas), default=0),
        })

    @action(detail=False, methods=['get'])
    def canary_gate(self, request):
        """
        Простой canary gate по shadow-дельте.
        Query:
          - limit (default 20)
          - max_abs_delta (default 20)
        """
        limit = int(request.query_params.get('limit', 20))
        threshold = float(request.query_params.get('max_abs_delta', 20))
        min_avg_confidence = float(request.query_params.get('min_avg_confidence', 3.0))
        auto_rollback = str(request.query_params.get('auto_rollback', 'true')).lower() in {'1', 'true', 'yes'}
        rollback_ttl_seconds = int(request.query_params.get('rollback_ttl_seconds', 1800))
        qs = self.get_queryset().filter(summary__shadow__isnull=False)[:limit]
        deltas = []
        confidence_values = []
        for run in qs:
            shadow = (run.summary or {}).get('shadow') or {}
            delta = shadow.get('delta')
            if isinstance(delta, (int, float)):
                deltas.append(float(delta))
            conf_dict = ((run.summary or {}).get('meta') or {}).get('column_mapping_confidence') or {}
            if not conf_dict:
                conf_dict = (shadow.get('secondary_meta') or {}).get('column_mapping_confidence') or {}
            if isinstance(conf_dict, dict):
                for val in conf_dict.values():
                    if isinstance(val, (int, float)):
                        confidence_values.append(float(val))
        max_abs = max((abs(d) for d in deltas), default=0.0)
        avg_conf = (sum(confidence_values) / len(confidence_values)) if confidence_values else 0.0
        passed = (max_abs <= threshold) and (avg_conf >= min_avg_confidence)

        rollback_applied = False
        rollback_reason = None
        if auto_rollback and not passed:
            cache.set('parser_canary_force_legacy', True, timeout=rollback_ttl_seconds)
            rollback_applied = True
            rollback_reason = 'canary_failed'
        elif passed:
            cache.delete('parser_canary_force_legacy')

        return Response({
            'passed': passed,
            'sample_size': len(deltas),
            'threshold_max_abs_delta': threshold,
            'observed_max_abs_delta': max_abs,
            'threshold_min_avg_confidence': min_avg_confidence,
            'observed_avg_confidence': avg_conf,
            'recent_deltas': deltas,
            'confidence_samples': confidence_values,
            'canary_force_legacy': bool(cache.get('parser_canary_force_legacy', False)),
            'rollback_applied': rollback_applied,
            'rollback_reason': rollback_reason,
            'rollback_ttl_seconds': rollback_ttl_seconds if rollback_applied else 0,
        })

    @action(detail=False, methods=['post'])
    def canary_reset(self, request):
        """Сбросить принудительный rollback на legacy-парсер."""
        cache.delete('parser_canary_force_legacy')
        return Response({'status': 'ok', 'canary_force_legacy': False})

    @action(detail=True, methods=['get'])
    def recommendations(self, request, pk=None):
        """
        Рекомендации по неоднозначному маппингу колонок для конкретного ParseRun.
        """
        run = self.get_object()
        meta = (run.summary or {}).get('meta') or {}
        candidates_by_sheet = meta.get('column_mapping_candidates') or {}
        if not candidates_by_sheet:
            shadow = (run.summary or {}).get('shadow') or {}
            candidates_by_sheet = (shadow.get('secondary_meta') or {}).get('column_mapping_candidates') or {}

        ambiguity_gap = float(request.query_params.get('ambiguity_gap', 1.0))
        min_score = float(request.query_params.get('min_score', 1.0))
        recs = []
        for sheet_name, field_opts in (candidates_by_sheet or {}).items():
            if not isinstance(field_opts, dict):
                continue
            for field_name, options in field_opts.items():
                if not isinstance(options, list) or not options:
                    continue
                top = options[0]
                second = options[1] if len(options) > 1 else None
                top_score = float(top.get('score', 0))
                second_score = float(second.get('score', 0)) if second else 0.0
                if top_score < min_score:
                    continue
                if second and abs(top_score - second_score) <= ambiguity_gap:
                    recs.append({
                        'sheet': sheet_name,
                        'field': field_name,
                        'recommended_header': top.get('header'),
                        'recommended_column_index': top.get('column_index'),
                        'top_score': top_score,
                        'second_best': second,
                        'all_candidates': options[:3],
                    })

        return Response({
            'parse_run_id': run.id,
            'ambiguity_gap': ambiguity_gap,
            'min_score': min_score,
            'recommendations': recs,
            'count': len(recs),
        })


class SupplierColumnMappingViewSet(viewsets.ModelViewSet):
    """CRUD ручных маппингов колонок. Только admin."""
    authentication_classes = [SessionAuthenticationNoCSRF]
    permission_classes = [IsAuthenticated, IsAdmin]
    queryset = SupplierColumnMapping.objects.select_related('supplier').order_by('-updated_at')
    serializer_class = SupplierColumnMappingSerializer


class ParsingFeedbackViewSet(viewsets.ModelViewSet):
    """CRUD feedback по сопоставлению колонок. Только admin."""
    authentication_classes = [SessionAuthenticationNoCSRF]
    permission_classes = [IsAuthenticated, IsAdmin]
    queryset = ParsingFeedback.objects.select_related('supplier', 'parse_run', 'user').order_by('-created_at')
    serializer_class = ParsingFeedbackSerializer

    def perform_create(self, serializer):
        feedback = serializer.save(user=self.request.user)
        auto_promote = str(self.request.query_params.get('auto_promote', 'true')).lower() in {'1', 'true', 'yes'}
        if auto_promote and feedback.accepted:
            try:
                promote_feedback_to_mapping(
                    feedback,
                    scope=self.request.query_params.get('scope') or SupplierColumnMapping.SCOPE_SUPPLIER,
                    confidence=self.request.query_params.get('confidence'),
                )
            except Exception as exc:
                logger.warning(f"Auto-promote feedback #{feedback.id} skipped: {exc}")

    @action(detail=True, methods=['post'])
    def promote(self, request, pk=None):
        """
        Promote accepted feedback into SupplierColumnMapping.
        Body (optional): {"scope":"global|supplier|exact_file","confidence":0.95}
        """
        feedback = self.get_object()
        if not feedback.accepted:
            return Response(
                {'error': 'Можно продвигать только accepted feedback.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        scope = request.data.get('scope') or SupplierColumnMapping.SCOPE_SUPPLIER
        confidence = request.data.get('confidence', feedback.confidence)
        try:
            mapping, created = promote_feedback_to_mapping(feedback, scope=scope, confidence=confidence)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                'status': 'created' if created else 'updated',
                'mapping': SupplierColumnMappingSerializer(mapping).data,
            },
            status=status.HTTP_200_OK,
        )

