"""Background execution of POST /api/files/<id>/parse/ (HTTP 202 + this job)."""
import logging
import traceback

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.shortcuts import get_object_or_404

from .models import File, ParsedItem, FileMetadata, Supplier, SupplierColumnMapping
from .validators import ParsedItemValidator
from .filters import ContactFilter
from .normalizers import DataNormalizer
from .untappd_client import UntappdClient
from .services.parse_dispatcher import dispatch_parse
from .services.parse_run_service import persist_parse_run
from .services.autopilot_repair import autopilot_repair_raw_items
from .pipeline_v2 import ParseStatus

logger = logging.getLogger(__name__)


def _cache_parse_error(progress_key: str, message: str) -> None:
    try:
        cache.set(
            progress_key,
            {
                "status": "error",
                "progress": 0,
                "message": message,
                "total_items": 0,
                "processed_items": 0,
            },
            timeout=600,
        )
    except Exception:
        pass


def run_file_parse_job(file_id: int, user_id: int, request_data: dict) -> None:
    """Runs the full parse pipeline; updates cache for GET parse_progress/."""
    lock_key = f"parse_running_{file_id}"
    try:
        _run_file_parse_job_impl(file_id, user_id, request_data)
    finally:
        try:
            cache.delete(lock_key)
        except Exception:
            pass


def _run_file_parse_job_impl(file_id: int, user_id: int, request_data: dict) -> None:
    file_obj = File.objects.get(pk=file_id)
    user = get_user_model().objects.get(pk=user_id)
    progress_key = f"parse_progress_{file_obj.id}"

    supplier_type_from_request = request_data.get('supplier_type')
    brewery_name_from_request = request_data.get('brewery_name')
    supplier_id_from_request = request_data.get('supplier_id')
    supplier_column_mapping = None
    if supplier_id_from_request:
        try:
            supplier = get_object_or_404(Supplier, pk=supplier_id_from_request)
            supplier_column_mapping = supplier.column_mapping or {}
            logger.info(f"Используется маппинг поставщика: {supplier.name}")
        except Exception as e:
            logger.warning(f"Не удалось загрузить поставщика {supplier_id_from_request}: {e}")
    if supplier_column_mapping is None:
        # Fallback на новый feedback-loop реестр: берем global mappings.
        global_rows = SupplierColumnMapping.objects.filter(
            scope=SupplierColumnMapping.SCOPE_GLOBAL
        ).values('target_field', 'source_column')
        if global_rows:
            supplier_column_mapping = {}
            for row in global_rows:
                supplier_column_mapping.setdefault(row['target_field'], []).append(row['source_column'])

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
        # Оркестровый rollout-контур: можно принудительно запустить shadow/v2
        # для конкретного запроса без рестарта сервера.
        if 'shadow_mode' in request_data:
            parse_kwargs['__shadow_mode_override'] = bool(request_data.get('shadow_mode'))
        if 'use_v2' in request_data:
            parse_kwargs['__use_v2_override'] = bool(request_data.get('use_v2'))
        if 'force_legacy' in request_data:
            parse_kwargs['__force_legacy_override'] = bool(request_data.get('force_legacy'))
    
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
    
        parse_result = dispatch_parse(file_obj, parse_kwargs)
        persist_parse_run(
            file_obj=file_obj,
            parse_result=parse_result,
            parse_kwargs=parse_kwargs,
            user=user,
            supplier_id=supplier_id_from_request,
        )
        if parse_result.status == ParseStatus.FAILED:
            err_msg = 'Ошибка парсинга'
            if parse_result.errors:
                err_msg = parse_result.errors[0].message
            _cache_parse_error(progress_key, err_msg)
            return

        raw_items = parse_result.items
        raw_items = autopilot_repair_raw_items(raw_items)
        logger.info(f"Парсинг завершен, извлечено {len(raw_items)} позиций")

        # Re-parse должен быть идемпотентным: очищаем старые позиции файла
        # перед сохранением нового результата, чтобы не смешивать прайсы.
        ParsedItem.objects.filter(file=file_obj).delete()
    
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
        _cache_parse_error(progress_key, f'Ошибка парсинга: {str(e)}')
        return

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
        'parser_stats': parse_result.meta.get('parser_stats', {}),
        'pipeline': {
            'version': parse_result.meta.get('pipeline_version', 'legacy'),
            'status': parse_result.status,
            'warnings': [w.to_dict() for w in parse_result.warnings],
            'shadow': parse_result.meta.get('shadow'),
        },
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
        }, timeout=600)  # Держим дольше, чтобы фронт стабильно увидел terminal state
    except Exception as cache_err:
        logger.warning(f"Ошибка завершения прогресса в кэше: {cache_err}")

    return
