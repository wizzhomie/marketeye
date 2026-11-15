"""Alert rules, matches and the daily digest — computed on the server.

The browser only renders what this module returns. Rules are plain data
(``id``, ``kind``, ``enabled``, ``threshold``) so they can be stored, validated
and changed without touching the UI.

The only AI in the product lives next door in ``ai_note.py``; nothing here
invents numbers.
"""

from __future__ import annotations

import math
from typing import Any

RULE_KINDS = ("below", "drop", "rise")
RULE_ORDER = {kind: index for index, kind in enumerate(RULE_KINDS)}
MIN_THRESHOLD = 1
MAX_THRESHOLD = 50


def _round_half_up(value: float) -> int:
    """Round like JavaScript's Math.round (half away from zero)."""
    return int(math.floor(abs(value) + 0.5))


def _fmt(value: float | int) -> str:
    """Thousands separators, no trailing .0 (62,500 not 62,500.0)."""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value:,}"


def percent_text(raw: float) -> str:
    """'12', '4' or '0.5' — one decimal only for sub-percent moves."""
    raw = abs(raw)
    rounded = _round_half_up(raw)
    if rounded == 0 and raw > 0:
        return f"{_round_half_up(raw * 10) / 10:g}"
    return str(rounded)


def normalize_rules(raw_rules: Any, defaults: list[dict]) -> list[dict]:
    """Validate rules coming from the browser against the known defaults."""
    rules = []
    for rule in defaults:
        normalized = {
            "id": rule["id"],
            "kind": rule["kind"],
            "title": rule["title"],
            "description": rule["description"],
            "enabled": bool(rule.get("enabled")),
        }
        if rule.get("threshold") is not None:
            normalized["threshold"] = int(rule["threshold"])
        rules.append(normalized)

    if raw_rules is None:
        return rules
    if not isinstance(raw_rules, list):
        raise ValueError("rules must be a list")

    known = {rule["id"]: rule for rule in rules}
    for item in raw_rules:
        if not isinstance(item, dict):
            raise ValueError("each rule must be an object")
        rule = known.get(item.get("id"))
        if rule is None:
            continue
        if "enabled" in item:
            rule["enabled"] = bool(item["enabled"])
        if "threshold" in item and rule["kind"] != "below":
            try:
                threshold = int(item["threshold"])
            except (TypeError, ValueError) as exc:
                raise ValueError("threshold must be a whole percent") from exc
            rule["threshold"] = max(MIN_THRESHOLD, min(threshold, MAX_THRESHOLD))
    return rules


def _day_prices(data: dict, day: dict, product_id: str, competitor: str) -> float:
    return day["prices"][product_id][competitor]


def _alerts_for(data: dict, day_index: int, rules: list[dict]) -> list[dict]:
    """All rule matches for one history day."""
    history = data["history"]
    day = history[day_index]
    before = history[day_index - 1] if day_index > 0 else None
    by_id = {rule["id"]: rule for rule in rules}
    found: list[dict] = []

    for product in data["products"]:
        product_id = product["id"]
        ours = data["ourPrices"][product_id]
        for competitor in data["competitors"]:
            price = _day_prices(data, day, product_id, competitor)
            earlier = (
                _day_prices(data, before, product_id, competitor) if before else price
            )

            below = by_id.get("below")
            if below and below["enabled"] and price < ours:
                found.append(
                    {
                        "kind": "below",
                        "ruleTitle": below["title"],
                        "product": {"id": product_id, "name": product["name"]},
                        "competitor": competitor,
                        "price": price,
                        "ourPrice": ours,
                        "percent": _round_half_up((ours - price) / ours * 100),
                        "percentText": percent_text((ours - price) / ours * 100),
                    }
                )

            drop = by_id.get("drop")
            if drop and drop["enabled"] and before and price < earlier:
                raw = abs((price - earlier) / earlier * 100)
                if raw >= drop["threshold"]:
                    found.append(
                        {
                            "kind": "drop",
                            "ruleTitle": drop["title"],
                            "product": {"id": product_id, "name": product["name"]},
                            "competitor": competitor,
                            "price": price,
                            "from": earlier,
                            "percent": _round_half_up(raw),
                            "percentText": percent_text(raw),
                        }
                    )

            rise = by_id.get("rise")
            if rise and rise["enabled"] and before and price > earlier:
                raw = abs((price - earlier) / earlier * 100)
                if raw >= rise["threshold"]:
                    found.append(
                        {
                            "kind": "rise",
                            "ruleTitle": rise["title"],
                            "product": {"id": product_id, "name": product["name"]},
                            "competitor": competitor,
                            "price": price,
                            "from": earlier,
                            "percent": _round_half_up(raw),
                            "percentText": percent_text(raw),
                        }
                    )

    found.sort(
        key=lambda alert: (
            RULE_ORDER[alert["kind"]],
            -(alert.get("percent") or 0),
        )
    )
    return found


