"""Парсер для Excel файлов."""

import pandas as pd
from typing import Optional, List


class ExcelParser:
    """Парсер Excel файлов (.xlsx, .xls).

    Читает и извлекает данные из Excel файлов, поддерживает
    множественные листы.
    """

    @staticmethod
    def parse(file_path: str, sheet_name: Optional[str] = None) -> pd.DataFrame:
        """Парсинг Excel файла.

        Args:
            file_path: Путь к файлу
            sheet_name: Название листа (если None - берет первый)

        Returns:
            DataFrame с данными

        Raises:
            ValueError: Если файл не может быть прочитан
        """
        try:
            # Пробуем прочитать указанный лист
            if sheet_name:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
            else:
                # Читаем первый лист
                excel_file = pd.ExcelFile(file_path)
                df = pd.read_excel(excel_file, sheet_name=0)

            # Убираем полностью пустые строки
            df = df.dropna(how='all')

            # Убираем полностью пустые колонки
            df = df.dropna(axis=1, how='all')

            return df

        except Exception as e:
            raise ValueError(f"Ошибка чтения Excel файла: {str(e)}")

    @staticmethod
    def get_sheet_names(file_path: str) -> List[str]:
        """Получить список всех листов в файле.

        Args:
            file_path: Путь к файлу

        Returns:
            Список названий листов
        """
        try:
            excel_file = pd.ExcelFile(file_path)
            return excel_file.sheet_names
        except Exception as e:
            raise ValueError(f"Ошибка чтения структуры файла: {str(e)}")
