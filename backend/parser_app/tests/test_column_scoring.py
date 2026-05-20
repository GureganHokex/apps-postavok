"""Unit tests for flexible column mapping."""

from django.test import SimpleTestCase

from parser_app.services.column_scoring import (
    build_mapping_from_keywords,
    score_header_for_field,
)
from parser_app.services.column_mapping_registry import _merge_layers


class ColumnScoringTests(SimpleTestCase):
    def test_exact_header_match(self):
        score = score_header_for_field("Название товара", "beer_name", ["название", "наименование"])
        self.assertGreater(score, 0)

    def test_fuzzy_match_typo(self):
        score = score_header_for_field("Наименоване", "beer_name", ["наименование"])
        self.assertGreaterEqual(score, 3.0)

    def test_build_mapping_resolves_columns(self):
        headers = ["Пивоварня", "Название", "Цена, руб", "Описание"]
        patterns = {
            "brewery": ["пивоварня"],
            "beer_name": ["название"],
            "price": ["цена"],
            "description": ["описание"],
        }
        mapping = build_mapping_from_keywords(headers, patterns)
        self.assertEqual(mapping.get("beer_name"), 1)
        self.assertEqual(mapping.get("price"), 2)

    def test_manual_weight_wins_ambiguous(self):
        headers = ["Товар", "Наименование"]
        patterns = {"beer_name": ["товар", "наименование"]}
        mapping_default = build_mapping_from_keywords(headers, patterns)
        mapping_weighted = build_mapping_from_keywords(
            headers,
            patterns,
            keyword_weights={"beer_name": 2.0},
        )
        self.assertEqual(mapping_default.get("beer_name"), mapping_weighted.get("beer_name"))

    def test_merge_layers_dedupes(self):
        merged = _merge_layers(
            {"price": ["цена"]},
            {"price": ["Цена за шт"], "beer_name": ["название"]},
        )
        self.assertIn("цена", [k.lower() for k in merged["price"]])
        self.assertIn("beer_name", merged)
