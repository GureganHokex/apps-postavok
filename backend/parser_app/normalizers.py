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
        
        # Нормализация цены и валюты
        if 'price' in normalized:
            price_data = self.normalize_price(normalized.get('price', ''))
            if price_data:
                normalized['price'] = price_data.get('price')
                normalized['currency'] = price_data.get('currency', 'RUB')
                # Не перезаписываем volume из цены, если он уже был извлечен из формата
                if 'volume' in price_data and 'volume' not in normalized:
                    normalized['volume'] = price_data['volume']
        
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
        
        # Нормализация формата
        if 'format_type' in normalized:
            normalized['format_type'] = self.normalize_format_type(
                normalized['format_type']
            )
        
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

