"""
Скоринг колонок по содержимому ячеек (дополнение к заголовкам).
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional

_EMPTY_TOKENS = frozenset({"", "-", "—", "–", "nan", "none", "null", "n/a", "xx", "хх"})


def _is_na(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return False


def _parse_number(value: object) -> Optional[float]:
    if _is_na(value):
        return None
    text = str(value).strip().replace(" ", "").replace(",", ".")
    if not text or text.lower() in _EMPTY_TOKENS:
        return None
    text = re.sub(r"[^\d.\-/%]", "", text)
    if not text:
        return None
    try:
        return float(text.rstrip("%"))
    except ValueError:
        return None


def sample_column_values(
    df: Any,
    col_idx: int,
    *,
    start_row: int = 0,
    max_rows: int = 40,
) -> List[str]:
    """Берёт непустые значения колонки из тела таблицы."""
    if df.empty or col_idx < 0 or col_idx >= len(df.columns):
        return []
    values: List[str] = []
    end = min(len(df), start_row + max_rows)
    for row_i in range(start_row, end):
        try:
            raw = df.iloc[row_i, col_idx]
        except Exception:
            continue
        if _is_na(raw):
            continue
        text = str(raw).strip()
        if text.lower() in _EMPTY_TOKENS:
            continue
        values.append(text)
    return values


def build_column_samples(
    df: Any,
    *,
    start_row: int = 0,
    max_rows: int = 40,
) -> Dict[int, List[str]]:
    samples: Dict[int, List[str]] = {}
    for col_idx in range(len(df.columns)):
        vals = sample_column_values(df, col_idx, start_row=start_row, max_rows=max_rows)
        if vals:
            samples[col_idx] = vals
    return samples


def score_column_content_for_field(values: List[str], field_name: str) -> float:
    """
    0..10 — насколько содержимое колонки похоже на поле.
    """
    if not values:
        return 0.0

    numbers: List[float] = []
    text_values: List[str] = []
    for val in values:
        num = _parse_number(val)
        if num is not None:
            numbers.append(num)
        text_values.append(str(val).strip())

    numeric_ratio = len(numbers) / len(values) if values else 0.0
    avg_len = sum(len(t) for t in text_values) / len(text_values) if text_values else 0.0
    joined_lower = " ".join(text_values).lower()

    if field_name == "price":
        if numeric_ratio < 0.5:
            return 0.0
        in_range = [n for n in numbers if 15 <= n <= 100_000]
        if not in_range:
            return 1.0
        ratio = len(in_range) / len(numbers)
        # «330 / 6600» — цена в прайсах
        slash_prices = sum(1 for t in text_values if re.search(r"\d+\s*/\s*\d+", t))
        bonus = min(2.0, slash_prices * 0.5)
        return min(10.0, 4.0 + 6.0 * ratio + bonus)

    if field_name == "abv":
        abv_hits = 0
        for t in text_values:
            if "%" in t or re.search(r"\babv\b", t, re.I):
                abv_hits += 1
        pct_nums = [n for n in numbers if 0 <= n <= 20]
        if pct_nums and numeric_ratio >= 0.4:
            return min(10.0, 3.0 + 7.0 * (len(pct_nums) / len(numbers)) + abv_hits)
        if abv_hits:
            return 6.0
        return 0.0

    if field_name == "ibu":
        ibu_nums = [n for n in numbers if 0 <= n <= 120]
        if ibu_nums and numeric_ratio >= 0.5:
            return min(10.0, 5.0 + 5.0 * (len(ibu_nums) / len(numbers)))
        return 0.0

    if field_name == "volume":
        # OG/ABV/IBU часто 5–20 — не путать с литражом
        if numeric_ratio >= 0.7:
            in_beer_gravity_band = sum(1 for n in numbers if 0.5 <= n <= 25) / len(numbers)
            if in_beer_gravity_band >= 0.8 and not any(
                re.search(r"\d+[.,]?\d*\s*л", t, re.I) for t in text_values
            ):
                return 0.0
        vol_nums = [n for n in numbers if 0.05 <= n <= 100]
        if vol_nums and numeric_ratio >= 0.4:
            return min(10.0, 4.0 + 6.0 * (len(vol_nums) / len(numbers)))
        return 0.0

    if field_name == "stock":
        intish = [n for n in numbers if n == int(n) and 0 <= n <= 50_000]
        if intish and numeric_ratio >= 0.6:
            return min(10.0, 3.0 + 7.0 * (len(intish) / len(numbers)))
        stock_words = ("много", "мало", "есть", "нет", "в наличии", "под заказ")
        if any(w in joined_lower for w in stock_words):
            return 5.0
        return 0.0

    if field_name == "beer_name":
        packaging_hits = sum(
            1
            for t in text_values
            if re.search(r"(банка|бутылк|кег|can|keg|шт/кор|не дробим)", t, re.I)
        )
        if packaging_hits >= max(1, len(text_values) // 2):
            return 0.0
        if numeric_ratio > 0.8:
            return 0.0
        multi_line_names = sum(1 for t in text_values if "\n" in t and len(t) > 20)
        if multi_line_names:
            return min(10.0, 6.0 + multi_line_names)
        if avg_len < 8:
            return 1.0
        if avg_len > 120:
            return 2.0
        alpha_ratio = sum(1 for t in text_values if re.search(r"[а-яa-z]", t, re.I)) / len(text_values)
        return min(10.0, 2.0 + 8.0 * alpha_ratio)

    if field_name == "brewery":
        if numeric_ratio > 0.5:
            return 0.0
        if 3 <= avg_len <= 40:
            short_text = sum(1 for t in text_values if 2 <= len(t) <= 35) / len(text_values)
            return min(10.0, 3.0 + 7.0 * short_text)
        return 0.0

    if field_name == "style":
        style_kw = (
            "ipa", "lager", "ale", "stout", "porter", "pilsner", "gose", "neipa",
            "сайсон", "стаут", "эль", "лагер",
        )
        hits = sum(1 for kw in style_kw if kw in joined_lower)
        if hits and avg_len < 60:
            return min(10.0, 4.0 + hits * 2.0)
        return 0.0

    if field_name == "description":
        if avg_len > 50:
            return min(10.0, 4.0 + (avg_len - 50) / 25.0)
        return 0.0

    if field_name == "format_type":
        fmt_kw = ("банка", "can", "кег", "keg", "бутыл", "bottle", "розлив", "тара", "фасов")
        if any(k in joined_lower for k in fmt_kw):
            return 8.0
        return 0.0

    return 0.0
