"""Competitor analysis computed on the server.

Everything here is arithmetic over the saved snapshots: how far each competitor
sits from our price, on how many products it undercuts us, how that gap moved
over the last two weeks, and what it means in one plain sentence. The browser
renders these numbers; nothing is guessed and the model writes nothing here.

The demo day is the second-to-last snapshot, the same day the alerts screen and
the digest use. ``snapshot_index`` moves it, like ``alerts.evaluate``.
"""

from __future__ import annotations

import math
from typing import Any

WINDOW_DAYS = 14


def _round1(value: float) -> float:
    """Round to one decimal, half away from zero (same as the digest)."""
    sign = -1.0 if value < 0 else 1.0
    return sign * math.floor(abs(value) * 10 + 0.5) / 10


def _fmt(value: float | int) -> str:
    """Thousands separators, no trailing .0 (62,500 not 62,500.0)."""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value:,}"


def _money(value: float | int, currency: str) -> str:
    return f"{_fmt(value)} {currency}"


def _short_name(name: str) -> str:
    """'Cement M500 · 50 kg' → 'Cement M500', for sentences and loose tables."""
    return name.split(" · ")[0]


def _index_of(competitor: str, day: dict, products: list[dict], our_prices: dict) -> float:
    """Average of (price / our price - 1) across the watched products."""
    total = 0.0
    for product in products:
        product_id = product["id"]
        price = day["prices"][product_id][competitor]
        ours = our_prices[product_id]
        total += (price - ours) / ours * 100
    return total / len(products)


def _insights(
    products: list[dict],
    rows: list[dict],
    below: list[dict],
    widest: dict,
    currency: str,
    window_days: int,
) -> list[dict]:
    """Plain-language findings built from the numbers above, never from AI."""
    count = len(products)
    main = max(
        rows,
        key=lambda row: (row["below"], row["avgBelow"], row["cheapest"], -row["index"]),
    )
    findings: list[dict] = []

    if below:
        worst = below[0]
        findings.append(
            {
                "kind": "main",
                "text": (
                    f"{main['name']} is your closest competitor — it undercuts you "
                    f"on {main['below']} of {count} products, on average "
                    f"{main['avgBelow']:.1f}% below your price."
                ),
            }
        )
        findings.append(
            {
                "kind": "warn",
                "text": (
                    f"Biggest gap: {worst['productName']} — {worst['competitor']} at "
                    f"{_money(worst['price'], currency)} vs your "
                    f"{_money(worst['ourPrice'], currency)}, "
                    f"{abs(worst['percent']):.1f}% lower."
                ),
            }
        )
    else:
        findings.append(
            {
                "kind": "main",
                "text": (
                    f"{main['name']} sets the lowest prices — on average "
                    f"{abs(main['index']):.1f}% below yours."
                ),
            }
        )
        findings.append(
            {
                "kind": "ok",
                "text": "No competitor is below your price on this snapshot.",
            }
        )

    falling = min(rows, key=lambda row: row["change"])
    if falling["change"] < 0:
        findings.append(
            {
                "kind": "trend",
                "text": (
                    f"{falling['name']} has been cutting prices: its index fell "
                    f"{abs(falling['change']):.1f} points over {window_days} days."
                ),
            }
        )

    at_or_below = [row for row in rows if row["below"] == 0]
    safe = [row for row in products if not row["belowUs"]]
    if len(at_or_below) == len(rows) and len(safe) == count:
        findings.append(
            {
                "kind": "ok",
                "text": "Every watched product is priced at or above you — nothing to answer.",
            }
        )
    elif safe:
        names = ", ".join(row["shortName"] for row in safe)
        findings.append(
            {
                "kind": "ok",
                "text": (
                    f"You are at or below the market on {len(safe)} of {count} "
                    f"products — {names}."
                ),
            }
        )

    findings.append(
        {
            "kind": "info",
            "text": (
                f"Widest spread: {widest['name']} — {widest['cheapest']['competitor']} "
                f"at {_money(widest['cheapest']['price'], currency)} vs "
                f"{widest['dearest']['competitor']} at "
                f"{_money(widest['dearest']['price'], currency)}, "
                f"{widest['spread']:.1f}% apart."
            ),
        }
    )
    return findings


