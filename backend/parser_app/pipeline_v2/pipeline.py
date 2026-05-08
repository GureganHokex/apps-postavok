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

    На данном этапе выполняет безопасный bridge к существующему ExcelParser,
    чтобы можно было включать флагом и собирать telemetry без регрессий.
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.loader = LoaderStage()
        self.header_detector = HeaderDetectorStage()
        self.column_mapper = ColumnMapperStage()
        self.row_extractor = RowExtractorStage()

    def run(self, **parse_kwargs: Dict[str, Any]) -> ParseResult:
        try:
            workbook = self.loader.run(self.file_path)
            workbook = self.header_detector.run(workbook)
            workbook = self.column_mapper.run(workbook)
            items = self.row_extractor.run(workbook, parse_kwargs)
            return ParseResult(
                status=ParseStatus.COMPLETED,
                items=items,
                warnings=[
                    ParseIssue(
                        code="v2_bridge_mode",
                        message="ExcelPipelineV2 работает в bridge-режиме через legacy parser",
                        severity="warning",
                    )
                ],
                meta={
                    "pipeline_version": "v2-bridge",
                    "sheet_count": len(workbook.get("sheet_names", [])),
                    "header_rows": workbook.get("header_rows", {}),
                    "header_diagnostics": workbook.get("header_diagnostics", {}),
                    "column_mappings": workbook.get("column_mappings", {}),
                    "column_mapping_candidates": workbook.get("column_mapping_candidates", {}),
                    "column_mapping_confidence": workbook.get("column_mapping_confidence", {}),
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
                meta={"pipeline_version": "v2-bridge"},
            )

