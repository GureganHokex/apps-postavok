"""Диспетчер парсинга с feature-flag и shadow-режимом."""

from pathlib import Path
from typing import Any, Dict

from django.conf import settings
from django.core.cache import cache

from parser_app.parsers import PDFParser, ExcelParser, GoogleSheetsParser
from parser_app.pipeline_v2 import ExcelPipelineV2, ParseResult, ParseStatus, ParseIssue


def _build_legacy_parser(file_obj, file_full_path: Path):
    if file_obj.file_type == "pdf":
        return PDFParser(str(file_full_path))
    if file_obj.file_type == "excel":
        return ExcelParser(str(file_full_path))
    if file_obj.file_type == "google_sheets":
        return GoogleSheetsParser(str(file_full_path), file_obj.google_sheet_url)
    return None


def _run_legacy(file_obj, parse_kwargs: Dict[str, Any], file_full_path: Path) -> ParseResult:
    legacy_parser = _build_legacy_parser(file_obj, file_full_path)
    if legacy_parser is None:
        return ParseResult(
            status=ParseStatus.FAILED,
            items=[],
            errors=[ParseIssue(code="unknown_file_type", message="Неизвестный тип файла", severity="error")],
            meta={"pipeline_version": "legacy"},
        )
    try:
        items = legacy_parser.parse(**parse_kwargs)
        parser_stats = getattr(legacy_parser, "stats", {})
        return ParseResult(
            status=ParseStatus.COMPLETED,
            items=items,
            meta={"pipeline_version": "legacy", "parser_stats": parser_stats},
        )
    except Exception as exc:
        return ParseResult(
            status=ParseStatus.FAILED,
            items=[],
            errors=[ParseIssue(code="legacy_parse_failed", message=str(exc), severity="error")],
            meta={"pipeline_version": "legacy"},
        )


def _with_shadow(primary: ParseResult, secondary: ParseResult) -> ParseResult:
    primary_count = len(primary.items)
    secondary_count = len(secondary.items)
    delta = primary_count - secondary_count
    denominator = secondary_count if secondary_count > 0 else 1
    delta_pct = (delta / denominator) * 100.0
    secondary_status = getattr(secondary.status, "value", secondary.status)
    primary.meta["shadow"] = {
        "primary_count": primary_count,
        "secondary_count": secondary_count,
        "delta": delta,
        "delta_pct": delta_pct,
        "secondary_status": str(secondary_status),
        "secondary_version": secondary.meta.get("pipeline_version"),
        "secondary_errors": [e.to_dict() for e in secondary.errors],
        "secondary_meta": {
            "column_mapping_confidence": secondary.meta.get("column_mapping_confidence"),
            "column_mapping_candidates": secondary.meta.get("column_mapping_candidates"),
            "column_mappings": secondary.meta.get("column_mappings"),
        },
    }
    return primary


def dispatch_parse(file_obj, parse_kwargs: Dict[str, Any]) -> ParseResult:
    file_full_path = Path(settings.MEDIA_ROOT) / file_obj.file_path
    use_v2 = bool(parse_kwargs.pop("__use_v2_override", getattr(settings, "EXCEL_PARSER_PIPELINE_V2", False)))
    force_legacy = bool(parse_kwargs.pop("__force_legacy_override", getattr(settings, "PARSER_LEGACY_FORCE", False)))
    shadow_mode = bool(parse_kwargs.pop("__shadow_mode_override", getattr(settings, "PARSER_SHADOW_MODE", False)))
    canary_rollback_active = bool(cache.get("parser_canary_force_legacy", False))
    if canary_rollback_active:
        force_legacy = True

    if file_obj.file_type == "excel" and use_v2 and not force_legacy:
        primary = ExcelPipelineV2(str(file_full_path)).run(**parse_kwargs)
        primary.meta["canary_force_legacy"] = canary_rollback_active
        if shadow_mode:
            secondary = _run_legacy(file_obj, parse_kwargs, file_full_path)
            return _with_shadow(primary, secondary)
        return primary

    primary = _run_legacy(file_obj, parse_kwargs, file_full_path)
    primary.meta["canary_force_legacy"] = canary_rollback_active
    if shadow_mode and file_obj.file_type == "excel":
        secondary = ExcelPipelineV2(str(file_full_path)).run(**parse_kwargs)
        return _with_shadow(primary, secondary)
    return primary

