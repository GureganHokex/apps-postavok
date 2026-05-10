"""
API views для парсинга прайсов и работы с заказами.
"""

import os
import zipfile
import logging
import traceback
from pathlib import Path
from django.conf import settings
from django.db import models
from collections import defaultdict
from django.http import FileResponse, JsonResponse
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, parser_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from parser_app.models import (
    File, ParsedItem, FileMetadata, Order, 
    TapLocation, Tap, AvailableBeer, TapChangeHistory
)
from parser_app.presentation.validators.parsed_item_validator import ParsedItemValidator
from parser_app.presentation.api.serializers import (
    FileSerializer, ParsedItemSerializer, FileMetadataSerializer,
    OrderSerializer, OrderCreateSerializer, TapLocationSerializer,
    TapLocationListSerializer, TapSerializer, AvailableBeerSerializer
)
from parser_app.infrastructure.parsers.pdf_parser import PDFParser
from parser_app.infrastructure.parsers.excel_parser import ExcelParser
from parser_app.infrastructure.parsers.google_sheets_parser import GoogleSheetsParser
from parser_app.presentation.filters.contact_filter import ContactFilter
from parser_app.domain.services.normalization import DataNormalizer
from parser_app.infrastructure.exporters.order_exporter import OrderExporter
from parser_app.infrastructure.exporters.taps_exporter import TapsExporter
from parser_app.shared.utils import detect_file_type, extract_zip
from parser_app.infrastructure.external.untappd_client import UntappdClient
from parser_app.application.use_cases.parsing_service import ParsingService
from parser_app.shared.constants import CACHE_TIMEOUT_PARSE_PROGRESS

logger = logging.getLogger(__name__)


