"""
Парсер для Excel файлов.
"""

import pandas as pd
import re
import logging
from typing import List, Dict, Optional
from .base_parser import BaseParser
from .supplier_profiles import (
    SupplierProfileDetector, SupplierType,
    DistributorProfile, BreweryProfile
)

logger = logging.getLogger(__name__)


class ExcelParser(BaseParser):
    """
    Парсер для Excel файлов (.xls, .xlsx).
    
    Использует pandas для чтения и парсинга данных.
    Обрабатывает несколько листов в файле.
    """
    
    def parse(self) -> List[Dict]:
        """
        Парсинг Excel файла.
        
        Returns:
            Список словарей с данными о позициях
        """
        items = []
        
        try:
            # Пробуем прочитать все листы
            excel_file = pd.ExcelFile(self.file_path)
            logger.info(f"Открыт файл Excel: {self.file_path}, листов: {len(excel_file.sheet_names)}")
            
            for sheet_name in excel_file.sheet_names:
                try:
                    logger.info(f"Обработка листа: {sheet_name}")
                    # Пробуем несколько стратегий чтения
                    parsed_items = self._parse_sheet(excel_file, sheet_name)
                    if parsed_items:
                        items.extend(parsed_items)
                        logger.info(f"Извлечено {len(parsed_items)} позиций из листа {sheet_name}")
                    else:
                        logger.warning(f"Не удалось извлечь позиции из листа {sheet_name}")
                except Exception as e:
                    logger.error(f"Ошибка при обработке листа {sheet_name}: {str(e)}", exc_info=True)
                    continue
        except Exception as e:
            logger.error(f"Ошибка при чтении Excel файла {self.file_path}: {str(e)}", exc_info=True)
            # Если не удалось прочитать как Excel, пробуем как CSV
            try:
                logger.info("Пробуем прочитать как CSV")
                df = pd.read_csv(self.file_path)
                parsed_items = self._parse_dataframe(df, 'Sheet1')
                items.extend(parsed_items)
            except Exception as csv_error:
                logger.error(f"Ошибка при чтении как CSV: {str(csv_error)}")
        
        return items
    
    def _parse_sheet(self, excel_file: pd.ExcelFile, sheet_name: str) -> List[Dict]:
        """
        Парсит один лист Excel файла, пробуя разные стратегии.
        
        Args:
            excel_file: Объект ExcelFile
            sheet_name: Имя листа
            
        Returns:
            Список словарей с данными позиций
        """
        # Сначала определяем тип поставщика
        detector = SupplierProfileDetector()
        
        # Стратегия 1: Ищем строку заголовков в первых 20 строках
        try:
            df_sample = pd.read_excel(excel_file, sheet_name=sheet_name, header=None, nrows=20)
            header_row = self._find_header_row(df_sample)
            
            if header_row is not None:
                logger.debug(f"Найдена строка заголовков на строке {header_row + 1}")
                df = pd.read_excel(excel_file, sheet_name=sheet_name, header=header_row)
                
                # Определяем тип поставщика
                try:
                    supplier_type, characteristics = detector.detect(df, sheet_name)
                    logger.info(f"Лист {sheet_name}: тип поставщика = {supplier_type.value}")
                except Exception as e:
                    logger.warning(f"Ошибка при определении типа поставщика: {str(e)}", exc_info=True)
                    supplier_type = SupplierType.UNKNOWN
                    characteristics = {}
                
                return self._parse_dataframe(df, sheet_name, supplier_type=supplier_type, 
                                           characteristics=characteristics)
        except Exception as e:
            logger.debug(f"Стратегия 1 не сработала: {str(e)}")
        
        # Стратегия 2: Пробуем header=1 (вторая строка)
        try:
            df = pd.read_excel(excel_file, sheet_name=sheet_name, header=1)
            
            # Определяем тип поставщика
            try:
                supplier_type, characteristics = detector.detect(df, sheet_name)
                logger.info(f"Лист {sheet_name}: тип поставщика = {supplier_type.value}")
            except Exception as e:
                logger.warning(f"Ошибка при определении типа поставщика: {str(e)}", exc_info=True)
                supplier_type = SupplierType.UNKNOWN
                characteristics = {}
            
            parsed_items = self._parse_dataframe(df, sheet_name, supplier_type=supplier_type,
                                                characteristics=characteristics, file_brewery=file_brewery)
            if parsed_items:
                logger.debug("Стратегия 2 (header=1) успешна")
                return parsed_items
        except Exception as e:
            logger.debug(f"Стратегия 2 не сработала: {str(e)}")
        
        # Стратегия 3: Пробуем header=0 (первая строка)
        try:
            df = pd.read_excel(excel_file, sheet_name=sheet_name, header=0)
            
            # Определяем тип поставщика
            try:
                supplier_type, characteristics = detector.detect(df, sheet_name)
                logger.info(f"Лист {sheet_name}: тип поставщика = {supplier_type.value}")
            except Exception as e:
                logger.warning(f"Ошибка при определении типа поставщика: {str(e)}", exc_info=True)
                supplier_type = SupplierType.UNKNOWN
                characteristics = {}
            
            parsed_items = self._parse_dataframe(df, sheet_name, supplier_type=supplier_type,
                                                characteristics=characteristics, file_brewery=file_brewery)
            if parsed_items:
                logger.debug("Стратегия 3 (header=0) успешна")
                return parsed_items
        except Exception as e:
            logger.debug(f"Стратегия 3 не сработала: {str(e)}")
        
        # Стратегия 4: Читаем без заголовков и ищем их в данных
        try:
            df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
            header_row = self._find_header_row(df)
            if header_row is not None:
                col_mapping = self._map_columns(df.iloc[header_row].tolist(), df)
                if col_mapping:
                    df_data = df.iloc[header_row + 1:].reset_index(drop=True)
                    
                    # Определяем тип поставщика
                    try:
                        supplier_type, characteristics = detector.detect(df_data, sheet_name)
                        logger.info(f"Лист {sheet_name}: тип поставщика = {supplier_type.value}")
                    except Exception as e:
                        logger.warning(f"Ошибка при определении типа поставщика: {str(e)}", exc_info=True)
                        supplier_type = SupplierType.UNKNOWN
                        characteristics = {}
                    
                    return self._parse_dataframe(df_data, sheet_name, col_mapping=col_mapping, 
                                                supplier_type=supplier_type,
                                                characteristics=characteristics)
        except Exception as e:
            logger.debug(f"Стратегия 4 не сработала: {str(e)}")
        
        return []
    
    def _parse_dataframe(self, df: pd.DataFrame, sheet_name: str, 
                        col_mapping: Optional[Dict[str, int]] = None,
                        supplier_type: SupplierType = SupplierType.UNKNOWN,
                        characteristics: Dict = None) -> List[Dict]:
        """
        Парсинг DataFrame из Excel.
        
        Args:
            df: DataFrame с данными
            sheet_name: Имя листа
            col_mapping: Предопределенный маппинг колонок (опционально)
            
        Returns:
            Список словарей с данными позиций
        """
        items = []
        
        if df.empty:
            logger.debug(f"DataFrame пуст для листа {sheet_name}")
            return items
        
        # Определяем тип поставщика, если не передан
        if supplier_type is None:
            try:
                detector = SupplierProfileDetector()
                supplier_type, characteristics = detector.detect(df, sheet_name)
                logger.info(f"Автоопределение типа поставщика: {supplier_type.value}")
            except Exception as e:
                logger.warning(f"Ошибка при автоопределении типа поставщика: {str(e)}", exc_info=True)
                supplier_type = SupplierType.UNKNOWN
                characteristics = {}
        
        # Убеждаемся, что supplier_type не None
        if supplier_type is None:
            supplier_type = SupplierType.UNKNOWN
        
        if characteristics is None:
            characteristics = {}
        
        # Если маппинг не передан, определяем его с учетом типа поставщика
        if col_mapping is None:
            col_mapping = {}
            # Применяем профиль поставщика
            if supplier_type:
                try:
                    if supplier_type == SupplierType.DISTRIBUTOR:
                        profile = DistributorProfile()
                        profile_mapping = profile.get_column_mapping_strategy(df, characteristics)
                        col_mapping.update(profile_mapping)
                        logger.debug(f"Применен профиль дистрибьютора, начальный маппинг: {col_mapping}")
                    elif supplier_type == SupplierType.BREWERY:
                        brewery_name = characteristics.get('single_brewery_name')
                        profile = BreweryProfile(brewery_name)
                        profile_mapping = profile.get_column_mapping_strategy(df, characteristics)
                        col_mapping.update(profile_mapping)
                        logger.debug(f"Применен профиль пивоварни ({brewery_name}), начальный маппинг: {col_mapping}")
                except Exception as e:
                    logger.warning(f"Ошибка при применении профиля поставщика: {str(e)}", exc_info=True)
            
            # Проверяем, есть ли названия колонок (если читали с header=None, колонки будут 0, 1, 2...)
            has_named_columns = not all(isinstance(col, (int, float)) for col in df.columns)
            
            if has_named_columns:
                # Если колонки именованные, пробуем определить маппинг по названиям
                mapping_by_names = self._map_columns(df.columns.tolist(), df)
                # Объединяем с профилем (профиль имеет приоритет)
                col_mapping = {**mapping_by_names, **col_mapping}
                logger.debug(f"Маппинг по названиям колонок: {mapping_by_names}, объединенный: {col_mapping}")
            
            # Если не нашли маппинг по названиям колонок, ищем заголовки в данных
            if not col_mapping:
                header_row = self._find_header_row(df)
                if header_row is not None:
                    mapping_by_header = self._map_columns(
                        df.iloc[header_row].tolist(), df
                    )
                    col_mapping = {**mapping_by_header, **col_mapping}
                    df = df.iloc[header_row + 1:].reset_index(drop=True)
                    logger.debug(f"Найден заголовок в строке {header_row}, маппинг: {mapping_by_header}")
        
        # Если маппинг все еще не найден, используем эвристику по позициям колонок
        if not col_mapping:
            col_mapping = self._guess_column_mapping(df)
            logger.debug(f"Маппинг по эвристике: {col_mapping}")
        
        # Если все еще нет маппинга, пробуем определить по содержимому первых строк
        if not col_mapping:
            col_mapping = self._analyze_data_content(df)
            logger.debug(f"Маппинг по анализу содержимого: {col_mapping}")
        
        # Если маппинг определен частично, но не все ключевые поля найдены,
        # запускаем агрессивный анализ содержимого всех колонок
        essential_fields = ['beer_name', 'price']
        missing_fields = [f for f in essential_fields if f not in col_mapping]
        
        if missing_fields and not df.empty:
            logger.debug(f"Не найдены поля: {missing_fields}, запускаем анализ содержимого")
            col_mapping = self._aggressive_column_mapping(df, col_mapping)
            logger.debug(f"Маппинг после агрессивного анализа: {col_mapping}")
        
        if not col_mapping:
            logger.warning(f"Не удалось определить маппинг колонок для листа {sheet_name}")
            return items
        
        logger.debug(f"Используется маппинг: {col_mapping}")
        
        # Парсим строки данных
        # Сохраняем последнюю заполненную пивоварню для заполнения пустых значений
        last_brewery = None
        
        # Определяем, является ли лист розливным (кеги)
        is_draft_sheet = ('розлив' in sheet_name.lower() or 
                         'draft' in sheet_name.lower() or 
                         'кeg' in sheet_name.lower() or
                         'keg' in sheet_name.lower())
        
        # Для пивоварни получаем название по умолчанию
        default_brewery = None
        if supplier_type == SupplierType.BREWERY:
            try:
                brewery_name = characteristics.get('single_brewery_name')
                if brewery_name:
                    profile = BreweryProfile(brewery_name)
                    default_brewery = profile.get_default_brewery_name()
                    logger.debug(f"Установлена пивоварня по умолчанию: {default_brewery}")
            except Exception as e:
                logger.warning(f"Ошибка при установке пивоварни по умолчанию: {str(e)}", exc_info=True)
        
        for idx, row in df.iterrows():
            try:
                item = self._extract_row_data(row, col_mapping)
                if item:
                    # Обработка пивоварни в зависимости от типа поставщика
                    if supplier_type == SupplierType.BREWERY:
                        # Для пивоварни устанавливаем название по умолчанию, если не найдено
                        if not item.get('brewery') and default_brewery:
                            item['brewery'] = default_brewery
                    else:
                        # Для дистрибьютора используем логику с предыдущей пивоварней
                        if not item.get('brewery') and last_brewery:
                            item['brewery'] = last_brewery
                        # Сохраняем текущую пивоварню, если она заполнена
                        elif item.get('brewery'):
                            last_brewery = item['brewery']
                    
                    # Для розливных листов автоматически устанавливаем формат "кега"
                    if is_draft_sheet and not item.get('format_type'):
                        item['format_type'] = 'кега'
                    
                    item['raw_source_location'] = {
                        'sheet': sheet_name,
                        'row': int(idx) + 1
                    }
                    items.append(item)
            except Exception as e:
                logger.debug(f"Ошибка при обработке строки {idx}: {str(e)}")
                continue
        
        return items
    
    def _find_header_row(self, df: pd.DataFrame) -> Optional[int]:
        """
        Ищет строку с заголовками в DataFrame.
        
        Args:
            df: DataFrame для поиска
            
        Returns:
            Индекс строки с заголовками или None
        """
        # Расширенный список паттернов для заголовков
        header_patterns = [
            # Пивоварня
            'пивоварня', 'производитель', 'brewery', 'manufacturer',
            'производитель', 'бренд', 'brand', 'марка',
            # Название пива
            'название', 'пиво', 'beer', 'name', 'наименование',
            'товар', 'продукт', 'product', 'наименование товара',
            # Цена
            'цена', 'price', 'стоимость', 'cost', 'руб', 'рублей',
            'цена за', 'цена/шт', 'цена за шт',
            # Стиль
            'стиль', 'style', 'тип', 'type', 'категория', 'category',
            # Характеристики
            'abv', 'крепость', 'алкоголь', 'alcohol', '%', 'объем',
            'ibu', 'горечь', 'bitterness', 'og', 'fg',
            # Описание
            'описание', 'description', 'опис', 'desc', 'комментарий',
            # Фасовка
            'фасовки', 'фасовка', 'формат', 'format', 'упаковка', 
            'packaging', 'тара', 'тип фасовки', 'объем упаковки',
            # Остальное
            'остаток', 'stock', 'наличие', 'availability', 'кол-во',
            'количество', 'quantity', 'заказ'
        ]
        
        best_match = None
        best_score = 0
        
        # Ограничиваем поиск до 10 строк для скорости
        for idx in range(min(10, len(df))):
            try:
                row_values = [str(val).lower().strip() if pd.notna(val) else '' 
                             for val in df.iloc[idx].tolist()[:20]]  # Только первые 20 колонок
                
                # Считаем количество совпадений с паттернами (оптимизировано)
                matches = 0
                matched_patterns = set()
                # Проверяем только первые 10 паттернов для скорости
                for pattern in header_patterns[:10]:
                    for val in row_values:
                        if pattern in val and len(val) > 2:
                            if pattern not in matched_patterns:
                                matches += 1
                                matched_patterns.add(pattern)
                                break
                
                # Также проверяем, что в строке нет слишком много пустых значений
                non_empty = sum(1 for v in row_values if v and len(v) > 2)
                
                # Специальные проверки для точного определения заголовков
                has_brewery_header = any(
                    'наименование пивоварни' in v or 
                    ('наименование' in v and 'пивоварни' in v) or
                    'пивоварня' in v or 'brewery' in v
                    for v in row_values
                )
                has_product_header = any(
                    ('наименование' in v and 'пивоварни' not in v) or
                    'название' in v or 'beer' in v or 'name' in v
                    for v in row_values
                )
                has_price_header = any(
                    'цена' in v or 'price' in v or 'стоимость' in v or 'руб' in v
                    for v in row_values
                )
                
                # Если найдены все три ключевых заголовка - это точно заголовки
                if has_brewery_header and has_product_header and has_price_header:
                    logger.debug(f"Найдена строка заголовков (точное совпадение) на строке {idx + 1}")
                    return idx
                
                # Проверяем комбинации из двух ключевых заголовков
                if (has_brewery_header and has_price_header) or \
                   (has_product_header and has_price_header):
                    score = matches * 3 + (non_empty if non_empty < 20 else 0)
                    if score > best_score:
                        best_score = score
                        best_match = idx
                
                # Считаем общий скор: количество совпадений + количество непустых значений
                score = matches * 2 + (non_empty if non_empty < 20 else 0)
                
                if score > best_score and matches >= 2:
                    best_score = score
                    best_match = idx
            except Exception as e:
                logger.debug(f"Ошибка при проверке строки {idx}: {str(e)}")
                continue
        
        if best_match is not None:
            logger.debug(f"Найдена строка заголовков (лучшее совпадение) на строке {best_match + 1}, скор: {best_score}")
        
        return best_match
    
    def _map_columns(self, headers: List[str], df: pd.DataFrame = None) -> Dict[str, int]:
        """
        Определяет соответствие колонок заголовкам.
        
        Args:
            headers: Список заголовков колонок
            
        Returns:
            Словарь {название_поля: индекс_колонки}
        """
        mapping = {}
        
        # Расширенные варианты названий для каждого поля
        field_patterns = {
            'brewery': [
                'пивоварня', 'производитель', 'brewery', 'manufacturer', 
                'brand', 'бренд', 'марка', 'производитель пива',
                'наименование пивоварни', 'пивоварня/производитель'
            ],
            'beer_name': [
                'название', 'пиво', 'beer', 'name', 'наименование', 
                'товар', 'продукт', 'product', 'наименование товара',
                'название пива', 'наименование пива', 'название товара'
            ],
            'style': [
                'стиль', 'style', 'тип', 'type', 'категория', 'category',
                'сорт', 'вид', 'класс'
            ],
            'abv': [
                'abv', 'крепость', 'алкоголь', 'alcohol', '%', 
                'объем алкоголя', 'алк.объем', 'abv%'
            ],
            'ibu': [
                'ibu', 'горечь', 'bitterness', 'горькость'
            ],
            'price': [
                'цена', 'price', 'стоимость', 'cost', 'руб', 'рублей',
                'цена за', 'цена/шт', 'цена за шт', 'цена за единицу',
                'цена руб', 'цена (руб)', 'стоимость руб'
            ],
            'currency': [
                'валюта', 'currency', 'вал'
            ],
            'volume': [
                'объём', 'volume', 'литр', 'литров', 'л', 'ml', 'мл', 
                'литраж', 'объем', 'объем упаковки', 'объем тары',
                'объем (л)', 'литраж (л)'
            ],
            'format_type': [
                'формат', 'format', 'упаковка', 'packaging', 'тара', 
                'фасовки', 'тип фасовки', 'фасовка', 'тип упаковки',
                'формат упаковки', 'тип тары', 'упаковка/формат'
            ],
            'stock': [
                'остаток', 'stock', 'наличие', 'availability', 
                'в наличии', 'количество на складе', 'склад'
            ],
            'supplier_name': [
                'поставщик', 'supplier', 'компания', 'компания-поставщик'
            ],
            'description': [
                'описание', 'description', 'опис', 'desc', 
                'комментарий', 'comment', 'примечание'
            ],
        }
        
        headers_lower = [str(h).lower().strip() if h else '' 
                        for h in headers]
        
        # Специальная обработка для русских заголовков
        for idx, header in enumerate(headers_lower):
            if header:
                # "Наименование пивоварни" = brewery
                if 'наименование пивоварни' in header or ('наименование' in header and 'пивоварни' in header):
                    if 'brewery' not in mapping:
                        mapping['brewery'] = idx
                        continue
                # "Наименование" (без пивоварни) = beer_name
                elif 'наименование' in header and 'пивоварни' not in header:
                    if 'beer_name' not in mapping:
                        mapping['beer_name'] = idx
                        continue
                # Пивоварня - общие паттерны
                elif any(p in header for p in ['пивоварня', 'brewery', 'производитель', 'manufacturer', 'бренд', 'brand']):
                    if 'brewery' not in mapping:
                        mapping['brewery'] = idx
                        continue
                # Название пива
                elif any(p in header for p in ['название', 'beer', 'name']):
                    if 'beer_name' not in mapping:
                        mapping['beer_name'] = idx
                        continue
                # Тип фасовки / формат (может содержать формат и объем) - приоритетная обработка
                if 'тип фасовки' in header or ('фасовки' in header and 'кол-во' in header):
                    if 'format_type' not in mapping:
                        mapping['format_type'] = idx
                        continue
                # Объем / литраж - приоритетная обработка перед стилем
                # Проверяем явно "литраж" первой
                if 'литраж' in header:
                    if 'volume' not in mapping:
                        mapping['volume'] = idx
                        continue
                # Проверяем другие паттерны для объема, но только если это не "Стиль"
                if any(p in header for p in ['объём', 'volume', 'литр', 'литров']) and 'стиль' not in header:
                    if 'volume' not in mapping:
                        mapping['volume'] = idx
                        continue
                # Цена
                if any(p in header for p in ['цена', 'price', 'стоимость', 'cost']):
                    if 'price' not in mapping:
                        mapping['price'] = idx
                        continue
                # Стиль - только если это не литраж
                if ('стиль' in header or 'style' in header) and 'литраж' not in header:
                    if 'style' not in mapping:
                        mapping['style'] = idx
                        continue
                # Описание
                if 'описание' in header or 'description' in header:
                    if 'description' not in mapping:
                        mapping['description'] = idx
                        continue
                # ABV / IBU (может быть в одной колонке типа "ABV / OG / IBU")
                if 'abv' in header or 'крепость' in header:
                    if 'abv' not in mapping:
                        mapping['abv'] = idx
                if 'ibu' in header or 'горечь' in header:
                    if 'ibu' not in mapping:
                        mapping['ibu'] = idx
                        continue
        
        # Если передан DataFrame, анализируем содержимое колонок для более точного определения
        if df is not None and not df.empty:
            sample_rows = df.head(min(10, len(df)))
            
            # Анализируем каждую колонку по содержимому
            for idx, header in enumerate(headers_lower):
                if idx >= len(df.columns):
                    continue
                
                try:
                    col_data = sample_rows.iloc[:, idx].dropna().astype(str).tolist()
                    if not col_data:
                        continue
                    
                    # Анализируем содержимое колонки
                    col_analysis = self._analyze_column_content(col_data, idx)
                    
                    # Применяем результаты анализа, если поле еще не определено
                    for field_name, should_map in col_analysis.items():
                        if should_map and field_name not in mapping:
                            mapping[field_name] = idx
                            logger.debug(f"Определено поле {field_name} по содержимому колонки {idx}")
                            break
                except Exception as e:
                    logger.debug(f"Ошибка при анализе колонки {idx}: {str(e)}")
                    continue
        
        # Затем ищем по общим паттернам для остальных полей
        for field, patterns in field_patterns.items():
            if field not in mapping:  # Пропускаем уже найденные поля
                for idx, header in enumerate(headers_lower):
                    if header and any(pattern in header for pattern in patterns):
                        # Для volume пропускаем, если это "Стиль" или другие не-объемные колонки
                        if field == 'volume':
                            # Не маппим volume к колонкам со стилем
                            if 'стиль' in header or 'style' in header:
                                continue
                        mapping[field] = idx
                        break
        
        # Дополнительная проверка: если есть колонка с похожим названием
        # Например, "Название товара" или "Наименование"
        for idx, header in enumerate(headers_lower):
            if header:
                # Проверяем более широкие паттерны
                if ('назв' in header or 'наимен' in header or 'товар' in header) and 'beer_name' not in mapping:
                    # Но только если это не пивоварня
                    if 'пивоварни' not in header:
                        mapping['beer_name'] = idx
                elif ('произв' in header or 'бренд' in header or 'марка' in header) and 'brewery' not in mapping:
                    mapping['brewery'] = idx
                elif ('цена' in header or 'стоим' in header or 'руб' in header) and 'price' not in mapping:
                    mapping['price'] = idx
                elif ('фасов' in header or 'формат' in header or 'упаковка' in header) and 'format_type' not in mapping:
                    mapping['format_type'] = idx
        
        return mapping
    
    def _analyze_column_content(self, col_data: List[str], col_idx: int) -> Dict[str, bool]:
        """
        Анализирует содержимое колонки для определения её назначения.
        
        Args:
            col_data: Список значений из колонки (первые 10 строк)
            col_idx: Индекс колонки
            
        Returns:
            Словарь {название_поля: True/False} - должно ли это поле маппиться к этой колонке
        """
        analysis = {
            'brewery': False,
            'beer_name': False,
            'style': False,
            'abv': False,
            'ibu': False,
            'price': False,
            'volume': False,
            'format_type': False,
            'stock': False,
            'description': False,
        }
        
        if not col_data:
            return analysis
        
        # Анализируем первые несколько значений
        sample_values = col_data[:min(10, len(col_data))]
        
        # Проверяем на числа (цена, объем, ABV, IBU)
        numeric_count = 0
        numeric_values = []
        for val in sample_values:
            try:
                # Пробуем преобразовать в число
                num_val = float(str(val).replace(',', '.').replace(' ', ''))
                numeric_count += 1
                numeric_values.append(num_val)
            except (ValueError, TypeError):
                pass
        
        numeric_ratio = numeric_count / len(sample_values) if sample_values else 0
        
        # Если больше 70% чисел - это числовая колонка
        if numeric_ratio > 0.7:
            if numeric_values:
                avg_value = sum(numeric_values) / len(numeric_values)
                max_value = max(numeric_values)
                
                # Цена обычно в диапазоне 50-10000
                if 50 <= avg_value <= 10000 and max_value < 50000:
                    analysis['price'] = True
                # Объем обычно 0.1-50 литров
                elif 0.1 <= avg_value <= 50:
                    analysis['volume'] = True
                # ABV обычно 0-15%
                elif 0 <= avg_value <= 15:
                    analysis['abv'] = True
                # IBU обычно 0-120
                elif 0 <= avg_value <= 120:
                    analysis['ibu'] = True
        
        # Анализируем текстовое содержимое
        text_values = [str(v).strip() for v in sample_values if v and str(v).strip()]
        if text_values:
            # Проверяем длину текста
            avg_length = sum(len(v) for v in text_values) / len(text_values)
            
            # Название пива обычно длинное (более 15 символов)
            # Может содержать описание, но это все равно название позиции
            if avg_length > 15:
                # Проверяем признаки названия пива:
                # - содержит слова о пиве, стилях, вкусах
                # - обычно первая колонка с длинным текстом
                # - может начинаться с заглавной буквы (название бренда)
                beer_name_indicators = [
                    'ipa', 'lager', 'ale', 'stout', 'porter', 'pilsner', 'wheat', 'sour',
                    'пиво', 'beer', 'пивоварня', 'brewery', 'gose', 'neipa', 'hazy',
                    'томатный', 'клубничный', 'базилик', 'чеснок', 'перцы',  # Примеры из вашего файла
                    'безалкогольный', 'non-alcoholic', 'new england', 'grapefruit',
                    'alisperi', 'back to balance', 'berry forward', 'bitter joy'  # Примеры названий
                ]
                has_beer_keywords = any(
                    keyword in ' '.join(text_values).lower() 
                    for keyword in beer_name_indicators
                )
                
                # Если содержит ключевые слова о пиве - это название
                if has_beer_keywords:
                    analysis['beer_name'] = True
                # Если очень длинное (более 150 символов) и не содержит ключевых слов - это описание
                elif avg_length > 150:
                    # Но только если это не единственная длинная колонка
                    analysis['description'] = True
                # Иначе считаем названием (может содержать описание в названии)
                # Это более агрессивный подход - любая длинная текстовая колонка может быть названием
                else:
                    analysis['beer_name'] = True
            
            # Пивоварня обычно короткая (5-30 символов) и содержит названия компаний
            elif 5 <= avg_length <= 30:
                has_brewery_keywords = any(
                    keyword in ' '.join(text_values).lower()
                    for keyword in ['brewery', 'пивоварня', 'brewing', 'company', 'компания']
                )
                if has_brewery_keywords:
                    analysis['brewery'] = True
            
            # Стиль обычно короткий (3-50 символов) и содержит названия стилей
            if 3 <= avg_length <= 50:
                style_keywords = [
                    'ipa', 'lager', 'ale', 'stout', 'porter', 'pilsner', 'wheat', 'sour',
                    'gose', 'neipa', 'hazy', 'imperial', 'double', 'triple',
                    'стиль', 'style', 'томатный', 'tomato', 'georgian',
                    'new england', 'grapefruit', 'strawberry', 'sour ale'
                ]
                has_style_keywords = any(
                    keyword in ' '.join(text_values).lower()
                    for keyword in style_keywords
                )
                # Также проверяем, что это не название пива (название обычно длиннее)
                if has_style_keywords and avg_length < 50:
                    analysis['style'] = True
            
            # Формат обычно очень короткий (1-15 символов)
            if avg_length <= 15:
                format_keywords = [
                    'банка', 'can', 'кега', 'keg', 'кег', 'бутылка', 'bottle',
                    'ж/б', 'бут', 'л', 'ml', 'мл'
                ]
                has_format_keywords = any(
                    keyword in ' '.join(text_values).lower()
                    for keyword in format_keywords
                )
                if has_format_keywords:
                    analysis['format_type'] = True
            
            # Остатки обычно содержат слова типа "много", "мало", "достаточно"
            stock_keywords = [
                'много', 'мало', 'достаточно', 'нет', 'есть', 'в наличии',
                'many', 'few', 'enough', 'available', 'stock'
            ]
            has_stock_keywords = any(
                keyword in ' '.join(text_values).lower()
                for keyword in stock_keywords
            )
            if has_stock_keywords:
                analysis['stock'] = True
        
        return analysis
    
    def _aggressive_column_mapping(self, df: pd.DataFrame, 
                                   existing_mapping: Dict[str, int]) -> Dict[str, int]:
        """
        Агрессивно определяет маппинг колонок, анализируя содержимое всех колонок.
        
        Args:
            df: DataFrame с данными
            existing_mapping: Существующий маппинг (может быть частичным)
            
        Returns:
            Обновленный маппинг колонок
        """
        mapping = existing_mapping.copy() if existing_mapping else {}
        
        if df.empty:
            return mapping
        
        # Анализируем все колонки
        sample_rows = df.head(min(20, len(df)))
        used_indices = set(mapping.values())
        
        # Собираем анализ для всех колонок
        column_analyses = []
        for col_idx in range(len(df.columns)):
            if col_idx in used_indices:
                continue
            
            try:
                col_data = sample_rows.iloc[:, col_idx].dropna().astype(str).tolist()
                if not col_data:
                    continue
                
                analysis = self._analyze_column_content(col_data, col_idx)
                column_analyses.append((col_idx, analysis))
            except Exception as e:
                logger.debug(f"Ошибка при анализе колонки {col_idx}: {str(e)}")
                continue
        
        # Определяем приоритеты полей (важные поля первыми)
        field_priority = [
            'beer_name', 'price', 'style', 'abv', 'ibu', 
            'brewery', 'volume', 'format_type', 'stock', 'description'
        ]
        
        # Применяем анализ, учитывая приоритеты
        for field in field_priority:
            if field in mapping:
                continue
            
            # Ищем лучшую колонку для этого поля
            best_col = None
            best_score = 0
            
            for col_idx, analysis in column_analyses:
                if col_idx in used_indices:
                    continue
                
                if analysis.get(field, False):
                    # Оцениваем колонку
                    score = 1
                    # Дополнительные проверки для важных полей
                    if field == 'beer_name':
                        # Название пива должно быть длинным текстом
                        col_data = sample_rows.iloc[:, col_idx].dropna().astype(str).tolist()
                        if col_data:
                            avg_len = sum(len(v) for v in col_data[:5]) / min(5, len(col_data))
                            if avg_len > 20:
                                score = 2
                    elif field == 'price':
                        # Цена должна быть числом
                        col_data = sample_rows.iloc[:, col_idx].dropna()
                        numeric_count = sum(1 for v in col_data if isinstance(v, (int, float)) or 
                                           (isinstance(v, str) and v.replace(',', '.').replace(' ', '').replace('-', '').isdigit()))
                        if numeric_count > len(col_data) * 0.7:
                            score = 2
                    
                    if score > best_score:
                        best_score = score
                        best_col = col_idx
            
            if best_col is not None:
                mapping[field] = best_col
                used_indices.add(best_col)
                logger.debug(f"Агрессивно определено поле {field} -> колонка {best_col}")
        
        # Fallback: если beer_name все еще не найден, берем первую длинную текстовую колонку
        if 'beer_name' not in mapping:
            # Сначала пробуем первую колонку (обычно там название)
            if 0 not in used_indices:
                try:
                    col_data = sample_rows.iloc[:, 0].dropna().astype(str).tolist()
                    if col_data:
                        avg_len = sum(len(str(v)) for v in col_data[:5]) / min(5, len(col_data))
                        if avg_len > 10:  # Снижаем порог для первой колонки
                            mapping['beer_name'] = 0
                            logger.debug(f"Fallback: beer_name -> колонка 0 (первая колонка, средняя длина: {avg_len:.1f})")
                except Exception:
                    pass
            
            # Если первая колонка не подошла, ищем любую длинную текстовую колонку
            if 'beer_name' not in mapping:
                for col_idx in range(len(df.columns)):
                    if col_idx in used_indices:
                        continue
                    try:
                        col_data = sample_rows.iloc[:, col_idx].dropna().astype(str).tolist()
                        if col_data:
                            avg_len = sum(len(str(v)) for v in col_data[:5]) / min(5, len(col_data))
                            if avg_len > 15:
                                mapping['beer_name'] = col_idx
                                logger.debug(f"Fallback: beer_name -> колонка {col_idx} (средняя длина: {avg_len:.1f})")
                                break
                    except Exception:
                        continue
        
        # Fallback: если style не найден, ищем колонку с коротким текстом и ключевыми словами стилей
        if 'style' not in mapping:
            # Сначала пробуем вторую колонку (обычно там стиль, если первая - название)
            if 1 not in used_indices:
                try:
                    col_data = sample_rows.iloc[:, 1].dropna().astype(str).tolist()
                    if col_data:
                        avg_len = sum(len(str(v)) for v in col_data[:5]) / min(5, len(col_data))
                        if 3 <= avg_len <= 50:
                            text_lower = ' '.join(col_data[:5]).lower()
                            style_keywords = ['ipa', 'lager', 'ale', 'stout', 'gose', 'sour', 'style', 'стиль', 
                                            'tomato', 'georgian', 'new england', 'grapefruit', 'strawberry']
                            if any(kw in text_lower for kw in style_keywords):
                                mapping['style'] = 1
                                logger.debug(f"Fallback: style -> колонка 1 (вторая колонка)")
                except Exception:
                    pass
            
            # Если вторая колонка не подошла, ищем любую подходящую
            if 'style' not in mapping:
                for col_idx in range(len(df.columns)):
                    if col_idx in used_indices:
                        continue
                    try:
                        col_data = sample_rows.iloc[:, col_idx].dropna().astype(str).tolist()
                        if col_data:
                            avg_len = sum(len(str(v)) for v in col_data[:5]) / min(5, len(col_data))
                            if 3 <= avg_len <= 50:
                                text_lower = ' '.join(col_data[:5]).lower()
                                style_keywords = ['ipa', 'lager', 'ale', 'stout', 'gose', 'sour', 'style', 'стиль',
                                                'tomato', 'georgian', 'new england', 'grapefruit', 'strawberry']
                                if any(kw in text_lower for kw in style_keywords):
                                    mapping['style'] = col_idx
                                    logger.debug(f"Fallback: style -> колонка {col_idx}")
                                    break
                    except Exception:
                        continue
        
        return mapping
    
    def _extract_brewery_from_name(self, beer_name: str) -> Optional[str]:
        """
        Извлекает название пивоварни из начала названия пива.
        
        Примеры:
        - "ALISPERI (Fresh Brewed) Томатный гозе..." -> "ALISPERI"
        - "BACK TO BALANCE (Fresh Brewed) Безалкогольный..." -> "BACK TO BALANCE"
        - "PARADOX BERRY FORWARD..." -> "PARADOX"
        - "Бокал "Paradox", 400 ml" -> "Paradox"
        - "Кружка "Paradox", 500 ml" -> "Paradox"
        
        Args:
            beer_name: Полное название пива
            
        Returns:
            Название пивоварни или None
        """
        if not beer_name or len(beer_name) < 3:
            return None
        
        # Убираем лишние пробелы
        beer_name = beer_name.strip()
        
        # Паттерны для извлечения пивоварни:
        # 1. Пивоварня в кавычках (например, "Paradox" в "Бокал "Paradox", 400 ml")
        # 2. Слово в верхнем регистре до скобки: "ALISPERI (Fresh Brewed)"
        # 3. Несколько слов в верхнем регистре: "BACK TO BALANCE"
        # 4. Одно слово в верхнем регистре в начале
        
        # Паттерн 1: Пивоварня в кавычках (обычно после слов типа "Бокал", "Кружка", "Стакан")
        # Ищем текст в кавычках (как обычных, так и типографских)
        quote_patterns = [
            r'[""]([A-ZА-ЯЁ][A-ZА-ЯЁa-zа-яё\s]{1,30}?)[""]',  # "Paradox" или "Paradox"
            r'[«»]([A-ZА-ЯЁ][A-ZА-ЯЁa-zа-яё\s]{1,30}?)[«»]',  # «Paradox»
        ]
        for pattern in quote_patterns:
            matches = re.findall(pattern, beer_name)
            if matches:
                brewery = matches[0].strip()
                # Проверяем, что это не слишком длинное и не обычное слово
                if 2 <= len(brewery) <= 30:
                    common_words = ['ipa', 'ale', 'lager', 'stout', 'porter', 'pilsner', 'wheat', 'sour', 'ml', 'л']
                    if brewery.upper() not in [w.upper() for w in common_words]:
                        logger.debug(f"Извлечена пивоварня из кавычек: {brewery} из '{beer_name}'")
                        return brewery
        
        # Паттерн 2: До скобки
        match = re.match(r'^([A-ZА-ЯЁ][A-ZА-ЯЁ\s]+?)\s*\(', beer_name)
        if match:
            brewery = match.group(1).strip()
            # Проверяем, что это не слишком длинное (больше 50 символов - вероятно не пивоварня)
            if len(brewery) <= 50:
                return brewery
        
        # Паттерн 3: Несколько слов в верхнем регистре в начале
        # Ищем последовательность слов в верхнем регистре (минимум 2, максимум 5 слов)
        match = re.match(r'^([A-ZА-ЯЁ][A-ZА-ЯЁ\s]{2,50}?)(?:\s+[a-zа-яё]|\s*\(|\s*$)', beer_name)
        if match:
            brewery = match.group(1).strip()
            # Проверяем количество слов (пивоварня обычно 1-3 слова)
            word_count = len(brewery.split())
            if 1 <= word_count <= 5 and len(brewery) <= 50:
                return brewery
        
        # Паттерн 4: Одно слово в верхнем регистре в начале (если оно не слишком короткое)
        match = re.match(r'^([A-ZА-ЯЁ][A-ZА-ЯЁ]{2,30})\s+', beer_name)
        if match:
            brewery = match.group(1).strip()
            # Проверяем, что это не обычное слово (например, не "IPA", "ALE")
            common_words = ['ipa', 'ale', 'lager', 'stout', 'porter', 'pilsner', 'wheat', 'sour']
            if brewery.upper() not in [w.upper() for w in common_words]:
                return brewery
        
        return None
    
    def _extract_row_data(self, row: pd.Series, 
                         col_mapping: Dict[str, int]) -> Optional[Dict]:
        """
        Извлекает данные из строки DataFrame.
        
        Args:
            row: Строка DataFrame
            col_mapping: Соответствие полей и индексов колонок
            
        Returns:
            Словарь с данными позиции или None
        """
        item = {}
        
        # Проверяем, что маппинг не пустой
        if not col_mapping:
            return None
        
        # Извлекаем значения по маппингу
        # Важно: извлекаем каждое поле только один раз, чтобы избежать дублирования
        # Сначала обрабатываем format_type, чтобы извлечь volume
        for field, idx in col_mapping.items():
            try:
                # Проверяем корректность индекса
                if idx is None or idx < 0:
                    continue
                    
                # Проверяем, что индекс в пределах строки
                if idx >= len(row):
                    continue
                
                # Проверяем, что значение не пустое
                if pd.isna(row.iloc[idx]):
                    continue
                
                value = row.iloc[idx]
                
                # Обрабатываем тире и другие обозначения пустых значений
                if isinstance(value, str):
                    value_str_check = value.strip().lower()
                    # Тире, прочерк, пустая строка считаем пустым значением
                    if value_str_check in ['-', '—', '–', '', 'nan', 'none', 'null']:
                        continue
                
                # Преобразуем в строку и очищаем
                if isinstance(value, (int, float)):
                    # Для чисел сохраняем как строку, но без лишних нулей
                    if field in ['price', 'abv']:
                        item[field] = str(value)
                    elif field == 'volume':
                        # volume сохраняем как число только если он еще не был извлечен из format_type
                        if 'volume' not in item:
                            item[field] = float(value)
                    else:
                        item[field] = str(int(value)) if float(value).is_integer() else str(value)
                else:
                    value_str = str(value).strip()
                    if value_str and value_str.lower() not in ['nan', 'none', '']:
                        # Если это поле ABV или IBU, и значение содержит "/", парсим его
                        if field == 'abv' and '/' in value_str:
                            # Парсим формат типа "5,1 / 12 / 27" или "4 / 11 / 20"
                            parts = value_str.split('/')
                            if len(parts) >= 1:
                                abv_val = parts[0].strip().replace(',', '.')
                                try:
                                    item['abv'] = str(float(abv_val))
                                except:
                                    item['abv'] = abv_val
                            if len(parts) >= 3 and 'ibu' not in col_mapping:
                                # Если IBU не определен отдельно, берем из этой колонки
                                ibu_val = parts[2].strip()
                                item['ibu'] = ibu_val
                        elif field == 'ibu' and '/' in value_str:
                            # Парсим IBU из формата "ABV / OG / IBU"
                            parts = value_str.split('/')
                            if len(parts) >= 3:
                                ibu_val = parts[2].strip()
                                item['ibu'] = ibu_val
                            elif len(parts) >= 1:
                                item['ibu'] = parts[0].strip()
                        elif field == 'format_type':
                            # Парсим формат и объем из колонки типа "ж/б 0.45 / 20" или "Тип фасовки / кол-во в уп"
                            # Формат: "ж/б 0.45" (жестяная банка 0.45 л) или "банка 0.5"
                            # Важно: используем split с ограничением, чтобы не разбить "ж/б"
                            if '/' in value_str:
                                # Разбиваем по "/" с ограничением в 2 части (формат/объем и количество)
                                # Но сначала нужно найти последний "/" который разделяет формат и количество
                                parts = value_str.rsplit('/', 1)  # Разбиваем справа только один раз
                                
                                if len(parts) >= 1:
                                    format_part = parts[0].strip()
                                    # Извлекаем формат (банка, кега, бутылка)
                                    format_lower = format_part.lower()
                                    if 'ж/б' in format_lower or 'банка' in format_lower or 'can' in format_lower:
                                        item['format_type'] = 'банка'
                                    elif 'кeg' in format_lower or 'кега' in format_lower or 'keg' in format_lower:
                                        item['format_type'] = 'кега'
                                    elif 'бут' in format_lower or 'bottle' in format_lower or 'бутылка' in format_lower:
                                        item['format_type'] = 'бутылка'
                                    else:
                                        item['format_type'] = format_part
                                    
                                    # Извлекаем объем из формата (например "0.45" или "0.5")
                                    # Ищем все числа в строке и берем последнее (обычно это объем)
                                    all_numbers = re.findall(r'(\d+[.,]?\d*)', format_part)
                                    if all_numbers:
                                        # Берем последнее число (оно обычно объем после формата)
                                        vol_val = all_numbers[-1].replace(',', '.')
                                        try:
                                            vol_float = float(vol_val)
                                            # Если объем меньше 1, предполагаем литры, иначе мл
                                            if vol_float < 1:
                                                item['volume'] = vol_float  # Сохраняем как число, не строку
                                            elif vol_float < 100:
                                                # Если число от 1 до 100, вероятно это литры (например, 5 л)
                                                item['volume'] = vol_float  # Сохраняем как число
                                            else:
                                                item['volume'] = vol_float / 1000  # мл в литры, сохраняем как число
                                        except Exception as e:
                                            pass
                                
                                if len(parts) >= 2:
                                    # Вторая часть может содержать количество в упаковке
                                    qty_part = parts[1].strip()
                                    # Если это число, можем использовать для объема или оставить как есть
                                    pass
                            else:
                                # Если нет "/", обрабатываем формат типа "кег 20 л" или "банка"
                                # Извлекаем объем из формата, если он указан
                                # Паттерны: "кег 20 л", "банка 0.5", "банка"
                                volume_patterns = [
                                    r'(\d+[.,]?\d*)\s*л\b',  # "20 л", "0.5 л"
                                    r'(\d+[.,]?\d*)\s*ml\b',  # "500 ml"
                                    r'(\d+[.,]?\d*)\s*мл\b',  # "500 мл"
                                ]
                                
                                volume_found = False
                                for pattern in volume_patterns:
                                    match = re.search(pattern, value_str, re.IGNORECASE)
                                    if match:
                                        vol_val = match.group(1).replace(',', '.')
                                        try:
                                            vol_float = float(vol_val)
                                            if 'мл' in match.group(0).lower() or 'ml' in match.group(0).lower():
                                                item['volume'] = vol_float / 1000
                                            else:
                                                item['volume'] = vol_float
                                            volume_found = True
                                            break
                                        except Exception:
                                            pass
                                
                                # Если не нашли объем по паттернам, ищем любое число
                                if not volume_found:
                                    all_numbers = re.findall(r'(\d+[.,]?\d*)', value_str)
                                    if all_numbers:
                                        vol_val = all_numbers[-1].replace(',', '.')
                                        try:
                                            vol_float = float(vol_val)
                                            if vol_float < 1:
                                                item['volume'] = vol_float
                                            elif vol_float < 100:
                                                item['volume'] = vol_float
                                            else:
                                                item['volume'] = vol_float / 1000
                                        except Exception:
                                            pass
                                
                                # Сохраняем формат (нормализуем)
                                format_lower = value_str.lower()
                                if 'ж/б' in format_lower or 'банка' in format_lower or 'can' in format_lower:
                                    item['format_type'] = 'банка'
                                elif 'кeg' in format_lower or 'кега' in format_lower or 'keg' in format_lower or 'кег' in format_lower:
                                    item['format_type'] = 'кега'
                                elif 'бут' in format_lower or 'bottle' in format_lower or 'бутылка' in format_lower:
                                    item['format_type'] = 'бутылка'
                                else:
                                    # Сохраняем оригинальное значение, но очищаем от объема
                                    # Удаляем числа с единицами измерения
                                    cleaned_format = re.sub(r'\s*\d+[.,]?\d*\s*(л|ml|мл|l)\b', '', value_str, flags=re.IGNORECASE)
                                    cleaned_format = cleaned_format.strip()
                                    item['format_type'] = cleaned_format if cleaned_format else value_str.strip()
                        elif field == 'volume':
                            # Если volume уже был извлечен из format_type, не перезаписываем
                            if 'volume' not in item:
                                if isinstance(value, (int, float)):
                                    item['volume'] = float(value)
                                else:
                                    # Пробуем извлечь число из строки
                                    vol_match = re.search(r'(\d+[.,]?\d*)', str(value))
                                    if vol_match:
                                        vol_val = vol_match.group(1).replace(',', '.')
                                        try:
                                            item['volume'] = float(vol_val)
                                        except:
                                            pass
                        elif field == 'beer_name':
                            # Извлекаем brewery из начала названия пива, если его нет отдельно
                            if 'brewery' not in col_mapping or not item.get('brewery'):
                                brewery_from_name = self._extract_brewery_from_name(value_str)
                                if brewery_from_name:
                                    item['brewery'] = brewery_from_name
                                    # Удаляем brewery из названия
                                    beer_name_cleaned = value_str
                                    # Если brewery была в кавычках, удаляем кавычки с содержимым
                                    quote_patterns = [
                                        r'[""]([A-ZА-ЯЁ][A-ZА-ЯЁa-zа-яё\s]{1,30}?)[""]',
                                        r'[«»]([A-ZА-ЯЁ][A-ZА-ЯЁa-zа-яё\s]{1,30}?)[«»]',
                                    ]
                                    brewery_in_quotes = False
                                    for pattern in quote_patterns:
                                        if re.search(pattern, value_str):
                                            # Удаляем кавычки с содержимым
                                            beer_name_cleaned = re.sub(pattern, '', beer_name_cleaned)
                                            brewery_in_quotes = True
                                            break
                                    
                                    if not brewery_in_quotes:
                                        # Удаляем brewery из начала названия
                                        beer_name_cleaned = value_str.replace(brewery_from_name, '', 1).strip()
                                        # Удаляем скобки с дополнительной информацией типа "(Fresh Brewed)"
                                        beer_name_cleaned = re.sub(r'\s*\([^)]*\)\s*', ' ', beer_name_cleaned).strip()
                                    
                                    # Очищаем от лишних пробелов и запятых
                                    beer_name_cleaned = re.sub(r'\s*,\s*', ' ', beer_name_cleaned).strip()
                                    beer_name_cleaned = re.sub(r'\s+', ' ', beer_name_cleaned).strip()
                                    
                                    item['beer_name'] = beer_name_cleaned if beer_name_cleaned else value_str
                                else:
                                    item[field] = value_str
                            else:
                                item[field] = value_str
                        else:
                            item[field] = value_str
            except (IndexError, KeyError, ValueError, TypeError) as e:
                logger.debug(f"Ошибка при извлечении поля {field} (индекс {idx}): {str(e)}")
                continue
        
        # Пост-обработка: исправляем неправильный маппинг
        # Сохраняем volume, если он был извлечен из format_type
        volume_val = item.get('volume')
        
        # Если в beer_name или других полях есть "brewery", перемещаем в brewery
        beer_name_val_raw = item.get('beer_name', '')
        brewery_val_raw = item.get('brewery', '')
        ibu_val = item.get('ibu', '')
        style_val_raw = item.get('style', '')
        price_val_raw = item.get('price', '')
        
        # Проверяем, не был ли volume случайно перезаписан текстовым значением
        # Если volume строка и не является числом, удаляем его
        if 'volume' in item and isinstance(item['volume'], str):
            try:
                # Пробуем преобразовать в число
                float(item['volume'])
            except (ValueError, TypeError):
                # Если не число, удаляем (был перезаписан текстовым значением)
                del item['volume']
                # Восстанавливаем из сохраненного значения
                if volume_val and isinstance(volume_val, (int, float)):
                    item['volume'] = float(volume_val)
        
        # Проверяем все текстовые поля на наличие слова "brewery"
        for field_name, field_value in [('beer_name', beer_name_val_raw), ('ibu', ibu_val), ('style', style_val_raw)]:
            if field_value and isinstance(field_value, str):
                field_lower = field_value.lower()
                # Если в значении есть "brewery" или "пивоварня", это пивоварня
                if 'brewery' in field_lower or 'пивоварня' in field_lower:
                    # Если brewery пустое, перемещаем значение туда
                    if not brewery_val_raw:
                        item['brewery'] = field_value
                        item[field_name] = ''  # Очищаем исходное поле
                    elif brewery_val_raw != field_value:
                        # Если brewery уже заполнено и отличается, оставляем brewery, очищаем это поле
                        item[field_name] = ''
        
        # Если brewery все еще пустое, но есть beer_name с "brewery", меняем местами
        if not brewery_val_raw and beer_name_val_raw:
            beer_name_lower = str(beer_name_val_raw).lower()
            if 'brewery' in beer_name_lower or 'пивоварня' in beer_name_lower:
                item['brewery'] = beer_name_val_raw
                item['beer_name'] = ''
        
        # Фильтрация: отбрасываем строки-заголовки без данных о пиве
        # Если есть только brewery, но нет beer_name, price, style - это заголовок секции
        brewery_val_check = item.get('brewery', '').strip() if item.get('brewery') else ''
        beer_name_val_check = item.get('beer_name', '').strip() if item.get('beer_name') else ''
        price_val_check = item.get('price', '').strip() if item.get('price') else ''
        style_val_check = item.get('style', '').strip() if item.get('style') else ''
        
        if brewery_val_check and not beer_name_val_check and not price_val_check and not style_val_check:
            # Проверяем, не содержит ли brewery адрес (г., г., город, city)
            brewery_lower = str(brewery_val_check).lower()
            address_indicators = [
                'г.', 'г ', 'город', 'city', 'ул.', 'улица', 'street', 
                'владимир', 'москва', 'санкт-петербург', 'spb', 'мск',
                'проспект', 'пр.', 'переулок', 'пер.', 'площадь', 'пл.'
            ]
            has_address = any(indicator in brewery_lower for indicator in address_indicators)
            
            # Проверяем, не является ли brewery служебным текстом
            service_keywords = ['прайс', 'price list', 'каталог', 'менеджер', 
                              'контакт', 'телефон', 'email', 'адрес']
            has_service_keyword = any(keyword in brewery_lower for keyword in service_keywords)
            
            if has_address or has_service_keyword or len(brewery_val_check.strip()) < 3:
                # Это заголовок секции или некорректная строка, пропускаем
                logger.debug(f"Пропущена строка с brewery '{brewery_val_check}' - похоже на заголовок")
                return None
        
        # Строгая проверка валидности записи
        # Запись считается валидной, если:
        # 1. Есть beer_name И (price ИЛИ brewery ИЛИ style)
        # 2. ИЛИ есть brewery И price (даже без beer_name)
        # 3. НО НЕ только brewery без других данных
        
        beer_name_val = beer_name_val_check
        brewery_val = brewery_val_check
        price_val = price_val_check
        style_val = style_val_check
        
        # Проверяем, что все поля не являются только тире или пустыми
        def is_empty_value(val):
            """Проверяет, является ли значение пустым или только тире"""
            if not val:
                return True
            val_str = str(val).strip().lower()
            return val_str in ['-', '—', '–', '', 'nan', 'none', 'null']
        
        # Подсчитываем количество заполненных полей
        filled_fields = []
        if beer_name_val and not is_empty_value(beer_name_val):
            filled_fields.append('beer_name')
        if brewery_val and not is_empty_value(brewery_val):
            filled_fields.append('brewery')
        if price_val and not is_empty_value(price_val):
            filled_fields.append('price')
        if style_val and not is_empty_value(style_val):
            filled_fields.append('style')
        
        # Если нет заполненных полей - пропускаем
        if not filled_fields:
            logger.debug("Пропущена строка без заполненных полей")
            return None
        
        # Если только brewery без других данных - это заголовок секции
        if len(filled_fields) == 1 and 'brewery' in filled_fields:
            logger.debug(f"Пропущена строка с только brewery '{brewery_val}' без других данных")
            return None
        
        # Если есть beer_name, но нет price и нет brewery и нет style - возможно некорректная запись
        if beer_name_val and not is_empty_value(beer_name_val):
            if not price_val and not brewery_val and not style_val:
                # Проверяем, не является ли beer_name служебным текстом
                beer_name_lower = beer_name_val.lower()
                service_keywords = ['прайс', 'price list', 'каталог', 'менеджер', 
                                  'контакт', 'телефон', 'email', 'адрес', 'наименование',
                                  'название', 'товар', 'продукт']
                if any(keyword in beer_name_lower for keyword in service_keywords):
                    logger.debug(f"Пропущена строка с служебным текстом в beer_name: '{beer_name_val}'")
                    return None
        
        # Если нет beer_name, но есть brewery и price - это валидная запись
        # Если есть beer_name и хотя бы одно из (price, brewery, style) - это валидная запись
        has_valid_combination = (
            (beer_name_val and not is_empty_value(beer_name_val) and 
             (price_val or brewery_val or style_val)) or
            (brewery_val and not is_empty_value(brewery_val) and price_val)
        )
        
        if not has_valid_combination:
            logger.debug(f"Пропущена строка без валидной комбинации полей: beer_name={bool(beer_name_val)}, brewery={bool(brewery_val)}, price={bool(price_val)}")
            return None
        
        return item
    
    def _guess_column_mapping(self, df: pd.DataFrame) -> Dict[str, int]:
        """
        Пытается угадать маппинг колонок по содержимому первых строк.
        
        Args:
            df: DataFrame с данными
            
        Returns:
            Словарь {название_поля: индекс_колонки}
        """
        mapping = {}
        
        if df.empty or len(df.columns) == 0:
            return mapping
        
        # Анализируем первые несколько строк для определения типов данных
        sample_rows = df.head(min(10, len(df)))
        
        # Ищем колонки с текстом
        text_columns = []
        for col_idx in range(min(10, len(df.columns))):
            col_name = df.columns[col_idx]
            sample_values = sample_rows[col_name].dropna().astype(str).tolist()
            
            # Проверяем паттерны в значениях
            text_values = [v for v in sample_values 
                          if len(str(v)) > 2 and 
                          not str(v).replace('.', '').replace('-', '').replace(' ', '').isdigit()]
            
            if len(text_values) > len(sample_values) * 0.5:  # Если больше половины - текст
                text_columns.append((col_idx, text_values))
        
        # Определяем пивоварню и название пива
        # Пивоварня часто содержит слова типа "Brewery", "Пивоварня", короткие названия компаний
        # Название пива обычно длиннее и содержит больше слов
        for col_idx, text_values in text_columns:
            # Проверяем на наличие слов "brewery", "пивоварня" в значениях
            has_brewery_words = any('brewery' in str(v).lower() or 'пивоварня' in str(v).lower() 
                                   for v in text_values[:5])
            
            if has_brewery_words and 'brewery' not in mapping:
                mapping['brewery'] = col_idx
            elif 'beer_name' not in mapping:
                # Если это первая текстовая колонка без brewery - вероятно название пива
                mapping['beer_name'] = col_idx
        
        # Ищем колонку с ценами (содержит числа)
        for col_idx in range(min(10, len(df.columns))):
            col_name = df.columns[col_idx]
            sample_values = sample_rows[col_name].dropna()
            
            if len(sample_values) > 0:
                numeric_values = [v for v in sample_values if isinstance(v, (int, float)) and v > 0]
                if len(numeric_values) > len(sample_values) * 0.5:  # Если больше половины - числа
                    if 'price' not in mapping and max(numeric_values) < 10000:  # Цены обычно меньше 10000
                        mapping['price'] = col_idx
                    elif 'abv' not in mapping and max(numeric_values) <= 100:  # Крепость обычно до 100
                        mapping['abv'] = col_idx
        
        return mapping
    
    def _analyze_data_content(self, df: pd.DataFrame) -> Dict[str, int]:
        """
        Анализирует содержимое данных для определения колонок.
        Более агрессивный подход: анализирует первые несколько строк.
        
        Args:
            df: DataFrame с данными
            
        Returns:
            Словарь {название_поля: индекс_колонки}
        """
        mapping = {}
        
        if df.empty or len(df.columns) == 0:
            return mapping
        
        # Берем первые 5 строк для анализа
        sample = df.head(5)
        
        # Проходим по каждой колонке и анализируем содержимое
        for col_idx in range(min(10, len(df.columns))):
            col_data = sample.iloc[:, col_idx].dropna().astype(str).tolist()
            
            if not col_data:
                continue
            
            # Проверяем наличие слова "brewery" в данных
            has_brewery = any('brewery' in str(v).lower() or 'пивоварня' in str(v).lower() 
                            for v in col_data)
            
            # Проверяем на числа (цены)
            numeric_count = sum(1 for v in col_data 
                              if isinstance(df.iloc[0, col_idx], (int, float)) 
                              or (isinstance(v, str) and v.replace('.', '').replace(',', '').isdigit()))
            
            # Проверяем длину текста (названия пива обычно длиннее)
            avg_length = sum(len(str(v)) for v in col_data[:3]) / min(3, len(col_data))
            
            if has_brewery and 'brewery' not in mapping:
                mapping['brewery'] = col_idx
            elif numeric_count > len(col_data) * 0.6 and 'price' not in mapping:
                # Если много чисел - вероятно цена
                try:
                    first_num = float(str(col_data[0]).replace(',', '.'))
                    if 10 < first_num < 10000:
                        mapping['price'] = col_idx
                except:
                    pass
            elif avg_length > 10 and 'beer_name' not in mapping and not has_brewery:
                # Длинный текст без brewery - вероятно название пива
                mapping['beer_name'] = col_idx
            elif avg_length > 5 and 'brewery' not in mapping and 'beer_name' not in mapping:
                # Средний текст - может быть пивоварня или название
                if 'brewery' not in mapping:
                    mapping['beer_name'] = col_idx
        
        return mapping
    
    def extract_tables(self):
        """
        Извлечение всех таблиц из Excel.
        
        Returns:
            Список таблиц (DataFrames преобразуются в списки)
        """
        tables = []
        try:
            excel_file = pd.ExcelFile(self.file_path)
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name)
                tables.append(df.values.tolist())
        except Exception:
            pass
        return tables
    
    def extract_text(self):
        """
        Извлечение всего текста из Excel.
        
        Returns:
            Текст файла (все значения соединены)
        """
        text = ""
        try:
            excel_file = pd.ExcelFile(self.file_path)
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name)
                text += f"Sheet: {sheet_name}\n"
                text += df.to_string() + "\n\n"
        except Exception:
            pass
        return text

