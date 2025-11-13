"""
Базовый класс для парсеров файлов.
"""

from abc import ABC, abstractmethod
from typing import List, Dict


class BaseParser(ABC):
    """
    Базовый класс для всех парсеров файлов.
    
    Определяет интерфейс для парсинга файлов различных форматов.
    Все парсеры должны реализовать метод parse().
    """
    
    def __init__(self, file_path: str):
        """
        Инициализация парсера.
        
        Args:
            file_path: Путь к файлу для парсинга
        """
        self.file_path = file_path
    
    @abstractmethod
    def parse(self) -> List[Dict]:
        """
        Основной метод парсинга файла.
            
        Returns:
            Список словарей с данными о позициях.
            Каждый словарь должен содержать ключи:
            - brewery, beer_name, style, abv, ibu, price, currency,
              volume, format_type, stock, supplier_name, raw_source_location
        """
        pass
    
    def extract_tables(self):
        """
        Извлечение таблиц из файла (если применимо).
        
        Returns:
            Список таблиц в виде списков строк
        """
        return []
    
    def extract_text(self):
        """
        Извлечение текста из файла (если применимо).
            
        Returns:
            Текст файла
        """
        return ""
