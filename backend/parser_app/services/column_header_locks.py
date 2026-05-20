"""
Жёсткое сопоставление заголовка колонки полю (приоритет над content-scoring).
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple


def _normalize_header(value: object) -> str:
    text = str(value or "").strip().lower()
    return re.sub(r"\s+", " ", text)

# Поле -> подстроки заголовка (порядок важен: более специфичные правила первыми)
_HEADER_RULES: List[Tuple[str, List[str]]] = [
    ("beer_name", ["наименование", "название товара", "название пива"]),
    ("brewery", ["наименование пивоварни", "пивоварня", "производитель", "бренд"]),
    ("format_type", ["тип тары", "тип фасовки", "фасовка", "упаковка", "тара"]),
    ("stock", ["наличие", "остаток", "в наличии"]),
    ("price", ["цена", "стоимость", "price", "cost"]),
    ("style", ["стиль", "style", "сорт"]),
    ("abv", ["abv", "крепость", "алк"]),
    ("ibu", ["ibu", "горечь"]),
    ("volume", ["объем", "объём", "литраж", "volume"]),
    ("description", ["описание", "description", "комментар", "примечан"]),
    ("currency", ["валюта", "currency"]),
]

# Заголовки, которые не маппим на продуктовые поля
_SKIP_HEADER_TOKENS = ("этикетка", "годен до", "скидки", "акции", "заказ (кег", "сайт", "почта", "telegram")

# Колонки с этими заголовками не должны получать volume/price/abv по content
_NUMERIC_BLOCK_HEADERS = frozenset({"og", "original gravity"})


def locked_field_for_header(header: object) -> Optional[str]:
    """
    Возвращает поле для колонки или None.
    '__skip__' — колонку не использовать.
    """
    h = _normalize_header(header)
    if not h:
        return None
    if any(tok in h for tok in _SKIP_HEADER_TOKENS):
        return "__skip__"
    if h in _NUMERIC_BLOCK_HEADERS or h.startswith("og "):
        return "__og__"

    for field, tokens in _HEADER_RULES:
        for tok in tokens:
            if tok == h or tok in h:
                if field == "beer_name" and "пивоварни" in h:
                    continue
                if field == "brewery" and "наименование" in h and "пивоварни" not in h:
                    continue
                return field
    return None


def apply_header_locks(
    headers: List[object],
) -> Tuple[Dict[str, int], Set[int], Set[int]]:
    """
    Returns:
        locked mapping field->col_idx
        used column indices
        skipped column indices
    """
    mapping: Dict[str, int] = {}
    used_cols: Set[int] = set()
    skipped: Set[int] = set()

    for idx, header in enumerate(headers):
        field = locked_field_for_header(header)
        if field == "__skip__" or field == "__og__":
            skipped.add(idx)
            continue
        if not field or field in mapping:
            continue
        mapping[field] = idx
        used_cols.add(idx)

    return mapping, used_cols, skipped
