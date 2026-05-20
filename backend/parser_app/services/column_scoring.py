"""
Скоринг заголовков колонок для маппинга полей прайса.
Общий модуль для legacy-парсера и pipeline_v2.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

from parser_app.services.column_content_scoring import score_column_content_for_field
from parser_app.services.column_header_locks import apply_header_locks, locked_field_for_header

CONTENT_SCORE_WEIGHT = 3.0
HEADER_LOCK_BONUS = 50.0

# Веса источников совпадения (keyword list order задаётся в registry).
WEIGHT_EXACT = 10.0
WEIGHT_SUBSTRING = 6.0
WEIGHT_REVERSE_SUBSTRING = 3.0
WEIGHT_FUZZY = 4.0
FUZZY_MIN_RATIO = 0.82

# Анти-паттерны: поле -> подстроки в заголовке, которые снижают score.
FIELD_HEADER_PENALTIES: Dict[str, List[str]] = {
    "beer_name": ["описан", "description", "стиль", "style", "коммент", "примечан"],
    "description": [],
}

FIELD_HEADER_BONUSES: Dict[str, List[str]] = {
    "description": ["описан", "description", "коммент", "примечан"],
}


def _normalize_header(value: object) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _fuzzy_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def score_header_for_field(
    header: object,
    field_name: str,
    keywords: List[str],
    *,
    keyword_weight: float = 1.0,
) -> float:
    """
    Оценка соответствия заголовка колонки целевому полю.
    keyword_weight > 1 для пользовательских/выученных ключевых слов.
    """
    h = _normalize_header(header)
    if not h or not keywords:
        return 0.0

    score = 0.0
    for raw_kw in keywords:
        kw = _normalize_header(raw_kw)
        if not kw:
            continue
        if kw == h:
            score = max(score, WEIGHT_EXACT * keyword_weight)
        elif kw in h:
            score = max(score, WEIGHT_SUBSTRING * keyword_weight)
        elif h in kw:
            score = max(score, WEIGHT_REVERSE_SUBSTRING * keyword_weight)
        else:
            ratio = _fuzzy_ratio(kw, h)
            if ratio >= FUZZY_MIN_RATIO:
                score = max(score, WEIGHT_FUZZY * ratio * keyword_weight)

    for token in FIELD_HEADER_PENALTIES.get(field_name, []):
        if token in h:
            score -= 6.0
    for token in FIELD_HEADER_BONUSES.get(field_name, []):
        if token in h:
            score += 2.0

    return max(score, 0.0)


def build_mapping_from_keywords(
    headers: List[object],
    field_keywords: Dict[str, List[str]],
    *,
    keyword_weights: Optional[Dict[str, float]] = None,
    column_samples: Optional[Dict[int, List[str]]] = None,
    content_weight: float = CONTENT_SCORE_WEIGHT,
) -> Dict[str, int]:
    """
    Строит field -> column_index по заголовкам + опционально содержимому колонок.
    Сначала жёсткие locks по заголовку, затем greedy для остальных полей.
    """
    if not headers or not field_keywords:
        return {}

    weights = keyword_weights or {}
    headers_display = [str(h) if h is not None else "" for h in headers]

    mapping, used_cols, skipped_cols = apply_header_locks(headers)

    # (score, field, col_idx)
    candidates: List[Tuple[float, str, int]] = []
    for field, keywords in field_keywords.items():
        if field in mapping:
            continue
        if not isinstance(keywords, list):
            keywords = [keywords] if keywords else []
        kw_weight = float(weights.get(field, 1.0))
        for idx, header in enumerate(headers_display):
            if idx in used_cols or idx in skipped_cols:
                continue
            locked = locked_field_for_header(header)
            if locked and locked not in ("__skip__", "__og__") and locked != field:
                continue
            if locked == "__og__" and field in ("volume", "abv", "ibu", "price", "beer_name"):
                continue

            header_s = score_header_for_field(header, field, keywords, keyword_weight=kw_weight)
            if locked == field:
                header_s = max(header_s, HEADER_LOCK_BONUS)

            # «НАИМЕНОВАНИЕ» — не отдаём колонку description по content
            if field == "description" and locked_field_for_header(header) == "beer_name":
                continue

            content_s = 0.0
            if column_samples and idx in column_samples:
                content_s = score_column_content_for_field(column_samples[idx], field)
            total = header_s + content_weight * content_s
            if total > 0:
                candidates.append((total, field, idx))

    candidates.sort(key=lambda x: x[0], reverse=True)
    for score, field, idx in candidates:
        if field in mapping or idx in used_cols:
            continue
        mapping[field] = idx
        used_cols.add(idx)

    return mapping


def score_header_row(row_values: List[object], field_patterns: Dict[str, List[str]]) -> float:
    """Оценка строки как строки заголовков таблицы."""
    score = 0.0
    for value in row_values:
        cell = _normalize_header(value)
        if not cell:
            continue
        if any(
            score_header_for_field(cell, field, aliases) > 0
            for field, aliases in field_patterns.items()
        ):
            score += 2.0
        if len(cell) <= 40:
            score += 0.5
        if any(ch.isdigit() for ch in cell):
            score -= 0.8
    return score
