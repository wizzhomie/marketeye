"""CSV export of the demo price history.

The panels render the same data this module flattens into one table for a
spreadsheet: one row per day, product and competitor, plus our own price so the
comparison survives the export. It reads the demo payload (``storage.bootstrap``)
— it is a view, not a second source of truth.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

HEADER = ["date", "product_id", "product", "competitor", "price", "currency", "our_price"]


def _amount(value: float | int) -> float | int:
    """Drop the trailing .0 so a spreadsheet sees 399, not 399.0."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def history_rows(data: dict) -> list[list]:
    """Rows in fixture order: day, then product, then competitor."""
    rows = []
    for day in data["history"]:
        for product in data["products"]:
            product_id = product["id"]
            for competitor in data["competitors"]:
                rows.append(
                    [
                        day["date"],
                        product_id,
                        product["name"],
                        competitor,
                        _amount(day["prices"][product_id][competitor]),
                        data["currency"],
                        _amount(data["ourPrices"][product_id]),
                    ]
                )
    return rows


def history_csv(data: dict) -> str:
    """The whole price history as CSV text (UTF-8, comma-separated)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(HEADER)
    writer.writerows(history_rows(data))
    return buffer.getvalue()


def suggest_filename(data: dict) -> str:
    """``marketeye-history-2026-11-16.csv`` from the last history day."""
    last = data["history"][-1]["date"]
    try:
        stamp = datetime.strptime(last, "%d %B %Y").date().isoformat()
    except (TypeError, ValueError):
        stamp = "latest"
    return f"marketeye-history-{stamp}.csv"
