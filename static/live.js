/*
 * Live check: fetch two real pages over HTTP, show what the server stored.
 *
 * The browser does not fetch the competitor pages itself: it asks
 * POST /api/live/collect, and the server reads the pages, parses them with the
 * parser profile and stores one reading per source. The browser only renders.
 */
(() => {
  "use strict";

  const state = { busy: false, data: null };

  const el = (selector) => document.querySelector(selector);
  const els = {
    stats: el("#stats"),
    sources: el("#live-sources"),
    collect: el("#collect-live"),
    collectLabel: el("#collect-live-label"),
    reset: el("#reset-live"),
    lastCheck: el("#last-check"),
    banner: el("#live-banner"),
    bannerText: el("#live-banner-text"),
  };

  if (!els.sources || !els.stats) return;

  const priceFmt = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 2 });
  const fmt = (value) => priceFmt.format(value);
  const timeFmt = new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  const clockFmt = new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  const dateFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" });
  const when = (iso) => {
    if (!iso) return "—";
    const date = new Date(iso);
    return Number.isNaN(date.getTime()) ? iso : timeFmt.format(date);
  };

  function stat(value, label, hint) {
    return `<li class="stat">
      <span class="stat__label">${label}</span>
      <span class="stat__value">${value}</span>
      <span class="stat__hint">${hint}</span>
    </li>`;
  }

  function showBanner(message) {
    if (!els.banner) return;
    els.bannerText.textContent = message;
    els.banner.hidden = false;
  }

  function hideBanner() {
    if (els.banner) els.banner.hidden = true;
  }

  function renderStats(data) {
    const readings = data.sources.reduce((total, source) => total + source.readings.length, 0);
    const moves = data.sources.filter(
      (source) => source.change && source.change.direction !== "flat"
    ).length;
    const last = data.collectedAt ? new Date(data.collectedAt) : null;
    const validLast = last && !Number.isNaN(last.getTime());
    els.stats.innerHTML = [
      stat(data.sources.length, "Sources", "fetched over HTTP"),
      stat(readings, "Readings", "stored in SQLite"),
      stat(moves, moves === 1 ? "Move" : "Moves", "since previous check"),
      stat(
        validLast ? clockFmt.format(last) : "—",
        "Last check",
        validLast ? dateFmt.format(last) : "not collected yet"
      ),
    ].join("");
  }

  function renderReadings(source) {
    if (!source.readings.length) {
      return '<p class="readings__empty">Not checked yet. Run Collect now.</p>';
    }
    const rows = source.readings
      .slice(0, 4)
      .map(
        (reading) => `<li class="reading${reading.status === "error" ? " reading--error" : ""}">
          <span class="reading__time">${when(reading.fetchedAt)} · ${
            reading.status === "error" ? "error" : "read"
          }</span>
          <span class="reading__price">${
            reading.status === "error" ? "—" : `${fmt(reading.price)} ${reading.currency}`
          }</span>
        </li>`
      )
      .join("");
    return `<p class="readings__title">Recent readings</p><ul class="readings">${rows}</ul>`;
  }

  function renderSource(source) {
    const latest = source.latest;
    const lastOk = source.lastOk;
    const change = source.change;
    const failed = latest && latest.status === "error";

    let statusBadge = '<span class="badge badge--muted">Not checked</span>';
    if (latest) {
      statusBadge = failed
        ? '<span class="badge badge--outline">Error</span>'
        : '<span class="badge badge--solid">Live</span>';
    }

    let price = '<p class="source__price source__price--none">—</p>';
    if (lastOk) {
      price = `<p class="source__price">${fmt(lastOk.price)} <span>${lastOk.currency}</span></p>`;
    }

    let changePill = "";
    if (change && lastOk) {
      if (change.direction === "flat") {
        changePill = '<span class="badge badge--outline">No change</span>';
      } else {
        const down = change.direction === "down";
        changePill = `<span class="delta delta--${down ? "down" : "up"}">${
          down ? "▼" : "▲"
        } ${change.percent}%</span>`;
      }
    }

    const meta = latest
      ? `Parser profile <code>${source.profile}</code> · ${
          failed ? "last attempt" : "checked"
        } ${when(latest.fetchedAt)}`
      : `Parser profile <code>${source.profile}</code> · not collected yet`;

    const note = latest && latest.status === "error" ? `<p class="source__note">${latest.note}</p>` : "";

    return `<article class="card source${failed ? " source--error" : ""}">
      <div class="source__head">
        <div>
          <p class="source__competitor">${source.competitor}</p>
          <p class="source__product">${source.product}</p>
        </div>
        ${statusBadge}
      </div>
      <p class="source__url"><a href="${source.previewUrl || source.url}" target="_blank" rel="noopener">${source.url}</a></p>
      <div class="source__price-row">
        ${price}
        ${changePill}
      </div>
      <p class="source__meta">${meta}</p>
      ${note}
      ${renderReadings(source)}
    </article>`;
  }

  function render(data) {
    state.data = data;
    els.lastCheck.textContent = data.collectedAt
      ? `Last check ${when(data.collectedAt)}`
      : "Never collected";
    renderStats(data);
    els.sources.innerHTML = data.sources.map(renderSource).join("");
  }

  async function collect() {
    if (state.busy) return;
    state.busy = true;
    els.collect.disabled = true;
    els.collectLabel.textContent = "Collecting…";
    hideBanner();
    try {
      const response = await fetch("/api/live/collect", { method: "POST" });
      const data = await response.json().catch(() => null);
      if (!response.ok || !data) {
        throw new Error((data && data.detail) || "The server could not collect the pages.");
      }
      render(data);
      const failures = data.sources.filter(
        (source) => source.latest && source.latest.status === "error"
      );
      if (failures.length) {
        showBanner(
          `${failures.length} source${failures.length === 1 ? "" : "s"} could not be read: ` +
            failures.map((source) => `${source.competitor} — ${source.latest.note}`).join("; ")
        );
      }
    } catch (error) {
      showBanner(error && error.message ? error.message : "Could not collect the pages.");
    } finally {
      state.busy = false;
      els.collect.disabled = false;
      els.collectLabel.textContent = "Collect now";
    }
  }

  async function reset() {
    if (state.busy) return;
    state.busy = true;
    els.collect.disabled = true;
    els.reset.disabled = true;
    hideBanner();
    try {
      const response = await fetch("/api/live/reset", { method: "POST" });
      const data = await response.json().catch(() => null);
      if (!response.ok || !data) {
        throw new Error((data && data.detail) || "The server could not reset the demo.");
      }
      render(data);
    } catch (error) {
      showBanner(error && error.message ? error.message : "Could not reset the demo.");
    } finally {
      state.busy = false;
      els.collect.disabled = false;
      els.reset.disabled = false;
    }
  }

  els.collect.addEventListener("click", collect);
  els.reset.addEventListener("click", reset);

  fetch("/api/live")
    .then((response) => {
      if (!response.ok) throw new Error("The server did not answer.");
      return response.json();
    })
    .then((data) => {
      render(data);
      if (!data.sources.length) {
        showBanner("No live sources are configured.");
      }
    })
    .catch(() => {
      showBanner("Could not load the live sources. Check that ./dev.sh is running.");
    });
})();
