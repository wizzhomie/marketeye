# MarketEye

**Watch what competitors do with prices — see the change before it hurts the deal.**

MarketEye is a B2B SaaS prototype for a small distributor or retailer: add the
products you sell and the pages where competitors sell the same things, and every
day the service records their prices. The dashboard shows what moved, by how much
and when; a digest and alerts tell the buyer before a deal is lost to a cheaper
competitor.

> Status: **front-end first.** The landing page and the Overview demo panel are
> built in a quiet monochrome workspace style; an optional AI buyer note is wired
> to Groq. The product page, price history, alert delivery and the FastAPI backend
> are next. This is a portfolio project, not a production platform.

## The problem, in one paragraph

A small distributor buys and sells a few hundred SKUs. Competitors publish prices
on their websites, but nobody has time to check them every day. So the buyer
learns that "the competitor dropped prices on cement by 12%" either by accident,
from a customer, or after losing an order. The information exists in public HTML;
what is missing is a daily, comparable, alerting view of it.

## What the first version shows

- A landing page that explains the product: a problem story, three steps, feature
  list and one demo day of the future panel — all in the project's design code.
- An **Overview** demo panel: watch list with current prices, change badges since
  the previous snapshot, undercut highlights, snapshot moves, price alerts and an
  optional AI buyer note. "Collect now" simulates the next daily snapshot, "Reset
  demo" makes the show repeatable.
- A watch list: product + competitor + URL (a seed set of 5 products × 3
  competitors for the demo).
- A daily snapshot of each page, with the price parsed and stored as history.
- A dashboard: current price, change since the previous snapshot, a small price
  history chart, and the market spread per product.
- An alert when a price moves beyond a threshold, and a short daily digest
  (console/file first, Telegram later if requested).
- CSV export of the history.

## Design code

The interface is a quiet monochrome workspace inspired by shadcn/ui: warm paper
canvas, a near-black sidebar, white cards on 1px hairline borders with barely
visible elevation, 24px card radii and 18px controls, and compact Inter
typography. The brand mark is a small monogram — two dots in a rounded square.
There is no decorative illustration; the product data is the visual. Price moves
stay readable without colour: arrows and small pills carry the meaning. Inter is
self-hosted in `static/fonts`, and all UI is plain HTML/CSS/JS — no external CDN,
React or Tailwind.

## Demo flow

1. Landing page: the problem, three steps, features and one sample price day.
2. “Watch the demo” → **Overview**: five products × three competitors, current
   prices, change since the previous snapshot, spread and a live alert.
3. **Collect now** simulates the daily collection on saved pages and appends the
   next snapshot: prices move, moves and alerts update.
4. **Draft with AI** asks the model for a short buyer note based only on that
   verified snapshot (optional — needs a Groq key).
5. **Reset demo** brings the baseline back, so the demo can be shown again.
6. The panel states its limits honestly: demo data, saved pages, no live scraping.

## AI buyer note (optional)

The Overview panel can ask Groq to write a short buyer note from the verified
snapshot. This is the only AI in the product: it explains the data, it never
fetches prices or invents numbers. The key lives server-side in `.env`
(`GROQ_API_KEY`, see `.env.example`) and never reaches the browser or git.
Without a key the button honestly says AI is not configured and the rest of the
demo works unchanged. The free Groq tier is enough for a portfolio demo; by
default it uses `openai/gpt-oss-20b` (another model id can be set in `.env`).

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
./dev.sh start     # local site: http://127.0.0.1:8767/ and /overview
./tunnel.sh start  # tailnet address: https://marketeye.tail5bc03a.ts.net/overview
```

For the optional AI note, copy `.env.example` to `.env` and add a free Groq key.
The file is gitignored; the demo works without it.

DocFlow keeps port 8765; MarketEye uses **8767**.

## Live demo (tailnet only)

The landing page is published inside the owner's Tailscale network at
**<https://marketeye.tail5bc03a.ts.net>**. It is served by a separate userspace
Tailscale node called `marketeye` that runs from `.run/ts` (gitignored, fetched
once with `./tunnel.sh setup`) and proxies port 443 to the local dev server.
Tailnet-only: Funnel is not enabled and the public internet cannot reach it.
The host's `server` node (DeepSeek Harness GUI) and the old `orbit-site` node
are untouched.

## Status and limits

- Landing page and the Overview demo panel implemented and checked at desktop,
  tablet and mobile widths.
- Overview runs on frozen fixtures (`static/demo-data.js`); collection is simulated
  in the browser so the demo is deterministic.
- Product page, history chart, CSV export, alert delivery and the FastAPI backend
  are not implemented yet.
- Interface copy is in English (the product's language); this README is in
  Russian for the owner.
- Live collection is deliberately not the first step: the demo proves the product
  mechanics on saved snapshots, then a live adapter is added per site.
- No accounts, roles or billing; one workspace, one user.
- The demo is a portfolio demonstration, not a claim of production readiness.

## Repository layout

```text
dev.sh             start / stop / status for the local demo (port 8767)
dev_server.py      tiny standard-library static server (replaced by FastAPI)
templates/         landing page and Overview panel markup
static/            UI theme, landing and Overview styles/logic, Inter, demo data
docs/              product brief, demo script (planned)
app.py             FastAPI app: watch list, dashboard, API (planned)
collector.py       snapshot and HTTP collection (planned)
parsers/           per-site parser profiles (planned)
storage.py         SQLite history and queries (planned)
alerts.py          threshold checks, digest (planned)
tests/             deterministic fixtures and parser checks (planned)
```
