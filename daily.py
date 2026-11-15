"""The daily check: one collection pass and a plain-text digest.

The product's promise is "every day, see what competitors did". This module is
the smallest honest version of that promise: it fetches every watched page once,
stores the readings, moves the local demo shop on and writes a readable digest
to ``data/digests/YYYY-MM-DD.txt`` (gitignored). The same function powers three
entrances:

* ``python daily.py run`` — one pass from the console, digest printed;
* ``python daily.py loop`` — the scheduler loop started by ``./daily.sh``; it
  runs the pass once a day at ``MARKETEYE_DAILY_AT`` (default 09:00 local);
* ``POST /api/daily/run`` — the "Run daily check" button on the Live check
  screen, so the demo can show the digest without a terminal.

Nothing here guesses a price: the collector in ``collector.py`` already refuses
to, and this module only formats what it returned.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, time as clock, timedelta, timezone
from pathlib import Path
from typing import Callable

import alerts
import collector
import demo_shop
import storage
import telegram

ROOT = Path(__file__).resolve().parent
DIGEST_DIR = ROOT / "data" / "digests"
PID_FILE = ROOT / ".run" / "daily.pid"
DEFAULT_AT = "09:00"


# --- schedule ---------------------------------------------------------------


def configured_at() -> str:
    """Local time of the daily run, ``HH:MM``; invalid values fall back to 09:00."""
    raw = os.environ.get("MARKETEYE_DAILY_AT", "").strip()
    if not raw:
        return DEFAULT_AT
    try:
        hour_text, minute_text = raw.split(":", 1)
        hour, minute = int(hour_text), int(minute_text)
    except (TypeError, ValueError):
        return DEFAULT_AT
    if not (0 <= hour < 24 and 0 <= minute < 60):
        return DEFAULT_AT
    return f"{hour:02d}:{minute:02d}"


def next_run(now: datetime | None = None) -> str:
    """The next scheduled local time, as an ISO string (for the UI)."""
    hour, minute = (int(part) for part in configured_at().split(":"))
    current = now or datetime.now().astimezone()
    candidate = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= current:
        candidate += timedelta(days=1)
    return candidate.isoformat(timespec="seconds")


def is_due(current: datetime | None = None) -> bool:
    """True once the configured time has passed today (local time)."""
    hour, minute = (int(part) for part in configured_at().split(":"))
    current = current or datetime.now().astimezone()
    return current.time() >= clock(hour, minute)


def scheduler_status() -> dict:
    """Is the background loop running, and when will it fire next?"""
    pid = None
    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        pid = None

    running = False
    if pid is not None:
        try:
            os.kill(pid, 0)
            running = True
        except ProcessLookupError:
            running = False
        except PermissionError:
            running = True

    return {
        "running": running,
        "pid": pid if running else None,
        "at": configured_at(),
        "nextRun": next_run() if running else None,
    }


# --- digest text ------------------------------------------------------------


def change_between(reading: dict | None, previous: dict | None) -> dict | None:
    """Price move between two ok readings; ``None`` when it cannot be said."""
    if not reading or not previous:
        return None
    if reading.get("status") != "ok" or previous.get("status") != "ok":
        return None
    price, before = reading.get("price"), previous.get("price")
    if price is None or not before:
        return None
    amount = round(price - before, 2)
    raw = abs(amount / before * 100)
    return {
        "amount": amount,
        "percentText": alerts.percent_text(raw),
        "direction": "down" if amount < 0 else ("up" if amount > 0 else "flat"),
        "fromPrice": before,
    }


def _move_line(reading: dict, change: dict | None) -> str:
    currency = reading.get("currency") or ""
    price = f"{alerts.amount_text(reading['price'])} {currency}".strip()
    if change is None:
        return f"  {price} — first reading"
    if change["direction"] == "flat":
        return f"  {price} — no change since the previous check"
    direction = "lower" if change["direction"] == "down" else "higher"
    before = f"{alerts.amount_text(change['fromPrice'])} {currency}".strip()
    return (
        f"  {price} — {change['percentText']}% {direction} than the previous "
        f"check ({before})"
    )


def build_digest(entries: list[dict], generated_at: datetime, tick: int) -> str:
    """The plain-text digest for one collection pass.

    ``entries`` are ``{"source", "reading", "previous"}`` dicts in source order;
    ``previous`` is the previous ok reading (or ``None``).
    """
    lines = [
        "MarketEye · daily check",
        f"{generated_at.strftime('%Y-%m-%d %H:%M')} UTC · "
        f"{len(entries)} source{'s' if len(entries) != 1 else ''}",
        "",
    ]

    errors = []
    read = 0
    for entry in entries:
        source = entry["source"]
        reading = entry["reading"]
        if reading["status"] != "ok":
            errors.append((source, reading))
            continue
        title = reading.get("title") or source["product"]
        lines.append(f"{source['competitor']} · {title}")
        lines.append(_move_line(reading, change_between(reading, entry.get("previous"))))
        lines.append(f"  {source['url']}")
        lines.append("")
        read += 1

    if errors:
        lines.append(f"Errors ({len(errors)}):")
        for source, reading in errors:
            note = reading.get("note") or "the page could not be read"
            lines.append(f"  {source['competitor']} · {source['product']} — {note}")
            lines.append(f"  {source['url']}")
        lines.append("")

    read_text = f"{read} page{'s' if read != 1 else ''} read"
    error_text = f"{len(errors)} error{'s' if len(errors) != 1 else ''}"
    lines.append(f"{read_text}, {error_text}. Demo shop tick: {tick}.")
    lines.append("Daily check only: the panels still run on saved snapshots.")
    lines.append("")
    return "\n".join(lines)


# --- files ------------------------------------------------------------------


def _digests_dir(digest_dir: Path | str | None = None) -> Path:
    return Path(digest_dir) if digest_dir is not None else DIGEST_DIR


def write_digest(
    text: str, generated_at: datetime, digest_dir: Path | str | None = None
) -> Path:
    """Save one digest as ``YYYY-MM-DD.txt`` (the day of the run, local time)."""
    folder = _digests_dir(digest_dir)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{generated_at.astimezone().date().isoformat()}.txt"
    path.write_text(text, encoding="utf-8")
    return path


def latest_digest(digest_dir: Path | str | None = None) -> dict | None:
    """The newest saved digest, with the time it was saved."""
    folder = _digests_dir(digest_dir)
    try:
        files = sorted(folder.glob("*.txt"))
    except OSError:
        files = []
    if not files:
        return None
    path = files[-1]
    try:
        text = path.read_text(encoding="utf-8")
        saved = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    except OSError:
        return None
    return {
        "date": path.stem,
        "file": path.name,
        "generatedAt": saved.isoformat(timespec="seconds"),
        "digest": text,
        "count": len(files),
    }


def clear_digests(digest_dir: Path | str | None = None) -> int:
    """Remove saved digests (used by Reset live demo); returns how many went."""
    folder = _digests_dir(digest_dir)
    removed = 0
    for path in sorted(folder.glob("*.txt")):
        try:
            path.unlink()
            removed += 1
        except OSError:
            continue
    return removed


# --- the pass ---------------------------------------------------------------


def default_sender() -> Callable[[str], dict] | None:
    """The configured delivery, or ``None`` when delivery is not set up."""
    return telegram.send if telegram.config()["configured"] else None


def run_pass(
    collect: Callable[[], list[dict]] | None = None,
    now: datetime | None = None,
    digest_dir: Path | str | None = None,
    connection=None,
    advance: Callable[[], int] | None = None,
    sender: Callable[[str], dict] | None = None,
) -> dict:
    """Fetch every source once, store the readings and save today's digest.

    ``sender`` is optional: when given, the digest text is delivered to it and
    the outcome lands in ``delivery``. Tests pass no sender, so they stay offline.
    """
    generated_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    readings = (collect or collector.collect_all)()

    own_connection = connection is None
    connection = connection or storage.connect()
    try:
        by_source = {reading["sourceId"]: reading for reading in readings}
        entries = []
        for source in collector.load_sources():
            reading = by_source.get(source["id"])
            if reading is None:
                continue
            previous = next(
                (
                    item
                    for item in storage.live_readings(
                        connection, source["id"], limit=8
                    )
                    if item["status"] == "ok"
                ),
                None,
            )
            entries.append(
                {"source": source, "reading": reading, "previous": previous}
            )
        for reading in readings:
            storage.add_live_reading(connection, reading)
    finally:
        if own_connection:
            connection.close()

    tick = (advance or demo_shop.advance_tick)()
    text = build_digest(entries, generated_at, tick)
    path = write_digest(text, generated_at, digest_dir)
    try:
        relative = path.relative_to(ROOT).as_posix()
    except ValueError:
        relative = path.as_posix()

    delivery = sender(text) if sender is not None else None

    return {
        "date": generated_at.astimezone().date().isoformat(),
        "generatedAt": generated_at.isoformat(timespec="seconds"),
        "file": path.name,
        "path": relative,
        "digest": text,
        "sources": len(entries),
        "read": sum(1 for entry in entries if entry["reading"]["status"] == "ok"),
        "errors": sum(
            1 for entry in entries if entry["reading"]["status"] != "ok"
        ),
        "tick": tick,
        "delivery": delivery,
    }


# --- the loop ---------------------------------------------------------------


def send_latest(
    digest_dir: Path | str | None = None,
    sender: Callable[[str], dict] | None = None,
) -> dict:
    """Send the newest saved digest (the UI's "Send to Telegram" button)."""
    latest = latest_digest(digest_dir)
    if latest is None:
        return {
            "sent": False,
            "reason": "no_digest",
            "error": "No digest saved yet. Run the daily check first.",
        }
    sender = sender or default_sender()
    if sender is None:
        return {
            "sent": False,
            "reason": "not_configured",
            "error": "Telegram delivery is not configured.",
        }
    result = sender(latest["digest"])
    return {
        "sent": bool(result.get("sent")),
        "reason": "sent" if result.get("sent") else "failed",
        "error": result.get("error"),
        "date": latest["date"],
    }


def _delivery_line(delivery: dict | None) -> str:
    if delivery is None:
        return "[daily] Telegram delivery is not configured (no message sent)"
    if delivery.get("sent"):
        return "[daily] digest sent to Telegram"
    return f"[daily] Telegram delivery failed: {delivery.get('error')}"


def loop(interval: float = 30.0) -> None:
    """Run the pass once a day at the configured local time."""
    attempted_today = None
    print(
        f"[daily] scheduler started: every day at {configured_at()} local, "
        f"digest folder {DIGEST_DIR}",
        flush=True,
    )
    while True:
        try:
            current = datetime.now().astimezone()
            today = current.date().isoformat()
            if is_due(current) and attempted_today != today:
                attempted_today = today
                result = run_pass(sender=default_sender())
                print(
                    f"[daily] {result['generatedAt']}: {result['sources']} sources, "
                    f"{result['read']} read, {result['errors']} errors, "
                    f"digest {result['path']}",
                    flush=True,
                )
                print(_delivery_line(result.get("delivery")), flush=True)
                print(result["digest"], flush=True)
            time.sleep(interval)
        except KeyboardInterrupt:
            raise
        except Exception as exc:  # keep the scheduler alive and say what broke
            print(f"[daily] check failed: {type(exc).__name__}: {exc}", flush=True)
            time.sleep(interval)


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "run"
    if command == "run":
        result = run_pass(sender=default_sender())
        print(result["digest"], end="")
        print(f"[daily] saved {result['path']}", flush=True)
        print(_delivery_line(result.get("delivery")), flush=True)
        return 0
    if command == "loop":
        loop()
        return 0
    if command == "show":
        latest = latest_digest()
        if latest is None:
            print("no digest yet: run `python daily.py run` first")
            return 1
        print(latest["digest"], end="")
        return 0
    if command == "send":
        result = send_latest()
        if result.get("sent"):
            print(f"sent the {result['date']} digest to Telegram")
            return 0
        print(f"not sent: {result.get('error')}", file=sys.stderr)
        return 1
    if command == "telegram":
        status = telegram.config()
        print(f"channel: telegram, configured: {status['configured']}")
        print(f"token: {'yes' if status['hasToken'] else 'no'}, chat id: {'yes' if status['hasChat'] else 'no'}")
        print("send the digest with: ./daily.sh send")
        return 0 if status["configured"] else 1
    if command == "status":
        status = scheduler_status()
        if status["running"]:
            print(f"running: pid {status['pid']}, daily at {status['at']}, next {status['nextRun']}")
        else:
            print(f"not running: daily at {status['at']}")
        return 0 if status["running"] else 1
    print("usage: daily.py run|loop|show|send|telegram|status", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
