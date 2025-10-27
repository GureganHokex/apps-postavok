"""Анализатор типов пива."""

from typing import Optional, List
import re


class BeerAnalyzer:
    """Анализирует и определяет стили пива.

    Определяет стили пива по названию используя ключевые слова
    и паттерны.
    """

    # Словарь стилей пива и их ключевых слов
    BEER_STYLES = {
        'IPA': ['ipa', 'индийск', 'pale ale', 'apa', 'хмель'],
        'Lager': ['lager', 'лагер', 'pilsner', 'пилсн', 'helles'],
        'Stout': ['stout', 'стаут', 'porter', 'портер'],
        'Wheat': ['wheat', 'weizen', 'белое', 'вит', 'пшеничн'],
        'Sour': ['sour', 'кисл', 'gose', 'berliner'],
        'Pale Ale': ['pale ale', 'pale', 'светл'],
        'Dark': ['dark', 'темн', 'черн', 'dunkel'],
        'Hazy IPA': ['hazy', 'нефильтр', 'мутн'],
    }

    # Общие ключевые слова для пива
    BEER_KEYWORDS = ['пиво', 'beer', 'бир', 'ale']

    @staticmethod
    def detect_style(name: str) -> Optional[str]:
        """Определить стиль пива по названию.

        Args:
            name: Название пива

        Returns:
            Название стиля или None
        """
        name_lower = name.lower()

        # Проверяем каждый стиль
        for style, keywords in BeerAnalyzer.BEER_STYLES.items():
            for keyword in keywords:
                if keyword in name_lower:
                    return style

        return None

    @staticmethod
    def is_beer(text: str) -> bool:
        """Проверить, является ли текст названием пива.

        Args:
            text: Текст для проверки

        Returns:
            True если вероятно это пиво
        """
        text_lower = text.lower()

        # Проверка на ключевые слова пива
        for keyword in BeerAnalyzer.BEER_KEYWORDS:
            if keyword in text_lower:
                return True

        # Проверка на наличие стилей в тексте
        for style, keywords in BeerAnalyzer.BEER_STYLES.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return True

        return False

    @staticmethod
    def extract_brewery(name: str) -> Optional[str]:
        """Извлечь название пивоварни из полного названия.

        Args:
            name: Полное название пива

        Returns:
            Название пивоварни или None
        """
        # Простая эвристика: первое слово до пробела/тире
        parts = re.split(r'[\s\-]+', name.strip())

        if len(parts) > 1:
            # Возвращаем первые 1-2 слова как пивоварню
            if len(parts[0]) > 3:  # Игнорируем артикли
                return parts[0]

        return None