def _rule_label(rule: dict) -> str:
    if rule["kind"] == "below":
        return "below my price"
    name = "price drop" if rule["kind"] == "drop" else "price rise"
    return f"{name} ≥ {rule['threshold']}%"


def _digest(data: dict, alerts: list[dict], rules: list[dict], day_index: int) -> str:
    history = data["history"]
    day = history[day_index]
    previous = history[day_index - 1] if day_index > 0 else None
    currency = data["currency"]
    enabled = [rule for rule in rules if rule["enabled"]]

    lines = ["MarketEye · daily digest", f"{day['date']} · demo data (saved pages)", ""]

    if not alerts:
        lines.extend(["No alerts today. Nothing to report.", ""])
    else:
        products = len({alert["product"]["id"] for alert in alerts})
        lines.extend(
            [
                f"{len(alerts)} alert{'s' if len(alerts) != 1 else ''} across "
                f"{products} product{'s' if products != 1 else ''}.",
                "",
            ]
        )
        for kind in RULE_KINDS:
            group = [alert for alert in alerts if alert["kind"] == kind]
            if not group:
                continue
            lines.append(group[0]["ruleTitle"])
            for alert in group:
                name = f"{alert['competitor']} · {alert['product']['name']}"
                if kind == "below":
                    lines.append(
                        f"- {name} — {_fmt(alert['price'])} {currency}, "
                        f"{alert['percent']}% below our "
                        f"{_fmt(alert['ourPrice'])} {currency}"
                    )
                else:
                    direction = "lower" if kind == "drop" else "higher"
                    lines.append(
                        f"- {name} — {_fmt(alert['from'])} → "
                        f"{_fmt(alert['price'])} {currency}, "
                        f"{alert['percentText']}% {direction}"
                    )
            lines.append("")

    lines.append(
        "Rules: "
        + (" · ".join(_rule_label(rule) for rule in enabled) if enabled else "none switched on")
    )
    lines.append(
        f"Snapshot: {day['date']}"
        + (f" vs {previous['date']}" if previous else "")
    )
    lines.append("Demo mode: saved pages, no live scraping. Delivery is not connected.")
    lines.append("")
    return "\n".join(lines)


def evaluate(data: dict, raw_rules: Any = None, snapshot_index: int | None = None) -> dict:
    """Evaluate the rules for one snapshot and build the digest."""
    snapshots = data["snapshots"]
    history = data["history"]
    if not snapshots or not history:
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

    rules = normalize_rules(raw_rules, data.get("alertRules", []))
    alerts = _alerts_for(data, day_index, rules)
    digest = _digest(data, alerts, rules, day_index)
    previous = history[day_index - 1] if day_index > 0 else None

    recent = []
    for offset in range(3):
        index = day_index - offset
        if index < 1:
            break
        count = len(_alerts_for(data, index, rules))
        recent.append({"date": history[index]["date"], "alerts": count})

    return {
        "snapshotIndex": snapshot_index,
        "date": history[day_index]["date"],
        "previousDate": previous["date"] if previous else None,
        "rules": rules,
        "alerts": alerts,
        "digest": digest,
        "stats": {
            "rulesOn": sum(1 for rule in rules if rule["enabled"]),
            "rulesTotal": len(rules),
            "alerts": len(alerts),
            "products": len({alert["product"]["id"] for alert in alerts}),
            "digestLines": len(digest.strip().splitlines()),
        },
        "recent": recent,
    }
