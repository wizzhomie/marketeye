"""SQLite storage for the MarketEye demo.

The demo database is derived, not authored: it is rebuilt from
``static/demo.json`` on every start, so the panels always show the same
fixtures and a broken database can be fixed by restarting the app.

Shape of the demo payload (also what ``bootstrap()`` reconstructs):

    {
      currency, ourPrices, products, competitors,
      snapshots, history, alertRules, collection
    }
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEMO_JSON = ROOT / "static" / "demo.json"
DB_PATH = ROOT / "data" / "marketeye.db"

SNAPSHOT_WINDOW = 3

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    our_price REAL NOT NULL,
    position INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS competitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    position INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS prices (
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    competitor_id INTEGER NOT NULL REFERENCES competitors(id) ON DELETE CASCADE,
    price REAL NOT NULL,
    PRIMARY KEY (snapshot_id, product_id, competitor_id)
);

CREATE TABLE IF NOT EXISTS alert_rules (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    enabled INTEGER NOT NULL,
    threshold REAL,
    position INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Live readings are real fetched pages, not demo fixtures: the seed leaves this
-- table alone, so a restart keeps what was actually collected.
CREATE TABLE IF NOT EXISTS live_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    status TEXT NOT NULL,
    title TEXT,
    price REAL,
    currency TEXT,
    raw_value TEXT,
    note TEXT,
    url TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_live_readings_source
    ON live_readings (source_id, id DESC);
"""


def load_demo() -> dict:
    """Read the canonical demo fixtures."""
    return json.loads(DEMO_JSON.read_text(encoding="utf-8"))


