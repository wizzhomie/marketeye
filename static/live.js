/*
 * Live check: fetch two real pages over HTTP, show what the server stored.
 *
 * The browser does not fetch the competitor pages itself: it asks
 * POST /api/live/collect, and the server reads the pages, parses them with the
 * parser profile and stores one reading per source. The browser only renders.
 * The daily digest card reads GET /api/daily and runs the scheduled pass with
 * POST /api/daily/run — same collection, plus a saved plain-text digest.
 */
(() => {
  "use strict";

  const state = { busy: false, data: null, daily: null };

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
    dailyMeta: el("#daily-meta"),
    dailyText: el("#daily-text"),
    runDaily: el("#run-daily"),
    copyDaily: el("#copy-daily"),
    downloadDaily: el("#download-daily"),
  };

  if (!els.sources || !els.stats) return;

  const copyTimer = { id: 0 };

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

  function showFailures(data) {
    const failures = data.sources.filter(
      (source) => source.latest && source.latest.status === "error"
    );
    if (!failures.length) return;
    showBanner(
      `${failures.length} source${failures.length === 1 ? "" : "s"} could not be read: ` +
        failures.map((source) => `${source.competitor} — ${source.latest.note}`).join("; ")
    );
  }

  /* --- daily digest ------------------------------------------------------ */

  function syncDailyButtons() {
    const hasDigest = Boolean(state.daily && state.daily.latest);
    els.copyDaily.disabled = !hasDigest;
    els.downloadDaily.disabled = !hasDigest;
  }

  function renderDaily(data) {
    state.daily = data || null;
    const latest = (data && data.latest) || null;
    const scheduler = (data && data.scheduler) || {};

    const parts = [latest ? `Last run ${when(latest.generatedAt)}` : "No digest saved yet"];
    parts.push(
      scheduler.running
        ? `Automatic run on · daily at ${scheduler.at}`
        : "Automatic run off"
    );
    if (latest && latest.count > 1) {
      parts.push(`${latest.count} digests saved`);
    }
    els.dailyMeta.textContent = parts.join(" · ");

    els.dailyText.textContent = latest
      ? latest.digest
      : "No digest yet. Run the daily check to fetch every page and write one.";
    syncDailyButtons();
  }

  async function loadDaily() {
    try {
      const response = await fetch("/api/daily");
      const data = await response.json().catch(() => null);
      if (!response.ok || !data) throw new Error("The server did not answer.");
      renderDaily(data);
    } catch {
      els.dailyMeta.textContent = "Could not load the daily digest";
      els.dailyText.textContent = "Check that ./dev.sh is running, then reload the page.";
    }
  }

  function setBusy(busy) {
    state.busy = busy;
    els.collect.disabled = busy;
    els.reset.disabled = busy;
    els.runDaily.disabled = busy;
    syncDailyButtons();
  }

  async function fetchLive() {
    const response = await fetch("/api/live");
    if (!response.ok) throw new Error("The server did not answer.");
    return response.json();
  }

  async function runDaily() {
    if (state.busy) return;
    setBusy(true);
    hideBanner();
    els.runDaily.textContent = "Checking…";
    try {
      const response = await fetch("/api/daily/run", { method: "POST" });
      const data = await response.json().catch(() => null);
      if (!response.ok || !data) {
        throw new Error((data && data.detail) || "The daily check did not finish.");
      }
      renderDaily(data);
      const live = await fetchLive();
      render(live);
      showFailures(live);
    } catch (error) {
      showBanner(
        error && error.message ? error.message : "Could not run the daily check."
      );
    } finally {
      setBusy(false);
      els.runDaily.textContent = "Run daily check";
    }
  }

  async function collect() {
    if (state.busy) return;
    setBusy(true);
    hideBanner();
    els.collectLabel.textContent = "Collecting…";
    try {
      const response = await fetch("/api/live/collect", { method: "POST" });
      const data = await response.json().catch(() => null);
      if (!response.ok || !data) {
        throw new Error((data && data.detail) || "The server could not collect the pages.");
      }
      render(data);
      showFailures(data);
    } catch (error) {
      showBanner(error && error.message ? error.message : "Could not collect the pages.");
    } finally {
      setBusy(false);
      els.collectLabel.textContent = "Collect now";
    }
  }

  async function reset() {
    if (state.busy) return;
    setBusy(true);
    hideBanner();
    try {
      const response = await fetch("/api/live/reset", { method: "POST" });
      const data = await response.json().catch(() => null);
      if (!response.ok || !data) {
        throw new Error((data && data.detail) || "The server could not reset the demo.");
      }
      render(data);
      loadDaily();
    } catch (error) {
      showBanner(error && error.message ? error.message : "Could not reset the demo.");
    } finally {
      setBusy(false);
    }
  }

  /* --- copy and download -------------------------------------------------- */

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
    range.selectNodeContents(els.dailyText);
    const selection = window.getSelection();
    if (!selection) return;
    selection.removeAllRanges();
    selection.addRange(range);
  }

  async function copyDaily() {
    if (!state.daily || !state.daily.latest) return;
    const text = els.dailyText.textContent;
    let ok = false;
    try {
      await navigator.clipboard.writeText(text);
      ok = true;
    } catch {
      ok = legacyCopy(text);
    }
    if (!ok) selectDigestText();
    els.copyDaily.textContent = ok ? "Copied" : "Selected · Ctrl+C";
    window.clearTimeout(copyTimer.id);
    copyTimer.id = window.setTimeout(() => {
      els.copyDaily.textContent = "Copy";
    }, 1800);
  }

  function downloadDaily() {
    if (!state.daily || !state.daily.latest) return;
    const blob = new Blob([state.daily.latest.digest], {
      type: "text/plain;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `marketeye-daily-${state.daily.latest.date}.txt`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  els.collect.addEventListener("click", collect);
  els.reset.addEventListener("click", reset);
  els.runDaily.addEventListener("click", runDaily);
  els.copyDaily.addEventListener("click", copyDaily);
  els.downloadDaily.addEventListener("click", downloadDaily);

  els.copyDaily.disabled = true;
  els.downloadDaily.disabled = true;

  fetchLive()
    .then((data) => {
      render(data);
      if (!data.sources.length) {
        showBanner("No live sources are configured.");
      }
    })
    .catch(() => {
      showBanner("Could not load the live sources. Check that ./dev.sh is running.");
    });
  loadDaily();
})();
