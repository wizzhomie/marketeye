# MarketEye

**Watch what competitors do with prices — see the change before it hurts the deal.**

MarketEye is a B2B SaaS prototype for a small distributor or retailer: add the
products you sell and the pages where competitors sell the same things, and every
day the service records their prices. The dashboard shows what moved, by how much
and when; a digest and alerts tell the buyer before a deal is lost to a cheaper
competitor.

> Status: **front-end first.** The landing page, the Overview demo panel, the
> product page with a two-week price history and the Alerts screen with a plain-text
> daily digest are built in a quiet monochrome workspace style; an optional AI buyer
> note is wired to Groq. Real alert delivery, CSV export and the FastAPI backend are
> next. This is a portfolio project, not a production platform.

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
- A **product page** for any product in the watch list: two weeks of daily prices
  in a small line chart (hover a day to read it), the current competitor spread and
  the latest snapshots. It opens on the same day the Overview was showing.
- An **Alerts** screen: three rules with switches and editable thresholds, the
  alerts they trigger on the snapshot, and a one-message daily digest in plain text
  that can be copied or downloaded. Delivery (email or chat) is not connected yet.
- A watch list: product + competitor + URL (a seed set of 5 products × 3
  competitors for the demo).
- A daily snapshot of each page, with the price parsed and stored as history.
- A dashboard: current price, change since the previous snapshot, the price history
  chart and the market spread per product (the product page covers this for now).
- An alert when a price moves beyond a threshold, and a short daily digest —
  shown and downloadable today, delivered to email or chat later.
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
3. Click a product name or **Inspect listing** on an alert → **product page**:
   two weeks of history, the chart, the spread and the latest snapshots.
4. **Collect now** simulates the daily collection on saved pages and appends the
   next snapshot: prices move, moves and alerts update.
5. **Draft with AI** asks the model for a short buyer note based only on that
   verified snapshot (optional — needs a Groq key).
6. **Alerts** (sidebar or “All alerts”): switch rules on and off, change the
   threshold and watch the list and the digest follow; copy the digest or download
   the `.txt`.
7. **Reset demo** brings the baseline back, so the demo can be shown again.
8. The panels state their limits honestly: demo data, saved pages, no live scraping.

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
./dev.sh start     # local site: http://127.0.0.1:8767/, /overview, /product?id=cement, /alerts
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

- Landing page, the Overview demo panel, the product page and the Alerts screen are
  implemented and checked at desktop, tablet and mobile widths.
- The panels run on frozen fixtures (`static/demo-data.js`, including fifteen days
  of prices and the alert rules); collection and rule evaluation run in the browser,
  so the demo is deterministic.
- Real alert delivery (email/chat), CSV export and the FastAPI backend are not
  implemented yet. The digest is generated locally and downloaded as a `.txt`.
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
templates/         landing page, Overview panel, product page and Alerts markup
static/            UI theme, styles/logic for landing, Overview, product and alerts,
                   Inter, demo data
docs/              product brief, demo script (planned)
app.py             FastAPI app: watch list, dashboard, API (planned)
collector.py       snapshot and HTTP collection (planned)
parsers/           per-site parser profiles (planned)
storage.py         SQLite history and queries (planned)
alerts.py          threshold checks, digest (planned)
tests/             deterministic fixtures and parser checks (planned)
```
