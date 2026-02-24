"""
Парсер для Google Sheets.
"""

import pandas as pd
from typing import List, Dict, Optional
from .base_parser import BaseParser


class GoogleSheetsParser(BaseParser):
    """
    Парсер для Google Sheets.
    
    Использует Google Sheets API для получения данных,
    затем парсит аналогично Excel парсеру.
    """
    
    def __init__(self, file_path: str, sheet_url: Optional[str] = None):
        """
        Инициализация парсера Google Sheets.
        
        Args:
            file_path: Путь для сохранения данных (не используется)
            sheet_url: URL Google Sheets документа
        """
        super().__init__(file_path)
        self.sheet_url = sheet_url
    
    def parse(self, supplier_type=None, brewery_name=None, supplier_column_mapping=None, **kwargs) -> List[Dict]:
        """
        Парсинг Google Sheets.
        
        Returns:
            Список словарей с данными о позициях
        """
        items = []
        self._supplier_column_mapping = supplier_column_mapping
        
        if not self.sheet_url:
            return items
        
        try:
            # Преобразуем Google Sheets URL в экспорт URL
            export_url = self._convert_to_export_url(self.sheet_url)
            
            # Читаем данные через pandas
            df = pd.read_csv(export_url)
            
            # Парсим аналогично Excel парсеру
            parsed_items = self._parse_dataframe(df, 'Sheet1', supplier_column_mapping=supplier_column_mapping)
            items.extend(parsed_items)
        except Exception as e:
            # Если не удалось через CSV, пробуем через API
            items = self._parse_with_api()
        
        return items
    
    def _convert_to_export_url(self, sheet_url: str) -> str:
        """
        Преобразует Google Sheets URL в URL для экспорта CSV.
        
        Args:
            sheet_url: Оригинальный URL Google Sheets
            
        Returns:
            URL для экспорта CSV
        """
        # Извлекаем ID документа из URL
        # Формат: https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit
        if '/d/' in sheet_url:
            sheet_id = sheet_url.split('/d/')[1].split('/')[0]
            export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=0"
            return export_url
        
        return sheet_url
    
    def _parse_with_api(self) -> List[Dict]:
        """
        Парсинг через Google Sheets API (требует настройки API ключа).
        
        Returns:
            Список словарей с данными позиций
        """
        items = []
        # TODO: Реализовать при необходимости через google-api-python-client
        # Это требует настройки credentials и API ключа
        return items
    
    def _parse_dataframe(self, df: pd.DataFrame, sheet_name: str, supplier_column_mapping: Optional[Dict] = None) -> List[Dict]:
        """
        Парсинг DataFrame из Google Sheets.
        
        Args:
            df: DataFrame с данными
            sheet_name: Имя листа
            supplier_column_mapping: маппинг от настроек поставщика (поле -> список ключевых слов)
            
        Returns:
            Список словарей с данными позиций
        """
        items = []
        
        if df.empty:
            return items
        
        # Используем ту же логику, что и Excel парсер
        from .excel_parser import ExcelParser
        
        # Создаем временный Excel парсер для переиспользования логики
        temp_parser = ExcelParser(self.file_path)
        col_mapping = temp_parser._map_columns(df.columns.tolist())
        if supplier_column_mapping:
            user_mapping = temp_parser._build_col_mapping_from_supplier(df.columns.tolist(), supplier_column_mapping)
            if user_mapping:
                col_mapping = {**col_mapping, **user_mapping}
        
        if not col_mapping:
            header_row = temp_parser._find_header_row(df)
            if header_row is not None:
                col_mapping = temp_parser._map_columns(
                    df.iloc[header_row].tolist()
                )
                df = df.iloc[header_row + 1:].reset_index(drop=True)
        
        for idx, row in df.iterrows():
            item = temp_parser._extract_row_data(row, col_mapping)
            if item:
                item['raw_source_location'] = {
                    'sheet': sheet_name,
                    'row': idx + 1,
                    'source': 'google_sheets'
                }
                items.append(item)
        
        return items
    
    def extract_tables(self):
        """
        Извлечение всех таблиц из Google Sheets.
        
        Returns:
            Список таблиц
        """
        tables = []
        try:
            export_url = self._convert_to_export_url(self.sheet_url)
            df = pd.read_csv(export_url)
            tables.append(df.values.tolist())
        except Exception:
            pass
        return tables
    
    def extract_text(self):
        """
        Извлечение всего текста из Google Sheets.
        
        Returns:
            Текст файла
        """
        text = ""
        try:
            export_url = self._convert_to_export_url(self.sheet_url)
            df = pd.read_csv(export_url)
            text = df.to_string()
        except Exception:
            pass
        return text

