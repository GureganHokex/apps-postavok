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
from django.http import FileResponse, JsonResponse
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, parser_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from .models import (
    File, ParsedItem, FileMetadata, Order, Supplier,
    TapLocation, Tap, AvailableBeer, TapChangeHistory
)
from .validators import ParsedItemValidator
from .serializers import (
    FileSerializer, ParsedItemSerializer, FileMetadataSerializer,
    OrderSerializer, OrderCreateSerializer, SupplierSerializer,
    TapLocationSerializer, TapLocationListSerializer, TapSerializer, AvailableBeerSerializer
)
from .parsers.pdf_parser import PDFParser
from .parsers.excel_parser import ExcelParser
from .parsers.google_sheets_parser import GoogleSheetsParser
from .filters import ContactFilter
from .normalizers import DataNormalizer
from .exporters import OrderExporter, TapsExporter
from .utils import detect_file_type, extract_zip
from .untappd_client import UntappdClient

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
        supplier_id_from_request = request.data.get('supplier_id')
        supplier_column_mapping = None
        if supplier_id_from_request:
            try:
                supplier = get_object_or_404(Supplier, pk=supplier_id_from_request)
                supplier_column_mapping = supplier.column_mapping or {}
                logger.info(f"Используется маппинг поставщика: {supplier.name}")
            except Exception as e:
                logger.warning(f"Не удалось загрузить поставщика {supplier_id_from_request}: {e}")
        
        # Инициализируем прогресс
        cache.set(progress_key, {
            'status': 'starting',
            'progress': 0,
            'message': 'Инициализация парсинга...',
            'total_items': 0,
            'processed_items': 0,
        }, timeout=600)  # 10 минут
        
        # Определяем парсер в зависимости от типа файла
        parser = None
        # Получаем полный путь к файлу
        file_full_path = Path(settings.MEDIA_ROOT) / file_obj.file_path
        if file_obj.file_type == 'pdf':
            parser = PDFParser(str(file_full_path))
        elif file_obj.file_type == 'excel':
            parser = ExcelParser(str(file_full_path))
        elif file_obj.file_type == 'google_sheets':
            parser = GoogleSheetsParser(
                str(file_full_path),
                file_obj.google_sheet_url
            )
        
        if not parser:
            return Response(
                {'error': 'Неизвестный тип файла'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Парсим файл с переданной информацией о поставщике
        try:
            logger.info(
                f"Начало парсинга файла {file_obj.original_filename} "
                f"(тип: {file_obj.file_type}, supplier_type: {supplier_type_from_request}, "
                f"brewery_name: {brewery_name_from_request})"
            )
            
            # Передаем информацию о поставщике в парсер
            parse_kwargs = {}
            if supplier_type_from_request:
                parse_kwargs['supplier_type'] = supplier_type_from_request
            if brewery_name_from_request:
                parse_kwargs['brewery_name'] = brewery_name_from_request
            if supplier_column_mapping is not None:
                parse_kwargs['supplier_column_mapping'] = supplier_column_mapping
            
            # Обновляем прогресс - парсинг начался
            try:
                cache.set(progress_key, {
                    'status': 'parsing',
                    'progress': 10,
                    'message': 'Парсинг файла...',
                    'total_items': 0,
                    'processed_items': 0,
                }, timeout=600)
            except Exception as cache_err:
                logger.warning(f"Ошибка обновления прогресса в кэше: {cache_err}")
            
            raw_items = parser.parse(**parse_kwargs)
            logger.info(f"Парсинг завершен, извлечено {len(raw_items)} позиций")
            
            # Обновляем прогресс - парсинг завершен, начинаем обработку
            total_items = len(raw_items)
            try:
                cache.set(progress_key, {
                    'status': 'processing',
                    'progress': 30,
                    'message': f'Обработка {total_items} позиций...',
                    'total_items': total_items,
                    'processed_items': 0,
                }, timeout=600)
            except Exception as cache_err:
                logger.warning(f"Ошибка обновления прогресса в кэше: {cache_err}")
        except Exception as e:
            error_traceback = traceback.format_exc()
            logger.error(f"Ошибка парсинга файла {file_obj.original_filename}: {str(e)}\n{error_traceback}", exc_info=True)
            return Response(
                {'error': f'Ошибка парсинга: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Фильтруем и нормализуем данные
        contact_filter = ContactFilter()
        normalizer = DataNormalizer()
        
        all_contacts = {
            'phones': [],
            'emails': [],
            'addresses': [],
            'links': []
        }
        extra_texts = []
        product_items = []
        
        # Инициализируем валидатор
        validator = ParsedItemValidator()
        validation_items = []  # Для валидации после парсинга
        skipped_count = 0
        total_items_count = len(raw_items)
        
        for idx, raw_item in enumerate(raw_items):
            # Обновляем прогресс каждые 10 позиций или на последней
            if idx % 10 == 0 or idx == total_items_count - 1:
                try:
                    progress = 30 + int((idx + 1) / total_items_count * 60) if total_items_count > 0 else 30
                    cache.set(progress_key, {
                        'status': 'processing',
                        'progress': progress,
                        'message': f'Обработка позиций: {idx + 1} из {total_items_count}',
                        'total_items': total_items_count,
                        'processed_items': idx + 1,
                    }, timeout=600)
                except Exception as cache_err:
                    logger.warning(f"Ошибка обновления прогресса в кэше: {cache_err}")
            # Собираем текст строки для фильтрации
            row_text = ' '.join(str(v) for v in raw_item.values() if v)
            
            # Проверяем, является ли строка товарной
            is_product, contacts = contact_filter.filter_row(raw_item, row_text)
            
            if is_product:
                # Нормализуем данные
                normalized_item = normalizer.normalize_item(raw_item)
                
                # ВАЖНО: Если brewery было установлено в парсере, но нормализация его удалила,
                # восстанавливаем его из raw_item
                if 'brewery' in raw_item and raw_item['brewery']:
                    if not normalized_item.get('brewery'):
                        # Пробуем нормализовать brewery из raw_item
                        brewery_from_raw = normalizer.normalize_brewery(raw_item['brewery'])
                        if brewery_from_raw and brewery_from_raw.strip():
                            normalized_item['brewery'] = brewery_from_raw
                        elif raw_item['brewery'].strip():
                            # Если нормализация удалила brewery (например, посчитала городом),
                            # используем оригинальное значение
                            normalized_item['brewery'] = raw_item['brewery'].strip()
                    else:
                        # Если brewery уже есть в normalized_item, проверяем, что оно не пустое
                        if not normalized_item['brewery'] or not normalized_item['brewery'].strip():
                            # Восстанавливаем из raw_item
                            brewery_from_raw = normalizer.normalize_brewery(raw_item['brewery'])
                            if brewery_from_raw and brewery_from_raw.strip():
                                normalized_item['brewery'] = brewery_from_raw
                            else:
                                normalized_item['brewery'] = raw_item['brewery'].strip()
                elif 'brewery' not in normalized_item and 'brewery' in raw_item and raw_item['brewery']:
                    # Если brewery было в raw_item, но не попало в normalized_item, добавляем его
                    brewery_from_raw = normalizer.normalize_brewery(raw_item['brewery'])
                    if brewery_from_raw and brewery_from_raw.strip():
                        normalized_item['brewery'] = brewery_from_raw
                    else:
                        normalized_item['brewery'] = raw_item['brewery'].strip()
                
                normalized_item['file'] = file_obj
                
                # Валидация числовых полей перед сохранением
                # Убеждаемся, что abv, price, volume либо валидные числа, либо None
                for field in ['abv', 'price', 'volume']:
                    if field in normalized_item:
                        value = normalized_item[field]
                        # Если значение - строка, пытаемся преобразовать в число
                        if isinstance(value, str):
                            value_stripped = value.strip().lower()
                            # Пропускаем служебные строки
                            if value_stripped in ['', '-', '—', '–', 'nan', 'none', 'null', 'n/a', 'na', 'хх', 'xx', 'н/д', 'н.д.']:
                                normalized_item[field] = None
                            else:
                                # Пытаемся извлечь число из строки
                                from .utils import safe_float
                                if field == 'price':
                                    from decimal import Decimal, InvalidOperation
                                    try:
                                        float_val = safe_float(value)
                                        if float_val is not None:
                                            normalized_item[field] = Decimal(str(float_val))
                                        else:
                                            normalized_item[field] = None
                                    except (ValueError, InvalidOperation):
                                        normalized_item[field] = None
                                else:
                                    normalized_item[field] = safe_float(value)
                        elif value is not None:
                            # Проверяем, что это валидное число
                            try:
                                if field == 'price':
                                    from decimal import Decimal, InvalidOperation
                                    normalized_item[field] = Decimal(str(value))
                                else:
                                    float(value)  # Просто проверяем, что можно преобразовать
                            except (ValueError, TypeError, InvalidOperation):
                                normalized_item[field] = None
                
                # Если стиль отсутствует, пытаемся найти его через Untappd (веб-скрейпинг или эвристика)
                if not normalized_item.get('style') or not normalized_item.get('style', '').strip():
                    beer_name = normalized_item.get('beer_name', '').strip()
                    brewery_name = normalized_item.get('brewery', '').strip()
                    description = normalized_item.get('description', '').strip()
                    
                    if beer_name:
                        try:
                            untappd_client = UntappdClient()
                            style_from_untappd = None
                            
                            # Сначала пробуем эвристику по названию пива (приоритет выше описания)
                            beer_name_lower = beer_name.lower()
                            if 'берлинер вайссе' in beer_name_lower or 'berliner weisse' in beer_name_lower or 'berliner weisse' in beer_name_lower:
                                style_from_untappd = 'Berliner Weisse'
                            elif 'гозэ' in beer_name_lower or 'гозе' in beer_name_lower or 'gose' in beer_name_lower:
                                style_from_untappd = 'Gose'
                            elif 'саур' in beer_name_lower or 'sour' in beer_name_lower:
                                if 'эль' in beer_name_lower or 'ale' in beer_name_lower:
                                    style_from_untappd = 'Sour Ale'
                                else:
                                    style_from_untappd = 'Sour Ale'
                            elif 'стаут' in beer_name_lower or 'stout' in beer_name_lower:
                                if 'имперский' in beer_name_lower or 'imperial' in beer_name_lower:
                                    style_from_untappd = 'Imperial Stout'
                                else:
                                    style_from_untappd = 'Stout'
                            elif 'портер' in beer_name_lower or 'porter' in beer_name_lower:
                                style_from_untappd = 'Porter'
                            elif 'ипа' in beer_name_lower or 'ipa' in beer_name_lower:
                                style_from_untappd = 'IPA'
                            elif 'лагер' in beer_name_lower or 'lager' in beer_name_lower:
                                style_from_untappd = 'Lager'
                            elif 'эль' in beer_name_lower or 'ale' in beer_name_lower:
                                if 'пале' in beer_name_lower or 'pale' in beer_name_lower:
                                    style_from_untappd = 'Pale Ale'
                                else:
                                    style_from_untappd = 'Ale'
                            
                            # Если не нашли по названию, пробуем по описанию
                            if not style_from_untappd and description:
                                desc_lower = description.lower()
                                # Проверяем на Gose (разные варианты написания)
                                if 'гозэ' in desc_lower or 'гозе' in desc_lower or 'gose' in desc_lower:
                                    style_from_untappd = 'Gose'
                                elif 'берлинер вайссе' in desc_lower or 'berliner weisse' in desc_lower:
                                    style_from_untappd = 'Berliner Weisse'
                                elif 'саур эль' in desc_lower or 'sour ale' in desc_lower or ('sour' in desc_lower and 'эль' in desc_lower):
                                    style_from_untappd = 'Sour Ale'
                                elif 'стаут' in desc_lower or 'stout' in desc_lower:
                                    if 'имперский' in desc_lower or 'imperial' in desc_lower:
                                        style_from_untappd = 'Imperial Stout'
                                    else:
                                        style_from_untappd = 'Stout'
                                elif 'портер' in desc_lower or 'porter' in desc_lower:
                                    style_from_untappd = 'Porter'
                            
                            # Если все еще не нашли, пробуем через Untappd API
                            if not style_from_untappd:
                                style_from_untappd = untappd_client.get_beer_style(beer_name, brewery_name)
                            
                            if style_from_untappd:
                                normalized_item['style'] = style_from_untappd
                                logger.info(f"Стиль найден через эвристику/Untappd: {beer_name} (brewery: {brewery_name}) -> {style_from_untappd}")
                        except Exception as e:
                            logger.warning(f"Ошибка при поиске стиля через Untappd для {beer_name}: {str(e)}")
                
                # Логируем brewery перед сохранением
                logger.debug(f"Сохранение позиции: beer_name={normalized_item.get('beer_name', '')[:50]}, brewery={normalized_item.get('brewery', '')}")
                
                # Удаляем служебные поля, которых нет в модели ParsedItem
                item_for_save = {k: v for k, v in normalized_item.items() if not k.startswith('_')}
                
                # Валидация перед сохранением
                is_valid, errors, warnings = validator.validate_item(item_for_save)
                
                if errors:
                    logger.warning(f"Ошибки валидации для позиции {normalized_item.get('beer_name', 'Не указано')}: {', '.join(errors)}")
                
                if warnings:
                    logger.debug(f"Предупреждения валидации для позиции {normalized_item.get('beer_name', 'Не указано')}: {', '.join(warnings)}")
                
                # Сохраняем для итоговой валидации
                validation_items.append({
                    'item': item_for_save,
                    'errors': errors,
                    'warnings': warnings,
                    'is_valid': is_valid,
                })
                
                # Создаем ParsedItem (даже если есть ошибки валидации, но логируем их)
                parsed_item = ParsedItem.objects.create(**item_for_save)
                product_items.append(parsed_item)
                
                # Проверяем, что brewery сохранилось
                parsed_item.refresh_from_db()
                if not parsed_item.brewery and normalized_item.get('brewery'):
                    logger.warning(f"brewery не сохранилось в БД для позиции {parsed_item.id}: beer_name={parsed_item.beer_name[:50]}, ожидалось brewery={normalized_item.get('brewery')}")
            else:
                # Сохраняем контакты и служебные тексты
                skipped_count += 1
                for key, values in contacts.items():
                    if values:
                        all_contacts[key].extend(values)
                
                # Извлекаем служебные тексты
                extra = contact_filter.extract_extra_text(row_text)
                extra_texts.extend(extra)
        
        # Итоговая валидация всех позиций
        validation_stats = validator.validate_batch([v['item'] for v in validation_items])
        
        # Создаем или обновляем метаданные
        metadata, created = FileMetadata.objects.get_or_create(file=file_obj)
        metadata.contacts = all_contacts
        metadata.extra_text = list(set(extra_texts))  # Убираем дубликаты
        
        metadata.summary = {
            'total_items': len(product_items),
            'skipped_rows': skipped_count,
            'contacts_found': {
                'phones': len(all_contacts['phones']),
                'emails': len(all_contacts['emails']),
                'addresses': len(all_contacts['addresses']),
                'links': len(all_contacts['links']),
            },
            'validation': {
                'valid': validation_stats['valid'],
                'invalid': validation_stats['invalid'],
                'total_errors': validation_stats['total_errors'],
                'total_warnings': validation_stats['total_warnings'],
            },
            'parser_stats': getattr(parser, 'stats', {}),
        }
        metadata.save()
        
        # Завершаем прогресс
        try:
            cache.set(progress_key, {
                'status': 'completed',
                'progress': 100,
                'message': f'Парсинг завершен! Обработано {len(product_items)} позиций',
                'total_items': len(product_items),
                'processed_items': len(product_items),
            }, timeout=60)  # Храним 1 минуту после завершения
        except Exception as cache_err:
            logger.warning(f"Ошибка завершения прогресса в кэше: {cache_err}")
        
        return Response({
            'message': 'Парсинг завершен',
            'items_created': len(product_items),
            'skipped_rows': skipped_count,
            'summary': metadata.summary
        })
    
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


class SupplierViewSet(viewsets.ModelViewSet):
    """ViewSet для настроек поставщиков (маппинг колонок)."""
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer


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
            order = Order.objects.create(
                items=serializer.validated_data['items'],
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


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def upload_file(request):
    """
    Загружает файл на сервер.
    
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