def evaluate(data: dict, snapshot_index: int | None = None) -> dict:
    """Analyse one snapshot: per-competitor gaps, trend and plain findings."""
    snapshots = data.get("snapshots") or []
    history = data.get("history") or []
    products = data.get("products") or []
    competitors = data.get("competitors") or []
    if not snapshots or not history or not products or not competitors:
        raise ValueError("demo data has no snapshots")

    if snapshot_index is None:
        snapshot_index = max(0, len(snapshots) - 2)
    snapshot_index = max(0, min(int(snapshot_index), len(snapshots) - 1))
    snapshot_date = snapshots[snapshot_index]["date"]
    day_index = next(
        (index for index, day in enumerate(history) if day["date"] == snapshot_date),
        None,
    )
    if day_index is None:
        raise ValueError("snapshot date is missing from the history")

    window = history[max(0, day_index - (WINDOW_DAYS - 1)) : day_index + 1]
    day = history[day_index]
    currency = data["currency"]
    our_prices = data["ourPrices"]

    cheapest_prices = {
        product["id"]: min(
            day["prices"][product["id"]][competitor] for competitor in competitors
        )
        for product in products
    }

    rows = []
    for competitor in competitors:
        gaps = []
        below = above = equal = 0
        for product in products:
            product_id = product["id"]
            ours = our_prices[product_id]
            price = day["prices"][product_id][competitor]
            percent = _round1((price - ours) / ours * 100)
            if price < ours:
                below += 1
            elif price > ours:
                above += 1
            else:
                equal += 1
            gaps.append(
                {
                    "productId": product_id,
                    "productName": product["name"],
                    "shortName": _short_name(product["name"]),
                    "price": price,
                    "ourPrice": ours,
                    "percent": percent,
                }
            )

        trend = [
            {"date": when["date"], "index": _round1(_index_of(competitor, when, products, our_prices))}
            for when in window
        ]
        index_now = trend[-1]["index"]
        rows.append(
            {
                "name": competitor,
                "index": index_now,
                "below": below,
                "above": above,
                "equal": equal,
                "avgBelow": (
                    _round1(
                        sum(-gap["percent"] for gap in gaps if gap["percent"] < 0) / below
                    )
                    if below
                    else 0.0
                ),
                "cheapest": sum(
                    1
                    for product in products
                    if day["prices"][product["id"]][competitor]
                    == cheapest_prices[product["id"]]
                ),
                "change": _round1(index_now - trend[0]["index"]),
                "trend": trend,
                "gaps": gaps,
            }
        )

    below_pairs = sorted(
        (
            {"competitor": row["name"], **gap}
            for row in rows
            for gap in row["gaps"]
            if gap["price"] < gap["ourPrice"]
        ),
        key=lambda pair: pair["percent"],
    )

    main = max(
        rows,
        key=lambda row: (row["below"], row["avgBelow"], row["cheapest"], -row["index"]),
    )

    product_rows = []
    for product in products:
        product_id = product["id"]
        ours = our_prices[product_id]
        values = [(row["name"], day["prices"][product_id][row["name"]]) for row in rows]
        cheap_name, cheap_price = min(values, key=lambda item: item[1])
        dear_name, dear_price = max(values, key=lambda item: item[1])
        product_rows.append(
            {
                "id": product_id,
                "name": product["name"],
                "shortName": _short_name(product["name"]),
                "ourPrice": ours,
                "cells": [
                    {
                        "competitor": row["name"],
                        "price": day["prices"][product_id][row["name"]],
                        "percent": next(
                            gap["percent"] for gap in row["gaps"] if gap["productId"] == product_id
                        ),
                    }
                    for row in rows
                ],
                "cheapest": {"competitor": cheap_name, "price": cheap_price},
                "dearest": {"competitor": dear_name, "price": dear_price},
                "spread": (
                    _round1((dear_price - cheap_price) / cheap_price * 100)
                    if cheap_price
                    else 0.0
                ),
                "belowUs": any(price < ours for _, price in values),
            }
        )

    widest = max(product_rows, key=lambda row: row["spread"])
    stats = {
        "products": len(products),
        "competitors": len(competitors),
        "below": len(below_pairs),
        "biggestGap": abs(below_pairs[0]["percent"]) if below_pairs else 0.0,
        "biggestGapProduct": below_pairs[0]["productName"] if below_pairs else None,
        "widestSpread": widest["spread"],
        "widestSpreadProduct": widest["shortName"],
    }

    previous = history[day_index - 1] if day_index > 0 else None
    return {
        "date": day["date"],
        "snapshotIndex": snapshot_index,
        "previousDate": previous["date"] if previous else None,
        "currency": currency,
        "window": {
            "days": len(window),
            "start": window[0]["date"],
            "end": window[-1]["date"],
        },
        "products": product_rows,
        "competitors": rows,
        "main": {
            "name": main["name"],
            "below": main["below"],
            "avgBelow": main["avgBelow"],
            "cheapest": main["cheapest"],
            "change": main["change"],
        },
        "below": below_pairs,
        "insights": _insights(
            product_rows, rows, below_pairs, widest, currency, len(window)
        ),
        "stats": stats,
    }
