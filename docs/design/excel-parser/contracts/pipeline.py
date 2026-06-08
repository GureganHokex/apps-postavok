"""
Псевдокод модульных интерфейсов устойчивого Excel-парсинг pipeline.

Этот файл — design contract. Он не подключается к Django, не импортирует
проектный код и не предполагает запуска. Он существует, чтобы:

1. Зафиксировать DTO между стадиями pipeline (см. architecture.md §4-§5).
2. Зафиксировать сигнатуры стадий (Protocol).
3. Быть синтаксически валидным Python (проверяется ast.parse как часть
   acceptance).

Реализации этих интерфейсов появятся в backend/parser_app/* в рамках
плана миграции (architecture.md §12.1). Здесь — только формы.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    Generic,
    Iterable,
    Literal,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    TypeVar,
    runtime_checkable,
)


# ---------------------------------------------------------------------------
# Базовые типы и енумы
# ---------------------------------------------------------------------------


class Field(str, Enum):
    BREWERY = "brewery"
    BEER_NAME = "beer_name"
    STYLE = "style"
    ABV = "abv"
    IBU = "ibu"
    PRICE = "price"
    CURRENCY = "currency"
    VOLUME = "volume"
    FORMAT_TYPE = "format_type"
    STOCK = "stock"
    DESCRIPTION = "description"


class FormatType(str, Enum):
    BOTTLE = "bottle"
    CAN = "can"
    KEG = "keg"
    OTHER = "other"
    UNKNOWN = "unknown"


class CandidateSource(str, Enum):
    USER = "user"
    HEADER_EXACT = "header_exact"
    HEADER_STEM = "header_stem"
    HEADER_FUZZY = "header_fuzzy"
    HEADER_EMBEDDING = "header_embedding"
    CONTENT = "content"
    PROFILE = "profile"
    POSITION = "position"


SheetKind = Literal["data", "meta", "trash"]
RowKind = Literal["data", "group_header", "total", "divider", "noise"]
ParseStatus = Literal["ok", "partial", "failed"]


CellValue = Optional[Any]


# ---------------------------------------------------------------------------
# DTO: вход и промежуточные представления
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RawFile:
    filename: str
    content: bytes
    mime_hint: Optional[str] = None


@dataclass(frozen=True)
class MergedRange:
    row_start: int
    row_end: int
    col_start: int
    col_end: int


@dataclass(frozen=True)
class Sheet:
    name: str
    cells: Sequence[Sequence[CellValue]]
    merged_ranges: Sequence[MergedRange] = field(default_factory=tuple)


@dataclass(frozen=True)
class Workbook:
    source: RawFile
    sheets: Sequence[Sheet]


@dataclass(frozen=True)
class SheetVerdict:
    sheet: Sheet
    kind: SheetKind
    confidence: float
    reasons: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class FileMeta:
    supplier_name: Optional[str] = None
    price_date: Optional[date] = None
    default_currency: Optional[str] = None
    confidence: float = 0.0
    reasons: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class DataRegion:
    sheet: Sheet
    row_start: int
    row_end: int
    col_start: int
    col_end: int


@dataclass(frozen=True)
class HeaderCandidate:
    rows: tuple[int, ...]
    headers: Sequence[str]
    confidence: float
    reasons: Sequence[str] = field(default_factory=tuple)


T = TypeVar("T")


@dataclass(frozen=True)
class Candidate(Generic[T]):
    value: T
    confidence: float
    source: CandidateSource
    reasons: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class ColumnPlan:
    mapping: Mapping[Field, Candidate[int]]
    rejected: Mapping[Field, Sequence[Candidate[int]]]
    overall_confidence: float


@dataclass(frozen=True)
class RawRow:
    sheet: str
    row_index: int
    cells: Sequence[CellValue]
    kind: RowKind
    group_context: Mapping[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# DTO: результат парсинга
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParseWarning:
    code: str
    message: str
    sheet: Optional[str] = None
    row: Optional[int] = None
    field_name: Optional[str] = None


@dataclass(frozen=True)
class ParseError:
    code: str
    message: str
    sheet: Optional[str] = None
    row: Optional[int] = None
    field_name: Optional[str] = None


@dataclass(frozen=True)
class ParsedItem:
    beer_name: str
    source_sheet: str
    source_row: int
    confidence: float
    field_confidences: Mapping[str, float]
    brewery: Optional[str] = None
    style: Optional[str] = None
    abv: Optional[float] = None
    ibu: Optional[float] = None
    price: Optional[Decimal] = None
    currency: Optional[str] = None
    volume: Optional[Decimal] = None
    format_type: FormatType = FormatType.UNKNOWN
    stock: Optional[Decimal] = None
    description: Optional[str] = None
    warnings: Sequence[ParseWarning] = field(default_factory=tuple)


@dataclass(frozen=True)
class ParseResult:
    status: ParseStatus
    items: Sequence[ParsedItem]
    invalid_items: Sequence[ParsedItem]
    warnings: Sequence[ParseWarning]
    errors: Sequence[ParseError]
    file_meta: FileMeta
    pipeline_version: str


# ---------------------------------------------------------------------------
# Конфигурация и контекст
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SupplierColumnMapping:
    supplier_id: Optional[str]
    file_pattern: Optional[str]
    sheet_pattern: Optional[str]
    mapping: Mapping[str, str]


@dataclass(frozen=True)
class SupplierProfileHint:
    type_: Literal["distributor", "brewery", "unknown"]
    confidence: float
    reasons: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class PipelineConfig:
    field_threshold: float = 0.45
    optional_field_threshold: float = 0.30
    max_header_scan_rows: int = 30
    max_columns: int = 200
    enable_embedding_match: bool = False
    enable_parallel_sheets: bool = False
    streaming_mode_threshold_bytes: int = 20 * 1024 * 1024


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TelemetryEvent:
    event: str
    payload: Mapping[str, Any]


@runtime_checkable
class TelemetrySink(Protocol):
    def emit(self, event: TelemetryEvent) -> None:
        ...


# ---------------------------------------------------------------------------
# Реестры (lexicons + profiles)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldLexicon:
    synonyms: Mapping[Field, Sequence[str]]


@dataclass(frozen=True)
class FormatLexicon:
    mapping: Mapping[str, FormatType]


@dataclass(frozen=True)
class CurrencyLexicon:
    mapping: Mapping[str, str]


@dataclass(frozen=True)
class VolumePattern:
    regex: str
    multiplier_to_litres: Decimal


@dataclass(frozen=True)
class VolumeLexicon:
    patterns: Sequence[VolumePattern]


@dataclass(frozen=True)
class SupplierHintEntry:
    keywords: Sequence[str]
    type_: Literal["distributor", "brewery"]


@dataclass(frozen=True)
class SupplierHints:
    entries: Sequence[SupplierHintEntry]


@dataclass(frozen=True)
class Lexicons:
    fields: FieldLexicon
    formats: FormatLexicon
    currencies: CurrencyLexicon
    volumes: VolumeLexicon
    supplier_hints: SupplierHints


@runtime_checkable
class SupplierProfile(Protocol):
    name: str

    def match(self, hint: SupplierProfileHint, meta: FileMeta) -> float:
        ...

    def suggest_columns(
        self, headers: Sequence[str], region: DataRegion
    ) -> Mapping[Field, Candidate[int]]:
        ...


@runtime_checkable
class ProfileRegistry(Protocol):
    def all(self) -> Sequence[SupplierProfile]:
        ...

    def match_best(
        self, hint: SupplierProfileHint, meta: FileMeta
    ) -> Optional[SupplierProfile]:
        ...


# ---------------------------------------------------------------------------
# PipelineContext
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PipelineContext:
    config: PipelineConfig
    lexicons: Lexicons
    profiles: ProfileRegistry
    telemetry: TelemetrySink
    user_mapping: Optional[SupplierColumnMapping] = None
    pipeline_version: str = "v2"


# ---------------------------------------------------------------------------
# Стадии (Protocol)
# ---------------------------------------------------------------------------


@runtime_checkable
class Loader(Protocol):
    def load(self, raw_file: RawFile, ctx: PipelineContext) -> Workbook:
        ...


@runtime_checkable
class SheetClassifier(Protocol):
    def classify(
        self, workbook: Workbook, ctx: PipelineContext
    ) -> Sequence[SheetVerdict]:
        ...


@runtime_checkable
class MetaExtractor(Protocol):
    def extract(self, workbook: Workbook, ctx: PipelineContext) -> FileMeta:
        ...


@runtime_checkable
class RegionDetector(Protocol):
    def detect(self, sheet: Sheet, ctx: PipelineContext) -> Optional[DataRegion]:
        ...


@runtime_checkable
class HeaderDetector(Protocol):
    def detect(
        self, region: DataRegion, ctx: PipelineContext
    ) -> Sequence[HeaderCandidate]:
        ...


@runtime_checkable
class ColumnMapper(Protocol):
    def map(
        self,
        header: HeaderCandidate,
        region: DataRegion,
        ctx: PipelineContext,
        profile: Optional[SupplierProfile] = None,
    ) -> ColumnPlan:
        ...


@runtime_checkable
class RowExtractor(Protocol):
    def extract(
        self,
        region: DataRegion,
        plan: ColumnPlan,
        ctx: PipelineContext,
    ) -> Iterable[RawRow]:
        ...


@runtime_checkable
class Normalizer(Protocol):
    def normalize(
        self,
        rows: Iterable[RawRow],
        plan: ColumnPlan,
        meta: FileMeta,
        ctx: PipelineContext,
    ) -> Iterable[ParsedItem]:
        ...


@runtime_checkable
class Validator(Protocol):
    def validate(
        self,
        items: Iterable[ParsedItem],
        ctx: PipelineContext,
    ) -> tuple[Sequence[ParsedItem], Sequence[ParsedItem]]:
        """Возвращает (valid, invalid)."""
        ...


@runtime_checkable
class Deduplicator(Protocol):
    def dedupe(
        self,
        items: Sequence[ParsedItem],
        ctx: PipelineContext,
    ) -> Sequence[ParsedItem]:
        ...


# ---------------------------------------------------------------------------
# Pipeline-фасад
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PipelineStages:
    loader: Loader
    sheet_classifier: SheetClassifier
    meta_extractor: MetaExtractor
    region_detector: RegionDetector
    header_detector: HeaderDetector
    column_mapper: ColumnMapper
    row_extractor: RowExtractor
    normalizer: Normalizer
    validator: Validator
    deduplicator: Deduplicator


@runtime_checkable
class Pipeline(Protocol):
    stages: PipelineStages

    def run(self, raw_file: RawFile, ctx: PipelineContext) -> ParseResult:
        ...


# ---------------------------------------------------------------------------
# Ошибки уровня стадии
# ---------------------------------------------------------------------------


class PipelineStageError(Exception):
    code: str = "pipeline_stage_error"


class FileLoadError(PipelineStageError):
    code = "file_load_error"


class SheetClassifierError(PipelineStageError):
    code = "no_data_sheets"


class ColumnMapperError(PipelineStageError):
    code = "mandatory_fields_missing"


__all__ = [
    "Field",
    "FormatType",
    "CandidateSource",
    "RawFile",
    "MergedRange",
    "Sheet",
    "Workbook",
    "SheetVerdict",
    "FileMeta",
    "DataRegion",
    "HeaderCandidate",
    "Candidate",
    "ColumnPlan",
    "RawRow",
    "ParseWarning",
    "ParseError",
    "ParsedItem",
    "ParseResult",
    "SupplierColumnMapping",
    "SupplierProfileHint",
    "PipelineConfig",
    "TelemetryEvent",
    "TelemetrySink",
    "FieldLexicon",
    "FormatLexicon",
    "CurrencyLexicon",
    "VolumePattern",
    "VolumeLexicon",
    "SupplierHintEntry",
    "SupplierHints",
    "Lexicons",
    "SupplierProfile",
    "ProfileRegistry",
    "PipelineContext",
    "Loader",
    "SheetClassifier",
    "MetaExtractor",
    "RegionDetector",
    "HeaderDetector",
    "ColumnMapper",
    "RowExtractor",
    "Normalizer",
    "Validator",
    "Deduplicator",
    "PipelineStages",
    "Pipeline",
    "PipelineStageError",
    "FileLoadError",
    "SheetClassifierError",
    "ColumnMapperError",
]
