// Seamline layers: "Was this area actually observed?" (the coverage example) and the Experimental outlook.
// Both read saved results only (GET /api/coverage, GET /api/outlook). When a result is missing or its release rule
// did not pass, the page says exactly that; nothing is estimated or filled in here.
(function () {
  "use strict";
  if (typeof window === "undefined" || !window.Seam) return;
  const S = window.Seam, $ = (id) => document.getElementById(id);
  const { fmt, esc, css, MONTH_FULL } = S;
  const NS = "http://www.w3.org/2000/svg";
  const svgEl = (tag, attrs, parent) => { const n = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, v); if (parent) parent.appendChild(n); return n; };
  const pct = (v, d = 1) => (v == null ? "–" : fmt(v * 100, d) + "%");
  const longDate = (iso) => { const [y, m, d] = iso.split("-").map(Number); return `${d} ${MONTH_FULL[m - 1]} ${y}`; };

  // =========================================================================================================
  // Coverage: the product's own class for each 1 km cell on one UTC day
  // =========================================================================================================
  const CV = { info: null, on: false, day: null, grid: null, req: 0, loading: false };
  const COV_VAR = { fire: "--cov-fire", clear: "--cov-clear", cloud: "--cov-cloud", unknown: "--cov-unknown", water: "--cov-water" };
  function rgb(token) {
    const probe = document.createElement("span");
    probe.style.color = css(token); document.body.appendChild(probe);
    const m = getComputedStyle(probe).color.match(/[\d.]+/g).map(Number);
    probe.remove();
    return m;
  }
  async function covLoad() {
    if (CV.info || CV.loading) return;
    CV.loading = true;
    try { CV.info = await fetch("/api/coverage").then((r) => r.json()); }
    catch (e) { CV.info = { available: false, reason: `The coverage example could not be read (${e.message}).` }; }
    CV.loading = false;
    if (CV.info.available && !CV.day) CV.day = (CV.info.days.find((d) => d.date === "2025-11-06") || CV.info.days[0]).date;
    covUi(); covDetail();
  }
  const covDay = () => CV.info.days.find((d) => d.date === CV.day);
  function covUi() {
    const box = $("coverage-ui"), I = CV.info;
    if (!box || !I) return;
    if (!I.available) {
      const last = I.last_attempt ? `<details><summary>Last acquisition attempt (${esc(I.last_attempt.at_utc)})</summary><ul class="note">${I.last_attempt.routes.map((r) =>
        `<li><b>${esc(r.product)}</b>: ${esc(r.error || r.note || `HTTP ${r.final_status}, ${r.is_hdf ? "data file returned" : "no data file returned"}`)}</li>`).join("")}</ul></details>` : "";
      box.innerHTML = `<p class="warnbox"><b>Coverage layer unavailable.</b> ${esc(I.reason)}</p><p class="note">An empty map is not evidence of clear sky. To build the example: <code>${esc(I.how || "")}</code></p>${last}`;
      return;
    }
    const d = covDay(), ver = I.verification;
    const rows = I.classes.map((c) => {
      const n = d.counts[c.key], share = c.key === "water" ? "not land" : pct(n / d.land_cells);
      return `<span><i class="cov-sw cov-${c.key}"></i>${esc(c.label)}<b>${share}</b></span>`;
    }).join("");
    box.innerHTML = `<p class="note">A real example, not a full layer: <b>${esc(I.product.platform)} ${esc(I.product.instrument)}</b>, ${I.days.length} days, ${esc(I.area)}.</p>
      <label class="inline"><input type="checkbox" id="cov-on"${CV.on ? " checked" : ""}> Show the classes on the map</label>
      <label>Day (UTC) <select id="cov-day">${I.days.map((x) => `<option value="${x.date}"${x.date === CV.day ? " selected" : ""}>${esc(longDate(x.date))}</option>`).join("")}</select></label>
      <div class="cov-legend" aria-live="polite">${rows}</div>
      <p class="note">Shares of ${fmt(d.land_cells)} land cells (1 km) on ${esc(longDate(d.date))}: ${fmt(d.counts.fire)} hotspot cells, ${fmt(d.counts.cloud)} cloud, ${fmt(d.counts.unknown)} unknown. ${esc(I.time_support)}</p>
      <div class="btn-row"><button type="button" class="btn" id="cov-fit">Zoom to the example area</button><button type="button" class="btn" id="cov-points">Show Aqua's detections for this day</button></div>
      <details><summary>What this shows, and what it cannot</summary><ul class="note">${I.notes.map((n) => `<li>${esc(n)}</li>`).join("")}<li>${esc(I.denominator)}</li><li>${esc(I.level2_route)}</li></ul>
        <p class="note"><b>${I.verified ? "Checked" : "Not verified"}:</b> ${ver ? `${fmt(ver.on_or_next_to_a_hotspot_cell)} of ${fmt(ver.detections)} FIRMS Aqua detections on these days fall on or next to a hotspot cell (${pct(ver.share, 0)}); every day's classes sum to its land cells: ${ver.all_days_sum_to_land ? "yes" : "no"}; land/water state agrees with the classes: ${ver.qa_state_matches_classes ? "yes" : "no"}.` : "no check has been run."}</p>
        <p class="note">Source: ${esc(I.product.long_name)}, ${esc(I.product.provider)}, DOI ${esc(I.product.doi)}; tile ${esc(I.tile)}. Files: ${I.files.map((f) => `${esc(f.granule)} (SHA-256 ${esc(f.sha256.slice(0, 12))}…, retrieved ${esc(String(f.retrieved_utc).slice(0, 16).replace("T", " "))} UTC)`).join("; ")}. Manifest: ${esc(I.manifest)}.</p></details>`;
  }
  function covDetail() {
    const box = $("cov-detail"), I = CV.info;
    if (!box || !I) return;
    if (!I.available) { box.innerHTML = `<p class="warnbox"><b>Coverage detail unavailable.</b> ${esc(I.reason)}</p>`; return; }
    const by = {};
    for (const r of (I.verification && I.verification.rows) || []) by[r.date] = r;
    box.innerHTML = `<p class="note">${esc(I.product.platform)} ${esc(I.product.instrument)} only, ${esc(I.area)}. ${esc(I.time_support)} ${esc(I.denominator)}</p>
      <div class="table-wrap"><table><thead><tr><th scope="col">Day (UTC)</th><th scope="col">Land cells</th><th scope="col">Hotspot cells</th><th scope="col">Usable land, no hotspot</th><th scope="col">Cloud-obscured</th><th scope="col">Unknown</th><th scope="col">FIRMS Aqua detections on or next to a hotspot cell</th><th scope="col"></th></tr></thead><tbody>` +
      I.days.map((d) => `<tr><th scope="row">${esc(longDate(d.date))}</th><td>${fmt(d.land_cells)}</td><td>${fmt(d.counts.fire)}</td><td>${pct(d.counts.clear / d.land_cells)}</td><td>${pct(d.cloud_share)}</td><td>${pct(d.unknown_share)}</td><td>${by[d.date] ? `${fmt(by[d.date].on_or_next_to_a_hotspot_cell)} of ${fmt(by[d.date].firms_aqua_detections_in_area)}` : "–"}</td><td><button type="button" class="btn" data-cov-open="${d.date}">Show on the map</button></td></tr>`).join("") +
      `</tbody></table></div><p class="note">"Usable land, no hotspot" is the instrument's class for that day. It is not proof that nothing burned, and these shares are never used to scale detection counts.</p>`;
  }
  async function covDraw() {
    const eng = window.SeamMap && window.SeamMap.engine();
    if (!eng || !CV.info || !CV.info.available) return;
    if (!CV.on) { eng.setOverlay(null); return; }
    const id = ++CV.req;
    try {
      if (!CV.grid || CV.grid.date !== CV.day) {
        const g = await fetch(`/api/coverage/${CV.day}`).then((r) => r.json());
        if (id !== CV.req) return;
        if (!g.available) { S.toast(g.reason, { error: true }); return; }
        CV.grid = g;
      }
      const g = CV.grid, bin = atob(g.data_base64), cv = document.createElement("canvas");
      cv.width = g.width; cv.height = g.height;
      const ctx = cv.getContext("2d"), img = ctx.createImageData(g.width, g.height);
      const col = g.classes.map((k) => rgb(COV_VAR[k]));
      for (let i = 0; i < bin.length; i++) {
        const c = bin.charCodeAt(i);
        if (!c) continue;                                       // outside the area: transparent
        const [r, gg, b] = col[c - 1], x = i % g.width, y = (i / g.width) | 0;
        const hatch = g.classes[c - 1] === "unknown" && (x + y) % 3 === 0;   // unknown is also hatched, not colour alone
        img.data[i * 4] = hatch ? 20 : r; img.data[i * 4 + 1] = hatch ? 24 : gg; img.data[i * 4 + 2] = hatch ? 26 : b; img.data[i * 4 + 3] = 255;
      }
      ctx.putImageData(img, 0, 0);
      eng.setOverlay(cv.toDataURL("image/png"), g.bbox_wsen, 0.82);
    } catch (e) { S.toast(`The coverage picture could not be drawn (${e.message}).`, { error: true }); }
  }
  function covOpenDay(day) {
    const [y, m, d] = day.split("-").map(Number);
    CV.day = day; CV.on = true;
    S.UI.sats = ["Aqua"]; S.UI.dn = "DN";
    S.go("explore");
    if (S.dayMonth()[0] !== y || S.dayMonth()[1] !== m) S.setDayMonth(y, m);
    S.UI.mapDay = d;
    S.emit("filters");
    covUi(); covDraw();
    const eng = window.SeamMap.engine();
    if (eng) eng.fit(CV.info.bbox_wsen, true);
    S.syncUrl();
  }

  // =========================================================================================================
  // Experimental outlook: the saved evaluation and release rule of Protocol O01
  // =========================================================================================================
  const OL = { data: null, loading: false, pick: null };
  async function outlookLoad() {
    if (OL.data) { outlookDraw(); return; }
    if (OL.loading) return;
    OL.loading = true;
    $("outlook-body").innerHTML = `<div class="skeleton" aria-hidden="true"></div><p class="note">Loading the saved evaluation…</p>`;
    try { OL.data = await fetch("/api/outlook").then((r) => r.json()); }
    catch (e) { OL.loading = false; $("outlook-body").innerHTML = `<p class="msg error">The saved evaluation could not be read (${esc(e.message)}). <button type="button" class="btn" id="ol-retry">Try again</button></p>`; return; }
    OL.loading = false;
    outlookDraw();
  }
  const mark = (ok) => `<span class="badge ${ok ? "badge-pass" : "badge-fail"}"><svg class="ic"><use href="#i-${ok ? "check" : "cross"}"/></svg>${ok ? "Met" : "Not met"}</span>`;
  function outlookDraw() {
    const D = OL.data, box = $("outlook-body");
    if (!D || !box) return;
    const head = `<div class="outlook-banner"><p><span class="badge badge-exp">Experimental</span> <b>${esc(D.reason || "")}</b></p><p class="note">${esc(D.not)}</p></div>`;
    if (!D.available) { box.innerHTML = head + `<dl class="facts"><dt>Target</dt><dd>${esc(D.target)}</dd><dt>Area and satellite</dt><dd>${esc(D.area)}, ${esc(D.satellite)}</dd><dt>Protocol</dt><dd>${esc(D.protocol)}</dd></dl>`; return; }
    const h = D.holdout, v = D.validation, m = h.scores[h.carried_forward], iv = m.interval, dir = m.direction;
    if (!OL.pick) OL.pick = h.rows[h.rows.length - 1].origin;
    const order = ["B0", "B1", "B2", "M1", "M2"];
    const table = `<div class="table-wrap"><table><thead><tr><th scope="col">Held-out year ${h.held_out_year}, ${h.test_origins} weekly origins</th><th scope="col">Error of ln(count)</th><th scope="col">Typical miss</th><th scope="col">Count error (WAPE)</th><th scope="col">Oct–Nov</th><th scope="col">Apr–May</th><th scope="col">Other months</th></tr></thead><tbody>` +
      order.map((k) => { const s = h.scores[k], se = (x) => (s.by_season[x] ? `${pct(s.by_season[x].wape, 0)} (${s.by_season[x].n})` : "–");
        return `<tr><th scope="row">${esc(h.names[k])}${k === h.carried_forward ? " · carried forward" : ""}${k.startsWith("B") ? " · benchmark" : " · ML candidate"}</th><td>${fmt(s.mae_z, 3)}</td><td>×${fmt(s.typical_factor, 2)}</td><td>${pct(s.wape, 0)}</td><td>${se("OctNov")}</td><td>${se("AprMay")}</td><td>${se("other")}</td></tr>`; }).join("") +
      `</tbody></table></div><p class="note">Errors against NOAA-20's own later counts. A percentage error is an error, not an accuracy. Season columns: count error and (number of weeks). ${h.ineligible_test_origins} weeks of ${h.held_out_year} were left out because a day in them had no usable data.</p>`;
    box.innerHTML = head + `
      <dl class="facts facts-2"><dt>Target</dt><dd>${esc(D.target)}</dd><dt>Area and satellite</dt><dd>${esc(D.area)} only; ${esc(D.satellite)} alone, no conversion</dd>
        <dt>Change band</dt><dd>${esc(D.threshold)}</dd><dt>Input cutoff</dt><dd>Archive (standard processing) to ${esc(h.last_input_day)}</dd>
        <dt>Model version</dt><dd>${esc(h.names[h.carried_forward])}, Protocol O01, trained on weeks ending by 31 Dec 2024</dd><dt>Tested on</dt><dd>${h.test_origins} weeks of ${h.held_out_year}, read once; choices made on ${v.years[0]}–${v.years[v.years.length - 1]} (${v.pooled_validation_origins} weeks)</dd></dl>
      <h3>Release rule</h3>
      <div class="table-wrap"><table><tbody>${D.rules.map((r) => `<tr><th scope="row" style="white-space:normal">${esc(r.rule)}</th><td style="text-align:left;white-space:normal">${esc(r.value)}</td><td>${mark(r.passed)}</td></tr>`).join("")}</tbody></table></div>
      <p class="note">All rules must be met before any outlook is shown. They were written down before the models were fitted (${esc(D.protocol)}).</p>
      <h3>What was measured</h3>${table}
      <p>80% interval: it held the observed count in <b>${pct(iv.coverage, 0)}</b> of the held-out weeks; its ends differ by a factor of <b>${fmt(iv.width_ratio, 1)}</b>. Direction: issued on <b>${dir.issued}</b> of ${h.test_origins} weeks (${dir.issued_increase} increase, ${dir.issued_decrease} decrease), right on ${dir.right_when_issued}; no direction on ${dir.abstained}. No direction is an abstention, not a finding that nothing changed.</p>
      <h3>Hindcast, week by week (${h.held_out_year})</h3>
      <div class="replay-ctrl"><label>Issued after <select id="ol-pick">${h.rows.map((r) => `<option value="${r.origin}"${r.origin === OL.pick ? " selected" : ""}>${esc(longDate(r.origin))}</option>`).join("")}</select></label><span class="note">Past weeks only. Each prediction used data up to its own issue day.</span></div>
      <div class="legend" id="ol-legend"></div><div class="chart" id="ol-chart"></div><div class="cal-detail" id="ol-read" aria-live="polite"></div>
      <details><summary>Show the weeks as a table</summary><div class="table-wrap" id="ol-table"></div></details>
      <details><summary>Validation, data audit, limits and files</summary>
        <p class="note">Validation ${v.years.join(", ")} (mean error of ln(count)): ${Object.entries(v.mean_mae_z).map(([k, x]) => `${esc(k)} ${fmt(x, 3)}`).join("; ")}. Chosen by the lowest of these: ${esc(v.chosen.carried_forward)}.</p>
        ${D.audit ? `<p class="note">Series: ${fmt(D.audit.days)} days, ${fmt(D.audit.complete_days)} complete, ${fmt(D.audit.days_without_a_value)} with no value (never counted as zero). ${D.audit.eligible_origins} of ${D.audit.origins} weekly origins were eligible. ${esc(D.audit.vintage)}</p>` : ""}
        <p class="note">${esc(h.note)} One area, one satellite, one horizon. Cloud, smoke and overpass timing change what is detected without any change in burning. Files: ${D.files.map(esc).join(", ")}.</p></details>`;
    outlookChart();
  }
  function outlookChart() {
    const h = OL.data.holdout, host = $("ol-chart");
    if (!host) return;
    host.innerHTML = "";
    const rows = h.rows, n = rows.length, W = Math.max(340, Math.round(host.clientWidth || 900)), H = 290, L = 58, R = 14, T = 14, B = 34;
    const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `Hindcast chart for ${h.held_out_year}: each week's observed seven-day count of NOAA-20 detections in Punjab as a solid line, and the count predicted one week earlier as hollow diamonds with an 80% interval. The table below lists every week.` }, host);
    const max = Math.max(...rows.map((r) => Math.max(r.y_next, r.hi80, r.predicted)));
    const t0 = Date.parse(`${h.held_out_year}-01-01`), t1 = Date.parse(`${h.held_out_year}-12-31`);
    const x = (iso) => L + (W - L - R) * ((Date.parse(iso) - t0) / (t1 - t0)), y = (val) => T + (H - T - B) * (1 - Math.sqrt(Math.max(0, val) / max));
    const c = { obs: css("--harm"), pred: css("--n21"), band: css("--band") };
    for (const val of [0, 100, 500, 1000, 2500, 5000, 10000].filter((t) => t <= max)) {
      svgEl("line", { x1: L, x2: W - R, y1: y(val), y2: y(val), stroke: css("--grid") }, svg);
      svgEl("text", { x: L - 6, y: y(val) + 4, "text-anchor": "end" }, svg).textContent = fmt(val);
    }
    for (let mo = 0; mo < 12; mo++) {
      const iso = `${h.held_out_year}-${String(mo + 1).padStart(2, "0")}-01`;
      svgEl("line", { x1: x(iso), x2: x(iso), y1: H - B, y2: H - B + 5, stroke: css("--axis") }, svg);
      if (W > 560 || mo % 2 === 0) svgEl("text", { x: x(iso) + 4, y: H - B + 18 }, svg).textContent = S.MONTHS[mo];
    }
    svgEl("line", { x1: L, x2: W - R, y1: H - B, y2: H - B, stroke: css("--axis") }, svg);
    const pick = rows.find((r) => r.origin === OL.pick) || rows[n - 1];
    // the selected week: its issue boundary and target week
    svgEl("rect", { x: x(pick.target_start), y: T, width: Math.max(3, x(pick.target_end) - x(pick.target_start)), height: H - T - B, fill: css("--era") }, svg);
    svgEl("line", { x1: x(pick.origin), x2: x(pick.origin), y1: T, y2: H - B, stroke: css("--ink"), "stroke-width": 1.5, "stroke-dasharray": "4 3" }, svg);
    svgEl("text", { x: Math.min(W - R - 4, x(pick.origin) + 6), y: T + 12, "text-anchor": x(pick.origin) > W - 170 ? "end" : "start", style: `font:600 12px ${css("--font").replace(/"/g, "'")};fill:${css("--ink")}` }, svg).textContent = "issued here";
    // observed: solid line through the middle of each target week, broken where weeks are missing
    let d = "", prev = null;
    for (const r of rows) {
      const gap = prev && (Date.parse(r.origin) - Date.parse(prev.origin)) / 864e5 > 7.5;
      d += `${prev && !gap ? "L" : "M"}${x(r.target_start) + 3},${y(r.y_next)}`;
      prev = r;
    }
    svgEl("path", { d, fill: "none", stroke: c.obs, "stroke-width": 2.2, "stroke-linejoin": "round" }, svg);
    for (const r of rows) {
      const px = x(r.target_start) + 3;
      svgEl("line", { x1: px, x2: px, y1: y(r.hi80), y2: y(r.lo80), stroke: c.pred, "stroke-width": 1.4, opacity: 0.55 }, svg);
      const p = svgEl("path", { d: `M${px},${y(r.predicted) - 4.6}l4.6,4.6l-4.6,4.6l-4.6,-4.6z`, fill: css("--surface"), stroke: c.pred, "stroke-width": 1.8 }, svg);
      svgEl("title", {}, p).textContent = `Issued after ${r.origin} for ${r.target_start} to ${r.target_end}: predicted ${fmt(r.predicted)} (80% interval ${fmt(r.lo80)} to ${fmt(r.hi80)}); observed ${fmt(r.y_next)}`;
      svgEl("circle", { cx: px, cy: y(r.y_next), r: 3, fill: c.obs }, svg);
    }
    svgEl("text", { x: 12, y: T + (H - T - B) / 2, "text-anchor": "middle", transform: `rotate(-90 12 ${T + (H - T - B) / 2})` }, svg).textContent = "Detections in 7 days (square-root scale)";
    $("ol-legend").innerHTML = `<span style="color:${c.obs}"><i class="swatch"></i><span style="color:var(--ink2)">● Observed afterwards (NOAA-20, 7-day count)</span></span>` +
      `<span style="color:${c.pred}"><i class="swatch thin dashed"></i><span style="color:var(--ink2)">◇ Predicted one week before, with its 80% interval</span></span><span>Weeks with a day of no data are left out, so the line breaks there.</span>`;
    const obsR = (pick.y_next + 7) / (pick.y_prev + 7), predR = (pick.predicted + 7) / (pick.y_prev + 7);
    $("ol-read").innerHTML = `<div class="cd-main"><div><b>Issued after ${esc(longDate(pick.origin))}</b> for ${esc(longDate(pick.target_start))} to ${esc(longDate(pick.target_end))} (a past week)</div>
      <div><span class="cd-num">${fmt(pick.predicted)}</span> predicted, 80% interval ${fmt(pick.lo80)}–${fmt(pick.hi80)} · the week before: ${fmt(pick.y_prev)} (×${fmt(predR, 2)})</div>
      <div class="note">Model said: <b>${esc(pick.issued)}</b>. Observed afterwards: ${fmt(pick.y_next)} (×${fmt(obsR, 2)} against the week before: ${esc(pick.observed)}). The seasonal baseline said ${fmt(pick.b2)}.</div></div>`;
    $("ol-table").innerHTML = `<table><thead><tr><th scope="col">Issued after</th><th scope="col">Target week</th><th scope="col">Week before</th><th scope="col">Predicted</th><th scope="col">80% interval</th><th scope="col">Baseline B2</th><th scope="col">Observed</th><th scope="col" style="text-align:left">Model said</th><th scope="col" style="text-align:left">Observed change</th></tr></thead><tbody>` +
      rows.map((r) => `<tr><th scope="row">${r.origin}</th><td>${r.target_start} to ${r.target_end}</td><td>${fmt(r.y_prev)}</td><td>${fmt(r.predicted)}</td><td>${fmt(r.lo80)}–${fmt(r.hi80)}</td><td>${fmt(r.b2)}</td><td>${fmt(r.y_next)}</td><td style="text-align:left">${esc(r.issued)}</td><td style="text-align:left">${esc(r.observed)}</td></tr>`).join("") + `</tbody></table>`;
  }

  // ---------- wiring ----------
  document.addEventListener("change", (e) => {
    if (e.target.id === "cov-on") { CV.on = e.target.checked; covDraw(); }
    if (e.target.id === "cov-day") { CV.day = e.target.value; covUi(); covDraw(); }
    if (e.target.id === "ol-pick") { OL.pick = e.target.value; outlookChart(); }
  });
  document.addEventListener("click", (e) => {
    const t = e.target.closest ? e.target : null;
    if (!t) return;
    if (t.closest("#cov-fit")) { const eng = window.SeamMap.engine(); if (eng) eng.fit(CV.info.bbox_wsen, true); return; }
    if (t.closest("#cov-points")) { covOpenDay(CV.day); return; }
    const open = t.closest("[data-cov-open]");
    if (open) { covOpenDay(open.dataset.covOpen); return; }
    if (t.closest("#ol-retry")) outlookLoad();
  });
  S.on("ws", (w) => { if (w === "explore" || w === "calendar") covLoad(); if (w === "calendar" && S.UI.sub === "outlook") outlookLoad(); });
  S.on("sub", (k) => { if (k === "outlook") outlookLoad(); if (k === "days") covLoad(); });
  S.on("theme", () => { covDraw(); if (OL.data && S.UI.sub === "outlook") outlookDraw(); });
  let rz = 0;
  window.addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(() => { if (OL.data && OL.data.available && S.UI.ws === "calendar" && S.UI.sub === "outlook") outlookChart(); }, 180); });
  window.SeamCoverage = { redraw: covDraw, state: CV };
  if (S.UI.ws === "explore" || S.UI.ws === "calendar") covLoad();
  if (S.UI.ws === "calendar" && S.UI.sub === "outlook") outlookLoad();
})();
