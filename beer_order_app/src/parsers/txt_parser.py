"""Парсер для текстовых файлов."""

import pandas as pd
from typing import Optional
import re


class TXTParser:
    """Парсер текстовых файлов.

    Распознает табличные данные в текстовых файлах,
    поддерживает разделители: табуляция, запятая, точка с запятой.
    """

    @staticmethod
    def parse(file_path: str, delimiter: Optional[str] = None) -> pd.DataFrame:
        """Парсинг текстового файла.

        Args:
            file_path: Путь к файлу
            delimiter: Разделитель (автоопределение если None)

        Returns:
            DataFrame с данными

        Raises:
            ValueError: Если файл не может быть прочитан
        """
        try:
            # Автоопределение разделителя
            if delimiter is None:
                delimiter = TXTParser._detect_delimiter(file_path)

            # Чтение файла
            df = pd.read_csv(file_path, delimiter=delimiter, encoding='utf-8')

            # Если utf-8 не сработал, пробуем другие кодировки
            if df.empty or df.shape[1] == 1:
                for encoding in ['cp1251', 'latin-1']:
                    try:
                        df = pd.read_csv(
                            file_path, delimiter=delimiter, encoding=encoding
                        )
                        break
                    except:
                        continue

            # Очистка данных
            df = df.dropna(how='all')
            df = df.dropna(axis=1, how='all')

            return df

        except Exception as e:
            raise ValueError(f"Ошибка чтения текстового файла: {str(e)}")

    @staticmethod
    def _detect_delimiter(file_path: str) -> str:
        """Автоматическое определение разделителя.

        Args:
            file_path: Путь к файлу

        Returns:
            Разделитель
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            first_line = f.readline()

        # Подсчет частоты различных разделителей
        delimiters = {'\t': first_line.count('\t'),
                      ',': first_line.count(','),
                      ';': first_line.count(';')}

        # Возвращаем наиболее частый разделитель
        if max(delimiters.values()) == 0:
            return ' '  # Пробел по умолчанию

        return max(delimiters, key=delimiters.get)
