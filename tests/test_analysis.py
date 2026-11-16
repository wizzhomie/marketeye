"""Deterministic tests for the server-side competitor analysis.

Run from the project root:

    .venv/bin/python -m unittest discover -s tests -v
"""

from __future__ import annotations

import unittest

import analysis
import storage

DATA = storage.load_demo()


class AnalysisFixtureTests(unittest.TestCase):
    def setUp(self):
        self.result = analysis.evaluate(DATA)

    def test_uses_the_demo_day(self):
        self.assertEqual(self.result["date"], "15 November 2026")
        self.assertEqual(self.result["previousDate"], "14 November 2026")
        self.assertEqual(self.result["currency"], "RUB")

    def test_window_is_fourteen_days_ending_on_the_demo_day(self):
        window = self.result["window"]
        self.assertEqual(window["days"], 14)
        self.assertEqual(window["start"], "2 November 2026")
        self.assertEqual(window["end"], "15 November 2026")

    def test_competitors_keep_the_fixture_order(self):
        self.assertEqual(
            [row["name"] for row in self.result["competitors"]],
            DATA["competitors"],
        )

    def test_price_index_and_counts(self):
        rows = {row["name"]: row for row in self.result["competitors"]}
        self.assertEqual(rows["StroyBaza"]["index"], 2.4)
        self.assertEqual(rows["StroyBaza"]["below"], 0)
        self.assertEqual(rows["StroyBaza"]["above"], 4)
        self.assertEqual(rows["StroyBaza"]["equal"], 1)

        self.assertEqual(rows["MasterStroy"]["index"], 0.0)
        self.assertEqual(rows["MasterStroy"]["below"], 1)
        self.assertEqual(rows["MasterStroy"]["above"], 3)
        self.assertEqual(rows["MasterStroy"]["equal"], 1)
        self.assertEqual(rows["MasterStroy"]["avgBelow"], 7.3)

        self.assertEqual(rows["GlavSnab"]["index"], 3.9)
        self.assertEqual(rows["GlavSnab"]["below"], 0)
        self.assertEqual(rows["GlavSnab"]["above"], 5)

    def test_cheapest_counts_and_main_competitor(self):
        rows = {row["name"]: row for row in self.result["competitors"]}
        self.assertEqual(rows["StroyBaza"]["cheapest"], 1)
        self.assertEqual(rows["MasterStroy"]["cheapest"], 2)
        self.assertEqual(rows["GlavSnab"]["cheapest"], 2)
        self.assertEqual(self.result["main"]["name"], "MasterStroy")
        self.assertEqual(self.result["main"]["below"], 1)

    def test_trend_has_a_point_per_day_and_moves_over_the_window(self):
        for row in self.result["competitors"]:
            trend = row["trend"]
            self.assertEqual(len(trend), 14)
            self.assertEqual(trend[-1]["date"], "15 November 2026")
            self.assertEqual(trend[-1]["index"], row["index"])
        rows = {row["name"]: row for row in self.result["competitors"]}
        self.assertEqual(rows["StroyBaza"]["change"], -0.7)
        self.assertEqual(rows["MasterStroy"]["change"], -3.1)
        self.assertEqual(rows["GlavSnab"]["change"], 0.1)

    def test_below_pairs_are_sorted_worst_first(self):
        below = self.result["below"]
        self.assertEqual(len(below), 1)
        pair = below[0]
        self.assertEqual(pair["competitor"], "MasterStroy")
        self.assertEqual(pair["productName"], "Cement M500 · 50 kg")
        self.assertEqual(pair["price"], 370)
        self.assertEqual(pair["ourPrice"], 399)
        self.assertEqual(pair["percent"], -7.3)

    def test_products_carry_cells_and_spread(self):
        products = {row["id"]: row for row in self.result["products"]}
        self.assertEqual(len(products), 5)
        cement = products["cement"]
        self.assertEqual(cement["ourPrice"], 399)
        self.assertEqual(cement["cheapest"], {"competitor": "MasterStroy", "price": 370})
        self.assertEqual(cement["dearest"], {"competitor": "GlavSnab", "price": 430})
        self.assertEqual(cement["spread"], 16.2)
        self.assertTrue(cement["belowUs"])
        self.assertEqual(
            [cell["competitor"] for cell in cement["cells"]],
            DATA["competitors"],
        )
        self.assertFalse(products["brick"]["belowUs"])

    def test_stats(self):
        stats = self.result["stats"]
        self.assertEqual(stats["products"], 5)
        self.assertEqual(stats["competitors"], 3)
        self.assertEqual(stats["below"], 1)
        self.assertEqual(stats["biggestGap"], 7.3)
        self.assertEqual(stats["biggestGapProduct"], "Cement M500 · 50 kg")
        self.assertEqual(stats["widestSpread"], 16.2)
        self.assertEqual(stats["widestSpreadProduct"], "Cement M500")

    def test_insights_are_plain_sentences_without_the_model(self):
        insights = self.result["insights"]
        self.assertEqual(
            [item["kind"] for item in insights],
            ["main", "warn", "trend", "ok", "info"],
        )
        self.assertIn("MasterStroy", insights[0]["text"])
        self.assertIn("370 RUB", insights[1]["text"])
        self.assertIn("Cement M500", insights[4]["text"])


class AnalysisEdgeTests(unittest.TestCase):
    def test_snapshot_index_is_clamped(self):
        first = analysis.evaluate(DATA, snapshot_index=-5)
        last = analysis.evaluate(DATA, snapshot_index=99)
        self.assertEqual(first["date"], "14 November 2026")
        self.assertEqual(last["date"], "16 November 2026")

    def test_missing_data_is_rejected(self):
        with self.assertRaises(ValueError):
            analysis.evaluate({})
        broken = dict(DATA)
        broken["snapshots"] = []
        with self.assertRaises(ValueError):
            analysis.evaluate(broken)


if __name__ == "__main__":
    unittest.main()
