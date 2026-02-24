"""
Модуль для дедупликации распарсенных позиций.

Удаляет дубликаты на основе ключевых полей:
- brewery, beer_name (нормализованное), style, format_type, price
"""

import re
import logging
from typing import List, Dict
from decimal import Decimal

logger = logging.getLogger(__name__)


class Deduplicator:
    """Дедупликация распарсенных позиций."""
    
    @staticmethod
    def normalize_description(desc: str, name: str) -> str:
        """
        Убирает название из начала описания для сравнения.
        
        Args:
            desc: Описание
            name: Название пива
            
        Returns:
            Нормализованное описание
        """
        if not desc or not name:
            return desc
        desc_lower = desc.lower()
        name_lower = name.lower()
        if desc_lower.startswith(name_lower):
            normalized = desc[len(name):].strip()
            normalized = re.sub(r'^[:\-\s]+', '', normalized)
            return normalized
        return desc
    
    @staticmethod
    def normalize_price(price_val) -> str:
        """
        Нормализует цену для сравнения (убирает различия в формате).
        
        Args:
            price_val: Значение цены
            
        Returns:
            Нормализованная строка цены
        """
        if price_val is not None:
            try:
                if isinstance(price_val, str):
                    price_val = float(price_val.replace(',', '.'))
                elif isinstance(price_val, Decimal):
                    price_val = float(price_val)
                return f"{float(price_val):.2f}"
            except (ValueError, TypeError):
                return str(price_val)
        return ''
    
    @staticmethod
    def normalize_beer_name(beer_name: str) -> str:
        """
        Нормализует название пива для сравнения.
        
        Args:
            beer_name: Название пива
            
        Returns:
            Нормализованное название (без скобок типа "(Fresh Brewed)")
        """
        if not beer_name:
            return ''
        beer_name_norm = beer_name.strip().lower()
        # Убираем варианты типа "(Fresh Brewed)", "(NEW)" из названия
        beer_name_base = re.sub(r'\s*\([^)]*\)\s*', '', beer_name_norm).strip()
        return beer_name_base
    
    @staticmethod
    def create_deduplication_key(item: Dict) -> tuple:
        """
        Создает ключ для дедупликации.
        
        Args:
            item: Словарь с данными позиции
            
        Returns:
            Кортеж с ключевыми полями для сравнения
        """
        beer_name_base = Deduplicator.normalize_beer_name(item.get('beer_name') or '')
        price_normalized = Deduplicator.normalize_price(item.get('price'))
        
        return (
            (item.get('brewery') or '').strip().lower(),
            beer_name_base,
            (item.get('style') or '').strip().lower(),
            (item.get('format_type') or '').strip().lower(),
            price_normalized
        )
    
    @staticmethod
    def deduplicate(items: List[Dict]) -> List[Dict]:
        """
        Удаляет дубликаты из списка позиций.
        
        Args:
            items: Список позиций для дедупликации
            
        Returns:
            Список без дубликатов
        """
        if not items:
            return []
        
        seen = {}
        deduplicated_items = []
        
        for item in items:
            key = Deduplicator.create_deduplication_key(item)
            
            if key not in seen:
                seen[key] = item
                deduplicated_items.append(item)
            else:
                # Если дубликат найден, выбираем вариант с более полным описанием
                existing = seen[key]
                current_name = (item.get('beer_name') or '').strip()
                existing_name = (existing.get('beer_name') or '').strip()
                current_desc = (item.get('description') or '').strip()
                existing_desc = (existing.get('description') or '').strip()
                
                # Нормализуем описания
                current_desc_norm = Deduplicator.normalize_description(current_desc, current_name)
                existing_desc_norm = Deduplicator.normalize_description(existing_desc, existing_name)
                
                # Предпочитаем вариант без "(Fresh Brewed)" или с нормализованным описанием
                if '(fresh' not in current_name.lower() and '(fresh' in existing_name.lower():
                    seen[key] = item
                    deduplicated_items[deduplicated_items.index(existing)] = item
                elif current_desc_norm == existing_desc_norm:
                    # Описания совпадают после нормализации - выбираем вариант БЕЗ названия в описании
                    current_desc_lower = current_desc.lower()
                    existing_desc_lower = existing_desc.lower()
                    current_name_lower = current_name.lower()
                    existing_name_lower = existing_name.lower()
                    if not current_desc_lower.startswith(current_name_lower) and existing_desc_lower.startswith(existing_name_lower):
                        seen[key] = item
                        deduplicated_items[deduplicated_items.index(existing)] = item
                    elif len(current_desc_norm) > len(existing_desc_norm):
                        seen[key] = item
                        deduplicated_items[deduplicated_items.index(existing)] = item
                elif len(current_desc_norm) > len(existing_desc_norm):
                    seen[key] = item
                    deduplicated_items[deduplicated_items.index(existing)] = item
        
        if len(deduplicated_items) < len(items):
            logger.info(f"Удалено {len(items) - len(deduplicated_items)} дубликатов из {len(items)} позиций")
        
        return deduplicated_items
