"""Deterministic tests for AI discovery: page verification and acceptance.

No network and no model call: pages are injected as strings and the model answer
as a dict, so the tests exercise exactly the parsing rules.
"""

from __future__ import annotations

import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

import collector
import demo_shop
import discover
import discovered
import page_parser

BOOK_PAGE = (
    "<html><head><title>Shop</title></head><body>"
    "<h1>A Light in the Attic</h1>"
    '<p class="price_color">£51.77</p>'
    "</body></html>"
)


def fake_fetch(page: str):
    return lambda url: page


def failing_fetch(exc: Exception):
    def fetch(url):
        raise exc

    return fetch


class VerifyTests(unittest.TestCase):
    def test_reads_one_clear_price_and_drafts_a_profile(self):
        result = discover.verify_candidate(
            {"url": "https://shop.test/book", "competitor": "Bookshop"},
            fetch=fake_fetch(BOOK_PAGE),
        )
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["price"], 51.77)
        self.assertEqual(result["currency"], "GBP")
        self.assertEqual(result["title"], "A Light in the Attic")
        self.assertEqual(result["profile"]["price_selector"], ".price_color")
        self.assertEqual(result["profile"]["title_selector"], "h1")

        parsed = page_parser.read_page(BOOK_PAGE, result["profile"])
        self.assertEqual(parsed["price"], 51.77)
        self.assertEqual(parsed["currency"], "GBP")

    def test_reads_the_demo_shop_page(self):
        page = demo_shop.render_page()
        result = discover.verify_candidate(
            {"url": "http://127.0.0.1:8768/cement"}, fetch=fake_fetch(page)
        )
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["currency"], "RUB")
        self.assertGreater(result["price"], 0)
        parsed = page_parser.read_page(page, result["profile"])
        self.assertEqual(parsed["price"], result["price"])

    def test_page_without_a_price_is_not_acceptible(self):
        page = "<h1>Book</h1><p class='availability'>In stock</p>"
        result = discover.verify_candidate(
            {"url": "https://shop.test/book"}, fetch=fake_fetch(page)
        )
        self.assertEqual(result["status"], "no_price")
        self.assertIsNone(result["profile"])

    def test_two_different_prices_need_a_confirmation(self):
        page = (
            "<h1>Book</h1>"
            '<p class="price">£51.77</p>'
            '<p class="price sale">£40.00</p>'
        )
        result = discover.verify_candidate(
            {"url": "https://shop.test/book"}, fetch=fake_fetch(page)
        )
        self.assertEqual(result["status"], "likely")
        self.assertEqual(result["price"], 51.77)
        self.assertIn("check the page", result["note"])


    def test_missing_title_is_reported(self):
        page = '<p class="price">£51.77</p>'
        result = discover.verify_candidate(
            {"url": "https://shop.test/book"}, fetch=fake_fetch(page)
        )
        self.assertEqual(result["status"], "no_title")

    def test_unreachable_page_keeps_the_reason(self):
        result = discover.verify_candidate(
            {"url": "https://shop.test/book"},
            fetch=failing_fetch(urllib.error.URLError(OSError("no route"))),
        )
        self.assertEqual(result["status"], "unreachable")
        self.assertIn("could not reach the page", result["note"])

    def test_http_error_keeps_the_status(self):
        error = urllib.error.HTTPError(
            "https://shop.test/book", 403, "Forbidden", None, None
        )
        result = discover.verify_candidate(
            {"url": "https://shop.test/book"}, fetch=failing_fetch(error)
        )
        self.assertEqual(result["status"], "unreachable")
        self.assertIn("HTTP 403", result["note"])

    def test_verify_all_keeps_the_order(self):
        pages = {
            "https://a.test/one": "<h1>One</h1><p class='price'>$10.00</p>",
            "https://b.test/two": "<h1>Two</h1>",
        }

        def fetch(url):
            return pages[url]

        results = discover.verify_all(
            [{"url": "https://a.test/one"}, {"url": "https://b.test/two"}], fetch=fetch
        )
        self.assertEqual([item["url"] for item in results], list(pages))
        self.assertEqual([item["status"] for item in results], ["ready", "no_price"])