class FileViewSet(viewsets.ModelViewSet):
    """ViewSet для работы с файлами."""
    
    queryset = File.objects.all()
    serializer_class = FileSerializer
    
    @action(detail=True, methods=['post'])
    def parse(self, request, pk=None):
        """
        Запускает парсинг файла.
        
        POST /api/files/<id>/parse/
        Body (опционально): {
            "supplier_type": "distributor" | "brewery",
            "brewery_name": "Dieta"  # только для brewery
        }
        """
        file_obj = self.get_object()
        
        # Создаем ключ для прогресса парсинга
        progress_key = f'parse_progress_{file_obj.id}'
        
        # Получаем информацию о поставщике из запроса
        supplier_type_from_request = request.data.get('supplier_type')
        brewery_name_from_request = request.data.get('brewery_name')
        
        # Инициализируем прогресс
        try:
            cache.set(progress_key, {
                'status': 'starting',
                'progress': 0,
                'message': 'Инициализация парсинга...',
                'total_items': 0,
                'processed_items': 0,
            }, timeout=CACHE_TIMEOUT_PARSE_PROGRESS)
        except Exception as cache_err:
            logger.warning(f"Ошибка инициализации прогресса в кэше: {cache_err}")
        
        # Используем сервис парсинга
        try:
            parsing_service = ParsingService()
            product_items, metadata_summary = parsing_service.parse_file(
                file_obj=file_obj,
                supplier_type=supplier_type_from_request,
                brewery_name=brewery_name_from_request,
                progress_key=progress_key
            )
            
            return Response({
                'message': 'Парсинг завершен',
                'items_created': len(product_items),
                'skipped_rows': metadata_summary.get('skipped_rows', 0),
                'summary': metadata_summary
            })
        except ValueError as e:
            logger.error(f"Ошибка валидации при парсинге файла {file_obj.original_filename}: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            error_traceback = traceback.format_exc()
            logger.error(
                f"Ошибка парсинга файла {file_obj.original_filename}: {str(e)}\n{error_traceback}",
                exc_info=True
            )
            return Response(
                {'error': f'Ошибка парсинга: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def parse_progress(self, request, pk=None):
        """
        Получение прогресса парсинга файла.
        
        GET /api/files/<id>/parse_progress/
        """
        file_obj = self.get_object()
        progress_key = f'parse_progress_{file_obj.id}'
        
        progress = cache.get(progress_key)
        
        if not progress:
            return Response({
                'status': 'not_started',
                'progress': 0,
                'message': 'Парсинг не запущен',
                'total_items': 0,
                'processed_items': 0,
            })
        
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


class ParsedItemViewSet(viewsets.ModelViewSet):
    """ViewSet для работы с распарсенными позициями."""
    
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
    """ViewSet для работы с заказами."""
    
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    
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
            raw_items = serializer.validated_data['items']
            enriched = []
            for row in raw_items:
                item_id = row.get('item_id')
                qty = int(row.get('quantity') or 1)
                snap = {'item_id': item_id, 'quantity': qty}
                try:
                    item = ParsedItem.objects.get(pk=item_id)
                    if item.price is not None:
                        try:
                            snap['price'] = float(item.price)
                        except (TypeError, ValueError):
                            pass
                    if item.beer_name:
                        snap['beer_name'] = item.beer_name
                    if item.brewery:
                        snap['brewery'] = item.brewery
                    if item.format_type:
                        snap['format_type'] = item.format_type
                    if isinstance(item.raw_source_location, dict) and item.raw_source_location.get('sheet'):
                        snap['sheet'] = item.raw_source_location['sheet']
                except ParsedItem.DoesNotExist:
                    pass
                enriched.append(snap)
            order = Order.objects.create(
                items=enriched,
                export_format=serializer.validated_data['export_format']
            )
            return Response(
                OrderSerializer(order).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def export(self, request, pk=None):
        """
        Экспортирует заказ и возвращает файл для скачивания.
        
        GET /api/orders/<id>/export/
        """
        order = self.get_object()
        
        # Всегда экспортируем заново для актуального имени файла
        exporter = OrderExporter(order)
        exporter.export()
        
        # Путь к файлу
        file_path = Path(settings.MEDIA_ROOT) / order.export_file_path
        
        if not file_path.exists():
            return Response(
                {'error': 'Экспортированный файл не найден'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Возвращаем файл для скачивания
        return FileResponse(
            open(file_path, 'rb'),
            as_attachment=True,
            filename=file_path.name
        )

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Агрегированная статистика по заказам за период.

        GET /api/orders/statistics/?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD

        Возвращает: по листам (кеги/фасовка), по формату, тренд цен, рейтинг заказов по позициям с датами.
        """
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        qs = Order.objects.all().order_by('created_at')
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        orders = list(qs)
        total_orders = len(orders)
        total_sum = 0
        total_positions = 0
        brewery_sum = defaultdict(lambda: {'count': 0, 'sum': 0})
        item_sum = defaultdict(lambda: {'name': '', 'quantity': 0, 'sum': 0})
        by_sheet = defaultdict(lambda: {'count': 0, 'sum': 0, 'quantity': 0})
        by_format = defaultdict(lambda: {'count': 0, 'sum': 0, 'quantity': 0})
        item_order_dates = defaultdict(list)
        item_prices_by_date = defaultdict(list)

        for order in orders:
            order_date = order.created_at.date().isoformat()
            for row in order.items or []:
                item_id = row.get('item_id') or row.get('id')
                qty = int(row.get('quantity') or 1)
                if not item_id:
                    continue
                price_val = None
                if row.get('price') is not None:
                    try:
                        price_val = float(row['price'])
                    except (TypeError, ValueError):
                        pass
                sheet_name = (row.get('sheet') or '').strip() or 'Без листа'
                format_name = (row.get('format_type') or '').strip() or 'Не указано'
                name = (row.get('beer_name') or '').strip()
                brewery = (row.get('brewery') or '').strip()

                try:
                    item = ParsedItem.objects.get(pk=item_id)
                except ParsedItem.DoesNotExist:
                    item = None
                if price_val is None and item and item.price is not None:
                    try:
                        price_val = float(item.price)
                    except (TypeError, ValueError):
                        pass
                if not name and item:
                    name = (item.beer_name or '').strip() or f'ID {item.id}'
                if not brewery and item:
                    brewery = (item.brewery or '').strip() or 'Не указано'
                if not sheet_name or sheet_name == 'Без листа':
                    if item and isinstance(item.raw_source_location, dict) and item.raw_source_location.get('sheet'):
                        sheet_name = item.raw_source_location['sheet']
                if not format_name or format_name == 'Не указано':
                    if item and item.format_type:
                        format_name = item.format_type

                total_positions += qty
                line_sum = (price_val * qty) if (price_val is not None and price_val > 0) else 0
                if price_val is not None and price_val > 0:
                    total_sum += line_sum
                    brewery_sum[brewery]['count'] += qty
                    brewery_sum[brewery]['sum'] += line_sum
                by_sheet[sheet_name]['quantity'] += qty
                by_sheet[sheet_name]['sum'] += line_sum
                by_sheet[sheet_name]['count'] += 1
                by_format[format_name]['quantity'] += qty
                by_format[format_name]['sum'] += line_sum
                by_format[format_name]['count'] += 1
                item_sum[item_id]['name'] = name or f'ID {item_id}'
                item_sum[item_id]['quantity'] = item_sum[item_id]['quantity'] + qty
                item_sum[item_id]['sum'] = item_sum[item_id]['sum'] + line_sum
                item_order_dates[item_id].append({'date': order_date, 'quantity': qty, 'order_id': order.id})
                if price_val is not None:
                    item_prices_by_date[item_id].append({'date': order_date, 'price': price_val})

        top_breweries = sorted(
            [{'name': k, 'count': v['count'], 'sum': round(v['sum'], 2)} for k, v in brewery_sum.items()],
            key=lambda x: -x['sum']
        )[:10]
        top_items = sorted(
            [{'item_id': k, 'name': v['name'], 'quantity': v['quantity'], 'sum': round(v['sum'], 2)} for k, v in item_sum.items()],
            key=lambda x: -x['sum']
        )[:15]

        by_sheet_list = sorted(
            [{'sheet': k, 'quantity': v['quantity'], 'count': v['count'], 'sum': round(v['sum'], 2)} for k, v in by_sheet.items()],
            key=lambda x: -x['sum']
        )
        by_format_list = sorted(
            [{'format': k, 'quantity': v['quantity'], 'count': v['count'], 'sum': round(v['sum'], 2)} for k, v in by_format.items()],
            key=lambda x: -x['sum']
        )

        ranking_with_dates = []
        for item_id, v in item_sum.items():
            dates = item_order_dates.get(item_id, [])
            ranking_with_dates.append({
                'item_id': item_id,
                'name': v['name'],
                'total_quantity': v['quantity'],
                'total_sum': round(v['sum'], 2),
                'by_date': sorted(dates, key=lambda x: x['date']),
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

        orders_by_day = defaultdict(lambda: {'count': 0, 'sum': 0})
        for order in orders:
            day = order.created_at.date().isoformat()
            orders_by_day[day]['count'] += 1
            day_sum = 0
            for row in order.items or []:
                item_id = row.get('item_id') or row.get('id')
                qty = int(row.get('quantity') or 1)
                price_val = row.get('price')
                if price_val is None and item_id:
                    try:
                        item = ParsedItem.objects.get(pk=item_id)
                        price_val = float(item.price) if item.price is not None else None
                    except ParsedItem.DoesNotExist:
                        pass
                if price_val is not None and qty:
                    day_sum += float(price_val) * qty
            orders_by_day[day]['sum'] += day_sum
        by_day = [{'date': k, 'orders_count': v['count'], 'sum': round(v['sum'], 2)} for k, v in sorted(orders_by_day.items())]

        return Response({
            'total_orders': total_orders,
            'total_sum': round(total_sum, 2),
            'total_positions': total_positions,
            'average_order_sum': round(total_sum / total_orders, 2) if total_orders else 0,
            'top_breweries': top_breweries,
            'top_items': top_items,
            'by_day': by_day,
            'by_sheet': by_sheet_list,
            'by_format': by_format_list,
            'ranking_with_dates': ranking_with_dates[:50],
            'price_trend': price_trend[:30],
        })


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def upload_file(request):
    """
    Загружает файл на сервер.
    
    POST /api/upload/
    Body: multipart/form-data с полем 'file'

    Пока ответ не отправлен, клиент ждёт полного приёма тела + запись на диск; для ZIP дополнительно
    синхронная распаковка — при прокси Vercel→Render возможен 502/HTML при очень больших архивах или
    медленном канале (лимиты шлюза). Парсинг вынесен в POST /parse/ (202); тяжёлую работу после upload
    держать здесь минимальной.
    """
    try:
        if 'file' not in request.FILES:
            return Response(
                {'error': 'Файл не предоставлен'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        uploaded_file = request.FILES['file']
        logger.info(f"Начало загрузки файла: {uploaded_file.name}, размер: {uploaded_file.size} байт")
        
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
        try:
            with open(file_path, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            logger.info(f"Файл {uploaded_file.name} успешно сохранен в {file_path}")
        except Exception as save_error:
            logger.error(f"Ошибка сохранения файла {uploaded_file.name}: {str(save_error)}", exc_info=True)
            return Response(
                {'error': f'Ошибка сохранения файла: {str(save_error)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
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
        try:
            file_obj = File.objects.create(
                original_filename=uploaded_file.name,
                file_type=file_type,
                file_path=str(relative_path)
            )
            logger.info(f"Создана запись о файле: ID={file_obj.id}, тип={file_type}")
        except Exception as create_error:
            logger.error(f"Ошибка создания записи о файле {uploaded_file.name}: {str(create_error)}", exc_info=True)
            return Response(
                {'error': f'Ошибка создания записи о файле: {str(create_error)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        serializer = FileSerializer(file_obj)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"Критическая ошибка при загрузке файла: {str(e)}\n{error_traceback}", exc_info=True)
        return Response(
            {'error': f'Ошибка загрузки файла: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class TapLocationViewSet(viewsets.ModelViewSet):
    """ViewSet для работы с локациями кранов."""
    
    queryset = TapLocation.objects.prefetch_related('taps', 'available_beers')
    
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
    """ViewSet для работы с кранами."""
    
    queryset = Tap.objects.select_related('location')
    serializer_class = TapSerializer
    
    def update(self, request, *args, **kwargs):
        """Обновление крана."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        # Сохраняем старые значения для истории
        old_brewery = instance.brewery
        old_beer_name = instance.beer_name
        old_price = instance.price_per_liter
        old_next_1 = instance.next_beer_1
        old_next_2 = instance.next_beer_2
        
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial
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
            from parser_app.models import TapChangeHistory
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


class AvailableBeerViewSet(viewsets.ModelViewSet):
    """ViewSet для работы с доступным пивом."""
    
    queryset = AvailableBeer.objects.select_related('location')
    serializer_class = AvailableBeerSerializer
    
    def get_queryset(self):
        """Фильтрация по локации если указана."""
        queryset = super().get_queryset()
        location_id = self.request.query_params.get('location')
        if location_id:
            queryset = queryset.filter(location_id=location_id)
        return queryset
    
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
            
            created = []
            for item in items:
                price = item.get('price_per_liter')
                # Преобразуем цену в Decimal или None
                if price is not None:
                    try:
                        from decimal import Decimal
                        price = Decimal(str(price))
                    except (ValueError, TypeError):
                        price = None
                
                beer = AvailableBeer.objects.create(
                    location_id=location_id,
                    brewery=item.get('brewery', ''),
                    beer_name=item.get('beer_name', ''),
                    price_per_liter=price,
                )
                created.append(beer)
            
            serializer = AvailableBeerSerializer(created, many=True)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f'Ошибка при создании доступных пива: {str(e)}', exc_info=True)
            return Response(
                {'error': f'Ошибка сервера: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

