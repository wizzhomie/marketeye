/*
 * Competitors screen: the server computes the gap, the price index and the
 * plain findings (see /api/competitors); this file only draws them.
 *
 * The 14-day sparkline is measured in pixels on the spot, so it stays sharp on
 * every card width and survives a resize.
 */
(async () => {
  "use strict";

  const el = (selector) => document.querySelector(selector);
  const els = {
    date: el("#snapshot-date"),
    stats: el("#stats"),
    cards: el("#competitor-cards"),
    gapHead: el("#gap-head"),
    gapBody: el("#gap-body"),
    gapsSub: el("#gaps-sub"),
    insights: el("#insights"),
    hint: el("#gap-hint"),
    tableWrap: el(".table-wrap"),
  };
  if (!els.cards || !els.gapBody || !els.insights) return;

  const nf = new Intl.NumberFormat("en-US");
  const fmt = (value) => nf.format(value);
  const one = (value) => value.toFixed(1);
  const signed = (value) => `${value > 0 ? "+" : ""}${one(value)}%`;
  const shortName = (name) => String(name).split(" · ")[0];

  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const shortDate = (text) => {
    const [day, month] = String(text).split(" ");
    const index = MONTHS.indexOf(month);
    return index === -1 ? text : `${day} ${MONTHS[index]}`;
  };

  const esc = (text) =>
    String(text).replace(
      /[&<>"]/g,
      (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[ch]
    );

  const ICONS = {
    main: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="3.2"/><path d="M12 3.5v3M12 17.5v3M3.5 12h3M17.5 12h3"/>',
    warn: '<path d="M12 4.5 21 20H3z"/><path d="M12 10v4.5"/><path d="M12 17.2v.3"/>',
    trend: '<path d="M12 4v13"/><path d="M6.5 11.5 12 17l5.5-5.5"/>',
    ok: '<path d="M5 12.5 10 17.5 19.5 7"/>',
    info: '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5"/><path d="M12 7.8v.2"/>',
  };

  const state = { data: null, resizeTimer: 0 };

  function stat(value, label, hint) {
    return `<li class="stat">
      <span class="stat__label">${label}</span>
      <span class="stat__value">${value}</span>
      <span class="stat__hint">${hint}</span>
    </li>`;
  }

  function movePill(change) {
    if (change === 0) return '<span class="delta">flat</span>';
    const down = change < 0;
    return `<span class="delta delta--${down ? "down" : "up"}">${
      down ? "▼" : "▲"
    } ${one(Math.abs(change))} pts</span>`;
  }

  function spark(trend, width) {
    const height = 56;
    const padX = 6;
    const padY = 8;
    const values = trend.map((point) => point.index);
    const last = trend.length - 1;
    const min = Math.min(0, ...values);
    const max = Math.max(0, ...values);
    const span = max - min || 1;
    const x = (index) => padX + (index * (width - padX * 2)) / Math.max(1, last);
    const y = (value) => padY + ((max - value) / span) * (height - padY * 2);
    const points = trend
      .map((point, index) => `${x(index).toFixed(1)},${y(point.index).toFixed(1)}`)
      .join(" ");
    const zero = y(0).toFixed(1);
    return `<svg class="comp-spark" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-label="Price index from ${signed(values[0])} to ${signed(values[last])} over ${trend.length} days">
      <path class="comp-spark__zero" d="M0 ${zero}H${width}"/>
      <polyline class="comp-spark__line" points="${points}"/>
      <circle class="comp-spark__dot" cx="${x(last).toFixed(1)}" cy="${y(values[last]).toFixed(1)}" r="2.4"/>
    </svg>`;
  }

  function renderStats() {
    const stats = state.data.stats;
    els.stats.innerHTML = [
      stat(String(stats.competitors), "Competitors", "watched daily"),
      stat(
        String(stats.below),
        stats.below === 1 ? "Undercut" : "Undercuts",
        "prices below yours"
      ),
      stat(
        `${one(stats.biggestGap)}%`,
        "Biggest gap",
        stats.biggestGapProduct ? shortName(stats.biggestGapProduct) : "no undercut today"
      ),
      stat(
        `${one(stats.widestSpread)}%`,
        "Market spread",
        stats.widestSpreadProduct || "—"
      ),
    ].join("");
  }

  function renderCards() {
    const data = state.data;
    const main = data.main.name;
    const count = data.stats.products;
    els.cards.innerHTML = data.competitors
      .map((row) => {
        const badge =
          row.name === main
            ? '<span class="badge badge--solid">Closest rival</span>'
            : row.below === 0
              ? '<span class="badge badge--muted">Above you</span>'
              : '<span class="badge badge--outline">Undercuts you</span>';
        return `<article class="card comp-card" aria-label="${esc(row.name)}">
          <div class="comp-card__head">
            <h2>${esc(row.name)}</h2>
            ${badge}
          </div>
          <p class="comp-card__index">
            <span class="comp-card__value">${signed(row.index)}</span>
            <span class="comp-card__vs">avg vs your prices</span>
          </p>
          <div class="comp-card__spark" data-spark="${esc(row.name)}"></div>
          <div class="comp-card__spark-meta" aria-hidden="true">
            <span>${shortDate(data.window.start)}</span>
            <span>${shortDate(data.window.end)} · ${data.window.days} days</span>
          </div>
          <dl class="comp-card__meta">
            <div class="comp-card__row"><dt>Undercuts you</dt><dd>${row.below} of ${count}</dd></div>
            <div class="comp-card__row"><dt>Cheapest on</dt><dd>${row.cheapest} of ${count}</dd></div>
            <div class="comp-card__row"><dt>14-day move</dt><dd>${movePill(row.change)}</dd></div>
          </dl>
        </article>`;
      })
      .join("");
    drawSparks();
  }

  function drawSparks() {
    if (!state.data) return;
    const byName = new Map(
      state.data.competitors.map((row) => [row.name, row])
    );
    els.cards.querySelectorAll("[data-spark]").forEach((slot) => {
      const row = byName.get(slot.dataset.spark);
      const width = Math.max(120, Math.round(slot.clientWidth));
      slot.innerHTML = row ? spark(row.trend, width) : "";
    });
  }

  function renderTable() {
    const data = state.data;
    els.gapsSub.textContent = `Prices in ${data.currency} — ▼ below, ▲ above, = equal`;
    els.gapHead.innerHTML = `<tr>
      <th scope="col">Product</th>
      <th scope="col" class="num">You</th>
      ${data.competitors
        .map((row) => `<th scope="col" class="num">${esc(row.name)}</th>`)
        .join("")}
      <th scope="col" class="num">Spread</th>
    </tr>`;
    els.gapBody.innerHTML = data.products
      .map((product) => {
        const cells = product.cells
          .map((cell) => {
            const gap =
              cell.percent < 0
                ? `<span class="gap-cell__gap gap--below">▼ ${one(Math.abs(cell.percent))}%</span>`
                : cell.percent > 0
                  ? `<span class="gap-cell__gap gap--above">▲ ${one(cell.percent)}%</span>`
                  : '<span class="gap-cell__gap gap--equal">=</span>';
            return `<td class="num gap-cell" title="${esc(cell.competitor)}: ${fmt(
              cell.price
            )} ${data.currency} vs your ${fmt(product.ourPrice)}">
              <span class="gap-cell__price">${fmt(cell.price)}</span>${gap}
            </td>`;
          })
          .join("");
        return `<tr>
          <th scope="row"><a class="product-link" href="/product?id=${esc(
            product.id
          )}&snapshot=${data.snapshotIndex}">${esc(product.name)}</a></th>
          <td class="num gap-table__you">${fmt(product.ourPrice)}</td>
          ${cells}
          <td class="num gap-table__spread" title="${esc(product.cheapest.competitor)} ${fmt(
            product.cheapest.price
          )} → ${esc(product.dearest.competitor)} ${fmt(product.dearest.price)}">${one(
            product.spread
          )}%</td>
        </tr>`;
      })
      .join("");
    updateHint();
  }

  function renderInsights() {
    els.insights.innerHTML = state.data.insights
      .map(
        (item) => `<li class="insight insight--${item.kind}">
          <svg class="insight__icon" viewBox="0 0 24 24" aria-hidden="true">${
            ICONS[item.kind] || ICONS.info
          }</svg>
          <span>${esc(item.text)}</span>
        </li>`
      )
      .join("");
  }

  function updateHint() {
    if (!els.tableWrap || !els.hint) return;
    els.hint.classList.toggle(
      "is-visible",
      els.tableWrap.scrollWidth > els.tableWrap.clientWidth + 1
    );
  }

  async function load() {
    try {
      const response = await fetch("/api/competitors", { cache: "no-store" });
      if (!response.ok) throw new Error("analysis unavailable");
      const data = await response.json();
      if (!data || !Array.isArray(data.competitors)) {
        throw new Error("analysis unavailable");
      }
      state.data = data;
      els.date.textContent = data.date;
      renderStats();
      renderCards();
      renderTable();
      renderInsights();
    } catch (error) {
      els.cards.innerHTML =
        '<p class="comp-error">The analysis needs the demo server. Start it and reload this page.</p>';
      els.gapHead.innerHTML = "";
      els.gapBody.innerHTML = "";
      els.insights.innerHTML = "";
    }
  }

  window.addEventListener("resize", () => {
    clearTimeout(state.resizeTimer);
    state.resizeTimer = setTimeout(() => {
      drawSparks();
      updateHint();
    }, 120);
  });

  load();
})();
