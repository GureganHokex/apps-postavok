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
        self.error_details = []
        self.warning_details = []
    
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
        self.error_details = []
        self.warning_details = []
        
        # Валидация цены
        self._validate_price(item)
        
        # Валидация объёма
        self._validate_volume(item)
        
        # Валидация крепости (ABV)
        self._validate_abv(item)

        # Валидация stock (если распознан как число)
        self._validate_stock(item)
        
        # Валидация обязательных полей
        self._validate_required_fields(item)
        
        # Проверка на подозрительные значения
        self._check_suspicious_values(item)
        
        is_valid = len(self.errors) == 0
        return is_valid, self.errors, self.warnings

    def _add_error(self, code: str, message: str, field_name: str):
        self.errors.append(message)
        self.error_details.append({
            'code': code,
            'message': message,
            # Каноничное имя поля
            'field_name': field_name,
            # Legacy alias для обратной совместимости
            'field': field_name,
            'severity': 'error',
        })

    def _add_warning(self, code: str, message: str, field_name: str):
        self.warnings.append(message)
        self.warning_details.append({
            'code': code,
            'message': message,
            'field_name': field_name,
            'field': field_name,
            'severity': 'warning',
        })
    
    def _validate_price(self, item: Dict):
        """Валидация цены."""
        price = item.get('price')
        if price is None or price == '':
            return  # Цена не обязательна
        
        try:
            price_val = float(price)
            
            if price_val < self.MIN_PRICE:
                self._add_error('price_negative', f"Цена отрицательная: {price_val} ₽", 'price')
            elif price_val > self.MAX_PRICE:
                self._add_warning('price_high', f"Цена подозрительно высокая: {price_val} ₽", 'price')
            elif price_val == 0:
                self._add_warning('price_zero', "Цена равна нулю", 'price')
        except (ValueError, TypeError):
            self._add_error('price_invalid', f"Некорректное значение цены: {price}", 'price')
    
    def _validate_volume(self, item: Dict):
        """Валидация объёма."""
        volume = item.get('volume')
        if volume is None or volume == '':
            return  # Объём не обязателен
        
        try:
            volume_val = float(volume)
            
            if volume_val < self.MIN_VOLUME:
                self._add_error('volume_negative', f"Объём отрицательный: {volume_val} л", 'volume')
            elif volume_val > self.MAX_VOLUME:
                self._add_warning('volume_high', f"Объём подозрительно большой: {volume_val} л", 'volume')
            elif volume_val == 0:
                self._add_warning('volume_zero', "Объём равен нулю", 'volume')
        except (ValueError, TypeError):
            self._add_error('volume_invalid', f"Некорректное значение объёма: {volume}", 'volume')
    
    def _validate_abv(self, item: Dict):
        """Валидация крепости (ABV)."""
        abv = item.get('abv')
        if abv is None or abv == '':
            return  # ABV не обязателен
        
        try:
            abv_val = float(abv)
            
            if abv_val < self.MIN_ABV:
                self._add_error('abv_negative', f"Крепость отрицательная: {abv_val}%", 'abv')
            elif abv_val > self.MAX_ABV:
                self._add_warning('abv_high', f"Крепость подозрительно высокая: {abv_val}%", 'abv')
            elif abv_val == 0:
                self._add_warning('abv_zero', "Крепость равна нулю", 'abv')
        except (ValueError, TypeError):
            self._add_error('abv_invalid', f"Некорректное значение крепости: {abv}", 'abv')

    def _validate_stock(self, item: Dict):
        """Валидация stock, если значение числовое."""
        stock = item.get('stock')
        if stock is None or stock == '':
            return
        try:
            stock_val = float(stock)
            if stock_val < 0:
                self._add_error('stock_negative', f"Остаток отрицательный: {stock_val}", 'stock')
        except (ValueError, TypeError):
            # Для нечисловых форматов (например "в наличии") ошибку не поднимаем.
            return
    
    def _validate_required_fields(self, item: Dict):
        """Проверка наличия минимальных данных."""
        beer_name = item.get('beer_name', '').strip()
        brewery = item.get('brewery', '').strip()
        
        if not beer_name and not brewery:
            self._add_warning('missing_beer_and_brewery', "Отсутствует название пива и пивоварня", 'beer_name')
        elif not beer_name:
            self._add_warning('missing_beer_name', "Отсутствует название пива", 'beer_name')
        elif not brewery:
            self._add_warning('missing_brewery', "Отсутствует пивоварня", 'brewery')
    
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
                        self._add_warning(
                            'price_per_liter_low',
                            f"Цена за литр подозрительно низкая: {price_per_liter:.2f} ₽/л",
                            'price',
                        )
                    elif price_per_liter > 10000:
                        self._add_warning(
                            'price_per_liter_high',
                            f"Цена за литр подозрительно высокая: {price_per_liter:.2f} ₽/л",
                            'price',
                        )
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
                'error_details': self.error_details.copy(),
                'warning_details': self.warning_details.copy(),
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
