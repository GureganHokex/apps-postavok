"""
Парсер для PDF файлов.
"""

import pdfplumber
try:
    import pytesseract
    from PIL import Image
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
from typing import List, Dict
from .base_parser import BaseParser


class PDFParser(BaseParser):
    """
    Парсер для PDF файлов.
    
    Использует pdfplumber для структурированных PDF и
    pytesseract для сканов с OCR.
    """
    
    def parse(self) -> List[Dict]:
        """
        Парсинг PDF файла.
        
        Returns:
            Список словарей с данными о позициях
        """
        items = []
        
        try:
            # Пробуем извлечь таблицы через pdfplumber
            with pdfplumber.open(self.file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    # Извлекаем таблицы
                    tables = page.extract_tables()
                    for table_num, table in enumerate(tables):
                        if table:
                            parsed_items = self._parse_table(
                                table, page_num, table_num
                            )
                            items.extend(parsed_items)
                    
                    # Если таблиц нет, пробуем извлечь текст построчно
                    if not tables:
                        text = page.extract_text()
                        if text:
                            parsed_items = self._parse_text_lines(
                                text, page_num
                            )
                            items.extend(parsed_items)
        except Exception as e:
            # Если pdfplumber не справился, пробуем OCR
            items = self._parse_with_ocr()
        
        return items
    
    def _parse_table(self, table: List[List], page_num: int, 
                     table_num: int) -> List[Dict]:
        """
        Парсинг таблицы из PDF.
        
        Args:
            table: Таблица как список строк
            page_num: Номер страницы
            table_num: Номер таблицы на странице
            
        Returns:
            Список словарей с данными позиций
        """
        items = []
        
        if not table or len(table) < 2:
            return items
        
        # Первая строка обычно заголовки
        headers = [str(cell).strip().lower() if cell else '' 
                   for cell in table[0]]
        
        # Определяем индексы колонок
        col_mapping = self._map_columns(headers)
        
        # Парсим строки данных
        for row_num, row in enumerate(table[1:], start=2):
            if not row or all(not cell for cell in row):
                continue
            
            item = self._extract_row_data(row, col_mapping)
            if item:
                item['raw_source_location'] = {
                    'page': page_num,
                    'table': table_num,
                    'row': row_num
                }
                items.append(item)
        
        return items
    
    def _parse_text_lines(self, text: str, page_num: int) -> List[Dict]:
        """
        Парсинг текста построчно (когда таблиц нет).
        
        Args:
            text: Текст страницы
            page_num: Номер страницы
            
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
            item = self._extract_line_data(line)
            if item:
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
        
        # Варианты названий для каждого поля
        field_patterns = {
            'brewery': ['пивоварня', 'производитель', 'brewery', 
                       'manufacturer', 'brand'],
            'beer_name': ['название', 'пиво', 'beer', 'name', 
                         'наименование'],
            'style': ['стиль', 'style', 'тип', 'type'],
            'abv': ['abv', 'крепость', 'алкоголь', 'alcohol'],
            'ibu': ['ibu', 'горечь', 'bitterness'],
            'price': ['цена', 'price', 'стоимость', 'cost'],
            'volume': ['объём', 'volume', 'литр', 'литров', 'л', 
                      'ml', 'мл'],
            'format_type': ['формат', 'format', 'упаковка', 
                          'packaging'],
            'stock': ['остаток', 'stock', 'наличие', 'availability'],
        }
        
        for field, patterns in field_patterns.items():
            for idx, header in enumerate(headers):
                if any(pattern in header for pattern in patterns):
                    mapping[field] = idx
                    break
        
        return mapping
    
    def _extract_row_data(self, row: List, col_mapping: Dict[str, int]) -> Dict:
        """
        Извлекает данные из строки таблицы.
        
        Args:
            row: Строка таблицы
            col_mapping: Соответствие полей и индексов колонок
            
        Returns:
            Словарь с данными позиции или None
        """
        item = {}
        
        # Извлекаем значения по маппингу
        for field, idx in col_mapping.items():
            if idx < len(row) and row[idx]:
                value = str(row[idx]).strip()
                if value:
                    item[field] = value
        
        # Если нет хотя бы названия пива или пивоварни, пропускаем
        if not item.get('beer_name') and not item.get('brewery'):
            return None
        
        return item
    
    def _extract_line_data(self, line: str) -> Dict:
        """
        Извлекает данные из текстовой строки.
        
        Args:
            line: Текстовая строка
            
        Returns:
            Словарь с данными позиции или None
        """
        # Базовая реализация - можно улучшить регулярными выражениями
        # Пока возвращаем None, чтобы не парсить мусорные строки
        return None
    
    def extract_tables(self):
        """
        Извлечение всех таблиц из PDF.
        
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
    
    def extract_text(self):
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

