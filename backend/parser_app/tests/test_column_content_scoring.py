"""Tests for content-based column scoring."""

from django.test import SimpleTestCase

from parser_app.services.column_content_scoring import (
    score_column_content_for_field,
)
from parser_app.services.column_scoring import build_mapping_from_keywords


class ColumnContentScoringTests(SimpleTestCase):
    def test_price_column_numeric(self):
        values = ["450", "520", "380", "410", "490"]
        score = score_column_content_for_field(values, "price")
        self.assertGreaterEqual(score, 6.0)

    def test_beer_name_text_column(self):
        values = [
            "Paradox Berry Forward",
            "Alispiri Tomato Gose",
            "Back to Balance IPA",
        ]
        score = score_column_content_for_field(values, "beer_name")
        self.assertGreater(score, 3.0)

    def test_abv_column(self):
        values = ["5.2%", "6.0%", "4.8%", "5.5%"]
        score = score_column_content_for_field(values, "abv")
        self.assertGreater(score, 5.0)

    def test_content_disambiguates_price_vs_name(self):
        headers = ["Товар", "Сумма", "Примечание"]
        patterns = {
            "beer_name": ["товар", "название"],
            "price": ["сумма", "цена"],
        }
        samples = {
            0: ["Paradox IPA", "CBD Lager", "Two Peaks Stout"],
            1: ["450", "520", "380"],
            2: ["доставка кег", "минимальный заказ"],
        }
        mapping = build_mapping_from_keywords(
            headers, patterns, column_samples=samples
        )
        self.assertEqual(mapping.get("price"), 1)
        self.assertEqual(mapping.get("beer_name"), 0)
