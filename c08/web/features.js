// Seamline features: the "Why the sensors differ" explainer, the Comparison Studio and the Satellite Handover
// Simulator. (The coverage layer and the experimental outlook are in layers.js.)
// Every number here comes from the local API. The explainer is a labelled diagram, not data.
(function () {
  "use strict";
  if (typeof window === "undefined" || !window.Seam) return;
  const S = window.Seam, $ = (id) => document.getElementById(id);
  const { fmt, esc, css, MONTH_FULL, MONTHS, SATS, SAT_INFO } = S;
  const NS = "http://www.w3.org/2000/svg";
  const svgEl = (tag, attrs, parent) => { const n = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, v); if (parent) parent.appendChild(n); return n; };
  const pct = (v, d = 1) => (v == null ? "–" : fmt(v * 100, d) + "%");

  // =========================================================================================================
  // 1. "Why the sensors differ": a short, optional, replayable diagram (about 10 seconds)
  // =========================================================================================================
  const EX_STEPS = [
    ["One patch of ground, two sensors", "MODIS sees this ground in ~1 km nadir pixels across a ±45° swath (stretching toward 4.83 × 2.01 km off-nadir). VIIRS C2 uses 375 m nadir pixels with 3:1→2:1→1:1 onboard aggregation keeping edge pixels < 0.8 km (Giglio et al. 2016; Schroeder et al. 2014)."],
    ["Small burning patches & FRP floors", "MODIS needs roughly 3.7–40 MW minimum FRP to trigger, whereas VIIRS reaches ~0.5 MW (Sofiev & Kouznetsov 2026). Both compute Wooster MIR-linear FRP (VIIRS falls back from 367 K saturated I4 to dual-gain M13), so VIIRS captures smaller/cooler burns missed at 1 km."],
    ["So the count changes with the sensor", "Join raw counts across 2012/2018/2023 or mix standard type=0 archives with untyped NRT static flares/kilns, and counts jump artificially—e.g. Punjab averages ~7.6× more VIIRS detections by day yet ~64× by night."],
    ["A finer grid is not harmonisation", "Seamline does not redraw pixels or apply a universal multiplier. It fits region-calibrated P01 bridges on overlap months, validates held-out years (including NOAA-20 post-2 Nov 2026 S-NPP cessation at 5.1% WAPE in Punjab), and flags missing passes openly."],
  ];
  let exTimer = null, exStep = 0;
  const FONT = () => css("--font").replace(/"/g, "'"), DISPLAY = () => css("--display").replace(/"/g, "'");
  function explainerSvg() {
    // A 3 km x 3 km patch drawn twice. Marks are illustrative only and are labelled so in the figure.
    const c = { ink: css("--ink"), line: css("--line2"), aqua: css("--aqua"), snpp: css("--snpp"), muted: css("--muted"), bg: css("--raised"), naive: css("--naive") };
    const X0 = 40, X1 = 420, Y = 62, SZ = 270, km = SZ / 3, v = 0.375 * km;
    const marks = [[0.55, 0.5, 0.11], [1.62, 1.3, 0.2], [1.95, 1.52, 0.16], [2.4, 2.45, 0.07], [0.8, 2.3, 0.06]];     // km: x, y, radius
    const modisOn = [[1, 1]], viirsOn = [[1, 1], [4, 3], [4, 4], [5, 3], [5, 4], [6, 6]];
    let s = `<svg viewBox="0 0 760 392" role="img" aria-label="Diagram, not data: the same 3 km patch of ground as a MODIS grid of 1 km pixels and as a VIIRS grid of 375 m pixels, with five illustrative burning patches. MODIS flags one pixel; VIIRS flags six.">`;
    s += `<text x="380" y="22" text-anchor="middle" style="font:600 13px ${FONT()};fill:${c.muted};letter-spacing:.06em">DIAGRAM · NOT MEASURED DATA · NOMINAL PIXEL SIZES AT THE CENTRE OF THE SCAN</text>`;
    const grid = (x0, step, n, color, on, cls) => {
      let g = `<g class="${cls}">`;
      for (const [i, j] of on) g += `<rect class="ex-fade ex-s3" x="${x0 + i * step}" y="${Y + j * step}" width="${step}" height="${step}" fill="${color}" opacity=".3"/>`;
      for (let i = 0; i <= n; i++) {
        const p = Math.min(SZ, i * step);
        g += `<line x1="${x0 + p}" y1="${Y}" x2="${x0 + p}" y2="${Y + SZ}" stroke="${color}" stroke-width="${i === 0 || p === SZ ? 1.6 : 0.9}"/><line x1="${x0}" y1="${Y + p}" x2="${x0 + SZ}" y2="${Y + p}" stroke="${color}" stroke-width="${i === 0 || p === SZ ? 1.6 : 0.9}"/>`;
      }
      return g + "</g>";
    };
    s += `<text x="${X0}" y="${Y - 12}" style="font:650 15px ${FONT()};fill:${c.aqua}">MODIS · about 1 km pixels</text>` + grid(X0, km, 3, c.aqua, modisOn, "ex-g");
    s += `<text x="${X1}" y="${Y - 12}" style="font:650 15px ${FONT()};fill:${c.snpp}">VIIRS · about 375 m pixels</text>` + grid(X1, v, 8, c.snpp, viirsOn, "ex-g");
    for (const x0 of [X0, X1]) for (const [mx, my, r] of marks) s += `<circle class="ex-fade ex-s2" cx="${x0 + mx * km}" cy="${Y + my * km}" r="${r * km}" fill="${c.ink}" opacity=".78"/>`;
    s += `<text class="ex-fade ex-s2" x="${X0}" y="${Y + SZ + 20}" style="font:500 12.5px ${FONT()};fill:${c.muted}">● illustrative burning patches (the same five on both sides)</text>`;
    s += `<g class="ex-fade ex-s3"><text x="${X0 + SZ / 2}" y="${Y + SZ + 44}" text-anchor="middle" style="font:700 20px ${DISPLAY()};fill:${c.aqua}">1 detection</text>` +
      `<text x="${X1 + SZ / 2}" y="${Y + SZ + 44}" text-anchor="middle" style="font:700 20px ${DISPLAY()};fill:${c.snpp}">6 detections</text>` +
      `<text x="380" y="${Y + SZ + 44}" text-anchor="middle" style="font:500 12.5px ${FONT()};fill:${c.muted}">in this diagram</text></g>`;
    s += `<g class="ex-fade ex-s4"><rect x="${X0 + SZ + 12}" y="${Y + 96}" width="${X1 - X0 - SZ - 24}" height="78" rx="8" fill="${c.bg}" stroke="${c.ink}" stroke-width="1.5"/>` +
      `<text x="380" y="${Y + 122}" text-anchor="middle" style="font:650 12.5px ${FONT()};fill:${c.ink}">calibrated</text>` +
      `<text x="380" y="${Y + 139}" text-anchor="middle" style="font:650 12.5px ${FONT()};fill:${c.ink}">conversion,</text>` +
      `<text x="380" y="${Y + 156}" text-anchor="middle" style="font:650 12.5px ${FONT()};fill:${c.ink}">then tested</text></g>`;
    return s + "</svg>";
  }
  function exShow(i, body) {
    exStep = Math.max(0, Math.min(EX_STEPS.length - 1, i));
    for (const n of body.querySelectorAll(".ex-fade")) {
      const need = Number((n.getAttribute("class").match(/ex-s(\d)/) || [0, 1])[1]);
      n.style.opacity = exStep + 1 >= need ? (n.getAttribute("opacity") || "1") : "0";
    }
    body.querySelectorAll(".ex-steps button").forEach((b, j) => { if (j === exStep) b.setAttribute("aria-current", "step"); else b.removeAttribute("aria-current"); });
    body.querySelector(".ex-cap").innerHTML = `<b>${exStep + 1}. ${esc(EX_STEPS[exStep][0])}.</b> ${esc(EX_STEPS[exStep][1])}`;
    body.querySelector("#ex-live").textContent = `Step ${exStep + 1} of ${EX_STEPS.length}: ${EX_STEPS[exStep][0]}. ${EX_STEPS[exStep][1]}`;
  }
  function exStop(body) {
    clearInterval(exTimer); exTimer = null;
    const b = body && body.querySelector("#ex-play");
    if (b) { b.textContent = "Play"; b.setAttribute("aria-pressed", "false"); }
  }
  function exPlay(body) {
    exStop(body);
    if (exStep >= EX_STEPS.length - 1) exShow(0, body);
    const b = body.querySelector("#ex-play");
    b.textContent = "Pause"; b.setAttribute("aria-pressed", "true");
    exTimer = setInterval(() => { if (exStep >= EX_STEPS.length - 1) exStop(body); else exShow(exStep + 1, body); }, 2600);
  }
  function openExplainer(opener) {
    const still = S.motionMode() !== "full";
    const html = `<div class="explainer">${explainerSvg()}
      <div class="ex-steps" role="group" aria-label="Steps">${EX_STEPS.map((s, i) => `<button type="button" data-ex="${i}">${i + 1}. ${esc(s[0])}</button>`).join("")}</div>
      <p class="ex-cap"></p><p class="sr" id="ex-live" aria-live="polite"></p>
      ${still ? `<ol class="note">${EX_STEPS.map((s) => `<li><b>${esc(s[0])}.</b> ${esc(s[1])}</li>`).join("")}</ol>` : ""}
      <div class="btn-row">${still ? "" : `<button type="button" class="btn-primary" id="ex-play" aria-pressed="false">Play</button>`}
        <button type="button" class="btn" id="ex-back">Back</button><button type="button" class="btn" id="ex-next">Next</button>
        <button type="button" class="btn" id="ex-replay">${still ? "First step" : "Replay"}</button><button type="button" class="btn" id="ex-skip">Skip to the end</button></div>
      <p class="note">Educational context only. The patches and counts in the diagram are made up to show the idea; they are not detections and not evidence about any model. Real pixel sizes grow toward the edge of each scan.</p></div>`;
    const body = S.openDialog("Why the sensors differ", html, opener, () => exStop(null));
    exShow(still ? EX_STEPS.length - 1 : 0, body);
    body.addEventListener("click", (e) => {
      const st = e.target.closest("[data-ex]");
      if (st) { exStop(body); exShow(Number(st.dataset.ex), body); return; }
      if (e.target.closest("#ex-play")) { exTimer ? exStop(body) : exPlay(body); return; }
      if (e.target.closest("#ex-back")) { exStop(body); exShow(exStep - 1, body); }
      if (e.target.closest("#ex-next")) { exStop(body); exShow(exStep + 1, body); }
      if (e.target.closest("#ex-replay")) { exStop(body); exShow(0, body); if (!still) exPlay(body); }
      if (e.target.closest("#ex-skip")) { exStop(body); exShow(EX_STEPS.length - 1, body); }
    });
    if (!still) exPlay(body);
  }

  // =========================================================================================================
  // 2. Comparison Studio: two areas over one period, or one area over two periods
  // =========================================================================================================
  const ST = { a: null, b: null, linked: true, res: null, req: 0, ctrl: null, maps: {}, pts: {}, sat: { a: "SNPP", b: "SNPP" }, built: false, busy: false, err: "" };
  function studioDefaults() {
    const r = S.result(), m = S.meta();
    const base = { region: r.request.bbox ? null : r.region, bbox: r.request.bbox ? r.request.bbox.map(Number) : null, years: r.years.slice(), month: r.request.month.slice(), model: r.model };
    ST.a = { ...base };
    const other = m.regions.find((x) => x !== base.region && x !== "Pakistan") || "Sindh";
    ST.b = { ...base, bbox: null, region: base.region === "Punjab" || !base.region ? "Sindh" : other === base.region ? "Punjab" : "Punjab" };
  }
  const paneLabel = (p) => (p.bbox ? `Rectangle ${p.bbox.map((v) => fmt(v, 2)).join(", ")}` : p.region);
  function paneForm(k) {
    const p = ST[k], m = S.meta(), r = S.result();
    const areas = m.regions.map((x) => `<option value="${esc(x)}"${!p.bbox && p.region === x ? " selected" : ""}>${esc(x)}</option>`).join("") +
      (r.request.bbox ? `<option value="__box"${p.bbox ? " selected" : ""}>The selected rectangle</option>` : "");
    const years = []; for (let y = p.years[0]; y <= p.years[1]; y++) years.push(y);
    return `<div class="studio-fields">
      <label>Area <select data-st="${k}:area">${areas}</select></label>
      <label>Month <select data-st="${k}:month">${MONTH_FULL.map((n, i) => `<option value="${i + 1}"${p.month[1] === i + 1 ? " selected" : ""}>${n}</option>`).join("")}</select></label>
      <label>Year <select data-st="${k}:year">${years.map((y) => `<option${p.month[0] === y ? " selected" : ""}>${y}</option>`).join("")}</select></label>
      <label>Model <select data-st="${k}:model">${m.models.map((x) => `<option${p.model === x ? " selected" : ""}>${x}</option>`).join("")}</select></label>
      <label>Map satellite <select data-st="${k}:sat">${SATS.map((x) => `<option value="${x}"${ST.sat[k] === x ? " selected" : ""}>${esc(SAT_INFO[x].label)}</option>`).join("")}</select></label></div>`;
  }
  function studioShell() {
    $("studio-body").innerHTML = `<p class="lede">Put two selections side by side: two areas over the same period, or one area over two periods. Each side keeps its own area, dates, model, calibration and seasonal baseline.</p>
      <div class="btn-row" role="group" aria-label="Quick set-ups">
        <button type="button" class="btn" data-st-preset="areas">Two areas, same month</button>
        <button type="button" class="btn" data-st-preset="periods">One area, two periods</button>
        <label class="inline"><input type="checkbox" id="st-linked"${ST.linked ? " checked" : ""}> Linked: one colour scale, one map scale, and month changes copy across</label>
        <button type="button" class="btn-primary" id="st-export">Export both (ZIP)</button></div>
      <p class="msg" id="st-msg" role="status" aria-live="polite"></p>
      <div id="st-reading"></div>
      <div class="studio-form"><div class="studio-pane" id="st-a"></div><div class="studio-pane" id="st-b"></div></div>
      <section class="panel" style="margin-top:var(--s3)"><h3 style="margin-top:0">The same month across the years, each side on its own line</h3><div class="legend" id="st-legend"></div><div class="chart" id="st-chart"></div>
        <details><summary>Show these values as a table</summary><div class="table-wrap" id="st-table"></div></details></section>
      <div id="st-defs"></div>`;
    ST.built = true;
  }
  async function studioRun() {
    if (!S.result()) return;
    if (!ST.a) studioDefaults();
    if (!ST.built) studioShell();
    const id = ++ST.req;
    if (ST.ctrl) ST.ctrl.abort();
    ST.ctrl = new AbortController();
    ST.busy = true; ST.err = "";
    $("st-msg").className = "msg";
    $("st-msg").textContent = ST.res ? "Updating the comparison… The panes below still show the previous pair." : "Calculating the comparison…";
    for (const k of ["a", "b"]) $(`st-${k}`).classList.toggle("is-stale", !!ST.res);
    const sel = (p) => ({ region: p.region, bbox: p.bbox || undefined, years: p.years, month: p.month, model: p.model });
    try {
      const res = await (await S.post("/api/compare", { a: sel(ST.a), b: sel(ST.b) }, ST.ctrl.signal)).json();
      if (id !== ST.req) return;
      ST.res = res; ST.busy = false;
      $("st-msg").textContent = "";
      studioRender();
      for (const k of ["a", "b"]) studioPoints(k, id);
    } catch (e) {
      if (id !== ST.req || e.name === "AbortError") return;
      ST.busy = false; ST.err = e.message;
      $("st-msg").className = "msg error";
      $("st-msg").innerHTML = `The comparison could not be calculated. ${esc(e.message)} <button type="button" class="btn" id="st-retry">Try again</button>`;
    }
  }
  const clsBadge = (h) => (h && h.cls ? `<span class="cls ${h.cls}">${h.cls}</span>` : "");
  function paneHtml(k) {
    const p = ST.res[k], h = p.month_value;
    const val = h.value == null ? `<b>No harmonised value</b> for ${esc(p.month_name)}` : `<span class="cd-num">${fmt(h.value)}</span> detections in ${esc(p.month_name)} ${clsBadge(h)}`;
    const normal = String(h.status || "").startsWith("compared")
      ? `${fmt(h.ratio, 2)}× its own normal (median ${fmt(h.median)} over ${h.baseline_n} other years, ${p.years[0]}–${p.years[1]})${h.status !== "compared" ? `. ${esc(h.status)}` : ""}`
      : esc(h.status || "not compared");
    const season = (s) => (s.value == null ? esc(s.status) : `${fmt(s.value)}${s.status === "compared" ? `; ${fmt(s.ratio, 2)}× its own median of ${fmt(s.median)} (${s.baseline_n} years)` : `; ${esc(s.status)}`}`);
    return `<h3><span class="pane-tag">${k.toUpperCase()}</span>${esc(p.region)} · ${esc(p.month_name)}</h3>${paneForm(k)}
      <p class="msg ${p.supported ? "" : "error"}" style="margin:8px 0 0">${p.supported ? "" : "This area has no conversion, so months before February 2012 have no value here."}</p>
      <div class="cal-detail"><div class="cd-main"><div>${val}</div><div class="note">Harmonised, S-NPP-equivalent · ${esc(p.month_source || "no source")} · model ${esc(p.model)}</div></div></div>
      <div class="studio-map" id="st-map-${k}" aria-label="Map of pane ${k.toUpperCase()}"></div><p class="note" id="st-mapnote-${k}">Loading the observed points…</p>
      <dl class="facts">
        <dt>Against its own normal</dt><dd>${normal}</dd>
        <dt>October–November ${p.seasons.OctNov.year}</dt><dd>${season(p.seasons.OctNov)}</dd>
        <dt>April–May ${p.seasons.AprMay.year}</dt><dd>${season(p.seasons.AprMay)}</dd>
        <dt>Area</dt><dd>${fmt(p.area_km2)} km² (${esc(p.area_kind)})${p.box ? `; ${fmt(p.box.share_inside_pakistan * 100)}% inside Pakistan` : ""}</dd>
        <dt>Per 1,000 km²</dt><dd>${p.per_1000_km2 == null ? "–" : fmt(p.per_1000_km2, 2) + " detections in the month ÷ area"} <span class="note">(${esc(p.per_area_note)})</span></dd>
        <dt>Calibration</dt><dd>${esc(p.calibration_scope)}${p.cv_wape == null ? "" : ` Cross-validation error ${pct(p.cv_wape, 0)}.`}</dd>
        <dt>Coverage</dt><dd>${p.coverage.months_with_a_coverage_flag} of ${p.coverage.months_total} months carry a coverage flag${p.coverage.selected_month_flag ? `; this month: ${esc(p.coverage.selected_month_flag)}` : ""}. <span class="note">${esc(p.coverage.note)}</span></dd>
        <dt>Reference scale</dt><dd>${esc(p.reference)}</dd></dl>
      <h4>Calendar of this side (harmonised)</h4><div class="chart" id="st-cal-${k}"></div>
      ${p.warnings.length ? `<details><summary>${p.warnings.length} notes for this area</summary><ul class="note">${p.warnings.map((w) => `<li>${esc(w)}</li>`).join("")}</ul></details>` : ""}`;
  }
  function miniCal(host, cells, max, mark) {
    host.innerHTML = "";
    const years = [...new Set(cells.map((c) => c.year))];
    const avail = Math.max(280, Math.round(host.clientWidth || 420)), L = 36, T = 16, cw = Math.max(16, Math.floor((avail - L - 2) / 12)), ch = 11;
    const W = L + cw * 12 + 2, H = T + ch * years.length + 2;
    const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Monthly detections by year and month; darker is more. The numbers are in the main Calendar view for each area." }, host);
    const seq = [...Array(7).keys()].map((i) => css(`--seq-${i}`));
    MONTHS.forEach((m, i) => { svgEl("text", { x: L + cw * i + cw / 2, y: 11, "text-anchor": "middle", style: `font:11px ${css("--font")};fill:${css("--muted")}` }, svg).textContent = m[0]; });
    years.forEach((y, j) => { if (j % 4 === 0) svgEl("text", { x: L - 5, y: T + ch * j + 9, "text-anchor": "end", style: `font:11px ${css("--font")};fill:${css("--muted")}` }, svg).textContent = y; });
    for (const c of cells) {
      const x = L + cw * (c.month - 1), y = T + ch * years.indexOf(c.year);
      const b = c.value == null ? -1 : Math.min(6, Math.floor((Math.log1p(c.value) / Math.log1p(max)) * 7));
      const r = svgEl("rect", { x: x + 0.5, y: y + 0.5, width: cw - 1, height: ch - 1, rx: 1.5, fill: b < 0 ? css("--nodata") : seq[b] }, svg);
      svgEl("title", {}, r).textContent = `${MONTH_FULL[c.month - 1]} ${c.year}: ${c.value == null ? "no data" : fmt(c.value) + " detections"}${c.flag ? ` (coverage: ${c.flag})` : ""}`;
      if (mark && c.year === mark[0] && c.month === mark[1]) svgEl("rect", { x: x + 0.5, y: y + 0.5, width: cw - 1, height: ch - 1, rx: 1.5, fill: "none", stroke: css("--ink"), "stroke-width": 2 }, svg);
    }
  }
  function studioRender() {
    const R = ST.res, rd = R.reading;
    const head = rd.unavailable ? `<p><b>${esc(rd.unavailable)}</b></p>`
      : (rd.difference ? `<p><span class="cd-num" style="font:700 30px/1 var(--display)">${rd.difference.value > 0 ? "+" : ""}${fmt(rd.difference.value)}</span> detections (${fmt(rd.difference.ratio, 2)}×): ${esc(rd.difference.definition)}.</p>` : "") +
        (rd.ratio_of_normals ? `<p>Against each side's own normal: A <b>${fmt(rd.ratio_of_normals.a, 2)}×</b>, B <b>${fmt(rd.ratio_of_normals.b, 2)}×</b>. <span class="note">${esc(rd.ratio_of_normals.definition)}</span></p>` : "");
    $("st-reading").innerHTML = `<div class="reading"><h3>What can be said: ${esc(rd.mode)}</h3>${head}${rd.notes.length ? `<ul class="note">${rd.notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>` : ""}</div>`;
    for (const k of ["a", "b"]) { $(`st-${k}`).classList.remove("is-stale"); $(`st-${k}`).innerHTML = paneHtml(k); }
    // calendars: one colour scale when linked (so the two can be read against each other), otherwise each its own
    const mx = (k) => Math.max(1, ...R[k].calendar.map((c) => c.value || 0));
    const shared = Math.max(mx("a"), mx("b"));
    for (const k of ["a", "b"]) miniCal($(`st-cal-${k}`), R[k].calendar, ST.linked ? shared : mx(k), R[k].month.split("-").map(Number));
    studioChart();
    const d = R.definitions;
    $("st-defs").innerHTML = `<details><summary>Definitions used on this page</summary><dl class="facts"><dt>Units</dt><dd>${esc(d.units)}</dd><dt>Reference</dt><dd>${esc(d.reference)}</dd><dt>Baseline</dt><dd>${esc(d.baseline)}</dd><dt>Above, below</dt><dd>${esc(d.above_below)}</dd><dt>Per area</dt><dd>${esc(d.per_area)}</dd><dt>Coverage</dt><dd>${esc(d.coverage)}</dd></dl>
      <p class="note">Calendars use ${ST.linked ? "one shared colour scale (log steps up to " + fmt(shared) + ")" : "each side's own colour scale"}. Maps use ${ST.linked ? "the same map scale, each centred on its own area" : "each side's own scale"}.</p></details>`;
  }
  function studioChart() {
    const R = ST.res, host = $("st-chart");
    host.innerHTML = "";
    const line = (k) => { const mo = Number(R[k].month.split("-")[1]); return R[k].series.filter((s) => Number(s.month.split("-")[1]) === mo).map((s) => ({ y: Number(s.month.slice(0, 4)), v: s.H, src: s.source, flag: s.flag })); };
    const A = line("a"), B = line("b");
    const ys = [...new Set([...A, ...B].map((p) => p.y))].sort();
    const vals = [...A, ...B].map((p) => p.v).filter((v) => v != null && v > 0);
    const W = Math.max(340, Math.round(host.clientWidth || 900)), H = 250, L = 62, Rm = 16, T = 12, Bm = 30;
    const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Line chart, log scale: harmonised detections in each side's chosen month, by year. The table below has every value." }, host);
    const colors = { a: css("--harm"), b: css("--n20") };
    $("st-legend").innerHTML = ["a", "b"].map((k) => `<span style="color:${colors[k]}"><i class="swatch${k === "b" ? " dashed" : ""}"></i><span style="color:var(--ink2)">${k.toUpperCase()}: ${esc(R[k].region)}, ${esc(MONTH_FULL[Number(R[k].month.split("-")[1]) - 1])} of each year (harmonised, S-NPP-equivalent)</span></span>`).join("");
    if (!vals.length) { svgEl("text", { x: L, y: H / 2 }, svg).textContent = "No harmonised values to draw for these selections."; }
    else {
      const lo = Math.max(0.5, Math.min(...vals) * 0.8), hi = Math.max(...vals) * 1.25;
      const y = (v) => T + (H - T - Bm) * (1 - (Math.log10(Math.max(v, lo)) - Math.log10(lo)) / (Math.log10(hi) - Math.log10(lo)));
      const x = (yr) => L + (W - L - Rm) * ((yr - ys[0]) / Math.max(1, ys[ys.length - 1] - ys[0]));
      for (let e = Math.floor(Math.log10(lo)); e <= Math.ceil(Math.log10(hi)); e++) for (const m of [1, 2, 5]) {
        const v = m * 10 ** e;
        if (v < lo || v > hi) continue;
        svgEl("line", { x1: L, x2: W - Rm, y1: y(v), y2: y(v), stroke: css("--grid"), "stroke-width": m === 1 ? 1 : 0.5 }, svg);
        if (m !== 5 || hi / lo < 50) svgEl("text", { x: L - 6, y: y(v) + 4, "text-anchor": "end" }, svg).textContent = fmt(v);
      }
      svgEl("line", { x1: L, x2: W - Rm, y1: H - Bm, y2: H - Bm, stroke: css("--axis") }, svg);
      const step = Math.max(1, Math.ceil(ys.length / (W < 560 ? 6 : 12)));
      ys.forEach((yr, i) => { if (i % step === 0) svgEl("text", { x: x(yr), y: H - Bm + 17, "text-anchor": "middle" }, svg).textContent = yr; });
      for (const [k, pts] of [["a", A], ["b", B]]) {
        let d = "", pen = false;
        for (const p of pts) { if (p.v == null) { pen = false; continue; } d += `${pen ? "L" : "M"}${x(p.y)},${y(p.v)}`; pen = true; }
        const path = svgEl("path", { d, fill: "none", stroke: colors[k], "stroke-width": 2.4, "stroke-linejoin": "round" }, svg);
        if (k === "b") path.setAttribute("stroke-dasharray", "7 4"); else S.drawIn(path);
        for (const p of pts) if (p.v != null) {
          const m = k === "a" ? svgEl("circle", { cx: x(p.y), cy: y(p.v), r: 3.4, fill: colors[k], stroke: css("--surface"), "stroke-width": 1.3 }, svg)
            : svgEl("rect", { x: x(p.y) - 3, y: y(p.v) - 3, width: 6, height: 6, fill: colors[k], stroke: css("--surface"), "stroke-width": 1.3 }, svg);
          svgEl("title", {}, m).textContent = `${k.toUpperCase()} ${p.y}: ${fmt(p.v)} (${p.src}${p.flag ? "; " + p.flag : ""})`;
        }
      }
    }
    $("st-table").innerHTML = `<table><thead><tr><th scope="col">Year</th><th scope="col">A: ${esc(R.a.region)}</th><th scope="col" style="text-align:left">A source</th><th scope="col">B: ${esc(R.b.region)}</th><th scope="col" style="text-align:left">B source</th></tr></thead><tbody>` +
      ys.map((yr) => { const a = A.find((p) => p.y === yr) || {}, b = B.find((p) => p.y === yr) || {}; return `<tr><th scope="row">${yr}</th><td>${fmt(a.v)}</td><td style="text-align:left">${esc(a.src || "–")}${a.flag ? " *" : ""}</td><td>${fmt(b.v)}</td><td style="text-align:left">${esc(b.src || "–")}${b.flag ? " *" : ""}</td></tr>`; }).join("") +
      `</tbody></table><p class="note">– means no value (missing is not zero). * the month carries a coverage flag.</p>`;
  }
  async function studioPoints(k, id) {
    const p = ST.res[k], [y, m] = p.month.split("-").map(Number), note = $(`st-mapnote-${k}`), box = $(`st-map-${k}`);
    if (ST.maps[k]) { ST.maps[k].destroy(); ST.maps[k] = null; }
    const A = S.areas();
    const eng = window.SeamMap2D.create(box, { colors: window.SeamMap2D.colors(), geo: S.geo(), areas: A.areas, labels: false, padTop: 14, focusable: true,
      label: `Top-down map of pane ${k.toUpperCase()}: ${p.region}, ${p.month_name}. Arrow keys pan, plus and minus zoom.` });
    ST.maps[k] = eng;
    eng.setSelection({ region: p.region, bbox: p.bbox });
    const bounds = p.bbox || (A.areas[p.region] || A.areas.Pakistan).bounds;
    eng.fit(bounds);
    studioLink();
    try {
      const body = { region: p.bbox ? undefined : p.region, bbox: p.bbox || undefined, day_month: [y, m] };
      const res = await (await S.post("/api/points", body)).json();
      if (id !== ST.req || ST.maps[k] !== eng) return;
      res.day = res.minute.map((v) => Math.floor(v / 1440) + 1);
      ST.pts[k] = res;
      eng.setPoints(res);
      const sat = ST.sat[k], pi = SATS.indexOf(sat);
      eng.setFilter({ sats: [pi], dn: "DN", day: 0 });
      const n = res.counts[sat].D + res.counts[sat].N;
      note.textContent = res.record[sat].status === "outside_record" ? `${SAT_INFO[sat].label} has no record in ${p.month_name} (it begins ${res.record[sat].first}). Missing, not zero.`
        : `${fmt(n)} ${SAT_INFO[sat].label} observed detections in ${p.month_name} (day and night). Raw points, not the converted monthly value above.`;
    } catch (e) { if (ST.maps[k] === eng) note.textContent = `The points could not be loaded (${e.message}).`; }
  }
  function studioLink() {      // linked: both maps at the coarser of the two scales, each centred on its own area
    const a = ST.maps.a, b = ST.maps.b;
    if (!ST.linked || !a || !b) return;
    const k = Math.min(a.view().k, b.view().k);
    for (const e of [a, b]) e.setView({ ...e.view(), k });
  }
  function studioPreset(kind) {
    const r = S.result();
    studioDefaults();
    if (kind === "periods") {
      ST.b = { ...ST.a };
      const y = ST.a.month[0] > ST.a.years[0] ? ST.a.month[0] - 1 : ST.a.month[0] + 1;
      ST.b.month = [Math.min(Math.max(y, r.years[0]), r.years[1]), ST.a.month[1]];
    }
    studioShell(); studioRun();
  }
  function studioChange(e) {
    const t = e.target.closest("[data-st]");
    if (!t) { if (e.target.id === "st-linked") { ST.linked = e.target.checked; if (ST.res) { studioRender(); for (const k of ["a", "b"]) studioPoints(k, ST.req); } } return; }
    const [k, f] = t.dataset.st.split(":"), p = ST[k], o = k === "a" ? "b" : "a";
    if (f === "sat") { ST.sat[k] = t.value; if (ST.res) studioPoints(k, ST.req); return; }
    if (f === "area") { if (t.value === "__box") { p.bbox = S.result().request.bbox.map(Number); p.region = null; } else { p.bbox = null; p.region = t.value; } }
    if (f === "month") p.month = [p.month[0], Number(t.value)];
    if (f === "year") p.month = [Number(t.value), p.month[1]];
    if (f === "model") p.model = t.value;
    // Linked, two different areas: the period is shared, so a month or year change copies across.
    if (ST.linked && (f === "month" || f === "year") && (ST.a.region !== ST.b.region || String(ST.a.bbox) !== String(ST.b.bbox))) ST[o].month = p.month.slice();
    studioRun();
  }
  async function studioExport(btn) {
    if (!ST.res || ST.busy) { S.toast("The comparison is still loading. Export again when both panes are up to date.", { error: true }); return; }
    const sel = (p) => ({ region: p.region, bbox: p.bbox || undefined, years: p.years, month: p.month, model: p.model });
    btn.classList.add("is-pending");
    try {
      const r = await S.post("/api/export/compare", { a: sel(ST.a), b: sel(ST.b) });
      const blob = await r.blob();
      const name = ((r.headers.get("Content-Disposition") || "").match(/filename="?([^";]+)"?/) || [])[1] || "seamline_comparison.zip";
      if (!blob.size) throw new Error("the server returned an empty file");
      S.save(blob, name);
      S.toast(`Saved ${name}: both selections, their metrics, definitions and provenance.`);
    } catch (e) { S.toast(`The export failed: ${e.message}`, { error: true }); }
    finally { btn.classList.remove("is-pending"); }
  }
  function studioOpen() {
    if (!S.result()) return;
    if (!ST.a || ST.err) { ST.built = false; studioDefaults(); }
    if (!ST.res || ST.err) studioRun(); else { studioRender(); for (const k of ["a", "b"]) studioPoints(k, ST.req); }
  }

  // =========================================================================================================
  // 3. Satellite Handover Simulator: a historical sensor-withholding replay of the saved 2026 bridge test
  // =========================================================================================================
  const RP = { data: null, i: 0, reveal: false, raw: true, timer: null, loading: false };
  async function replayLoad() {
    if (RP.data || RP.loading) { if (RP.data) replayDraw(); return; }
    RP.loading = true;
    $("replay-body").innerHTML = `<div class="skeleton" aria-hidden="true"></div><p class="note">Loading the saved test…</p>`;
    try {
      const r = await fetch("/api/handover").then((x) => x.json());
      RP.loading = false;
      if (!r.available) { $("replay-body").innerHTML = `<p class="warnbox"><b>Replay unavailable.</b> ${esc(r.reason || "")}</p>`; return; }
      RP.data = r; RP.i = r.days.length - 1;
      replayShell(); replayDraw();
    } catch (e) {
      RP.loading = false;
      $("replay-body").innerHTML = `<p class="msg error">The saved test could not be loaded (${esc(e.message)}). <button type="button" class="btn" id="rp-retry">Try again</button></p>`;
    }
  }
  function replayShell() {
    const d = RP.data, s = d.saved;
    $("replay-body").innerHTML = `<p class="lede">What if S-NPP's feed had been cut off earlier? This replays the saved 2026 test day by day: S-NPP is withheld, the record continues on converted NOAA-20, and the withheld S-NPP counts can then be shown beside it.</p>
      <dl class="facts facts-2"><dt>Simulation</dt><dd>${esc(d.simulation)}</dd><dt>Actual platform status</dt><dd>${esc(d.platform_status || "")}</dd>
        <dt>Test dates</dt><dd>${esc(d.test_window[0])} to ${esc(d.test_window[1])}, ${esc(d.area)} only</dd><dt>Calibration dates</dt><dd>${esc(d.calibration_window)}</dd></dl>
      <div class="replay-grid"><div>
        <div class="replay-ctrl"><button type="button" class="btn-primary" id="rp-play" aria-pressed="false">Play</button>
          <input type="range" id="rp-range" min="0" max="${d.days.length - 1}" step="1" value="${RP.i}" aria-label="Replay date">
          <button type="button" class="btn" id="rp-reset">Reset</button></div>
        <div class="replay-ctrl"><label class="inline"><input type="checkbox" id="rp-reveal"> Reveal the withheld S-NPP reference</label>
          <label class="inline"><input type="checkbox" id="rp-raw" checked> Show NOAA-20 as counted (no conversion)</label></div>
        <div class="legend" id="rp-legend"></div><div class="chart" id="rp-chart"></div>
        <p class="note">${esc(d.units)}. Hatched days were left out by the frozen test's own matched-day rule (no usable count for one of the satellites): they are gaps, not zeros, and no line is drawn across them. ${esc(d.not)}</p>
      </div><div class="replay-read" id="rp-read" aria-live="polite"></div></div>
      <details><summary>Months of the test as a table</summary><div class="table-wrap" id="rp-table"></div></details>
      <p class="note">${esc(d.area_scope)} Saved result: ${esc(s.file)} (run ${esc(String(s.run_utc).slice(0, 16).replace("T", " "))} UTC, protocol SHA-256 ${esc(String(s.protocol_sha256).slice(0, 12))}…). Pass mark: ${esc(s.pass_mark)}. Replay built ${esc(String(d.built_utc).slice(0, 16).replace("T", " "))} UTC from ${d.raw_files} hash-checked 2026 files; nothing was refitted.</p>`;
  }
  function replayStats(upto) {
    // Whole scored months that have fully passed at the playhead; the saved test's metric on those months.
    const d = RP.data, date = d.days[upto].date, done = d.months.filter((m) => m.scored && d.days.filter((x) => x.month === m.month).slice(-1)[0].date <= date);
    const obs = done.reduce((a, m) => a + m.observed_snpp, 0);
    return { done, wape: obs ? done.reduce((a, m) => a + Math.abs(m.converted - m.observed_snpp), 0) / obs : null, m0: obs ? done.reduce((a, m) => a + Math.abs(m.noaa20_raw - m.observed_snpp), 0) / obs : null };
  }
  function replayDraw() {
    const d = RP.data;
    if (!d || !$("rp-chart")) return;
    const host = $("rp-chart");
    host.innerHTML = "";
    const n = d.days.length, W = Math.max(340, Math.round(host.clientWidth || 820)), H = 270, L = 54, R = 12, T = 14, B = 40;
    const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `Replay chart for ${d.area}, January to October 2026: converted NOAA-20 day by day up to the replay date${RP.reveal ? ", with the withheld S-NPP reference shown" : "; the S-NPP reference is hidden"}. The table below lists the months.` }, host);
    const c = { conv: css("--n20"), ref: css("--snpp"), raw: css("--muted") };
    const max = Math.max(1, ...d.days.map((x) => Math.max(x.snpp || 0, x.noaa20 || 0, x.converted || 0)));
    const x = (i) => L + (W - L - R) * (i / (n - 1)), y = (v) => T + (H - T - B) * (1 - Math.sqrt(v / max));
    const defs = svgEl("defs", {}, svg), pat = svgEl("pattern", { id: "rp-hatch", width: 5, height: 5, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, defs);
    svgEl("rect", { width: 5, height: 5, fill: css("--nodata") }, pat);
    svgEl("line", { x1: 0, y1: 0, x2: 0, y2: 5, stroke: css("--muted"), "stroke-width": 1 }, pat);
    for (const v of [0, 25, 100, 250, 500, 1000].filter((t) => t <= max)) {
      svgEl("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), stroke: css("--grid") }, svg);
      svgEl("text", { x: L - 6, y: y(v) + 4, "text-anchor": "end" }, svg).textContent = fmt(v);
    }
    // gaps: runs of days the test left out
    let run = null;
    d.days.forEach((dd, i) => {
      if (!dd.matched && run == null) run = i;
      if ((dd.matched || i === n - 1) && run != null) {
        const end = dd.matched ? i - 1 : i, g = svgEl("rect", { x: x(run) - (W - L - R) / n / 2, y: T, width: Math.max(1.5, x(end) - x(run) + (W - L - R) / n), height: H - T - B, fill: "url(#rp-hatch)", opacity: 0.8 }, svg);
        svgEl("title", {}, g).textContent = `${d.days[run].date}${end > run ? " to " + d.days[end].date : ""}: left out by the test (${d.days[run].why_not})`;
        run = null;
      }
    });
    // month ticks
    d.months.forEach((m) => {
      const i0 = d.days.findIndex((dd) => dd.month === m.month), i1 = n - 1 - [...d.days].reverse().findIndex((dd) => dd.month === m.month);
      svgEl("line", { x1: x(i0), x2: x(i0), y1: H - B, y2: H - B + 5, stroke: css("--axis") }, svg);
      svgEl("text", { x: (x(i0) + x(i1)) / 2, y: H - B + 17, "text-anchor": "middle" }, svg).textContent = MONTHS[Number(m.month.slice(5)) - 1];
      if (W > 620 || !m.scored) svgEl("text", { x: (x(i0) + x(i1)) / 2, y: H - B + 31, "text-anchor": "middle", style: `font:10.5px ${css("--font")};fill:${css("--muted")}` }, svg).textContent = m.scored ? (m.stream === "SP" ? "standard" : "near-real-time") : "not scored";
    });
    svgEl("line", { x1: L, x2: W - R, y1: H - B, y2: H - B, stroke: css("--axis") }, svg);
    const line = (key, color, width, dash, upto) => {
      let p = "", pen = false;
      for (let i = 0; i <= upto; i++) { const v = d.days[i][key]; if (v == null) { pen = false; continue; } p += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`; pen = true; }
      const el2 = svgEl("path", { d: p, fill: "none", stroke: color, "stroke-width": width, "stroke-linejoin": "round" }, svg);
      if (dash) el2.setAttribute("stroke-dasharray", dash);
    };
    if (RP.raw) line("noaa20", c.raw, 1.2, "3 3", RP.i);
    if (RP.reveal) line("snpp", c.ref, 2, "", RP.i);
    line("converted", c.conv, 2.4, "", RP.i);
    svgEl("line", { x1: x(RP.i), x2: x(RP.i), y1: T, y2: H - B, stroke: css("--ink"), "stroke-width": 1.5 }, svg);
    if (!RP.reveal) svgEl("text", { x: W - R - 4, y: T + 12, "text-anchor": "end", style: `font:600 12px ${css("--font")};fill:${css("--muted")}` }, svg).textContent = "S-NPP withheld in this replay";
    svgEl("text", { x: 12, y: T + (H - T - B) / 2, "text-anchor": "middle", transform: `rotate(-90 12 ${T + (H - T - B) / 2})` }, svg).textContent = "Detections per day (square-root scale)";
    $("rp-legend").innerHTML = `<span style="color:${c.conv}"><i class="swatch"></i><span style="color:var(--ink2)">NOAA-20 converted with the saved bridge (the continued record)</span></span>` +
      (RP.raw ? `<span style="color:${c.raw}"><i class="swatch dashed thin"></i><span style="color:var(--ink2)">NOAA-20 as counted</span></span>` : "") +
      (RP.reveal ? `<span style="color:${c.ref}"><i class="swatch"></i><span style="color:var(--ink2)">S-NPP observed (the withheld reference)</span></span>` : "") +
      `<span><i class="rel-key rel-gap" style="background:repeating-linear-gradient(45deg,var(--muted) 0 1px,var(--nodata) 1px 5px)"></i>left out by the test: a gap, not zero</span>`;
    // readout
    const dd = d.days[RP.i], st = replayStats(RP.i), end = RP.i === n - 1, s = d.saved;
    const day = dd.matched ? `<div class="kv"><span>Converted NOAA-20</span><b>${fmt(dd.converted, 1)}</b></div><div class="kv"><span>NOAA-20 as counted</span><b>${fmt(dd.noaa20)}</b></div><div class="kv"><span>S-NPP (reference)</span><b>${RP.reveal ? fmt(dd.snpp) : "withheld"}</b></div>`
      : `<p class="warnbox">This day was left out by the test: ${esc(dd.why_not)}. No count is shown for it.</p>`;
    let err;
    if (!RP.reveal) err = `<p class="note">Reveal the reference to see how far the converted record was from S-NPP.</p>`;
    else if (!st.done.length) err = `<p class="note">No whole scored month has passed yet at this date.</p>`;
    else err = `<p class="eyebrow" style="margin-top:12px">Total error so far, ${st.done.length} whole month${st.done.length === 1 ? "" : "s"}, ${esc(d.area)}</p><div class="big">${pct(st.wape)}</div>
      <div class="kv"><span>With no conversion</span><b>${pct(st.m0)}</b></div>
      <p class="note">Error against S-NPP, the reference satellite (WAPE). It is not accuracy against the ground, and ${pct(st.wape)} error does not mean ${fmt(100 - st.wape * 100, 1)}% of burning was detected.</p>` +
      (end ? `<p><span class="badge badge-${s.status === "pass" ? "pass" : s.status === "fail" ? "fail" : "untested"}">${s.status === "pass" ? "Passed its frozen test" : s.status === "fail" ? "Failed its frozen test" : "Not testable"}</span> in ${esc(d.area)}.</p>
        <p class="note">Saved test: ${pct(s.wape)} (no conversion ${pct(s.m0_wape)}), ${s.scored_months} scored months. Replay: ${pct(d.replay.wape)} and ${pct(d.replay.m0_wape)}. ${d.reproduction.reproduced ? `Reproduced: the largest monthly difference is ${d.reproduction.largest_converted_diff.toExponential(1)} detections (tolerance ${d.reproduction.tolerance.converted_monthly_detections}).` : "<b>The replay does not reproduce the saved result; treat the saved file as the record.</b>"}</p>
        <p class="note">Not scored: ${s.months_not_scored.map((m) => `${esc(m.month)} (${esc(m.reason)})`).join("; ") || "none"}. Reported, not tested: ${Object.entries(s.reported).map(([a, r]) => `${esc(a)} ${pct(r.wape)}`).join("; ")}.</p>` : "");
    $("rp-read").innerHTML = `<p class="eyebrow">Replay date</p><div class="big" style="font-size:24px">${esc(dd.date)}</div><p class="note">UTC day · ${dd.stream === "SP" ? "standard" : "near-real-time"} files · historical</p>${day}${err}`;
    $("rp-table").innerHTML = `<table><thead><tr><th scope="col">Month</th><th scope="col">Files</th><th scope="col">Matched days</th><th scope="col">S-NPP observed</th><th scope="col">NOAA-20 converted</th><th scope="col">Error</th><th scope="col">NOAA-20 as counted</th><th scope="col">Error</th></tr></thead><tbody>` +
      d.months.map((m) => `<tr><th scope="row">${m.month}</th><td>${m.stream === "SP" ? "standard" : "near-real-time"}</td><td>${m.matched_days} of ${m.days_in_month}</td>` +
        (m.scored ? `<td>${RP.reveal ? fmt(m.observed_snpp) : "withheld"}</td><td>${fmt(m.converted, 1)}</td><td>${RP.reveal ? (m.error > 0 ? "+" : "") + pct(m.error) : "withheld"}</td><td>${fmt(m.noaa20_raw)}</td><td>${RP.reveal ? (m.raw_error > 0 ? "+" : "") + pct(m.raw_error) : "withheld"}</td>` : `<td colspan="5" style="text-align:left">not scored: fewer than 20 matched days</td>`) + `</tr>`).join("") + `</tbody></table>`;
    $("rp-range").value = String(RP.i);
  }
  function replayStop() {
    if (!RP.timer) return;
    clearInterval(RP.timer); RP.timer = null;
    const b = $("rp-play");
    if (b) { b.textContent = "Play"; b.setAttribute("aria-pressed", "false"); }
  }
  function replayPlay() {
    const d = RP.data, mode = S.motionMode();
    if (!d) return;
    if (mode === "off") { RP.i = d.days.length - 1; replayDraw(); S.toast("Motion is off, so the replay jumped to its last day.", { second: true }); return; }
    if (RP.i >= d.days.length - 1) RP.i = 0;
    $("rp-play").textContent = "Pause"; $("rp-play").setAttribute("aria-pressed", "true");
    const stepBy = mode === "reduced" ? 30 : 2;      // Reduced: month-sized steps; Full: a smooth sweep of about 12 seconds
    RP.timer = setInterval(() => {
      RP.i = Math.min(d.days.length - 1, RP.i + stepBy);
      replayDraw();
      if (RP.i >= d.days.length - 1) replayStop();
    }, mode === "reduced" ? 700 : 80);
  }

  // ---------- wiring ----------
  document.addEventListener("click", (e) => {
    const t = e.target.closest ? e.target : null;
    if (!t) return;
    if (t.closest("#explainer-btn")) { openExplainer(t.closest("#explainer-btn")); return; }
    if (t.closest("#compare-open")) { S.go("calendar", { sub: "compare" }); return; }
    const preset = t.closest("[data-st-preset]");
    if (preset) { studioPreset(preset.dataset.stPreset); return; }
    if (t.closest("#st-export")) { studioExport(t.closest("#st-export")); return; }
    if (t.closest("#st-retry")) { studioRun(); return; }
    if (t.closest("#rp-retry")) { replayLoad(); return; }
    if (t.closest("#rp-play")) { RP.timer ? replayStop() : replayPlay(); return; }
    if (t.closest("#rp-reset")) { replayStop(); RP.i = RP.data.days.length - 1; RP.reveal = false; $("rp-reveal").checked = false; replayDraw(); }
  });
  document.addEventListener("change", (e) => {
    if (e.target.closest && e.target.closest("#studio")) studioChange(e);
    if (e.target.id === "rp-reveal") { RP.reveal = e.target.checked; replayDraw(); }
    if (e.target.id === "rp-raw") { RP.raw = e.target.checked; replayDraw(); }
  });
  document.addEventListener("input", (e) => { if (e.target.id === "rp-range") { replayStop(); RP.i = Number(e.target.value); replayDraw(); } });
  S.on("sub", (k) => { if (k === "compare" && S.UI.ws === "calendar") studioOpen(); });
  S.on("ev", (k) => { if (k === "replay") replayLoad(); else replayStop(); });
  S.on("ws", (w) => {
    if (w !== "evidence") replayStop();
    if (w === "calendar" && S.UI.sub === "compare") studioOpen();
    if (w === "evidence" && S.UI.ev === "replay") replayLoad();
  });
  S.on("selection", () => {      // a new main selection resets the studio to it, the next time the studio is opened
    ST.a = null; ST.res = null; ST.built = false;
    if (S.UI.ws === "calendar" && S.UI.sub === "compare") studioOpen();
  });
  S.on("theme", () => { if (ST.res && S.UI.sub === "compare") { studioRender(); for (const k of ["a", "b"]) if (ST.maps[k]) ST.maps[k].setTheme(window.SeamMap2D.colors()); } if (RP.data) replayDraw(); });
  let rz = 0;
  window.addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(() => { if (RP.data && S.UI.ev === "replay") replayDraw(); if (ST.res && S.UI.sub === "compare" && S.UI.ws === "calendar") { studioChart(); } }, 180); });
  document.addEventListener("visibilitychange", () => { if (document.hidden) replayStop(); });
  window.SeamFeatures = { studio: ST, replay: RP };
  // If the page opened straight on one of these views, load it now.
  if (S.UI.ws === "evidence" && S.UI.ev === "replay") replayLoad();
  if (S.result() && S.UI.ws === "calendar" && S.UI.sub === "compare") studioOpen();
})();
