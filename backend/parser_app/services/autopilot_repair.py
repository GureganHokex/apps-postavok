"""
Autopilot post-processing for parsed raw items.

Задача: автоматически исправлять типовые ошибки маппинга колонок между поставщиками
без участия пользователя.
"""

import re
from typing import Dict, List, Tuple


def _is_empty(val) -> bool:
    if val is None:
        return True
    s = str(val).strip()
    return s == "" or s in {"-", "—", "–"}


def _word_count(text: str) -> int:
    return len([w for w in text.strip().split() if w])


def _is_description_like(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    words = _word_count(t)
    # Длинный текст, пунктуация и многословность чаще соответствуют description.
    return len(t) >= 70 or words >= 12 or (("," in t or "." in t or ":" in t) and words >= 8)


def _is_name_like(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    words = _word_count(t)
    # Название обычно короче и компактнее.
    return len(t) <= 80 and words <= 8


def _split_description_lines(text: str) -> Tuple[str, str]:
    lines = [ln.strip() for ln in str(text or "").splitlines() if ln and ln.strip()]
    if not lines:
        return "", ""
    first = lines[0]
    body = " ".join(lines[1:]).strip()
    return first, body


def _clean_name_token(text: str) -> str:
    t = str(text or "").strip()
    # Частые служебные метки из скобок не должны попадать в name.
    t = re.sub(r"\((fresh brewed|new|limited|лимитирован[а-я]*)\)", "", t, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", t).strip(" -—–,;")


def _looks_like_upper_title(text: str) -> bool:
    t = str(text or "").strip()
    if not t:
        return False
    words = [w for w in re.split(r"\s+", t) if w]
    if not words or len(words) > 6:
        return False
    alpha_words = [w for w in words if any(ch.isalpha() for ch in w)]
    if not alpha_words:
        return False
    upper_ratio = sum(1 for w in alpha_words if w == w.upper()) / len(alpha_words)
    return upper_ratio >= 0.8


def _repair_item(item: Dict) -> Dict:
    out = dict(item)
    beer_name = str(out.get("beer_name") or "").strip()
    description = str(out.get("description") or "").strip()
    style = str(out.get("style") or "").strip()
    first_desc_line, desc_body = _split_description_lines(description)
    first_desc_line_clean = _clean_name_token(first_desc_line)

    # 1) Классическая инверсия: в beer_name попал абзац, а в description короткое имя.
    if _is_description_like(beer_name) and _is_name_like(description):
        out["beer_name"], out["description"] = description, beer_name
        return out

    # 1.1) Description многострочный: первая строка похожа на имя, остальное — описание.
    if first_desc_line_clean and _is_name_like(first_desc_line_clean) and _is_description_like(desc_body):
        if _is_empty(beer_name) or _is_description_like(beer_name):
            out["beer_name"] = first_desc_line_clean
            out["description"] = desc_body or description
            beer_name = out["beer_name"]
            description = out["description"]

    # 2) beer_name пустой/тире, но в description есть короткое название.
    if _is_empty(beer_name) and _is_name_like(description):
        out["beer_name"] = description
        return out

    # 3) Иногда beer_name совпадает со style, а реальное имя лежит в description.
    if beer_name and style and beer_name.lower() == style.lower() and _is_name_like(description):
        out["beer_name"] = description
        return out

    # 4) brewery иногда приходит как "PARADOX HOPFEN WEISSE", а это скорее "brewery + beer_name".
    brewery = str(out.get("brewery") or "").strip()
    if brewery and (_is_empty(out.get("beer_name")) or brewery == str(out.get("beer_name") or "").strip()):
        if _looks_like_upper_title(brewery):
            parts = brewery.split()
            if len(parts) >= 2:
                out["brewery"] = parts[0]
                out["beer_name"] = " ".join(parts[1:])

    # 5) Если beer_name всё ещё выглядит абзацем, а в description есть первая строка-имя — берем её.
    if _is_description_like(str(out.get("beer_name") or "")) and first_desc_line_clean and _is_name_like(first_desc_line_clean):
        out["beer_name"] = first_desc_line_clean
        if desc_body:
            out["description"] = desc_body

    # 6) Если brewery очевидно содержит описание, очищаем его (лучше пусто, чем мусор в UI).
    brewery_now = str(out.get("brewery") or "").strip()
    if brewery_now and _is_description_like(brewery_now) and _is_name_like(str(out.get("beer_name") or "")):
        out["brewery"] = ""

    return out


def autopilot_repair_raw_items(raw_items: List[Dict]) -> List[Dict]:
    prepared = [item for item in raw_items if isinstance(item, dict)]
    if not prepared:
        return []

    # Диагностика качества brewery-колонки на уровне файла.
    brewery_values = [str(i.get("brewery") or "").strip() for i in prepared if not _is_empty(i.get("brewery"))]
    unique_ratio = (len(set(brewery_values)) / len(brewery_values)) if brewery_values else 0.0
    long_like_brewery = sum(1 for b in brewery_values if _word_count(b) >= 3 or len(b) > 25)
    malformed_brewery_ratio = (long_like_brewery / len(brewery_values)) if brewery_values else 0.0
    brewery_column_suspicious = unique_ratio > 0.7 and malformed_brewery_ratio > 0.3

    repaired = []
    for item in prepared:
        if not isinstance(item, dict):
            continue
        fixed = _repair_item(item)

        # Автоспасение: если brewery-поле похоже на источник названия (часто у "сломанного" маппинга),
        # переносим его в beer_name.
        brewery = str(fixed.get("brewery") or "").strip()
        beer_name = str(fixed.get("beer_name") or "").strip()
        if brewery_column_suspicious and brewery:
            if _is_empty(beer_name):
                fixed["beer_name"] = brewery
                fixed["brewery"] = ""

        repaired.append(fixed)
    return repaired

