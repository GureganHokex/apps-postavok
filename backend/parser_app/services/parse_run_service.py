"""
Persist ParseRun records for parser executions.
"""

from typing import Any, Dict, Optional

from parser_app.models import ParseRun, Supplier


def persist_parse_run(
    *,
    file_obj,
    parse_result,
    parse_kwargs: Dict[str, Any],
    user=None,
    supplier_id: Optional[int] = None,
) -> ParseRun:
    supplier = None
    if supplier_id:
        supplier = Supplier.objects.filter(pk=supplier_id).first()

    status_value = getattr(parse_result.status, "value", parse_result.status)
    return ParseRun.objects.create(
        file=file_obj,
        supplier=supplier,
        user=user if getattr(user, "is_authenticated", False) else None,
        pipeline_version=parse_result.meta.get("pipeline_version", "legacy"),
        status=str(status_value),
        items_count=len(parse_result.items),
        warning_count=len(parse_result.warnings),
        error_count=len(parse_result.errors),
        parse_kwargs=parse_kwargs or {},
        summary={
            "warnings": [w.to_dict() for w in parse_result.warnings],
            "errors": [e.to_dict() for e in parse_result.errors],
            "shadow": parse_result.meta.get("shadow"),
            "meta": parse_result.meta,
        },
    )

