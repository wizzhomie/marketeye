"""Deterministic tests for the CSV export of the price history."""

from __future__ import annotations

import csv
import io
import unittest

import export
import storage

DATA = storage.load_demo()


class HistoryCsvTests(unittest.TestCase):
    def setUp(self):
        self.text = export.history_csv(DATA)
        self.rows = list(csv.reader(io.StringIO(self.text)))

    def test_header_row(self):
        self.assertEqual(self.rows[0], export.HEADER)

    def test_one_row_per_day_product_competitor(self):
        expected = len(DATA["history"]) * len(DATA["products"]) * len(DATA["competitors"])
        self.assertEqual(len(self.rows) - 1, expected)
        self.assertEqual(len(self.rows), 226)

    def test_first_row_matches_the_fixture(self):
        day = DATA["history"][0]
        product = DATA["products"][0]
        competitor = DATA["competitors"][0]
        self.assertEqual(
            self.rows[1],
            [
                day["date"],
                product["id"],
                product["name"],
                competitor,
                str(day["prices"][product["id"]][competitor]),
                DATA["currency"],
                str(DATA["ourPrices"][product["id"]]),
            ],
        )

    def test_amounts_do_not_end_in_a_trailing_zero(self):
        for row in self.rows[1:]:
            self.assertNotIn(".0", row[4], row)
            self.assertNotIn(".0", row[6], row)

    def test_last_row_is_the_latest_day(self):
        self.assertEqual(self.rows[-1][0], DATA["history"][-1]["date"])

    def test_file_uses_plain_newlines(self):
        self.assertTrue(self.text.endswith("\n"))
        self.assertNotIn("\r", self.text)

    def test_comma_in_a_name_survives_the_export(self):
        data = {
            "currency": "RUB",
            "ourPrices": {"cement": 399},
            "products": [{"id": "cement", "name": "Cement M500, 50 kg"}],
            "competitors": ["StroyBaza"],
            "history": [
                {"date": "2 November 2026", "prices": {"cement": {"StroyBaza": 430.0}}}
            ],
        }
        text = export.history_csv(data)
        self.assertIn('"Cement M500, 50 kg"', text)
        rows = list(csv.reader(io.StringIO(text)))
        self.assertEqual(rows[1][2], "Cement M500, 50 kg")


class FileNameTests(unittest.TestCase):
    def test_filename_uses_the_last_history_day(self):
        self.assertEqual(export.suggest_filename(DATA), "marketeye-history-2026-11-16.csv")

    def test_filename_falls_back_for_odd_dates(self):
        data = {"history": [{"date": "someday"}]}
        self.assertEqual(export.suggest_filename(data), "marketeye-history-latest.csv")


if __name__ == "__main__":
    unittest.main()
