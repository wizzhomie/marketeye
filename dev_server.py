#!/usr/bin/env python3
"""Minimal static dev server for the MarketEye front-end.

Standard library only: the first front-end iteration has to run without
installing anything. Once the backend starts, FastAPI takes over the same
port and serves these files itself.

Routes:
    /            -> templates/index.html
    /overview    -> templates/overview.html
    /static/...  -> files from static/
    /healthz     -> "ok" (used by dev.sh)
"""

from __future__ import annotations

import mimetypes
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
STATIC_DIR = (ROOT / "static").resolve()
INDEX = ROOT / "templates" / "index.html"
OVERVIEW = ROOT / "templates" / "overview.html"
DEFAULT_PORT = 8767


class Handler(BaseHTTPRequestHandler):
    server_version = "MarketEyeDev/0.1"

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

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("[dev-server] " + fmt % args + "\n")


def main() -> None:
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
