// Seamline story cards: the project's story, read from saved result files (GET /api/showcase).
// Every number and sentence comes from the reply (c08/showcase.py); this file only lays them out,
// and it escapes every piece of text from the reply before it reaches the page. Colours come from
// the theme variables through classes in showcase.css, so a light/dark switch needs no redraw.
// Charts are drawn at the card's real width, and again when that width changes, so their text
// stays readable from 375 px phones to wide screens. Each chart has a table of its numbers.
// Wrapped in a function so nothing here collides with app.js, which loads first.
(function () {
  "use strict";

  const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const SAT = {
    SNPP: { label: "S-NPP", cls: "snpp" },
    NOAA20: { label: "NOAA-20", cls: "n20" },
    NOAA21: { label: "NOAA-21", cls: "n21" },
    Aqua: { label: "Aqua", cls: "aqua" },
    Terra: { label: "Terra", cls: "terra" },
  };
  const byId = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const isNum = (v) => typeof v === "number" && Number.isFinite(v);
  const fmt = (v, d = 0) => (isNum(v) ? v.toLocaleString("en-US", { maximumFractionDigits: d, minimumFractionDigits: d }) : "unknown");
  const r1 = (v) => Math.round(v * 10) / 10;
  function pct(v, d = 0, signed = false) {
    if (!isNum(v)) return "unknown";
    const t = fmt(Math.abs(v) * 100, d);
    if (!signed || Number(t.replace(/,/g, "")) === 0) return `${t}%`;
    return `${v < 0 ? "−" : "+"}${t}%`;
  }
  function shortDate(iso) {
    const [, m, d] = String(iso).split("-").map(Number);
    return m >= 1 && m <= 12 ? `${d} ${MON[m - 1]}` : String(iso);
  }
  const clockText = (min) => `${Math.floor(min / 60)}:${String(Math.round(min % 60)).padStart(2, "0")}`;
  const monthLabel = (ym) => { const m = Number(String(ym).slice(5, 7)); return m >= 1 && m <= 12 ? MON[m - 1] : String(ym); };

  const charts = new Map();  // container id -> draw(width) returning SVG markup

  // ---------- small building blocks (every piece of reply text goes through esc) ----------
  function put(key, html) {
    const b = byId(`${key}-body`);
    if (!b) return;
    b.innerHTML = html;
    b.setAttribute("aria-busy", "false");
  }
  const badge = (text, kind) => `<span class="sc-badge sc-badge-${esc(kind || "mixed")}">${esc(text)}</span>`;
  const para = (text, cls) => (text ? `<p${cls ? ` class="${cls}"` : ""}>${esc(text)}</p>` : "");
  function points(list) {
    if (!Array.isArray(list) || !list.length) return "";
    return `<ul class="sc-points">${list.map((p) => `<li>${p.lead ? `<b>${esc(p.lead)}</b>` : ""}${esc(p.text || "")}</li>`).join("")}</ul>`;
  }
  function waitBox(w) {
    if (!w) return "";
    return `<div class="sc-wait" role="note">
      <p>${badge("Not run yet", "wait")} <b>${esc(w.text)}</b>: ${esc(w.what)}.</p>
      <p>It needs ${esc(w.needs)}. ${esc(w.rule)}</p>
      <p class="sc-src">The result will be read from ${esc(w.file)}.</p></div>`;
  }
  function sourcesLine(list) {
    if (!Array.isArray(list) || !list.length) return "";
    const items = list.map((s) => {
      const extra = [];
      if (s.written) extra.push(`written ${esc(String(s.written).slice(0, 16).replace("T", " "))} UTC`);
      if (s.code_revision) extra.push(`code ${esc(s.code_revision)}`);
      if (s.protocol_sha256) extra.push(`under ${esc(s.protocol)}, SHA-256 ${esc(s.protocol_sha256)}…`);
      if (s.sha256) extra.push(`file SHA-256 ${esc(s.sha256)}…`);
      return esc(s.path) + (extra.length ? ` (${extra.join(", ")})` : "");
    });
    return `<p class="sc-src">Read from: ${items.join("; ")}.</p>`;
  }
  const errorBox = (c) => `<p class="sc-error" role="alert">${esc((c && c.error) || "This card could not be built.")}</p>`;
  function legend(keys, extra) {
    return `<div class="sc-legend">${keys.map((k) => `<span><i class="sc-sw-${SAT[k].cls}" aria-hidden="true"></i>${esc(SAT[k].label)}</span>`).join("")}${extra || ""}</div>`;
  }
  function chartBox(id, caption, draw, legendHtml) {
    charts.set(id, draw);
    return `<figure class="sc-fig">${legendHtml || ""}<div class="sc-chart" id="${id}"></div>${caption ? `<figcaption>${esc(caption)}</figcaption>` : ""}</figure>`;
  }
  function table(caption, head, rows) {
    const cells = (r) => r.map((c, i) => (i === 0 ? `<th scope="row">${esc(c)}</th>` : `<td>${esc(c)}</td>`)).join("");
    return `<div class="table-wrap"><table class="sc-table"><caption class="sr">${esc(caption)}</caption>` +
      `<thead><tr>${head.map((h) => `<th scope="col">${esc(h)}</th>`).join("")}</tr></thead>` +
      `<tbody>${rows.map((r) => `<tr>${cells(r)}</tr>`).join("")}</tbody></table></div>`;
  }
  const details = (summary, inner) => `<details class="sc-more"><summary>${esc(summary)}</summary>${inner}</details>`;
  function linkOrText(s) {
    const t = String(s);
    return /^https?:\/\/[^\s"'<>]+$/i.test(t) ? `<a href="${esc(t)}" target="_blank" rel="noopener noreferrer">${esc(t)}</a>` : esc(t);
  }

  // ---------- charts (plain SVG strings, sized in real pixels) ----------
  const svgOpen = (w, h, label) => `<svg class="sc-svg" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" role="img" aria-label="${esc(label)}">`;
  function niceStep(max) {
    const raw = max / 4, p = 10 ** Math.floor(Math.log10(raw)), m = raw / p;
    return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * p;
  }

  // Bars side by side within each group, never stacked. A missing value is an empty dashed slot, never a zero bar.
  function barChart(w, spec) {
    const H = spec.height || 230, L = 52, R = 8, T = 20, B = spec.subLabels ? 46 : 30;
    const vals = spec.groups.flatMap((g) => g.bars.map((b) => b.value)).filter(isNum);
    const most = Math.max(1, ...vals), step = niceStep(most);
    const top = Math.max(step, Math.ceil(most / step) * step);
    const y = (v) => r1(T + (H - T - B) * (1 - v / top));
    let s = svgOpen(w, H, spec.label);
    for (let t = 0; t <= top + step / 2; t += step) {
      s += `<line class="sc-gridline" x1="${L}" x2="${w - R}" y1="${y(t)}" y2="${y(t)}"/><text x="${L - 6}" y="${y(t) + 4}" text-anchor="end">${fmt(t)}</text>`;
    }
    const gw = (w - L - R) / spec.groups.length;
    const every = gw < 26 ? 2 : 1;
    spec.groups.forEach((g, i) => {
      const n = g.bars.length, gap = n > 1 ? 3 : 0;
      const bw = Math.max(3, Math.min(46, (gw * 0.8 - gap * (n - 1)) / n));
      const x0 = L + gw * i + (gw - (n * bw + gap * (n - 1))) / 2;
      g.bars.forEach((b, j) => {
        const x = r1(x0 + j * (bw + gap));
        const tip = `${b.label}, ${g.label}: ${isNum(b.value) ? fmt(b.value) : b.why || "unknown"}`;
        if (isNum(b.value)) {
          const top2 = y(b.value);
          s += `<rect class="sc-bar sc-fill-${b.cls}" x="${x}" y="${top2}" width="${r1(bw)}" height="${r1(Math.max(0.5, H - B - top2))}"><title>${esc(tip)}</title></rect>`;
          if (spec.valueLabels && bw >= 24) s += `<text class="sc-val" x="${r1(x + bw / 2)}" y="${top2 - 5}" text-anchor="middle">${fmt(b.value)}</text>`;
        } else {
          const hh = Math.min(26, (H - T - B) * 0.22);
          s += `<rect class="sc-missing" x="${r1(x + 0.5)}" y="${r1(H - B - hh)}" width="${r1(Math.max(1, bw - 1))}" height="${r1(hh)}"><title>${esc(tip)}</title></rect>`;
        }
      });
      if (i % every === 0) {
        const cx = r1(L + gw * i + gw / 2);
        s += `<text class="sc-strong" x="${cx}" y="${H - B + 16}" text-anchor="middle">${esc(g.label)}</text>`;
        if (spec.subLabels && g.sub) s += `<text x="${cx}" y="${H - B + 32}" text-anchor="middle">${esc(g.sub)}</text>`;
      }
    });
    s += `<line class="sc-axisline" x1="${L}" x2="${w - R}" y1="${H - B}" y2="${H - B}"/>`;
    return s + "</svg>";
  }

  // One line per satellite over years; a hollow dot marks a year that used only part of the season.
  function lineChart(w, spec) {
    const H = spec.height || 230, L = 46, R = 68, T = 14, B = 26;
    const f = (v) => (spec.log ? Math.log10(v) : v);
    const X = (x) => r1(L + (w - L - R) * ((x - spec.x0) / Math.max(1, spec.x1 - spec.x0)));
    const Y = (v) => r1(T + (H - T - B) * (1 - (f(Math.min(Math.max(v, spec.yMin), spec.yMax)) - f(spec.yMin)) / (f(spec.yMax) - f(spec.yMin))));
    let s = svgOpen(w, H, spec.label);
    for (const p of spec.periods || []) {
      const a = X(p[0] - 0.45), b = X(p[1] + 0.45);
      s += `<rect class="sc-period" x="${a}" y="${T}" width="${r1(b - a)}" height="${H - T - B}"/>`;
    }
    for (const t of spec.yTicks) {
      s += `<line class="sc-gridline" x1="${L}" x2="${w - R}" y1="${Y(t)}" y2="${Y(t)}"/><text x="${L - 6}" y="${Y(t) + 4}" text-anchor="end">${esc(spec.yFmt(t))}</text>`;
    }
    const room = Math.max(2, Math.floor((w - L - R) / 40));
    const every = Math.max(1, Math.ceil((spec.x1 - spec.x0 + 1) / room));
    for (let x = spec.x0; x <= spec.x1; x++) {
      if ((x - spec.x0) % every === 0) s += `<text x="${X(x)}" y="${H - B + 17}" text-anchor="middle">${x}</text>`;
    }
    s += `<line class="sc-axisline" x1="${L}" x2="${w - R}" y1="${H - B}" y2="${H - B}"/>`;
    const ends = [];
    for (const se of spec.series) {
      const pts = se.points.filter((p) => isNum(p.y));
      if (!pts.length) continue;
      let d = "", prev = null;
      for (const p of pts) { d += `${prev != null && p.x === prev + 1 ? "L" : "M"}${X(p.x)},${Y(p.y)}`; prev = p.x; }
      s += `<path class="sc-line sc-stroke-${se.cls}${se.dash ? " sc-dash" : ""}" d="${d}"/>`;
      for (const p of pts) {
        const tip = `${se.label}, ${p.x}: ${spec.yFmt(p.y)}${p.note ? ` (${p.note})` : ""}`;
        const cls = p.note ? `sc-dot-partial sc-stroke-${se.cls}` : `sc-dot sc-fill-${se.cls}`;
        s += `<circle class="${cls}" cx="${X(p.x)}" cy="${Y(p.y)}" r="3.4"><title>${esc(tip)}</title></circle>`;
      }
      const last = pts[pts.length - 1];
      ends.push({ x: X(last.x), y: Y(last.y), label: se.label });
    }
    // Labels at the line ends, pushed apart so that close lines (S-NPP and NOAA-20) stay readable.
    ends.sort((a, b) => a.y - b.y);
    for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 14) ends[i].y = ends[i - 1].y + 14;
    const over = ends.length ? ends[ends.length - 1].y - (H - B - 4) : 0;
    if (over > 0) ends.forEach((e) => { e.y -= over; });
    for (const e of ends) s += `<text class="sc-strong" x="${r1(e.x + 8)}" y="${r1(e.y + 4)}">${esc(e.label)}</text>`;
    return s + "</svg>";
  }

  // Season bands: per year, each satellite's span from its middle date (dot) to its end date.
  function bandChart(w, spec) {
    const sats = spec.sats, lane = 7, rowH = sats.length * lane + 8;
    const L = 42, R = 12, T = 6, B = 24, H = T + rowH * spec.rows.length + B;
    const day = (y, m, d) => Date.UTC(y, m - 1, d) / 864e5;
    const [sm, sd] = spec.window.start, [em, ed] = spec.window.end;
    const span = (y) => day(y, em, ed) - day(y, sm, sd);
    const X = (y, iso) => {
      const [yy, m, d] = String(iso).split("-").map(Number);
      const off = Math.min(Math.max(day(yy, m, d) - day(y, sm, sd), 0), span(y));
      return r1(L + (w - L - R) * (off / span(y)));
    };
    let s = svgOpen(w, H, spec.label);
    const ref = 2021;  // tick positions on a year without 29 February
    const ticks = [[sm, sd]];
    for (let m = sm + 1; m <= em; m++) ticks.push([m, 1]);
    let lastLabel = -1e9;
    for (const [m, d] of ticks) {
      const x = X(ref, `${ref}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`);
      s += `<line class="sc-gridline" x1="${x}" x2="${x}" y1="${T}" y2="${H - B}"/>`;
      if (x - lastLabel >= 46) { s += `<text x="${x}" y="${H - B + 16}" text-anchor="${m === sm ? "start" : "middle"}">${d} ${MON[m - 1]}</text>`; lastLabel = x; }
    }
    spec.rows.forEach((row, i) => {
      const y0 = T + rowH * i;
      if (i % 2 === 0) s += `<rect class="sc-rowbg" x="${L}" y="${y0}" width="${w - L - R}" height="${rowH}"/>`;
      s += `<text x="${L - 6}" y="${r1(y0 + rowH / 2 + 4)}" text-anchor="end"${row.eligible === false ? ' class="sc-dimtext"' : ""}>${row.year}</text>`;
      sats.forEach((k, j) => {
        const b = row.bands[k];
        if (!b) return;
        const yy = r1(y0 + 4 + lane * j + lane / 2);
        const tip = `${SAT[k].label}, ${row.year}: middle ${shortDate(b.mid)}, end ${shortDate(b.end)}${row.eligible === false ? " (not an eligible year)" : ""}`;
        s += `<g class="${row.eligible === false ? "sc-dim" : ""}"><title>${esc(tip)}</title>` +
          `<line class="sc-band sc-stroke-${SAT[k].cls}" x1="${X(row.year, b.mid)}" x2="${X(row.year, b.end)}" y1="${yy}" y2="${yy}"/>` +
          `<circle class="sc-fill-${SAT[k].cls}" cx="${X(row.year, b.mid)}" cy="${yy}" r="2.9"/></g>`;
      });
    });
    const xe = X(ref, `${ref}-${String(em).padStart(2, "0")}-${String(ed).padStart(2, "0")}`);
    s += `<line class="sc-axisline" x1="${xe}" x2="${xe}" y1="${T}" y2="${H - B}"/>`;
    s += `<line class="sc-axisline" x1="${L}" x2="${w - R}" y1="${H - B}" y2="${H - B}"/>`;
    return s + "</svg>";
  }
  function bandTable(caption, rows, sats) {
    const head = ["Year", ...sats.flatMap((k) => [`${SAT[k].label} middle`, `${SAT[k].label} end`])];
    return table(caption, head, rows.map((r) => [String(r.year) + (r.eligible === false ? ` (not eligible${r.why_not_eligible ? `: ${r.why_not_eligible}` : ""})` : ""),
      ...sats.flatMap((k) => (r.bands[k] ? [shortDate(r.bands[k].mid), shortDate(r.bands[k].end)] : ["–", "–"]))]));
  }
  const usedSats = (rows, sats) => sats.filter((k) => rows.some((r) => r.bands[k]));

  // ---------- 1. headline ----------
  // Order: the verdict, the punchline (one satellite against the naive sum), the chart, then the counts and notes.
  function renderHeadline(c) {
    const p = c.press;
    let h = c.state === "result" ? "" : para(c.lede, "sc-lede");
    const press = p ? `<div class="sc-stats">
        <div class="sc-stat"><p class="sc-stat-h">${esc(p.sum_label)} (press)</p><div class="sc-big">${fmt(p.sum)}</div><p>${esc(p.sum_what)}</p></div>
        <div class="sc-stat"><p class="sc-stat-h">${esc(p.snpp_label)} (press)</p><div class="sc-big">${fmt(p.snpp)}</div><p>${esc(p.snpp_what)}</p></div></div>
        <p class="sc-note">${esc(p.area)}, ${esc(p.period)}. Sources: ${(p.sources || []).map(esc).join("; ")}. ${esc(p.seen)}</p>` : "";
    if (c.state === "waiting") {
      h += press + para(c.flying_fact, "sc-note") + waitBox(c.waiting) + points((c.waiting_points || []).map((t) => ({ text: t })));
      h += details("Readings fixed before the test", `<ul class="sc-points">${(c.readings_fixed || []).map((t) => `<li>${esc(t)}</li>`).join("")}</ul>`);
    } else if (c.state === "result") {
      const r = c.result;
      const yn = (v) => (v === true ? "yes" : v === false ? "no" : "unknown");
      // The badge already says the reading when they are the same word ("Reproduced"); never print it twice.
      h += `<p class="sc-verdict">${badge(r.badge, r.badge_kind)}${sameWords(r.reading, r.badge) ? "" : ` ${esc(r.reading)}`}</p>`;
      h += `<div class="sc-stats">${r.changes.map((x) => `<div class="sc-stat ${x.kind === "naive" ? "sc-naive" : "sc-key"}">` +
        `<p class="sc-stat-h">${esc(x.label)}</p><div class="sc-big">${esc(x.text)}</div><p>${esc(x.note)}</p><p class="sc-src">${esc(x.from)}.</p></div>`).join("")}</div>`;
      h += para(r.snpp_range_text, "sc-note");
      const groups = r.years.map((y) => ({
        label: y.year, sub: `${y.flying} satellite${y.flying === 1 ? "" : "s"} flying`,
        bars: y.bars.map((b) => ({ ...b, cls: SAT[b.key].cls })),
      }));
      h += chartBox("sc-headline-bars", r.bars_caption, (w) => barChart(w, {
        label: "Bar chart: each VIIRS satellite's own count of detections for 1–29 October in Pakistani Punjab, 2019 and 2026, side by side",
        groups, valueLabels: true, subLabels: true, height: 240,
      }), legend(["SNPP", "NOAA20", "NOAA21"], `<span><i class="sc-sw-missing" aria-hidden="true"></i>not flying</span>`));
      h += para(c.lede, "sc-lede");
      h += `<h3>Our count beside the press figure</h3><div class="sc-stats">${[r.sum, r.snpp].map((x) => `<div class="sc-stat"><p class="sc-stat-h">${esc(x.label)}: our count</p>` +
        `<div class="sc-big">${fmt(x.value)}</div><p>Press figure ${fmt(x.target)}. Within ±20%: <b>${yn(x.within)}</b>.</p></div>`).join("")}</div>`;
      h += details("Press figures, counting rule and gaps", press + para(c.flying_fact, "sc-note") + para(r.count_rule, "sc-note") + para(r.gap_text, "sc-note"));
      h += details("Show the bar values as a table", table("Each satellite's own count, 1–29 October, Pakistani Punjab",
        ["Year", "S-NPP", "NOAA-20", "NOAA-21", "Satellites flying"],
        r.years.map((y) => [y.year, ...y.bars.map((b) => (isNum(b.value) ? fmt(b.value) : b.why || "unknown")), String(y.flying)])));
    } else h += errorBox(c);
    put("headline", h + sourcesLine(c.sources));
  }

  // True when two texts say the same words, ignoring case, marks and spacing ("✓ Reproduced" and "Reproduced").
  function sameWords(a, b) {
    const norm = (s) => String(s || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
    return norm(a) !== "" && norm(a) === norm(b);
  }

  // ---------- 2. seam ----------
  // Order: the verdict, the two totals side by side (converted against no conversion), the months, then the facts.
  function renderSeam(c) {
    let h = c.state === "result" ? "" : para(c.lede, "sc-lede");
    const facts = `<ul class="sc-facts">${(c.facts || []).map((f) => `<li><b>${esc(f.text)}</b> Source: ${esc(f.source)}. <span class="sc-note">${esc(f.also || "")}</span></li>`).join("")}</ul>`;
    const e = c.earlier_test;
    const earlier = e ? `<div class="sc-stat sc-earlier"><p class="sc-stat-h">${esc(e.label)}</p><p>${esc(e.text)}</p><p class="sc-note">${esc(e.note)}</p></div>` : "";
    if (c.state === "waiting") {
      h += facts + earlier + `<h3>The frozen test on 2026 (P04 G03)</h3>` + waitBox(c.waiting) + para(c.pass_mark, "sc-note") + para(c.availability_text, "sc-note");
    } else if (c.state === "result") {
      const r = c.result;
      h += `<p class="sc-verdict">${badge(r.status_text, r.badge_kind)} ${esc(r.reading || "")}</p>`;
      h += `<div class="sc-stats"><div class="sc-stat sc-key"><p class="sc-stat-h">Total error of converted NOAA-20 (WAPE), Punjab</p><div class="sc-big">${esc(r.wape_text)}</div><p>The frozen test on 2026 (P04 G03), against S-NPP as the reference.</p></div>` +
        `<div class="sc-stat sc-naive"><p class="sc-stat-h">No conversion at all (M0), Punjab, for comparison</p><div class="sc-big">${esc(r.m0_text)}</div><p>NOAA-20 as counted, against the same S-NPP months.</p></div></div>`;
      h += para(r.reading_note, "sc-note");
      if (r.reported && r.reported.length) h += `<p class="sc-note"><b>${esc(r.reported_note)}</b> ${r.reported.map((x) => esc(x.text)).join("; ")}.</p>`;
      if (r.months && r.months.length) {
        h += chartBox("sc-seam-months", r.months_caption, (w) => barChart(w, {
          label: "Bar chart: S-NPP's observed monthly detections in Punjab beside NOAA-20's converted to S-NPP's scale, for each scored month of 2026",
          groups: r.months.map((m) => ({ label: monthLabel(m.month), bars: [
            { label: "S-NPP observed", value: m.observed_snpp, cls: "snpp", why: "unknown" },
            { label: "NOAA-20 converted", value: m.predicted, cls: "n20", why: "unknown" }] })),
          height: 210,
        }), `<div class="sc-legend"><span><i class="sc-sw-snpp" aria-hidden="true"></i>S-NPP, observed</span><span><i class="sc-sw-n20" aria-hidden="true"></i>NOAA-20, converted to S-NPP's scale</span></div>`);
      }
      h += para(c.lede, "sc-lede") + para(r.means) + para(r.m0_note, "sc-note");
      if (r.facts && r.facts.length) h += `<ul class="sc-points sc-note">${r.facts.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>`;
      if (r.months && r.months.length) {
        const held = (v) => (v === true ? "yes" : v === false ? "no (under 300 S-NPP)" : "unknown");
        const within = (m) => (m.held_to_month_rule === false ? "not held" : m.within_month_rule === true ? "yes" : m.within_month_rule === false ? "no" : "unknown");
        h += details("Show the months as a table", table("Scored months of 2026, Punjab",
          ["Month", "Stream", "Matched days", "S-NPP observed", "NOAA-20 converted", "Error", "Held to the 20% month rule", "Within 20%"],
          r.months.map((m) => [m.month, m.stream || "unknown", fmt(m.matched_days), fmt(m.observed_snpp), fmt(m.predicted), pct(m.error, 1, true), held(m.held_to_month_rule), within(m)])));
      }
      h += details("S-NPP's end, the earlier test and the pass mark", facts + earlier + para(c.pass_mark, "sc-note"));
    } else h += errorBox(c);
    put("seam", h + sourcesLine(c.sources));
  }

  // ---------- 3. clock ----------
  function renderClock(c) {
    let h = para(c.lede, "sc-lede");
    const P = c.punjab;
    if (P) {
      h += `<h3>${esc(P.label)}</h3><div class="sc-grid2">`;
      const T = P.pass_times && P.pass_times.series;
      if (T) {
        const keys = ["Terra", "Aqua", "SNPP", "NOAA20"].filter((k) => T[k] && T[k].length);
        const xs = keys.flatMap((k) => T[k].map((p) => p.year));
        if (xs.length) {
          h += chartBox("sc-clock-times", P.pass_times.caption, (w) => lineChart(w, {
            label: "Line chart: the median local time of each satellite's October–November day-pass detections in Punjab, by year",
            x0: Math.min(...xs), x1: Math.max(...xs), yMin: 9 * 60, yMax: 15 * 60,
            yTicks: [540, 600, 660, 720, 780, 840, 900], yFmt: clockText,
            series: keys.map((k) => ({ label: SAT[k].label, cls: SAT[k].cls, dash: k === "NOAA20", points: T[k].map((p) => ({ x: p.year, y: p.minutes })) })),
          }), legend(keys));
        }
      }
      const Q = P.q && P.q.series;
      if (Q) {
        const keys = ["Terra", "Aqua"].filter((k) => Q[k] && Q[k].length);
        const xs = keys.flatMap((k) => Q[k].map((p) => p.year));
        if (xs.length) {
          h += chartBox("sc-clock-q", P.q.caption, (w) => lineChart(w, {
            label: "Line chart, log scale: each MODIS satellite's October–November detections relative to the number expected from S-NPP (Q), Punjab, by year",
            x0: Math.min(...xs), x1: Math.max(...xs), yMin: 0.01, yMax: 3, log: true,
            yTicks: [0.01, 0.03, 0.1, 0.3, 1, 3], yFmt: (v) => (v >= 1 ? fmt(v, 0) : fmt(v, v >= 0.1 ? 1 : 2)),
            periods: P.q.periods || [],
            series: keys.map((k) => ({ label: SAT[k].label, cls: SAT[k].cls, points: Q[k].map((p) => ({ x: p.year, y: p.q, note: p.note })) })),
          }), legend(keys, `<span><i class="sc-sw-period" aria-hidden="true"></i>periods compared</span><span><i class="sc-sw-partial" aria-hidden="true"></i>part of the season only</span>`));
        }
      }
      h += `</div>` + points(P.points) + para(P.caution, "sc-caution");
      // One table with every number the two charts draw.
      const years = [...new Set([...Object.values(T || {}), ...Object.values(Q || {})].flat().map((p) => p.year))].sort((a, b) => a - b);
      const tOf = (k, y) => { const p = T && T[k] && T[k].find((q) => q.year === y); return p ? p.time : "–"; };
      const qOf = (k, y) => { const p = Q && Q[k] && Q[k].find((q) => q.year === y); return p ? fmt(p.q, 3) + (p.note ? ` (${p.note})` : "") : "–"; };
      if (years.length) {
        h += details("Show the pass times and Q as a table", table("Punjab, October–November: median detection times and Q by year",
          ["Year", "Terra time", "Aqua time", "S-NPP time", "NOAA-20 time", "Terra Q", "Aqua Q"],
          years.map((y) => [String(y), tOf("Terra", y), tOf("Aqua", y), tOf("SNPP", y), tOf("NOAA20", y), qOf("Terra", y), qOf("Aqua", y)])));
      }
    } else h += para(c.text, "sc-error");
    const V = c.provinces;
    if (V) {
      h += `<h3>${esc(V.title)}</h3>`;
      if (V.state === "waiting") h += waitBox(V.waiting);
      else {
        if (V.summary) h += `<p><b>${esc(V.summary)}</b></p>`;
        h += `<ul class="sc-points">${(V.items || []).map((it) => {
          const named = it.reading.startsWith(it.name) ? "" : `<b>${esc(it.name)}:</b> `;
          return `<li>${named}${esc(it.reading)}${it.cause_note ? ` <span class="sc-cause">${esc(it.cause_note)}</span>` : ""}` +
            `${it.details && it.details.length ? `<span class="sc-cause">${it.details.map(esc).join("; ")}.</span>` : ""}</li>`;
        }).join("")}</ul>`;
        h += para(V.reading, "sc-note");
      }
    }
    put("clock", h + sourcesLine(c.sources));
  }

  // ---------- 4. season ----------
  // Overview shows Punjab's own dates (the development area) and how many pairs hold, fail or went untested.
  // Evidence shows every tested province and season as a matrix; a cell opens its chart, table and reading.
  // A failure or an untested pair is drawn as heavily as a pass.
  const OUTCOME_WORD = { holds: "Holds", fails: "Fails", not_testable: "Not tested" };
  const outcomeBadge = (o) => (OUTCOME_WORD[o] ? `<strong class="sc-outcome sc-out-${esc(o)}">${OUTCOME_WORD[o]}</strong>` : "");
  function outcomeText(l) {
    const word = OUTCOME_WORD[l.outcome];
    let rest = String(l.label || "");
    if (!word) return esc(rest);
    if (rest.toLowerCase().startsWith(word.toLowerCase())) rest = rest.slice(word.length).replace(/^[\s:;,]+/, "");
    return `${outcomeBadge(l.outcome)}${rest ? ` ${esc(rest)}` : ""}`;
  }
  const seasonKey = (title) => (/spring/i.test(String(title)) ? "spring" : "rice");
  function renderSeason(c) {
    let h = para(c.lede, "sc-lede");
    const P = c.punjab, T = c.tests;
    if (T && T.state === "waiting") h += waitBox(T.waiting);
    else if (T && T.items && T.items.length) {
      const all = T.items.flatMap((it) => it.labels.map((l) => l.outcome));
      const n = (k) => all.filter((o) => o === k).length;
      h += `<p class="sc-verdict">${outcomeBadge("holds")} <b>${n("holds")}</b> ${outcomeBadge("fails")} <b>${n("fails")}</b> ${outcomeBadge("not_testable")} <b>${n("not_testable")}</b>` +
        `<span class="sc-note">satellite pairs, over the tested province and season windows</span></p>`;
    }
    if (P) {
      const sats = usedSats(P.rows, P.sats);
      h += `<h3>${esc(P.title)}</h3><p>${badge(P.badge, "dev")}</p>`;
      h += chartBox("sc-season-punjab", P.caption, (w) => bandChart(w, {
        label: `Band chart: ${P.title}; for each year, each satellite's season from its middle date to its end date`,
        window: P.window, rows: P.rows, sats,
      }), legend(sats));
      h += points(P.points);
      h += details("Show the dates as a table", bandTable(`${P.title}: middle and end dates`, P.rows, sats));
    }
    h += para(c.past_only, "sc-note");
    put("season", h + sourcesLine(c.sources));
    renderSeasonMatrix(c);
  }
  function renderSeasonMatrix(c) {
    const T = c.tests;
    let h = para(c.lede, "sc-lede");
    if (!T) { put("seasons", h + para("No saved season tests were found.", "sc-note") + sourcesLine(c.sources)); return; }
    h += `<h3>${esc(T.title)}</h3>`;
    if (T.state === "waiting") { put("seasons", h + waitBox(T.waiting) + sourcesLine(c.sources)); return; }
    const items = T.items || [];
    const provs = ["Punjab", ...items.map((it) => it.province)].filter((v, i, a) => v && a.indexOf(v) === i);
    const seasons = [["rice", "Rice season (15 Sep–31 Dec)"], ["spring", "Spring season (15 Mar–30 Jun)"]];
    let open = items.findIndex((it) => it.labels.some((l) => l.outcome === "fails"));
    if (open < 0) open = 0;
    h += `<p class="sc-note">Each cell is one province and season window. Inside it, each satellite pair has its own outcome. Select a cell to open its chart, table and reading.</p>`;
    h += `<div class="table-wrap"><table class="matrix"><thead><tr><th scope="col">Province</th>${seasons.map(([, t]) => `<th scope="col">${esc(t)}</th>`).join("")}</tr></thead><tbody>`;
    for (const prov of provs) {
      h += `<tr><th scope="row">${esc(prov)}</th>`;
      for (const [key] of seasons) {
        const i = items.findIndex((it) => it.province === prov && seasonKey(it.title) === key);
        if (i >= 0) {
          h += `<td><button type="button" class="mx-cell" data-mx="${i}" aria-pressed="${i === open}">${items[i].labels.map((l) =>
            `<span class="mx-pair">${outcomeBadge(l.outcome)} ${esc(l.satellites)}</span>`).join("")}</button></td>`;
        } else if (prov === "Punjab" && key === "rice" && c.punjab) {
          h += `<td><span class="mx-none">${badge("Development area", "dev")} Its dates were seen before the test, so they are shown in Overview and never counted as a test.</span></td>`;
        } else h += `<td><span class="mx-none">Not part of this test</span></td>`;
      }
      h += `</tr>`;
    }
    h += `</tbody></table></div>`;
    items.forEach((it, i) => {
      const sats = usedSats(it.rows, it.sats);
      h += `<div class="mx-detail" id="sc-mx-${i}"${i === open ? "" : " hidden"}><h4>${esc(it.title)}</h4><ul class="sc-points">${it.labels.map((l) =>
        `<li><b>${esc(l.satellites)}:</b> ${outcomeText(l)}${l.reason ? ` (${esc(l.reason)})` : ""}</li>`).join("")}</ul>`;
      if (it.rows.length && sats.length) {
        h += chartBox(`sc-season-g02-${i}`, "", (w) => bandChart(w, {
          label: `Band chart: ${it.title}; for each year, each satellite's season from its middle date to its end date`,
          window: it.window, rows: it.rows, sats,
        }), legend(sats));
        h += details("Show the dates as a table", bandTable(`${it.title}: middle and end dates`, it.rows, sats));
      }
      h += `</div>`;
    });
    const R = T.readings || [];
    if (R.length) h += details("All readings saved by the test", `<ul class="sc-points">${R.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>`);
    h += para(T.unparsed_note, "sc-note") + para(c.past_only, "sc-note");
    put("seasons", h + sourcesLine(c.sources));
  }
  // A matrix cell opens its detail; the chart inside is drawn at its real width once it is visible.
  document.addEventListener("click", (e) => {
    const b = e.target && e.target.closest ? e.target.closest(".mx-cell") : null;
    if (!b) return;
    for (const o of document.querySelectorAll(".mx-cell")) o.setAttribute("aria-pressed", String(o === b));
    for (const d of document.querySelectorAll(".mx-detail")) d.hidden = d.id !== `sc-mx-${b.dataset.mx}`;
    drawCharts(false);
    const d = byId(`sc-mx-${b.dataset.mx}`);
    if (d && d.scrollIntoView) d.scrollIntoView({ block: "nearest" });
  });

  // ---------- 5. verification log ----------
  function renderLog(c) {
    if (c.state === "missing") { put("log", para(c.text) + sourcesLine(c.sources)); return; }
    if (c.state !== "result") { put("log", errorBox(c) + sourcesLine(c.sources)); return; }
    let h = c.updated ? `<p class="sc-note">Updated ${esc(c.updated)}.</p>` : "";
    h += `<h3>Mistakes we caught</h3>`;
    h += c.mistakes && c.mistakes.length ? `<ol class="sc-log">${c.mistakes.map((m) => `<li>${m.date ? `<b>${esc(m.date)}</b>: ` : ""}${esc(m.what || "")}` +
      `${m.found_by ? ` <span class="sc-note">Found by ${esc(m.found_by)}.</span>` : ""}` +
      `${m.fixed_in ? ` <span class="sc-note">Fixed in ${esc(m.fixed_in)}.</span>` : ""}` +
      `${m.source ? ` <span class="sc-note">Source: ${linkOrText(m.source)}</span>` : ""}</li>`).join("")}</ol>` : para("No entries yet.", "sc-note");
    h += `<h3>Satellite status, with the date we read it</h3>`;
    h += c.satellite_status && c.satellite_status.length ? `<ul class="sc-log">${c.satellite_status.map((f) => `<li>${esc(f.fact || "")} ` +
      `<span class="sc-note">Read ${esc(f.date_read || "on a date not recorded")}${f.source ? "; source: " : "."}</span>${f.source ? linkOrText(f.source) : ""}</li>`).join("")}</ul>` : para("No entries yet.", "sc-note");
    // A draft is never shown on the page: only Urdu wording that Hasnain has checked ("approved": true).
    if (c.urdu && c.urdu.text && c.urdu.approved === true) {
      h += `<h3>Summary in Urdu</h3><p class="sc-urdu" lang="ur" dir="rtl">${esc(c.urdu.text)}</p>`;
    }
    put("log", h + sourcesLine(c.sources));
  }

  // ---------- load and draw ----------
  const RENDER = { headline: renderHeadline, seam: renderSeam, clock: renderClock, season: renderSeason, log: renderLog };

  function drawCharts() {
    for (const [id, draw] of charts) {
      const host = byId(id);
      if (!host?.clientWidth) continue;
      const w = Math.max(240, Math.min(760, Math.floor(host.clientWidth)));
      if (host.dataset.w === String(w)) continue;
      host.dataset.w = String(w);
      try { host.innerHTML = draw(w); } catch (e) { host.innerHTML = `<p class="sc-error">This chart could not be drawn (${esc(e.message)}).</p>`; }
    }
  }

  let cards = null, pending = false, loadError = "";
  const rendered = new Set();
  async function load() {
    pending = true;
    try {
      const r = await fetch("/api/showcase", { headers: { Accept: "application/json" } });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      cards = (await r.json()).cards || {};
    } catch (e) {
      loadError = e.message;
    } finally {
      pending = false;
      redraw();
    }
  }

  function redraw() {
    const { ws, story, ev } = window.Seam.UI;
    const k = ws === "overview" && ["headline", "seam", "clock", "season"].includes(story) ? story
      : ws === "evidence" && ev === "log" ? "log"
      : ws === "evidence" && ev === "seasons" ? "season" : "";
    if (!k) return;
    if (loadError) { put(k, `<p class="sc-error" role="alert">The saved results could not be loaded (${esc(loadError)}). Check your connection and reload the page.</p>`); return; }
    if (!cards) { if (!pending) load(); return; }
    if (!rendered.has(k)) {
      rendered.add(k);
      const c = cards[k];
      if (!c) { put(k, para("This card is missing from the reply.", "sc-error")); return; }
      const t = byId(`${k}-title`);
      if (t && c.title) t.textContent = c.title;
      try {
        if (c.state === "error") put(k, errorBox(c) + sourcesLine(c.sources));
        else RENDER[k](c);
      } catch (e) {
        put(k, `<p class="sc-error" role="alert">This card could not be drawn (${esc(e.message)}).</p>`);
      }
    }
    drawCharts();
  }

  // Charts in a panel that was hidden are drawn again at their real width when the panel is shown.
  window.SeamShowcase = { redraw, ready: () => !pending };
  window.Seam.on("resize", drawCharts);

  let timer = null;
  window.addEventListener("resize", () => { clearTimeout(timer); timer = setTimeout(drawCharts, 150); });
})();
