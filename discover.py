"""AI-assisted discovery of competitor pages.

The model proposes candidate product-page URLs; the server is the one that
fetches a page and decides whether a price can be read. A candidate that cannot
be fetched, has no price element, or has several different price-like values is
shown with that honest reason and cannot be accepted.

Accepting a verified candidate writes a parser profile and a watched source into
``data/discovered.json`` (runtime data, gitignored) — the same "a site is a
profile, not code" rule as everywhere else.
"""

from __future__ import annotations

import concurrent.futures
import re
import urllib.error
import urllib.parse
from html.parser import HTMLParser

import ai_note
import collector
import discovered
import page_parser

MAX_CANDIDATES = 3
DEFAULT_TITLE_SELECTOR = "h1"
FALLBACK_TITLE_SELECTOR = "title"

SYSTEM_PROMPT = (
    "You help a small distributor find public product pages to monitor prices on. "
    "Given a product, propose up to three direct product-page URLs on public shop "
    "websites that do not require a login. Prefer well-known shops and pages you are "
    "confident exist; never invent URLs, never use search-result pages or query "
    "strings. Answer with strict JSON only: "
    '{"candidates":[{"url":"https://...","competitor":"Shop name","reason":"why this page"}]}'
)

CURRENCY_SYMBOLS = {"£": "GBP", "$": "USD", "€": "EUR", "₽": "RUB"}
CURRENCY_CODES = ("GBP", "USD", "EUR", "RUB")
CURRENCY_WORDS = {"руб": "RUB", "rur": "RUB", "eur": "EUR", "usd": "USD", "gbp": "GBP"}

_NUMBER = re.compile(r"\d+(?:[.,]\d{1,2})?")


class _PriceScanner(HTMLParser):
    """Collect the text of elements whose class or id mentions a price."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._frames: list[dict] = []
        self.elements: list[dict] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("br", "img", "meta", "link", "input", "hr", "source"):
            return
        classes: list[str] = []
        ident = None
        for name, value in attrs:
            if name == "class" and value:
                classes = value.split()
            elif name == "id" and value:
                ident = value
        hint = any("price" in token.lower() for token in classes) or bool(
            ident and "price" in ident.lower()
        )
        self._frames.append(
            {"tag": tag, "classes": classes, "id": ident, "hint": hint, "parts": []}
        )

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._frames) - 1, -1, -1):
            if self._frames[index]["tag"] == tag:
                frame = self._frames[index]
                del self._frames[index:]
                text = " ".join("".join(frame["parts"]).split())
                if frame["hint"] and text:
                    self.elements.append(
                        {
                            "tag": frame["tag"],
                            "classes": frame["classes"],
                            "id": frame["id"],
                            "text": text,
                        }
                    )
                return

    def handle_data(self, data: str) -> None:
        for frame in self._frames:
            frame["parts"].append(data)


def _currency_in(text: str) -> str | None:
    for symbol, code in CURRENCY_SYMBOLS.items():
        if symbol in text:
            return code
    upper = text.upper()
    for code in CURRENCY_CODES:
        if code in upper:
            return code
    lower = text.lower()
    for word, code in CURRENCY_WORDS.items():
        if word in lower:
            return code
    return None


def _amount_in(text: str) -> float | None:
    """One number only; a string with several numbers is not a price we can trust."""
    numbers = _NUMBER.findall(text)
    if len(numbers) != 1:
        return None
    try:
        return float(numbers[0].replace(",", "."))
    except ValueError:
        return None


def _selector_for(element: dict) -> str | None:
    for token in element.get("classes") or []:
        if re.fullmatch(r"[A-Za-z0-9_-]+", token):
            return f".{token}"
    ident = element.get("id")
    if ident and re.fullmatch(r"[A-Za-z0-9_-]+", ident):
        return f"#{ident}"
    return None


def _pattern_for(currency: str, element_text: str) -> str | None:
    """Build a price pattern that works on the text we just read."""
    if currency in CURRENCY_SYMBOLS.values():
        symbol = next(
            (item for item, code in CURRENCY_SYMBOLS.items() if code == currency), None
        )
        if symbol and symbol in element_text:
            return re.escape(symbol) + r"\s*(?P<amount>[0-9]+(?:[.,][0-9]{1,2})?)"
    return r"(?P<amount>[0-9]+(?:[.,][0-9]{1,2})?)\s*" + currency


def hostname(url: str) -> str:
    return urllib.parse.urlsplit(url).hostname or "unknown"


def slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "page"


def _fetch_error(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"the page answered HTTP {exc.code}"
    if isinstance(exc, urllib.error.URLError):
        reason = type(exc.reason).__name__ if getattr(exc, "reason", None) else "unknown"
        return f"could not reach the page ({reason})"
    if isinstance(exc, (TimeoutError, OSError)):
        return f"could not fetch the page ({type(exc).__name__})"
    return f"could not fetch the page ({type(exc).__name__})"


def verify_candidate(candidate: dict, fetch=None) -> dict:
    """Fetch one proposed page and decide, honestly, what can be read there."""
    url = str(candidate.get("url") or "").strip()
    competitor = str(candidate.get("competitor") or "").strip() or hostname(url)
    product = str(candidate.get("product") or "").strip()
    result = {
        "url": url,
        "competitor": competitor,
        "product": product,
        "reason": candidate.get("reason"),
        "title": None,
        "price": None,
        "currency": None,
        "raw": None,
        "status": "unreachable",
        "note": None,
        "profile": None,
    }

    try:
        html = (fetch or collector.fetch)(url)
    except Exception as exc:  # noqa: BLE001 - every failure becomes the reason
        result["note"] = _fetch_error(exc)
        return result

    title = page_parser.extract_text(html, DEFAULT_TITLE_SELECTOR)
    title_selector = DEFAULT_TITLE_SELECTOR
    if not title:
        title = page_parser.extract_text(html, FALLBACK_TITLE_SELECTOR)
        title_selector = FALLBACK_TITLE_SELECTOR
    if not title:
        result["status"] = "no_title"
        result["note"] = "the page has no readable title"
        return result
    result["title"] = title

    scanner = _PriceScanner()
    scanner.feed(html)
    if not scanner.elements:
        result["status"] = "no_price"
        result["note"] = "no price element on the page"
        return result

    ready: list[dict] = []
    for element in scanner.elements:
        currency = _currency_in(element["text"])
        amount = _amount_in(element["text"])
        selector = _selector_for(element)
        if currency is None or amount is None or selector is None:
            continue
        pattern = _pattern_for(currency, element["text"])
        if pattern is None:
            continue
        if page_parser.parse_price(element["text"], pattern) != amount:
            continue
        ready.append(
            {
                "amount": amount,
                "currency": currency,
                "raw": element["text"],
                "selector": selector,
                "pattern": pattern,
            }
        )

    if not ready:
        result["status"] = "no_price"
        first = scanner.elements[0]["text"]
        if len(first) > 80:
            first = first[:77] + "…"
        result["note"] = f"price-like elements exist, but none can be read safely (first: {first!r})"
        return result

    distinct = {(item["amount"], item["currency"]) for item in ready}
    if len(distinct) > 1:
        values = sorted(f"{item['amount']:g} {item['currency']}" for item in ready)
        shown = ", ".join(values[:4])
        if len(values) > 4:
            shown += f" and {len(values) - 4} more"
        found = ready[0]
        result.update(
            {
                "status": "likely",
                "price": found["amount"],
                "currency": found["currency"],
                "raw": found["raw"],
                "profile": {
                    "title": competitor,
                    "kind": "discovered",
                    "title_selector": title_selector,
                    "price_selector": found["selector"],
                    "price_pattern": found["pattern"],
                    "currency": found["currency"],
                },
                "note": (
                    f"{len(distinct)} different prices on the page ({shown}). "
                    f"The first one is {found['raw']} — check the page before adding."
                ),
            }
        )
        return result

    found = ready[0]
    result.update(
        {
            "status": "ready",
            "price": found["amount"],
            "currency": found["currency"],
            "raw": found["raw"],
            "profile": {
                "title": competitor,
                "kind": "discovered",
                "title_selector": title_selector,
                "price_selector": found["selector"],
                "price_pattern": found["pattern"],
                "currency": found["currency"],
            },
        }
    )
    return result


def verify_all(proposals: list[dict], fetch=None) -> list[dict]:
    """Verify proposed pages in parallel, keeping the model's order."""
    if not proposals:
        return []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(proposals))) as pool:
        return list(pool.map(lambda item: verify_candidate(item, fetch), proposals))


