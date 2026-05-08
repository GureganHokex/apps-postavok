"""
Self-learning helpers for parser feedback loop.
"""

from typing import Optional, Tuple

from parser_app.models import ParsingFeedback, SupplierColumnMapping


def promote_feedback_to_mapping(
    feedback: ParsingFeedback,
    *,
    scope: Optional[str] = None,
    confidence: Optional[float] = None,
) -> Tuple[SupplierColumnMapping, bool]:
    if not feedback.accepted:
        raise ValueError("Можно продвигать только accepted feedback.")

    use_scope = scope or SupplierColumnMapping.SCOPE_SUPPLIER
    if use_scope not in {
        SupplierColumnMapping.SCOPE_GLOBAL,
        SupplierColumnMapping.SCOPE_SUPPLIER,
        SupplierColumnMapping.SCOPE_EXACT_FILE,
    }:
        raise ValueError("Некорректный scope.")

    use_confidence = confidence if confidence is not None else feedback.confidence
    try:
        use_confidence = float(use_confidence)
    except (TypeError, ValueError):
        use_confidence = feedback.confidence

    file_pattern = ""
    if use_scope == SupplierColumnMapping.SCOPE_EXACT_FILE:
        if feedback.parse_run and feedback.parse_run.file:
            file_pattern = feedback.parse_run.file.original_filename
        else:
            raise ValueError("Для scope=exact_file нужен parse_run с файлом.")

    mapping, created = SupplierColumnMapping.objects.update_or_create(
        supplier=feedback.supplier if use_scope == SupplierColumnMapping.SCOPE_SUPPLIER else None,
        scope=use_scope,
        source_column=feedback.source_column,
        target_field=feedback.suggested_field,
        defaults={
            "confidence": use_confidence,
            "file_pattern": file_pattern,
            "meta": {
                "promoted_from_feedback_id": feedback.id,
                "note": feedback.note,
                "auto_promoted": True,
            },
        },
    )
    return mapping, created

