/*
 * Alerts screen: rule switches with thresholds, the alerts they trigger on the
 * demo day and the plain-text daily digest.
 *
 * Everything is deterministic and computed in the browser from the fixtures in
 * demo-data.js. Delivery (email or chat) is intentionally not connected yet.
 */
(() => {
  "use strict";

  const demo = window.MARKETEYE_DEMO;
  if (!demo) return;

  const nf = new Intl.NumberFormat("en-US");
  const fmt = (value) => nf.format(value);
  const pct = (from, to) => ((to - from) / from) * 100;
  const pctLabel = (from, to) => {
    const raw = Math.abs(pct(from, to));
    const rounded = Math.round(raw);
    return String(rounded === 0 && raw > 0 ? Math.round(raw * 10) / 10 : rounded);
  };
  const many = (count, one, few) => `${count} ${count === 1 ? one : few}`;

  const TODAY_SNAPSHOT = 1;
  const today = demo.snapshots[TODAY_SNAPSHOT];
  const dayIndex = demo.history.findIndex((day) => day.date === today.date);
  const previous = dayIndex > 0 ? demo.history[dayIndex - 1] : null;

  const state = {
    rules: demo.alertRules.map((rule) => ({ ...rule })),
    copyTimer: 0,
  };

  const el = (selector) => document.querySelector(selector);
  const els = {
    date: el("#snapshot-date"),
    stats: el("#stats"),
    rulesList: el("#rules-list"),
    rulesCount: el("#rules-count"),
    alertsList: el("#alerts-list"),
    alertsCount: el("#alerts-count"),
    triggeredSub: el("#triggered-sub"),
    digestText: el("#digest-text"),
    copyDigest: el("#copy-digest"),
    downloadDigest: el("#download-digest"),
    recentList: el("#recent-list"),
  };

  if (!els.rulesList || !els.alertsList || !els.digestText) return;

  const ICONS = {
    below:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 9a6 6 0 1 0-12 0c0 6-2.5 6-2.5 8h17c0-2-2.5-2-2.5-8"/><path d="M10.5 21a2 2 0 0 0 3 0"/></svg>',
    drop: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v13"/><path d="M6.5 11.5 12 17l5.5-5.5"/></svg>',
    rise: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20V7"/><path d="M6.5 12.5 12 7l5.5 5.5"/></svg>',
  };

  const ruleLabel = (rule) => {
    if (rule.kind === "below") return "below my price";
    const name = rule.kind === "drop" ? "price drop" : "price rise";
    return `${name} ≥ ${rule.threshold}%`;
  };

  const ruleById = (id) => state.rules.find((rule) => rule.id === id);

  function alertsFor(index) {
    const day = demo.history[index];
    const earlier = index > 0 ? demo.history[index - 1] : null;
    const found = [];

    for (const product of demo.products) {
      const ours = demo.ourPrices[product.id];
      for (const competitor of demo.competitors) {
        const price = day.prices[product.id][competitor];
        const before = earlier ? earlier.prices[product.id][competitor] : price;

        const below = ruleById("below");
        if (below && below.enabled && price < ours) {
          found.push({
            kind: "below",
            product,
            competitor,
            price,
            ours,
            percent: Math.round(((ours - price) / ours) * 100),
          });
        }

        const drop = ruleById("drop");
        if (drop && drop.enabled && earlier && price < before) {
          const move = Math.abs(pct(before, price));
          if (move >= drop.threshold) {
            found.push({
              kind: "drop",
              product,
              competitor,
              price,
              from: before,
              percent: Math.round(move),
            });
          }
        }

        const rise = ruleById("rise");
        if (rise && rise.enabled && earlier && price > before) {
          const move = Math.abs(pct(before, price));
          if (move >= rise.threshold) {
            found.push({
              kind: "rise",
              product,
              competitor,
              price,
              from: before,
              percent: Math.round(move),
            });
          }
        }
      }
    }

    const order = { below: 0, drop: 1, rise: 2 };
    return found.sort(
      (a, b) => order[a.kind] - order[b.kind] || (b.percent || 0) - (a.percent || 0)
    );
  }

  function stat(value, label, hint) {
    return `<li class="stat">
      <span class="stat__label">${label}</span>
      <span class="stat__value">${value}</span>
      <span class="stat__hint">${hint}</span>
    </li>`;
  }

  function renderRules() {
    els.rulesList.innerHTML = state.rules
      .map((rule) => {
        const threshold =
          rule.kind === "below"
            ? ""
            : `<label class="rule__threshold">Every
                <input type="number" min="1" max="50" step="1" value="${rule.threshold}"
                  data-threshold="${rule.id}" aria-label="Threshold for ${rule.title}, percent">
                %</label>`;
        return `<li class="rule${rule.enabled ? "" : " is-off"}">
          <label class="switch">
            <input type="checkbox" data-toggle="${rule.id}"${
              rule.enabled ? " checked" : ""
            } aria-label="${rule.title}">
            <span class="switch__track"></span>
          </label>
          <div class="rule__body">
            <p class="rule__title">${rule.title}</p>
            <p class="rule__desc">${rule.description}</p>
          </div>
          ${threshold}
        </li>`;
      })
      .join("");

    const on = state.rules.filter((rule) => rule.enabled).length;
    els.rulesCount.textContent = `${on} on`;
  }

  function renderStats(alerts) {
    const products = new Set(alerts.map((alert) => alert.product.id)).size;
    const on = state.rules.filter((rule) => rule.enabled).length;
    const digestLines = els.digestText.textContent.trim().split("\n").length;
    els.stats.innerHTML = [
      stat(`${on}/${state.rules.length}`, "Rules", "switched on"),
      stat(alerts.length, "Alerts", "matched today"),
      stat(products, products === 1 ? "Product" : "Products", "with an alert"),
      stat(digestLines, "Digest", "lines of plain text"),
    ].join("");
  }

  function renderAlerts(alerts) {
    els.alertsCount.textContent = String(alerts.length);

    if (!alerts.length) {
      els.alertsList.innerHTML =
        '<li class="alert-empty">No rule matched today. Loosen a threshold or switch a rule on.</li>';
      return;
    }

    els.alertsList.innerHTML = alerts
      .map((alert) => {
        const meta =
          alert.kind === "below"
            ? `${alert.percent}% below your ${fmt(alert.ours)} ${demo.currency}`
            : `${fmt(alert.from)} → ${fmt(alert.price)} ${demo.currency} · ${pctLabel(
                alert.from,
                alert.price
              )}% ${alert.kind === "drop" ? "lower" : "higher"} than yesterday`;
        return `<li class="alert-row">
          <span class="alert-row__icon" aria-hidden="true">${ICONS[alert.kind]}</span>
          <div class="alert-row__body">
            <p class="alert-row__text"><b>${alert.competitor}</b> · ${alert.product.name} — <b>${fmt(alert.price)} ${demo.currency}</b></p>
            <p class="alert-row__meta">${meta}</p>
            <div class="alert-row__foot">
              <span class="badge badge--soft">${ruleById(alert.kind).title}</span>
              <a class="alert-row__link" href="/product?id=${alert.product.id}&snapshot=${TODAY_SNAPSHOT}">Open product →</a>
            </div>
          </div>
        </li>`;
      })
      .join("");
  }

  function buildDigest(alerts) {
    const on = state.rules.filter((rule) => rule.enabled);
    const lines = ["MarketEye · daily digest", `${today.date} · demo data (saved pages)`, ""];

    if (!alerts.length) {
      lines.push("No alerts today. Nothing to report.", "");
    } else {
      const products = new Set(alerts.map((alert) => alert.product.id)).size;
      lines.push(
        `${many(alerts.length, "alert", "alerts")} across ${many(products, "product", "products")}.`,
        ""
      );
      for (const kind of ["below", "drop", "rise"]) {
        const group = alerts.filter((alert) => alert.kind === kind);
        if (!group.length) continue;
        lines.push(ruleById(kind).title);
        for (const alert of group) {
          if (kind === "below") {
            lines.push(
              `- ${alert.competitor} · ${alert.product.name} — ${fmt(alert.price)} ${demo.currency}, ${alert.percent}% below our ${fmt(alert.ours)} ${demo.currency}`
            );
          } else {
            lines.push(
              `- ${alert.competitor} · ${alert.product.name} — ${fmt(alert.from)} → ${fmt(alert.price)} ${demo.currency}, ${pctLabel(alert.from, alert.price)}% ${kind === "drop" ? "lower" : "higher"}`
            );
          }
        }
        lines.push("");
      }
    }

    lines.push(
      `Rules: ${on.length ? on.map(ruleLabel).join(" · ") : "none switched on"}`,
      `Snapshot: ${today.date}${previous ? ` vs ${previous.date}` : ""}`,
      "Demo mode: saved pages, no live scraping. Delivery is not connected.",
      ""
    );
    return lines.join("\n");
  }

  function renderDigest(alerts) {
    els.digestText.textContent = buildDigest(alerts);
  }

  function renderRecent() {
    const rows = [];
    for (let offset = 0; offset < 3; offset += 1) {
      const index = dayIndex - offset;
      if (index < 1) break;
      const day = demo.history[index];
      const count = alertsFor(index).length;
      rows.push(
        `<li class="recent-item">
          <span class="recent-item__date">${day.date}</span>
          <span class="recent-item__count">${count} ${count === 1 ? "alert" : "alerts"}</span>
        </li>`
      );
    }
    els.recentList.innerHTML = rows.join("") || '<li class="alert-empty">No earlier snapshots.</li>';
  }

  function renderAll() {
    const alerts = alertsFor(dayIndex);
    els.date.textContent = today.date;
    els.triggeredSub.textContent = `${today.date} vs ${previous ? previous.date : "no earlier snapshot"}`;
    renderRules();
    renderDigest(alerts);
    renderAlerts(alerts);
    renderStats(alerts);
    renderRecent();
  }

  /* --- actions ---------------------------------------------------------- */

  function legacyCopy(text) {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.top = "-999px";
    document.body.appendChild(area);
    area.select();
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch {
      ok = false;
    }
    area.remove();
    return ok;
  }

  function selectDigestText() {
    const range = document.createRange();
    range.selectNodeContents(els.digestText);
    const selection = window.getSelection();
    if (!selection) return;
    selection.removeAllRanges();
    selection.addRange(range);
  }

  async function copyDigest() {
    const text = els.digestText.textContent;
    let ok = false;
    try {
      await navigator.clipboard.writeText(text);
      ok = true;
    } catch {
      ok = legacyCopy(text);
    }
    if (!ok) selectDigestText();
    els.copyDigest.textContent = ok ? "Copied" : "Selected · Ctrl+C";
    window.clearTimeout(state.copyTimer);
    state.copyTimer = window.setTimeout(() => {
      els.copyDigest.textContent = "Copy";
    }, 1800);
  }

  function digestFileName() {
    const months = [
      "January", "February", "March", "April", "May", "June",
      "July", "August", "September", "October", "November", "December",
    ];
    const [dayNumber, monthName, year] = today.date.split(" ");
    const month = String(months.indexOf(monthName) + 1).padStart(2, "0");
    return `marketeye-digest-${year}-${month}-${dayNumber.padStart(2, "0")}.txt`;
  }

  function downloadDigest() {
    const blob = new Blob([els.digestText.textContent], {
      type: "text/plain;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = digestFileName();
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  els.rulesList.addEventListener("change", (event) => {
    const toggle = event.target.closest("[data-toggle]");
    if (toggle) {
      const rule = ruleById(toggle.dataset.toggle);
      rule.enabled = toggle.checked;
      renderAll();
      return;
    }
    const input = event.target.closest("[data-threshold]");
    if (input) {
      const rule = ruleById(input.dataset.threshold);
      const value = Number.parseInt(input.value, 10);
      rule.threshold = Math.min(Math.max(Number.isFinite(value) ? value : 5, 1), 50);
      renderAll();
    }
  });

  els.copyDigest.addEventListener("click", copyDigest);
  els.downloadDigest.addEventListener("click", downloadDigest);

  renderAll();
})();
