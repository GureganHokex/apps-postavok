"""V2-пайплайн: стадийный скелет с bridge-извлечением."""

from typing import Any, Dict

from .contracts import ParseResult, ParseStatus, ParseIssue
from .stages import (
    LoaderStage,
    HeaderDetectorStage,
    ColumnMapperStage,
    RowExtractorStage,
)


class ExcelPipelineV2:
    """
    Скелет нового пайплайна.

    V2: детектор заголовков и маппинг колонок (заголовки + содержимое),
    извлечение строк — через _parse_dataframe без полного parse().
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.loader = LoaderStage()
        self.header_detector = HeaderDetectorStage()
        self.column_mapper = ColumnMapperStage()
        self.row_extractor = RowExtractorStage()

    def run(self, **parse_kwargs: Dict[str, Any]) -> ParseResult:
        try:
            supplier_mapping = parse_kwargs.get("supplier_column_mapping")
            keyword_weights = parse_kwargs.get("supplier_keyword_weights")
            if supplier_mapping:
                self.column_mapper = ColumnMapperStage(field_patterns=supplier_mapping)
            if keyword_weights:
                self.column_mapper.keyword_weights = keyword_weights

            workbook = self.loader.run(self.file_path)
            workbook = self.header_detector.run(workbook)
            workbook = self.column_mapper.run(workbook)
            items = self.row_extractor.run(workbook, parse_kwargs)
            warnings = []
            if not items:
                warnings.append(
                    ParseIssue(
                        code="v2_empty_result",
                        message="V2 не извлёк ни одной позиции — проверьте маппинг колонок",
                        severity="warning",
                    )
                )
            status = ParseStatus.COMPLETED if items else ParseStatus.PARTIAL
            return ParseResult(
                status=status,
                items=items,
                warnings=warnings,
                meta={
                    "pipeline_version": "v2-native",
                    "sheet_count": len(workbook.get("sheet_names", [])),
                    "header_rows": workbook.get("header_rows", {}),
                    "header_diagnostics": workbook.get("header_diagnostics", {}),
                    "column_mappings": workbook.get("column_mappings", {}),
                    "column_mapping_candidates": workbook.get("column_mapping_candidates", {}),
                    "column_mapping_confidence": workbook.get("column_mapping_confidence", {}),
                    "column_content_scoring_used": workbook.get("column_content_scoring_used", {}),
                },
            )
        except Exception as exc:
            return ParseResult(
                status=ParseStatus.FAILED,
                items=[],
                errors=[
                    ParseIssue(
                        code="v2_parse_failed",
                        message=str(exc),
                        severity="error",
                    )
                ],
                meta={"pipeline_version": "v2-native"},
            )

