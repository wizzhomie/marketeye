"""Live page collection: fetch a page, parse it with its profile, report honestly.

No database and no FastAPI here — this module only turns a URL into a reading.
A fetch failure, a missing price or a value that does not match the profile is
recorded as an error with a plain reason; it is never stored as a price.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import discovered
import page_parser

ROOT = Path(__file__).resolve().parent
SOURCES_JSON = ROOT / "live_sources.json"
USER_AGENT = "MarketEyeDemo/1.0 (+portfolio demo)"
TIMEOUT_SECONDS = 15
MAX_PAGE_BYTES = 2 * 1024 * 1024


def load_sources(path: Path | str = SOURCES_JSON) -> list[dict]:
    """Configured sources, plus pages accepted from the AI discovery step."""
    sources = json.loads(Path(path).read_text(encoding="utf-8"))
    known = {source["id"] for source in sources}
    for source in discovered.sources():
        if source.get("id") not in known:
            sources.append(source)
    return sources


def fetch(url: str, timeout: int = TIMEOUT_SECONDS) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(MAX_PAGE_BYTES).decode("utf-8", errors="replace")


def collect_source(source: dict, profiles: dict) -> dict:
    """One reading: parsed price or an honest error."""
    reading = {
        "sourceId": source["id"],
        "competitor": source["competitor"],
        "product": source["product"],
        "url": source["url"],
        "profile": source["profile"],
        "fetchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "ok",
        "title": None,
        "price": None,
        "currency": None,
        "rawValue": None,
        "note": None,
    }

    profile = profiles.get(source["profile"])
    if profile is None:
        reading["status"] = "error"
        reading["note"] = f"unknown parser profile: {source['profile']}"
        return reading

    try:
        html = fetch(source["url"])
    except urllib.error.HTTPError as exc:
        reading["status"] = "error"
        reading["note"] = f"the site answered HTTP {exc.code}"
        return reading
    except urllib.error.URLError as exc:
        reason = type(exc.reason).__name__ if exc.reason else "unknown"
        reading["status"] = "error"
        reading["note"] = f"could not reach the site ({reason})"
        return reading
    except (TimeoutError, OSError) as exc:
        reading["status"] = "error"
        reading["note"] = f"could not fetch the page ({type(exc).__name__})"
        return reading

    try:
        parsed = page_parser.read_page(html, profile)
    except ValueError as exc:
        reading["status"] = "error"
        reading["note"] = str(exc)
        return reading

    reading.update(
        {
            "title": parsed["title"],
            "price": parsed["price"],
            "currency": parsed["currency"],
            "rawValue": parsed["raw"],
        }
    )
    return reading


def collect_all(sources: list[dict] | None = None, profiles: dict | None = None) -> list[dict]:
    sources = sources if sources is not None else load_sources()
    profiles = profiles if profiles is not None else page_parser.load_profiles()
    return [collect_source(source, profiles) for source in sources]
