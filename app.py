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
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

import ai_note
import alerts
import analysis
import collector
import daily
import demo_shop
import discover
import discovered
import export
import page_parser
import storage
import telegram

ROOT = Path(__file__).resolve().parent
TEMPLATES = ROOT / "templates"
MAX_AI_BODY = 32 * 1024
AI_MIN_INTERVAL = 2.0
DEMO_SHOP_PORT = 8768

PAGES = {
    "/": "index.html",
    "/overview": "overview.html",
    "/overview/": "overview.html",
    "/product": "product.html",
    "/product/": "product.html",
    "/alerts": "alerts.html",
    "/alerts/": "alerts.html",
    "/competitors": "competitors.html",
    "/competitors/": "competitors.html",
    "/live": "live.html",
    "/live/": "live.html",
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

    # The "competitor shop" is a real HTTP server on localhost; the collector
    # fetches it like any other page, so the live path is not a special case.
    shop = None
    try:
        shop = demo_shop.start(DEMO_SHOP_PORT)
    except OSError as exc:
        print(f"[demo-shop] could not start on port {DEMO_SHOP_PORT}: {exc}", flush=True)
    app.state.demo_shop = shop
    yield
    if shop is not None:
        shop.shutdown()
        shop.server_close()


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


@app.get("/demo-shop", include_in_schema=False)
def demo_shop_page() -> Response:
    """The local "competitor shop" page, for a human to look at."""
    return Response(
        content=demo_shop.render_page(),
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/bootstrap")
def api_bootstrap() -> dict:
    """Everything the panels need: products, competitors, 15 days, rules."""
    return _bootstrap()


@app.get("/api/competitors")
def api_competitors(snapshot: int | None = None) -> dict:
    """Gap by competitor, price index and plain findings for one snapshot."""
    connection = storage.connect()
    try:
        data = storage.bootstrap(connection)
    finally:
        connection.close()
    try:
        return analysis.evaluate(data, snapshot)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


async def _json_body(request: Request) -> dict:
    """Parse a JSON object body; raise 400 for anything else."""
    raw = await request.body()
    if not raw:
        return {}
    if len(raw) > MAX_AI_BODY:
        raise HTTPException(status_code=400, detail="Body is too large.")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object.")
    return payload


@app.get("/api/alerts/rules")
def api_alert_rules() -> dict:
    """The stored rules (the browser renders them, the server keeps them)."""
    return {"rules": _bootstrap()["alertRules"]}


@app.put("/api/alerts/rules")
async def api_save_alert_rules(request: Request) -> dict:
    payload = await _json_body(request)
    defaults = _bootstrap()["alertRules"]
    try:
        rules = alerts.normalize_rules(payload.get("rules"), defaults)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    connection = storage.connect()
    try:
        storage.save_alert_rules(connection, rules)
    finally:
        connection.close()
    return {"rules": rules}


@app.post("/api/alerts/evaluate")
async def api_evaluate_alerts(request: Request) -> dict:
    """Run the rules over one snapshot and return matches, stats and the digest."""
    payload = await _json_body(request)
    connection = storage.connect()
    try:
        data = storage.bootstrap(connection)
    finally:
        connection.close()
    try:
        return alerts.evaluate(data, payload.get("rules"), payload.get("snapshot"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


_live_lock = asyncio.Lock()


def _live_payload() -> dict:
    """Configured live sources, their readings and the latest change."""
    sources = collector.load_sources()
    profiles = page_parser.load_profiles()
    connection = storage.connect()
    try:
        payload_sources = []
        collected_at = None
        for source in sources:
            readings = storage.live_readings(connection, source["id"], limit=8)
            latest = readings[0] if readings else None
            ok_readings = [reading for reading in readings if reading["status"] == "ok"]
            last_ok = ok_readings[0] if ok_readings else None
            previous_ok = ok_readings[1] if len(ok_readings) > 1 else None

            change = None
            if last_ok and previous_ok:
                amount = round(last_ok["price"] - previous_ok["price"], 2)
                percent = (
                    abs(round(amount / previous_ok["price"] * 100))
                    if previous_ok["price"]
                    else 0
                )
                change = {
                    "amount": amount,
                    "percent": percent,
                    "direction": "down" if amount < 0 else ("up" if amount > 0 else "flat"),
                    "fromPrice": previous_ok["price"],
                }

            if latest and (collected_at is None or latest["fetchedAt"] > collected_at):
                collected_at = latest["fetchedAt"]

            profile = profiles.get(source["profile"], {})
            payload_sources.append(
                {
                    "id": source["id"],
                    "competitor": source["competitor"],
                    "product": source["product"],
                    "url": source["url"],
                    "previewUrl": source.get("previewUrl", source["url"]),
                    "profile": source["profile"],
                    "profileTitle": profile.get("title", source["profile"]),
                    "latest": latest,
                    "lastOk": last_ok,
                    "change": change,
                    "readings": readings,
                }
            )

        return {
            "sources": payload_sources,
            "collectedAt": collected_at,
            "demoShop": {
                "url": f"http://127.0.0.1:{DEMO_SHOP_PORT}/cement",
                "tick": demo_shop.state()["tick"],
                "price": demo_shop.current_price(),
            },
        }
    finally:
        connection.close()


@app.get("/api/live")
def api_live() -> dict:
    return _live_payload()


@app.post("/api/live/collect")
async def api_live_collect() -> dict:
    """Fetch every live source once, store the readings, move the demo shop on."""
    if _live_lock.locked():
        return JSONResponse({"detail": "Collection is already running."}, status_code=409)
    async with _live_lock:
        readings = await asyncio.to_thread(collector.collect_all)
        connection = storage.connect()
        try:
            for reading in readings:
                storage.add_live_reading(connection, reading)
        finally:
            connection.close()
        demo_shop.advance_tick()
        return _live_payload()


@app.post("/api/live/reset")
def api_live_reset() -> dict:
    """Forget the readings and put the demo shop back to its first price."""
    connection = storage.connect()
    try:
        storage.delete_live_readings(connection)
    finally:
        connection.close()
    demo_shop.reset()
    daily.clear_digests()
    discovered.clear()
    return _live_payload()


@app.get("/api/daily")
def api_daily() -> dict:
    """The scheduler state, the latest saved digest and the delivery channel."""
    return {
        "scheduler": daily.scheduler_status(),
        "latest": daily.latest_digest(),
        "delivery": telegram.config(),
    }


@app.post("/api/daily/run")
async def api_daily_run() -> dict:
    """Run one daily pass now: collect, store, advance the demo shop, save digest."""
    if _live_lock.locked():
        return JSONResponse({"detail": "A check is already running."}, status_code=409)
    async with _live_lock:
        try:
            result = await asyncio.to_thread(
                daily.run_pass, sender=daily.default_sender()
            )
        except Exception as exc:  # noqa: BLE001 - report the reason, keep the server up
            return JSONResponse(
                {"detail": f"The daily check failed: {type(exc).__name__}."},
                status_code=500,
            )
    return {
        "scheduler": daily.scheduler_status(),
        "latest": daily.latest_digest(),
        "delivery": telegram.config(),
        "result": result,
    }


@app.post("/api/daily/send")
async def api_daily_send() -> JSONResponse:
    """Send the latest saved digest to Telegram (the button on Live check)."""
    result = await asyncio.to_thread(daily.send_latest)
    if result.get("sent"):
        return JSONResponse({"sent": True, "date": result.get("date")}, status_code=200)
    error = result.get("error") or "Telegram delivery failed."
    status = {"no_digest": 400, "not_configured": 503}.get(result.get("reason"), 502)
    return JSONResponse({"detail": error}, status_code=status)


@app.post("/api/discover")
async def api_discover(request: Request) -> JSONResponse:
    """Ask the model for candidate pages (or verify one pasted URL), then verify."""
    payload = await _json_body(request)
    url = str(payload.get("url") or "").strip()
    product = str(payload.get("product") or "").strip()
    if not url and not product:
        return JSONResponse(
            {"detail": "Give a product name or a page URL."}, status_code=400
        )
    if len(product) > 200 or len(url) > 2000:
        return JSONResponse({"detail": "That input is too long."}, status_code=400)

    if url:
        if not re.match(r"^https?://", url, re.IGNORECASE):
            return JSONResponse(
                {"detail": "The page URL must start with http:// or https://."},
                status_code=400,
            )
        candidate = {"url": url, "competitor": discover.hostname(url), "product": product}
        verified = await asyncio.to_thread(discover.verify_candidate, candidate)
        return JSONResponse({"source": "manual", "candidates": [verified]}, status_code=200)

    if not ai_note.api_key():
        return JSONResponse(
            {"detail": "AI page search is not configured in this demo."}, status_code=503
        )
    now = time.monotonic()
    if now - _ai_state["last_call"] < AI_MIN_INTERVAL:
        return JSONResponse({"detail": "Give it a second."}, status_code=429)
    _ai_state["last_call"] = now

    proposals, error = await asyncio.to_thread(discover.ai_candidates, product)
    if error:
        return JSONResponse({"detail": error}, status_code=502)
    verified = await asyncio.to_thread(discover.verify_all, proposals)
    return JSONResponse({"source": "ai", "candidates": verified}, status_code=200)


@app.post("/api/discover/accept")
async def api_discover_accept(request: Request) -> JSONResponse:
    """Re-verify a candidate on the server, then watch it."""
    payload = await _json_body(request)
    url = str(payload.get("url") or "").strip()
    if not re.match(r"^https?://", url, re.IGNORECASE):
        return JSONResponse(
            {"detail": "The page URL must start with http:// or https://."},
            status_code=400,
        )
    candidate = {
        "url": url,
        "competitor": str(payload.get("competitor") or "").strip(),
        "product": str(payload.get("product") or "").strip(),
    }
    try:
        accepted = await asyncio.to_thread(discover.accept, candidate)
    except ValueError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=400)

    source = accepted["source"]
    reading = await asyncio.to_thread(
        collector.collect_source, source, page_parser.load_profiles()
    )
    connection = storage.connect()
    try:
        storage.add_live_reading(connection, reading)
    finally:
        connection.close()
    return JSONResponse(
        {"source": source, "profileId": accepted["profileId"], "reading": reading},
        status_code=200,
    )


@app.get("/api/products/{product_id}/history")
def api_product_history(product_id: str, days: int = 14) -> dict:
    connection = storage.connect()
    try:
        return storage.product_history(connection, product_id, days)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown product") from exc
    finally:
        connection.close()


@app.get("/api/export/history.csv", include_in_schema=False)
def api_export_history() -> Response:
    """The whole demo price history as one flat CSV file."""
    connection = storage.connect()
    try:
        data = storage.bootstrap(connection)
    finally:
        connection.close()
    return Response(
        content=export.history_csv(data),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{export.suggest_filename(data)}"',
            "Cache-Control": "no-store",
        },
    )


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