class ModelAnswerTests(unittest.TestCase):
    def test_parses_and_dedupes_candidates(self):
        payload = {
            "candidates": [
                {"url": "https://shop.test/a", "competitor": "A", "reason": "best"},
                {"url": "https://shop.test/a", "competitor": "A again"},
                {"url": "ftp://shop.test/b"},
                {"url": "not a url"},
                {"url": "https://shop.test/c", "competitor": "C"},
            ]
        }
        candidates, error = discover.parse_candidates(payload)
        self.assertIsNone(error)
        self.assertEqual([item["url"] for item in candidates], ["https://shop.test/a", "https://shop.test/c"])
        self.assertEqual(candidates[0]["competitor"], "A")

    def test_caps_the_number_of_candidates(self):
        payload = {"candidates": [{"url": f"https://shop.test/{i}"} for i in range(10)]}
        candidates, _ = discover.parse_candidates(payload)
        self.assertEqual(len(candidates), discover.MAX_CANDIDATES)

    def test_rejects_an_unexpected_answer(self):
        candidates, error = discover.parse_candidates({"nope": True})
        self.assertEqual(candidates, [])
        self.assertIn("unexpected", error)

    def test_ai_candidates_surfaces_a_model_error(self):
        def chat(*args, **kwargs):
            return None, "the model answered HTTP 429"

        candidates, error = discover.ai_candidates("Cement", chat=chat)
        self.assertEqual(candidates, [])
        self.assertIn("HTTP 429", error)

    def test_ai_candidates_returns_usable_pages(self):
        def chat(*args, **kwargs):
            return {"candidates": [{"url": "https://shop.test/a", "competitor": "A"}]}, None

        candidates, error = discover.ai_candidates("Cement", chat=chat)
        self.assertIsNone(error)
        self.assertEqual(len(candidates), 1)


class AcceptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.object(
            discovered, "PATH", Path(self.tmp.name) / "discovered.json"
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.fetch = fake_fetch(BOOK_PAGE)

    def test_accept_writes_a_profile_and_a_source(self):
        accepted = discover.accept(
            {"url": "https://shop.test/book", "competitor": "Bookshop"},
            fetch=self.fetch,
        )
        stored = discovered.load()
        self.assertIn(accepted["profileId"], stored["profiles"])
        self.assertEqual(stored["sources"][0]["id"], accepted["profileId"])
        self.assertEqual(stored["sources"][0]["url"], "https://shop.test/book")
        self.assertEqual(stored["profiles"][accepted["profileId"]]["price_selector"], ".price_color")

    def test_accepted_page_is_merged_into_sources_and_profiles(self):
        accepted = discover.accept(
            {"url": "https://shop.test/book", "competitor": "Bookshop"},
            fetch=self.fetch,
        )
        sources = collector.load_sources()
        profiles = page_parser.load_profiles()
        self.assertIn(accepted["profileId"], [source["id"] for source in sources])
        self.assertIn(accepted["profileId"], profiles)

    def test_accepting_twice_keeps_ids_unique(self):
        first = discover.accept(
            {"url": "https://shop.test/book", "competitor": "Bookshop"},
            fetch=self.fetch,
        )
        second = discover.accept(
            {"url": "https://shop.test/book", "competitor": "Bookshop"},
            fetch=self.fetch,
        )
        self.assertNotEqual(first["profileId"], second["profileId"])
        self.assertEqual(len(discovered.load()["sources"]), 2)

    def test_unreadable_page_cannot_be_accepted(self):
        with self.assertRaises(ValueError) as context:
            discover.accept(
                {"url": "https://shop.test/book"},
                fetch=fake_fetch("<h1>Book</h1>"),
            )
        self.assertIn("price", str(context.exception))
        self.assertEqual(discovered.load()["sources"], [])

    def test_likely_page_can_be_accepted_after_confirmation(self):
        page = (
            "<h1>Book</h1>"
            '<p class="price">£51.77</p>'
            '<p class="price sale">£40.00</p>'
        )
        accepted = discover.accept(
            {"url": "https://shop.test/book", "competitor": "Bookshop"},
            fetch=fake_fetch(page),
        )
        self.assertEqual(accepted["source"]["url"], "https://shop.test/book")
        self.assertEqual(discovered.load()["profiles"][accepted["profileId"]]["price_selector"], ".price")

    def test_clear_forgets_accepted_pages(self):
        discover.accept(
            {"url": "https://shop.test/book", "competitor": "Bookshop"},
            fetch=self.fetch,
        )
        self.assertEqual(discovered.clear(), 1)
        self.assertEqual(discovered.load()["sources"], [])


if __name__ == "__main__":
    unittest.main()
