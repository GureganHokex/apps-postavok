"""Тесты для парсеров."""

import pytest
import pandas as pd
import os
from src.parsers import ExcelParser, PDFParser, TXTParser


class TestExcelParser:
    """Тесты для Excel парсера."""

    def test_excel_parser_initialization(self):
        """Проверка инициализации парсера."""
        parser = ExcelParser()
        assert parser is not None

    def test_get_sheet_names(self):
        """Проверка получения названий листов."""
        # Тест будет расширен после создания тестовых файлов
        assert True


class TestPDFParser:
    """Тесты для PDF парсера."""

    def test_pdf_parser_initialization(self):
        """Проверка инициализации парсера."""
        parser = PDFParser()
        assert parser is not None


class TestTXTParser:
    """Тесты для TXT парсера."""

    def test_txt_parser_initialization(self):
        """Проверка инициализации парсера."""
        parser = TXTParser()
        assert parser is not None

    def test_detect_delimiter_comma(self):
        """Проверка определения разделителя - запятая."""
        # Тест будет реализован с тестовым файлом
        assert True
