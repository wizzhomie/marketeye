# MarketEye

**Watch what competitors do with prices — see the change before it hurts the deal.**

MarketEye is a B2B SaaS prototype for a small distributor or retailer: add the
products you sell and the pages where competitors sell the same things, and every
day the service records their prices. The dashboard shows what moved, by how much
and when; a digest and alerts tell the buyer before a deal is lost to a cheaper
competitor.

> Status: **front-end first.** The landing page is built and runs on saved demo
> data. The dashboard and the FastAPI backend are next. This is a portfolio
> project, not a production platform.

## The problem, in one paragraph

A small distributor buys and sells a few hundred SKUs. Competitors publish prices
on their websites, but nobody has time to check them every day. So the buyer
learns that "the competitor dropped prices on cement by 12%" either by accident,
from a customer, or after losing an order. The information exists in public HTML;
what is missing is a daily, comparable, alerting view of it.

## What the first version shows

- A landing page that explains the product: a problem story, three steps, feature
  list and one demo day of the future panel — all in the project's design code.
- A watch list: product + competitor + URL (a seed set of 5 products × 3
  competitors for the demo).
- A daily snapshot of each page, with the price parsed and stored as history.
- A dashboard: current price, change since the previous snapshot, a small price
  history chart, and the market spread per product.
- An alert when a price moves beyond a threshold, and a short daily digest
  (console/file first, Telegram later if requested).
- CSV export of the history.

## Design code

The interface is a black-and-white 1950s cartoon: thick ink outlines, paper grain,
halftone dots, poster typography and a pair of big eyes as the brand mark. It has
to stay readable, so the monochrome palette carries meaning through shapes rather
than colour: price moves are arrows and `+`/`−` signs, alerts are inverted black
plates. Everything is drawn with CSS and inline SVG — no external fonts, images or
JS libraries, so the demo also works offline.

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

## Run it

No dependencies yet: a small Python standard-library server serves the landing
page. The FastAPI app will take over the same port later.

```bash
./dev.sh start     # http://127.0.0.1:8767/
./dev.sh status
./dev.sh stop
```

DocFlow keeps port 8765; MarketEye uses **8767**.

## Status and limits

- Landing page implemented and checked at desktop, tablet and mobile widths.
- Interface copy is in English (the product's language); the chapter text here and
  in `memory/` is in Russian for the owner.
- Dashboard, storage, collection and alerts are not implemented yet.
- Live collection is deliberately not the first step: the demo proves the product
  mechanics on saved snapshots, then a live adapter is added per site.
- No accounts, roles or billing; one workspace, one user.
- The demo is a portfolio demonstration, not a claim of production readiness.

## Repository layout

```text
dev.sh             start / stop / status for the local demo (port 8767)
dev_server.py      tiny standard-library static server (replaced by FastAPI)
templates/         landing page markup
static/            landing styles and the eye-tracking script
docs/              product brief, demo script (planned)
memory/            working memory: handoff, decisions, plain log
app.py             FastAPI app: watch list, dashboard, API (planned)
collector.py       snapshot and HTTP collection (planned)
parsers/           per-site parser profiles (planned)
storage.py         SQLite history and queries (planned)
alerts.py          threshold checks, digest (planned)
tests/             deterministic fixtures and parser checks (planned)
```

## Documentation

- Working transfer for the development chat (Russian): [`memory/handoff.md`](memory/handoff.md).
- Agent rules for this repository: [`AGENTS.md`](AGENTS.md).
