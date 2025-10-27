"""Парсер для PDF файлов."""

import pdfplumber
import pandas as pd
from typing import Optional


class PDFParser:
    """Парсер PDF файлов.

    Извлекает таблицы из PDF документов используя pdfplumber.
    """

    @staticmethod
    def parse(file_path: str, page_number: int = 0) -> pd.DataFrame:
        """Парсинг PDF файла.

        Args:
            file_path: Путь к PDF файлу
            page_number: Номер страницы для чтения

        Returns:
            DataFrame с данными

        Raises:
            ValueError: Если файл не может быть прочитан
        """
        try:
            with pdfplumber.open(file_path) as pdf:
                # Проверка количества страниц
                if len(pdf.pages) <= page_number:
                    raise ValueError(
                        f"Страница {page_number} не найдена в файле"
                    )

                # Извлекаем первую таблицу со страницы
                page = pdf.pages[page_number]
                tables = page.extract_tables()

                if not tables or len(tables) == 0:
                    raise ValueError("Таблицы не найдены на странице")

                # Берем первую таблицу и преобразуем в DataFrame
                table = tables[0]

                # Первая строка - заголовки
                if len(table) == 0:
                    raise ValueError("Пустая таблица")

                headers = table[0]
                data = table[1:] if len(table) > 1 else []

                df = pd.DataFrame(data, columns=headers)

                # Очистка данных
                df = df.dropna(how='all')
                df = df.dropna(axis=1, how='all')

                return df

        except Exception as e:
            raise ValueError(f"Ошибка чтения PDF файла: {str(e)}")

    @staticmethod
    def get_page_count(file_path: str) -> int:
        """Получить количество страниц в PDF.

        Args:
            file_path: Путь к файлу

        Returns:
            Количество страниц
        """
        try:
            with pdfplumber.open(file_path) as pdf:
                return len(pdf.pages)
        except Exception as e:
            raise ValueError(
                f"Ошибка чтения структуры PDF: {str(e)}"
            )
