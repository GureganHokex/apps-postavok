"""
Контракты V2-пайплайна для устойчивого Excel-парсинга.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ParseStatus(str, Enum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass
class ParseIssue:
    code: str
    message: str
    field_name: Optional[str] = None
    # legacy alias for backward compatibility
    field: Optional[str] = None
    severity: str = "warning"

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "field_name": self.field_name,
            "field": self.field if self.field is not None else self.field_name,
        }
        return payload


@dataclass
class ParseResult:
    status: ParseStatus
    items: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[ParseIssue] = field(default_factory=list)
    errors: List[ParseIssue] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

