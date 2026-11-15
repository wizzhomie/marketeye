"""Deterministic tests for the demo data and the server-side alert rules.

Run from the project root:

    .venv/bin/python -m unittest discover -s tests -v
"""

from __future__ import annotations

import unittest

import alerts
import storage

DATA = storage.load_demo()


class FixtureTests(unittest.TestCase):
    def test_snapshots_are_the_last_history_days(self):
        self.assertEqual(
            [day["date"] for day in DATA["snapshots"]],
            [day["date"] for day in DATA["history"][-3:]],
        )

    def test_history_is_fifteen_unique_days(self):
        dates = [day["date"] for day in DATA["history"]]
        self.assertEqual(len(dates), 15)
        self.assertEqual(len(set(dates)), 15)

    def test_database_round_trip_matches_the_fixture(self):
        connection = storage.connect(":memory:")
        try:
            storage.init_db(connection)
            storage.seed(connection, DATA)
            self.assertEqual(storage.bootstrap(connection), DATA)
        finally:
            connection.close()

    def test_product_history_window(self):
        connection = storage.connect(":memory:")
        try:
            storage.init_db(connection)
            storage.seed(connection, DATA)
            result = storage.product_history(connection, "cement", days=14)
            self.assertEqual(len(result["days"]), 14)
            self.assertEqual(result["days"][-1]["date"], "16 November 2026")
            self.assertEqual(result["ourPrice"], 399)
            with self.assertRaises(KeyError):
                storage.product_history(connection, "unknown")
        finally:
            connection.close()


class AlertRuleTests(unittest.TestCase):
    def test_default_rules(self):
        result = alerts.evaluate(DATA)
        self.assertEqual(result["date"], "15 November 2026")
        self.assertEqual(result["previousDate"], "14 November 2026")
        self.assertEqual([alert["kind"] for alert in result["alerts"]], ["below", "drop"])
        self.assertEqual(result["stats"]["alerts"], 2)
        self.assertEqual(result["stats"]["products"], 1)
        self.assertIn("below my price · price drop ≥ 5%", result["digest"])
        self.assertIn(
            "- MasterStroy · Cement M500 · 50 kg — 370 RUB, 7% below our 399 RUB",
            result["digest"],
        )
        self.assertEqual(
            result["recent"],
            [
                {"date": "15 November 2026", "alerts": 2},
                {"date": "14 November 2026", "alerts": 1},
                {"date": "13 November 2026", "alerts": 1},
            ],
        )

    def test_higher_threshold_filters_the_drop(self):
        rules = [
            {"id": "below", "enabled": True},
            {"id": "drop", "enabled": True, "threshold": 15},
        ]
        result = alerts.evaluate(DATA, rules)
        self.assertEqual([alert["kind"] for alert in result["alerts"]], ["below"])

    def test_switches_and_rise_threshold(self):
        rules = [
            {"id": "below", "enabled": False},
            {"id": "drop", "enabled": True, "threshold": 5},
            {"id": "rise", "enabled": True, "threshold": 1},
        ]
        result = alerts.evaluate(DATA, rules)
        self.assertEqual(len(result["alerts"]), 3)
        self.assertEqual(result["stats"]["products"], 3)
        self.assertIn("price drop ≥ 5% · price rise ≥ 1%", result["digest"])

    def test_all_rules_off(self):
        rules = [{"id": rule["id"], "enabled": False} for rule in DATA["alertRules"]]
        result = alerts.evaluate(DATA, rules)
        self.assertEqual(result["alerts"], [])
        self.assertEqual(result["stats"]["alerts"], 0)
        self.assertIn("No alerts today. Nothing to report.", result["digest"])

    def test_snapshot_parameter_and_order(self):
        result = alerts.evaluate(DATA, None, 2)
        self.assertEqual(result["date"], "16 November 2026")
        # StroyBaza also undercuts us on cement that day, so two "below" matches.
        self.assertEqual(
            [alert["kind"] for alert in result["alerts"]],
            ["below", "below", "drop"],
        )

    def test_threshold_is_clamped(self):
        result = alerts.evaluate(DATA, [{"id": "drop", "enabled": True, "threshold": 999}])
        self.assertEqual(result["rules"][1]["threshold"], 50)
        result = alerts.evaluate(DATA, [{"id": "drop", "enabled": True, "threshold": 0}])
        self.assertEqual(result["rules"][1]["threshold"], 1)

    def test_invalid_rules_are_rejected(self):
        with self.assertRaises(ValueError):
            alerts.evaluate(DATA, [{"id": "drop", "threshold": "abc"}])
        with self.assertRaises(ValueError):
            alerts.evaluate(DATA, "not-a-list")

    def test_unknown_rule_ids_are_ignored(self):
        result = alerts.evaluate(DATA, [{"id": "nope", "enabled": True}])
        self.assertEqual(len(result["rules"]), len(DATA["alertRules"]))

    def test_percent_text(self):
        self.assertEqual(alerts.percent_text(12.4), "12")
        self.assertEqual(alerts.percent_text(0.46), "0.5")
        self.assertEqual(alerts.percent_text(2.0), "2")


if __name__ == "__main__":
    unittest.main()
