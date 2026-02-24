"""
Модульная структура Excel парсера.

Разделение монолитного excel_parser.py на специализированные модули:
- column_mapper.py - маппинг колонок
- header_finder.py - поиск заголовков
- row_extractor.py - извлечение данных из строк
- format_detector.py - определение формата/объема
- deduplicator.py - дедупликация
- formatting_checker.py - проверка форматирования Excel
"""

from ..excel_parser import ExcelParser
from parser_app.domain.services.deduplication import Deduplicator
from .formatting_checker import ExcelFormattingChecker

__all__ = ['ExcelParser', 'Deduplicator', 'ExcelFormattingChecker']
