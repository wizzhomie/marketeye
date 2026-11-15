/*
 * Alerts screen: rule switches with thresholds, the alerts they trigger on the
 * demo day and the plain-text daily digest.
 *
 * The browser no longer decides anything: rules are saved through
 * PUT /api/alerts/rules and the matches, stats and digest come from
 * POST /api/alerts/evaluate. Only the rendering lives here.
 */
(async () => {
  "use strict";

  const demo = await window.MARKETEYE_READY;
  if (!demo) return;

  const nf = new Intl.NumberFormat("en-US");
  const fmt = (value) => nf.format(value);
  const TODAY_SNAPSHOT = 1;

  const state = {
    rules: demo.alertRules.map((rule) => ({ ...rule })),
    copyTimer: 0,
    requestSeq: 0,
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

  const ruleById = (id) => state.rules.find((rule) => rule.id === id);

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

  function renderStats(stats) {
    els.stats.innerHTML = [
      stat(`${stats.rulesOn}/${stats.rulesTotal}`, "Rules", "switched on"),
      stat(stats.alerts, "Alerts", "matched today"),
      stat(stats.products, stats.products === 1 ? "Product" : "Products", "with an alert"),
      stat(stats.digestLines, "Digest", "lines of plain text"),
    ].join("");
  }

  function renderAlerts(data) {
    els.alertsCount.textContent = String(data.alerts.length);

    if (!data.alerts.length) {
      els.alertsList.innerHTML =
        '<li class="alert-empty">No rule matched today. Loosen a threshold or switch a rule on.</li>';
      return;
    }

    els.alertsList.innerHTML = data.alerts
      .map((alert) => {
        const meta =
          alert.kind === "below"
            ? `${alert.percent}% below your ${fmt(alert.ourPrice)} ${demo.currency}`
            : `${fmt(alert.from)} → ${fmt(alert.price)} ${demo.currency} · ${
                alert.percentText
              }% ${alert.kind === "drop" ? "lower" : "higher"} than yesterday`;
        return `<li class="alert-row">
          <span class="alert-row__icon" aria-hidden="true">${ICONS[alert.kind]}</span>
          <div class="alert-row__body">
            <p class="alert-row__text"><b>${alert.competitor}</b> · ${alert.product.name} — <b>${fmt(alert.price)} ${demo.currency}</b></p>
            <p class="alert-row__meta">${meta}</p>
            <div class="alert-row__foot">
              <span class="badge badge--soft">${alert.ruleTitle}</span>
              <a class="alert-row__link" href="/product?id=${alert.product.id}&snapshot=${data.snapshotIndex}">Open product →</a>
            </div>
          </div>
        </li>`;
      })
      .join("");
  }

  function renderRecent(data) {
    els.recentList.innerHTML =
      data.recent
        .map(
          (row) => `<li class="recent-item">
            <span class="recent-item__date">${row.date}</span>
            <span class="recent-item__count">${row.alerts} ${
              row.alerts === 1 ? "alert" : "alerts"
            }</span>
          </li>`
        )
        .join("") || '<li class="alert-empty">No earlier snapshots.</li>';
  }

  function renderData(data) {
    els.date.textContent = data.date;
    els.triggeredSub.textContent = `${data.date} vs ${
      data.previousDate || "no earlier snapshot"
    }`;
    els.digestText.textContent = data.digest;
    renderAlerts(data);
    renderStats(data.stats);
    renderRecent(data);
  }

  function renderError(message) {
    els.alertsList.innerHTML = `<li class="alert-empty">${message}</li>`;
    els.digestText.textContent = "The digest could not be loaded from the server.";
  }

  async function evaluate() {
    const sequence = ++state.requestSeq;
    try {
      const response = await fetch("/api/alerts/evaluate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rules: state.rules, snapshot: TODAY_SNAPSHOT }),
      });
      const data = await response.json().catch(() => null);
      if (!response.ok || !data) {
        throw new Error(
          (data && data.detail) || "The server could not evaluate the rules."
        );
      }
      if (sequence !== state.requestSeq) return;
      renderData(data);
    } catch (error) {
      if (sequence !== state.requestSeq) return;
      renderError(error && error.message ? error.message : "Could not reach the server.");
    }
  }

  async function saveRules() {
    const response = await fetch("/api/alerts/rules", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rules: state.rules }),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error((data && data.detail) || "The server rejected the rules.");
    }
    if (data && Array.isArray(data.rules)) {
      state.rules = data.rules.map((rule) => ({ ...rule }));
      renderRules();
    }
  }

  async function persistAndEvaluate() {
    try {
      await saveRules();
      await evaluate();
    } catch (error) {
      renderError(error && error.message ? error.message : "Could not reach the server.");
    }
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
    const [dayNumber, monthName, year] = els.date.textContent.split(" ");
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
      if (!rule) return;
      rule.enabled = toggle.checked;
      renderRules();
      persistAndEvaluate();
      return;
    }
    const input = event.target.closest("[data-threshold]");
    if (input) {
      const rule = ruleById(input.dataset.threshold);
      if (!rule) return;
      const value = Number.parseInt(input.value, 10);
      rule.threshold = Math.min(Math.max(Number.isFinite(value) ? value : 5, 1), 50);
      renderRules();
      persistAndEvaluate();
    }
  });

  els.copyDigest.addEventListener("click", copyDigest);
  els.downloadDigest.addEventListener("click", downloadDigest);

  renderRules();
  evaluate();
})();
