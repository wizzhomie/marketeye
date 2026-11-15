"""Deliver the daily digest to Telegram.

The bot token and the chat id live in the project-local ``.env`` (gitignored),
never in the repository and never in the browser. Without them the product works
unchanged and the UI says delivery is not connected.

This is a demo delivery path: one message to one chat, no queue, no retries.
A failed send is reported honestly; the digest file stays on disk either way.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

import ai_note

API_ROOT = "https://api.telegram.org"
USER_AGENT = "MarketEyeDemo/1.0 (+portfolio demo)"
TIMEOUT_SECONDS = 10
MAX_MESSAGE = 4000  # Telegram's hard limit is 4096 characters.


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _load() -> None:
    """Read .env without overriding real environment variables."""
    ai_note.load_env()


def config() -> dict:
    """Is delivery configured? Never exposes the token."""
    _load()
    token = _env("TELEGRAM_BOT_TOKEN")
    chat_id = _env("TELEGRAM_CHAT_ID")
    return {
        "channel": "telegram",
        "configured": bool(token and chat_id),
        "hasToken": bool(token),
        "hasChat": bool(chat_id),
    }


def _api(token: str, method: str) -> str:
    return f"{API_ROOT}/bot{token}/{method}"


def _error_text(exc: urllib.error.HTTPError) -> str:
    """Telegram puts the reason in JSON; read it without failing again."""
    try:
        payload = json.loads(exc.read().decode("utf-8", errors="replace"))
    except (OSError, ValueError):
        return f"Telegram answered HTTP {exc.code}."
    description = payload.get("description") if isinstance(payload, dict) else None
    return str(description).strip() or f"Telegram answered HTTP {exc.code}."


def send(text: str, token: str | None = None, chat_id: str | None = None) -> dict:
    """Send one plain-text message. Returns ``{"sent": bool, "error": str|None}``."""
    _load()
    token = (token or _env("TELEGRAM_BOT_TOKEN")).strip()
    chat_id = (chat_id or _env("TELEGRAM_CHAT_ID")).strip()
    if not token or not chat_id:
        return {"sent": False, "error": "Telegram delivery is not configured."}

    body = json.dumps(
        {
            "chat_id": chat_id,
            "text": text[:MAX_MESSAGE],
            "disable_web_page_preview": True,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        _api(token, "sendMessage"),
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {"sent": False, "error": _error_text(exc)}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "sent": False,
            "error": f"could not reach Telegram ({type(exc).__name__})",
        }
    except ValueError:
        return {"sent": False, "error": "Telegram answered with invalid JSON."}

    if not isinstance(payload, dict) or not payload.get("ok"):
        description = payload.get("description") if isinstance(payload, dict) else None
        return {
            "sent": False,
            "error": str(description).strip() or "Telegram rejected the message.",
        }
    return {"sent": True, "error": None}


def discover_chat_id(token: str | None = None) -> dict:
    """Setup helper: find the chat that last wrote to the bot.

    The owner opens the bot and presses Start; this reads the updates and
    returns the chat id, so the id never has to be typed by hand.
    """
    _load()
    token = (token or _env("TELEGRAM_BOT_TOKEN")).strip()
    if not token:
        return {"found": False, "error": "No bot token yet (TELEGRAM_BOT_TOKEN)."}

    request = urllib.request.Request(
        _api(token, "getUpdates") + "?limit=10",
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {"found": False, "error": _error_text(exc)}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"found": False, "error": f"could not reach Telegram ({type(exc).__name__})"}
    except ValueError:
        return {"found": False, "error": "Telegram answered with invalid JSON."}

    updates = payload.get("result") if isinstance(payload, dict) else None
    for update in reversed(updates or []):
        message = update.get("message") or update.get("channel_post") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is not None:
            return {
                "found": True,
                "chatId": str(chat_id),
                "chatTitle": chat.get("title") or chat.get("username") or chat.get("first_name"),
            }
    return {
        "found": False,
        "error": "No message from you yet: open the bot and press Start, then try again.",
    }
