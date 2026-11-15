"""Small, honest HTML reading for the live example.

A site's specifics live in ``parsers/profiles.json`` as data — selectors and a
price pattern — so a new site is a profile, not a branch in the collector.

The parser deliberately refuses to guess: a missing title or price, or a price
that does not match the profile pattern, is an error for that reading, not a
"0" or a made-up number.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

import discovered

ROOT = Path(__file__).resolve().parent
PROFILES_JSON = ROOT / "parsers" / "profiles.json"


def load_profiles(path: Path | str = PROFILES_JSON) -> dict:
    """Tracked profiles, plus profiles drafted when a page was accepted."""
    profiles = json.loads(Path(path).read_text(encoding="utf-8"))
    for name, profile in discovered.profiles().items():
        profiles.setdefault(name, profile)
    return profiles


def _parse_selector(selector: str) -> tuple[str | None, list[str]]:
    """Turn ``h1``, ``.price`` or ``p.price`` into (tag, classes)."""
    selector = selector.strip()
    tag = None
    classes: list[str] = []
    match = re.match(r"^(?P<tag>[a-zA-Z][a-zA-Z0-9-]*)?(?P<classes>(?:\.[A-Za-z0-9_-]+)*)$", selector)
    if not match:
        raise ValueError(f"unsupported selector: {selector!r}")
    if match.group("tag"):
        tag = match.group("tag").lower()
    classes = [item for item in match.group("classes").split(".") if item]
    if tag is None and not classes:
        raise ValueError(f"empty selector: {selector!r}")
    return tag, classes


class _TextCollector(HTMLParser):
    """Collect the text of the first element matching a simple selector."""

    def __init__(self, selector: str):
        super().__init__(convert_charrefs=True)
        self._tag, self._classes = _parse_selector(selector)
        self._active = 0
        self._parts: list[str] = []
        self.result: str | None = None

    def _matches(self, tag: str, attrs: list[tuple[str, str | None]]) -> bool:
        if self._tag is not None and tag.lower() != self._tag:
            return False
        if not self._classes:
            return True
        classes = []
        for name, value in attrs:
            if name == "class" and value:
                classes = value.split()
                break
        return all(item in classes for item in self._classes)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.result is not None:
            return
        if self._active:
            self._active += 1
            return
        if self._matches(tag, attrs):
            self._active = 1
            self._parts = []

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.result is not None or self._active:
            return
        if self._matches(tag, attrs):
            self.result = ""

    def handle_endtag(self, tag: str) -> None:
        if not self._active:
            return
        self._active -= 1
        if self._active == 0:
            self.result = " ".join("".join(self._parts).split())

    def handle_data(self, data: str) -> None:
        if self._active:
            self._parts.append(data)


def extract_text(html: str, selector: str) -> str | None:
    """Text of the first matching element, whitespace-collapsed."""
    collector = _TextCollector(selector)
    collector.feed(html)
    if collector.result is None and collector._active:  # unclosed element
        collector.result = " ".join("".join(collector._parts).split())
    return collector.result


def parse_price(raw: str, pattern: str) -> float | None:
    """Pull the amount out of a raw price string; None when it does not fit."""
    match = re.search(pattern, raw)
    if not match or "amount" not in (match.groupdict() or {}):
        return None
    try:
        value = float(match.group("amount"))
    except (TypeError, ValueError):
        return None
    if value <= 0 or value >= 10**9:
        return None
    return value


def read_page(html: str, profile: dict) -> dict:
    """Read title and price from a page using one profile.

    Returns ``{"title", "price", "currency", "raw"}`` or raises ValueError with
    a plain reason; the caller stores the reason as the reading's note.
    """
    title = extract_text(html, profile["title_selector"])
    if not title:
        raise ValueError("title not found on the page")

    raw_price = extract_text(html, profile["price_selector"])
    if not raw_price:
        raise ValueError("price element not found on the page")

    price = parse_price(raw_price, profile["price_pattern"])
    if price is None:
        raise ValueError(f"price does not match the profile pattern: {raw_price!r}")

    return {
        "title": title,
        "price": price,
        "currency": profile["currency"],
        "raw": raw_price,
    }
