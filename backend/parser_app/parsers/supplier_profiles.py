"""
Профили парсинга для разных типов поставщиков.
"""

import pandas as pd
import re
import logging
from typing import Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class SupplierType(Enum):
    """Типы поставщиков."""
    DISTRIBUTOR = "distributor"  # Дистрибьютор (много пивоварен)
    BREWERY = "brewery"  # Конкретная пивоварня
    UNKNOWN = "unknown"  # Неизвестный тип


class SupplierProfileDetector:
    """
    Определяет тип поставщика и структуру прайса.
    """
    
    def detect(self, df: pd.DataFrame, sheet_name: str = None, file_name: str = None) -> Tuple[SupplierType, Dict]:
        """
        Определяет тип поставщика и его характеристики.
        
        Args:
            df: DataFrame с данными
            sheet_name: Имя листа
            file_name: Имя файла (опционально)
            
        Returns:
            Tuple (тип поставщика, характеристики)
        """
        try:
            if df.empty or df is None:
                return SupplierType.UNKNOWN, {}
            
            # Анализируем первые строки для определения структуры (ограничиваем для скорости)
            sample_rows = df.head(min(10, len(df)))  # Уменьшаем с 20 до 10
            
            characteristics = {
                'has_brewery_column': False,
                'brewery_in_name_column': False,
                'multiple_breweries': False,
                'single_brewery_name': None,
                'structure_type': 'unknown'
            }
            
            # 1. Анализ имени файла и листа (НОВОЕ)
            file_name_hints = self._analyze_filename_hints(file_name, sheet_name)
            if file_name_hints:
                characteristics.update(file_name_hints)
                logger.debug(f"Подсказки из имени файла/листа: {file_name_hints}")
            
            # Проверяем наличие отдельной колонки пивоварни (ограничиваем до 5 колонок)
            for col_idx in range(min(5, len(df.columns))):
                try:
                    col_header = str(df.columns[col_idx]).lower() if col_idx < len(df.columns) else ''
                    # Проверяем только заголовок колонки для скорости
                    brewery_indicators = ['пивоварня', 'brewery', 'производитель', 'manufacturer']
                    if any(indicator in col_header for indicator in brewery_indicators):
                        characteristics['has_brewery_column'] = True
                        break
                except Exception:
                    continue
            
            # Анализируем первую текстовую колонку (обычно название) - ограничиваем до 3 колонок
            for col_idx in range(min(3, len(df.columns))):
                try:
                    col_data = sample_rows.iloc[:, col_idx].dropna().astype(str).tolist()[:15]  # Только первые 15 строк
                    if col_data:
                        avg_len = sum(len(str(v)) for v in col_data[:5]) / min(5, len(col_data))  # Только первые 5 для расчета
                        
                        # Если длинная текстовая колонка - анализируем содержимое
                        if avg_len > 15:
                            # Извлекаем пивоварни из названий (уменьшаем выборку до 15)
                            breweries = self._extract_breweries_from_names(col_data[:15])
                            
                            if len(breweries) > 1:
                                characteristics['multiple_breweries'] = True
                                characteristics['brewery_in_name_column'] = True
                                characteristics['structure_type'] = 'distributor'
                                logger.debug(f"Найдено {len(breweries)} разных пивоварен: {breweries[:5]}")
                            elif len(breweries) == 1:
                                characteristics['single_brewery_name'] = breweries[0]
                                characteristics['brewery_in_name_column'] = True
                                characteristics['structure_type'] = 'brewery'
                                logger.debug(f"Найдена одна пивоварня: {breweries[0]}")
                            else:
                                # Не нашли пивоварни - возможно они в отдельной колонке или формат другой
                                # Проверяем, может быть все названия начинаются одинаково
                                first_words = []
                                for name in col_data[:20]:
                                    if name and len(name) > 3:
                                        first_word = name.split()[0] if name.split() else name[:10]
                                        first_words.append(first_word.upper())
                                
                                if first_words:
                                    unique_first_words = set(first_words)
                                    if len(unique_first_words) == 1:
                                        # Все начинаются одинаково - вероятно одна пивоварня
                                        characteristics['single_brewery_name'] = first_words[0]
                                        characteristics['brewery_in_name_column'] = True
                                        characteristics['structure_type'] = 'brewery'
                                        logger.debug(f"Все названия начинаются с '{first_words[0]}' - одна пивоварня")
                                else:
                                    characteristics['structure_type'] = 'unknown'
                            break
                except Exception as e:
                    logger.debug(f"Ошибка при анализе колонки {col_idx}: {str(e)}")
                    continue
            
            # Определяем тип поставщика
            try:
                # Приоритет 1: Явные признаки в данных (самый надежный источник)
                # Если найдено множество пивоварен - это дистрибьютор
                if characteristics.get('multiple_breweries'):
                    supplier_type = SupplierType.DISTRIBUTOR
                    logger.info(f"Тип поставщика определен по данным: Дистрибьютор (найдено множество пивоварен)")
                # Если есть отдельная колонка brewery с множеством значений
                elif characteristics.get('has_brewery_column'):
                    supplier_type = self._check_brewery_diversity(df, sample_rows)
                    if supplier_type == SupplierType.DISTRIBUTOR:
                        logger.info(f"Тип поставщика определен по колонке brewery: Дистрибьютор")
                    elif supplier_type == SupplierType.BREWERY:
                        logger.info(f"Тип поставщика определен по колонке brewery: Пивоварня")
                # Приоритет 2: Одна пивоварня в данных
                elif characteristics.get('single_brewery_name'):
                    supplier_type = SupplierType.BREWERY
                    logger.info(f"Тип поставщика определен по данным: Пивоварня ({characteristics.get('single_brewery_name')})")
                # Приоритет 3: Подсказка из имени файла (используется только если данных недостаточно)
                else:
                    filename_hint = characteristics.get('filename_hint')
                    if filename_hint == 'distributor':
                        supplier_type = SupplierType.DISTRIBUTOR
                        logger.info(f"Тип поставщика определен по имени файла: Дистрибьютор")
                    elif filename_hint == 'brewery':
                        supplier_type = SupplierType.BREWERY
                        # Если нашли название пивоварни в имени файла, используем его
                        if characteristics.get('filename_brewery'):
                            characteristics['single_brewery_name'] = characteristics.get('filename_brewery')
                        logger.info(f"Тип поставщика определен по имени файла: Пивоварня")
                    else:
                        supplier_type = SupplierType.UNKNOWN
            except Exception as e:
                logger.warning(f"Ошибка при определении типа поставщика: {str(e)}", exc_info=True)
                supplier_type = SupplierType.UNKNOWN
            
            logger.info(f"Определен тип поставщика: {supplier_type.value}, характеристики: {characteristics}")
            
            return supplier_type, characteristics
        except Exception as e:
            logger.error(f"Критическая ошибка при определении типа поставщика: {str(e)}", exc_info=True)
            return SupplierType.UNKNOWN, {}
    
    def _extract_breweries_from_names(self, names: List[str]) -> List[str]:
        """
        Извлекает названия пивоварен из списка названий пива.
        
        Args:
            names: Список названий пива
            
        Returns:
            Список уникальных названий пивоварен
        """
        breweries = set()
        
        for name in names:
            if not name or len(name) < 3:
                continue
            
            # Паттерны для извлечения пивоварни
            # 1. Пивоварня в кавычках (например, "Paradox" в "Бокал "Paradox", 400 ml")
            quote_patterns = [
                r'[""]([A-ZА-ЯЁ][A-ZА-ЯЁa-zа-яё\s]{1,30}?)[""]',  # "Paradox" или "Paradox"
                r'[«»]([A-ZА-ЯЁ][A-ZА-ЯЁa-zа-яё\s]{1,30}?)[«»]',  # «Paradox»
            ]
            found_in_quotes = False
            for pattern in quote_patterns:
                matches = re.findall(pattern, name)
                if matches:
                    brewery = matches[0].strip()
                    if 2 <= len(brewery) <= 30:
                        common_words = ['ipa', 'ale', 'lager', 'stout', 'porter', 'pilsner', 'wheat', 'sour', 'ml', 'л']
                        if brewery.upper() not in [w.upper() for w in common_words]:
                            breweries.add(brewery)
                            found_in_quotes = True
                            break
            if found_in_quotes:
                continue
            
            # 2. Слово в верхнем регистре до скобки
            match = re.match(r'^([A-ZА-ЯЁ][A-ZА-ЯЁ\s]+?)\s*\(', name)
            if match:
                brewery = match.group(1).strip()
                if 2 <= len(brewery) <= 50:
                    breweries.add(brewery)
                    continue
            
            # 3. Несколько слов в верхнем регистре
            match = re.match(r'^([A-ZА-ЯЁ][A-ZА-ЯЁ\s]{2,50}?)(?:\s+[a-zа-яё]|\s*\(|\s*$)', name)
            if match:
                brewery = match.group(1).strip()
                word_count = len(brewery.split())
                if 1 <= word_count <= 5 and 2 <= len(brewery) <= 50:
                    breweries.add(brewery)
                    continue
            
            # 4. Одно слово в верхнем регистре
            match = re.match(r'^([A-ZА-ЯЁ][A-ZА-ЯЁ]{2,30})\s+', name)
            if match:
                brewery = match.group(1).strip()
                common_words = ['IPA', 'ALE', 'LAGER', 'STOUT', 'PORTER', 'PILSNER']
                if brewery.upper() not in common_words:
                    breweries.add(brewery)
        
        return list(breweries)
    
    def _analyze_filename_hints(self, file_name: str = None, sheet_name: str = None) -> Dict:
        """
        Анализирует имя файла и листа на наличие подсказок о типе поставщика.
        
        Args:
            file_name: Имя файла (может быть полный путь или только имя)
            sheet_name: Имя листа
            
        Returns:
            Словарь с подсказками о типе поставщика
        """
        hints = {}
        text_to_check = ''
        
        # Извлекаем только имя файла из пути (если передан полный путь)
        if file_name:
            # Берем только имя файла без расширения
            import os
            file_basename = os.path.basename(file_name)
            file_name_only = os.path.splitext(file_basename)[0]
            text_to_check += ' ' + file_name_only.lower()
        
        if sheet_name:
            text_to_check += ' ' + sheet_name.lower()
        
        if not text_to_check:
            return hints
        
        # Ключевые слова для дистрибьютора
        distributor_keywords = [
            'дистрибьютор', 'distributor', 'каталог', 'catalog', 
            'прайс', 'price', 'поставщик', 'supplier', 'оптовый',
            'wholesale', 'импортер', 'importer', 'дистриб', 'distrib'
        ]
        
        # Ключевые слова для пивоварни (названия известных пивоварен и общие термины)
        brewery_keywords = [
            'brewery', 'пивоварня', 'brewing', 'пивоварение',
            'paradox', 'alisperi', 'back to balance', 'two peaks',
            'otherlab', 'incider'
        ]
        
        has_distributor_hint = any(kw in text_to_check for kw in distributor_keywords)
        has_brewery_hint = any(kw in text_to_check for kw in brewery_keywords)
        
        if has_distributor_hint and not has_brewery_hint:
            hints['filename_hint'] = 'distributor'
            logger.debug(f"Найдена подсказка дистрибьютора в имени файла/листа: {text_to_check}")
        elif has_brewery_hint:
            hints['filename_hint'] = 'brewery'
            logger.debug(f"Найдена подсказка пивоварни в имени файла/листа: {text_to_check}")
            
            # Пытаемся извлечь название пивоварни из имени файла
            # Ищем слова с большой буквы (возможные названия пивоварен)
            source_text = file_name or sheet_name or ''
            brewery_match = re.search(r'\b([A-ZА-ЯЁ][a-zа-яё]+(?:\s+[A-ZА-ЯЁ][a-zа-яё]+)?)\b', 
                                     source_text, re.IGNORECASE)
            if brewery_match:
                potential_brewery = brewery_match.group(1)
                # Проверяем, что это не служебное слово
                service_words = ['excel', 'xlsx', 'xls', 'sheet', 'лист', 'прайс', 'price', 
                               'актуальный', 'actual', 'price list', 'прайс-лист']
                if potential_brewery.lower() not in service_words:
                    hints['filename_brewery'] = potential_brewery
                    logger.debug(f"Извлечено название пивоварни из имени файла: {potential_brewery}")
        
        return hints
    
    def _check_brewery_diversity(self, df: pd.DataFrame, sample_rows: pd.DataFrame) -> SupplierType:
        """
        Проверяет разнообразие пивоварен в данных.
        
        Args:
            df: DataFrame с данными
            sample_rows: Первые строки для анализа
            
        Returns:
            Тип поставщика
        """
        # Ищем колонку с пивоварнями (проверяем больше строк для надежности)
        try:
            # Увеличиваем размер выборки для анализа
            analysis_rows = df.head(min(50, len(df)))
            
            for col_idx in range(min(10, len(df.columns))):
                try:
                    if col_idx >= len(analysis_rows.columns):
                        continue
                    
                    # Проверяем заголовок колонки
                    col_header = str(df.columns[col_idx]).lower() if col_idx < len(df.columns) else ''
                    brewery_indicators = ['пивоварня', 'brewery', 'производитель', 'manufacturer', 'бренд', 'brand']
                    is_brewery_column = any(indicator in col_header for indicator in brewery_indicators)
                    
                    # Если это колонка brewery или похожая, анализируем содержимое
                    if is_brewery_column or col_idx == 0:  # Также проверяем первую колонку
                        col_data = analysis_rows.iloc[:, col_idx].dropna().astype(str).tolist()
                        if col_data:
                            # Фильтруем пустые значения и служебные символы
                            unique_values = set(
                                v.strip() for v in col_data 
                                if v.strip() and v.strip().lower() not in ['-', '—', 'nan', 'none', '', 'null']
                            )
                            
                            # Если найдено более 1 уникального значения - это дистрибьютор
                            if len(unique_values) > 1:
                                logger.debug(f"Найдено {len(unique_values)} уникальных пивоварен в колонке {col_idx}: {list(unique_values)[:5]}")
                                return SupplierType.DISTRIBUTOR
                            # Если только одно значение и оно заполнено - это пивоварня
                            elif len(unique_values) == 1:
                                brewery_name = list(unique_values)[0]
                                logger.debug(f"Найдена одна пивоварня в колонке {col_idx}: {brewery_name}")
                                return SupplierType.BREWERY
                except Exception as e:
                    logger.debug(f"Ошибка при проверке колонки {col_idx}: {str(e)}")
                    continue
        except Exception as e:
            logger.warning(f"Ошибка при проверке разнообразия пивоварен: {str(e)}", exc_info=True)
        
        return SupplierType.UNKNOWN