def parse_candidates(payload: dict) -> tuple[list[dict], str | None]:
    """Validate what the model returned; only usable candidates survive."""
    items = payload.get("candidates") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return [], "the model returned an unexpected answer"
    candidates: list[dict] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not re.match(r"^https?://", url) or url in seen:
            continue
        seen.add(url)
        candidates.append(
            {
                "url": url,
                "competitor": str(item.get("competitor") or hostname(url)).strip(),
                "reason": str(item.get("reason") or "").strip(),
            }
        )
        if len(candidates) >= MAX_CANDIDATES:
            break
    if not candidates:
        return [], "the model did not propose any usable page"
    return candidates, None


def ai_candidates(product: str, chat=None) -> tuple[list[dict], str | None]:
    """Ask the model for candidate pages; parsing lives in parse_candidates."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": product},
    ]
    payload, error = (chat or ai_note.chat_json)(
        ai_note.api_key(), ai_note.model_name(), messages, max_tokens=700
    )
    if error:
        return [], error
    return parse_candidates(payload)


def _unique_id(base: str, known: set[str]) -> str:
    candidate = base
    index = 2
    while candidate in known:
        candidate = f"{base}-{index}"
        index += 1
    return candidate


def accept(candidate: dict, fetch=None) -> dict:
    """Re-verify a candidate on the server and remember it as a watched source."""
    verified = verify_candidate(
        {
            "url": candidate.get("url"),
            "competitor": candidate.get("competitor"),
            "product": candidate.get("product"),
        },
        fetch,
    )
    if verified["status"] not in ("ready", "likely"):
        raise ValueError(verified["note"] or "the page cannot be read safely")

    host = slug(hostname(verified["url"]))
    known_ids = {source["id"] for source in collector.load_sources()}
    known_ids |= set(discovered.profiles())
    base_id = f"discovered-{host}"
    profile_id = _unique_id(base_id, known_ids)

    profile = dict(verified["profile"])
    profile["title"] = verified["competitor"]
    source = {
        "id": profile_id,
        "competitor": verified["competitor"],
        "product": verified["title"] or candidate.get("product") or "Discovered page",
        "url": verified["url"],
        "profile": profile_id,
        "kind": "discovered",
    }
    discovered.accept(profile_id, profile, source)
    return {"profileId": profile_id, "source": source}
