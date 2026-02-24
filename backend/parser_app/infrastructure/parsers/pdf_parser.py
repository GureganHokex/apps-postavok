"""
Парсер для PDF файлов.
"""

import pdfplumber
import re
try:
    import pytesseract
    from PIL import Image
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
from typing import List, Dict, Optional
from .base_parser import BaseParser
from .supplier_profiles import (
    SupplierProfileDetector, SupplierType,
    DistributorProfile, BreweryProfile
)
import logging

logger = logging.getLogger(__name__)


class PDFParser(BaseParser):
    """
    Парсер для PDF файлов.
    
    Поддерживает структурированные PDF (с таблицами) и текст.
    """

    def __init__(self, file_path: str):
        super().__init__(file_path)
        # Статистика парсинга для диагностики (обновляется в ходе работы)
        self.stats = {
            'pages': 0,
            'tables': 0,
            'headers_found': 0,
            'parsed_header_rows': 0,
            'parsed_heuristic_rows': 0,
            'skipped_empty': 0,
        }
    
    def parse(self, supplier_type: Optional[str] = None, 
              brewery_name: Optional[str] = None) -> List[Dict]:
        """
        Парсит PDF файл.
        
        Args:
            supplier_type: Тип поставщика ('distributor' | 'brewery')
            brewery_name: Название пивоварни (для частного поставщика)
        
        Returns:
            Список словарей с данными позиций
        """
        items = []
        
        # Преобразуем supplier_type в enum
        supplier_type_enum = None
        if supplier_type:
            try:
                supplier_type_enum = SupplierType(supplier_type)
            except ValueError:
                logger.warning(f"Неизвестный тип поставщика: {supplier_type}, используем None")
        
        # Для пивоварни получаем название по умолчанию
        default_brewery = None
        original_brewery_name = None
        if supplier_type_enum == SupplierType.BREWERY:
            try:
                brewery_name_to_use = brewery_name
                original_brewery_name = brewery_name_to_use
                if brewery_name_to_use:
                    profile = BreweryProfile(brewery_name_to_use)
                    default_brewery = profile.get_default_brewery_name()
                    logger.info(f"Установлена пивоварня по умолчанию для PDF: {default_brewery} (из {brewery_name_to_use})")
                else:
                    logger.warning("Для частного поставщика не указано название пивоварни")
            except Exception as e:
                logger.warning(f"Ошибка при установке пивоварни по умолчанию: {str(e)}")
                # Используем переданное название напрямую
                if brewery_name:
                    default_brewery = brewery_name
                    original_brewery_name = brewery_name
        
        logger.info(f"Начало парсинга PDF файла: {self.file_path}, supplier_type={supplier_type_enum}, brewery_name={brewery_name}, default_brewery={default_brewery}")
        
        try:
            # Пробуем извлечь таблицы через pdfplumber
            with pdfplumber.open(self.file_path) as pdf:
                logger.info(f"PDF файл содержит {len(pdf.pages)} страниц")
                
                for page_num, page in enumerate(pdf.pages, 1):
                    self.stats['pages'] += 1
                    logger.debug(f"Обработка страницы {page_num}")
                    
                    # СНАЧАЛА пробуем извлечь таблицы (для структурированных PDF)
                    # Текст используем только как fallback, если таблиц нет или они пустые
                    tables = page.extract_tables()
                    logger.debug(f"Страница {page_num}: найдено {len(tables)} таблиц")
                    self.stats['tables'] += len(tables or [])
                    
                    # Извлекаем текст страницы для fallback и для таблиц с 1 колонкой
                    page_text = page.extract_text()
                    if page_text:
                        logger.debug(f"Страница {page_num}: извлечено {len(page_text)} символов текста")
                    
                    items_from_tables_on_this_page = 0
                    single_column_tables_count = 0
                    
                    for table_num, table in enumerate(tables):
                        if table and len(table) >= 2:
                            # Проверяем, является ли таблица стандартной таблицей Dieta (после поворота)
                            # Стандартная таблица имеет заголовки в первых строках и данные в последующих
                            # Проверяем наличие заголовков в первых строках
                            is_standard_dieta_table = False
                            if len(table) > 2 and len(table[0]) > 5:
                                # Проверяем первую строку на наличие заголовков
                                first_row_lower = [str(cell).strip().lower() if cell else '' for cell in table[0]]
                                has_headers = any(
                                    h in ' '.join(first_row_lower) 
                                    for h in ['название', 'стиль', 'ттх', 'ttx', 'описание', 'объём', 'объем', 'цена', 'наличие']
                                )
                                if has_headers:
                                    is_standard_dieta_table = True
                                    logger.debug(f"Таблица {table_num} - стандартная таблица Dieta с заголовками")
                            
                            # ОТКЛЮЧЕНО: карточный макет работает неправильно, парсит служебные строки как названия
                            # Используем только стандартный табличный парсинг
                            # if not is_standard_dieta_table and len(table) > 0 and len(table[0]) > 8 and len(table) < 6:
                            #     logger.debug(f"Таблица {table_num} выглядит как макет карточек ({len(table)} строк, {len(table[0])} колонок), пробуем парсить как карточки")
                            #     parsed_items = self._parse_dieta_card_layout(
                            #         table, page_num, table_num,
                            #         default_brewery=default_brewery,
                            #         original_brewery_name=original_brewery_name
                            #     )
                            #     if parsed_items:
                            #         items.extend(parsed_items)
                            #         items_from_tables_on_this_page += len(parsed_items)
                            #         logger.info(f"Из макета карточек таблицы {table_num} страницы {page_num} извлечено {len(parsed_items)} позиций")
                            #         continue
                            
                            # Проверяем структуру таблицы - если меньше 3 колонок, может быть проблемой
                            if len(table[0]) < 3:
                                single_column_tables_count += 1
                                logger.debug(f"Таблица {table_num} имеет только {len(table[0])} колонок, пропускаем для последующего текстового парсинга всей страницы")
                                continue  # Пропускаем таблицы с 1 колонкой, будем парсить всю страницу как текст
                            
                            parsed_items = self._parse_table(
                                table, page_num, table_num,
                                supplier_type=supplier_type_enum,
                                default_brewery=default_brewery,
                                original_brewery_name=original_brewery_name
                            )
                            if parsed_items:
                                items.extend(parsed_items)
                                items_from_tables_on_this_page += len(parsed_items)
                                logger.info(f"Из таблицы {table_num} страницы {page_num} извлечено {len(parsed_items)} позиций")
                    
                    # Если нашли много таблиц с 1 колонкой или не нашли позиций в многоколоночных таблицах,
                    # пробуем извлечь текст построчно из всей страницы (fallback)
                    # Это нужно, потому что данные могут быть разбросаны по разным таблицам
                    if items_from_tables_on_this_page == 0 or (single_column_tables_count > 3 and items_from_tables_on_this_page < single_column_tables_count):
                        logger.debug(f"На странице {page_num} найдено {single_column_tables_count} таблиц с 1 колонкой и {items_from_tables_on_this_page} позиций из многоколоночных таблиц, пробуем текстовый парсинг всей страницы")
                        if page_text:
                            # Для частных поставщиков используем специальный метод
                            if supplier_type_enum == SupplierType.BREWERY and original_brewery_name:
                                parsed_items = self._parse_text_for_brewery(
                                    page_text, page_num, original_brewery_name, default_brewery
                                )
                            else:
                                parsed_items = self._parse_text_lines(
                                    page_text, page_num,
                                    supplier_type=supplier_type_enum,
                                    default_brewery=default_brewery,
                                    original_brewery_name=original_brewery_name
                                )
                            if parsed_items:
                                # Объединяем с уже извлеченными позициями (если есть)
                                # Избегаем дублей: если позиция уже была извлечена из таблицы, не добавляем из текста
                                existing_names = {item.get('beer_name', '').strip().lower() for item in items if item.get('beer_name')}
                                new_items = []
                                for item in parsed_items:
                                    item_name = item.get('beer_name', '').strip().lower()
                                    if item_name and item_name not in existing_names:
                                        new_items.append(item)
                                        existing_names.add(item_name)
                                    elif item_name:
                                        # Если позиция уже есть, но новая более полная (имеет больше данных), обновляем
                                        for idx, existing_item in enumerate(items):
                                            if existing_item.get('beer_name', '').strip().lower() == item_name:
                                                # Подсчитываем количество заполненных полей
                                                existing_fields = sum(1 for k in ['style', 'abv', 'price', 'volume', 'format_type'] if existing_item.get(k))
                                                new_fields = sum(1 for k in ['style', 'abv', 'price', 'volume', 'format_type'] if item.get(k))
                                                if new_fields > existing_fields:
                                                    # Заменяем существующую позицию на более полную
                                                    items[idx] = item
                                                    logger.debug(f"Обновлена позиция {item_name}: заменена на более полную версию ({new_fields} полей вместо {existing_fields})")
                                                break
                                if new_items:
                                    items.extend(new_items)
                                    logger.info(f"Из текстовых строк страницы {page_num} извлечено {len(new_items)} новых позиций (всего {len(parsed_items)}, дублей пропущено: {len(parsed_items) - len(new_items)})")
        except Exception as e:
            logger.error(f"Ошибка при парсинге PDF: {str(e)}", exc_info=True)
            # Если pdfplumber не справился, пробуем OCR
            items = self._parse_with_ocr()
        
        # Финальная проверка: для частного поставщика убеждаемся, что у всех позиций есть brewery
        if supplier_type_enum == SupplierType.BREWERY:
            brewery_to_ensure = default_brewery or original_brewery_name
            if brewery_to_ensure:
                from parser_app.domain.services.normalization import DataNormalizer
                normalizer = DataNormalizer()
                brewery_normalized = normalizer.normalize_brewery(brewery_to_ensure)
                final_brewery = brewery_normalized if brewery_normalized else brewery_to_ensure
                
                items_without_brewery = 0
                for item in items:
                    if not item.get('brewery'):
                        item['brewery'] = final_brewery
                        items_without_brewery += 1
                        logger.info(f"Добавлена пивоварня в финальной проверке для позиции '{item.get('beer_name', 'без названия')}': {final_brewery}")
                
                if items_without_brewery > 0:
                    logger.info(f"В финальной проверке добавлена пивоварня для {items_without_brewery} позиций")
            else:
                logger.warning("Для частного поставщика не указана пивоварня для финальной проверки")
        
        logger.info(f"Парсинг PDF завершен, извлечено позиций: {len(items)}")
        if items:
            sample_item = items[0]
            logger.info(f"Пример первой позиции: beer_name={sample_item.get('beer_name')}, brewery={sample_item.get('brewery')}, style={sample_item.get('style')}")
        return items
    
    def _parse_text_for_brewery(self, text: str, page_num: int, 
                                original_brewery_name: str, default_brewery: Optional[str] = None) -> List[Dict]:
        """
        Парсинг текста для частного поставщика - ищет названия продуктов, содержащие название пивоварни.
        
        Args:
            text: Текст страницы
            page_num: Номер страницы
            original_brewery_name: Оригинальное название пивоварни (например, "Dieta")
            default_brewery: Нормализованное название пивоварни
            
        Returns:
            Список словарей с данными позиций
        """
        items = []
        lines = text.split('\n')
        
        brewery_upper = original_brewery_name.upper()
        current_item = {}
        item_start_line = 0
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or len(line) < 3:
                # Если пустая строка и есть накопленный item - сохраняем его только если есть минимальный набор данных
                if current_item.get('beer_name'):
                    beer_name = current_item.get('beer_name', '')
                    
                    # ПРОВЕРКА: не сохраняем элементы с общими/служебными названиями или без минимальных данных
                    # Минимальный набор: название должно быть информативным И (цена ИЛИ ABV)
                    has_minimal_data = current_item.get('price') or current_item.get('abv')
                    beer_name_lower = beer_name.lower()
                    
                    generic_words = ['traditional', 'smoothie', 'libra', 'baltic', 'porter', 'stout', 'gose', 'pilsner',
                                   'ipa', 'ale', 'lager', 'sour', 'collab', 'коллаб', 'fruited', 'fruited розмарином',
                                   'крепкий', 'клюквенный', 'клюквой', 'персиком', 'манго']
                    is_generic = any(word in beer_name_lower for word in generic_words) and len(beer_name.split()) <= 2
                    
                    # Проверяем, что название содержит "DIETA" или достаточно информативное
                    has_dieta = brewery_upper in beer_name.upper()
                    is_too_short = len(beer_name) < 5 and not has_dieta
                    
                    # КРИТИЧЕСКАЯ ПРОВЕРКА: если название - это только "DIETA" (название пивоварни) без дополнительного названия продукта
                    # Это НЕ валидное название пива, даже если есть цена и ABV
                    is_only_brewery_name = (beer_name_lower.strip() == 'dieta' or 
                                          beer_name_lower.strip() == brewery_upper.lower() or
                                          (beer_name_lower.startswith('dieta') and len(beer_name.split()) == 1))
                    
                    # Сохраняем только если:
                    # 1. Название содержит "DIETA" И не слишком общее И не только название пивоварни
                    # 2. ИЛИ название достаточно информативное (не одно слово) И есть минимальный набор данных
                    # 3. ИЛИ есть и цена, и ABV (полный набор данных) И название не только "DIETA" И есть объем ИЛИ формат
                    has_full_data = current_item.get('price') and current_item.get('abv')
                    has_format_or_volume = current_item.get('volume') or current_item.get('format_type')
                    is_informative = len(beer_name.split()) >= 2 and not is_generic
                    
                    # Для элементов с полным набором данных (цена + ABV) требуем наличие объема или формата
                    # Если нет объема и формата, даже при наличии цены и ABV - пропускаем (неполные данные)
                    if (has_dieta and not is_generic and not is_only_brewery_name) or \
                       (is_informative and has_minimal_data) or \
                       (has_full_data and not is_only_brewery_name and has_format_or_volume):
                        brewery_to_set = default_brewery or original_brewery_name
                        if brewery_to_set:
                            from parser_app.domain.services.normalization import DataNormalizer
                            normalizer = DataNormalizer()
                            brewery_normalized = normalizer.normalize_brewery(brewery_to_set)
                            current_item['brewery'] = brewery_normalized if brewery_normalized else brewery_to_set
                        current_item['raw_source_location'] = {'page': page_num, 'line': item_start_line}
                        items.append(current_item)
                        logger.debug(f"Создан item из текста: beer_name={current_item.get('beer_name')}, brewery={current_item.get('brewery')}, price={current_item.get('price')}, abv={current_item.get('abv')}")
                    else:
                        logger.debug(f"Пропущен item из текста (недостаточно данных): beer_name={beer_name}, price={current_item.get('price')}, abv={current_item.get('abv')}")
                    current_item = {}
                continue
            
            line_upper = line.upper()
            
            # Ищем строки, содержащие название пивоварни
            if brewery_upper in line_upper:
                # Сохраняем предыдущий item если есть (с проверкой на валидность)
                if current_item.get('beer_name'):
                    beer_name = current_item.get('beer_name', '')
                    beer_name_lower = beer_name.lower()
                    
                    # ПРОВЕРКА: не сохраняем элементы с общими/служебными названиями или без минимальных данных
                    has_minimal_data = current_item.get('price') or current_item.get('abv')
                    generic_words = ['traditional', 'smoothie', 'libra', 'baltic', 'porter', 'stout', 'gose', 'pilsner',
                                   'ipa', 'ale', 'lager', 'sour', 'collab', 'коллаб', 'fruited', 'fruited розмарином',
                                   'крепкий', 'клюквенный', 'клюквой', 'персиком', 'манго']
                    is_generic = any(word in beer_name_lower for word in generic_words) and len(beer_name.split()) <= 2
                    has_dieta = brewery_upper in beer_name.upper()
                    is_too_short = len(beer_name) < 5 and not has_dieta
                    
                    # КРИТИЧЕСКАЯ ПРОВЕРКА: если название - это только "DIETA" (название пивоварни) без дополнительного названия продукта
                    is_only_brewery_name = (beer_name_lower.strip() == 'dieta' or 
                                          beer_name_lower.strip() == brewery_upper.lower() or
                                          (beer_name_lower.startswith('dieta') and len(beer_name.split()) == 1))
                    
                    has_full_data = current_item.get('price') and current_item.get('abv')
                    has_format_or_volume = current_item.get('volume') or current_item.get('format_type')
                    is_informative = len(beer_name.split()) >= 2 and not is_generic
                    
                    # Для элементов из текста требуем наличие объема или формата
                    # Если нет объема и формата, даже при наличии цены и ABV - пропускаем (неполные данные)
                    if (has_dieta and not is_generic and not is_only_brewery_name) or \
                       (is_informative and has_minimal_data) or \
                       (has_full_data and not is_only_brewery_name and has_format_or_volume):
                        brewery_to_set = default_brewery or original_brewery_name
                        if brewery_to_set:
                            from parser_app.domain.services.normalization import DataNormalizer
                            normalizer = DataNormalizer()
                            brewery_normalized = normalizer.normalize_brewery(brewery_to_set)
                            current_item['brewery'] = brewery_normalized if brewery_normalized else brewery_to_set
                        current_item['raw_source_location'] = {'page': page_num, 'line': item_start_line}
                        items.append(current_item)
                        logger.debug(f"Создан item при встрече нового названия: beer_name={current_item.get('beer_name')}, brewery={current_item.get('brewery')}, price={current_item.get('price')}, abv={current_item.get('abv')}, volume={current_item.get('volume')}, format={current_item.get('format_type')}")
                    else:
                        logger.debug(f"Пропущен item при встрече нового названия (недостаточно данных): beer_name={beer_name}, price={current_item.get('price')}, abv={current_item.get('abv')}, volume={current_item.get('volume')}, format={current_item.get('format_type')}, has_dieta={has_dieta}, is_informative={is_informative}, is_only_brewery_name={is_only_brewery_name}")
                
                # Проверяем, не является ли это контактной информацией
                line_lower = line.lower()
                contact_indicators = ['@', 'http', 'www.', 'тел', 'телефон', 'phone', '+7', '+375', 'telegram', 't.me', 'instagram', 'vk.com']
                if any(indicator in line_lower for indicator in contact_indicators):
                    logger.debug(f"Пропущена строка с контактами: {line[:50]}")
                    continue
                
                # Очищаем от префиксов типа "(NEW)"
                cleaned = re.sub(r'^\(NEW\)\s*', '', line, flags=re.IGNORECASE).strip()
                
                # Если строка достаточно длинная и содержит название пивоварни - это продукт
                if len(cleaned) > 5 and brewery_upper in cleaned.upper():
                    # Пропускаем служебные строки (но не те, что содержат данные)
                    cleaned_lower = cleaned.lower()
                    if any(skip in cleaned_lower for skip in ['дата', 'коробка', 'шт', 'наличии', 'наличие']) and not any(data in cleaned_lower for data in ['%', 'abv', 'руб', 'р/']):
                        continue
                    
                    # Извлекаем данные из самой строки названия
                    beer_name_parts = []
                    extracted_abv = None
                    extracted_price = None
                    extracted_volume = None
                    extracted_format = None
                    
                    # Извлекаем ABV из строки (например, "4.5%ABV" или "8.5%")
                    abv_match = re.search(r'(\d+\.?\d*)\s*%', cleaned, re.IGNORECASE)
                    if abv_match:
                        extracted_abv = abv_match.group(1)
                        # Удаляем ABV из названия
                        cleaned = re.sub(r'\s*\d+\.?\d*\s*%ABV?\s*', ' ', cleaned, flags=re.IGNORECASE).strip()
                    
                    # Извлекаем цену (например, "3800p", "400р/л", "4400р")
                    price_match = re.search(r'(\d+\.?\d*)\s*[рруб₽]/?\s*л?', cleaned_lower)
                    if price_match:
                        extracted_price = price_match.group(1)
                        # Проверяем, есть ли объем в цене (например, "400р/л")
                        volume_in_price = re.search(r'(\d+\.?\d*)\s*[рруб₽]/\s*л', cleaned_lower)
                        if volume_in_price:
                            extracted_volume = '1.0'  # 1 литр
                        # Удаляем цену из названия
                        cleaned = re.sub(r'\s*\d+\.?\d*\s*[рруб₽p]/?\s*л?\s*', ' ', cleaned, flags=re.IGNORECASE).strip()
                    
                    # Извлекаем формат (например, "банка", "бутылка", "кег")
                    format_match = re.search(r'\b(банка|бутылка|кег|keg|can|bottle|бут|б|к)\b', cleaned_lower)
                    if format_match:
                        extracted_format = format_match.group(1)
                    
                    # Очищаем название от лишних символов
                    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
                    
                    # Разбиваем на части и формируем название
                    parts = cleaned.split()
                    for part in parts:
                        if brewery_upper not in part.upper() and len(part) > 2:
                            beer_name_parts.append(part)
                    
                    beer_name = ' '.join(beer_name_parts) if beer_name_parts else cleaned
                    if not beer_name or len(beer_name.strip()) < 3:
                        beer_name = cleaned
                    
                    # ОБЯЗАТЕЛЬНАЯ ПРОВЕРКА: название должно содержать "DIETA" или быть достаточно информативным
                    beer_name_final = beer_name.strip() if beer_name else cleaned
                    beer_name_lower = beer_name_final.lower()
                    
                    # Список слишком общих/служебных слов, которые не являются полными названиями продуктов
                    generic_words = ['traditional', 'smoothie', 'libra', 'baltic', 'porter', 'stout', 'gose', 'pilsner',
                                   'ipa', 'ale', 'lager', 'sour', 'collab', 'коллаб', 'fruited', 'fruited розмарином',
                                   'крепкий', 'клюквенный', 'клюквой', 'персиком', 'манго']
                    
                    # Проверяем, что название содержит "DIETA" или достаточно информативное
                    has_dieta = brewery_upper in cleaned.upper() or brewery_upper in beer_name_final.upper()
                    is_generic = any(word in beer_name_lower for word in generic_words) and len(beer_name_final.split()) <= 2
                    
                    # Если название слишком общее и не содержит "DIETA" - пропускаем
                    if is_generic and not has_dieta:
                        logger.debug(f"Пропущено общее название без DIETA: {beer_name_final}")
                        continue
                    
                    # Если название слишком короткое (менее 5 символов) и не содержит "DIETA" - пропускаем
                    if len(beer_name_final) < 5 and not has_dieta:
                        logger.debug(f"Пропущено слишком короткое название без DIETA: {beer_name_final}")
                        continue
                    
                    # КРИТИЧЕСКАЯ ПРОВЕРКА: если название - это только "DIETA" (название пивоварни) без дополнительного названия продукта
                    # Даже если есть цена и ABV, это не валидное название пива
                    is_only_brewery_name = (beer_name_final.lower().strip() == 'dieta' or 
                                          beer_name_final.lower().strip() == brewery_upper.lower() or
                                          (beer_name_final.lower().startswith('dieta') and len(beer_name_final.split()) == 1))
                    if is_only_brewery_name:
                        logger.debug(f"Пропущено название, состоящее только из названия пивоварни: {beer_name_final}")
                        continue
                    
                    # Начинаем новый item
                    current_item = {
                        'beer_name': beer_name_final,
                        'brewery': default_brewery or original_brewery_name
                    }
                    
                    # Добавляем извлеченные данные
                    if extracted_abv:
                        current_item['abv'] = extracted_abv
                    if extracted_price:
                        current_item['price'] = extracted_price
                        current_item['currency'] = 'RUB'
                    if extracted_volume:
                        current_item['volume'] = extracted_volume
                    if extracted_format:
                        current_item['format_type'] = extracted_format
                    
                    item_start_line = line_num
                    logger.debug(f"Начало нового item: beer_name={current_item.get('beer_name')}, abv={extracted_abv}, price={extracted_price}")
            # Ищем стиль в следующей строке (только если не найден в названии)
            elif current_item.get('beer_name') and not current_item.get('style'):
                style_keywords = ['ipa', 'lager', 'ale', 'porter', 'stout', 'gose', 'pilsner', 'sour', 'witbier', 'wheat', 'belgian', 
                                 'эль', 'пилснер', 'traditional', 'imperial', 'berliner', 'weisse', 'вайссе', 'гозэ', 'гозе',
                                 'baltic', 'smoked', 'fruit', 'smoothie', 'saison', 'wit', 'hefeweizen']
                line_lower = line.lower()
                # Пропускаем строки с контактами
                if any(indicator in line_lower for indicator in ['@', 'http', 'www.', 'тел', 'phone', '+7']):
                    continue
                # Пропускаем строки с ценами и датами
                if re.search(r'\d+\.?\d*\s*[рруб₽]', line_lower) or re.search(r'\d+\.\d+\.\d+', line_lower):
                    continue
                # Проверяем, содержит ли строка стиль
                # НО: исключаем служебные слова, которые НЕ являются стилями
                invalid_style_words = ['untappd', 'untapped', 'domination', 'scarlet drank', 'главное', 'участие', 
                                      'iso fucking', 'strong fruit эль в в', 'strong fruit beer', 'в в',
                                      'smoothie', 'sour ale', 'smoothie sour ale',  # "smoothie sour ale" - это стиль, но просто "smoothie" - нет
                                      '(new)', 'new', 'deserve:', 'mango', 'tonic',  # Части названий, не стили
                                      'tomato с базиликом в', 'tomato с тимьяном в',  # Фрагменты описаний
                                      'острый синьор']  # Название, не стиль
                
                # Проверяем, что строка не является служебным словом
                is_invalid_style = any(inv in line_lower for inv in invalid_style_words)
                
                if not is_invalid_style and (any(kw in line_lower for kw in style_keywords) or (len(line) < 50 and len(line) > 3 and not re.match(r'^[\d\s\-–—]+$', line))):
                    # Проверяем, что это не служебная строка
                    if not any(skip in line_lower for skip in ['дата', 'коробка', 'наличии', 'наличие', 'розлива', 'шт']):
                        # Очищаем стиль от лишних символов
                        style_cleaned = line.strip()
                        # Убираем ABV из стиля, если есть
                        style_cleaned = re.sub(r'\s*\d+\.?\d*\s*%ABV?\s*', ' ', style_cleaned, flags=re.IGNORECASE).strip()
                        # Убираем "UNTAPPD" из стиля
                        style_cleaned = re.sub(r'\s*untappd\s*', ' ', style_cleaned, flags=re.IGNORECASE).strip()
                        # Убираем лишние пробелы и дефисы в начале/конце
                        style_cleaned = style_cleaned.strip(' -–—')
                        
                        # Проверяем, что стиль не пустой и не является служебным словом
                        if style_cleaned and style_cleaned.lower() not in invalid_style_words and len(style_cleaned) > 2:
                            # Проверяем, что это похоже на стиль (содержит буквы, не только цифры/символы)
                            if re.search(r'[a-zа-яё]', style_cleaned, re.IGNORECASE):
                                current_item['style'] = style_cleaned
                                logger.debug(f"Найден стиль для {current_item.get('beer_name')}: {style_cleaned}")
            # Ищем ABV (если не найден в названии)
            elif current_item.get('beer_name') and not current_item.get('abv'):
                abv_match = re.search(r'(\d+\.?\d*)\s*%', line)
                if abv_match:
                    current_item['abv'] = abv_match.group(1)
                    logger.debug(f"Найден ABV для {current_item.get('beer_name')}: {current_item['abv']}")
            # Ищем цену (если не найдена в названии)
            elif current_item.get('beer_name') and not current_item.get('price'):
                price_match = re.search(r'(\d+\.?\d*)\s*[рруб₽]', line.lower())
                if price_match:
                    # Проверяем, что это не дата
                    if not re.search(r'\d+\.\d+\.\d+', line):
                        current_item['price'] = price_match.group(1)
                        current_item['currency'] = 'RUB'
                        logger.debug(f"Найдена цена для {current_item.get('beer_name')}: {current_item['price']}")
                        # Пробуем извлечь объем из цены (например, "400р/л")
                        volume_in_price = re.search(r'(\d+\.?\d*)\s*[рруб₽]/\s*л', line.lower())
                        if volume_in_price:
                            current_item['volume'] = '1.0'
                        # Пробуем извлечь формат из строки с ценой
                        format_match = re.search(r'\b(банка|бутылка|кег|keg|can|bottle|бут|б|к)\b', line.lower())
                        if format_match:
                            format_val = format_match.group(1).lower()
                            if format_val in ['банка', 'can', 'б']:
                                current_item['format_type'] = 'банка'
                            elif format_val in ['бутылка', 'bottle', 'бут']:
                                current_item['format_type'] = 'бутылка'
                            elif format_val in ['кег', 'keg', 'к']:
                                current_item['format_type'] = 'кег'
                            # Пробуем извлечь объем кега (например, "кег 20л")
                            if current_item.get('format_type') == 'кег':
                                vol_match = re.search(r'(\d+\.?\d*)\s*л', line.lower())
                                if vol_match:
                                    current_item['volume'] = vol_match.group(1)
                                else:
                                    current_item['volume'] = None  # Неизвестный объем кега
                            # Для банок по умолчанию 0.45л, если не указано
                            elif current_item.get('format_type') == 'банка' and not current_item.get('volume'):
                                vol_match = re.search(r'(\d+\.?\d*)\s*л', line.lower())
                                if vol_match:
                                    current_item['volume'] = vol_match.group(1)
                                else:
                                    current_item['volume'] = '0.45'  # По умолчанию для банок
            # Ищем цену (если не найдена в названии)
            elif current_item.get('beer_name') and not current_item.get('price'):
                price_match = re.search(r'(\d+\.?\d*)\s*[рруб₽p]/?\s*л?', line.lower())
                if price_match:
                    current_item['price'] = price_match.group(1)
                    current_item['currency'] = 'RUB'
                    # Проверяем объем в цене
                    volume_match = re.search(r'(\d+\.?\d*)\s*[рруб₽p]/\s*л', line.lower())
                    if volume_match and not current_item.get('volume'):
                        current_item['volume'] = '1.0'
        
        # Сохраняем последний item (с проверкой на валидность)
        if current_item.get('beer_name'):
            beer_name = current_item.get('beer_name', '')
            beer_name_lower = beer_name.lower()
            
            # ПРОВЕРКА: не сохраняем элементы с общими/служебными названиями или без минимальных данных
            has_minimal_data = current_item.get('price') or current_item.get('abv')
            generic_words = ['traditional', 'smoothie', 'libra', 'baltic', 'porter', 'stout', 'gose', 'pilsner',
                           'ipa', 'ale', 'lager', 'sour', 'collab', 'коллаб', 'fruited', 'fruited розмарином',
                           'крепкий', 'клюквенный', 'клюквой', 'персиком', 'манго']
            is_generic = any(word in beer_name_lower for word in generic_words) and len(beer_name.split()) <= 2
            has_dieta = brewery_upper in beer_name.upper()
            is_too_short = len(beer_name) < 5 and not has_dieta
            
            # КРИТИЧЕСКАЯ ПРОВЕРКА: если название - это только "DIETA" (название пивоварни) без дополнительного названия продукта
            is_only_brewery_name = (beer_name_lower.strip() == 'dieta' or 
                                  beer_name_lower.strip() == brewery_upper.lower() or
                                  (beer_name_lower.startswith('dieta') and len(beer_name.split()) == 1))
            
            has_full_data = current_item.get('price') and current_item.get('abv')
            has_format_or_volume = current_item.get('volume') or current_item.get('format_type')
            is_informative = len(beer_name.split()) >= 2 and not is_generic
            
            # Для элементов из текста требуем наличие объема или формата
            # Если нет объема и формата, даже при наличии цены и ABV - пропускаем (неполные данные)
            if (has_dieta and not is_generic and not is_only_brewery_name) or \
               (is_informative and has_minimal_data) or \
               (has_full_data and not is_only_brewery_name and has_format_or_volume):
                brewery_to_set = default_brewery or original_brewery_name
                if brewery_to_set:
                    from parser_app.domain.services.normalization import DataNormalizer
                    normalizer = DataNormalizer()
                    brewery_normalized = normalizer.normalize_brewery(brewery_to_set)
                    current_item['brewery'] = brewery_normalized if brewery_normalized else brewery_to_set
                current_item['raw_source_location'] = {'page': page_num, 'line': item_start_line}
                items.append(current_item)
                logger.debug(f"Создан последний item из текста: beer_name={beer_name}, brewery={current_item.get('brewery')}, price={current_item.get('price')}, abv={current_item.get('abv')}, volume={current_item.get('volume')}, format={current_item.get('format_type')}")
            else:
                logger.debug(f"Пропущен последний item из текста (недостаточно данных): beer_name={beer_name}, price={current_item.get('price')}, abv={current_item.get('abv')}, volume={current_item.get('volume')}, format={current_item.get('format_type')}, is_only_brewery_name={is_only_brewery_name}, has_format_or_volume={has_format_or_volume}")
        
        # Удаляем дубликаты: если элемент из текста уже есть в таблицах, пропускаем текстовый вариант
        # (элементы из таблиц более полные и точные)
        logger.debug(f"Извлечено {len(items)} элементов из текста")
        
        return items
    
    def _parse_table(self, table: List[List], page_num: int, table_num: int,
                     supplier_type: Optional[SupplierType] = None,
                     default_brewery: Optional[str] = None,
                     original_brewery_name: Optional[str] = None) -> List[Dict]:
        """
        Парсинг таблицы из PDF.
        
        Args:
            table: Таблица как список строк
            page_num: Номер страницы
            table_num: Номер таблицы на странице
            supplier_type: Тип поставщика
            default_brewery: Название пивоварни по умолчанию (нормализованное)
            original_brewery_name: Оригинальное название пивоварни
            
        Returns:
            Список словарей с данными позиций
        """
        items = []
        
        if not table or len(table) < 2:
            logger.debug(f"Таблица пуста или слишком короткая: {len(table) if table else 0} строк")
            return items
        
        logger.debug(f"Парсинг таблицы: {len(table)} строк, {len(table[0]) if table else 0} колонок")
        
        # Пробуем найти строку заголовков (может быть не первая)
        header_row_idx = 0
        headers = []
        col_mapping = {}
        
        # Пробуем первые 5 строк как заголовки
        # Для Dieta после поворота заголовки могут быть в строках 0-1
        for header_idx in range(min(5, len(table))):
            potential_headers = [str(cell).strip().lower() if cell else '' 
                               for cell in table[header_idx]]
            
            # Проверяем, что строка выглядит как заголовки (не содержит данных продуктов)
            # Заголовки обычно короткие, не содержат цен и ABV
            is_likely_header = True
            for header_cell in potential_headers:
                if not header_cell:
                    continue
                # Если ячейка содержит цену или ABV - это не заголовок
                if re.search(r'\d+\s*[рруб₽]', header_cell) or re.search(r'\d+\.?\d*\s*%abv', header_cell, re.IGNORECASE):
                    is_likely_header = False
                    break
                # Если ячейка очень длинная и содержит слова из названий продуктов - это не заголовок
                # Но разрешаем длинные описания заголовков
                if len(header_cell) > 50 and not any(h in header_cell for h in ['объём', 'объем', 'цена', 'описание']):
                    is_likely_header = False
                    break
            
            if not is_likely_header:
                continue
            
            potential_mapping = self._map_columns(potential_headers)
            
            # Более строгая проверка: заголовки должны содержать известные поля
            # или хотя бы несколько распознанных заголовков
            known_header_keywords = ['название', 'наименование', 'name', 'beer', 
                                   'стиль', 'style', 'тип', 'type', 'с/п/пь',
                                   'цена', 'price', 'стоимость', 'cost',
                                   'объём', 'объем', 'volume', 'литр',
                                   'abv', 'ttx', 'ттх', 'крепость',
                                   'формат', 'format', 'упаковка', 'packaging',
                                   'описание', 'description', 'наличие']
            
            has_known_headers = any(
                any(keyword in header for keyword in known_header_keywords)
                for header in potential_headers
            )
            
            # Если нашли известные заголовки или несколько полей - это заголовки
            if has_known_headers and (len(potential_mapping) >= 2 or 'beer_name' in potential_mapping):
                headers = potential_headers
                col_mapping = potential_mapping
                header_row_idx = header_idx
                logger.debug(f"Найдены заголовки в строке {header_idx + 1}, маппинг: {col_mapping}, заголовки: {potential_headers[:5]}")
                self.stats['headers_found'] += 1
                
                # Для Dieta: проверяем строку после заголовков на наличие подзаголовков (например, "кег", "фасовка")
                # Если в следующей строке есть "кег" или "фасовка" - это подзаголовки ценовых колонок
                if header_idx + 1 < len(table):
                    next_row = [str(cell).strip().lower() if cell else '' for cell in table[header_idx + 1]]
                    has_subheaders = any('кег' in cell or 'фасовка' in cell or 'банка' in cell or 'keg' in cell for cell in next_row)
                    if has_subheaders:
                        header_row_idx = header_idx + 1  # Используем строку с подзаголовками как начало данных
                        logger.debug(f"Найдены подзаголовки ценовых колонок в строке {header_idx + 2}")
                break
        
        # Если не нашли заголовки, используем позиционный маппинг
        if not col_mapping:
            logger.debug("Заголовки не найдены, используем позиционный маппинг")
            col_mapping = {
                'beer_name': 0,
                'style': 1,
            }
            # Пробуем найти другие колонки по содержимому первых строк данных
            # Берем несколько строк для более точного определения
            sample_rows = table[1:min(4, len(table))] if len(table) > 1 else []
            
            for sample_row in sample_rows:
                if not sample_row:
                    continue
                for idx, cell in enumerate(sample_row):
                    if idx < 2:
                        continue
                    cell_str = str(cell).strip().lower() if cell else ''
                    if not cell_str or cell_str in ['none', 'nan', '']:
                        continue
                    
                    # ABV обычно содержит % или ABV (например, "8.5%ABV", "11%ABV")
                    if ('%' in cell_str and 'abv' in cell_str) or re.search(r'\d+\.?\d*\s*%abv', cell_str, re.IGNORECASE):
                        if 'abv' not in col_mapping:
                            col_mapping['abv'] = idx
                            logger.debug(f"Определена колонка ABV: индекс {idx} (значение: '{cell_str}')")
                    # Описание обычно длинное (более 30 символов) и содержит описательные слова
                    elif len(cell_str) > 30 and ('untappd' in cell_str or 'imperial' in cell_str or 'traditional' in cell_str or 'традиционный' in cell_str):
                        if 'description' not in col_mapping:
                            col_mapping['description'] = idx
                            logger.debug(f"Определена колонка description: индекс {idx}")
                    # Колонка с ценой и объемом (например, "230р/ банка 0.33л коробка 20шт – 4600р")
                    elif 'р/' in cell_str or 'руб' in cell_str or ('банка' in cell_str and 'л' in cell_str):
                        # Это может быть цена, объем и формат
                        if 'price' not in col_mapping:
                            col_mapping['price'] = idx
                            logger.debug(f"Определена колонка price: индекс {idx}")
                        if 'volume' not in col_mapping:
                            col_mapping['volume'] = idx
                            logger.debug(f"Определена колонка volume: индекс {idx}")
                        if 'format_type' not in col_mapping:
                            col_mapping['format_type'] = idx
                            logger.debug(f"Определена колонка format_type: индекс {idx}")
                    # Наличие обычно короткое и содержит "в наличии"
                    elif cell_str in ['в наличии', 'есть', 'b наличии', 'наличие'] or 'наличии' in cell_str:
                        if 'stock' not in col_mapping:
                            col_mapping['stock'] = idx
                            logger.debug(f"Определена колонка stock: индекс {idx}")
        
        # Определяем ценовые колонки для Dieta (несколько ценовых колонок - для кегов и банок)
        price_columns = {}
        # Ищем ценовые колонки двумя способами:
        # 1. По заголовкам в строке header_row_idx (например, "объ.вицено (м)")
        # 2. По подзаголовкам в следующей строке (например, "кег", "фасовка")
        if headers:
            # Сначала проверяем заголовки
            for col_idx, header in enumerate(headers):
                if col_idx >= len(table[0]):
                    continue
                header_lower = header.lower()
                # Ищем ценовые колонки по заголовкам (объём, объем, цена, объ.вицено)
                if ('объём' in header_lower or 'объем' in header_lower or 'цена' in header_lower or 
                    'price' in header_lower or 'вицено' in header_lower or 'объ.вицено' in header_lower):
                    # Определяем формат и объем из подзаголовка или данных
                    format_type = None
                    volume = None
                    
                    # Проверяем подзаголовки в строке после заголовков (если есть)
                    subheader_row_idx = header_row_idx + 1 if header_row_idx + 1 < len(table) else None
                    if subheader_row_idx is not None and col_idx < len(table[subheader_row_idx]):
                        subheader = str(table[subheader_row_idx][col_idx]).strip().lower() if table[subheader_row_idx][col_idx] else ''
                        # Объединяем многострочные подзаголовки
                        subheader = ' '.join(subheader.split())
                        
                        # OCR коррекция для подзаголовков
                        subheader_ocr = subheader.replace('aer', 'кег').replace('бажжя', 'банка').replace('бачка', 'банка')
                        subheader_ocr = re.sub(r'(\d+)\s*n\s*([\s\-])', r'\1 л\2', subheader_ocr)
                        subheader_ocr = re.sub(r'(\d+)\s*n\s*$', r'\1 л', subheader_ocr)
                        
                        # Определяем формат и объем из подзаголовка
                        if 'кег' in subheader_ocr or 'keg' in subheader_ocr:
                            format_type = 'кег'
                            # Извлекаем объем кега из подзаголовка (например, "кег 20л", "20л кег")
                            vol_match = re.search(r'(\d+\.?\d*)\s*л', subheader_ocr)
                            if vol_match:
                                try:
                                    vol_val = float(vol_match.group(1).replace(',', '.'))
                                    # Объем кега обычно от 10 до 50 литров
                                    if 5 <= vol_val <= 50:
                                        volume = vol_val
                                    else:
                                        volume = None
                                except:
                                    volume = None
                            else:
                                volume = None  # Для кегов, если объем не указан, будет None
                        elif 'банка' in subheader_ocr or 'фасовка' in subheader_ocr or 'can' in subheader_ocr:
                            format_type = 'банка'
                            # Извлекаем объем банки из подзаголовка (например, "банка 0.45л", "0.33л")
                            vol_match = re.search(r'(\d+\.?\d*)\s*л', subheader_ocr)
                            if vol_match:
                                try:
                                    vol_val = float(vol_match.group(1).replace(',', '.'))
                                    # Объем банки обычно от 0.25 до 1 литра
                                    if 0.1 <= vol_val <= 1.5:
                                        volume = vol_val
                                    else:
                                        volume = 0.45  # По умолчанию
                                except:
                                    volume = 0.45
                            else:
                                # Для банок по умолчанию 0.45л, если не указано
                                volume = 0.45
                    
                    # Если формат не определили из подзаголовков, пробуем из первых данных
                    # Пробуем несколько первых строк данных для надежности
                    if not format_type:
                        for sample_row_idx in range(header_row_idx + 2, min(header_row_idx + 5, len(table))):
                            if col_idx < len(table[sample_row_idx]) and table[sample_row_idx][col_idx]:
                                sample_cell = str(table[sample_row_idx][col_idx]).strip().lower()
                                sample_cell = ' '.join(sample_cell.split())  # Объединяем многострочные данные
                                
                                # OCR коррекция
                                sample_cell_ocr = sample_cell.replace('aer', 'кег').replace('бажжя', 'банка').replace('бачка', 'банка')
                                sample_cell_ocr = re.sub(r'(\d+)\s*n\s*([\s\-])', r'\1 л\2', sample_cell_ocr)
                                sample_cell_ocr = re.sub(r'(\d+)\s*n\s*$', r'\1 л', sample_cell_ocr)
                                
                                if 'кег' in sample_cell_ocr or 'keg' in sample_cell_ocr:
                                    format_type = 'кег'
                                    # Извлекаем объем кега
                                    vol_match = re.search(r'(\d+\.?\d*)\s*л', sample_cell_ocr)
                                    if vol_match:
                                        try:
                                            vol_val = float(vol_match.group(1).replace(',', '.'))
                                            if 5 <= vol_val <= 50:
                                                volume = vol_val
                                            else:
                                                volume = None
                                        except:
                                            volume = None
                                    else:
                                        volume = None
                                    break  # Нашли формат, прекращаем поиск
                                elif 'банка' in sample_cell_ocr or 'can' in sample_cell_ocr:
                                    format_type = 'банка'
                                    # Извлекаем объем из данных (например, "220p/ бажжя ( 0.45 )" или "0.45л")
                                    vol_match = re.search(r'\(?\s*(\d+\.?\d*)\s*\)', sample_cell_ocr) or re.search(r'(\d+\.?\d*)\s*л', sample_cell_ocr)
                                    if vol_match:
                                        try:
                                            vol_val = float(vol_match.group(1).replace(',', '.'))
                                            if 0.1 <= vol_val <= 1.5:
                                                volume = vol_val
                                            else:
                                                volume = 0.45
                                        except:
                                            volume = 0.45
                                    else:
                                        volume = 0.45  # По умолчанию для банок
                                    break  # Нашли формат, прекращаем поиск
                    
                    # Добавляем ценовую колонку (даже если формат не определили - определим из данных)
                    price_columns[col_idx] = {
                        'format': format_type,
                        'volume': volume,
                        'header': header
                    }
                    logger.debug(f"Найдена ценовая колонка {col_idx}: format={format_type}, volume={volume}, header='{header}'")
        
        logger.debug(f"Начало парсинга строк таблицы, header_row_idx={header_row_idx}, всего строк={len(table)}, маппинг={col_mapping}, ценовые колонки={list(price_columns.keys())}")
        
        # Парсим строки данных
        for row_num, row in enumerate(table[header_row_idx + 1:], start=header_row_idx + 2):
            if not row or all(not cell or str(cell).strip() == '' for cell in row):
                logger.debug(f"Пропущена пустая строка {row_num}")
                continue
            
            try:
                # Пропускаем строки, которые выглядят как служебные (очень короткие или только числа)
                row_text = ' '.join(str(cell).strip() for cell in row if cell and str(cell).strip())
                if len(row_text) < 5 or re.match(r'^[\d\s\-–—]+$', row_text):
                    logger.debug(f"Пропущена служебная строка {row_num}: {row_text[:50]}")
                    continue
                
                # Проверяем, не является ли строка заголовком или служебной строкой
                # Заголовки обычно короткие и не содержат цен/ABV
                first_cells_text = ' '.join(str(cell).strip().lower() if cell else '' for cell in row[:3] if cell)
                header_keywords = ['название', 'наименование', 'name', 'beer', 'стиль', 'style', 'тип', 'type',
                                 'цена', 'price', 'стоимость', 'cost', 'объём', 'объем', 'volume',
                                 'abv', 'ttx', 'ттх', 'крепость', 'формат', 'format', 'упаковка',
                                 'описание', 'description', 'наличие', 'availability']
                is_likely_header = any(keyword in first_cells_text for keyword in header_keywords)
                # Если строка содержит заголовки и нет цен/ABV - это заголовок, пропускаем
                if is_likely_header and not re.search(r'\d+\s*[рруб₽]', row_text) and not re.search(r'\d+\.?\d*\s*%', row_text):
                    logger.debug(f"Пропущена строка с заголовками {row_num}: {row_text[:50]}")
                    continue
                
                # Проверяем, не является ли первая ячейка заголовком или служебной строкой
                if len(row) > 0 and row[0]:
                    first_cell = str(row[0]).strip().lower()
                    if first_cell in ['название', 'наименование', 'name', 'beer', 'стиль', 'style', 
                                     'ttx', 'ттх', 'цена', 'price', 'объём', 'объем']:
                        logger.debug(f"Пропущена строка с заголовком в первой ячейке {row_num}: {first_cell}")
                        continue
                
                # Строгая проверка: пропускаем строки, которые явно не являются продуктами
                # Проверяем первую ячейку - она должна содержать название продукта, а не данные
                if len(row) > 0 and row[0]:
                    first_cell = str(row[0]).strip()
                    first_lower = first_cell.lower()
                    
                    # Пропускаем если первая ячейка:
                    # 1. Только цена/ABV без названия
                    if (re.search(r'^\d+\.?\d*\s*%\s*$', first_lower) or 
                        re.search(r'^\d+\.?\d*\s*[рруб₽p]\s*$', first_lower)):
                        logger.debug(f"Пропущена строка {row_num}: первая ячейка только цена/ABV: {first_cell}")
                        continue
                    
                    # 2. Заголовки таблиц
                    if first_lower in ['название', 'наименование', 'name', 'beer', 'стиль', 'style']:
                        logger.debug(f"Пропущена строка {row_num}: первая ячейка - заголовок: {first_cell}")
                        continue
                    
                    # 3. Явно служебные строки
                    # НО: разрешаем "(NEW)" в начале - это маркер нового продукта, не служебная строка
                    # НО: разрешаем коллаборации типа "ON THE BONES X DIETA" - это валидное название
                    is_collaboration = (' x ' in first_lower or ' xdieta' in first_lower or 
                                      'x dieta' in first_lower or 'x diеta' in first_lower or
                                      'on the bones' in first_lower or 'libra' in first_lower)
                    if not first_lower.startswith('(new)') and not first_lower.startswith('new') and not is_collaboration:
                        service_indicators = ['дата', 'коробка', 'шт', 'розлива', 'наличии', 'наличие', 
                                             'банка', 'бутылка', 'кег', 'keg', 'can', 'bottle',
                                             'руб', 'р/', '₽', 'литр', 'л', 'l']
                        if (any(indicator in first_lower for indicator in service_indicators) or
                            len(first_cell.strip()) < 3 or
                            # Проверяем, не является ли это строкой с ценой и данными (например, "220р/ Дата коробка...")
                            re.search(r'^\d+\.?\d*\s*[рруб₽]', first_cell) or  # Только если начинается с цены
                            re.search(r'\d+\.\d+\.\d+', first_cell)):  # Дата типа "29.08.25"
                            logger.debug(f"Пропущена строка {row_num}: первая ячейка служебная: {first_cell}")
                            continue
                
                logger.debug(f"Обработка строки {row_num}: строка имеет {len(row)} колонок, первые ячейки={[str(c)[:50] if c else '' for c in row[:3]]}, маппинг={col_mapping}, ценовые колонки={list(price_columns.keys())}")
                
                # Если строка содержит меньше колонок, чем ожидается, но есть данные - пробуем извлечь все
                # ВАЖНО: для таблиц Dieta данные могут быть в одной строке, но не все колонки заполнены
                # Поэтому сначала пробуем извлечь все данные из строки без skip_price
                # Если price_columns пустой, значит данные должны быть в самой строке
                if not price_columns:
                    # Пробуем извлечь все данные из строки (включая price, volume, format из доступных колонок)
                    item = self._extract_row_data(row, col_mapping, original_brewery_name, skip_price=False)
                    if item and item.get('beer_name'):
                        # Для частного поставщика устанавливаем пивоварню
                        if supplier_type == SupplierType.BREWERY:
                            brewery_to_set = None
                            if default_brewery:
                                from parser_app.domain.services.normalization import DataNormalizer
                                normalizer = DataNormalizer()
                                brewery_normalized = normalizer.normalize_brewery(default_brewery)
                                brewery_to_set = brewery_normalized if brewery_normalized else default_brewery
                            elif original_brewery_name:
                                brewery_to_set = original_brewery_name
                            
                            if brewery_to_set:
                                item['brewery'] = brewery_to_set
                                logger.info(f"Установлена пивоварня для частного поставщика в PDF (строка {row_num}): {item['brewery']}")
                        
                item['raw_source_location'] = {
                    'page': page_num,
                    'table': table_num,
                    'row': row_num
                }
                items.append(item)
                logger.debug(f"Извлечен item из строки {row_num}: beer_name={item.get('beer_name')}, brewery={item.get('brewery')}, style={item.get('style')}, abv={item.get('abv')}, price={item.get('price')}, volume={item.get('volume')}, format={item.get('format_type')}")
                continue  # Пропускаем дальнейшую обработку
                
                # Извлекаем базовые данные без цены (название, стиль, ABV, описание)
                base_item = self._extract_row_data(row, col_mapping, original_brewery_name, skip_price=True)
                
                if not base_item:
                    logger.debug(f"Строка {row_num} не содержит данных: {row_text[:100]}")
                    continue
                
                # Проверяем, была ли установлена коллаборация в brewery (это означает, что название пива уже установлено правильно)
                is_collaboration_item = base_item.get('brewery') and ('X' in base_item.get('brewery', '') or 'x' in base_item.get('brewery', ''))
                
                beer_name = base_item.get('beer_name', '').strip()
                beer_name_lower = beer_name.lower()
                
                # Если нет названия и это не коллаборация - пропускаем
                if not beer_name and not is_collaboration_item:
                    logger.debug(f"Строка {row_num} не содержит названия пива: {row_text[:100]}")
                    continue
                
                # Объединяем многострочные значения в названии
                beer_name = ' '.join(beer_name.split())
                beer_name_lower = beer_name.lower()
                
                # Очищаем название от подзаголовков и маркетинговых слоганов
                # НО: если это коллаборация, название пива ("Главное – Участие!") уже установлено в _extract_row_data,
                # и мы НЕ должны его удалять здесь
                if not is_collaboration_item:
                    slogan_patterns = [
                        r'\s*главное\s*[–—\-]\s*участие\s*!?\s*',
                        r'\s*главное\s*участие\s*!?\s*',
                        r'\s*the main thing[–—\-]?\s*participation\s*!?\s*',
                    ]
                    for pattern in slogan_patterns:
                        beer_name = re.sub(pattern, ' ', beer_name, flags=re.IGNORECASE)
                        beer_name = beer_name.strip()
                    beer_name_lower = beer_name.lower()
                
                # Дополнительная проверка: название должно быть валидным
                invalid_names = ['ttx', 'ттх', 'описание', 'description', 'название', 'наименование', 
                                'наличие', 'наличии', 'traditional', 'traditional gose',
                                'копидный', 'копидный', 'опис', 'desc']
                
                service_keywords = ['дата', 'коробка', 'шт', 'розлива', 'наличии', 'наличие',
                                   'банка', 'бутылка', 'кег', 'keg', 'can', 'bottle',
                                   'руб', 'р/', '₽', 'литр', 'л', 'l', 'кг', 'kg']
                
                # Для названий с "DIETA" делаем более мягкую проверку
                # Учитываем "(NEW)" в начале и многострочные значения
                # Также учитываем коллаборации типа "ON THE BONES X DIETA" или "LIBRA X DIETA"
                beer_name_cleaned = beer_name_lower.replace('(new)', '').strip()
                # Очищаем от подзаголовков типа "Главное – Участие!" перед проверкой
                beer_name_cleaned = re.sub(r'\s*главное\s*[–—\-]\s*участие\s*!?\s*', ' ', beer_name_cleaned, flags=re.IGNORECASE).strip()
                # Проверяем, содержит ли название "DIETA" (может быть в начале, после "(NEW)", или в коллаборации)
                # Коллаборации обычно содержат "X" или "x" перед "DIETA"
                is_dieta_name = (beer_name_cleaned.startswith('dieta ') or 
                                beer_name_lower.startswith('dieta ') or 
                                beer_name_lower.startswith('(new) dieta') or
                                ('(new)' in beer_name_lower and 'dieta' in beer_name_lower) or
                                (' x dieta' in beer_name_lower or ' xdieta' in beer_name_lower or 'x dieta' in beer_name_lower or 'x diеta' in beer_name_lower) or  # Коллаборации
                                ('on the bones' in beer_name_lower and 'dieta' in beer_name_lower) or  # Специально для ON THE BONES X DIETA
                                (beer_name_lower.count('dieta') >= 1 and len(beer_name.replace('(NEW)', '').replace('DIETA', '').strip()) > 0))
                
                # Если это коллаборация - название пива уже установлено правильно, пропускаем валидацию
                if is_collaboration_item:
                    logger.debug(f"Разрешено название для коллаборации (строка {row_num}): brewery={base_item.get('brewery')}, beer_name={beer_name}")
                elif is_dieta_name:
                    # Для названий с DIETA проверяем только явно невалидные случаи
                    # Разрешаем ВСЕ названия с DIETA, если после "DIETA" есть хотя бы один символ (кроме пробелов)
                    text_after_dieta = beer_name_cleaned.replace('dieta', '').strip()
                    # Пропускаем только если название - это буквально только "DIETA" (без дополнительного текста)
                    if beer_name_cleaned.strip() == 'dieta' and len(beer_name.strip()) <= 5:
                        logger.debug(f"Пропущена строка {row_num}: название только 'DIETA' без дополнительного текста: {beer_name}")
                        continue
                    # Все остальные названия с DIETA разрешаем - они валидные
                    logger.debug(f"Разрешено название DIETA для строки {row_num}: {beer_name}")
                else:
                    # Для остальных названий - строгая проверка
                    if (beer_name_lower in invalid_names or
                        re.search(r'^\d+\.?\d*\s*%\s*$', beer_name_lower) or
                        re.search(r'^\d+\.?\d*\s*[рруб₽p]\s*$', beer_name_lower) or
                        any(keyword in beer_name_lower for keyword in service_keywords) or
                        re.search(r'\d+\.\d+\.\d+', beer_name_lower) or
                        re.search(r'^\d+\.?\d*\s*[рруб₽p]', beer_name_lower) or  # Только если начинается с цены
                        (len(beer_name) < 5)):
                        logger.debug(f"Пропущена строка {row_num}: невалидное название: {beer_name}")
                        continue
                
                # Обновляем название в base_item (на случай, если оно было многострочным)
                base_item['beer_name'] = beer_name
                
                logger.debug(f"Обработка ценовых колонок для строки {row_num}: price_columns={list(price_columns.keys()) if price_columns else None}, len(row)={len(row)}")
                
                # Если есть несколько ценовых колонок, создаем отдельный элемент для каждой
                if price_columns:
                    logger.debug(f"Найдены ценовые колонки для строки {row_num}: {list(price_columns.keys())}")
                    # Логируем все ячейки строки для диагностики
                    logger.debug(f"Все ячейки строки {row_num}: {[str(cell)[:30] if cell else 'None' for cell in row[:15]]}")
                    
                    for price_col_idx, price_info in price_columns.items():
                        logger.debug(f"Обработка ценовой колонки {price_col_idx} для строки {row_num}: price_info={price_info}, row[price_col_idx]={row[price_col_idx] if price_col_idx < len(row) else 'OUT OF RANGE'}")
                        if price_col_idx >= len(row):
                            logger.debug(f"Пропущена ценовая колонка {price_col_idx} для строки {row_num}: индекс вне диапазона")
                            continue
                        
                        # Проверяем, пустая ли ячейка
                        price_cell_value = row[price_col_idx]
                        if not price_cell_value or (isinstance(price_cell_value, str) and not price_cell_value.strip()):
                            # Пробуем найти цену в соседних ячейках или во всей строке
                            logger.debug(f"Ячейка {price_col_idx} пустая для строки {row_num}, ищем цену в соседних ячейках")
                            # Ищем цену в соседних ячейках (±1, ±2)
                            found_price_cell = None
                            for offset in [-1, 1, -2, 2]:
                                check_idx = price_col_idx + offset
                                if 0 <= check_idx < len(row):
                                    check_cell = row[check_idx]
                                    if check_cell and isinstance(check_cell, str):
                                        # Проверяем, содержит ли ячейка цену
                                        if re.search(r'\d+\.?\d*\s*[рруб₽]', str(check_cell).lower()):
                                            found_price_cell = check_cell
                                            logger.debug(f"Найдена цена в соседней ячейке {check_idx} для строки {row_num}: {str(check_cell)[:50]}")
                                            price_cell_value = found_price_cell
                                            break
                            
                            if not found_price_cell:
                                logger.debug(f"Пропущена ценовая колонка {price_col_idx} для строки {row_num}: ячейка пустая и цена не найдена в соседних")
                                continue
                        
                        # Теперь обрабатываем price_cell_value (либо из основной ячейки, либо из соседней)
                        
                        # Правильно обрабатываем многострочные значения в ценовой колонке
                        # ВАЖНО: не перезаписываем price_cell_value, если мы нашли его в соседней ячейке
                        if isinstance(price_cell_value, list):
                            price_cell = ' '.join(str(v).strip() for v in price_cell_value if v and str(v).strip())
                        else:
                            price_cell = str(price_cell_value).strip()
                        
                        # Объединяем многострочные значения
                        price_cell = ' '.join(price_cell.split())
                        
                        if not price_cell or price_cell.lower() in ['none', 'nan', '', '-', '—', '–']:
                            continue
                        
                        # Создаем копию базового элемента
                        item = base_item.copy()
                        
                        # Извлекаем цену, объем и формат из ценовой колонки
                        price_data = self._extract_price_data(price_cell, price_info.get('format'), price_info.get('volume'))
                        item.update(price_data)
                        
                        # Если цена не извлечена, пытаемся извлечь из самой ячейки напрямую (с OCR коррекцией)
                        if not item.get('price'):
                            # Применяем OCR коррекцию к ячейке
                            price_cell_ocr = price_cell.lower()
                            price_cell_ocr = price_cell_ocr.replace('p/n', 'р/л').replace('p/', 'р/').replace('aer', 'кег')
                            price_cell_ocr = price_cell_ocr.replace('бачка', 'банка').replace('бажжя', 'банка')
                            price_cell_ocr = re.sub(r'(\d+)\s*n\s*([\s\-])', r'\1 л\2', price_cell_ocr)
                            price_cell_ocr = re.sub(r'(\d+)\s*n\s*$', r'\1 л', price_cell_ocr)
                            
                            # Пробуем найти цену (сначала цена за единицу, потом общая)
                            price_per_unit_match = re.search(r'(\d+\.?\d*)\s*[рруб₽]\s*/\s*', price_cell_ocr)
                            if price_per_unit_match:
                                item['price'] = price_per_unit_match.group(1)
                                item['currency'] = 'RUB'
                                logger.debug(f"Найдена цена за единицу в ячейке {price_col_idx} для строки {row_num}: {item['price']}")
                            else:
                                # Пробуем найти любую цену в ячейке
                                all_prices = re.findall(r'(\d+\.?\d*)\s*[рруб₽p]', price_cell_ocr)
                                if all_prices:
                                    # Берем первую цену (обычно это цена за единицу)
                                    item['price'] = all_prices[0]
                                    item['currency'] = 'RUB'
                                    logger.debug(f"Найдена цена напрямую в ячейке {price_col_idx} для строки {row_num}: {item['price']}")
                                else:
                                    logger.debug(f"Пропущена ценовая колонка {price_col_idx} для строки {row_num}: не найдена цена в '{price_cell[:50]}'")
                                    continue
                        
                        # Для частного поставщика добавляем brewery
                        # НО: если brewery уже установлена как коллаборация (содержит "X"), не перезаписываем
                        if supplier_type == SupplierType.BREWERY:
                            # Проверяем, является ли текущая brewery коллаборацией
                            is_collaboration_brewery = item.get('brewery') and ('X' in item.get('brewery', '') or 'x' in item.get('brewery', ''))
                            
                            if not is_collaboration_brewery:
                                brewery_to_set = None
                                if default_brewery:
                                    from parser_app.domain.services.normalization import DataNormalizer
                                    normalizer = DataNormalizer()
                                    brewery_normalized = normalizer.normalize_brewery(default_brewery)
                                    brewery_to_set = brewery_normalized if brewery_normalized else default_brewery
                                elif original_brewery_name:
                                    brewery_to_set = original_brewery_name
                                
                                if brewery_to_set:
                                    item['brewery'] = brewery_to_set
                            else:
                                logger.debug(f"Оставляем коллаборацию как brewery для строки {row_num}: {item.get('brewery')}")
                        
                        item['raw_source_location'] = {
                            'page': page_num,
                            'table': table_num,
                            'row': row_num,
                            'price_column': price_col_idx
                        }
                        items.append(item)
                        logger.debug(f"Создан элемент для строки {row_num}, колонка {price_col_idx}: beer_name={item.get('beer_name')}, format={item.get('format_type')}, price={item.get('price')}")
                else:
                    # Обычная обработка с одной ценовой колонкой
                    # ВАЖНО: извлекаем ВСЕ данные из строки, включая abv, price, volume, format
                    item = self._extract_row_data(row, col_mapping, original_brewery_name, skip_price=False)
                    
                    if not item or not item.get('beer_name'):
                        logger.debug(f"Строка {row_num} не содержит названия пива или item пустой")
                        continue
                    
                    # Для частного поставщика устанавливаем пивоварню
                    # НО: если brewery уже установлена как коллаборация (содержит "X"), не перезаписываем
                    if supplier_type == SupplierType.BREWERY:
                        # Проверяем, является ли текущая brewery коллаборацией
                        is_collaboration_brewery = item.get('brewery') and ('X' in item.get('brewery', '') or 'x' in item.get('brewery', ''))
                        
                        if not is_collaboration_brewery:
                            brewery_to_set = None
                            if default_brewery:
                                from parser_app.domain.services.normalization import DataNormalizer
                                normalizer = DataNormalizer()
                                brewery_normalized = normalizer.normalize_brewery(default_brewery)
                                brewery_to_set = brewery_normalized if brewery_normalized else default_brewery
                            elif original_brewery_name:
                                brewery_to_set = original_brewery_name
                            
                            if brewery_to_set:
                                item['brewery'] = brewery_to_set
                        else:
                            logger.debug(f"Оставляем коллаборацию как brewery для строки {row_num}: {item.get('brewery')}")
                            logger.info(f"Установлена пивоварня для частного поставщика в PDF (строка {row_num}): {item['brewery']}")
                    
                    item['raw_source_location'] = {
                        'page': page_num,
                        'table': table_num,
                        'row': row_num
                    }
                    items.append(item)
                    logger.debug(f"Извлечен item из строки {row_num}: beer_name={item.get('beer_name')}, brewery={item.get('brewery')}, style={item.get('style')}, abv={item.get('abv')}, price={item.get('price')}, volume={item.get('volume')}, format={item.get('format_type')}")
            except Exception as e:
                logger.error(f"Ошибка при обработке строки {row_num}: {str(e)}", exc_info=True)
                continue
        
        return items
    
    def _parse_text_lines(self, text: str, page_num: int,
                          supplier_type: Optional[SupplierType] = None,
                          default_brewery: Optional[str] = None,
                          original_brewery_name: Optional[str] = None) -> List[Dict]:
        """
        Парсинг текста построчно (когда таблиц нет).
        
        Args:
            text: Текст страницы
            page_num: Номер страницы
            supplier_type: Тип поставщика
            default_brewery: Название пивоварни по умолчанию
            original_brewery_name: Оригинальное название пивоварни
            
        Returns:
            Список словарей с данными позиций
        """
        items = []
        lines = text.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or len(line) < 3:
                continue
            
            # Пробуем извлечь данные из строки
            item = self._extract_line_data(line, original_brewery_name)
            if item and item.get('beer_name'):
                # Для частного поставщика устанавливаем пивоварню
                if supplier_type == SupplierType.BREWERY:
                    brewery_to_set = None
                    if default_brewery:
                        from parser_app.domain.services.normalization import DataNormalizer
                        normalizer = DataNormalizer()
                        brewery_normalized = normalizer.normalize_brewery(default_brewery)
                        brewery_to_set = brewery_normalized if brewery_normalized else default_brewery
                    elif original_brewery_name:
                        brewery_to_set = original_brewery_name
                    
                    if brewery_to_set:
                        item['brewery'] = brewery_to_set
                    else:
                        logger.warning(f"Не удалось установить пивоварню для частного поставщика (текст, строка {line_num})")
                
                item['raw_source_location'] = {
                    'page': page_num,
                    'line': line_num
                }
                items.append(item)
        
        return items
    
    def _parse_with_ocr(self) -> List[Dict]:
        """
        Парсинг PDF через OCR (для сканов).
        
        Returns:
            Список словарей с данными позиций
        """
        items = []
        # TODO: Реализовать OCR парсинг при необходимости
        # Это требует преобразования PDF страниц в изображения
        return items
    
    def _map_columns(self, headers: List[str]) -> Dict[str, int]:
        """
        Определяет соответствие колонок заголовкам.
        
        Args:
            headers: Список заголовков колонок
            
        Returns:
            Словарь {название_поля: индекс_колонки}
        """
        mapping = {}
        
        # Варианты названий для каждого поля (расширенный список)
        field_patterns = {
            'brewery': ['пивоварня', 'производитель', 'brewery',
                        'manufacturer', 'brand', 'бренд', 'марка',
                        'пивовар', 'произв', 'brewer', 'producer'],
            'beer_name': ['название', 'пиво', 'beer', 'name',
                          'наименование', 'товар', 'продукт',
                          'назв', 'наим', 'product'],
            'style': ['стиль', 'style', 'тип', 'type', 'сорт', 'с/п/пь', 'с/п/п', 'с.п.п', 'с п п', 'category', 'вид'],
            'abv': ['abv', 'крепость', 'алкоголь', 'alcohol',
                    'алк', '%', 'объемная доля', 'ttx', 'ттх', 'ттx', 'alc'],
            'ibu': ['ibu', 'горечь', 'bitterness', 'горьк'],
            'price': ['цена', 'price', 'стоимость', 'cost', 'руб',
                      'рублей', '₽', 'eur', 'usd', '$', '€',
                      'объём/цена', 'объем/цена',
                      'объём/цена кег', 'объем/цена кег',
                      'объём/цена фасовка', 'объем/цена фасовка'],
            'currency': ['валюта', 'currency', 'curr'],
            'volume': ['объём', 'volume', 'литр', 'литров', 'л',
                       'ml', 'мл', 'литры',
                       'объём/цена', 'объем/цена',
                       'объём/цена кег', 'объем/цена кег',
                       'объём/цена фасовка', 'объем/цена фасовка',
                       'lt', 'l.'],
            'format_type': ['формат', 'format', 'упаковка',
                            'packaging', 'банка', 'бутылка', 'кeg',
                            'кег', 'бут', 'бут',
                            'объём/цена фасовка', 'объем/цена фасовка',
                            'тара', 'фасовка'],
            'stock': ['остаток', 'stock', 'наличие', 'availability',
                      'в наличии', 'есть', 'доступно', 'наличие кег',
                      'наличие фасовка'],
            'description': ['описание', 'description', 'desc', 'коммент'],
        }
        
        # Сначала ищем точные совпадения для всех полей
        exact_matches = {}
        for idx, header in enumerate(headers):
            header_lower = header.lower().strip()
            if not header_lower:
                continue
            
            # Проверяем точные совпадения для каждого поля
            for field, patterns in field_patterns.items():
                if field in exact_matches:
                    continue
                for pattern in patterns:
                    pattern_lower = pattern.lower()
                    if header_lower == pattern_lower:
                        exact_matches[field] = idx
                        mapping[field] = idx
                        break
                if field in exact_matches:
                    break
        
        # Затем ищем частичные совпадения для полей, которые еще не найдены
        for field, patterns in field_patterns.items():
            if field in mapping:
                continue
            
            best_match_idx = None
            best_match_length = 0
            
            for idx, header in enumerate(headers):
                header_lower = header.lower().strip()
                if not header_lower:
                    continue
                
                # Для каждого паттерна проверяем вхождение в заголовок
                for pattern in patterns:
                    pattern_lower = pattern.lower()
                    # Вхождение паттерна в заголовок
                    if pattern_lower in header_lower:
                        # Приоритет более длинным паттернам и точным совпадениям
                        pattern_length = len(pattern_lower)
                        # Проверяем, что паттерн не слишком короткий или это начало/конец заголовка
                        if pattern_length >= 3 or header_lower.startswith(pattern_lower) or header_lower.endswith(pattern_lower):
                            # Если паттерн длиннее текущего лучшего совпадения - используем его
                            if pattern_length > best_match_length:
                                best_match_idx = idx
                                best_match_length = pattern_length
                                break
            
            # Если нашли лучшее совпадение, добавляем в маппинг
            if best_match_idx is not None:
                mapping[field] = best_match_idx
        
        logger.debug(f"Маппинг колонок: {mapping}, заголовки: {headers}")
        return mapping
    
    def _extract_row_data(self, row: List, col_mapping: Dict[str, int], 
                         original_brewery_name: Optional[str] = None,
                         skip_price: bool = False) -> Optional[Dict]:
        """
        Извлекает данные из строки таблицы.
        
        Args:
            row: Строка таблицы
            col_mapping: Соответствие полей и индексов колонок
            original_brewery_name: Оригинальное название пивоварни (для извлечения из названия)
            
        Returns:
            Словарь с данными позиции или None
        """
        item = {}
        
        # Извлекаем значения по маппингу
        logger.debug(f"_extract_row_data: row имеет {len(row)} колонок, маппинг={col_mapping}, skip_price={skip_price}")
        for field, idx in col_mapping.items():
            # Пропускаем цену, если skip_price=True (для обработки нескольких ценовых колонок)
            if skip_price and field == 'price':
                continue
            
            if idx < len(row) and row[idx]:
                logger.debug(f"_extract_row_data: извлечение поля '{field}' из колонки {idx}, значение='{row[idx]}'")
                # Правильно обрабатываем многострочные значения
                # Если это список (многострочная ячейка), объединяем
                cell_value = row[idx]
                if isinstance(cell_value, list):
                    value = ' '.join(str(v).strip() for v in cell_value if v and str(v).strip())
                else:
                    value = str(cell_value).strip()
                
                # Объединяем многострочные значения (например, названия или описания)
                # Убираем переносы строк и лишние пробелы
                value = ' '.join(value.split())
                
                if value and value.lower() not in ['-', '—', '–', 'nan', 'none', 'null', 'n/a', 'na', '']:
                    # Обработка специальных полей
                    if field == 'beer_name':
                        # Очищаем от префикса "(NEW)"
                        value = re.sub(r'^\(NEW\)\s*', '', value, flags=re.IGNORECASE).strip()
                        # Убираем лишние пробелы и переносы строк
                        value = ' '.join(value.split())
                        
                        # ОСОБЫЙ СЛУЧАЙ: Если название содержит коллаборацию типа "ON THE BONES X DIETA Главное – Участие!"
                        # "ON THE BONES X DIETA" - это коллаборация (пивоварня), "Главное – Участие!" - это название пива
                        # Паттерн: коллаборация может быть в начале или в середине, название пива может быть после
                        collaboration_patterns = [
                            # Паттерн 1: "ON THE BONES X DIETA Главное – Участие!"
                            re.compile(r'^(ON THE BONES|LIBRA)\s+X\s+DIETA\s+(.+)$', re.IGNORECASE),
                            # Паттерн 2: "ON THE BONES X\nDIETA\nГлавное –\nУчастие!" (многострочный)
                            re.compile(r'^(ON THE BONES|LIBRA)\s+X\s+DIETA\s+(.+)$', re.IGNORECASE | re.DOTALL),
                        ]
                        
                        collaboration_found = False
                        for pattern in collaboration_patterns:
                            match = pattern.match(value)
                            if match:
                                collaboration_part = match.group(1).strip() + ' X DIETA'
                                beer_name_part = match.group(2).strip()
                                
                                # Извлекаем название пива - ищем "Главное – Участие!"
                                main_thing_match = re.search(r'главное\s*[–—\-]\s*участие\s*!?', beer_name_part, re.IGNORECASE)
                                if main_thing_match:
                                    beer_name_part = main_thing_match.group(0).strip()
                                else:
                                    # Если "Главное – Участие!" не найдено в beer_name_part, ищем во всем value
                                    main_thing_match_full = re.search(r'главное\s*[–—\-]\s*участие\s*!?', value, re.IGNORECASE)
                                    if main_thing_match_full:
                                        beer_name_part = main_thing_match_full.group(0).strip()
                                
                                # Устанавливаем коллаборацию как brewery
                                if not item.get('brewery') or item.get('brewery') == original_brewery_name or item.get('brewery') == 'Dieta':
                                    item['brewery'] = collaboration_part
                                    logger.debug(f"Установлена коллаборация как brewery: {collaboration_part}")
                                
                                # Устанавливаем название пива
                                if beer_name_part:
                                    item[field] = beer_name_part
                                    logger.debug(f"Установлено название пива из коллаборации: {beer_name_part}")
                                else:
                                    # Если не нашли "Главное – Участие!", используем всю строку как название
                                    item[field] = value
                                    
                                collaboration_found = True
                                break
                        
                        if not collaboration_found:
                            # Если название содержит "DIETA" и несколько слов, убираем "DIETA" из начала, если оно дублируется
                            # Например: "DIETA\nISO FUCKING\nTONIC" -> "DIETA ISO FUCKING TONIC" (оставляем как есть)
                            # Или: "DIETA\nSeven Seas" -> "DIETA Seven Seas" (оставляем как есть)
                            
                            # Важно: не перезаписываем, если уже установлено
                            if not item.get(field):
                                item[field] = value
                    elif field == 'style':
                        # Убираем лишние пробелы и переносы строк
                        value = ' '.join(value.split())
                        # Фильтруем служебные слова и данные из других колонок
                        # Если в значении есть ABV или цена - это не стиль
                        if not re.search(r'\d+\.?\d*\s*%abv', value, re.IGNORECASE) and not re.search(r'\d+\s*[рруб₽p]', value):
                            # Не перезаписываем, если уже установлено
                            if not item.get(field):
                                item[field] = value
                    elif field == 'description':
                        # Убираем лишние пробелы и переносы строк
                        value = ' '.join(value.split())
                        item[field] = value
                    elif field == 'abv':
                        # Извлекаем число из строки типа "8.5%ABV" или "8.5%"
                        abv_match = re.search(r'(\d+\.?\d*)\s*%', value, re.IGNORECASE)
                        if abv_match:
                            item[field] = abv_match.group(1)
                        else:
                            # Пробуем найти просто число
                            num_match = re.search(r'(\d+\.?\d*)', value)
                            if num_match:
                                item[field] = num_match.group(1)
                    elif field == 'price':
                        # Извлекаем цену из различных форматов:
                        # "380р/л", "220р/ банка 0.45л", "коробка 20шт – 4400р", "кег 20л – 7600р"
                        # "230р/ банка 0.33л коробка 20шт – 4600р"
                        value_lower = value.lower()
                        
                        # Для Dieta: часто цена указана в формате "230р/ банка 0.33л коробка 20шт – 4600р"
                        # Берем первую цену (цену за единицу), а не общую цену коробки
                        
                        # Сначала пробуем найти цену за единицу (например, "230р/ банка")
                        price_per_unit = re.search(r'(\d+\.?\d*)\s*[рруб₽]\s*/\s*', value_lower)
                        if price_per_unit:
                            item[field] = price_per_unit.group(1)
                            item['currency'] = 'RUB'
                            # Пробуем извлечь объем из цены (например, "230р/ банка 0.33л")
                            volume_match = re.search(r'(\d+\.?\d*)\s*л', value_lower)
                            if volume_match:
                                vol_val = volume_match.group(1)
                                try:
                                    # Преобразуем в число
                                    vol_float = float(vol_val.replace(',', '.'))
                                    item['volume'] = vol_float
                                except:
                                    item['volume'] = vol_val
                            # Пробуем извлечь формат (например, "банка", "бутылка", "кег")
                            format_match = re.search(r'\b(банка|бутылка|кег|keg|can|bottle|бут|б|к)\b', value_lower)
                            if format_match:
                                format_val = format_match.group(1).lower()
                                # Нормализуем формат
                                if format_val in ['банка', 'can', 'б']:
                                    item['format_type'] = 'банка'
                                elif format_val in ['бутылка', 'bottle', 'бут']:
                                    item['format_type'] = 'бутылка'
                                elif format_val in ['кег', 'keg', 'к']:
                                    item['format_type'] = 'кег'
                                else:
                                    item['format_type'] = format_val
                        else:
                            # Пробуем найти общую цену (например, "4400р", "7600р")
                            # Но только если нет цены за единицу
                            total_price = re.search(r'(\d+\.?\d*)\s*[рруб₽]', value_lower)
                            if total_price:
                                item[field] = total_price.group(1)
                                item['currency'] = 'RUB'
                            else:
                                # Пробуем найти просто число
                                num_match = re.search(r'(\d+\.?\d*)', value)
                                if num_match:
                                    item[field] = num_match.group(1)
                                    item['currency'] = 'RUB'
                    elif field == 'volume':
                        # Извлекаем объем из строк типа "0.45л", "20л", "кег 20л"
                        volume_match = re.search(r'(\d+\.?\d*)\s*л', value.lower())
                        if volume_match:
                            item[field] = volume_match.group(1)
                        else:
                            # Пробуем найти просто число с литрами
                            num_match = re.search(r'(\d+\.?\d*)', value)
                            if num_match:
                                item[field] = num_match.group(1)
                    elif field == 'format_type':
                        # Извлекаем формат из строк типа "банка", "бутылка", "кег"
                        format_match = re.search(r'\b(банка|бутылка|кег|keg|can|bottle|бут|б|к)\b', value.lower())
                        if format_match:
                            item[field] = format_match.group(1)
                        else:
                            item[field] = value
                    else:
                        item[field] = value
        
        # Если нет названия пива, но есть данные в первой колонке - пробуем использовать её
        # НО: проверяем, что это действительно название продукта, а не данные из других колонок
        if not item.get('beer_name') and len(row) > 0 and row[0]:
            # Правильно обрабатываем многострочные значения
            first_cell_value = row[0]
            if isinstance(first_cell_value, list):
                first_cell = ' '.join(str(v).strip() for v in first_cell_value if v and str(v).strip())
            else:
                first_cell = str(first_cell_value).strip()
            
            # Объединяем многострочные значения
            first_cell = ' '.join(first_cell.split())
            
            if first_cell and len(first_cell) > 3:
                # Пропускаем служебные строки и заголовки
                first_lower = first_cell.lower()
                if any(skip in first_lower for skip in ['дата', 'коробка', 'руб', 'р/', 'шт', 'литр', 'л', 'наличии', 'наличие', 
                                                         'название', 'наименование', 'name', 'beer', 'стиль', 'style',
                                                         'ttx', 'ттх', 'цена', 'price', 'объём', 'объем', 'volume',
                                                         'формат', 'format', 'описание', 'description', 'опис']):
                    return None
                
                # Пропускаем строки с данными продуктов в первой колонке (например, "4.5%ABV 3800p", "TTX", "кег")
                if re.search(r'\d+\.?\d*\s*%', first_cell) or re.search(r'\d+\s*[рруб₽]', first_cell):
                    return None
                if first_lower in ['ttx', 'ттх', 'кег', 'keg', 'банка', 'can', 'бутылка', 'bottle', 'traditional']:
                    return None
                
                # Пропускаем строки, которые явно являются данными, а не названиями
                # Например, "220р/ Дата коробка 29.08.25 4400р банка розлива: 20шт 0.45л"
                if re.search(r'\d+\.?\d*\s*[рруб₽]', first_cell) or re.search(r'\d+\.\d+\.\d+', first_cell):  # Дата
                    return None
                if any(word in first_lower for word in ['розлива', 'коробка', 'шт', 'дата', 'в наличии', 'наличии']):
                    return None
                
                # Очищаем от префиксов
                cleaned_name = re.sub(r'^\(NEW\)\s*', '', first_cell, flags=re.IGNORECASE).strip()
                # Проверяем, что это похоже на название (не только цифры, не слишком короткое)
                # И не содержит явных данных продуктов (цены, даты, форматы)
                if cleaned_name and len(cleaned_name) >= 5:
                    # Проверяем, что это не только данные
                    if not re.match(r'^[\d\s\-–—\.]+$', cleaned_name):
                        # Проверяем, что название не начинается с цены или формата
                        if not re.match(r'^[\d\s\-–—\.]+$', cleaned_name[:10]):
                            item['beer_name'] = cleaned_name
        
        # Если нет хотя бы названия пива, пропускаем
        if not item.get('beer_name'):
            return None
        
        # Дополнительная валидация: название должно быть достаточно информативным
        beer_name = item.get('beer_name', '')
        beer_name_lower = beer_name.lower().strip()
        
        # Проверяем, является ли это коллаборацией (например, "ON THE BONES X DIETA")
        is_collaboration = (' x ' in beer_name_lower or ' xdieta' in beer_name_lower or 
                          'x dieta' in beer_name_lower or 'x diеta' in beer_name_lower or
                          'on the bones' in beer_name_lower or 'libra' in beer_name_lower or
                          beer_name_lower.count('dieta') >= 1)
        
        # Список служебных слов и фраз, которые НЕ должны быть названиями пива
        # НО: для коллабораций эти проверки более мягкие
        service_words = [
            'название', 'наименование', 'пиво', 'beer', 'товар', 'продукт', 
            'ttx', 'ттх', 'описание', 'description', 'стиль', 'style',
            'traditional', 'traditional gose', 'smoothie', 'smoothie sour ale',
            'strong fruit beer', 'feather', 'bohemian pforer',
            # УДАЛЕНО 'в собственном', 'в собственное', 'собственное', 'собственных' - это может быть часть названия
            # УДАЛЕНО 'участие', 'участие!' - это может быть часть названия типа "Главное – Участие!"
            'в наличии', 'наличии', 'наличие', 'в наличии!',
            'дата', 'коробка', 'шт', 'розлива', 'розлив',
            'банка', 'кег', 'кега', 'бутылка',
            # УДАЛЕНО 'соку:', 'соку' - это может быть часть названия (например, "DIETA В Собственном Соку: Вишня")
            # УДАЛЕНО 'в собственном' - это может быть часть названия
            # УДАЛЕНО 'и друг его', 'и братец', 'друг его', 'братец' - это могут быть части названий (например, "DIETA Синьор Помидор И Друг Его Тимьян")
            'десерт в твоем', 'в твоем', 'твоем бокале',
            'ерсиком и манг', 'персиком и манго', 'и манго',
            'розовой гуавой', 'гуавой', 'гуава',
            # УДАЛЕНО 'остр', 'signor', 'сеньор', 'сень', 'помидор', 'тимьян', 'thyme', 'розмарин', 'rosemary' 
            # - это могут быть части названий
            # УДАЛЕНО 'iso fucking', 'fucking' - это может быть часть названия (например, "DIETA ISO FUCKING TONIC")
            'untappd', 'untapped', 'untappd!'
            # ПРОВЕРЯЕМ отдельно: если название - это только "DIETA" без дополнительного текста,
            # это не валидное название пива (это название пивоварни)
        ]
        
        # Проверяем минимальную длину
        if len(beer_name) < 3:
            logger.debug(f"Пропущена строка: название слишком короткое: '{beer_name}'")
            return None
        
        # ОСОБАЯ ПРОВЕРКА: если название - это только "DIETA" (название пивоварни) без названия пива
        # НО: разрешаем названия типа "DIETA ISO FUCKING TONIC" или "DIETA Hot Smoothie You"
        # Проверяем, что после "DIETA" есть дополнительные слова (не только одно слово после DIETA)
        if beer_name_lower.strip() == 'диета' or beer_name_lower.strip() == 'dieta':
            logger.debug(f"Пропущена строка: название является только названием пивоварни без названия пива: '{beer_name}'")
            return None
        
        # Если название начинается с "DIETA", проверяем содержимое
        # Например, "DIETA ISO FUCKING TONIC" или "DIETA В Собственном Соку: Вишня" - это валидные названия
        if beer_name_lower.startswith('диета ') or beer_name_lower.startswith('dieta '):
            # Подсчитываем количество символов после "DIETA"
            words_after_dieta = beer_name_lower.replace('диета ', '').replace('dieta ', '').strip()
            # Если после DIETA ничего нет или только один короткий фрагмент - это может быть служебное
            if not words_after_dieta or len(words_after_dieta) < 3:
                logger.debug(f"Пропущена строка: название начинается с DIETA, но слишком короткое: '{beer_name}'")
                return None
            # Иначе - это валидное название (например, "DIETA ISO FUCKING TONIC", "DIETA В Собственном Соку: Вишня")
        
        # Проверяем служебные слова
        # НО: для названий с DIETA делаем более мягкую проверку - разрешаем все валидные названия
        # Также проверяем коллаборации (например, "ON THE BONES X DIETA")
        is_dieta_name_final = (beer_name_lower.startswith('dieta ') or 
                              beer_name_lower.startswith('(new) dieta') or
                              '(new)' in beer_name_lower and 'dieta' in beer_name_lower or
                              beer_name_lower.startswith('dieta') and len(beer_name) > 5 or
                              # Коллаборации типа "ON THE BONES X DIETA" или "LIBRA X DIETA"
                              (' x ' in beer_name_lower and 'dieta' in beer_name_lower) or
                              ('on the bones' in beer_name_lower and 'dieta' in beer_name_lower) or
                              ('libra' in beer_name_lower and 'dieta' in beer_name_lower))
        
        # Если это коллаборация или название с DIETA - пропускаем проверку служебных слов
        # Только проверяем, что это не только служебное слово без названия
        if is_dieta_name_final or is_collaboration:
            # Для коллабораций и названий с DIETA - разрешаем подзаголовки типа "Главное – Участие!"
            # Они будут удалены при очистке названия выше
            pass
        else:
            # Для не-DIETA названий - строгая проверка служебных слов
            if beer_name_lower in service_words or any(sw in beer_name_lower for sw in service_words):
                logger.debug(f"Пропущена строка: название является служебным словом: '{beer_name}'")
                return None
        
        # Проверяем, что название - не только ABV (например, "11%ABV", "8.5%")
        if re.search(r'^\d+\.?\d*\s*%', beer_name_lower) or re.search(r'^\d+\.?\d*\s*%abv\s*$', beer_name_lower):
            logger.debug(f"Пропущена строка: название содержит только ABV: '{beer_name}'")
            return None
        
        # Проверяем, что название - не только цена (например, "230р", "4400р")
        if re.search(r'^\d+\.?\d*\s*[рруб₽p]\s*$', beer_name_lower):
            logger.debug(f"Пропущена строка: название содержит только цену: '{beer_name}'")
            return None
        
        # Проверяем, что название - не цена с описанием (например, "230р/ банка 0.33л коробка 20шт – 4600р")
        if re.search(r'\d+\s*[рруб₽]\s*/\s*', beer_name_lower) or re.search(r'\d+\s*[рруб₽]\s+[а-я]+\s+\d+', beer_name_lower):
            logger.debug(f"Пропущена строка: название содержит цену: '{beer_name}'")
            return None
        
        # Проверяем, что название - не дата (например, "21.07.25", "29.08.25")
        if re.search(r'\d+\.\d+\.\d+', beer_name_lower):
            logger.debug(f"Пропущена строка: название содержит дату: '{beer_name}'")
            return None
        
        # Проверяем, что название не начинается с предлогов и союзов (например, "И Друг Его", "В Собственном")
        if re.match(r'^(и|в|на|с|по|для|о|об|от|из|к|у|за|под|над|про|при|перед|после|между|среди|через|без|ради|согласно)\s+', beer_name_lower):
            # Но разрешаем, если это часть реального названия (например, "In Your Mouth")
            if not any(word in beer_name_lower for word in ['mouth', 'glass', 'bone', 'own', 'your', 'his', 'the']):
                logger.debug(f"Пропущена строка: название начинается с предлога/союза: '{beer_name}'")
                return None
        
        # Проверяем, что название не является фрагментом (например, "ерсиком и манг", "розовой гуавой,")
        if beer_name_lower.endswith(',') or beer_name_lower.endswith('.'):
            if len(beer_name) < 10:  # Короткие фрагменты с запятой/точкой - скорее всего фрагменты
                logger.debug(f"Пропущена строка: название является фрагментом: '{beer_name}'")
            return None
        
        return item
    
    def _extract_line_data(self, line: str, original_brewery_name: Optional[str] = None) -> Optional[Dict]:
        """
        Извлекает данные из текстовой строки.
        
        Args:
            line: Текстовая строка
            original_brewery_name: Оригинальное название пивоварни
            
        Returns:
            Словарь с данными позиции или None
        """
        # Пробуем найти паттерн: название пива, стиль, ABV
        # Например: "DIETA X LIBRA Костёр Smoked Baltic Porter 8.5%ABV"
        pattern = r'(.+?)\s+([A-Z][a-z\s]+(?:Porter|Ale|IPA|Lager|Gose|Pilsner|Stout|Sour)[a-z\s]*)\s+(\d+\.?\d*)%'
        match = re.search(pattern, line, re.IGNORECASE)
        
        if match:
            beer_name = match.group(1).strip()
            style = match.group(2).strip()
            abv = match.group(3).strip()
            
            # Очищаем название от префиксов
            beer_name = re.sub(r'^\(NEW\)\s*', '', beer_name, flags=re.IGNORECASE).strip()
            
            item = {
                'beer_name': beer_name,
                'style': style,
                'abv': abv
            }
            
            # Если это частный поставщик, извлекаем пивоварню из названия
            if original_brewery_name:
                beer_name_upper = beer_name.upper()
                brewery_upper = original_brewery_name.upper()
                if brewery_upper in beer_name_upper:
                    item['brewery'] = original_brewery_name
            
            return item
        
        return None
    
    def _extract_price_data(self, price_cell: str, format_type: Optional[str] = None, 
                           volume: Optional[float] = None) -> Dict:
        """
        Извлекает данные о цене, объеме и формате из ячейки с ценой.
        
        Args:
            price_cell: Текст ячейки с ценой (например, "230р/ банка 0.33л коробка 20шт – 4600р" или "220p/ бажжя ( 0.45 )")
            format_type: Тип формата (если известен из заголовка)
            volume: Объем (если известен из заголовка)
            
        Returns:
            Словарь с полями price, volume, format_type, currency
        """
        result = {}
        price_cell_lower = price_cell.lower()
        
        # Объединяем многострочный текст
        price_cell_lower = ' '.join(price_cell_lower.split())
        
        # OCR ошибки: исправляем распространенные ошибки
        # ВАЖНО: порядок замен имеет значение - сначала специфичные паттерны, потом общие
        
        # Замены для формата: "aer" -> "кег", "бажжя"/"бачка" -> "банка"
        price_cell_lower = price_cell_lower.replace('aer', 'кег').replace('бажжя', 'банка').replace('бачка', 'банка')
        
        # Замены для валюты и единиц: "p/n" -> "р/л", "p/" -> "р/", "uгr" -> "шт"
        price_cell_lower = price_cell_lower.replace('p/n', 'р/л').replace('p/', 'р/').replace('uгr', 'шт')
        
        # Заменяем "n" на "л" только если это не часть других слов (например, "new" -> "new", но "20n" -> "20л")
        # Сначала обрабатываем паттерны с цифрами: "20n -" -> "20л -", "20n" -> "20л"
        price_cell_lower = re.sub(r'(\d+\.?\d*)\s*n\s*([\s\-])', r'\1 л\2', price_cell_lower)  # "20n -" -> "20л -"
        price_cell_lower = re.sub(r'(\d+\.?\d*)\s*n\s*$', r'\1 л', price_cell_lower)  # "20n" в конце -> "20л"
        price_cell_lower = re.sub(r'(\d+\.?\d*)\s*n\s*р', r'\1 л р', price_cell_lower)  # "20nр" -> "20л р"
        
        # Дополнительные OCR ошибки для объемов
        price_cell_lower = re.sub(r'0\.00s', '0.45л', price_cell_lower)  # "0.00s" -> "0.45л" (ошибка OCR)
        price_cell_lower = re.sub(r'(\d+)\.(\d+)\s*[il1]', r'\1.\2л', price_cell_lower)  # "0.45i" -> "0.45л"
        
        # Исправляем "кега" -> "кег", "банки" -> "банка"
        price_cell_lower = re.sub(r'\bкега\b', 'кег', price_cell_lower)
        price_cell_lower = re.sub(r'\bбанки\b', 'банка', price_cell_lower)
        
        # Извлекаем цену за единицу (например, "230р/ банка" или "380р/л")
        # Формат может быть: "380р/л", "220р/ банка 0.45л", "230р/ бачка (0.45)"
        price_per_unit = re.search(r'(\d+\.?\d*)\s*[рруб₽]\s*/\s*', price_cell_lower)
        if price_per_unit:
            result['price'] = price_per_unit.group(1)
            result['currency'] = 'RUB'
        else:
            # Если нет "р/", пробуем найти просто цену (например, "7600р", "4800р")
            # НО: сначала ищем цену за единицу, потом общую цену
            # Общая цена обычно больше (например, "7600р" для кега)
            # Цена за единицу обычно меньше (например, "380р/л")
            
            # Ищем все цены в ячейке
            all_prices = re.findall(r'(\d+\.?\d*)\s*[рруб₽]', price_cell_lower)
            if all_prices:
                # Берем первую цену (обычно это цена за единицу)
                # Если цена очень большая (> 3000), это может быть общая цена, но все равно берем её
                result['price'] = all_prices[0]
                result['currency'] = 'RUB'
            else:
                # Если не нашли цену с "р", пробуем просто число
                num_match = re.search(r'^(\d+\.?\d*)', price_cell_lower)
                if num_match:
                    result['price'] = num_match.group(1)
                    result['currency'] = 'RUB'
        
        # Определяем формат
        if not format_type:
            # Проверяем OCR ошибки: "бажжя" = "банка", "бачка" = "банка", "aer" = "кег"
            if 'бажжя' in price_cell_lower or 'бачка' in price_cell_lower or 'банка' in price_cell_lower or 'can' in price_cell_lower:
                result['format_type'] = 'банка'
            elif 'aer' in price_cell_lower or 'кег' in price_cell_lower or 'keg' in price_cell_lower:
                result['format_type'] = 'кег'
            else:
                format_match = re.search(r'\b(банка|бутылка|кег|keg|can|bottle|бут|б|к|бажжя|бачка|aer)\b', price_cell_lower)
                if format_match:
                    format_val = format_match.group(1).lower()
                    if format_val in ['банка', 'can', 'б', 'бажжя', 'бачка']:
                        result['format_type'] = 'банка'
                    elif format_val in ['бутылка', 'bottle', 'бут']:
                        result['format_type'] = 'бутылка'
                    elif format_val in ['кег', 'keg', 'к', 'aer']:
                        result['format_type'] = 'кег'
                    else:
                        result['format_type'] = format_val
        else:
            result['format_type'] = format_type
        
        # Извлекаем объем
        if volume is None:
            # Ищем объем в скобках (например, "( 0.45 )" или "(0.33)" или "( 120")
            volume_match = re.search(r'\(?\s*(\d+\.?\d*)\s*\)', price_cell_lower)
            if volume_match:
                vol_val = volume_match.group(1)
                try:
                    vol_float = float(vol_val.replace(',', '.'))
                    # Если объем больше 10, это может быть количество штук, не литры - пропускаем
                    if vol_float <= 10:
                        result['volume'] = vol_float
                except:
                    pass
            
            # Ищем "Xл" (например, "0.45л" или "20л")
            # После OCR исправления "n" уже заменено на "л"
            if 'volume' not in result:
                volume_match = re.search(r'(\d+\.?\d*)\s*л', price_cell_lower)
                if volume_match:
                    vol_val = volume_match.group(1)
                    try:
                        vol_float = float(vol_val.replace(',', '.'))
                        # Если объем больше 10 для банок - это может быть ошибка, но для кегов это нормально
                        if vol_float <= 10 or result.get('format_type') == 'кег':
                            result['volume'] = vol_float
                    except:
                        pass
            
            # Если не нашли объем и это банка - ставим по умолчанию 0.45
            if 'volume' not in result and result.get('format_type') == 'банка':
                result['volume'] = 0.45
            # Если не нашли объем и это кег - оставляем None (будет показано как "-")
            elif 'volume' not in result and result.get('format_type') == 'кег':
                result['volume'] = None
        else:
            result['volume'] = volume
        
        return result
    
    def _parse_dieta_card_layout(self, table: List[List], page_num: int, table_num: int,
                                 default_brewery: Optional[str] = None,
                                 original_brewery_name: Optional[str] = None) -> List[Dict]:
        """
        Парсинг карточного макета Dieta (много колонок, мало строк).
        Каждая колонка = один продукт, строки = атрибуты (название, стиль, ABV).
        
        Args:
            table: Таблица как список строк
            page_num: Номер страницы
            table_num: Номер таблицы на странице
            default_brewery: Название пивоварни по умолчанию
            original_brewery_name: Оригинальное название пивоварни
            
        Returns:
            Список словарей с данными позиций
        """
        items = []
        
        if not table or len(table) < 2:
            return items
        
        logger.debug(f"Парсинг карточного макета Dieta: {len(table)} строк, {len(table[0]) if table else 0} колонок")
        
        # Определяем индексы строк с данными
        # Обычно: строка 0 = названия, строка 1 = стили, строка 2 = ABV
        # Последняя колонка может содержать заголовки
        
        names_row = None
        styles_row = None
        abv_row = None
        
        # Ищем строки с названиями, стилями и ABV
        for row_idx, row in enumerate(table):
            if not row:
                continue
            
            # Проверяем, содержит ли строка заголовки в последней колонке
            last_col = str(row[-1]).strip().lower() if row and len(row) > 0 and row[-1] else ''
            if last_col in ['название', 'наименование', 'name']:
                names_row = row_idx
            elif last_col in ['стиль', 'style', 'с/п/пь']:
                styles_row = row_idx
            elif last_col in ['ттх', 'ttx', 'abv', 'ттx']:
                abv_row = row_idx
        
        # Если не нашли заголовки, пробуем определить по содержимому
        if names_row is None:
            # Ищем строку с названиями продуктов (обычно содержит "DIETA" и длинные названия)
            for row_idx, row in enumerate(table):
                if not row:
                    continue
                # Проверяем несколько первых колонок
                for col_idx in range(min(5, len(row))):
                    cell = str(row[col_idx]).strip() if row[col_idx] else ''
                    if cell and ('DIETA' in cell.upper() or len(cell) > 15):
                        names_row = row_idx
                        break
                if names_row is not None:
                    break
        
        if styles_row is None:
            # Ищем строку со стилями (обычно содержит слова типа Porter, Ale, IPA, Gose)
            for row_idx, row in enumerate(table):
                if not row or row_idx == names_row:
                    continue
                for col_idx in range(min(5, len(row))):
                    cell = str(row[col_idx]).strip().lower() if row[col_idx] else ''
                    if cell and any(word in cell for word in ['porter', 'ale', 'ipa', 'gose', 'stout', 'pilsner', 'sour']):
                        styles_row = row_idx
                        break
                if styles_row is not None:
                    break
        
        if abv_row is None:
            # Ищем строку с ABV (обычно содержит "%ABV" или просто "%")
            for row_idx, row in enumerate(table):
                if not row or row_idx == names_row or row_idx == styles_row:
                    continue
                for col_idx in range(min(5, len(row))):
                    cell = str(row[col_idx]).strip() if row[col_idx] else ''
                    if cell and ('%' in cell or 'abv' in cell.lower()):
                        abv_row = row_idx
                        break
                if abv_row is not None:
                    break
        
        logger.debug(f"Найдены строки: names_row={names_row}, styles_row={styles_row}, abv_row={abv_row}")
        
        # Если не нашли строки, пробуем по позициям (обычно 0, 1, 2)
        if names_row is None:
            names_row = 0
        if styles_row is None and names_row == 0:
            styles_row = 1
        if abv_row is None and names_row == 0 and styles_row == 1:
            abv_row = 2
        
        # Парсим каждую колонку как отдельный продукт
        # Игнорируем последнюю колонку, если она содержит заголовки
        num_cols = len(table[0]) if table else 0
        
        # Список служебных слов, которые НЕ должны быть названиями пива
        invalid_beer_names = [
            'imperial stout', 'imperial stout untappd', '11%abv', '4.5%abv',
            '230р/ банка', 'банка 0.33л', 'коробка 20шт', '4600р',
            'дата розлива', '21.07.25', 'в наличии', 'наличии',
            'traditional gose', 'традиционный гозе untappd',
            'десерт в твоем', 'твоем бокале', 'бокале'
        ]
        
        for col_idx in range(num_cols):
            # Проверяем последнюю колонку - если она содержит заголовки, пропускаем
            if col_idx == num_cols - 1:
                last_col_header = str(table[names_row][col_idx] if names_row < len(table) and col_idx < len(table[names_row]) else '').strip().lower()
                if last_col_header in ['название', 'наименование', 'name', 'стиль', 'style', 'ттх', 'ttx']:
                    continue
            
            item = {}
            
            # Извлекаем название из строки names_row
            if names_row is not None and names_row < len(table) and col_idx < len(table[names_row]):
                name_cell = str(table[names_row][col_idx]).strip() if table[names_row][col_idx] else ''
                if name_cell and name_cell.lower() not in ['none', 'nan', '']:
                    # Очищаем от префиксов "(NEW)" и объединяем многострочные названия
                    name_cell = re.sub(r'^\(NEW\)\s*', '', name_cell, flags=re.IGNORECASE).strip()
                    # Объединяем многострочные названия (заменяем переносы строк на пробелы)
                    name_cell = ' '.join(name_cell.split())
                    
                    # Пропускаем служебные строки
                    name_lower = name_cell.lower().strip()
                    
                    # Расширенный список служебных слов и фраз, которые НЕ должны быть названиями
                    invalid_patterns = [
                        'imperial stout', 'imperial stout untappd', '11%abv', '4.5%abv', '%abv',
                        '230р/ банка', 'банка 0.33л', 'коробка 20шт', '4600р', '3800р', '4200р',
                        'дата розлива', 'розлива:', '21.07.25', '10.07.25', 'в наличии', 'наличии',
                        'traditional gose', 'традиционный гозе untappd', 'traditional gose untappd',
                        'десерт в твоем', 'твоем бокале', 'бокале', 'в твоем',
                        'untappd', 'untapped'
                    ]
                    
                    # Проверяем, что название не является служебным словом или фрагментом
                    is_invalid = False
                    for pattern in invalid_patterns:
                        if pattern in name_lower:
                            is_invalid = True
                            break
                    
                    # Проверяем, что название - не только ABV
                    if re.search(r'^\d+\.?\d*\s*%abv\s*$', name_lower) or re.search(r'^\d+\.?\d*\s*%\s*$', name_lower):
                        is_invalid = True
                    
                    # Проверяем, что название - не только цена
                    if re.search(r'^\d+\.?\d*\s*[рруб₽]\s*$', name_lower):
                        is_invalid = True
                    
                    # Проверяем, что название - не цена с описанием (например, "230р/ банка 0.33л коробка 20шт – 4600р")
                    if re.search(r'\d+\s*[рруб₽]\s*/\s*', name_lower) or re.search(r'\d+\s*[рруб₽]\s+[а-я]+\s+\d+', name_lower):
                        is_invalid = True
                    
                    # Проверяем, что название - не дата
                    if re.search(r'\d+\.\d+\.\d+', name_lower):
                        is_invalid = True
                    
                    # Проверяем минимальную длину и наличие букв
                    if (not is_invalid and 
                        name_lower not in ['название', 'наименование', 'name'] and 
                        len(name_cell) > 3 and
                        not any(skip in name_lower for skip in ['ttx', 'ттх', 'ттx']) and
                        # Должно содержать буквы (не только цифры)
                        re.search(r'[a-zа-яё]', name_cell, re.IGNORECASE)):
                        item['beer_name'] = name_cell
                        # Извлекаем название пивоварни из названия (например, "DIETA X LIBRA Костёр")
                        if original_brewery_name and original_brewery_name.upper() in name_cell.upper():
                            item['brewery'] = default_brewery or original_brewery_name
            
            # Извлекаем стиль из строки styles_row
            if styles_row is not None and styles_row < len(table) and col_idx < len(table[styles_row]):
                style_cell = str(table[styles_row][col_idx]).strip() if table[styles_row][col_idx] else ''
                if style_cell and style_cell.lower() not in ['none', 'nan', '', 'стиль', 'style', 'с/п/пь']:
                    # Объединяем многострочные стили (заменяем переносы строк на пробелы)
                    style_cell = ' '.join(style_cell.split())
                    # Пропускаем, если это ABV или цена
                    style_lower = style_cell.lower()
                    if (not re.search(r'^\d+\.?\d*\s*%\s*$', style_lower) and  # Не только ABV
                        not re.search(r'^\d+\.?\d*\s*[рруб₽]', style_lower) and  # Не цена
                        style_lower not in ['ттх', 'ttx', 'ттx']):  # Не заголовок
                        item['style'] = style_cell
            
            # Извлекаем ABV из строки abv_row
            if abv_row is not None and abv_row < len(table) and col_idx < len(table[abv_row]):
                abv_cell = str(table[abv_row][col_idx]).strip() if table[abv_row][col_idx] else ''
                if abv_cell and abv_cell.lower() not in ['none', 'nan', '', 'ттх', 'ttx']:
                    # Извлекаем число из строки типа "8.5%ABV"
                    abv_match = re.search(r'(\d+\.?\d*)\s*%', abv_cell, re.IGNORECASE)
                    if abv_match:
                        item['abv'] = abv_match.group(1)
            
            # Если есть название - сохраняем позицию
            if item.get('beer_name'):
                if not item.get('brewery') and default_brewery:
                    item['brewery'] = default_brewery
                item['raw_source_location'] = {
                    'page': page_num,
                    'table': table_num,
                    'column': col_idx,
                    'layout': 'dieta_card'
                }
                items.append(item)
                logger.debug(f"Извлечен продукт из колонки {col_idx}: beer_name={item.get('beer_name')}, style={item.get('style')}, abv={item.get('abv')}")
        
        return items
    
    def extract_tables(self) -> List[List[List]]:
        """
        Извлечение таблиц из PDF.
        
        Returns:
            Список таблиц
        """
        tables = []
        try:
            with pdfplumber.open(self.file_path) as pdf:
                for page in pdf.pages:
                    page_tables = page.extract_tables()
                    tables.extend(page_tables)
        except Exception:
            pass
        return tables
    
    def extract_text(self) -> str:
        """
        Извлечение всего текста из PDF.
        
        Returns:
            Текст файла
        """
        text = ""
        try:
            with pdfplumber.open(self.file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception:
            pass
        return text
