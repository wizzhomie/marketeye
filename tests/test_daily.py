"""Deterministic tests for the daily check: digest text, digest files, schedule.

No network: the daily pass is tested with an injected collector and an in-memory
SQLite database, so these tests are as repeatable as the rest of the suite.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import daily
import storage

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 11, 15, 9, 0, tzinfo=timezone.utc)


def source(source_id="demo-cement", competitor="Demo Build Supply", product="Cement"):
    return {
        "id": source_id,
        "competitor": competitor,
        "product": product,
        "url": f"http://example.test/{source_id}",
        "profile": "demo_shop",
    }


def reading(
    price=349.0,
    currency="RUB",
    source_id="demo-cement",
    title="Portland cement M500, 50 kg",
    status="ok",
    note=None,
):
    return {
        "sourceId": source_id,
        "competitor": "Demo Build Supply",
        "product": "Portland cement M500, 50 kg",
        "url": f"http://127.0.0.1:8768/{source_id}",
        "profile": "demo_shop",
        "fetchedAt": "2026-11-15T09:00:00+00:00",
        "status": status,
        "title": title if status == "ok" else None,
        "price": price if status == "ok" else None,
        "currency": currency if status == "ok" else None,
        "rawValue": None,
        "note": note,
    }


class DigestTextTests(unittest.TestCase):
    def test_reports_a_drop_against_the_previous_check(self):
        entries = [
            {
                "source": source(),
                "reading": reading(349.0),
                "previous": reading(370.0),
            }
        ]
        text = daily.build_digest(entries, NOW, tick=1)
        self.assertIn("2026-11-15 09:00 UTC · 1 source", text)
        self.assertIn("349 RUB — 6% lower than the previous check (370 RUB)", text)
        self.assertIn("http://example.test/demo-cement", text)

    def test_flat_price_and_first_reading(self):
        flat = daily.build_digest(
            [{"source": source(), "reading": reading(349.0), "previous": reading(349.0)}],
            NOW,
            tick=2,
        )
        self.assertIn("349 RUB — no change since the previous check", flat)

        first = daily.build_digest(
            [{"source": source(), "reading": reading(349.0), "previous": None}],
            NOW,
            tick=2,
        )
        self.assertIn("349 RUB — first reading", first)

    def test_error_keeps_the_reason_and_is_not_a_price(self):
        failed = reading(
            source_id="books-attic",
            status="error",
            note="the site answered HTTP 500",
            title=None,
            price=None,
            currency=None,
        )
        text = daily.build_digest(
            [{"source": source("books-attic"), "reading": failed, "previous": None}],
            NOW,
            tick=3,
        )
        self.assertIn("Errors (1):", text)
        self.assertIn("— the site answered HTTP 500", text)
        self.assertIn("0 pages read, 1 error. Demo shop tick: 3.", text)

    def test_counts_both_kinds(self):
        entries = [
            {"source": source(), "reading": reading(349.0), "previous": reading(370.0)},
            {
                "source": source("books-attic"),
                "reading": reading(
                    source_id="books-attic",
                    status="error",
                    note="the page could not be read",
                    title=None,
                    price=None,
                    currency=None,
                ),
                "previous": None,
            },
        ]
        text = daily.build_digest(entries, NOW, tick=4)
        self.assertIn("2 sources", text)
        self.assertIn("1 page read, 1 error. Demo shop tick: 4.", text)


class DigestFilesTests(unittest.TestCase):
    def test_write_and_read_the_latest_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = daily.write_digest("hello\n", NOW, tmp)
            self.assertEqual(path.name, "2026-11-15.txt")
            self.assertEqual(path.read_text(encoding="utf-8"), "hello\n")

            latest = daily.latest_digest(tmp)
            self.assertIsNotNone(latest)
            self.assertEqual(latest["digest"], "hello\n")
            self.assertEqual(latest["date"], "2026-11-15")
            self.assertEqual(latest["file"], "2026-11-15.txt")
            self.assertEqual(latest["count"], 1)

    def test_no_digests_yet(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(daily.latest_digest(tmp))

    def test_latest_is_the_newest_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            daily.write_digest("older\n", datetime(2026, 11, 14, 9, 0, tzinfo=timezone.utc), tmp)
            daily.write_digest("newer\n", NOW, tmp)
            latest = daily.latest_digest(tmp)
            self.assertEqual(latest["digest"], "newer\n")
            self.assertEqual(latest["count"], 2)

    def test_clear_removes_saved_digests(self):
        with tempfile.TemporaryDirectory() as tmp:
            daily.write_digest("one\n", NOW, tmp)
            daily.write_digest("two\n", datetime(2026, 11, 14, 9, 0, tzinfo=timezone.utc), tmp)
            self.assertEqual(daily.clear_digests(tmp), 2)
            self.assertIsNone(daily.latest_digest(tmp))


class ScheduleTests(unittest.TestCase):
    def test_default_time(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(daily.configured_at(), "09:00")

    def test_reads_the_environment(self):
        with mock.patch.dict(os.environ, {"MARKETEYE_DAILY_AT": "07:30"}):
            self.assertEqual(daily.configured_at(), "07:30")

    def test_falls_back_for_invalid_values(self):
        for value in ("", "9", "25:00", "09:75", "nope"):
            with mock.patch.dict(os.environ, {"MARKETEYE_DAILY_AT": value}):
                self.assertEqual(daily.configured_at(), "09:00", value)

    def test_is_due_after_the_configured_time(self):
        with mock.patch.dict(os.environ, {"MARKETEYE_DAILY_AT": "09:00"}):
            local = datetime(2026, 11, 15, 8, 59).astimezone()
            self.assertFalse(daily.is_due(local))
            local = datetime(2026, 11, 15, 9, 0).astimezone()
            self.assertTrue(daily.is_due(local))

    def test_next_run_rolls_over_to_tomorrow(self):
        with mock.patch.dict(os.environ, {"MARKETEYE_DAILY_AT": "09:00"}):
            before = datetime(2026, 11, 15, 8, 0).astimezone()
            expected = before.replace(hour=9, minute=0, second=0, microsecond=0)
            self.assertEqual(daily.next_run(before), expected.isoformat(timespec="seconds"))

            after = datetime(2026, 11, 15, 10, 0).astimezone()
            expected = (after + timedelta(days=1)).replace(
                hour=9, minute=0, second=0, microsecond=0
            )
            self.assertEqual(daily.next_run(after), expected.isoformat(timespec="seconds"))


class RunPassTests(unittest.TestCase):
    def setUp(self):
        self.connection = storage.connect(":memory:")
        storage.init_db(self.connection)
        self.addCleanup(self.connection.close)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _collect(self, *readings):
        return lambda: list(readings)

    def test_pass_stores_readings_advances_the_shop_and_writes_a_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = daily.run_pass(
                collect=self._collect(reading(349.0), reading(source_id="books-attic", price=51.77, currency="GBP")),
                now=NOW,
                digest_dir=tmp,
                connection=self.connection,
                advance=lambda: 3,
            )

            self.assertEqual(result["sources"], 2)
            self.assertEqual(result["read"], 2)
            self.assertEqual(result["errors"], 0)
            self.assertEqual(result["tick"], 3)
            self.assertEqual(result["file"], "2026-11-15.txt")
            self.assertIn("349 RUB", result["digest"])

            saved = Path(tmp) / "2026-11-15.txt"
            self.assertTrue(saved.is_file())
            self.assertEqual(saved.read_text(encoding="utf-8"), result["digest"])

            stored = storage.live_readings(self.connection, "demo-cement", limit=8)
            self.assertEqual([item["price"] for item in stored], [349.0])
            stored_books = storage.live_readings(self.connection, "books-attic", limit=8)
            self.assertEqual(stored_books[0]["currency"], "GBP")

    def test_second_pass_reports_the_move(self):
        previous = reading(370.0)
        storage.add_live_reading(self.connection, previous)
        result = daily.run_pass(
            collect=self._collect(reading(349.0)),
            now=NOW,
            digest_dir=self.tmp.name,
            connection=self.connection,
            advance=lambda: 2,
        )
        self.assertIn("6% lower than the previous check (370 RUB)", result["digest"])
        self.assertEqual(
            [item["price"] for item in storage.live_readings(self.connection, "demo-cement")],
            [349.0, 370.0],
        )


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.connection = storage.connect(":memory:")
        storage.init_db(self.connection)
        self.addCleanup(self.connection.close)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_run_pass_reports_the_delivery(self):
        sent: list[str] = []

        def sender(text: str) -> dict:
            sent.append(text)
            return {"sent": True, "error": None}

        result = daily.run_pass(
            collect=lambda: [reading(349.0)],
            now=NOW,
            digest_dir=self.tmp.name,
            connection=self.connection,
            advance=lambda: 1,
            sender=sender,
        )
        self.assertTrue(result["delivery"]["sent"])
        self.assertEqual(sent, [result["digest"]])

    def test_run_pass_without_a_sender_does_not_deliver(self):
        result = daily.run_pass(
            collect=lambda: [reading(349.0)],
            now=NOW,
            digest_dir=self.tmp.name,
            connection=self.connection,
            advance=lambda: 1,
        )
        self.assertIsNone(result["delivery"])

    def test_send_latest_sends_the_saved_digest(self):
        daily.write_digest("saved digest\n", NOW, self.tmp.name)
        sent: list[str] = []
        result = daily.send_latest(
            digest_dir=self.tmp.name,
            sender=lambda text: sent.append(text) or {"sent": True, "error": None},
        )
        self.assertTrue(result["sent"])
        self.assertEqual(result["date"], "2026-11-15")
        self.assertEqual(sent, ["saved digest\n"])

    def test_send_latest_without_a_digest(self):
        result = daily.send_latest(
            digest_dir=self.tmp.name, sender=lambda text: {"sent": True}
        )
        self.assertEqual(result["reason"], "no_digest")
        self.assertFalse(result["sent"])

    def test_send_latest_without_delivery_is_honest(self):
        daily.write_digest("x\n", NOW, self.tmp.name)
        with mock.patch.object(daily, "default_sender", lambda: None):
            result = daily.send_latest(digest_dir=self.tmp.name)
        self.assertEqual(result["reason"], "not_configured")
        self.assertFalse(result["sent"])


if __name__ == "__main__":
    unittest.main()
