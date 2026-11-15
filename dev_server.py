#!/usr/bin/env python3
"""Minimal static dev server for the MarketEye front-end plus the optional AI note.

Standard library only: the demo has to run without installing anything. Once the
backend starts, FastAPI takes over the same port and serves these files itself.

Routes:
    /                -> templates/index.html
    /overview        -> templates/overview.html
    /static/...      -> files from static/
    /healthz         -> "ok" (used by dev.sh)
    POST /api/ai/note -> optional Groq-powered buyer note (needs GROQ_API_KEY)
"""

from __future__ import annotations

import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
STATIC_DIR = (ROOT / "static").resolve()
INDEX = ROOT / "templates" / "index.html"
OVERVIEW = ROOT / "templates" / "overview.html"
DEFAULT_PORT = 8767

MAX_AI_BODY = 32 * 1024
AI_MIN_INTERVAL = 2.0
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

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


def _groq_note(api_key: str, model: str, payload: dict) -> tuple[str | None, bool]:
    """Return (note, ok). Never logs or returns the API key."""
    body = {
        "model": model,
        "temperature": 0.3,
        "max_tokens": 200,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "Verified snapshot data (JSON):\n"
                + json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            },
        ],
    }
    request = urllib.request.Request(
        GROQ_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            data = json.loads(response.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"].strip()
        text = text.replace("**", "").replace("__", "").replace("`", "")
        text = " ".join(text.split())
        if not text:
            return None, False
        return text[:800], True
    except urllib.error.HTTPError as exc:
        sys.stderr.write(f"[ai] Groq returned HTTP {exc.code}\n")
        return None, False
    except Exception as exc:  # noqa: BLE001 - dev server, report and move on
        sys.stderr.write(f"[ai] Groq request failed: {type(exc).__name__}\n")
        return None, False


class Handler(BaseHTTPRequestHandler):
    server_version = "MarketEyeDev/0.2"
    last_ai_call = 0.0

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        path = urlsplit(self.path).path

        if path in ("/", "/index.html"):
            self._send_file(INDEX, "text/html; charset=utf-8")
            return

        if path in ("/overview", "/overview/"):
            self._send_file(OVERVIEW, "text/html; charset=utf-8")
            return

        if path == "/healthz":
            self._send_bytes(b"ok\n", "text/plain; charset=utf-8")
            return

        if path.startswith("/static/"):
            candidate = (ROOT / path.lstrip("/")).resolve()
            if STATIC_DIR in candidate.parents and candidate.is_file():
                self._send_file(candidate)
                return

        self.send_error(404, "Not found")

    def do_POST(self) -> None:  # noqa: N802 - stdlib naming
        path = urlsplit(self.path).path
        if path == "/api/ai/note":
            self._handle_ai_note()
            return
        self.send_error(404, "Not found")

    # --- AI note ---------------------------------------------------------

    def _handle_ai_note(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_AI_BODY:
            self._send_json(400, {"error": "bad_request", "message": "Invalid body."})
            return

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(400, {"error": "bad_request", "message": "Invalid JSON."})
            return
        if not isinstance(payload, dict) or not payload:
            self._send_json(400, {"error": "bad_request", "message": "Invalid payload."})
            return

        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not api_key:
            self._send_json(
                503,
                {
                    "error": "ai_unavailable",
                    "message": "AI note is not configured in this demo.",
                },
            )
            return

        now = time.monotonic()
        if now - Handler.last_ai_call < AI_MIN_INTERVAL:
            self._send_json(
                429,
                {"error": "too_many_requests", "message": "Give it a second."},
            )
            return
        Handler.last_ai_call = now

        model = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant").strip()
        note, ok = _groq_note(api_key, model or "llama-3.1-8b-instant", payload)
        if not ok:
            self._send_json(
                502,
                {
                    "error": "ai_failed",
                    "message": "The AI note is unavailable right now.",
                },
            )
            return

        self._send_json(200, {"note": note})

    # --- helpers ---------------------------------------------------------

    def _send_file(self, file_path: Path, content_type: str | None = None) -> None:
        if not file_path.is_file():
            self.send_error(404, "Not found")
            return
        if content_type is None:
            content_type = (
                mimetypes.guess_type(file_path.name)[0]
                or "application/octet-stream"
            )
        self._send_bytes(file_path.read_bytes(), content_type)

    def _send_bytes(self, body: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("[dev-server] " + fmt % args + "\n")


def main() -> None:
    load_env()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"MarketEye dev server: http://127.0.0.1:{port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