class DistributorProfile:
    """
    Профиль парсинга для дистрибьютора (много пивоварен).
    
    Особенности:
    - Обычно есть отдельная колонка пивоварни или пивоварня в начале названия
    - Много разных пивоварен в одном файле
    - Структура может быть более стандартизированной
    """
    
    def get_column_mapping_strategy(self, df: pd.DataFrame, 
                                   characteristics: Dict) -> Dict[str, int]:
        """
        Возвращает стратегию маппинга колонок для дистрибьютора.
        
        Args:
            df: DataFrame с данными
            characteristics: Характеристики структуры
            
        Returns:
            Маппинг колонок
        """
        mapping = {}
        sample_rows = df.head(min(20, len(df)))
        
        # Стратегия 1: Ищем колонку пивоварни отдельно
        if characteristics.get('has_brewery_column'):
            for col_idx in range(len(df.columns)):
                col_header = str(df.columns[col_idx]).lower()
                if any(ind in col_header for ind in ['пивоварня', 'brewery', 'производитель']):
                    mapping['brewery'] = col_idx
                    break
        
        # Стратегия 2: Пивоварня в начале названия
        if 'brewery' not in mapping and characteristics.get('brewery_in_name_column'):
            # Найдем колонку с названиями
            for col_idx in range(len(df.columns)):
                try:
                    col_data = sample_rows.iloc[:, col_idx].dropna().astype(str).tolist()
                    if col_data:
                        avg_len = sum(len(str(v)) for v in col_data[:5]) / min(5, len(col_data))
                        if avg_len > 20:
                            mapping['beer_name'] = col_idx
                            # Пивоварня будет извлекаться из названия
                            break
                except Exception:
                    continue
        
        # Стратегия 3: Стандартные колонки по позиции и содержимому
        # (будет дополнено в основном парсере)
        
        return mapping


