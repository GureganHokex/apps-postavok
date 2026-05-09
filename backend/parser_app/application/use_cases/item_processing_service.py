"""
Сервис для обработки позиций после парсинга.
"""

import logging
from typing import Dict, List, Optional, Tuple
from decimal import Decimal, InvalidOperation

from parser_app.models import ParsedItem
from parser_app.domain.services.normalization import DataNormalizer
from parser_app.presentation.validators.parsed_item_validator import ParsedItemValidator
from parser_app.presentation.filters.contact_filter import ContactFilter
from parser_app.infrastructure.external.untappd_client import UntappdClient
from parser_app.shared.utils import safe_float
from parser_app.shared.constants import EMPTY_VALUE_STRINGS, BEER_STYLE_KEYWORDS, BEER_STYLE_MAPPING

logger = logging.getLogger(__name__)


class ItemProcessingService:
    """
    Сервис для обработки и нормализации позиций после парсинга.
    """
    
    def __init__(self):
        self.normalizer = DataNormalizer()
        self.validator = ParsedItemValidator()
        self.contact_filter = ContactFilter()
        self.untappd_client = UntappdClient()
    
    def process_raw_items(
        self, 
        raw_items: List[Dict], 
        file_obj,
        progress_key: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> Tuple[List[ParsedItem], Dict, List[str], Dict]:
        """
        Обрабатывает сырые данные после парсинга.
        
        Args:
            raw_items: Список сырых позиций из парсера
            file_obj: Объект File
            progress_key: Ключ для обновления прогресса в кэше
            progress_callback: Функция для обновления прогресса
            
        Returns:
            Tuple (product_items, contacts, extra_texts, validation_stats)
        """
        all_contacts = {
            'phones': [],
            'emails': [],
            'addresses': [],
            'links': []
        }
        extra_texts = []
        product_items_data = []
        validation_items = []
        skipped_count = 0
        total_items_count = len(raw_items)
        
        for idx, raw_item in enumerate(raw_items):
            # Обновляем прогресс
            if progress_callback and (idx % 10 == 0 or idx == total_items_count - 1):
                progress_callback(idx + 1, total_items_count)
            
            # Собираем текст строки для фильтрации
            row_text = ' '.join(str(v) for v in raw_item.values() if v)
            
            # Проверяем, является ли строка товарной
            is_product, contacts = self.contact_filter.filter_row(raw_item, row_text)
            
            if is_product:
                # Обрабатываем товарную позицию
                processed_item = self._process_product_item(raw_item, file_obj)
                
                if processed_item:
                    # Валидация
                    is_valid, errors, warnings = self.validator.validate_item(processed_item)
                    
                    validation_items.append({
                        'item': processed_item,
                        'errors': errors,
                        'warnings': warnings,
                        'is_valid': is_valid,
                    })
                    
                    if errors:
                        logger.warning(
                            f"Ошибки валидации для позиции {processed_item.get('beer_name', 'Не указано')}: "
                            f"{', '.join(errors)}"
                        )
                    
                    product_items_data.append(processed_item)
            else:
                # Сохраняем контакты и служебные тексты
                skipped_count += 1
                for key, values in contacts.items():
                    if values:
                        all_contacts[key].extend(values)
                
                # Извлекаем служебные тексты
                extra = self.contact_filter.extract_extra_text(row_text)
                extra_texts.extend(extra)
        
        # Итоговая валидация
        validation_stats = self.validator.validate_batch([v['item'] for v in validation_items])
        
        # Дедупликация перед сохранением в БД
        product_items_data = self._deduplicate_items(product_items_data)
        
        # Удаляем существующие дубликаты из БД для этого файла
        self._remove_existing_duplicates(file_obj, product_items_data)
        
        # Массовое создание позиций
        product_items = self._bulk_create_items(product_items_data)
        
        # Удаляем дубликаты из БД после сохранения (на случай если они все же появились)
        self._remove_db_duplicates(file_obj)
        
        return product_items, all_contacts, extra_texts, validation_stats, skipped_count
    
    def _process_product_item(self, raw_item: Dict, file_obj) -> Optional[Dict]:
        """
        Обрабатывает одну товарную позицию.
        
        Args:
            raw_item: Сырые данные позиции
            file_obj: Объект File
            
        Returns:
            Словарь с обработанными данными или None
        """
        # Нормализуем данные
        normalized_item = self.normalizer.normalize_item(raw_item)
        
        # Восстанавливаем brewery если нужно
        normalized_item = self._ensure_brewery(normalized_item, raw_item)
        
        # Нормализуем числовые поля
        normalized_item = self._normalize_numeric_fields(normalized_item)
        
        # Определяем стиль если отсутствует
        normalized_item = self._ensure_style(normalized_item)
        
        # Добавляем файл
        normalized_item['file'] = file_obj
        
        # Удаляем служебные поля
        item_for_save = {
            k: v for k, v in normalized_item.items()
            if not k.startswith('_') and k != 'price_unit'
        }
        
        logger.debug(
            f"Обработка позиции: beer_name={item_for_save.get('beer_name', '')[:50]}, "
            f"brewery={item_for_save.get('brewery', '')}"
        )
        
        return item_for_save
    
    def _ensure_brewery(self, normalized_item: Dict, raw_item: Dict) -> Dict:
        """
        Обеспечивает наличие brewery в нормализованном элементе.
        
        Args:
            normalized_item: Нормализованные данные
            raw_item: Сырые данные
            
        Returns:
            Обновленный normalized_item
        """
        if 'brewery' in raw_item and raw_item['brewery']:
            raw_brewery = raw_item['brewery']
            normalized_brewery = normalized_item.get('brewery', '')
            
            if not normalized_brewery or not normalized_brewery.strip():
                # Пробуем нормализовать brewery из raw_item
                brewery_from_raw = self.normalizer.normalize_brewery(raw_brewery)
                if brewery_from_raw and brewery_from_raw.strip():
                    normalized_item['brewery'] = brewery_from_raw
                elif raw_brewery.strip():
                    # Если нормализация удалила brewery, используем оригинальное значение
                    normalized_item['brewery'] = raw_brewery.strip()
            elif not normalized_brewery.strip():
                # Если brewery пустое после нормализации, восстанавливаем
                brewery_from_raw = self.normalizer.normalize_brewery(raw_brewery)
                if brewery_from_raw and brewery_from_raw.strip():
                    normalized_item['brewery'] = brewery_from_raw
                else:
                    normalized_item['brewery'] = raw_brewery.strip()
        elif 'brewery' not in normalized_item and 'brewery' in raw_item and raw_item['brewery']:
            # Если brewery было в raw_item, но не попало в normalized_item
            brewery_from_raw = self.normalizer.normalize_brewery(raw_item['brewery'])
            if brewery_from_raw and brewery_from_raw.strip():
                normalized_item['brewery'] = brewery_from_raw
            else:
                normalized_item['brewery'] = raw_item['brewery'].strip()
        
        return normalized_item
    
    def _normalize_numeric_fields(self, normalized_item: Dict) -> Dict:
        """
        Нормализует числовые поля (abv, price, volume).
        
        Args:
            normalized_item: Данные позиции
            
        Returns:
            Обновленные данные
        """
        for field in ['abv', 'price', 'volume']:
            if field not in normalized_item:
                continue
                
            value = normalized_item[field]
            
            # Если значение - строка, пытаемся преобразовать в число
            if isinstance(value, str):
                value_stripped = value.strip().lower()
                
                # Пропускаем служебные строки
                if value_stripped in EMPTY_VALUE_STRINGS:
                    normalized_item[field] = None
                else:
                    # Пытаемся извлечь число из строки
                    if field == 'price':
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
                        normalized_item[field] = Decimal(str(value))
                    else:
                        float(value)  # Просто проверяем, что можно преобразовать
                except (ValueError, TypeError, InvalidOperation):
                    normalized_item[field] = None
        
        return normalized_item
    
    def _ensure_style(self, normalized_item: Dict) -> Dict:
        """
        Определяет стиль пива если он отсутствует.
        
        Args:
            normalized_item: Данные позиции
            
        Returns:
            Обновленные данные
        """
        if normalized_item.get('style') and normalized_item.get('style', '').strip():
            return normalized_item
        
        beer_name = normalized_item.get('beer_name', '').strip()
        brewery_name = normalized_item.get('brewery', '').strip()
        description = normalized_item.get('description', '').strip()
        
        if not beer_name:
            return normalized_item
        
        try:
            style_from_heuristic = self._detect_style_from_text(beer_name, description)
            
            if not style_from_heuristic:
                style_from_heuristic = self.untappd_client.get_beer_style(beer_name, brewery_name)
            
            if style_from_heuristic:
                normalized_item['style'] = style_from_heuristic
                logger.info(
                    f"Стиль найден: {beer_name} (brewery: {brewery_name}) -> {style_from_heuristic}"
                )
        except Exception as e:
            logger.warning(f"Ошибка при поиске стиля для {beer_name}: {str(e)}")
        
        return normalized_item
    
    def _detect_style_from_text(self, beer_name: str, description: str = '') -> Optional[str]:
        """
        Определяет стиль пива по тексту (эвристика).
        
        Args:
            beer_name: Название пива
            description: Описание
            
        Returns:
            Название стиля или None
        """
        beer_name_lower = beer_name.lower()
        desc_lower = description.lower() if description else ''
        
        # Проверяем по названию пива (приоритет выше)
        for style_key, keywords in BEER_STYLE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in beer_name_lower:
                    # Специальная обработка для imperial stout
                    if style_key == 'stout' and ('имперский' in beer_name_lower or 'imperial' in beer_name_lower):
                        return BEER_STYLE_MAPPING.get('imperial_stout')
                    # Специальная обработка для pale ale
                    elif style_key == 'ale' and ('пале' in beer_name_lower or 'pale' in beer_name_lower):
                        return BEER_STYLE_MAPPING.get('pale_ale')
                    return BEER_STYLE_MAPPING.get(style_key)
        
        # Проверяем по описанию
        if desc_lower:
            for style_key, keywords in BEER_STYLE_KEYWORDS.items():
                for keyword in keywords:
                    if keyword in desc_lower:
                        if style_key == 'stout' and ('имперский' in desc_lower or 'imperial' in desc_lower):
                            return BEER_STYLE_MAPPING.get('imperial_stout')
                        return BEER_STYLE_MAPPING.get(style_key)
        
        return None
    
    def _deduplicate_items(self, items_data: List[Dict]) -> List[Dict]:
        """
        Удаляет дубликаты из списка позиций перед сохранением в БД.
        
        Args:
            items_data: Список словарей с данными позиций
            
        Returns:
            Список без дубликатов
        """
        if not items_data:
            return []
        
        # Используем выделенный модуль для дедупликации
        from parser_app.domain.services.deduplication import Deduplicator
        return Deduplicator.deduplicate(items_data)
    
    def _remove_existing_duplicates(self, file_obj, items_data: List[Dict]) -> None:
        """
        Удаляет существующие дубликаты из БД перед сохранением новых элементов.
        
        Args:
            file_obj: Объект File
            items_data: Список новых элементов для сохранения
        """
        if not items_data:
            return
        
        import re
        from decimal import Decimal
        
        # Создаем множество ключей новых элементов
        new_keys = set()
        for item in items_data:
            beer_name_norm = (item.get('beer_name') or '').strip().lower()
            beer_name_base = re.sub(r'\s*\([^)]*\)\s*', '', beer_name_norm).strip()
            
            price_val = item.get('price')
            if price_val is not None:
                try:
                    if isinstance(price_val, str):
                        price_val = float(price_val.replace(',', '.'))
                    elif isinstance(price_val, Decimal):
                        price_val = float(price_val)
                    price_normalized = f"{float(price_val):.2f}"
                except (ValueError, TypeError):
                    price_normalized = str(price_val)
            else:
                price_normalized = ''
            
            key = (
                (item.get('brewery') or '').strip().lower(),
                beer_name_base,
                (item.get('style') or '').strip().lower(),
                (item.get('format_type') or '').strip().lower(),
                price_normalized
            )
            new_keys.add(key)
        
        # Находим и удаляем существующие дубликаты
        existing_items = ParsedItem.objects.filter(file=file_obj)
        duplicates_to_delete = []
        
        for existing_item in existing_items:
            beer_name_norm = (existing_item.beer_name or '').strip().lower()
            beer_name_base = re.sub(r'\s*\([^)]*\)\s*', '', beer_name_norm).strip()
            
            price_val = existing_item.price
            if price_val is not None:
                try:
                    price_normalized = f"{float(price_val):.2f}"
                except (ValueError, TypeError):
                    price_normalized = str(price_val)
            else:
                price_normalized = ''
            
            key = (
                (existing_item.brewery or '').strip().lower(),
                beer_name_base,
                (existing_item.style or '').strip().lower(),
                (existing_item.format_type or '').strip().lower(),
                price_normalized
            )
            
            if key in new_keys:
                duplicates_to_delete.append(existing_item.id)
        
        if duplicates_to_delete:
            deleted_count = ParsedItem.objects.filter(id__in=duplicates_to_delete).delete()[0]
            logger.info(f"Удалено {deleted_count} существующих дубликатов из БД перед сохранением новых")
    
    def _remove_db_duplicates(self, file_obj) -> None:
        """
        Удаляет дубликаты из БД для указанного файла.
        
        Args:
            file_obj: Объект File
        """
        import re
        from decimal import Decimal
        
        existing_items = list(ParsedItem.objects.filter(file=file_obj).order_by('id'))
        if len(existing_items) <= 1:
            return
        
        seen = {}
        duplicates_to_delete = []
        
        for item in existing_items:
            beer_name_norm = (item.beer_name or '').strip().lower()
            beer_name_base = re.sub(r'\s*\([^)]*\)\s*', '', beer_name_norm).strip()
            
            price_val = item.price
            if price_val is not None:
                try:
                    price_normalized = f"{float(price_val):.2f}"
                except (ValueError, TypeError):
                    price_normalized = str(price_val)
            else:
                price_normalized = ''
            
            key = (
                (item.brewery or '').strip().lower(),
                beer_name_base,
                (item.style or '').strip().lower(),
                (item.format_type or '').strip().lower(),
                price_normalized
            )
            
            if key in seen:
                # Оставляем первый элемент, остальные помечаем на удаление
                duplicates_to_delete.append(item.id)
            else:
                seen[key] = item
        
        if duplicates_to_delete:
            deleted_count = ParsedItem.objects.filter(id__in=duplicates_to_delete).delete()[0]
            logger.info(f"Удалено {deleted_count} дубликатов из БД после сохранения")
    
    def _bulk_create_items(self, items_data: List[Dict]) -> List[ParsedItem]:
        """
        Массовое создание позиций через bulk_create.
        
        Args:
            items_data: Список словарей с данными для создания
            
        Returns:
            Список созданных объектов ParsedItem
        """
        if not items_data:
            return []
        
        # Создаем объекты ParsedItem без сохранения
        items_to_create = []
        for item_data in items_data:
            try:
                # Удаляем поля, которых нет в модели
                cleaned_data = {
                    k: v for k, v in item_data.items()
                    if k in [f.name for f in ParsedItem._meta.get_fields()]
                }
                row = ParsedItem(**cleaned_data)
                row.truncate_varchar_fields()
                items_to_create.append(row)
            except Exception as e:
                logger.error(f"Ошибка при создании ParsedItem: {str(e)}, данные: {item_data}")
                continue
        
        # Массовое создание батчами
        created_items = []
        batch_size = 100
        
        for i in range(0, len(items_to_create), batch_size):
            batch = items_to_create[i:i + batch_size]
            batch_data = items_data[i:i + batch_size]  # Сохраняем исходные данные
            
            try:
                created_batch = ParsedItem.objects.bulk_create(batch, ignore_conflicts=True)
                created_items.extend(created_batch)
            except Exception as e:
                logger.error(f"Ошибка при bulk_create батча {i}: {str(e)}")
                # Fallback: создаем по одной
                for item_data in batch_data:
                    try:
                        # Очищаем данные от полей, которых нет в модели
                        cleaned_data = {
                            k: v for k, v in item_data.items()
                            if k in [f.name for f in ParsedItem._meta.get_fields()]
                        }
                        created_item = ParsedItem.objects.create(**cleaned_data)
                        created_items.append(created_item)
                    except Exception as e2:
                        logger.error(f"Ошибка при создании отдельной позиции: {str(e2)}")
        
        return created_items
