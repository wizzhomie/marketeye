"""Deterministic tests for the parser profiles and the live collector.

The only HTTP in these tests is the local demo shop (a thread server on an
ephemeral port); the real books page is read from a saved fixture, so the tests
never touch the network.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import collector
import demo_shop
import page_parser

ROOT = Path(__file__).resolve().parent.parent
BOOK_FIXTURE = ROOT / "tests" / "fixtures" / "books_product.html"
PROFILES = page_parser.load_profiles()


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.html = BOOK_FIXTURE.read_text(encoding="utf-8")

    def test_reads_a_real_book_page(self):
        parsed = page_parser.read_page(self.html, PROFILES["books_toscrape"])
        self.assertEqual(parsed["title"], "A Light in the Attic")
        self.assertEqual(parsed["price"], 51.77)
        self.assertEqual(parsed["currency"], "GBP")
        self.assertEqual(parsed["raw"], "£51.77")

    def test_missing_price_is_an_error(self):
        with self.assertRaises(ValueError) as context:
            page_parser.read_page("<h1>Only a title</h1>", PROFILES["books_toscrape"])
        self.assertIn("price element not found", str(context.exception))

    def test_junk_price_is_an_error(self):
        html = '<h1>Book</h1><p class="price_color">Call for price</p>'
        with self.assertRaises(ValueError) as context:
            page_parser.read_page(html, PROFILES["books_toscrape"])
        self.assertIn("does not match", str(context.exception))

    def test_reads_the_demo_shop_page(self):
        parsed = page_parser.read_page(demo_shop.render_page(), PROFILES["demo_shop"])
        self.assertEqual(parsed["currency"], "RUB")
        self.assertEqual(parsed["price"], float(demo_shop.current_price()))

    def test_selectors(self):
        self.assertEqual(page_parser.extract_text(self.html, "h1"), "A Light in the Attic")
        self.assertEqual(page_parser.extract_text(self.html, ".price_color"), "£51.77")
        with self.assertRaises(ValueError):
            page_parser.extract_text(self.html, "div#nope")

    def test_every_source_has_a_known_profile(self):
        for source in collector.load_sources():
            self.assertIn(source["profile"], PROFILES, source["id"])


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.server = demo_shop.start(0)
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def _source(self, url: str) -> dict:
        return {
            "id": "demo-cement",
            "competitor": "Demo Build Supply",
            "product": "Portland cement M500, 50 kg",
            "url": url,
            "profile": "demo_shop",
        }

    def test_collects_the_local_shop(self):
        reading = collector.collect_source(
            self._source(f"http://127.0.0.1:{self.port}/cement"), PROFILES
        )
        self.assertEqual(reading["status"], "ok")
        self.assertEqual(reading["price"], float(demo_shop.current_price()))
        self.assertEqual(reading["currency"], "RUB")
        self.assertIsNone(reading["note"])

    def test_unreachable_site_is_stored_as_an_error(self):
        reading = collector.collect_source(
            self._source("http://127.0.0.1:1/cement"), PROFILES
        )
        self.assertEqual(reading["status"], "error")
        self.assertIsNone(reading["price"])
        self.assertIn("could not reach the site", reading["note"])

    def test_unknown_profile_is_rejected_before_fetching(self):
        source = self._source("http://127.0.0.1:1/cement")
        source["profile"] = "nope"
        reading = collector.collect_source(source, PROFILES)
        self.assertEqual(reading["status"], "error")
        self.assertIn("unknown parser profile", reading["note"])


if __name__ == "__main__":
    unittest.main()
