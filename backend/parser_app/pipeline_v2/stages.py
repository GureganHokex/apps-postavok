"""
Скелет стадий V2 pipeline.
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
from django.conf import settings

from parser_app.parsers import ExcelParser


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
    HEADER_ALIASES = {
        "beer_name": ["название", "наименование", "beer", "name", "позиция", "товар"],
        "brewery": ["пивовар", "brewery", "бренд", "производитель"],
        "style": ["стиль", "style", "тип", "сорт"],
        "abv": ["abv", "крепост", "alc", "алк", "%"],
        "price": ["цена", "price", "стоим", "руб"],
        "volume": ["объем", "объём", "volume", "литр", "ml", "л"],
        "stock": ["остат", "stock", "налич", "кол-во", "количество"],
        "description": ["описан", "description", "коммент", "примечан"],
        "sku": ["артикул", "sku", "код"],
    }

    def _score_header_row(self, row_values: List[str]) -> float:
        score = 0.0
        for value in row_values:
            cell = str(value or "").strip().lower()
            if not cell:
                continue
            if any(token in cell for aliases in self.HEADER_ALIASES.values() for token in aliases):
                score += 2.0
            if len(cell) <= 40:
                score += 0.5
            if any(ch.isdigit() for ch in cell):
                score -= 0.8
        return score

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
    FIELD_PATTERNS = {
        "beer_name": ["название", "наименование", "beer", "name", "позиция", "товар"],
        "brewery": ["пивовар", "brewery", "бренд", "производитель"],
        "style": ["стиль", "style", "тип", "сорт"],
        "abv": ["abv", "крепост", "alc", "алк", "%"],
        "price": ["цена", "price", "стоим", "руб"],
        "volume": ["объем", "объём", "volume", "литр", "ml", "л"],
        "stock": ["остат", "stock", "налич", "кол-во", "количество"],
        "description": ["описан", "description", "коммент", "примечан"],
        "sku": ["артикул", "sku", "код"],
    }

    def _score_header_for_field(self, header: str, field_name: str) -> float:
        h = (header or "").strip().lower()
        if not h:
            return 0.0

        score = 0.0
        for token in self.FIELD_PATTERNS[field_name]:
            if token in h:
                score += 5.0
        # Антишум: description не должен вытеснять beer_name.
        if field_name == "beer_name" and any(x in h for x in ("описан", "description", "стиль", "style", "коммент")):
            score -= 6.0
        if field_name == "description" and any(x in h for x in ("описан", "description", "коммент", "примечан")):
            score += 2.0
        return score

    def _map_for_sheet(self, headers: List[str]) -> Tuple[Dict[str, int], Dict[str, List[Dict[str, Any]]]]:
        mapping: Dict[str, int] = {}
        candidates: Dict[str, List[Dict[str, Any]]] = {}
        used_cols = set()

        for field in self.FIELD_PATTERNS:
            scored: List[Tuple[float, int, str]] = []
            for idx, header in enumerate(headers):
                scored.append((self._score_header_for_field(header, field), idx, header))
            scored.sort(key=lambda x: x[0], reverse=True)
            top = [{"column_index": i, "header": h, "score": round(float(s), 3)} for s, i, h in scored[:3] if s > 0]
            candidates[field] = top

            for s, i, _h in scored:
                if s <= 0 or i in used_cols:
                    continue
                mapping[field] = i
                used_cols.add(i)
                break

        return mapping, candidates

    def run(self, workbook: Dict[str, Any]) -> Dict[str, Any]:
        excel_file = workbook.get("excel_file")
        header_rows = workbook.get("header_rows", {})
        sheet_mappings: Dict[str, Dict[str, int]] = {}
        sheet_candidates: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        confidence_by_sheet: Dict[str, float] = {}

        for sheet in workbook.get("sheet_names", []):
            header_row = int(header_rows.get(sheet, 0))
            df = pd.read_excel(excel_file, sheet_name=sheet, header=None, nrows=header_row + 1)
            if df.empty or header_row >= len(df):
                continue
            raw_headers = [str(v).strip() for v in df.iloc[header_row].fillna("").tolist()]
            mapping, candidates = self._map_for_sheet(raw_headers)
            sheet_mappings[sheet] = mapping
            sheet_candidates[sheet] = candidates

            top_scores = []
            for field, opts in candidates.items():
                if not opts:
                    continue
                top_scores.append(opts[0]["score"])
            confidence_by_sheet[sheet] = round(sum(top_scores) / len(top_scores), 3) if top_scores else 0.0

        workbook["column_mapping_status"] = "scored"
        workbook["column_mappings"] = sheet_mappings
        workbook["column_mapping_candidates"] = sheet_candidates
        workbook["column_mapping_confidence"] = confidence_by_sheet
        return workbook


class RowExtractorStage:
    def run(self, workbook: Dict[str, Any], parse_kwargs: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Bridge: реальное извлечение пока делегируем legacy-парсеру.
        parser = ExcelParser(workbook["file_path"])
        return parser.parse(**parse_kwargs)

