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
    timers: [],
  };

  const el = (selector) => document.querySelector(selector);
  const els = {
    date: el("#snapshot-date"),
    banner: el("#snapshot-banner"),
    bannerText: el("#banner-text"),
    bannerReset: el("#banner-reset"),
    stats: el("#stats"),
    alertPlate: el("#alert-plate"),
    watchBody: el("#watch-body"),
    watchMeta: el("#watch-meta"),
    moves: el("#moves"),
    movesMeta: el("#moves-meta"),
    alerts: el("#alerts"),
    alertsMeta: el("#alerts-meta"),
    collect: el("#collect-now"),
    collectLabel: el("#collect-label"),
    reset: el("#reset-demo"),
    overlay: el("#collect-overlay"),
    overlayTitle: el("#collect-title"),
    overlaySteps: el("#collect-steps"),
    overlayBar: el("#collect-bar"),
  };

  if (!els.watchBody) return;

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

  function stat(value, label, suffix = "") {
    return `<li><strong class="stats__num">${value}${suffix}</strong><span class="stats__label">${label}</span></li>`;
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
        const prices = demo.competitors.map((c) => snap.prices[product.id][c]);
        const low = Math.min(...prices);
        const high = Math.max(...prices);
        const productAlerts = alertsByProduct.get(product.id) || [];

        const cells = demo.competitors
          .map((competitor) => {
            const price = snap.prices[product.id][competitor];
            const prevPrice = prev ? prev.prices[product.id][competitor] : price;
            const diff = price - prevPrice;
            const changed = diff !== 0;
            const undercut = price < ours;
            const delta = changed
              ? ` <span class="delta delta--${diff < 0 ? "down" : "up"}">${
                  diff < 0 ? "▼" : "▲"
                } ${percent(prevPrice, price)}%</span>`
              : "";
            const title = `${competitor}: ${fmt(prevPrice)} → ${fmt(price)} ${demo.currency}`;
            return `<td class="num${changed ? " cell--moved" : ""}${
              undercut ? " cell--undercut" : ""
            }" title="${title}">${fmt(price)}${delta}</td>`;
          })
          .join("");

        const signal = productAlerts.length
          ? `<span class="signal">${productAlerts.length} below you</span>`
          : `<span class="signal signal--none">—</span>`;

        return `<tr id="product-${product.id}" class="watch-row${
          productAlerts.length ? " is-undercut" : ""
        }">
          <th scope="row"><span class="product-name">${product.name}</span></th>
          <td class="num num--ours">${fmt(ours)}</td>
          ${cells}
          <td class="num">${fmt(low)}–${fmt(high)}</td>
          <td class="signal-cell">${signal}</td>
        </tr>`;
      })
      .join("");
  }

  function renderAlertPlate(alerts) {
    if (!alerts.length) {
      els.alertPlate.hidden = true;
      return;
    }
    els.alertPlate.hidden = false;
    const top = alerts[0];
    const extra = alerts.length - 1;
    els.alertPlate.innerHTML = `
      <div class="alert-plate__main">
        <span class="stamp alert-plate__stamp">Alert</span>
        <p class="alert-plate__headline"><strong>${top.competitor}</strong> is <strong>${top.below}% below you</strong> on ${top.product.name}.</p>
        <p class="alert-plate__sub">${fmt(top.price)} ${demo.currency} against your ${fmt(top.ours)} ${demo.currency}.${
          extra ? ` Plus ${extra} more below you.` : " One to watch."
        }</p>
      </div>
      <button class="btn btn--paper" type="button" data-inspect="${top.product.id}">
        Inspect listing <span class="btn__arrow" aria-hidden="true">→</span>
      </button>`;
  }

  function renderMoves(moves) {
    els.moves.innerHTML = moves.length
      ? moves
          .map(
            (move) => `<li class="move">
              <span class="delta delta--${move.direction}">${
                move.direction === "down" ? "▼" : "▲"
              } ${move.percent}%</span>
              <span class="move__text"><strong>${move.competitor}</strong> · ${move.product.name}</span>
              <span class="move__prices">${fmt(move.from)} → ${fmt(move.to)}</span>
            </li>`
          )
          .join("")
      : `<li class="moves__empty">No price moves in this snapshot.</li>`;
  }

  function renderAlerts(alerts) {
    els.alerts.innerHTML = alerts.length
      ? alerts
          .map(
            (alert) => `<li class="alert-item">
              <span class="alert-item__badge">${alert.below}%</span>
              <span class="alert-item__text">
                <strong>${alert.competitor}</strong> undercuts you on ${alert.product.name}
                <span class="alert-item__math">${fmt(alert.price)} vs your ${fmt(alert.ours)} ${demo.currency}</span>
              </span>
            </li>`
          )
          .join("")
      : `<li class="alerts__empty">No competitor is below you. Good day.</li>`;
  }

  function render() {
    const snap = snapshot();
    const prev = previousSnapshot();
    const moves = computeMoves(snap, prev);
    const alerts = computeAlerts(snap);
    const latest = state.index >= demo.snapshots.length - 1;
    const pricesCount = demo.products.length * demo.competitors.length;

    els.date.textContent = snap.date;
    els.watchMeta.textContent = `${demo.products.length} products · ${demo.competitors.length} competitors`;
    els.movesMeta.textContent = prev ? `${snap.date} vs ${prev.date}` : snap.date;
    els.alertsMeta.textContent = `${alerts.length} ${alerts.length === 1 ? "alert" : "alerts"}`;

    els.stats.innerHTML = [
      stat(demo.products.length, "products"),
      stat(demo.competitors.length, "competitors"),
      stat(pricesCount, "prices watched"),
      stat(moves.length, moves.length === 1 ? "move" : "moves"),
      stat(alerts.length, alerts.length === 1 ? "alert" : "alerts"),
    ].join("");

    renderAlertPlate(alerts);
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
  }

  function inspect(productId) {
    const row = document.querySelector(`#product-${productId}`);
    if (!row) return;
    row.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "center" });
    row.classList.remove("is-flash");
    void row.offsetWidth;
    row.classList.add("is-flash");
    setTimeout(() => row.classList.remove("is-flash"), 1600);
  }

  function resetDemo() {
    state.timers.forEach(clearTimeout);
    state.timers = [];
    state.busy = false;
    state.index = INITIAL_SNAPSHOT;
    els.overlay.hidden = true;
    render();
  }

  function startCollection() {
    if (state.busy || state.index >= demo.snapshots.length - 1) return;

    state.busy = true;
    render();

    const steps = [...els.overlaySteps.querySelectorAll("li")];
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
        els.overlay.hidden = true;
        render();
        els.collect.focus();
      }, stepMs * (steps.length + 1))
    );
  }

  els.overlaySteps.innerHTML = demo.collection.pages
    .map((page) => `<li>${page}</li>`)
    .join("");

  els.collect.addEventListener("click", startCollection);
  els.reset.addEventListener("click", resetDemo);
  els.bannerReset.addEventListener("click", resetDemo);

  els.alertPlate.addEventListener("click", (event) => {
    const button = event.target.closest("[data-inspect]");
    if (button) inspect(button.dataset.inspect);
  });

  render();
})();
