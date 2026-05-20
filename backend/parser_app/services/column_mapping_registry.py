"""
Сборка эффективного маппинга колонок: JSON-реестр + БД + настройки поставщика.
"""

from __future__ import annotations

import fnmatch
import logging
from typing import Dict, List, Optional

from parser_app.infrastructure.config.column_config_loader import get_field_patterns
from parser_app.models import Supplier, SupplierColumnMapping

logger = logging.getLogger(__name__)

# Поля с повышенным весом ключевых слов (ручные / выученные).
PRIORITY_KEYWORD_WEIGHT = 1.35
MANUAL_SUPPLIER_WEIGHT = 1.5


def _append_keywords(target: Dict[str, List[str]], field: str, keyword: str) -> None:
    kw = str(keyword or "").strip()
    if not kw:
        return
    bucket = target.setdefault(field, [])
    if kw not in bucket:
        bucket.append(kw)


def _merge_layers(*layers: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Поздние слои добавляют ключевые слова в начало списка (выше приоритет при скоринге)."""
    merged: Dict[str, List[str]] = {}
    for layer in layers:
        if not layer:
            continue
        for field, keywords in layer.items():
            if not isinstance(keywords, list):
                keywords = [keywords] if keywords else []
            for kw in reversed(keywords):
                _append_keywords(merged, field, kw)
    return merged


def _rows_to_layer(
    rows,
    *,
    prepend: bool = False,
) -> Dict[str, List[str]]:
    layer: Dict[str, List[str]] = {}
    ordered = sorted(rows, key=lambda r: float(r.get("confidence") or 0), reverse=True)
    for row in ordered:
        field = row.get("target_field")
        col = row.get("source_column")
        if not field or not col:
            continue
        if prepend:
            bucket = layer.setdefault(field, [])
            kw = str(col).strip()
            if kw and kw not in bucket:
                bucket.insert(0, kw)
        else:
            _append_keywords(layer, field, col)
    return layer


def _filter_exact_file_rows(rows, filename: str) -> List[dict]:
    if not filename:
        return []
    name = filename.strip()
    matched = []
    for row in rows:
        pattern = (row.get("file_pattern") or "").strip()
        if not pattern:
            continue
        if pattern == name or fnmatch.fnmatch(name.lower(), pattern.lower()):
            matched.append(row)
    return matched


def load_db_mapping_layers(
    *,
    supplier_id: Optional[int] = None,
    filename: Optional[str] = None,
) -> Dict[str, List[str]]:
    """Global + supplier + exact_file слои из SupplierColumnMapping."""
    global_rows = list(
        SupplierColumnMapping.objects.filter(scope=SupplierColumnMapping.SCOPE_GLOBAL).values(
            "target_field", "source_column", "confidence", "file_pattern"
        )
    )
    supplier_rows = []
    exact_rows = []
    if supplier_id:
        supplier_rows = list(
            SupplierColumnMapping.objects.filter(
                scope=SupplierColumnMapping.SCOPE_SUPPLIER,
                supplier_id=supplier_id,
            ).values("target_field", "source_column", "confidence", "file_pattern")
        )
        all_exact = SupplierColumnMapping.objects.filter(
            scope=SupplierColumnMapping.SCOPE_EXACT_FILE,
            supplier_id=supplier_id,
        ).values("target_field", "source_column", "confidence", "file_pattern")
        exact_rows = _filter_exact_file_rows(list(all_exact), filename or "")

    return _merge_layers(
        _rows_to_layer(global_rows),
        _rows_to_layer(supplier_rows, prepend=True),
        _rows_to_layer(exact_rows, prepend=True),
    )


def load_effective_column_mapping(
    *,
    supplier_id: Optional[int] = None,
    filename: Optional[str] = None,
    manual_mapping: Optional[Dict[str, List[str]]] = None,
) -> tuple[Dict[str, List[str]], Dict[str, float]]:
    """
    Итоговый словарь field -> keywords и веса полей для скоринга.

    Порядок приоритета ключевых слов (в начале списка):
    manual supplier JSON -> exact_file -> supplier scope -> global -> column_patterns.json
    """
    base = get_field_patterns() or {}
    db_layer = load_db_mapping_layers(supplier_id=supplier_id, filename=filename)
    manual = manual_mapping or {}

    merged = _merge_layers(base, db_layer, manual)

    # Поля с ключевыми словами только из manual/db — повышенный вес
    keyword_weights: Dict[str, float] = {}
    manual_fields = set(manual.keys()) if manual else set()
    db_fields = set(db_layer.keys()) if db_layer else set()
    for field in manual_fields:
        keyword_weights[field] = MANUAL_SUPPLIER_WEIGHT
    for field in db_fields - manual_fields:
        keyword_weights[field] = PRIORITY_KEYWORD_WEIGHT

    if merged:
        logger.debug(
            "column_mapping_registry: fields=%s supplier_id=%s file=%s",
            list(merged.keys()),
            supplier_id,
            filename,
        )
    return merged, keyword_weights


def resolve_supplier_column_mapping(
    supplier_id: Optional[int] = None,
    filename: Optional[str] = None,
) -> Optional[Dict[str, List[str]]]:
    """
    Удобная обёртка для parse_job: загружает Supplier.column_mapping + реестры.
    Возвращает None, если нет ни одного ключевого слова.
    """
    manual: Dict[str, List[str]] = {}
    if supplier_id:
        try:
            supplier = Supplier.objects.get(pk=supplier_id)
            raw = supplier.column_mapping or {}
            if isinstance(raw, dict):
                for field, kws in raw.items():
                    if isinstance(kws, list):
                        manual[field] = [str(k) for k in kws if k]
                    elif kws:
                        manual[field] = [str(kws)]
            logger.info("Маппинг поставщика: %s", supplier.name)
        except Supplier.DoesNotExist:
            logger.warning("Поставщик %s не найден", supplier_id)

    merged, _weights = load_effective_column_mapping(
        supplier_id=supplier_id,
        filename=filename,
        manual_mapping=manual or None,
    )
    return merged if merged else None