def connect(path: Path | str = DB_PATH) -> sqlite3.Connection:
    """Open the demo database, creating the folder when needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA)
    connection.commit()


def _clear(connection: sqlite3.Connection) -> None:
    for table in ("prices", "snapshots", "alert_rules", "products", "competitors", "meta"):
        connection.execute(f"DELETE FROM {table}")


def seed(connection: sqlite3.Connection, data: dict) -> None:
    """Rebuild the database from the demo fixtures (idempotent)."""
    history = data["history"]
    snapshots = data["snapshots"]
    if [day["date"] for day in snapshots] != [day["date"] for day in history[-SNAPSHOT_WINDOW:]]:
        raise ValueError(
            "demo fixtures are inconsistent: snapshots must be the last "
            f"{SNAPSHOT_WINDOW} history days"
        )

    with connection:
        _clear(connection)

        connection.executemany(
            "INSERT INTO products (id, name, our_price, position) VALUES (?, ?, ?, ?)",
            [
                (product["id"], product["name"], data["ourPrices"][product["id"]], index)
                for index, product in enumerate(data["products"])
            ],
        )
        connection.executemany(
            "INSERT INTO competitors (name, position) VALUES (?, ?)",
            [(name, index) for index, name in enumerate(data["competitors"])],
        )

        competitor_rows = {
            row["name"]: row["id"] for row in connection.execute("SELECT id, name FROM competitors")
        }

        for day in history:
            cursor = connection.execute("INSERT INTO snapshots (date) VALUES (?)", (day["date"],))
            snapshot_id = cursor.lastrowid
            connection.executemany(
                "INSERT INTO prices (snapshot_id, product_id, competitor_id, price) "
                "VALUES (?, ?, ?, ?)",
                [
                    (snapshot_id, product_id, competitor_rows[competitor], price)
                    for product_id, prices in day["prices"].items()
                    for competitor, price in prices.items()
                ],
            )

        connection.executemany(
            "INSERT INTO alert_rules (id, kind, title, description, enabled, threshold, position) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    rule["id"],
                    rule["kind"],
                    rule["title"],
                    rule["description"],
                    1 if rule.get("enabled") else 0,
                    rule.get("threshold"),
                    index,
                )
                for index, rule in enumerate(data["alertRules"])
            ],
        )

        connection.executemany(
            "INSERT INTO meta (key, value) VALUES (?, ?)",
            [
                ("currency", data["currency"]),
                ("collection", json.dumps(data["collection"], ensure_ascii=False)),
                ("snapshot_window", str(SNAPSHOT_WINDOW)),
            ],
        )


_READING_FIELDS = {
    "sourceId": "source_id",
    "fetchedAt": "fetched_at",
    "status": "status",
    "title": "title",
    "price": "price",
    "currency": "currency",
    "rawValue": "raw_value",
    "note": "note",
    "url": "url",
}


def _reading_row(row: sqlite3.Row) -> dict:
    reading = {"id": row["id"]}
    for name, column in _READING_FIELDS.items():
        reading[name] = row[column]
    return reading


def add_live_reading(connection: sqlite3.Connection, reading: dict) -> int:
    """Store one fetched reading (ok or error) and return its id."""
    cursor = connection.execute(
        "INSERT INTO live_readings "
        "(source_id, fetched_at, status, title, price, currency, raw_value, note, url) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            reading["sourceId"],
            reading["fetchedAt"],
            reading["status"],
            reading.get("title"),
            reading.get("price"),
            reading.get("currency"),
            reading.get("rawValue"),
            reading.get("note"),
            reading["url"],
        ),
    )
    connection.commit()
    return int(cursor.lastrowid)


def live_readings(
    connection: sqlite3.Connection, source_id: str, limit: int = 8
) -> list[dict]:
    """The newest readings for one source, newest first."""
    rows = connection.execute(
        "SELECT * FROM live_readings WHERE source_id = ? ORDER BY id DESC LIMIT ?",
        (source_id, limit),
    )
    return [_reading_row(row) for row in rows]


def delete_live_readings(connection: sqlite3.Connection) -> None:
    with connection:
        connection.execute("DELETE FROM live_readings")


def save_alert_rules(connection: sqlite3.Connection, rules: list[dict]) -> None:
    """Persist enabled/threshold for known rules (the demo DB lives in data/)."""
    with connection:
        for rule in rules:
            connection.execute(
                "UPDATE alert_rules SET enabled = ?, threshold = ? WHERE id = ?",
                (1 if rule["enabled"] else 0, rule.get("threshold"), rule["id"]),
            )


def _history_rows(connection: sqlite3.Connection) -> list[dict]:
    """All daily price records, oldest first."""
    snapshots = list(connection.execute("SELECT id, date FROM snapshots ORDER BY id"))
    products = [
        row["id"] for row in connection.execute("SELECT id FROM products ORDER BY position")
    ]
    competitors = [
        row["name"]
        for row in connection.execute("SELECT name FROM competitors ORDER BY position")
    ]

    prices: dict[int, dict[str, dict[str, float]]] = {snapshot["id"]: {} for snapshot in snapshots}
    for row in connection.execute(
        "SELECT p.snapshot_id, p.product_id, c.name AS competitor, p.price "
        "FROM prices p JOIN competitors c ON c.id = p.competitor_id"
    ):
        prices[row["snapshot_id"]].setdefault(row["product_id"], {})[row["competitor"]] = (
            row["price"]
        )

    history = []
    for snapshot in snapshots:
        day = {
            product_id: {
                competitor: prices[snapshot["id"]][product_id][competitor]
                for competitor in competitors
            }
            for product_id in products
        }
        history.append({"date": snapshot["date"], "prices": day})
    return history


def bootstrap(connection: sqlite3.Connection) -> dict:
    """Reconstruct the demo payload the panels load on startup."""
    products = list(
        connection.execute("SELECT id, name, our_price FROM products ORDER BY position")
    )
    competitors = [
        row["name"] for row in connection.execute("SELECT name FROM competitors ORDER BY position")
    ]
    meta = {row["key"]: row["value"] for row in connection.execute("SELECT key, value FROM meta")}
    history = _history_rows(connection)

    rules = []
    for row in connection.execute("SELECT * FROM alert_rules ORDER BY position"):
        rule = {
            "id": row["id"],
            "kind": row["kind"],
            "title": row["title"],
            "description": row["description"],
            "enabled": bool(row["enabled"]),
        }
        if row["threshold"] is not None:
            rule["threshold"] = row["threshold"]
        rules.append(rule)

    return {
        "currency": meta["currency"],
        "ourPrices": {product["id"]: product["our_price"] for product in products},
        "products": [{"id": product["id"], "name": product["name"]} for product in products],
        "competitors": competitors,
        "snapshots": history[-SNAPSHOT_WINDOW:],
        "history": history,
        "alertRules": rules,
        "collection": json.loads(meta["collection"]),
    }


def product_history(connection: sqlite3.Connection, product_id: str, days: int = 14) -> dict:
    """Fourteen days of prices for one product, ending with the latest snapshot."""
    payload = bootstrap(connection)
    product = next(
        (item for item in payload["products"] if item["id"] == product_id), None
    )
    if product is None:
        raise KeyError(product_id)
    window = payload["history"][-max(1, min(days, len(payload["history"]))) :]
    return {
        "product": product,
        "ourPrice": payload["ourPrices"][product_id],
        "currency": payload["currency"],
        "competitors": payload["competitors"],
        "days": [
            {
                "date": day["date"],
                "ourPrice": payload["ourPrices"][product_id],
                "prices": day["prices"][product_id],
            }
            for day in window
        ],
    }
