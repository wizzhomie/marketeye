/*
 * Overview panel behaviour.
 *
 * Everything is rendered from the frozen fixtures in demo-data.js, so the
 * backend can later replace the data source without touching the markup.
 */
(() => {
  "use strict";

  const demo = window.MARKETEYE_DEMO;
  if (!demo) return;

  const INITIAL_SNAPSHOT = 1;
  const nf = new Intl.NumberFormat("en-US");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const state = {
    index: INITIAL_SNAPSHOT,
    busy: false,
    aiBusy: false,
    timers: [],
    hintFrame: 0,
  };

  const el = (selector) => document.querySelector(selector);
  const els = {
    date: el("#snapshot-date"),
    banner: el("#snapshot-banner"),
    bannerText: el("#banner-text"),
    bannerReset: el("#banner-reset"),
    stats: el("#stats"),
    watchBody: el("#watch-body"),
    watchMeta: el("#watch-meta"),
    watchDate: el("#watch-date"),
    moves: el("#moves-list"),
    movesMeta: el("#moves-meta"),
    alerts: el("#alerts-list"),
    alertsMeta: el("#alerts-meta"),
    alertsCount: el("#alerts-count"),
    collect: el("#collect-now"),
    collectLabel: el("#collect-label"),
    reset: el("#reset-demo"),
    overlay: el("#collect-overlay"),
    overlayTitle: el("#collect-title"),
    overlaySteps: el("#collect-steps"),
    overlayBar: el("#collect-bar"),
    tableWrap: el(".table-wrap"),
    tableHint: el("#table-hint"),
    aiNoteButton: el("#ai-note-button"),
    aiNoteText: el("#ai-note-text"),
    aiNoteMeta: el("#ai-note-meta"),
  };

  if (!els.watchBody) return;

  const AI_PLACEHOLDER =
    "A short, plain-language note on today's moves — written only from the verified snapshot.";

  const BELL_ICON =
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 9a6 6 0 1 0-12 0c0 6-2.5 6-2.5 8h17c0-2-2.5-2-2.5-8"/><path d="M10.5 21a2 2 0 0 0 3 0"/></svg>';

  const fmt = (value) => nf.format(value);
  const percent = (from, to) => Math.round((Math.abs(to - from) / from) * 100);
  const snapshot = () => demo.snapshots[state.index];
  const previousSnapshot = () => demo.snapshots[state.index - 1] || null;

  function computeMoves(snap, prev) {
    if (!prev) return [];
    const moves = [];
    for (const product of demo.products) {
      for (const competitor of demo.competitors) {
        const from = prev.prices[product.id][competitor];
        const to = snap.prices[product.id][competitor];
        if (from === to) continue;
        moves.push({
          product,
          competitor,
          from,
          to,
          percent: percent(from, to),
          direction: to > from ? "up" : "down",
        });
      }
    }
    return moves;
  }

  function computeAlerts(snap) {
    const alerts = [];
    for (const product of demo.products) {
      const ours = demo.ourPrices[product.id];
      for (const competitor of demo.competitors) {
        const price = snap.prices[product.id][competitor];
        if (price >= ours) continue;
        alerts.push({
          product,
          competitor,
          price,
          ours,
          below: Math.round(((ours - price) / ours) * 100),
        });
      }
    }
    return alerts.sort((a, b) => b.below - a.below);
  }

  function stat(value, label, hint) {
    return `<li class="stat">
      <span class="stat__label">${label}</span>
      <span class="stat__value">${value}</span>
      <span class="stat__hint">${hint}</span>
    </li>`;
  }

  function renderTable(snap, prev, alerts) {
    const alertsByProduct = new Map();
    for (const alert of alerts) {
      const list = alertsByProduct.get(alert.product.id) || [];
      list.push(alert);
      alertsByProduct.set(alert.product.id, list);
    }

    els.watchBody.innerHTML = demo.products
      .map((product) => {
        const ours = demo.ourPrices[product.id];
        const productAlerts = alertsByProduct.get(product.id) || [];

        const cells = demo.competitors
          .map((competitor) => {
            const price = snap.prices[product.id][competitor];
            const prevPrice = prev ? prev.prices[product.id][competitor] : price;
            const diff = price - prevPrice;
            const changed = diff !== 0;
            const below = price < ours;
            const delta = changed
              ? ` <span class="delta delta--${diff < 0 ? "down" : "up"}">${
                  diff < 0 ? "▼" : "▲"
                } ${percent(prevPrice, price)}%</span>`
              : "";
            const title = `${competitor}: ${fmt(prevPrice)} → ${fmt(price)} ${demo.currency}`;
            return `<td class="num${changed ? " cell--moved" : ""}${
              below ? " cell--below" : ""
            }" title="${title}">${fmt(price)}${delta}</td>`;
          })
          .join("");

        const signal = productAlerts.length
          ? '<span class="badge badge--solid">Below you</span>'
          : '<span class="badge badge--muted">—</span>';

        return `<tr id="product-${product.id}" class="watch-row${
          productAlerts.length ? " watch-row--alert" : ""
        }">
          <th scope="row"><a class="product-link" href="/product?id=${product.id}&snapshot=${state.index}">${product.name}</a></th>
          <td class="num">${fmt(ours)}</td>
          ${cells}
          <td class="signal-cell">${signal}</td>
        </tr>`;
      })
      .join("");
  }

  function renderMoves(moves) {
    els.moves.innerHTML = moves.length
      ? moves
          .map(
            (move) => `<li class="move">
              <span class="move__text"><b>${move.competitor}</b> · ${move.product.name}</span>
              <span class="move__delta">
                <span class="delta delta--${move.direction}">${
                  move.direction === "down" ? "▼" : "▲"
                } ${move.percent}%</span>
              </span>
            </li>`
          )
          .join("")
      : '<li class="move"><span class="move__text">No price moves in this snapshot.</span></li>';
  }

  function renderAlerts(alerts) {
    els.alerts.innerHTML = alerts.length
      ? alerts
          .map(
            (alert) => `<li class="alert-item">
              <span class="alert-item__icon" aria-hidden="true">${BELL_ICON}</span>
              <div class="alert-item__body">
                <p class="alert-item__text"><b>${alert.competitor}</b> is <b>${alert.below}% below you</b> on ${alert.product.name}.</p>
                <p class="alert-item__meta">${fmt(alert.price)} ${demo.currency} vs your ${fmt(alert.ours)} ${demo.currency}</p>
                <div class="alert-item__action">
                  <a class="btn btn--outline btn--sm" href="/product?id=${alert.product.id}&snapshot=${state.index}">Inspect listing</a>
                </div>
              </div>
            </li>`
          )
          .join("")
      : '<li class="alert-empty">No competitor is below you. Good day.</li>';
  }

  function updateTableHint() {
    state.hintFrame = 0;
    if (!els.tableWrap || !els.tableHint) return;
    els.tableHint.classList.toggle(
      "is-visible",
      els.tableWrap.scrollWidth > els.tableWrap.clientWidth + 1
    );
  }

  function scheduleTableHint() {
    if (!state.hintFrame) {
      state.hintFrame = requestAnimationFrame(updateTableHint);
    }
  }

  function buildAiPayload() {
    const snap = snapshot();
    const prev = previousSnapshot();
    const moves = computeMoves(snap, prev);
    const alerts = computeAlerts(snap);
    return {
      date: snap.date,
      currency: demo.currency,
      ourPrices: demo.products.map((product) => ({
        product: product.name,
        price: demo.ourPrices[product.id],
      })),
      competitorPrices: demo.products.map((product) => ({
        product: product.name,
        prices: snap.prices[product.id],
      })),
      moves: moves.map((move) => ({
        competitor: move.competitor,
        product: move.product.name,
        from: move.from,
        to: move.to,
        percent: move.percent,
        direction: move.direction,
      })),
      alerts: alerts.map((alert) => ({
        competitor: alert.competitor,
        product: alert.product.name,
        price: alert.price,
        ourPrice: alert.ours,
        percentBelow: alert.below,
      })),
    };
  }

  function clearAiNote() {
    if (!els.aiNoteText) return;
    els.aiNoteText.textContent = AI_PLACEHOLDER;
    els.aiNoteText.classList.add("is-placeholder");
    els.aiNoteMeta.hidden = true;
    els.aiNoteMeta.textContent = "";
    els.aiNoteButton.disabled = state.aiBusy;
    els.aiNoteButton.textContent = "Draft with AI";
  }

  async function requestAiNote() {
    if (state.aiBusy || !els.aiNoteButton) return;
    state.aiBusy = true;
    els.aiNoteButton.disabled = true;
    els.aiNoteButton.textContent = "Writing…";
    els.aiNoteText.classList.remove("is-placeholder");
    els.aiNoteText.textContent = "Reading today's snapshot…";
    els.aiNoteMeta.hidden = true;

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30000);
    try {
      const response = await fetch("/api/ai/note", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildAiPayload()),
        signal: controller.signal,
      });
      const data = await response.json().catch(() => null);
      if (!response.ok || !data || typeof data.note !== "string") {
        throw new Error((data && data.message) || "AI note is unavailable in this demo.");
      }
      els.aiNoteText.textContent = data.note;
      els.aiNoteMeta.textContent = `AI-generated from verified data · ${snapshot().date}`;
      els.aiNoteMeta.hidden = false;
    } catch (error) {
      els.aiNoteText.classList.add("is-placeholder");
      els.aiNoteText.textContent = "AI note is unavailable in this demo.";
      els.aiNoteMeta.textContent =
        error && error.name === "AbortError"
          ? "The request took too long."
          : (error && error.message) || "Try again in a moment.";
      els.aiNoteMeta.hidden = false;
    } finally {
      clearTimeout(timeout);
      state.aiBusy = false;
      els.aiNoteButton.disabled = false;
      els.aiNoteButton.textContent = "Draft with AI";
    }
  }

  function render() {
    const snap = snapshot();
    const prev = previousSnapshot();
    const moves = computeMoves(snap, prev);
    const alerts = computeAlerts(snap);
    const latest = state.index >= demo.snapshots.length - 1;

    els.date.textContent = snap.date;
    els.watchDate.textContent = snap.date;
    els.watchMeta.textContent = `${demo.products.length} products · ${demo.competitors.length} competitors`;
    els.movesMeta.textContent = prev ? `${snap.date} vs ${prev.date}` : snap.date;
    els.alertsMeta.textContent = `${alerts.length} ${alerts.length === 1 ? "alert" : "alerts"}`;
    els.alertsCount.textContent = String(alerts.length);

    els.stats.innerHTML = [
      stat(demo.products.length, "Products", "watched daily"),
      stat(demo.competitors.length, "Competitors", "tracked"),
      stat(moves.length, moves.length === 1 ? "Move" : "Moves", "vs. previous snapshot"),
      stat(alerts.length, alerts.length === 1 ? "Alert" : "Alerts", "below your price"),
    ].join("");

    renderTable(snap, prev, alerts);
    renderMoves(moves);
    renderAlerts(alerts);

    els.banner.hidden = state.index === INITIAL_SNAPSHOT;
    if (!els.banner.hidden) {
      els.bannerText.textContent = `${snap.date} · ${moves.length} change${
        moves.length === 1 ? "" : "s"
      } found`;
    }

    els.collect.disabled = state.busy || latest;
    els.collectLabel.textContent = latest ? "Snapshot collected" : "Collect now";
    els.reset.disabled = state.index === INITIAL_SNAPSHOT;

    scheduleTableHint();
  }

  function closeOverlay() {
    els.overlay.hidden = true;
  }

  function resetDemo() {
    state.timers.forEach(clearTimeout);
    state.timers = [];
    state.busy = false;
    state.index = INITIAL_SNAPSHOT;
    closeOverlay();
    clearAiNote();
    render();
  }

  function startCollection() {
    if (state.busy || state.index >= demo.snapshots.length - 1) return;

    state.busy = true;
    clearAiNote();
    render();

    const steps = [...els.overlaySteps.querySelectorAll(".collect-step")];
    steps.forEach((step) => step.classList.remove("is-done"));
    els.overlayBar.style.width = "0%";
    els.overlayTitle.textContent = "Reading the saved pages…";
    els.overlay.hidden = false;

    const stepMs = reduceMotion ? 140 : 500;
    steps.forEach((step, index) => {
      state.timers.push(
        setTimeout(() => {
          step.classList.add("is-done");
          els.overlayBar.style.width = `${Math.round(((index + 1) / steps.length) * 100)}%`;
        }, stepMs * (index + 1))
      );
    });

    state.timers.push(
      setTimeout(() => {
        state.timers = [];
        state.index += 1;
        state.busy = false;
        closeOverlay();
        render();
        els.collect.focus();
      }, stepMs * (steps.length + 1))
    );
  }

  els.overlaySteps.innerHTML = demo.collection.pages
    .map(
      (page) =>
        `<li class="collect-step"><span class="collect-step__dot" aria-hidden="true"></span><span>${page}</span></li>`
    )
    .join("");

  els.collect.addEventListener("click", startCollection);
  els.reset.addEventListener("click", resetDemo);
  els.bannerReset.addEventListener("click", resetDemo);
  els.aiNoteButton.addEventListener("click", requestAiNote);
  window.addEventListener("resize", scheduleTableHint);

  clearAiNote();
  render();
})();
