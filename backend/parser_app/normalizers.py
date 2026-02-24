"""
Нормализация данных о пиве.
"""

import re
from typing import Optional, Dict
from .utils import safe_float


class DataNormalizer:
    """
    Класс для нормализации данных о пиве.
    
    Приводит единицы измерения, валюты, форматы к стандартному виду.
    """
    
    # Соответствие валют
    CURRENCY_MAPPING = {
        'руб': 'RUB',
        'рублей': 'RUB',
        'рубль': 'RUB',
        'р.': 'RUB',
        'р': 'RUB',
        'usd': 'USD',
        'доллар': 'USD',
        'долларов': 'USD',
        'eur': 'EUR',
        'евро': 'EUR',
        '€': 'EUR',
        '$': 'USD',
    }
    
    # Соответствие единиц измерения
    VOLUME_UNITS = {
        'мл': 0.001,
        'ml': 0.001,
        'л': 1.0,
        'литр': 1.0,
        'литров': 1.0,
        'l': 1.0,
        'oz': 0.0295735,  # унции в литры
        'ounce': 0.0295735,
    }
    
    # Соответствие форматов (сохраняем русские названия для интерфейса)
    FORMAT_MAPPING = {
        'can': 'банка',
        'банка': 'банка',
        'bottle': 'бутылка',
        'бутылка': 'бутылка',
        'keg': 'кега',
        'кега': 'кега',
        'бут': 'бутылка',
        'б': 'бутылка',
    }
    
    def normalize_item(self, item: Dict) -> Dict:
        """
        Нормализует все поля позиции.
        
        Args:
            item: Словарь с данными позиции
            
        Returns:
            Нормализованный словарь
        """
        normalized = item.copy()
        
        # Нормализация крепости
        if 'abv' in normalized:
            normalized['abv'] = self.normalize_abv(normalized['abv'])
            # Если abv невалидно, устанавливаем в None
            if normalized['abv'] is not None:
                try:
                    float(normalized['abv'])
                except (ValueError, TypeError):
                    normalized['abv'] = None
        
        # Нормализация цены и валюты
        if 'price' in normalized:
            price_data = self.normalize_price(normalized.get('price', ''))
            if price_data and price_data.get('price') is not None:
                try:
                    # Проверяем, что price можно преобразовать в Decimal
                    from decimal import Decimal, InvalidOperation
                    price_val = price_data.get('price')
                    if price_val is not None:
                        normalized['price'] = Decimal(str(price_val))
                        normalized['currency'] = price_data.get('currency', 'RUB')
                        # Не перезаписываем volume из цены, если он уже был извлечен из формата
                        if 'volume' in price_data and 'volume' not in normalized:
                            normalized['volume'] = price_data['volume']
                    else:
                        normalized['price'] = None
                except (ValueError, TypeError, InvalidOperation):
                    normalized['price'] = None
            else:
                normalized['price'] = None
        
        # Нормализация валюты отдельно
        if 'currency' in normalized:
            normalized['currency'] = self.normalize_currency(
                normalized['currency']
            )
        
        # Нормализация объёма
        if 'volume' in normalized and normalized['volume'] is not None:
            # Если volume уже число, сохраняем как есть
            if isinstance(normalized['volume'], (int, float)):
                normalized['volume'] = float(normalized['volume'])
            else:
                normalized['volume'] = self.normalize_volume(
                    normalized.get('volume', '')
                )
            # Если volume невалидно, устанавливаем в None
            if normalized['volume'] is not None:
                try:
                    float(normalized['volume'])
                except (ValueError, TypeError):
                    normalized['volume'] = None
        
        # Нормализация формата
        if 'format_type' in normalized:
            normalized['format_type'] = self.normalize_format_type(
                normalized['format_type']
            )
        
        # Нормализация пивоварни (удаление города)
        # ВАЖНО: Сохраняем оригинальное значение brewery, если нормализация его удалила
        original_brewery = normalized.get('brewery', '')
        if 'brewery' in normalized and normalized['brewery']:
            normalized_brewery = self.normalize_brewery(normalized['brewery'])
            # Если нормализация удалила brewery (вернула пустую строку),
            # но оригинальное значение было не пустым - используем оригинал
            if not normalized_brewery and original_brewery:
                # Проверяем, не является ли оригинальное значение только городом
                # Если нет - используем оригинал
                original_lower = str(original_brewery).lower().strip()
                city_names = ['владимир', 'москва', 'санкт-петербург', 'спб', 'мск', 'moscow', 'spb']
                if original_lower not in city_names and not original_lower.startswith(('г.', 'г ')):
                    normalized['brewery'] = str(original_brewery).strip()
                else:
                    normalized['brewery'] = ''
            else:
                normalized['brewery'] = normalized_brewery
        
        return normalized
    
    def normalize_abv(self, abv_value) -> Optional[float]:
        """
        Нормализует крепость пива.
        
        Args:
            abv_value: Значение крепости (строка или число)
            
        Returns:
            Float значение крепости или None
        """
        if abv_value is None:
            return None
        
        if isinstance(abv_value, (int, float)):
            return float(abv_value)
        
        # Преобразуем строку
        abv_str = str(abv_value).strip()
        
        # Удаляем знак процента
        abv_str = abv_str.replace('%', '').strip()
        
        # Заменяем запятую на точку
        abv_str = abv_str.replace(',', '.')
        
        # Извлекаем число
        match = re.search(r'(\d+\.?\d*)', abv_str)
        if match:
            return safe_float(match.group(1))
        
        return None
    
    def normalize_price(self, price_value) -> Optional[Dict]:
        """
        Нормализует цену и извлекает валюту и объём.
        
        Обрабатывает форматы типа "150 руб (0,5 л)" или "500 за банку".
        
        Args:
            price_value: Значение цены (строка или число)
            
        Returns:
            Словарь с ключами: price, currency, volume или None
        """
        if price_value is None:
            return None
        
        if isinstance(price_value, (int, float)):
            return {'price': float(price_value), 'currency': 'RUB'}
        
        price_str = str(price_value).strip()
        
        # Извлекаем число (цену)
        price_match = re.search(r'(\d+[\.,]?\d*)', price_str)
        if not price_match:
            return None
        
        price = safe_float(price_match.group(1).replace(',', '.'))
        if price is None:
            return None
        
        result = {'price': price}
        
        # Определяем валюту
        currency = self._extract_currency(price_str)
        if currency:
            result['currency'] = currency
        
        # Извлекаем объём из строки типа "(0,5 л)" или "0.5L"
        volume = self._extract_volume_from_price(price_str)
        if volume:
            result['volume'] = volume
        
        return result
    
    def _extract_currency(self, text: str) -> Optional[str]:
        """
        Извлекает валюту из текста.
        
        Args:
            text: Текст для анализа
            
        Returns:
            Код валюты или None
        """
        text_lower = text.lower()
        for key, value in self.CURRENCY_MAPPING.items():
            if key in text_lower:
                return value
        return 'RUB'  # По умолчанию рубли
    
    def _extract_volume_from_price(self, text: str) -> Optional[float]:
        """
        Извлекает объём из строки цены.
        
        Args:
            text: Текст для анализа
            
        Returns:
            Объём в литрах или None
        """
        # Паттерны типа "(0,5 л)", "0.5L", "500ml"
        patterns = [
            r'\((\d+[\.,]?\d*)\s*(мл|л|ml|l|литр|литров)',
            r'(\d+[\.,]?\d*)\s*(мл|л|ml|l|литр|литров)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                volume_value = safe_float(match.group(1).replace(',', '.'))
                unit = match.group(2).lower()
                
                if volume_value and unit in self.VOLUME_UNITS:
                    multiplier = self.VOLUME_UNITS[unit]
                    return volume_value * multiplier
        
        return None
    
    def normalize_currency(self, currency_value) -> str:
        """
        Нормализует валюту.
        
        Args:
            currency_value: Значение валюты
            
        Returns:
            Стандартный код валюты
        """
        if not currency_value:
            return 'RUB'
        
        currency_str = str(currency_value).lower().strip()
        return self.CURRENCY_MAPPING.get(currency_str, 'RUB')
    
    def normalize_volume(self, volume_value) -> Optional[float]:
        """
        Нормализует объём в литры.
        
        Args:
            volume_value: Значение объёма (строка или число)
            
        Returns:
            Объём в литрах или None
        """
        if volume_value is None:
            return None
        
        if isinstance(volume_value, (int, float)):
            return float(volume_value)
        
        volume_str = str(volume_value).strip()
        
        # Извлекаем число и единицу измерения
        match = re.search(r'(\d+[\.,]?\d*)\s*([а-яa-z]+)?', volume_str, re.IGNORECASE)
        if match:
            value = safe_float(match.group(1).replace(',', '.'))
            unit = match.group(2).lower() if match.group(2) else 'л'
            
            if value and unit in self.VOLUME_UNITS:
                multiplier = self.VOLUME_UNITS[unit]
                return value * multiplier
        
        # Если единица не указана, предполагаем литры
        return safe_float(volume_str.replace(',', '.'))
    
    def normalize_format_type(self, format_value) -> str:
        """
        Нормализует формат упаковки.
        
        Args:
            format_value: Значение формата
            
        Returns:
            Стандартизированное значение формата
        """
        if not format_value:
            return ''
        
        format_str = str(format_value).lower().strip()
        return self.FORMAT_MAPPING.get(format_str, format_str)
    
    def normalize_brewery(self, brewery_value) -> str:
        """
        Нормализует название пивоварни, удаляя информацию о городе.
        
        Args:
            brewery_value: Название пивоварни
            
        Returns:
            Очищенное название пивоварни без города
        """
        if not brewery_value:
            return ''
        
        brewery_str = str(brewery_value).strip()
        original_str = brewery_str
        
        # Паттерны для удаления города и адреса
        # Удаляем информацию о городе в различных форматах
        # Сначала удаляем конкретные города, потом общие паттерны
        city_patterns = [
            # Конкретные города (более специфичные паттерны сначала)
            r'\s*г\.\s*Санкт-Петербург[а-яё]*',
            r'\s*г\s+Санкт-Петербург[а-яё]*',
            r'\s*Санкт-Петербург[а-яё]*',
            r'\s*СПб',
            r'\s*spb',
            r'\s*г\.\s*Москв[а-яё]*',
            r'\s*г\s+Москв[а-яё]*',
            r'\s*Москв[а-яё]*',
            r'\s*мск',
            r'\s*msk',
            r'\s*г\.\s*Владимир[а-яё]*',
            r'\s*г\s+Владимир[а-яё]*',
            r'\s*Владимир[а-яё]*',
            # Общие паттерны (после конкретных)
            r'\s*г\.\s*[А-ЯЁа-яё\s-]+',  # "г. Санкт-Петербург", "г. Владимир"
            r'\s*г\s+[А-ЯЁа-яё\s-]+',  # "г Санкт-Петербург", "г Владимир"
            r'\s*город\s+[А-ЯЁа-яё\s-]+',  # "город Москва", "город Владимир"
            r'\s*city\s+[А-ЯЁа-яёA-Za-z\s-]+',  # "city Moscow"
            r'\s*,\s*г\.\s*[А-ЯЁа-яё\s-]+',  # ", г. Санкт-Петербург", ", г. Владимир"
            r'\s*,\s*г\s+[А-ЯЁа-яё\s-]+',  # ", г Санкт-Петербург", ", г Владимир"
            r'\s*,\s*город\s+[А-ЯЁа-яё\s-]+',  # ", город Москва", ", город Владимир"
            r'\s*,\s*city\s+[А-ЯЁа-яёA-Za-z\s-]+',  # ", city Moscow"
        ]
        
        # Удаляем паттерны города (повторяем несколько раз для надежности)
        # Используем цикл для удаления всех вхождений
        max_iterations = 5  # Максимум 5 итераций для предотвращения бесконечного цикла
        iteration = 0
        previous_str = brewery_str
        
        while iteration < max_iterations:
            for pattern in city_patterns:
                brewery_str = re.sub(pattern, '', brewery_str, flags=re.IGNORECASE)
            
            # Если строка не изменилась, выходим из цикла
            if brewery_str == previous_str:
                break
            previous_str = brewery_str
            iteration += 1
        
        # Удаляем лишние пробелы и запятые в начале/конце
        brewery_str = brewery_str.strip().rstrip(',').strip()
        
        # Удаляем множественные пробелы
        brewery_str = re.sub(r'\s+', ' ', brewery_str)
        
        # Дополнительная проверка: если после нормализации остался только город или пустая строка
        # Пытаемся найти название пивоварни до города
        if not brewery_str or len(brewery_str.strip()) < 2:
            # Возвращаем исходную строку, но пытаемся удалить только явные паттерны города
            brewery_str = original_str
            # Удаляем только явные паттерны "г. Город" в конце строки
            brewery_str = re.sub(r'\s*г\.\s*[А-ЯЁа-яё]+[а-яё]*\s*$', '', brewery_str, flags=re.IGNORECASE)
            brewery_str = re.sub(r'\s*г\s+[А-ЯЁа-яё]+[а-яё]*\s*$', '', brewery_str, flags=re.IGNORECASE)
            brewery_str = brewery_str.strip()
        
        # Финальная проверка: если после всех операций остался только город (без других слов)
        # Проверяем, не является ли вся строка названием города
        city_names = ['владимир', 'москва', 'санкт-петербург', 'спб', 'мск', 'moscow', 'spb']
        brewery_lower = brewery_str.lower().strip()
        if brewery_lower in city_names or brewery_lower.startswith('г.') or brewery_lower.startswith('г '):
            # Если это только город, возвращаем пустую строку
            return ''
        
        return brewery_str

