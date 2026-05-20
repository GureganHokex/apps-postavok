"""
Извлечение строк прайса в V2 без вызова ExcelParser.parse().
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import pandas as pd

from parser_app.parsers.excel_parser import ExcelParser
from parser_app.parsers.supplier_profiles import SupplierType

logger = logging.getLogger(__name__)

# Листы без таблицы позиций
_SKIP_SHEET_KEYWORDS = (
    "инструк", "instruction", "readme", "условия", "доставка",
    "контакт", "contact", "оглавление",
)


def _should_skip_sheet(sheet_name: str) -> bool:
    lower = (sheet_name or "").lower()
    return any(k in lower for k in _SKIP_SHEET_KEYWORDS)


def _resolve_supplier_type(parse_kwargs: Dict[str, Any]) -> Optional[SupplierType]:
    raw = parse_kwargs.get("supplier_type")
    if raw == "distributor":
        return SupplierType.DISTRIBUTOR
    if raw == "brewery":
        return SupplierType.BREWERY
    if isinstance(raw, SupplierType):
        return raw
    return None


class V2RowExtractor:
    """
    Читает листы по плану колонок из workbook (header_rows + column_mappings),
    извлекает позиции через ExcelParser._parse_dataframe (без полного parse()).
    """

    def extract(self, workbook: Dict[str, Any], parse_kwargs: Dict[str, Any]) -> List[Dict[str, Any]]:
        excel_file = workbook.get("excel_file")
        if excel_file is None:
            return []

        file_path = workbook.get("file_path", "")
        parser = ExcelParser(file_path)
        parser._supplier_column_mapping = parse_kwargs.get("supplier_column_mapping")
        parser._supplier_keyword_weights = parse_kwargs.get("supplier_keyword_weights")

        supplier_type = _resolve_supplier_type(parse_kwargs)
        brewery_name = parse_kwargs.get("brewery_name")
        characteristics: Dict[str, Any] = {}
        if brewery_name and supplier_type == SupplierType.BREWERY:
            characteristics = {"single_brewery_name": brewery_name}

        header_rows = workbook.get("header_rows", {})
        sheet_mappings = workbook.get("column_mappings", {})
        all_items: List[Dict[str, Any]] = []

        for sheet_name in workbook.get("sheet_names", []):
            if _should_skip_sheet(sheet_name):
                logger.debug("V2 skip sheet: %s", sheet_name)
                continue

            header_row = int(header_rows.get(sheet_name, 0))
            col_mapping = dict(sheet_mappings.get(sheet_name) or {})
            if not col_mapping:
                logger.info("V2: нет маппинга колонок для листа %s", sheet_name)
                continue

            try:
                df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
            except Exception as exc:
                logger.warning("V2: не удалось прочитать лист %s: %s", sheet_name, exc)
                continue

            if df.empty or header_row >= len(df):
                continue

            headers = [
                str(v).strip() if pd.notna(v) else ""
                for v in df.iloc[header_row].fillna("").tolist()
            ]
            df_body = df.iloc[header_row + 1 :].reset_index(drop=True)
            # Именованные колонки — для пост-валидации и multi-price в legacy _parse_dataframe
            df_body.columns = [
                headers[i] if i < len(headers) and headers[i] else f"col_{i}"
                for i in range(len(df_body.columns))
            ]

            sheet_items = parser._parse_dataframe(
                df_body,
                sheet_name,
                col_mapping=col_mapping,
                supplier_type=supplier_type or SupplierType.UNKNOWN,
                characteristics=characteristics,
                brewery_name=brewery_name,
                supplier_column_mapping=None,
            )
            for item in sheet_items:
                loc = item.get("raw_source_location") or {}
                loc.setdefault("sheet", sheet_name)
                loc["pipeline"] = "v2"
                item["raw_source_location"] = loc
            logger.info(
                "V2 лист %s: header_row=%s, mapping=%s, items=%s",
                sheet_name,
                header_row,
                list(col_mapping.keys()),
                len(sheet_items),
            )
            all_items.extend(sheet_items)

        logger.info(
            "V2RowExtractor: file=%s items=%s sheets=%s",
            os.path.basename(file_path),
            len(all_items),
            len(workbook.get("sheet_names", [])),
        )
        return all_items
