"""MarketEye demo backend: FastAPI + SQLite.

Serves the three panels, their static assets, the demo payload from the SQLite
database and the optional AI buyer note. The database is rebuilt from
``static/demo.json`` on every start, so the demo is deterministic.

Run with ``./dev.sh start`` (uvicorn, port 8767) or directly:

    .venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port 8767
"""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

import ai_note
import storage

ROOT = Path(__file__).resolve().parent
TEMPLATES = ROOT / "templates"
MAX_AI_BODY = 32 * 1024
AI_MIN_INTERVAL = 2.0

PAGES = {
    "/": "index.html",
    "/overview": "overview.html",
    "/overview/": "overview.html",
    "/product": "product.html",
    "/product/": "product.html",
    "/alerts": "alerts.html",
    "/alerts/": "alerts.html",
}

_ai_state = {"last_call": 0.0}


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Load .env and rebuild the demo database from the fixtures."""
    ai_note.load_env()
    data = storage.load_demo()
    connection = storage.connect()
    try:
        storage.init_db(connection)
        storage.seed(connection, data)
    finally:
        connection.close()
    yield


app = FastAPI(
    title="MarketEye demo",
    version="0.3.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


def _page(name: str) -> FileResponse:
    path = TEMPLATES / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path, headers={"Cache-Control": "no-store"})


def _bootstrap() -> dict:
    connection = storage.connect()
    try:
        return storage.bootstrap(connection)
    finally:
        connection.close()


@app.get("/healthz", include_in_schema=False)
def healthz() -> PlainTextResponse:
    return PlainTextResponse("ok\n")


for _path, _template in PAGES.items():
    app.add_api_route(
        _path,
        lambda template=_template: _page(template),
        methods=["GET"],
        include_in_schema=False,
    )


@app.get("/api/bootstrap")
def api_bootstrap() -> dict:
    """Everything the panels need: products, competitors, 15 days, rules."""
    return _bootstrap()


@app.get("/api/products")
def api_products() -> list[dict]:
    payload = _bootstrap()
    return [
        {
            "id": product["id"],
            "name": product["name"],
            "ourPrice": payload["ourPrices"][product["id"]],
            "currency": payload["currency"],
        }
        for product in payload["products"]
    ]


@app.get("/api/products/{product_id}/history")
def api_product_history(product_id: str, days: int = 14) -> dict:
    connection = storage.connect()
    try:
        return storage.product_history(connection, product_id, days)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown product") from exc
    finally:
        connection.close()


@app.post("/api/ai/note")
async def api_ai_note(request: Request) -> JSONResponse:
    """Optional Groq note. Explains a verified snapshot; never fetches prices."""
    raw = await request.body()
    if not raw or len(raw) > MAX_AI_BODY:
        return JSONResponse({"error": "bad_request", "message": "Invalid body."}, status_code=400)
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JSONResponse({"error": "bad_request", "message": "Invalid JSON."}, status_code=400)
    if not isinstance(payload, dict) or not payload:
        return JSONResponse({"error": "bad_request", "message": "Invalid payload."}, status_code=400)

    key = ai_note.api_key()
    if not key:
        return JSONResponse(
            {"error": "ai_unavailable", "message": "AI note is not configured in this demo."},
            status_code=503,
        )

    now = time.monotonic()
    if now - _ai_state["last_call"] < AI_MIN_INTERVAL:
        return JSONResponse({"error": "too_many_requests", "message": "Give it a second."}, status_code=429)
    _ai_state["last_call"] = now

    note, ok = await asyncio.to_thread(ai_note.groq_note, key, ai_note.model_name(), payload)
    if not ok:
        return JSONResponse(
            {"error": "ai_failed", "message": "The AI note is unavailable right now."},
            status_code=502,
        )
    return JSONResponse({"note": note}, status_code=200)
