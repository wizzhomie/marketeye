"""Optional Groq buyer note.

The only AI in the product: it explains a verified snapshot in two or three
sentences and never invents prices. The key stays server-side in ``.env``; the
demo works without it.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-20b"

SYSTEM_PROMPT = (
    "You write short buyer notes for a small distributor that monitors competitor "
    "prices. You are given a verified daily snapshot in JSON: our prices, competitor "
    "prices, price moves and alerts. Write 2-3 plain sentences in English for the "
    "buyer: what changed, who is below our price, and what to check next. Use only "
    "the numbers and names present in the data; never invent products, prices or "
    "facts. No markdown, no lists, no preamble. Keep it under 70 words."
)


def load_env() -> None:
    """Read the project-local .env (gitignored) without overriding the environment."""
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def api_key() -> str:
    return os.environ.get("GROQ_API_KEY", "").strip()


def model_name() -> str:
    return os.environ.get("GROQ_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def groq_note(api_key_value: str, model: str, payload: dict) -> tuple[str | None, bool]:
    """Return (note, ok). Never logs or returns the API key."""
    body = {
        "model": model,
        "temperature": 0.3,
        "max_tokens": 400,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "Verified snapshot data (JSON):\n"
                + json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            },
        ],
    }
    if model.startswith("openai/gpt-oss"):
        body["reasoning_effort"] = "low"
    request = urllib.request.Request(
        GROQ_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key_value}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Cloudflare in front of Groq rejects the default Python user agent.
            "User-Agent": "MarketEyeDemo/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            data = json.loads(response.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"].strip()
        text = text.replace("**", "").replace("__", "").replace("`", "")
        text = " ".join(text.split()).replace(" %", "%")
        if not text:
            return None, False
        return text[:800], True
    except urllib.error.HTTPError as exc:
        sys.stderr.write(f"[ai] Groq returned HTTP {exc.code}\n")
        return None, False
    except Exception as exc:  # noqa: BLE001 - demo app, report and move on
        sys.stderr.write(f"[ai] Groq request failed: {type(exc).__name__}\n")
        return None, False