class BreweryProfile:
    """
    Профиль парсинга для конкретной пивоварни.
    
    Особенности:
    - Одна пивоварня во всем файле
    - Пивоварня может отсутствовать в данных (все позиции от одной пивоварни)
    - Структура может быть менее стандартизированной
    """
    
    def __init__(self, brewery_name: Optional[str] = None):
        """
        Инициализация профиля пивоварни.
        
        Args:
            brewery_name: Название пивоварни (если известно)
        """
        self.brewery_name = brewery_name
    
    def get_column_mapping_strategy(self, df: pd.DataFrame,
                                   characteristics: Dict) -> Dict[str, int]:
        """
        Возвращает стратегию маппинга колонок для пивоварни.
        
        Args:
            df: DataFrame с данными
            characteristics: Характеристики структуры
            
        Returns:
            Маппинг колонок
        """
        mapping = {}
        sample_rows = df.head(min(20, len(df)))
        
        # Для пивоварни пивоварня может отсутствовать в колонках
        # Все позиции автоматически получат название пивоварни
        
        # Ищем колонку с названиями (обычно первая длинная текстовая)
        for col_idx in range(min(5, len(df.columns))):
            try:
                col_data = sample_rows.iloc[:, col_idx].dropna().astype(str).tolist()
                if col_data:
                    avg_len = sum(len(str(v)) for v in col_data[:5]) / min(5, len(col_data))
                    if avg_len > 15:
                        mapping['beer_name'] = col_idx
                        break
            except Exception:
                continue
        
        # Ищем колонку со стилем (обычно вторая или рядом с названием)
        for col_idx in range(min(5, len(df.columns))):
            if col_idx in mapping.values():
                continue
            try:
                col_data = sample_rows.iloc[:, col_idx].dropna().astype(str).tolist()
                if col_data:
                    avg_len = sum(len(str(v)) for v in col_data[:5]) / min(5, len(col_data))
                    if 3 <= avg_len <= 50:
                        text_lower = ' '.join(col_data[:5]).lower()
                        style_keywords = ['ipa', 'lager', 'ale', 'stout', 'gose', 'sour', 'style', 'стиль']
                        if any(kw in text_lower for kw in style_keywords):
                            mapping['style'] = col_idx
                            break
            except Exception:
                continue
        
        return mapping
    
    def get_default_brewery_name(self) -> Optional[str]:
        """
        Возвращает название пивоварни по умолчанию.
        
        Returns:
            Название пивоварни или None
        """
        return self.brewery_name

