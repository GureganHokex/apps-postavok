"""
Загрузчик конфигурации синонимов колонок для парсера прайсов.
Позволяет менять и дополнять маппинг без правок кода.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

_CONFIG_CACHE: Dict[str, Any] = {}
_CONFIG_DIR = Path(__file__).resolve().parent


def _load_config() -> Dict[str, Any]:
    """Загружает конфиг из JSON. Кэширует результат."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE:
        return _CONFIG_CACHE
    config_path = _CONFIG_DIR / "column_patterns.json"
    try:
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                _CONFIG_CACHE = json.load(f)
            logger.debug("Загружен конфиг колонок из %s", config_path)
        else:
            _CONFIG_CACHE = {}
            logger.warning("Файл конфига не найден: %s", config_path)
    except Exception as e:
        logger.warning("Ошибка загрузки конфига колонок: %s", e)
        _CONFIG_CACHE = {}
    return _CONFIG_CACHE


def get_field_patterns() -> Dict[str, List[str]]:
    """Возвращает словарь {поле: [синонимы заголовков]}."""
    config = _load_config()
    patterns = config.get("field_patterns") or {}
    return patterns


def get_header_patterns() -> List[str]:
    """Возвращает список паттернов для поиска строки заголовков."""
    config = _load_config()
    patterns = config.get("header_patterns") or []
    return patterns


def get_price_header_keywords() -> List[str]:
    """Ключевые слова для определения ценовых колонок."""
    config = _load_config()
    return config.get("price_header_keywords") or ["цена", "price", "стоимость", "cost", "руб"]


def get_format_keywords() -> Dict[str, List[str]]:
    """Ключевые слова форматов упаковки в заголовках."""
    config = _load_config()
    return config.get("format_keywords_in_headers") or {}


def clear_cache() -> None:
    """Сбрасывает кэш конфига (для тестов или перезагрузки)."""
    global _CONFIG_CACHE
    _CONFIG_CACHE = {}
