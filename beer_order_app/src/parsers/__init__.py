"""Парсеры для различных форматов файлов."""

from .excel_parser import ExcelParser
from .pdf_parser import PDFParser
from .txt_parser import TXTParser

__all__ = ['ExcelParser', 'PDFParser', 'TXTParser']
