"""
Валидаторы для проверки корректности данных после парсинга.
"""

import logging
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ParsedItemValidator:
    """
    Класс для валидации распарсенных позиций.
    
    Проверяет корректность цен, объёмов, крепости и других полей.
    """
    
    # Разумные диапазоны для валидации
    MIN_PRICE = 0
    MAX_PRICE = 100000  # 100000 рублей максимум
    MIN_VOLUME = 0
    MAX_VOLUME = 100  # 100 литров максимум
    MIN_ABV = 0
    MAX_ABV = 20  # 20% максимум крепости
    
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def validate_item(self, item: Dict):
        """
        Валидирует одну позицию.
        
        Args:
            item: Словарь с данными позиции
            
        Returns:
            Tuple (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []
        
        # Валидация цены
        self._validate_price(item)
        
        # Валидация объёма
        self._validate_volume(item)
        
        # Валидация крепости (ABV)
        self._validate_abv(item)
        
        # Валидация обязательных полей
        self._validate_required_fields(item)
        
        # Проверка на подозрительные значения
        self._check_suspicious_values(item)
        
        is_valid = len(self.errors) == 0
        return is_valid, self.errors, self.warnings
    
    def _validate_price(self, item: Dict):
        """Валидация цены."""
        price = item.get('price')
        if price is None or price == '':
            return  # Цена не обязательна
        
        try:
            price_val = float(price)
            
            if price_val < self.MIN_PRICE:
                self.errors.append(f"Цена отрицательная: {price_val} ₽")
            elif price_val > self.MAX_PRICE:
                self.warnings.append(f"Цена подозрительно высокая: {price_val} ₽")
            elif price_val == 0:
                self.warnings.append("Цена равна нулю")
        except (ValueError, TypeError):
            self.errors.append(f"Некорректное значение цены: {price}")
    
    def _validate_volume(self, item: Dict):
        """Валидация объёма."""
        volume = item.get('volume')
        if volume is None or volume == '':
            return  # Объём не обязателен
        
        try:
            volume_val = float(volume)
            
            if volume_val < self.MIN_VOLUME:
                self.errors.append(f"Объём отрицательный: {volume_val} л")
            elif volume_val > self.MAX_VOLUME:
                self.warnings.append(f"Объём подозрительно большой: {volume_val} л")
            elif volume_val == 0:
                self.warnings.append("Объём равен нулю")
        except (ValueError, TypeError):
            self.errors.append(f"Некорректное значение объёма: {volume}")
    
    def _validate_abv(self, item: Dict):
        """Валидация крепости (ABV)."""
        abv = item.get('abv')
        if abv is None or abv == '':
            return  # ABV не обязателен
        
        try:
            abv_val = float(abv)
            
            if abv_val < self.MIN_ABV:
                self.errors.append(f"Крепость отрицательная: {abv_val}%")
            elif abv_val > self.MAX_ABV:
                self.warnings.append(f"Крепость подозрительно высокая: {abv_val}%")
            elif abv_val == 0:
                self.warnings.append("Крепость равна нулю")
        except (ValueError, TypeError):
            self.errors.append(f"Некорректное значение крепости: {abv}")
    
    def _validate_required_fields(self, item: Dict):
        """Проверка наличия минимальных данных."""
        beer_name = item.get('beer_name', '').strip()
        brewery = item.get('brewery', '').strip()
        
        if not beer_name and not brewery:
            self.warnings.append("Отсутствует название пива и пивоварня")
        elif not beer_name:
            self.warnings.append("Отсутствует название пива")
        elif not brewery:
            self.warnings.append("Отсутствует пивоварня")
    
    def _check_suspicious_values(self, item: Dict):
        """Проверка на подозрительные значения."""
        price = item.get('price')
        volume = item.get('volume')
        
        # Проверка соотношения цена/объём
        if price and volume:
            try:
                price_val = float(price)
                volume_val = float(volume)
                
                if volume_val > 0:
                    price_per_liter = price_val / volume_val
                    # Нормальный диапазон: 100-5000 руб/л
                    if price_per_liter < 50:
                        self.warnings.append(f"Цена за литр подозрительно низкая: {price_per_liter:.2f} ₽/л")
                    elif price_per_liter > 10000:
                        self.warnings.append(f"Цена за литр подозрительно высокая: {price_per_liter:.2f} ₽/л")
            except (ValueError, TypeError):
                pass
    
    def validate_batch(self, items: List[Dict]) -> Dict:
        """
        Валидация множества позиций.
        
        Args:
            items: Список позиций для валидации
            
        Returns:
            Словарь со статистикой валидации
        """
        valid_count = 0
        invalid_count = 0
        total_errors = 0
        total_warnings = 0
        item_results = []
        
        for idx, item in enumerate(items):
            is_valid, errors, warnings = self.validate_item(item)
            
            if is_valid:
                valid_count += 1
            else:
                invalid_count += 1
            
            total_errors += len(errors)
            total_warnings += len(warnings)
            
            item_results.append({
                'index': idx,
                'is_valid': is_valid,
                'errors': errors,
                'warnings': warnings,
                'beer_name': item.get('beer_name', 'Не указано'),
                'brewery': item.get('brewery', 'Не указано'),
            })
        
        return {
            'total': len(items),
            'valid': valid_count,
            'invalid': invalid_count,
            'total_errors': total_errors,
            'total_warnings': total_warnings,
            'results': item_results,
        }
