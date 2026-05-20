"""
Стадии V2 pipeline.
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
from django.conf import settings

from parser_app.infrastructure.config.column_config_loader import get_field_patterns
from parser_app.services.column_content_scoring import build_column_samples
from parser_app.services.column_scoring import (
    build_mapping_from_keywords,
    score_header_for_field,
    score_header_row,
)
from parser_app.pipeline_v2.row_extractor import V2RowExtractor

CONTENT_SAMPLE_ROWS = 50


def _field_patterns() -> Dict[str, List[str]]:
    patterns = get_field_patterns() or {}
    patterns.setdefault("sku", ["артикул", "sku", "код"])
    return patterns


class LoaderStage:
    def _resolve_file_path(self, file_path: str) -> str:
        candidate = Path(file_path)
        if candidate.exists():
            return str(candidate)

        probes = [
            Path.cwd() / file_path,
            Path(getattr(settings, "BASE_DIR", Path.cwd())) / file_path,
            Path(getattr(settings, "MEDIA_ROOT", Path.cwd())) / file_path,
            Path(getattr(settings, "MEDIA_ROOT", Path.cwd())) / candidate.name,
        ]
        for p in probes:
            if p.exists():
                return str(p)
        return file_path

    def run(self, file_path: str) -> Dict[str, Any]:
        resolved = self._resolve_file_path(file_path)
        excel_file = pd.ExcelFile(resolved, engine="openpyxl")
        return {"file_path": resolved, "sheet_names": excel_file.sheet_names, "excel_file": excel_file}


class HeaderDetectorStage:
    def _score_header_row(self, row_values: List[str]) -> float:
        return score_header_row(row_values, _field_patterns())

    def run(self, workbook: Dict[str, Any]) -> Dict[str, Any]:
        headers: Dict[str, int] = {}
        diagnostics: Dict[str, Dict[str, Any]] = {}
        excel_file = workbook.get("excel_file")

        for sheet in workbook.get("sheet_names", []):
            df = pd.read_excel(excel_file, sheet_name=sheet, header=None, nrows=10)
            if df.empty:
                headers[sheet] = 0
                diagnostics[sheet] = {"header_row": 0, "score": 0.0}
                continue

            best_idx = 0
            best_score = float("-inf")
            for idx in range(min(8, len(df))):
                row_values = [str(v) for v in df.iloc[idx].fillna("").tolist()]
                row_score = self._score_header_row(row_values)
                if row_score > best_score:
                    best_score = row_score
                    best_idx = idx

            headers[sheet] = int(best_idx)
            diagnostics[sheet] = {"header_row": int(best_idx), "score": round(float(best_score), 3)}

        workbook["header_rows"] = headers
        workbook["header_diagnostics"] = diagnostics
        return workbook


class ColumnMapperStage:
    def __init__(self, field_patterns: Dict[str, List[str]] | None = None):
        self.field_patterns = field_patterns or _field_patterns()
        self.keyword_weights = None

    def _score_header_for_field(self, header: str, field_name: str) -> float:
        keywords = self.field_patterns.get(field_name, [])
        return score_header_for_field(header, field_name, keywords)

    def _map_for_sheet(
        self,
        headers: List[str],
        column_samples: Dict[int, List[str]] | None = None,
    ) -> Tuple[Dict[str, int], Dict[str, List[Dict[str, Any]]]]:
        keyword_weights = getattr(self, "keyword_weights", None)
        mapping = build_mapping_from_keywords(
            headers,
            self.field_patterns,
            keyword_weights=keyword_weights,
            column_samples=column_samples,
        )

        candidates: Dict[str, List[Dict[str, Any]]] = {}
        for field in self.field_patterns:
            scored: List[Tuple[float, int, str]] = []
            for idx, header in enumerate(headers):
                s = self._score_header_for_field(header, field)
                if field in (keyword_weights or {}):
                    s *= float(keyword_weights[field])
                scored.append((s, idx, header))
            scored.sort(key=lambda x: x[0], reverse=True)
            candidates[field] = [
                {"column_index": i, "header": h, "score": round(float(s), 3)}
                for s, i, h in scored[:3]
                if s > 0
            ]

        return mapping, candidates

    def run(self, workbook: Dict[str, Any]) -> Dict[str, Any]:
        excel_file = workbook.get("excel_file")
        header_rows = workbook.get("header_rows", {})
        sheet_mappings: Dict[str, Dict[str, int]] = {}
        sheet_candidates: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        confidence_by_sheet: Dict[str, float] = {}
        content_used: Dict[str, bool] = {}

        for sheet in workbook.get("sheet_names", []):
            header_row = int(header_rows.get(sheet, 0))
            nrows = header_row + 1 + CONTENT_SAMPLE_ROWS
            df = pd.read_excel(excel_file, sheet_name=sheet, header=None, nrows=nrows)
            if df.empty or header_row >= len(df):
                continue

            raw_headers = [str(v).strip() for v in df.iloc[header_row].fillna("").tolist()]
            column_samples = None
            if header_row + 1 < len(df):
                body = df.iloc[header_row + 1 :].reset_index(drop=True)
                column_samples = build_column_samples(body, start_row=0, max_rows=CONTENT_SAMPLE_ROWS)
                content_used[sheet] = bool(column_samples)

            mapping, candidates = self._map_for_sheet(raw_headers, column_samples=column_samples)
            sheet_mappings[sheet] = mapping
            sheet_candidates[sheet] = candidates

            top_scores = []
            for field, opts in candidates.items():
                if not opts:
                    continue
                top_scores.append(opts[0]["score"])
            confidence_by_sheet[sheet] = round(sum(top_scores) / len(top_scores), 3) if top_scores else 0.0

        workbook["column_mapping_status"] = "scored_with_content"
        workbook["column_mappings"] = sheet_mappings
        workbook["column_mapping_candidates"] = sheet_candidates
        workbook["column_mapping_confidence"] = confidence_by_sheet
        workbook["column_content_scoring_used"] = content_used
        return workbook


class RowExtractorStage:
    def __init__(self):
        self._extractor = V2RowExtractor()

    def run(self, workbook: Dict[str, Any], parse_kwargs: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._extractor.extract(workbook, parse_kwargs)
