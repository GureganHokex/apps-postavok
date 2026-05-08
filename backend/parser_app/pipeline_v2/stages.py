"""
Скелет стадий V2 pipeline.
"""

from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from parser_app.parsers import ExcelParser


class LoaderStage:
    def run(self, file_path: str) -> Dict[str, Any]:
        excel_file = pd.ExcelFile(file_path, engine="openpyxl")
        return {"file_path": file_path, "sheet_names": excel_file.sheet_names}


class HeaderDetectorStage:
    def run(self, workbook: Dict[str, Any]) -> Dict[str, Any]:
        # Временный безопасный baseline: считаем 1-ю строку заголовком по каждому листу.
        headers = {sheet: 0 for sheet in workbook.get("sheet_names", [])}
        workbook["header_rows"] = headers
        return workbook


class ColumnMapperStage:
    def run(self, workbook: Dict[str, Any]) -> Dict[str, Any]:
        # Placeholder для будущего score/voting маппинга.
        workbook["column_mapping_status"] = "bridge"
        return workbook


class RowExtractorStage:
    def run(self, workbook: Dict[str, Any], parse_kwargs: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Bridge: реальное извлечение пока делегируем legacy-парсеру.
        parser = ExcelParser(workbook["file_path"])
        return parser.parse(**parse_kwargs)

