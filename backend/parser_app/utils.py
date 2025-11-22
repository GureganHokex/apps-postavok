"""
Вспомогательные функции для работы с файлами и данными.
"""

import os
import zipfile
from pathlib import Path


def extract_zip(zip_path, extract_to):
    """
    Распаковывает ZIP архив в указанную директорию.
    
    Args:
        zip_path: Путь к ZIP файлу
        extract_to: Директория для распаковки
        
    Returns:
        Список путей к распакованным файлам
    """
    extracted_files = []
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
        for file_info in zip_ref.namelist():
            extracted_path = os.path.join(extract_to, file_info)
            if os.path.isfile(extracted_path):
                extracted_files.append(extracted_path)
    return extracted_files


def detect_file_type(filename):
    """
    Определяет тип файла по расширению.
    
    Args:
        filename: Имя файла
        
    Returns:
        Строка с типом файла ('pdf', 'excel', 'zip', 'unknown')
    """
    ext = Path(filename).suffix.lower()
    if ext == '.pdf':
        return 'pdf'
    elif ext in ['.xls', '.xlsx']:
        return 'excel'
    elif ext == '.zip':
        return 'zip'
    else:
        return 'unknown'


def safe_float(value, default=None):
    """
    Безопасное преобразование в float.
    
    Args:
        value: Значение для преобразования
        default: Значение по умолчанию при ошибке
        
    Returns:
        Float или default
    """
    if value is None or value == '':
        return default
    try:
        # Заменяем запятую на точку для русских чисел
        if isinstance(value, str):
            value = value.replace(',', '.')
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value, default=None):
    """
    Безопасное преобразование в int.
    
    Args:
        value: Значение для преобразования
        default: Значение по умолчанию при ошибке
        
    Returns:
        Int или default
    """
    if value is None or value == '':
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default
