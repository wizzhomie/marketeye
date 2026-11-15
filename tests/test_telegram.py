"""Deterministic tests for Telegram delivery (a local mock, never the network)."""

from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

import telegram

REQUESTS: list[dict] = []


class _Handler(BaseHTTPRequestHandler):
    responses: dict = {}

    def do_POST(self):  # noqa: N802 - stdlib naming
        self._handle()

    def do_GET(self):  # noqa: N802 - stdlib naming
        self._handle()

    def _handle(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        REQUESTS.append(
            {"path": self.path, "body": json.loads(raw) if raw else None}
        )
        method = self.path.split("?")[0].rstrip("/").split("/")[-1]
        status, payload = self.responses.get(
            method, (200, {"ok": True, "result": {"message_id": 1}})
        )
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        return


class TelegramTests(unittest.TestCase):
    def setUp(self):
        REQUESTS.clear()
        _Handler.responses = {}
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        patcher = mock.patch.object(
            telegram, "API_ROOT", f"http://127.0.0.1:{self.server.server_address[1]}"
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_sends_one_plain_message(self):
        result = telegram.send("MarketEye · daily check\nhello", token="TOKEN", chat_id="42")
        self.assertTrue(result["sent"])
        self.assertEqual(len(REQUESTS), 1)
        self.assertEqual(REQUESTS[0]["path"], "/botTOKEN/sendMessage")
        self.assertEqual(REQUESTS[0]["body"]["chat_id"], "42")
        self.assertIn("MarketEye · daily check", REQUESTS[0]["body"]["text"])
        self.assertTrue(REQUESTS[0]["body"]["disable_web_page_preview"])

    def test_unconfigured_sends_nothing(self):
        with mock.patch.object(telegram, "_env", lambda name: ""):
            self.assertFalse(telegram.config()["configured"])
            result = telegram.send("hello")
        self.assertFalse(result["sent"])
        self.assertIn("not configured", result["error"])
        self.assertEqual(REQUESTS, [])

    def test_telegram_error_description_is_reported(self):
        _Handler.responses = {
            "sendMessage": (401, {"ok": False, "description": "Unauthorized"})
        }
        result = telegram.send("hello", token="TOKEN", chat_id="42")
        self.assertFalse(result["sent"])
        self.assertEqual(result["error"], "Unauthorized")
        self.assertNotIn("TOKEN", result["error"])

    def test_unreachable_telegram_is_honest(self):
        with mock.patch.object(telegram, "API_ROOT", "http://127.0.0.1:1"):
            result = telegram.send("hello", token="TOKEN", chat_id="42")
        self.assertFalse(result["sent"])
        self.assertIn("could not reach Telegram", result["error"])

    def test_long_digest_is_truncated_below_the_limit(self):
        telegram.send("x" * 5000, token="TOKEN", chat_id="42")
        self.assertLessEqual(len(REQUESTS[0]["body"]["text"]), telegram.MAX_MESSAGE)

    def test_config_never_returns_the_token(self):
        env = {"TELEGRAM_BOT_TOKEN": "SECRET", "TELEGRAM_CHAT_ID": "42"}
        with mock.patch.object(telegram, "_env", lambda name: env.get(name, "")):
            config = telegram.config()
        self.assertEqual(set(config), {"channel", "configured", "hasToken", "hasChat"})
        self.assertTrue(config["configured"])
        self.assertNotIn("SECRET", json.dumps(config))

    def test_discover_chat_id_from_the_last_message(self):
        _Handler.responses = {
            "getUpdates": (
                200,
                {
                    "ok": True,
                    "result": [
                        {"message": {"chat": {"id": 100, "first_name": "Old"}}},
                        {"message": {"chat": {"id": 777, "first_name": "Owner"}}},
                    ],
                },
            )
        }
        found = telegram.discover_chat_id(token="TOKEN")
        self.assertTrue(found["found"])
        self.assertEqual(found["chatId"], "777")
        self.assertEqual(found["chatTitle"], "Owner")

    def test_discover_reports_when_the_owner_has_not_written_yet(self):
        _Handler.responses = {"getUpdates": (200, {"ok": True, "result": []})}
        found = telegram.discover_chat_id(token="TOKEN")
        self.assertFalse(found["found"])
        self.assertIn("press Start", found["error"])


if __name__ == "__main__":
    unittest.main()
