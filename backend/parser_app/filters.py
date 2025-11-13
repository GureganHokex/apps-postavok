"""
Фильтрация контактов и служебных данных из прайсов.
"""

import re
from typing import List, Dict, Tuple


class ContactFilter:
    """
    Класс для фильтрации контактов и служебных данных.
    
    Определяет, является ли строка контактной информацией
    или служебным текстом, а не товарной позицией.
    """
    
    # Регулярные выражения для определения контактов
    PHONE_PATTERNS = [
        r'\+?[0-9]{1,3}[-.\s]?\(?[0-9]{1,4}\)?[-.\s]?[0-9]{1,4}[-.\s]?[0-9]{1,9}',
        r'\+?7[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{2}[-.\s]?[0-9]{2}',
        r'\+?375[-.\s]?\(?[0-9]{2}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{2}[-.\s]?[0-9]{2}',
    ]
    
    EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    
    URL_PATTERNS = [
        r'https?://[^\s]+',
        r'www\.[^\s]+',
        r'[a-zA-Z0-9-]+\.[a-zA-Z]{2,}[^\s]*',
    ]
    
    # Ключевые слова для служебных строк
    SERVICE_KEYWORDS = [
        'прайс', 'price list', 'прайс-лист', 'каталог',
        'менеджер', 'manager', 'контакт', 'contact',
        'телефон', 'phone', 'тел.', 'тел:', 'т.+',
        'email', 'e-mail', 'почта', 'mail',
        'адрес', 'address', 'ул.', 'улица', 'street',
        'акция', 'скидка', 'sale', 'discount',
        'новинка', 'new', 'новое',
        'цены без', 'цена без', 'без ндс', 'без ндс',
        'доставка', 'delivery',
        'инн', 'огрн', 'р/с', 'банк',
        'instagram', 'instagram.com', 'vk.com', 'facebook',
        'соцсети', 'social',
        'г.', 'г ', 'город', 'city',  # Адреса
        'владимир', 'москва', 'санкт-петербург', 'spb', 'мск',  # Города
    ]
    
    def __init__(self):
        """Инициализация фильтра."""
        self.phone_regex = re.compile('|'.join(self.PHONE_PATTERNS))
        self.email_regex = re.compile(self.EMAIL_PATTERN)
        self.url_regex = re.compile('|'.join(self.URL_PATTERNS))
    
    def filter_row(self, row_data: Dict, row_text: str = '') -> Tuple[bool, Dict]:
        """
        Определяет, является ли строка товарной позицией или служебной.
        
        Args:
            row_data: Данные строки (словарь с полями)
            row_text: Текст строки для анализа
            
        Returns:
            Tuple (is_product_row, extracted_contacts)
            - is_product_row: True если это товарная позиция
            - extracted_contacts: Словарь с найденными контактами
        """
        # Если нет текста, собираем из данных
        if not row_text:
            row_text = ' '.join(str(v) for v in row_data.values() if v)
        
        row_text_lower = row_text.lower()
        
        # Извлекаем контакты
        contacts = self._extract_contacts(row_text)
        
        # Проверяем служебные ключевые слова
        has_service_keywords = any(
            keyword in row_text_lower for keyword in self.SERVICE_KEYWORDS
        )
        
        # Проверяем наличие данных о товаре
        has_product_data = (
            row_data.get('beer_name') or 
            row_data.get('brewery') or
            row_data.get('price')
        )
        
        # Проверяем наличие цены - это важный индикатор товарной строки
        has_price = bool(row_data.get('price'))
        
        # Проверяем наличие названия пива или других товарных данных
        has_beer_name = bool(row_data.get('beer_name'))
        has_style = bool(row_data.get('style'))
        
        # Если есть только brewery без других данных - это может быть заголовок секции
        only_brewery = (
            row_data.get('brewery') and 
            not row_data.get('beer_name') and 
            not row_data.get('price') and
            not row_data.get('style')
        )
        
        # Если найдены контакты или служебные ключевые слова
        if contacts or has_service_keywords:
            # Если есть и товарные данные, и контакты - это может быть строка с товаром
            # Но если только контакты/служебное - это служебная строка
            if not has_product_data:
                return False, contacts
        
        # Если только brewery без других данных - это заголовок секции
        if only_brewery:
            # Проверяем, содержит ли brewery адресные данные
            brewery_text = str(row_data.get('brewery', '')).lower()
            address_indicators = ['г.', 'г ', 'город', 'city', 'ул.', 'улица']
            has_address_in_brewery = any(indicator in brewery_text for indicator in address_indicators)
            
            if has_address_in_brewery or not has_beer_name:
                return False, contacts
        
        # Если нет товарных данных, но есть контакты - это служебная строка
        if not has_product_data and contacts:
            return False, contacts
        
        return True, contacts
    
    def _extract_contacts(self, text: str) -> Dict:
        """
        Извлекает контакты из текста.
        
        Args:
            text: Текст для анализа
            
        Returns:
            Словарь с найденными контактами:
            {'phones': [], 'emails': [], 'addresses': [], 'links': []}
        """
        contacts = {
            'phones': [],
            'emails': [],
            'addresses': [],
            'links': []
        }
        
        # Извлекаем телефоны
        phones = self.phone_regex.findall(text)
        contacts['phones'] = [p.strip() for p in phones if p.strip()]
        
        # Извлекаем email
        emails = self.email_regex.findall(text)
        contacts['emails'] = [e.strip() for e in emails if e.strip()]
        
        # Извлекаем URL
        urls = self.url_regex.findall(text)
        contacts['links'] = [u.strip() for u in urls if u.strip()]
        
        # Определяем адреса (простая эвристика)
        addresses = self._extract_addresses(text)
        contacts['addresses'] = addresses
        
        return contacts
    
    def _extract_addresses(self, text: str) -> List[str]:
        """
        Извлекает адреса из текста (эвристика).
        
        Args:
            text: Текст для анализа
            
        Returns:
            Список найденных адресов
        """
        addresses = []
        
        # Паттерны для адресов
        address_patterns = [
            r'ул\.\s*[^,\n]+',
            r'улица\s+[^,\n]+',
            r'пр\.\s*[^,\n]+',
            r'проспект\s+[^,\n]+',
            r'г\.\s*[^,\n]+',
            r'город\s+[^,\n]+',
        ]
        
        for pattern in address_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            addresses.extend([m.strip() for m in matches])
        
        return addresses
    
    def extract_extra_text(self, text: str) -> List[str]:
        """
        Извлекает служебные тексты из строки.
        
        Args:
            text: Текст для анализа
            
        Returns:
            Список служебных текстов
        """
        extra_texts = []
        text_lower = text.lower()
        
        # Проверяем наличие служебных фраз
        service_phrases = [
            'цены без ндс',
            'без ндс',
            'цена указана без ндс',
            'акция',
            'новинка',
            'скидка',
            'специальное предложение',
        ]
        
        for phrase in service_phrases:
            if phrase in text_lower:
                extra_texts.append(phrase)
        
        return extra_texts

