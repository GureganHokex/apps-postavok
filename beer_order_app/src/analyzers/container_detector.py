"""Детектор типа тары и объема."""

import re
from typing import Optional, Tuple


class ContainerDetector:
    """Определяет тип тары и объем.

    Распознает кеги, банки, бутылки и извлекает объем.
    """

    # Ключевые слова для распознавания типа тары
    KEG_KEYWORDS = ['кег', 'keg', 'кега', 'кеги']
    CAN_KEYWORDS = ['банк', 'can', 'жестян']
    BOTTLE_KEYWORDS = ['бутыл', 'bottle', 'бут']

    # Паттерны для извлечения объема
    VOLUME_PATTERN = re.compile(r'(\d+[,.]?\d*)\s*(л|л\.|мл|ml|L)', re.IGNORECASE)

    @staticmethod
    def detect(text: str) -> Tuple[str, Optional[float]]:
        """Определить тип тары и объем.

        Args:
            text: Текст для анализа

        Returns:
            Tuple (тип_тары, объем_в_литрах)
            Типы: 'keg', 'can', 'bottle', 'unknown'
            Объем: float или None
        """
        text_lower = text.lower()

        # Определение типа тары
        container_type = 'unknown'

        for keyword in ContainerDetector.KEG_KEYWORDS:
            if keyword in text_lower:
                container_type = 'keg'
                break

        if container_type == 'unknown':
            for keyword in ContainerDetector.CAN_KEYWORDS:
                if keyword in text_lower:
                    container_type = 'can'
                    break

        if container_type == 'unknown':
            for keyword in ContainerDetector.BOTTLE_KEYWORDS:
                if keyword in text_lower:
                    container_type = 'bottle'
                    break

        # Извлечение объема
        volume = ContainerDetector._extract_volume(text_lower)

        return container_type, volume

    @staticmethod
    def _extract_volume(text: str) -> Optional[float]:
        """Извлечь объем из текста.

        Args:
            text: Текст

        Returns:
            Объем в литрах или None
        """
        match = ContainerDetector.VOLUME_PATTERN.search(text)
        if not match:
            return None

        value = float(match.group(1).replace(',', '.'))
        unit = match.group(2).lower()

        # Конвертация в литры
        if 'ml' in unit or 'мл' in unit:
            value = value / 1000

        return value

    @staticmethod
    def format_volume(volume: Optional[float]) -> str:
        """Форматировать объем для отображения.

        Args:
            volume: Объем в литрах

        Returns:
            Отформатированная строка
        """
        if volume is None:
            return "н/д"

        if volume >= 1:
            return f"{volume:.1f}л"

        return f"{volume * 1000:.0f}мл"
