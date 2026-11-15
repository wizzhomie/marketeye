/*
 * Product page: fourteen-day price history, the current competitor spread and
 * the latest snapshots for one product.
 *
 * Data comes from the frozen fixtures in demo-data.js. The page is opened from
 * the Overview watch list or an alert as /product?id=<product>&snapshot=<index>,
 * so it always shows the same day the Overview was showing.
 */
(() => {
  "use strict";

  const demo = window.MARKETEYE_DEMO;
  if (!demo) return;

  const nf = new Intl.NumberFormat("en-US");
  const fmt = (value) => nf.format(value);
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const WINDOW_DAYS = 14;
  const SNAPSHOT_ROWS = 5;
  const SERIES_COLORS = { ours: "#141310", c0: "#141310", c1: "#8d8475", c2: "#b3aa98" };

  const params = new URLSearchParams(window.location.search);
  const product =
    demo.products.find((item) => item.id === params.get("id")) || demo.products[0];

  const requested = Number.parseInt(params.get("snapshot") || "", 10);
  const snapIndex = Number.isInteger(requested)
    ? Math.min(Math.max(requested, 0), demo.snapshots.length - 1)
    : 1;

  const snapDate = demo.snapshots[snapIndex].date;
  const endIndex = demo.history.findIndex((day) => day.date === snapDate);
  const history =
    endIndex >= 0
      ? demo.history.slice(0, endIndex + 1).slice(-WINDOW_DAYS)
      : demo.history.slice(-WINDOW_DAYS);
  const days = history.length;
  const comps = demo.competitors;
  const ours = demo.ourPrices[product.id];
  const current = history[days - 1];
  const previous = days > 1 ? history[days - 2] : null;

  const priceOn = (day, competitor) => day.prices[product.id][competitor];
  const pct = (from, to) => Math.round(((to - from) / from) * 100);
  const pctShort = (from, to) => {
    const raw = Math.abs(((to - from) / from) * 100);
    const rounded = Math.round(raw);
    return String(rounded === 0 && raw > 0 ? Math.round(raw * 10) / 10 : rounded);
  };
  const pctLabel = (from, to) => {
    const raw = Math.abs(((to - from) / from) * 100);
    if (raw >= 10) return String(Math.round(raw));
    const rounded = Math.round(raw * 10) / 10;
    return String(rounded);
  };
  const shortDate = (date) => {
    const [day, month] = date.split(" ");
    return `${day} ${month.slice(0, 3)}`;
  };

  const el = (selector) => document.querySelector(selector);
  const els = {
    title: el("#product-title"),
    crumb: el("#crumb-product"),
    date: el("#snapshot-date"),
    stats: el("#stats"),
    legend: el("#chart-legend"),
    chart: el("#chart"),
    chartSub: el("#chart-sub"),
    chartWindow: el("#chart-window"),
    chartHint: el("#chart-hint"),
    chartTable: el("#chart-table"),
    spread: el("#spread-list"),
    spreadSub: el("#spread-sub"),
    snapshotsHead: el("#snapshots-head"),
    snapshotsBody: el("#snapshots-body"),
    snapshotsSub: el("#snapshots-sub"),
    snapshotsCount: el("#snapshots-count"),
  };

  if (!els.chart || !els.stats || !els.spread) return;

  /* --- numbers ---------------------------------------------------------- */

  const priced = comps
    .map((name) => ({
      name,
      price: priceOn(current, name),
      previous: previous ? priceOn(previous, name) : null,
    }))
    .sort((a, b) => a.price - b.price);

  const lowest = priced[0];
  const highest = priced[priced.length - 1];
  const gapPct = ours > lowest.price ? Math.round(((ours - lowest.price) / ours) * 100) : 0;
  const spreadAbs = highest.price - lowest.price;
  const spreadPct = Math.round((spreadAbs / highest.price) * 100);

  const marketLow = history.map((day) =>
    Math.min(...comps.map((competitor) => priceOn(day, competitor)))
  );
  const movePct = pct(marketLow[0], marketLow[days - 1]);

  const series = [
    { id: "ours", name: "Your price", value: ours, swatch: "legend-swatch--ours" },
    ...comps.map((name, index) => ({
      id: `c${index}`,
      name,
      value: priceOn(current, name),
      swatch: `legend-swatch--c${index}`,
    })),
  ];

  function stat(value, label, hint) {
    return `<li class="stat">
      <span class="stat__label">${label}</span>
      <span class="stat__value">${value}</span>
      <span class="stat__hint">${hint}</span>
    </li>`;
  }

  function renderHead() {
    document.title = `${product.name} — Market Eye`;
    els.title.textContent = product.name;
    els.crumb.textContent = product.name;
    els.date.textContent = snapDate;
    els.chartSub.textContent = `${history[0].date} – ${snapDate}`;
    els.chartWindow.textContent = `${days} days`;
    els.spreadSub.textContent = `Against your ${fmt(ours)} ${demo.currency}`;
    els.chartHint.textContent = reduceMotion
      ? "The chart shows daily saved prices."
      : "Hover the chart to read a day.";
  }

  function renderStats() {
    const gap = gapPct ? `${gapPct}%` : "0%";
    const move = `${movePct > 0 ? "+" : "−"}${Math.abs(movePct)}%`;
    els.stats.innerHTML = [
      stat(fmt(ours), "Ours", demo.currency),
      stat(fmt(lowest.price), "Lowest", lowest.name),
      stat(gap, "Gap to lowest", gapPct ? "below your price" : "no one below you"),
      stat(movePct ? move : "0%", "Window move", `${days} days · market low`),
    ].join("");
  }

  function renderLegend() {
    els.legend.innerHTML = series
      .map(
        (item) => `<li class="legend-item">
          <span class="legend-swatch ${item.swatch}"></span>
          <b>${item.name}</b> ${fmt(item.value)}
        </li>`
      )
      .join("");
  }

  /* --- chart ------------------------------------------------------------ */

  function niceStep(raw) {
    const power = Math.pow(10, Math.floor(Math.log10(raw)));
    const fraction = raw / power;
    let multiple = 10;
    if (fraction <= 1) multiple = 1;
    else if (fraction <= 2) multiple = 2;
    else if (fraction <= 2.5) multiple = 2.5;
    else if (fraction <= 5) multiple = 5;
    return multiple * power;
  }

  // The chart is drawn in its own pixel space, so text stays readable on a
  // phone: the viewBox width follows the card width and the page redraws on
  // resize.
  function chartModel(width) {
    const narrow = width < 520;
    const VB = {
      width,
      height: narrow ? 260 : 300,
      left: narrow ? 46 : 58,
      right: narrow ? 12 : 16,
      top: 16,
      bottom: 34,
    };
    const plotW = VB.width - VB.left - VB.right;
    const plotH = VB.height - VB.top - VB.bottom;

    const values = [];
    for (const day of history) {
      values.push(ours);
      for (const competitor of comps) values.push(priceOn(day, competitor));
    }
    const min = Math.min(...values);
    const max = Math.max(...values);
    let step = niceStep((max - min) / 4 || Math.max(1, max / 8));
    let yMin = Math.floor(min / step) * step;
    let yMax = Math.ceil(max / step) * step;
    while ((yMax - yMin) / step > 6) {
      step *= 2;
      yMin = Math.floor(min / step) * step;
      yMax = Math.ceil(max / step) * step;
    }

    const x = (index) =>
      VB.left + (days === 1 ? plotW / 2 : (index / (days - 1)) * plotW);
    const y = (value) => VB.top + ((yMax - value) / (yMax - yMin)) * plotH;

    const ticks = [];
    for (let value = yMin; value <= yMax + 1e-9; value += step) ticks.push(value);

    const labelCount = Math.min(narrow ? 4 : 5, days);
    const labelIndexes = [];
    for (let i = 0; i < labelCount; i += 1) {
      labelIndexes.push(Math.round((i / Math.max(labelCount - 1, 1)) * (days - 1)) || 0);
    }

    const valuesAt = (index) => {
      const day = history[index];
      return series.map((item) =>
        item.id === "ours" ? ours : priceOn(day, comps[Number(item.id.slice(1))])
      );
    };

    return { VB, plotW, x, y, ticks, labelIndexes, valuesAt };
  }

  function renderChart() {
    const style = getComputedStyle(els.chart);
    const padding =
      (parseFloat(style.paddingLeft) || 0) + (parseFloat(style.paddingRight) || 0);
    const width = Math.max(300, Math.round(els.chart.clientWidth - padding));
    const { VB, plotW, x, y, ticks, labelIndexes, valuesAt } = chartModel(width);

    const parts = [
      `<svg viewBox="0 0 ${VB.width} ${VB.height}" role="img" aria-label="${product.name}: ${days} days of prices for you and ${comps.length} competitors.">`,
    ];

    for (const tick of ticks) {
      parts.push(
        `<line class="chart-grid" x1="${VB.left}" y1="${y(tick)}" x2="${VB.width - VB.right}" y2="${y(tick)}"/>`,
        `<text x="${VB.left - 8}" y="${y(tick) + 3.5}" text-anchor="end">${fmt(tick)}</text>`
      );
    }

    parts.push(
      `<line class="chart-axis" x1="${VB.left}" y1="${VB.height - VB.bottom}" x2="${VB.width - VB.right}" y2="${VB.height - VB.bottom}"/>`
    );

    for (const index of labelIndexes) {
      parts.push(
        `<text x="${x(index)}" y="${VB.height - VB.bottom + 16}" text-anchor="middle">${shortDate(history[index].date)}</text>`
      );
    }

    series.forEach((item) => {
      const competitor = item.id === "ours" ? null : comps[Number(item.id.slice(1))];
      const points = history
        .map((day, index) => {
          const value = competitor ? priceOn(day, competitor) : ours;
          return `${x(index).toFixed(1)},${y(value).toFixed(1)}`;
        })
        .join(" ");
      parts.push(`<polyline class="series series-${item.id}" points="${points}"/>`);
    });

    const dots = series
      .map(
        (item) =>
          `<circle class="chart-hover-dot" data-series="${item.id}" r="4" style="stroke:${SERIES_COLORS[item.id]};fill:#ffffff"/>`
      )
      .join("");
    parts.push(
      `<g id="chart-hover" style="opacity:0">` +
        `<line class="chart-hover-line" x1="0" y1="${VB.height - VB.bottom}" x2="0" y2="${VB.top}"/>` +
        dots +
        `</g>`
    );

    parts.push("</svg>");
    els.chart.querySelector("svg")?.remove();
    els.chart.querySelector(".chart-tooltip")?.remove();
    els.chart.insertAdjacentHTML("afterbegin", parts.join(""));

    const tooltip = document.createElement("div");
    tooltip.className = "chart-tooltip";
    els.chart.appendChild(tooltip);

    const svg = els.chart.querySelector("svg");
    const hover = svg.querySelector("#chart-hover");
    const hoverLine = hover.querySelector(".chart-hover-line");
    const hoverDots = [...hover.querySelectorAll(".chart-hover-dot")];
    const xs = history.map((_, index) => x(index));
    let activeIndex = -1;

    function hide() {
      activeIndex = -1;
      hover.style.opacity = "0";
      tooltip.classList.remove("is-visible");
    }

    function show(index) {
      if (index === activeIndex) return;
      activeIndex = index;
      hover.style.opacity = "1";

      const svgRect = svg.getBoundingClientRect();
      const chartRect = els.chart.getBoundingClientRect();
      const scaleX = svgRect.width / VB.width;
      const scaleY = svgRect.height / VB.height;
      const anchorX = xs[index];
      const values = valuesAt(index);

      hoverLine.setAttribute("x1", String(anchorX));
      hoverLine.setAttribute("x2", String(anchorX));
      hoverDots.forEach((dot, seriesIndex) => {
        dot.setAttribute("cx", String(anchorX));
        dot.setAttribute("cy", String(y(values[seriesIndex])));
      });

      const day = history[index];
      tooltip.innerHTML =
        `<p class="chart-tooltip__date">${day.date}</p>` +
        series
          .map(
            (item, seriesIndex) =>
              `<p class="chart-tooltip__row"><span class="chart-tooltip__name"><span class="legend-swatch ${item.swatch}"></span>${item.name}</span><b>${fmt(values[seriesIndex])}</b></p>`
          )
          .join("");

      const left = svgRect.left - chartRect.left + anchorX * scaleX;
      const top = svgRect.top - chartRect.top + Math.min(...values.map(y)) * scaleY - 10;
      const half = tooltip.offsetWidth / 2;
      tooltip.style.left = `${Math.min(Math.max(left, half + 4), chartRect.width - half - 4)}px`;
      tooltip.style.top = `${top}px`;
      tooltip.classList.add("is-visible");
    }

    svg.addEventListener("pointermove", (event) => {
      const rect = svg.getBoundingClientRect();
      const scale = rect.width / VB.width;
      const localX = (event.clientX - rect.left) / scale;
      let index = 0;
      if (days > 1) {
        index = Math.round(((localX - VB.left) / plotW) * (days - 1));
      }
      show(Math.min(Math.max(index, 0), days - 1));
    });
    svg.addEventListener("pointerleave", hide);
    svg.addEventListener("pointercancel", hide);

    // Screen-reader view of the same data.
    els.chartTable.innerHTML =
      `<table><caption>Daily prices, ${history[0].date} to ${snapDate}</caption><thead><tr><th>Date</th><th>Your price</th>` +
      comps.map((name) => `<th>${name}</th>`).join("") +
      `</tr></thead><tbody>` +
      history
        .map(
          (day) =>
            `<tr><td>${day.date}</td><td>${fmt(ours)}</td>` +
            comps.map((name) => `<td>${fmt(priceOn(day, name))}</td>`).join("") +
            `</tr>`
        )
        .join("") +
      `</tbody></table>`;
  }

  let resizeFrame = 0;
  window.addEventListener("resize", () => {
    if (resizeFrame) return;
    resizeFrame = requestAnimationFrame(() => {
      resizeFrame = 0;
      renderChart();
    });
  });

  /* --- spread ----------------------------------------------------------- */

  function renderSpread() {
    els.spread.innerHTML = priced
      .map((item, index) => {
        const isLowest = index === 0;
        const versusOurs =
          item.price === ours
            ? "At your price"
            : item.price < ours
            ? `${pctShort(ours, item.price)}% below your price`
            : `${pctShort(ours, item.price)}% above your price`;
        const dayMove =
          item.previous === null || item.previous === item.price
            ? "No change vs yesterday"
            : `<span class="delta delta--${item.price < item.previous ? "down" : "up"}">${
                item.price < item.previous ? "▼" : "▲"
              } ${pctLabel(item.previous, item.price)}%</span> vs yesterday`;
        return `<li class="spread-item${isLowest ? " spread-item--lowest" : ""}">
          <span class="spread-item__name">
            <b>${item.name}${isLowest ? ' <span class="badge badge--solid">Lowest</span>' : ""}</b>
            <span class="spread-item__meta">${versusOurs}</span>
          </span>
          <span class="spread-item__price">
            <span class="spread-price">${fmt(item.price)}</span>
            <span class="spread-delta">${dayMove}</span>
          </span>
        </li>`;
      })
      .join("");
  }

  /* --- latest snapshots -------------------------------------------------- */

  function renderSnapshots() {
    els.snapshotsHead.innerHTML =
      `<tr><th scope="col">Date</th><th scope="col" class="num">Ours</th>` +
      comps.map((name) => `<th scope="col" class="num">${name}</th>`).join("") +
      `</tr>`;

    const rows = history.slice(-SNAPSHOT_ROWS).reverse();
    els.snapshotsBody.innerHTML = rows
      .map((day, rowIndex) => {
        const dayIndex = history.indexOf(day);
        const earlier = dayIndex > 0 ? history[dayIndex - 1] : null;
        const cells = comps
          .map((name) => {
            const price = priceOn(day, name);
            const from = earlier ? priceOn(earlier, name) : price;
            const diff = price - from;
            const delta = diff
              ? ` <span class="delta delta--${diff < 0 ? "down" : "up"}">${
                  diff < 0 ? "▼" : "▲"
                } ${pctLabel(from, price)}%</span>`
              : "";
            return `<td class="num${price < ours ? " cell--below" : ""}">${fmt(price)}${delta}</td>`;
          })
          .join("");
        return `<tr${rowIndex === 0 ? ' class="is-latest"' : ""}>
          <th scope="row" class="date-cell">${day.date}</th>
          <td class="num">${fmt(ours)}</td>
          ${cells}
        </tr>`;
      })
      .join("");

    els.snapshotsSub.textContent = `${rows.length} saved ${rows.length === 1 ? "day" : "days"} · one snapshot a day`;
    els.snapshotsCount.textContent = `${rows.length} ${rows.length === 1 ? "day" : "days"}`;
  }

  renderHead();
  renderStats();
  renderLegend();
  renderChart();
  renderSpread();
  renderSnapshots();
})();
