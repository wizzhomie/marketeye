# MarketEye

**Watch what competitors do with prices — see the change before it hurts the deal.**

MarketEye is a B2B SaaS prototype for a small distributor or retailer: add the
products you sell and the pages where competitors sell the same things, and every
day the service records their prices. The dashboard shows what moved, by how much
and when; a digest and alerts tell the buyer before a deal is lost to a cheaper
competitor.

> Status: **foundation only.** The product is described here; the first working
> version is built in a separate development chat. This is a portfolio project,
> not a production platform.

## The problem, in one paragraph

A small distributor buys and sells a few hundred SKUs. Competitors publish prices
on their websites, but nobody has time to check them every day. So the buyer
learns that "the competitor dropped prices on cement by 12%" either by accident,
from a customer, or after losing an order. The information exists in public HTML;
what is missing is a daily, comparable, alerting view of it.

## What the first version shows

- A watch list: product + competitor + URL (a seed set of 5 products × 3
  competitors for the demo).
- A daily snapshot of each page, with the price parsed and stored as history.
- A dashboard: current price, change since the previous snapshot, a small price
  history chart, and the market spread per product.
- An alert when a price moves beyond a threshold, and a short daily digest
  (Telegram-first, e-mail optional).
- CSV export of the history.

## How it works (planned)

```text
watch list (product, competitor, url)
        │
        ▼
   collector ── HTTP adapter (live sites) / snapshot adapter (demo)
        │
        ▼
   parser profiles ── per-site selectors, kept as data, not code branches
        │
        ▼
   SQLite history ──► dashboard (FastAPI + plain HTML/JS) ──► alerts / digest
```

The snapshot adapter is the honest core of the demo: live sites block bots, change
layouts and need consent, so the demo runs on saved pages and a local fake source.
A live site is enabled by adding its parser profile and pointing the collector at
it — the same "profile is data" approach as the first portfolio project.

## Status and limits

- Nothing is implemented yet; this repository holds the brief and the working
  memory for the development chat.
- Live collection is deliberately not the first step: the demo proves the product
  mechanics on saved snapshots, then a live adapter is added per site.
- No accounts, roles or billing; one workspace, one user.
- The demo is a portfolio demonstration, not a claim of production readiness.

## Repository layout (planned)

```text
app.py             FastAPI app: watch list, dashboard, API
collector.py       snapshot and HTTP collection
parsers/           per-site parser profiles (selectors as data)
storage.py         SQLite history and queries
alerts.py          threshold checks, digest
templates/         dashboard UI
tests/             deterministic fixtures and parser checks
docs/              product brief, demo script
memory/            working memory: handoff, decisions, plain log
```

## Documentation

- Working transfer for the development chat (Russian): [`memory/handoff.md`](memory/handoff.md).
- Agent rules for this repository: [`AGENTS.md`](AGENTS.md).
