// Seamline front end (core). Every number shown comes from the local API (/api/analyze, /api/daily, ...);
// nothing is computed here except sums for the yearly chart views, which are labelled as such.
// Other scripts (showcase.js, explore.js, features.js, map3d.js) talk to this one through window.Seam.
"use strict";

const IN_BROWSER = typeof document !== "undefined";  // false when the pure helpers are loaded by Node for tests
const $ = (id) => document.getElementById(id);
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTH_FULL = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const NS = "http://www.w3.org/2000/svg";
const VIEWS = ["OctNov", "AprMay", "year", "month"];  // the "Record over time" chart views
const CAL_SOURCES = ["H", "aqua", "naive"];  // the calendar's series
const OFFLINE_MSG = "The analysis service is currently unreachable. Check your connection and try again.";
let META = null, RESULT = null, GEO = null;
let REQ = 0, CTRL = null;  // only the newest /api/analyze reply may be drawn

const fmt = (v, d = 0) => v == null || Number.isNaN(v) ? "–" : Number(v).toLocaleString("en-US", { maximumFractionDigits: d, minimumFractionDigits: d });
const sfmt = (v, d = 0) => v == null ? "–" : (v > 0 ? "+" : "") + fmt(v, d);
const pct100 = (v, d = 0) => v == null ? "–" : fmt(v * 100, d);  // share -> percent text; null stays a dash
const PASSES = { D: "day", N: "night" };
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const reducedMotion = () => IN_BROWSER && window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const ym = (y, m) => `${y}-${String(m).padStart(2, "0")}`;

function el(tag, attrs = {}, parent) {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (parent) parent.appendChild(n);
  return n;
}

// ---------- tooltip ----------
const tip = IN_BROWSER ? $("tip") : null;
function showTip(html, evt) {
  tip.innerHTML = html;
  tip.hidden = false;
  const pad = 14, w = tip.offsetWidth, h = tip.offsetHeight;
  let x = evt.clientX + pad, y = evt.clientY + pad;
  if (x + w > window.innerWidth - 8) x = evt.clientX - w - pad;
  if (y + h > window.innerHeight - 8) y = evt.clientY - h - pad;
  tip.style.left = Math.max(8, x) + "px";
  tip.style.top = Math.max(8, y) + "px";
}
const hideTip = () => { tip.hidden = true; };

// ---------- application state: one explicit selection, mirrored in the address ----------
const WORKSPACES = ["overview", "explore", "calendar", "evidence"];
const STORIES = ["record", "headline", "seam", "clock", "days", "season"];
const SUBS = ["months", "days", "normal", "compare", "outlook"];
const EVS = ["method", "experiments", "seasons", "replay", "log", "limits", "science", "downloads"];
const SATS = ["Terra", "Aqua", "SNPP", "NOAA20", "NOAA21"];
const SAT_INFO = {
  Terra: { label: "Terra MODIS", short: "Terra", cls: "terra", round: false },
  Aqua: { label: "Aqua MODIS", short: "Aqua", cls: "aqua", round: false },
  SNPP: { label: "S-NPP VIIRS", short: "S-NPP", cls: "snpp", round: true },
  NOAA20: { label: "NOAA-20 VIIRS", short: "NOAA-20", cls: "n20", round: true },
  NOAA21: { label: "NOAA-21 VIIRS", short: "NOAA-21", cls: "n21", round: true },
};
// What is on screen besides the analysis selection. Defaults are the documented "Reset" state.
const UI_DEFAULT = { ws: "overview", story: "record", sub: "months", ev: "method", sats: ["SNPP"], dn: "DN", mapDay: 0, mode: "3d", scale: "log", season: "OctNov" };
const UI = JSON.parse(JSON.stringify(UI_DEFAULT));
let AREAS = null, PENDING = false, LAST_ERROR = null;

const HANDLERS = {};
const Seam = {
  on(evt, fn) { (HANDLERS[evt] = HANDLERS[evt] || []).push(fn); },
  emit(evt, data) { for (const fn of HANDLERS[evt] || []) { try { fn(data); } catch (e) { console.error(`Seamline: handler for "${evt}" failed`, e); } } },
};

// ?area=Punjab (or box=w,s,e,n) &from=2003&to=2025 &month=2025-11 &model=M2 &day=2025-11 &view=OctNov &cal=H
// plus the view: &ws=explore &story=seam &sub=days &ev=replay &sat=SNPP,NOAA20 &pass=D &d=14 &map=2d &scale=lin &season=AprMay
function parseState(search, meta) {
  const q = new URLSearchParams(search || "");
  const state = {}, ignored = [];
  const [first, last] = meta.years;
  const year = (v) => (/^\d{4}$/.test(v || "") ? Number(v) : NaN);
  const inRange = (y) => Number.isInteger(y) && y >= first && y <= last;
  const yearMonth = (v) => {
    const m = /^(\d{4})-(\d{1,2})$/.exec(v || "");
    if (!m) return null;
    const y = Number(m[1]), mo = Number(m[2]);
    return inRange(y) && mo >= 1 && mo <= 12 ? [y, mo] : null;
  };
  if (q.has("box")) {
    const parts = q.get("box").split(",").map((s) => s.trim());
    const b = parts.map(Number);
    const ok = parts.length === 4 && parts.every((s) => /^-?\d+(\.\d+)?$/.test(s)) &&
      b[0] < b[2] && b[1] < b[3] && b[0] >= -180 && b[2] <= 180 && b[1] >= -90 && b[3] <= 90;
    if (ok) state.bbox = b; else ignored.push("box");
  }
  if (q.has("area")) {
    if (meta.regions.includes(q.get("area"))) state.region = q.get("area"); else ignored.push("area");
  }
  if (q.has("from") || q.has("to")) {
    const y0 = q.has("from") ? year(q.get("from")) : first, y1 = q.has("to") ? year(q.get("to")) : last;
    if (inRange(y0) && inRange(y1) && y0 < y1) state.years = [y0, y1]; else ignored.push("years");
  }
  if (q.has("month")) {
    const m = yearMonth(q.get("month")), span = state.years || meta.years;
    if (m && m[0] >= span[0] && m[0] <= span[1]) state.month = m; else ignored.push("compare month");
  }
  if (q.has("model")) {
    if (meta.models.includes(q.get("model"))) state.model = q.get("model"); else ignored.push("model");
  }
  if (q.has("day")) {
    const m = yearMonth(q.get("day"));
    if (m) state.day = m; else ignored.push("day-by-day month");
  }
  if (q.has("view")) {
    if (VIEWS.includes(q.get("view"))) state.view = q.get("view"); else ignored.push("chart view");
  }
  if (q.has("cal")) {
    if (CAL_SOURCES.includes(q.get("cal"))) state.cal = q.get("cal"); else ignored.push("calendar series");
  }
  const pick = (key, list, name, as) => {
    if (!q.has(key)) return;
    if (list.includes(q.get(key))) state[as || key] = q.get(key); else ignored.push(name);
  };
  pick("ws", WORKSPACES, "workspace");
  pick("story", STORIES, "story");
  pick("sub", SUBS, "calendar view");
  pick("ev", EVS, "evidence section");
  pick("pass", ["DN", "D", "N"], "pass filter", "dn");
  pick("map", ["globe", "2d", "3d"], "map view", "mode");
  pick("scale", ["log", "lin"], "chart scale");
  pick("season", ["OctNov", "AprMay"], "season");
  if (q.has("sat")) {
    const s = q.get("sat").split(",").filter(Boolean);
    if (s.length && s.every((k) => SATS.includes(k))) state.sats = [...new Set(s)]; else ignored.push("satellites");
  }
  if (q.has("d")) {
    const d = Number(q.get("d"));
    if (Number.isInteger(d) && d >= 0 && d <= 31) state.mapDay = d; else ignored.push("map day");
  }
  return { state, ignored };
}

function stateQuery(s) {
  const q = new URLSearchParams();
  if (!s) return "";
  if (s.bbox) q.set("box", s.bbox.map((v) => String(Number(v))).join(","));
  else if (s.region) q.set("area", s.region);
  if (s.years) { q.set("from", String(s.years[0])); q.set("to", String(s.years[1])); }
  if (s.month) q.set("month", ym(s.month[0], s.month[1]));
  if (s.model) q.set("model", s.model);
  if (s.day) q.set("day", ym(s.day[0], s.day[1]));
  if (s.view) q.set("view", s.view);
  if (s.cal) q.set("cal", s.cal);
  // The view is written only where it differs from the default, so plain links stay short.
  if (s.ws && s.ws !== UI_DEFAULT.ws) q.set("ws", s.ws);
  if (s.story && s.story !== UI_DEFAULT.story) q.set("story", s.story);
  if (s.sub && s.sub !== UI_DEFAULT.sub) q.set("sub", s.sub);
  if (s.ev && s.ev !== UI_DEFAULT.ev) q.set("ev", s.ev);
  if (s.sats && s.sats.join(",") !== UI_DEFAULT.sats.join(",")) q.set("sat", s.sats.join(","));
  if (s.dn && s.dn !== UI_DEFAULT.dn) q.set("pass", s.dn);
  if (s.mapDay) q.set("d", String(s.mapDay));
  if (s.mode && s.mode !== UI_DEFAULT.mode) q.set("map", s.mode);
  if (s.scale && s.scale !== UI_DEFAULT.scale) q.set("scale", s.scale);
  if (s.season && s.season !== UI_DEFAULT.season) q.set("season", s.season);
  if (["simple", "advanced"].includes(s.experience)) q.set("experience", s.experience);
  if (s.basemap === "terrain" || s.basemap === "satellite") q.set("basemap", s.basemap);
  return q.toString().replace(/%2C/gi, ",");  // box=65,27,65.2,27.2 reads better, and parses the same
}

// ---------- reliability of each harmonised point (pure; used by the band under the chart) ----------
const REL_TEXT = {
  observed: "observed S-NPP",
  converted: "converted from Aqua (tested on whole months only; its rough range was too narrow in testing) or NOAA-20 (Punjab Nov 2026 bridge; no uncertainty range)",
  mixed: "partly converted from Aqua or NOAA-20",
  gap: "missing, partly covered or untyped NRT",
};
function relClass(p) {
  if (p.H == null || p.flag) return "gap";  // no value, or the satellite's record is partial/untyped that month
  const srcs = p.srcs || [p.src];
  if (srcs.every((s) => String(s).startsWith("observed S-NPP"))) return "observed";
  if (srcs.every((s) => String(s).startsWith("modelled") || String(s).startsWith("NOAA-20 converted"))) return "converted";
  return "mixed";
}
function relRuns(pts) {
  const runs = [];
  for (const p of pts) {
    const c = relClass(p), last = runs[runs.length - 1];
    if (last && last.c === c) last.to = p.label; else runs.push({ c, from: p.label, to: p.label });
  }
  return runs;
}

// ---------- form ----------
function fillSelect(sel, items, value) {
  sel.innerHTML = items.map(([v, t]) => `<option value="${esc(v)}">${esc(t)}</option>`).join("");
  if (value != null) sel.value = String(value);
}

function payload() {
  const p = {
    region: $("region").value,
    years: [Number($("y0").value), Number($("y1").value)],
    month: [Number($("cy").value), Number($("cm").value)],
    model: document.querySelector('input[name="model"]:checked').value,
  };
  if ($("use-box").checked) p.bbox = ["bw", "bs", "be", "bn"].map((k) => $(k).value.trim());
  return p;
}

// ---------- status, errors, motion ----------
let TOAST_T = null;
function toast(msg, opts = {}) {
  const m = $(opts.second ? "share-msg" : "form-msg");
  m.textContent = msg || "";
  m.classList.toggle("error", !!opts.error);
  clearTimeout(TOAST_T);
  if (msg && !opts.sticky) TOAST_T = setTimeout(() => { m.textContent = ""; }, opts.error ? 9000 : 4200);
}
function setBusy(on, msg = "") {
  PENDING = on;
  Seam.emit("loading", on);
  $("main").setAttribute("aria-busy", on ? "true" : "false");
  $("context").classList.toggle("pending", on);
  $("go").disabled = on;
  // The map's live count already confirms a completed selection in Simple mode.
  if (!on && /^Showing /.test(msg) && document.documentElement.dataset.experience === "simple") { toast(""); return; }
  toast(msg, { sticky: on });
}
function showError(msg) { toast(msg, { error: true }); }
function motionMode() {
  const set = document.documentElement.dataset.motion;
  if (set) return set;
  return reducedMotion() ? "reduced" : "full";
}

async function post(url, body, signal) {
  let r;
  try {
    r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal });
  } catch (e) {
    if (e.name === "AbortError") throw e;
    throw new Error(OFFLINE_MSG);  // each browser words a network failure differently
  }
  if (!r.ok) {
    let msg = `Request failed (HTTP ${r.status})`;
    try { msg = (await r.json()).message || msg; } catch (_) { /* not JSON */ }
    throw new Error(msg);
  }
  return r;
}

async function run() {
  const p = payload();
  if (p.years[0] >= p.years[1]) { showError("Choose a 'From' year earlier than the 'To' year."); return; }
  if (p.month[0] < p.years[0] || p.month[0] > p.years[1]) {
    showError("The compare month must fall inside the chosen years."); return;
  }
  if (p.bbox) {
    const why = boxProblem(p.bbox);
    if (why) { showError(why); return; }
  }
  // A newer request cancels the older one, and a late reply is never drawn over a newer selection.
  const id = ++REQ;
  if (CTRL) CTRL.abort();
  CTRL = new AbortController();
  LAST_ERROR = null;
  const wanted = p.bbox ? "the rectangle" : p.region;
  setBusy(true, RESULT ? `Loading ${wanted}, ${p.years[0]}–${p.years[1]}… The view below still shows ${RESULT.region}.` : "Calculating… The first view of an area can take up to about 15 seconds.");
  if (!RESULT) $("summary").innerHTML = "<p>Calculating the results… The first view of an area can take up to about 15 seconds.</p>";
  try {
    const request = post("/api/analyze", p, CTRL.signal);
    if (!RESULT) Seam.emit("initial-selection", p);
    const r = await request;
    const res = await r.json();
    if (id !== REQ) return;
    RESULT = res;
    RESULT.request = p;
    render();
    setBusy(false, `Showing ${RESULT.region}, ${RESULT.years[0]}–${RESULT.years[1]}.`);
    syncUrl();
    Seam.emit("selection", RESULT);
    if (window.SeamScience) window.SeamScience.sync(RESULT, { calSrc: $("cal-src").value, years: RESULT.years, go, setSub, setEv, toast, META, MONTH_FULL });
  } catch (e) {
    if (id !== REQ || e.name === "AbortError") return;
    setBusy(false);
    window.SeamIntro?.dismiss(true);
    LAST_ERROR = e.message;
    showError(e.message);
    renderSummary();
    Seam.emit("analysis-error", e.message);
  }
}

// Rectangle rules, said before the server is asked: order, ranges and the supported extent.
function boxProblem(b) {
  const v = b.map(Number);
  if (b.some((x) => String(x).trim() === "") || v.some((x) => !Number.isFinite(x))) return "The rectangle needs four numbers: west, south, east and north, in degrees.";
  if (v[0] >= v[2]) return "West must be less than east.";
  if (v[1] >= v[3]) return "South must be less than north.";
  if (v[0] < -180 || v[2] > 180 || v[1] < -90 || v[3] > 90) return "Use longitudes from −180 to 180 and latitudes from −90 to 90.";
  const ex = AREAS ? AREAS.extent : [60, 23, 78.5, 37.5];
  if (v[2] <= ex[0] || v[0] >= ex[2] || v[3] <= ex[1] || v[1] >= ex[3]) return `This rectangle is outside the supported extent (${ex[0]}–${ex[2]}°E, ${ex[1]}–${ex[3]}°N). The data are Pakistan's files only.`;
  return "";
}

// The address bar always holds the view on screen, so it can be bookmarked or shared.
function currentState() {
  if (!RESULT) return null;
  const p = RESULT.request;
  const s = { years: p.years, month: p.month, model: p.model, view: $("view").value, cal: $("cal-src").value,
              day: [Number($("daily-year").value), Number($("daily-month").value)],
              ws: UI.ws, story: UI.story, sub: UI.sub, ev: UI.ev, sats: UI.sats, dn: UI.dn, mapDay: UI.mapDay, mode: UI.mode, scale: UI.scale, season: UI.season,
              experience: IN_BROWSER ? document.documentElement.dataset.experience : "simple",
              basemap: IN_BROWSER ? document.documentElement.dataset.basemap : "terrain" };
  if (p.bbox) s.bbox = p.bbox.map(Number); else s.region = p.region;
  return s;
}
const shareUrl = () => `${location.origin}${location.pathname}?${stateQuery(currentState())}`;
function syncUrl(push) {
  if (!RESULT) return;
  const url = `${location.pathname}?${stateQuery(currentState())}`;
  try {
    if (push && url !== location.pathname + location.search) history.pushState(null, "", url);
    else history.replaceState(null, "", url);
  } catch (_) { /* not allowed here */ }
}
function applyState(s) {
  if (s.bbox) {
    ["bw", "bs", "be", "bn"].forEach((k, i) => { $(k).value = String(s.bbox[i]); });
    $("use-box").checked = true;
    $("box-details").open = true;
  } else if (s.region) {
    $("region").value = s.region;
    $("use-box").checked = false;
  }
  if (s.years) { $("y0").value = String(s.years[0]); $("y1").value = String(s.years[1]); }
  if (s.month) { $("cy").value = String(s.month[0]); $("cm").value = String(s.month[1]); }
  else if (s.years) $("cy").value = String(s.years[1]);  // keep the compare month inside the chosen years
  if (s.model) {
    const r = document.querySelector(`input[name="model"][value="${s.model}"]`);
    if (r) r.checked = true;
  }
  if (s.view) $("view").value = s.view;
  if (s.cal) $("cal-src").value = s.cal;
  if (s.day) {
    $("daily-year").value = String(s.day[0]);
    $("daily-month").value = String(s.day[1]);
    DAILY_SET = true;
  }
  for (const k of ["story", "sub", "ev", "dn", "mode", "scale", "season", "mapDay"]) if (s[k] != null) UI[k] = s[k];
  if (s.sats) UI.sats = s.sats.slice();
  if (s.ws) UI.ws = s.ws;
}

async function copyLink() {
  if (!RESULT) { toast("Wait for the first results; the link holds the view on screen.", { second: true }); return; }
  const url = shareUrl();
  let ok = false;
  try {
    if (navigator.clipboard && window.isSecureContext) { await navigator.clipboard.writeText(url); ok = true; }
  } catch (_) { ok = false; }
  if (!ok) {  // older browsers: copy through a hidden text box
    const t = document.createElement("textarea");
    t.value = url;
    t.setAttribute("readonly", "");
    t.className = "sr";
    document.body.appendChild(t);
    t.select();
    try { ok = document.execCommand("copy"); } catch (_) { ok = false; }
    t.remove();
    $("copy-link").focus();
  }
  // Said only after the copy really worked; otherwise the link is shown to copy by hand.
  toast(ok ? "Link copied. It opens this same view wherever Seamline runs at this address." : `Copy this link by hand: ${url}`, { second: true, sticky: !ok });
}

// ---------- workspaces, stories and tabs ----------
function placeInk() {
  const nav = $("ws-nav"), b = nav.querySelector('[aria-current="page"]'), ink = nav.querySelector(".ws-ink");
  if (!b) return;
  ink.style.width = `${b.offsetWidth - 20}px`;
  ink.style.transform = `translateX(${b.offsetLeft + 10}px)`;
}
function go(ws, opts = {}) {
  if (!WORKSPACES.includes(ws)) return;
  const changed = UI.ws !== ws;
  UI.ws = ws;
  for (const sec of document.querySelectorAll("main > .ws")) sec.hidden = sec.dataset.ws !== ws;
  for (const b of $("ws-nav").querySelectorAll("button")) {
    if (b.dataset.ws === ws) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current");
  }
  placeInk();
  closePop(false);
  hideTip();
  if (opts.story) setStory(opts.story, true);
  if (opts.sub) setSub(opts.sub, true);
  if (opts.ev) setEv(opts.ev, true);
  Seam.emit("ws", ws);
  renderWorkspaceResults();
  if (ws === "calendar" && RESULT && window.SeamScience) window.SeamScience.sync(RESULT, { calSrc: $("cal-src").value, years: RESULT.years, go, setSub, setEv, toast, META, MONTH_FULL });
  if (ws === "evidence" && window.SeamScience) window.SeamScience.renderScience();
  if (window.SeamShowcase) window.SeamShowcase.redraw();
  if (!opts.quiet) syncUrl(changed);
  if (opts.focus) { const h = $(`ws-${ws}`); h.tabIndex = -1; h.focus({ preventScroll: true }); }
}
function setTabs(listId, attr, key) {
  let panel = null;
  for (const b of $(listId).querySelectorAll('[role="tab"]')) {
    const on = b.dataset[attr] === key;
    b.setAttribute("aria-selected", String(on));
    b.tabIndex = on ? 0 : -1;
    const p = $(b.getAttribute("aria-controls"));
    if (p) { p.hidden = !on; if (on) panel = p; }
  }
  return panel;
}
function setStory(key, quiet) {
  if (!STORIES.includes(key)) return;
  UI.story = key;
  setTabs("story-tabs", "story", key);
  $("story-stack").scrollTop = 0;
  if (key === "record" && RESULT) renderInsight();
  if (key === "days" && DAILY) renderDaysPreview();
  if (window.SeamShowcase) window.SeamShowcase.redraw();
  Seam.emit("story", key);
  if (!quiet) syncUrl();
}
function setSub(key, quiet) {
  if (!SUBS.includes(key)) return;
  UI.sub = key;
  setTabs("cal-subnav", "sub", key);
  if (UI.ws === "calendar") renderWorkspaceResults();
  Seam.emit("sub", key);
  if (!quiet) syncUrl();
}
function setEv(key, quiet) {
  if (!EVS.includes(key)) return;
  UI.ev = key;
  setTabs("ev-nav", "ev", key);
  if (UI.ws === "evidence") renderWorkspaceResults();
  if (window.SeamShowcase) window.SeamShowcase.redraw();
  Seam.emit("ev", key);
  if (!quiet) syncUrl();
}
// Arrow keys move along a tab list (one tab stop per list).
function tabKeys(e) {
  const tab = e.target.closest('[role="tab"]');
  if (!tab || !["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) return;
  const tabs = [...tab.parentElement.querySelectorAll('[role="tab"]')];
  let i = tabs.indexOf(tab);
  i = e.key === "Home" ? 0 : e.key === "End" ? tabs.length - 1 : (i + (e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : -1) + tabs.length) % tabs.length;
  e.preventDefault();
  tabs[i].focus();
  tabs[i].click();
}

// ---------- selection sheet and dialog (focus goes in, Escape closes, focus returns) ----------
let SHEET_OPENER = null, DIALOG_OPENER = null, DIALOG_CLOSE = null;
function trapTab(box, e) {
  if (e.key !== "Tab") return;
  const f = [...box.querySelectorAll('button, select, input, a[href], summary, [tabindex="0"]')].filter((n) => !n.disabled && n.getClientRects().length);
  if (!f.length) return;
  const first = f[0], last = f[f.length - 1];
  if (e.shiftKey && (document.activeElement === first || !box.contains(document.activeElement))) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
}
function openSheet(field, opener) {
  SHEET_OPENER = opener || document.activeElement;
  $("controls").hidden = false;
  $("sheet-shade").hidden = false;
  $("ctx-open").setAttribute("aria-expanded", "true");
  const target = field && $("controls").querySelector(`[data-field="${field}"]`);
  if (field === "box") $("box-details").open = true;
  const first = (target && target.querySelector("select, input, summary")) || $("region");
  first.focus();
  if (target) { target.classList.remove("flash"); void target.offsetWidth; target.classList.add("flash"); }
}
function closeSheet() {
  if ($("controls").hidden) return;
  $("controls").hidden = true;
  $("sheet-shade").hidden = true;
  $("ctx-open").setAttribute("aria-expanded", "false");
  if (SHEET_OPENER && document.contains(SHEET_OPENER)) SHEET_OPENER.focus();
  SHEET_OPENER = null;
}
function openDialog(title, html, opener, onClose) {
  DIALOG_OPENER = opener || document.activeElement;
  DIALOG_CLOSE = onClose || null;
  $("dialog-title").textContent = title;
  $("dialog-body").innerHTML = html;
  $("dialog").hidden = false;
  $("dialog-shade").hidden = false;
  $("dialog-title").focus();
  return $("dialog-body");
}
function closeDialog() {
  if ($("dialog").hidden) return;
  $("dialog").hidden = true;
  $("dialog-shade").hidden = true;
  if (DIALOG_CLOSE) { try { DIALOG_CLOSE(); } catch (_) { /* ignore */ } }
  DIALOG_CLOSE = null;
  $("dialog-body").innerHTML = "";
  if (DIALOG_OPENER && document.contains(DIALOG_OPENER)) DIALOG_OPENER.focus();
  DIALOG_OPENER = null;
}

// ---------- render ----------
function renderWorkspaceResults() {
  if (!RESULT) return;
  if (UI.ws === "overview") {
    renderInsight();
    if (UI.story === "days" && DAILY) renderDaysPreview();
  } else if (UI.ws === "calendar") {
    if (UI.sub === "months") { renderSeries(); renderCalendar(); }
    if (UI.sub === "days" && DAILY) renderDailyBase();
    if (UI.sub === "normal") { renderCompare(); renderLatest(); }
  } else if (UI.ws === "evidence") {
    if (UI.ev === "method") renderCalibration();
    if (UI.ev === "experiments") renderEvidence();
  }
}

function render() {
  const r = RESULT;
  closePop(false);
  renderChips();
  renderSummary();
  if (!DAILY_SET) {  // the first time, open the day-by-day view on the compare month; later the reader's choice stays
    $("daily-year").value = String(r.request.month[0]);
    $("daily-month").value = String(r.request.month[1]);
    DAILY_SET = true;
    syncMapMonth();
  }
  loadDaily();
  renderWorkspaceResults();
  renderExport();
  $("warnings").innerHTML = r.warnings.map((w) => `<li>${esc(w)}</li>`).join("");
}

function renderChips() {
  const p = RESULT.request;
  $("ctx-area").textContent = RESULT.region.includes("PK") || RESULT.region === "Pakistan" ? RESULT.region : `${RESULT.region}, PK`;
  $("ctx-years").textContent = `${RESULT.years[0]}–${RESULT.years[1]}`;
  $("ctx-month").textContent = `${MONTH_FULL[p.month[1] - 1]} ${p.month[0]}`;
  $("ctx-model").textContent = RESULT.model;
  for (const b of $("area-list").querySelectorAll("button")) b.setAttribute("aria-pressed", String(!p.bbox && b.dataset.area === p.region));
  $("export-what").textContent = `Exports use the selection on screen: ${RESULT.region}, ${RESULT.years[0]}–${RESULT.years[1]}, model ${RESULT.model}.`;
}

function renderSummary() {
  if (!RESULT) {
    if (LAST_ERROR) $("summary").innerHTML = `<div class="ctx-line"><span class="msg error">${esc(LAST_ERROR)}</span><button type="button" class="more-btn" id="retry-btn">Try again</button></div>`;
    return;
  }
  const r = RESULT, c = r.calibration;
  $("summary-title").textContent = `${r.region}, ${r.years[0]}–${r.years[1]}`;
  const cv = c.supported ? c.cv_agreement.model.wape : null;
  // Visible context pills keep selection, units, source type and support flag readable without ellipsis truncation.
  const s = c.supported
    ? `Detections per month on one scale (S-NPP-equivalent), ${esc(r.passes)}. Model ${esc(r.model)}, calibrated on this area's own 2012–2017 data; in cross-validation it missed S-NPP by ${pct100(cv)}% of the total.`
    : `No harmonised values before 2012 for this area: ${esc(c.reasons.join("; "))}.`;
  const pills = [];
  if (!c.supported) pills.push("No values before 2012 here");
  if (r.box && r.box.share_inside_pakistan < 0.99) pills.push(`Only ${fmt(r.box.share_inside_pakistan * 100)}% of the rectangle is inside Pakistan`);
  if (LAST_ERROR) pills.push("The last request failed; this is the previous selection");
  const metaPills = `<span class="ctx-pill"><b>Units:</b> fire pixels/mo</span>` +
    `<span class="ctx-pill"><b>Scale:</b> S-NPP ref (${esc(r.passes)})</span>` +
    `<span class="ctx-pill ${c.supported ? "is-ok" : "is-warn"}">${c.supported ? `Supported · CV ${pct100(cv)}%` : "Unsupported pre-2012"}</span>`;
  $("summary").innerHTML = `<div class="ctx-line">${pills.map((t) => `<b class="ctx-warn">${esc(t)}</b>`).join("")}${metaPills}<span class="ctx-sentence" title="${s.replace(/"/g, "&quot;")}">${s}</span>` +
    `<button type="button" class="more-btn" id="summary-more" aria-haspopup="dialog">Units, method and ${r.warnings.length} notes</button></div>`;
}
function summaryDialog(opener) {
  const r = RESULT, c = r.calibration;
  const more = `<p><b>Units:</b> ${esc(r.units)}.</p><p><b>Reference scale:</b> ${esc(r.reference)}. S-NPP is another satellite used as the reference, not ground truth.</p>` +
    (c.supported ? `<p><b>Calibration:</b> ${c.fit_months} overlap months (February 2012 to December 2017), this area's own data. Cross-validation error (WAPE) ${pct100(c.cv_agreement.model.wape)}%.</p>` : `<p><b>Calibration:</b> failed the support check (${esc(c.reasons.join("; "))}).</p>`) +
    (r.box ? `<p><b>Rectangle:</b> ${r.box.bbox.map((v) => fmt(v, 2)).join(", ")} (west, south, east, north); ${fmt(r.box.share_inside_pakistan * 100)}% inside Pakistan.</p>` : "") +
    `<h3>Read before using these numbers</h3><ul>${r.warnings.map((w) => `<li>${esc(w)}</li>`).join("")}</ul>`;
  openDialog(`${r.region}, ${r.years[0]}–${r.years[1]}: units, method and notes`, more, opener);
}

function infoBtn(kind, key, what) {
  return `<button type="button" class="info" data-prov="${esc(kind)}" data-key="${esc(key)}" aria-haspopup="dialog" aria-expanded="false" aria-label="Where did this number come from? ${esc(what)}" title="Where did this number come from?">i</button>`;
}

// The opening contrast: what joining raw records shows against the same record on one scale. Values come from
// this selection's own result (r.change); nothing is fixed in the page.
function renderInsight() {
  const r = RESULT, ch = r.change;
  const name = UI.season === "AprMay" ? "April–May" : "October–November";
  $("insight-eyebrow").textContent = `${r.region} · ${name} · MCD14ML (1 km) ↔ VNP14IMG (375 m) · Bridge ${r.model}`;
  const sw = `<div class="season-switch"><div class="seg" role="group" aria-label="Season compared">` +
    [["OctNov", "Oct–Nov"], ["AprMay", "Apr–May"]].map(([k, t]) => `<button type="button" data-season="${k}" aria-pressed="${UI.season === k}">${t}</button>`).join("") + `</div><span><b>${esc(r.region)}</b> · mean season 2012–2021 ÷ 2003–2011</span></div>`;
  if (!ch) {
    $("insight").innerHTML = `<div class="c-box c-harm" style="grid-column:1/-1"><p class="c-k">Not available for these years</p><p>This contrast divides the average season of 2012–2021 by that of 2003–2011, so the selection must include both periods. Choose years from 2003 to at least 2021.</p></div>`;
    $("insight-mini").innerHTML = "";
    if ($("insight-metrics")) $("insight-metrics").innerHTML = "";
    $("insight-note").innerHTML = "";
    return;
  }
  const v = ch[UI.season];
  let harm;
  if (!v.defined) {
    harm = `<p class="c-k">Harmonised (VNP14IMG-eq, ${esc(r.model)})</p><p class="c-num">–<small>not defined</small></p><p class="c-q">${esc(v.reason)}</p>`;
  } else if (!v.point_in_interval) {
    harm = `<p class="c-k">Harmonised (VNP14IMG-eq, ${esc(r.model)}) ${infoBtn("change", UI.season, `${name} change`)}</p><p class="c-num">${fmt(v.H_interval[0], 2)}–${fmt(v.H_interval[1], 2)}×<small>80% CV range</small></p>` +
      `<p class="c-q">${esc(r.region)}, ${name} (2012–2021 ÷ 2003–2011). Point estimate (${fmt(v.H, 2)}×) lies outside the cross-validation interval. Read the range.</p>`;
  } else {
    harm = `<p class="c-k">Harmonised (VNP14IMG-eq, ${esc(r.model)}) ${infoBtn("change", UI.season, `${name} change`)}</p><p class="c-num">${fmt(v.H, 2)}×<small>80% CV range ${fmt(v.H_interval[0], 2)}–${fmt(v.H_interval[1], 2)}×</small></p>` +
      `<p class="c-q">Pre-2012 Aqua <code>MCD14ML</code> (1 km) bridged to S-NPP <code>VNP14IMG</code> (375 m). Unconverted Aqua <code>MCD14ML</code> alone: ${fmt(v.aqua, 2)}×.</p>`;
  }
  const snpp = v.naive_snpp == null ? "" : ` MODIS→<code>VNP14IMG</code> alone: ${fmt(v.naive_snpp, 2)}×.`;
  $("insight").innerHTML = sw.replace('class="season-switch"', 'class="season-switch" style="grid-column:1/-1"') +
    `<div class="c-box c-naive"><p class="c-k">Uncalibrated stitch (MCD14ML → VIIRS)</p><p class="c-num">${fmt(v.naive, 2)}×</p>` +
    `<p>All MODIS <code>MCD14ML</code> (C6.1, 1 km, ~4–40 MW floor) to 2011, then VIIRS <code>VNP14IMG</code>/<code>VJ114IMG</code> (C2, 375 m, ~0.5 MW floor). Diagnostic only.${snpp}</p></div>` +
    `<div class="c-box c-harm">${harm}</div>`;
  const e = META.evidence;
  const covPct = e && e.available ? `${fmt(e.interval_coverage * 100)}%` : "59%";
  const cvWape = r.calibration && r.calibration.supported && r.calibration.cv_agreement ? `${pct100(r.calibration.cv_agreement.model.wape)}%` : "13%";
  const frpInfo = window.SeamMap && window.SeamMap.frpSummary ? window.SeamMap.frpSummary() : null;
  const frpTag = frpInfo && frpInfo.count > 0
    ? `Σ ${fmt(frpInfo.sumMw, 0)} MW · med ${fmt(frpInfo.medMw, 1)} MW (p90 ${fmt(frpInfo.p90Mw, 1)} MW)`
    : `VNP14IMG ~0.5 MW vs MCD14ML ~4–40 MW floor`;
  const ciStr = v.defined && v.H_interval ? `${fmt(v.H_interval[0], 2)}–${fmt(v.H_interval[1], 2)}×` : "–";
  let tableRows = `<tr class="row-naive"><th scope="row">Naive Stitch (MCD14ML→VIIRS)</th><td><b>${fmt(v.naive, 2)}×</b></td><td>Uncalibrated</td><td><span class="val-tag is-diag">Diagnostic only</span></td></tr>`;
  if (r.region === "Punjab" && UI.season === "OctNov" && e && e.sensitivity_octnov) {
    const modelLabels = {
      M1: "M1 (Single Ratio)",
      M2: "M2 (Monthly)",
      M3: "M3 (Pass-Split D/N)",
      M4: "M4 (Log-Linear)",
    };
    for (const [m, x] of Object.entries(e.sensitivity_octnov)) {
      const isSel = m === r.model;
      const mCi = isSel ? ciStr : "Not available";
      const validTxt = isSel ? `Selected · CV ${cvWape} · ${covPct} interval coverage` : "Saved E03 sensitivity";
      tableRows += `<tr class="${isSel ? "row-sel" : ""}"><th scope="row">${esc(modelLabels[m] || m)}</th><td><b>${fmt(x.ratio, 2)}×</b></td><td>${mCi}</td><td><span class="val-tag is-valid">${validTxt}</span></td></tr>`;
    }
  } else {
    tableRows += `<tr class="row-sel"><th scope="row">${esc(r.model)} (Harmonised Bridge)</th><td><b>${v.defined ? fmt(v.H, 2) + "×" : "–"}</b></td><td>${ciStr}</td><td><span class="val-tag is-valid">${r.calibration && r.calibration.supported ? `✓ Valid (CV ${cvWape} · ${covPct} PI)` : "Unsupported pre-2012"}</span></td></tr>`;
  }
  tableRows += `<tr><th scope="row">Aqua MCD14ML (1 km Control)</th><td><b>${fmt(v.aqua, 2)}×</b></td><td>Single-sensor</td><td><span class="val-tag is-ref">✓ Ref (${frpTag})</span></td></tr>`;
  if ($("insight-metrics")) {
    $("insight-metrics").innerHTML = `<table class="telem-table"><thead><tr><th scope="col">Model</th><th scope="col">Value</th><th scope="col">Rough range</th><th scope="col">Support</th></tr></thead><tbody>${tableRows}</tbody></table>`;
  }
  const cov = e && e.available ? `In the held-out test such ranges caught only ${fmt(e.interval_coverage * 100)}% of months, so read them as too narrow. ` : "";
  let note = `"Rough range": the nominal 80% range from this area's own cross-validation. ${cov}` +
    `Aqua alone is a consistency check, not separate proof: harmonised years before 2012 are calculated from Aqua.`;
  if (r.region === "Punjab" && UI.season === "OctNov" && e && e.sensitivity_octnov && r.model === e.selected) {
    const s = Object.entries(e.sensitivity_octnov);
    const vals = s.map(([, x]) => x.ratio);
    note = `<b>All four frozen models give ${fmt(Math.min(...vals), 2)}–${fmt(Math.max(...vals), 2)}×</b> (${s.map(([m, x]) => `${m} ${fmt(x.ratio, 2)}×`).join(", ")}; E03). ` +
      `The selected ${esc(e.selected)} is the highest, and its early years extrapolate below the calibration range, so the lower end is more plausible. ` + note;
  }
  $("insight-note").innerHTML = note;
  miniRecord($("insight-mini"), aggregate(UI.season), name);
}

// A compact preview of the long record for the story panel: harmonised against the naive stitch, log scale, with 80% CV band.
function miniRecord(host, pts, name) {
  host.innerHTML = "";
  const W = Math.max(300, Math.round(host.clientWidth || 600)), H = W < 420 ? 122 : 114, L = 58, R = 98, T = 18, B = 18;
  const vals = pts.flatMap((p) => [p.H, p.H_lo, p.H_hi, p.naive]).filter((v) => v != null && v > 0);
  if (!vals.length) return;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `${name} season totals by year for ${RESULT.region}, Log-Scale (1,000 to 10,000+) with 2012 satellite transition marker and 80% CI shaded band.` }, host);
  const lo = Math.min(800, Math.min(...vals) * 0.8), hi = Math.max(12000, Math.max(...vals) * 1.25), n = pts.length;
  const ly = (v) => T + (H - T - B) * (1 - (Math.log10(Math.max(v, lo)) - Math.log10(lo)) / (Math.log10(hi) - Math.log10(lo)));
  const lx = (i) => L + (W - L - R) * (n === 1 ? 0.5 : i / (n - 1));
  el("text", { x: 4, y: 11, "text-anchor": "start", style: `fill:${css("--ink2")};font:700 9.5px ${css("--mono")}` }, svg).textContent = "Log-Scale";
  const era = pts.findIndex((p) => p.x >= 2012);
  if (era > 0) {
    const x0 = (lx(era - 1) + lx(era)) / 2;
    el("rect", { x: x0, y: T, width: W - R - x0, height: H - T - B, fill: css("--era") }, svg);
    el("line", { x1: x0, x2: x0, y1: T - 2, y2: H - B, stroke: css("--accent"), "stroke-width": 1.3, "stroke-dasharray": "3 2" }, svg);
    el("text", { x: x0 + 5, y: T + 10, style: `fill:${css("--accent-ink")};font:600 9.5px ${css("--font")}` }, svg).textContent = "2012 Satellite Transition / Handover";
  }
  // Pre-2012 80% cross-validation uncertainty band (H_lo .. H_hi)
  const bandPts = pts.map((p, i) => [i, p]).filter(([, p]) => p.H_lo != null && p.H_hi != null && p.H_lo > 0 && p.H_hi > 0 && p.x <= 2012);
  if (bandPts.length > 1) {
    const topD = bandPts.map(([i, p], k) => `${k ? "L" : "M"}${lx(i).toFixed(1)},${ly(p.H_hi).toFixed(1)}`).join("");
    const botD = [...bandPts].reverse().map(([i, p]) => `L${lx(i).toFixed(1)},${ly(p.H_lo).toFixed(1)}`).join("");
    el("path", { d: `${topD}${botD}Z`, fill: css("--band") }, svg);
    el("path", { d: topD, fill: "none", stroke: css("--harm"), "stroke-width": 1.0, "stroke-dasharray": "2 2", opacity: "0.7" }, svg);
    el("path", { d: bandPts.map(([i, p], k) => `${k ? "L" : "M"}${lx(i).toFixed(1)},${ly(p.H_lo).toFixed(1)}`).join(""), fill: "none", stroke: css("--harm"), "stroke-width": 1.0, "stroke-dasharray": "2 2", opacity: "0.7" }, svg);
    const mid = bandPts[Math.floor(bandPts.length / 2)];
    el("text", { x: lx(mid[0]), y: Math.max(T + 11, ly(mid[1].H_hi) - 4), "text-anchor": "middle", style: `fill:${css("--harm")};font:600 9.5px ${css("--font")}` }, svg).textContent = "80% CI (1.66–2.02×)";
  }
  for (let e = Math.ceil(Math.log10(lo)); e <= Math.floor(Math.log10(hi)); e++) {
    const y = ly(10 ** e);
    el("line", { x1: L, x2: W - R, y1: y, y2: y, stroke: css("--grid") }, svg);
    const lbl = 10 ** e >= 10000 ? `${fmt(10 ** e)}+` : fmt(10 ** e);
    el("text", { x: L - 6, y: y + 4, "text-anchor": "end", style: `fill:${css("--ink2")};font:600 10px ${css("--mono")}` }, svg).textContent = lbl;
  }
  const line = (key, color, dash, width) => {
    let d = "", pen = false, last = null;
    pts.forEach((p, i) => { if (p[key] == null) { pen = false; return; } d += `${pen ? "L" : "M"}${lx(i).toFixed(1)},${ly(p[key]).toFixed(1)}`; pen = true; last = [lx(i), ly(p[key])]; });
    const path = el("path", { d, fill: "none", stroke: color, "stroke-width": width, "stroke-linejoin": "round", "stroke-linecap": "round" }, svg);
    if (dash) path.setAttribute("stroke-dasharray", dash);
    else drawIn(path);
    return last;
  };
  const a = line("naive", css("--naive"), "6 4", 1.9), b = line("H", css("--harm"), "", 2.4);
  const lab = (pt, text, color, weight) => { if (pt) el("text", { x: pt[0] + 6, y: pt[1] + 4, style: `fill:${color};font:${weight} 11.5px ${css("--font")}` }, svg).textContent = text; };
  if (a && b && Math.abs(a[1] - b[1]) < 13) b[1] = a[1] + 13;
  lab(a, "Naive stitch", css("--naive"), 600);
  lab(b, "Harmonised", css("--harm"), 700);
  for (const i of [0, n - 1]) el("text", { x: lx(i), y: H - 3, "text-anchor": i ? "end" : "start", style: `fill:${css("--muted")};font:10.5px ${css("--mono")}` }, svg).textContent = pts[i].label;
}

// Chart lines draw in once, on a real value path (Motion: Full only). Axes and labels never move.
function drawIn(path) {
  if (motionMode() !== "full" || !path.getTotalLength) return;
  let len = 0;
  try { len = path.getTotalLength(); } catch (_) { return; }
  if (!len) return;
  path.style.strokeDasharray = `${len}`;
  path.style.strokeDashoffset = `${len}`;
  path.getBoundingClientRect();
  path.style.transition = `stroke-dashoffset ${css("--t-chart") || "320ms"} ${css("--ease-out") || "ease-out"}`;
  path.style.strokeDashoffset = "0";
  setTimeout(() => { path.style.strokeDasharray = ""; path.style.strokeDashoffset = ""; path.style.transition = ""; }, 500);
}

function aggregate(view) {
  const ms = RESULT.months;
  if (view === "month") return ms.map((m) => ({ x: m.month, label: m.month, H: m.H, H_lo: m.H_lo, H_hi: m.H_hi, naive: m.naive, aqua: m.aqua, src: m.H_source, srcs: [m.H_source], flag: m.H_flag }));
  const want = view === "OctNov" ? [10, 11] : view === "AprMay" ? [4, 5] : [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];
  const byYear = new Map();
  for (const m of ms) {
    const [y, mo] = m.month.split("-").map(Number);
    if (!want.includes(mo)) continue;
    if (!byYear.has(y)) byYear.set(y, []);
    byYear.get(y).push(m);
  }
  const incomplete = (f) => /(partial_period|partial_record|outside_record|no_usable_support)/.test(f || "");
  const sum = (arr, k, fk) => arr.some((m) => m[k] == null || (fk && incomplete(m[fk]))) ? null : arr.reduce((a, m) => a + m[k], 0);
  return [...byYear.entries()].filter(([, arr]) => arr.length === want.length).map(([y, arr]) => {
    const srcs = [...new Set(arr.map((m) => m.H_source))];
    return {
      x: y, label: String(y), H: sum(arr, "H", "H_flag"), H_lo: sum(arr, "H_lo", "H_flag"), H_hi: sum(arr, "H_hi", "H_flag"), naive: sum(arr, "naive", "naive_flag"), aqua: sum(arr, "aqua", "aqua_flag"),
      src: srcs.join(" and "), srcs, flag: arr.map((m) => m.H_flag).filter(Boolean).join(", "),
    };
  });
}

function ensureAfter(anchorId, id, tag, cls) {  // a small element the series card needs, added once next to the chart
  let n = $(id);
  if (!n) {
    n = document.createElement(tag);
    n.id = id;
    if (cls) n.className = cls;
    $(anchorId).insertAdjacentElement("afterend", n);
  }
  return n;
}

// Record over time: harmonised (solid, heavy), naive stitch (dashed), Aqua only (thin). Log or linear, always labelled.
function renderSeries() {
  const view = $("view").value;
  const pts = aggregate(view);
  const host = $("series");
  host.innerHTML = "";
  hideTip();
  const viewName = $("view").selectedOptions[0].text;
  const LOG = UI.scale !== "lin";
  const W = Math.max(340, Math.round(host.clientWidth || 760)), H = W < 560 ? 310 : 372, L = 62, R = 14, T = 12, B = 58;  // real pixels, so labels keep their size on a phone
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", tabindex: "0",
    "aria-label": `Line chart of ${viewName} for ${RESULT.region}, ${LOG ? "logarithmic" : "linear"} scale: harmonised, naive stitch and Aqua only. A band under the chart shows where each harmonised value comes from. Use the left and right arrow keys to read each point.` }, host);
  const colors = { H: css("--harm"), naive: css("--naive"), aqua: css("--aqua") };
  const live = ensureAfter("series", "series-live", "p", "sr");
  live.setAttribute("aria-live", "polite");
  const relLegend = ensureAfter("series-live", "rel-legend", "div", "legend rel-legend");
  const vals = pts.flatMap((p) => [p.H, p.H_lo, p.H_hi, p.naive, p.aqua]).filter((v) => v != null && v > 0);
  if (!vals.length) {
    el("text", { x: L, y: H / 2 }, svg).textContent = "No detections in this selection. No detection is not no burning.";
    relLegend.innerHTML = "";
    if ($("series-table")) $("series-table").innerHTML = "";
    return;
  }
  const lo = LOG ? Math.max(0.5, Math.min(...vals) * 0.8) : 0, hi = Math.max(...vals) * (LOG ? 1.25 : 1.06);
  const ly = LOG
    ? (v) => T + (H - T - B) * (1 - (Math.log10(Math.max(v, lo)) - Math.log10(lo)) / (Math.log10(hi) - Math.log10(lo)))
    : (v) => T + (H - T - B) * (1 - v / hi);
  const n = pts.length;
  const lx = (i) => L + (W - L - R) * (n === 1 ? 0.5 : i / (n - 1));
  const defs = el("defs", {}, svg);
  const pat = el("pattern", { id: "rel-hatch", width: 5, height: 5, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, defs);
  el("rect", { width: 5, height: 5, fill: css("--surface") }, pat);
  el("line", { x1: 0, y1: 0, x2: 0, y2: 5, stroke: colors.H, "stroke-width": 1.6 }, pat);
  // VIIRS era shading
  const eraIdx = pts.findIndex((p) => (view === "month" ? p.x >= "2012-02" : p.x >= 2012));
  if (eraIdx >= 0) {
    const x0 = eraIdx === 0 ? L : (lx(eraIdx - 1) + lx(eraIdx)) / 2;
    el("rect", { x: x0, y: T, width: W - R - x0, height: H - T - B, fill: css("--era") }, svg);
    el("text", { x: x0 + 6, y: T + 14 }, svg).textContent = "VIIRS era: S-NPP observed";
  }
  // The naive stitch adds a second VIIRS satellite (NOAA-20) from April 2018: its second jump.
  const n20 = pts.findIndex((p) => (view === "month" ? p.x >= "2018-04" : p.x >= 2018));
  const n20x = n20 > 0 ? (lx(n20 - 1) + lx(n20)) / 2 : null;
  if (n20x != null) el("line", { x1: n20x, x2: n20x, y1: T, y2: H - B, stroke: css("--naive"), "stroke-width": 1, "stroke-dasharray": "4 3" }, svg);
  // grid and y ticks
  const ticks = [];
  if (LOG) {
    for (let e = Math.floor(Math.log10(lo)); e <= Math.ceil(Math.log10(hi)); e++) for (const m of [1, 2, 5]) {
      const v = m * 10 ** e;
      if (v >= lo && v <= hi) ticks.push([v, m === 1, m !== 5 || hi / lo < 50]);
    }
  } else {
    const raw = hi / 5, p10 = 10 ** Math.floor(Math.log10(raw)), m = raw / p10, step = (m <= 1 ? 1 : m <= 2 ? 2 : m <= 5 ? 5 : 10) * p10;
    for (let v = 0; v <= hi; v += step) ticks.push([v, true, true]);
  }
  let lastTickY = 1e9;
  for (const [v, major, label] of ticks) {
    const y = ly(v);
    el("line", { x1: L, x2: W - R, y1: y, y2: y, stroke: css("--grid"), "stroke-width": major ? 1 : 0.5 }, svg);
    if (label && Math.abs(y - lastTickY) >= 14 && y >= T + 4 && y <= H - B + 4) {
      el("text", { x: L - 6, y: y + 4, "text-anchor": "end" }, svg).textContent = fmt(v);
      lastTickY = y;
    }
  }
  const yl = el("text", { x: 12, y: T + (H - T - B) / 2, "text-anchor": "middle", transform: `rotate(-90 12 ${T + (H - T - B) / 2})` }, svg);
  yl.textContent = `Detections (${LOG ? "log scale" : "linear scale"})`;
  el("line", { x1: L, x2: W - R, y1: H - B, y2: H - B, stroke: css("--axis") }, svg);
  const step = Math.max(1, Math.ceil(n / 12));
  const minGapPx = view === "month" ? 54 : 44;
  let lastTickX = -1e9;
  const endX = lx(n - 1);
  pts.forEach((p, i) => {
    const x = lx(i);
    const isLast = i === n - 1;
    const okStep = (i % step === 0 || isLast) && (x - lastTickX >= minGapPx) && (isLast || (endX - x >= minGapPx));
    if (okStep) {
      const anchor = isLast && x + 18 > W - 4 ? "end" : "middle";
      const t = el("text", { x, y: H - B + 18, "text-anchor": anchor }, svg);
      t.textContent = view === "month" ? p.label.slice(0, 4) + (p.label.endsWith("-01") ? "" : "-" + p.label.slice(5)) : p.label;
      lastTickX = x;
    }
  });
  // interval band (modelled points only)
  const band = pts.map((p, i) => [i, p]).filter(([, p]) => p.H_lo != null && p.H_hi != null && p.H_hi > p.H_lo);
  if (band.length) {
    const d = band.map(([i, p], k) => `${k ? "L" : "M"}${lx(i)},${ly(p.H_hi)}`).join("") +
      band.slice().reverse().map(([i, p]) => `L${lx(i)},${ly(p.H_lo)}`).join("") + "Z";
    el("path", { d, fill: css("--band"), stroke: "none" }, svg);
  }
  const STYLE = { H: { w: 2.6, dash: "" }, naive: { w: 2, dash: "7 4" }, aqua: { w: 1.6, dash: "" } };
  const line = (key) => {
    let d = "", pen = false;
    pts.forEach((p, i) => {
      if (p[key] == null) { pen = false; return; }
      d += `${pen ? "L" : "M"}${lx(i)},${ly(p[key])}`;
      pen = true;
    });
    const path = el("path", { d, fill: "none", stroke: colors[key], "stroke-width": STYLE[key].w, "stroke-linejoin": "round" }, svg);
    if (STYLE[key].dash) path.setAttribute("stroke-dasharray", STYLE[key].dash); else if (key === "H") drawIn(path);
    if (view !== "month") pts.forEach((p, i) => {
      if (p[key] == null) return;
      // Marker shapes differ as well as colours: harmonised a dot, naive a diamond, Aqua a square.
      const x = lx(i), y = ly(p[key]), a = { fill: colors[key], stroke: css("--surface"), "stroke-width": 1.4 };
      if (key === "H") el("circle", { cx: x, cy: y, r: 3.6, ...a }, svg);
      else if (key === "naive") el("path", { d: `M${x},${y - 4.4}L${x + 4.4},${y}L${x},${y + 4.4}L${x - 4.4},${y}Z`, ...a }, svg);
      else el("rect", { x: x - 3, y: y - 3, width: 6, height: 6, ...a }, svg);
    });
  };
  line("naive"); line("aqua"); line("H");
  // Linked highlight from the selected Calendar cell (CAL_SEL) to the corresponding trend point on Record over time.
  const activeCalKey = CAL_SEL || (RESULT && RESULT.request && RESULT.request.month ? `${RESULT.request.month[0]}-${RESULT.request.month[1]}` : null);
  if (activeCalKey) {
    const [selY, selM] = activeCalKey.split("-").map(Number);
    const linkedIdx = pts.findIndex((p) => (view === "month" ? p.x === ym(selY, selM) : p.x === selY));
    if (linkedIdx >= 0) {
      const cx = lx(linkedIdx), lp = pts[linkedIdx];
      const yv = lp.H != null ? lp.H : lp.naive != null ? lp.naive : lp.aqua;
      el("line", { class: "series-cal-link", x1: cx, x2: cx, y1: T, y2: H - B, stroke: css("--select-bg"), "stroke-width": 1.5, "stroke-dasharray": "3 3" }, svg);
      if (yv != null && (!LOG || yv > 0)) {
        el("circle", { class: "series-cal-ring", cx, cy: ly(yv), r: 6.8, fill: "none", stroke: css("--select-bg"), "stroke-width": 2.2 }, svg);
      }
    }
  }
  // Label drawn over the lines, with a halo in the background colour so it stays readable.
  const halo = `paint-order:stroke;stroke:${css("--surface")};stroke-width:4px;stroke-linejoin:round`;
  if (n20x != null) {
    const t = el("text", { x: n20x + 6, y: H - B - 8, style: halo }, svg);
    t.textContent = "NOAA-20 added to the naive stitch";
    // Near the right edge the chart would cut the label off, so put it on the left of the line instead.
    if (n20x + 6 + t.getComputedTextLength() > W - R) { t.setAttribute("x", n20x - 6); t.setAttribute("text-anchor", "end"); }
  }
  else if (n20 === 0) el("text", { x: L + 6, y: H - B - 8, style: halo }, svg).textContent = "Naive stitch includes NOAA-20 here (from April 2018)";
  // Reliability band: where each harmonised value comes from (solid: observed S-NPP; hatched: converted from
  // Aqua; grey: missing or partly covered). Shapes differ as well as colours.
  const bandY = H - B + 30, bandH = 11;
  el("text", { x: L - 6, y: bandY + 10, "text-anchor": "end" }, svg).textContent = "Source";
  pts.forEach((p, i) => {
    const x0 = i === 0 ? L : (lx(i - 1) + lx(i)) / 2, x1 = i === n - 1 ? W - R : (lx(i) + lx(i + 1)) / 2;
    const c = relClass(p), box = { x: x0, y: bandY, width: Math.max(0.6, x1 - x0), height: bandH };
    if (c === "observed") el("rect", { ...box, fill: colors.H }, svg);
    else if (c === "gap") el("rect", { ...box, fill: css("--nodata"), stroke: css("--muted"), "stroke-width": 0.8 }, svg);
    else el("rect", { ...box, fill: "url(#rel-hatch)", stroke: colors.H, "stroke-width": 0.8 }, svg);
  });
  $("series-legend").innerHTML =
    `<span style="color:${colors.H}"><i class="swatch"></i><span style="color:var(--ink2)">● Harmonised, S-NPP-equivalent</span></span>` +
    `<span style="color:${colors.naive}"><i class="swatch dashed"></i><span style="color:var(--ink2)">◆ Naive stitch, comparison only (all MODIS, then all VIIRS; NOAA-20 from 2018)</span></span>` +
    `<span style="color:${colors.aqua}"><i class="swatch thin"></i><span style="color:var(--ink2)">■ Aqua MODIS only</span></span>`;
  // The band's key, and the same information as text (also read by screen readers).
  const runs = relRuns(pts);
  const said = ["observed", "converted", "mixed", "gap"].map((c) => {
    const rs = runs.filter((r) => r.c === c);
    if (!rs.length) return "";
    const spans = rs.slice(0, 5).map((r) => (r.from === r.to ? r.from : `${r.from} to ${r.to}`));
    return `${REL_TEXT[c].split(" (")[0]}: ${spans.join(", ")}${rs.length > 5 ? ` and ${rs.length - 5} more` : ""}`;
  }).filter(Boolean).join("; ");
  relLegend.innerHTML = `<span><i class="rel-key rel-observed"></i>Observed S-NPP</span>` +
    `<span><i class="rel-key rel-converted"></i>Converted from Aqua: tested on whole months only; its rough range was too narrow in testing</span>` +
    `<span><i class="rel-key rel-gap"></i>Missing or partly covered</span>` +
    `<span class="rel-said">Source of each harmonised point: ${esc(said)}.</span>`;
  // The same numbers as a table (the chart's text alternative; shown on request).
  const fresh = !$("series-table");
  const tbl = ensureAfter("rel-legend", "series-table", "div", "table-wrap");
  if (fresh) tbl.hidden = !($("series-table-btn") && $("series-table-btn").getAttribute("aria-expanded") === "true");
  const unit = view === "month" ? "Month" : "Year";
  tbl.innerHTML = `<table><caption class="note" style="caption-side:bottom;text-align:left">${esc(viewName)}, ${esc(RESULT.region)}: detections${view === "month" ? " per month" : ", summed over the months shown"}. Each satellite is counted on its own; the naive stitch adds satellites on purpose, for comparison.</caption>` +
    `<thead><tr><th scope="col">${unit}</th><th scope="col">Harmonised</th><th scope="col">Rough range</th><th scope="col">Naive stitch</th><th scope="col">Aqua only</th><th scope="col" style="text-align:left">Source of the harmonised value</th></tr></thead><tbody>` +
    pts.map((p) => {
      const rc = relClass(p);
      const why = rc === "gap" && p.flag ? `partly covered: ${p.flag}` : rc === "gap" ? `missing: ${p.src}` : REL_TEXT[rc].split(" (")[0];
      const iv = p.H_lo != null && p.H_hi > p.H_lo ? `${fmt(p.H_lo)}–${fmt(p.H_hi)}` : "";
      return `<tr><th scope="row">${esc(p.label)}</th><td>${fmt(p.H)}</td><td>${iv}</td><td>${fmt(p.naive)}</td><td>${fmt(p.aqua)}</td><td style="text-align:left">${esc(why)}</td></tr>`;
    }).join("") + "</tbody></table>";
  // hover layer: crosshair + tooltip; the arrow keys do the same without a mouse
  const cross = el("line", { y1: T, y2: H - B, stroke: css("--ink2"), "stroke-width": 1, visibility: "hidden" }, svg);
  const hit = el("rect", { x: L, y: T, width: W - L - R, height: H - T - B + 44, fill: "transparent" }, svg);
  const describe = (p) => {
    const iv = p.H_lo != null && p.H_hi > p.H_lo ? ` (rough range ${fmt(p.H_lo)}–${fmt(p.H_hi)})` : "";
    const rc = relClass(p);
    const why = rc === "gap" && p.flag ? `partly covered: ${p.flag}` : rc === "gap" ? `missing: ${p.src}` : REL_TEXT[rc];
    return { html: `<b>${esc(p.label)}</b><br>Harmonised: ${fmt(p.H)}${iv}<br>Naive stitch: ${fmt(p.naive)}<br>Aqua only: ${fmt(p.aqua)}<br><span style="opacity:.8">Source: ${esc(why)}</span>`,
             text: `${p.label}: harmonised ${fmt(p.H)}${iv}; naive stitch ${fmt(p.naive)}; Aqua only ${fmt(p.aqua)}. Source: ${why}.` };
  };
  const point = (i) => {
    cross.setAttribute("x1", lx(i)); cross.setAttribute("x2", lx(i)); cross.setAttribute("visibility", "visible");
  };
  const at = (evt) => {
    const box = svg.getBoundingClientRect();
    const x = ((evt.clientX - box.left) / box.width) * W;
    return Math.max(0, Math.min(n - 1, Math.round(((x - L) / (W - L - R)) * (n - 1))));
  };
  hit.addEventListener("pointermove", (evt) => { const i = at(evt); point(i); showTip(describe(pts[i]).html, evt); });
  hit.addEventListener("pointerleave", () => { cross.setAttribute("visibility", "hidden"); hideTip(); });
  let ki = -1;
  const keyShow = (i) => {
    ki = Math.max(0, Math.min(n - 1, i));
    point(ki);
    const box = svg.getBoundingClientRect(), p = pts[ki];
    const yv = p.H != null ? p.H : p.naive != null ? p.naive : p.aqua;
    const cy = yv != null ? ly(yv) : T + (H - T - B) / 2;
    showTip(describe(p).html, { clientX: box.left + (lx(ki) / W) * box.width, clientY: box.top + (cy / H) * box.height });
    live.textContent = describe(p).text;
  };
  svg.addEventListener("keydown", (evt) => {
    const k = evt.key;
    if (k === "ArrowRight" || k === "ArrowLeft" || k === "Home" || k === "End") {
      evt.preventDefault();
      keyShow(k === "Home" ? 0 : k === "End" ? n - 1 : ki < 0 ? (k === "ArrowRight" ? 0 : n - 1) : ki + (k === "ArrowRight" ? 1 : -1));
    } else if (k === "Escape") { cross.setAttribute("visibility", "hidden"); hideTip(); }
  });
  svg.addEventListener("blur", () => { cross.setAttribute("visibility", "hidden"); hideTip(); });
  $("series-note").textContent = `${LOG ? "Log scale: equal steps mean equal ratios. " : "Linear scale from zero. "}Grey band: rough range for modelled years (before Feb 2012), too narrow in testing. Shaded area: VIIRS era. Dashed vertical line: NOAA-20 joins the naive stitch. ${RESULT.years[1] >= 2026 ? "Standard country archive through Dec 2025; 2026 uses the cached current supplement (partial or untyped NRT months are flagged)." : "The record ends in December 2025."}`;
}

// Seasonal calendar: colour carries magnitude (sequential, log steps), a corner triangle carries the anomaly,
// hatching carries partial coverage, and the no-data colour is never a zero. Numbers show on focus and in the table.
let CAL_SEL = null;  // "year-month" of the selected cell
function renderCalendar() {
  const src = $("cal-src").value;
  const cells = RESULT.calendar[src];
  const years = [...new Set(cells.map((c) => c.year))];
  const host = $("calendar");
  host.innerHTML = "";
  hideTip();
  const avail = Math.max(320, Math.round(host.clientWidth || 670));
  const L = 44, T = 20, cw = Math.max(22, Math.floor((avail - L - 2) / 12)), ch = 17, W = L + cw * 12 + 2, H = T + ch * years.length + 2;
  const srcName = $("cal-src").selectedOptions[0].text;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "group", "aria-label": `Calendar of monthly detections for ${RESULT.region}, ${srcName}. Arrow keys move between months; Enter selects one. 'Show as table' lists every number.` }, host);
  const defs = el("defs", {}, svg);
  const pat = el("pattern", { id: "hatch", width: 5, height: 5, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, defs);
  el("line", { x1: 0, y1: 0, x2: 0, y2: 5, stroke: css("--ink"), "stroke-width": 1.1, "stroke-opacity": 0.55 }, pat);
  const max = Math.max(1, ...cells.map((c) => c.value || 0));
  const steps = 7;
  const bin = (v) => Math.min(steps - 1, Math.floor(Math.sqrt(v / max) * steps));   // square-root steps: seasons stand out, quiet months stay light
  const seq = [...Array(steps).keys()].map((i) => css(`--seq-${i}`));
  const dark = css("color-scheme") === "dark";
  MONTHS.forEach((m, i) => { el("text", { x: L + cw * i + cw / 2, y: 13, "text-anchor": "middle" }, svg).textContent = m; });
  years.forEach((y, j) => { if (j % 2 === 0 || years.length < 14) el("text", { x: L - 6, y: T + ch * j + 13, "text-anchor": "end" }, svg).textContent = y; });
  const key = (c) => `${c.year}-${c.month}`;
  const said = (c) => {
    const cls = c.class ? `${c.class === "typical" ? "typical for" : c.class} this area's normal` : "not classed";
    return c.value == null ? `${MONTH_FULL[c.month - 1]} ${c.year}: no data${c.flag ? ` (${c.flag})` : ""}`
      : `${MONTH_FULL[c.month - 1]} ${c.year}: ${fmt(c.value)} detections, ${cls}${c.flag ? `, coverage: ${c.flag}` : ""}`;
  };
  const nodes = new Map();
  if (!cells.some((c) => key(c) === CAL_SEL)) {
    const defKey = `${RESULT.request.month[0]}-${RESULT.request.month[1]}`;
    CAL_SEL = cells.some((c) => key(c) === defKey) ? defKey : null;
  }
  for (const c of cells) {
    const x = L + cw * (c.month - 1), y = T + ch * years.indexOf(c.year);
    const g = el("g", { class: "cal-cell", role: "button", tabindex: "-1", "aria-label": said(c), "aria-selected": String(key(c) === CAL_SEL), "data-k": key(c) }, svg);
    const b = c.value == null ? -1 : bin(c.value);
    el("rect", { class: "c-bg", x: x + 1, y: y + 1, width: cw - 2, height: ch - 2, rx: 2, fill: b < 0 ? css("--nodata") : seq[b] }, g);
    if (c.flag) el("rect", { x: x + 1, y: y + 1, width: cw - 2, height: ch - 2, rx: 2, fill: "url(#hatch)", "pointer-events": "none" }, g);
    const strong = b >= 4;
    const mark = b < 0 ? css("--ink2") : (strong !== dark ? "#ffffff" : "#0b0b0b");
    if (c.value == null) el("text", { x: x + cw / 2, y: y + 13, "text-anchor": "middle", style: `fill:${mark}` }, g).textContent = "–";
    else if (c.class === "above") el("path", { d: `M${x + cw - 12},${y + 12}l4.5,-7l4.5,7z`, fill: mark, "pointer-events": "none" }, g);
    else if (c.class === "below") el("path", { d: `M${x + cw - 12},${y + 5}l4.5,7l4.5,-7z`, fill: mark, "pointer-events": "none" }, g);
    g.addEventListener("pointermove", (evt) => {
      const cls = c.class ? `${c.class} normal` : "not classed";
      showTip(`<b>${MONTH_FULL[c.month - 1]} ${c.year}</b><br>${c.value == null ? "No data" : fmt(c.value) + " detections"}<br>Median of other years: ${fmt(c.median_other_years)} (${c.n_years} years)<br>${esc(cls)}${c.flag ? `<br><span style="opacity:.8">Coverage: ${esc(c.flag)}</span>` : ""}`, evt);
    });
    g.addEventListener("pointerleave", hideTip);
    g.addEventListener("click", () => calSelect(c, true));
    nodes.set(key(c), [g, c]);
  }
  // one tab stop; arrows move, Enter or Space selects
  const first = nodes.get(CAL_SEL) || nodes.get(`${RESULT.request.month[0]}-${RESULT.request.month[1]}`) || [...nodes.values()].pop();
  if (first) first[0].setAttribute("tabindex", "0");
  svg.addEventListener("keydown", (evt) => {
    const g = evt.target.closest(".cal-cell");
    if (!g) return;
    const [y, m] = g.dataset.k.split("-").map(Number);
    let ny = y, nm = m;
    if (evt.key === "ArrowRight") nm++; else if (evt.key === "ArrowLeft") nm--; else if (evt.key === "ArrowDown") ny++; else if (evt.key === "ArrowUp") ny--;
    else if (evt.key === "Enter" || evt.key === " ") { evt.preventDefault(); calSelect(nodes.get(g.dataset.k)[1], true); return; }
    else return;
    evt.preventDefault();
    if (nm < 1) { nm = 12; ny--; } if (nm > 12) { nm = 1; ny++; }
    const next = nodes.get(`${ny}-${nm}`);
    if (!next) return;
    g.setAttribute("tabindex", "-1");
    next[0].setAttribute("tabindex", "0");
    next[0].focus();
    calSelect(next[1], false);
  });
  const edges = [...Array(steps + 1).keys()].map((i) => (i / steps) ** 2 * max);
  $("cal-legend").innerHTML = "<span>Detections per month</span>" + seq.map((c, i) => `<i style="background:${c}" title="${fmt(edges[i])}–${fmt(edges[i + 1])}"></i>`).join("") +
    `<span>0 → ${fmt(max)} (7 square-root steps)</span><i class="lg-gap" style="background:${css("--nodata")}"></i><span>– no data (never zero)</span>` +
    `<span class="lg-gap">▲ above / ▼ below this area's normal</span><span class="lg-gap"><i style="background:repeating-linear-gradient(45deg,${css("--ink2")} 0 1px,transparent 1px 4px);border:1px solid ${css("--line2")}"></i> partial coverage</span>`;
  // table view
  let tbl = `<table><caption class="note" style="caption-side:bottom;text-align:left">${esc(srcName)}; ▲ above / ▼ below this area's normal for that month</caption><thead><tr><th scope="col">Year</th>${MONTHS.map((m) => `<th scope="col">${m}</th>`).join("")}</tr></thead><tbody>`;
  for (const y of years) {
    tbl += `<tr><th scope="row">${y}</th>` + MONTHS.map((_, i) => {
      const c = cells.find((q) => q.year === y && q.month === i + 1);
      return `<td>${c.value == null ? "–" : (c.class === "above" ? "▲ " : c.class === "below" ? "▼ " : "") + fmt(c.value)}${c.flag ? "*" : ""}</td>`;
    }).join("") + "</tr>";
  }
  $("cal-table").innerHTML = tbl + "</tbody></table><p class='note'>* partial record or provider-reported missing days.</p>";
  const cur = CAL_SEL && nodes.get(CAL_SEL);
  calDetail(cur ? cur[1] : null);
}
function calSelect(c, focusDetail) {
  CAL_SEL = `${c.year}-${c.month}`;
  for (const g of $("calendar").querySelectorAll(".cal-cell")) g.setAttribute("aria-selected", String(g.dataset.k === CAL_SEL));
  calDetail(c);
  if (RESULT && $("series")) renderSeries();
  if (focusDetail) hideTip();
}
function calDetail(c) {
  const box = $("cal-detail-month");
  if (!c) { box.innerHTML = `<span class="note">Select a month to read its number and open its days or its detections on the map.</span>`; return; }
  const name = `${MONTH_FULL[c.month - 1]} ${c.year}`;
  const cls = c.class ? `<span class="cls ${c.class}">${c.class}</span>` : `<span class="cls">not classed</span>`;
  const st = (window.SeamScience && RESULT && RESULT.calendar)
    ? window.SeamScience.cellStats(RESULT.calendar[$("cal-src").value], c)
    : null;
  const meanNote = (c.median_other_years != null && st) ? ` · Mean ${fmt(st.mean)} (IQR ${fmt(st.p25)}–${fmt(st.p75)})` : "";
  const supTxt = RESULT && RESULT.calibration
    ? (RESULT.calibration.supported ? `Supported (${esc(RESULT.model)})` : "Unsupported pre-2012")
    : "";
  const covTxt = c.flag ? `Coverage: ${esc(c.flag)}` : "Full monthly support";
  box.innerHTML = `<div class="cd-main"><div><b>${name}</b> · ${esc($("cal-src").selectedOptions[0].text)}</div>` +
    `<div><span class="cd-num">${c.value == null ? "No data" : fmt(c.value)}</span>${c.value == null ? "" : " detections"} ${c.value == null ? "" : cls}</div>` +
    `<div class="note">${c.median_other_years == null ? "Too few other years to compare." : `Same-month median: <b>${fmt(c.median_other_years)}</b> (baseline <b>n = ${c.n_years}</b> eligible years)${meanNote}.`} · ${covTxt}${supTxt ? ` · ${supTxt}` : ""}.${c.value == null ? " Missing is not zero." : ""}</div></div>` +
    `<div class="btn-row"><button type="button" class="btn-primary" data-cal-act="map">Show on the map</button><button type="button" class="btn" data-cal-act="days">Open day by day</button><button type="button" class="btn" data-cal-act="month">Set as compare month</button></div>`;
  box.dataset.y = c.year; box.dataset.m = c.month;
}

// One month drives the day-by-day view and the map's point window.
function syncMapMonth() {
  const y = Number($("daily-year")?.value || 2025), mo = Number($("daily-month")?.value || 11);
  if ($("map-year") && $("daily-year")?.value) {
    $("map-year").value = $("daily-year").value;
    $("map-month").value = $("daily-month").value;
  }
  const when = MONTH_FULL[mo - 1] ? `${MONTHS[mo - 1]} ${y}` : "";
  const fullWhen = MONTH_FULL[mo - 1] ? `${MONTH_FULL[mo - 1]} ${y}` : "";
  if ($("map-when-m")) $("map-when-m").textContent = when;
  if ($("daily-scope-tag")) $("daily-scope-tag").textContent = `Map & daily month: ${fullWhen}`;
  if (RESULT && RESULT.request && RESULT.request.month) {
    const [cy, cm] = RESULT.request.month;
    const cmpText = `${MONTH_FULL[cm - 1]} ${cy}`;
    const same = cy === y && cm === mo;
    if ($("map-cmp-ref")) $("map-cmp-ref").textContent = same ? `(Matches compare month: ${cmpText})` : `(Compare month is ${cmpText})`;
    if ($("map-sync-compare")) $("map-sync-compare").textContent = same ? `Compare month (${MONTHS[cm - 1]} ${cy})` : `Match compare month (${MONTHS[cm - 1]} ${cy})`;
    if ($("daily-sync-compare")) $("daily-sync-compare").textContent = same ? `Compare month (${MONTHS[cm - 1]} ${cy})` : `Match compare month (${MONTHS[cm - 1]} ${cy})`;
    if ($("compare-to-map")) $("compare-to-map").textContent = `Show compare month (${MONTHS[cm - 1]} ${cy}) on map`;
  }
}
function setDayMonth(y, m) {
  if (!META || y < META.years[0] || y > META.years[1] || m < 1 || m > 12) return false;
  $("daily-year").value = String(y);
  $("daily-month").value = String(m);
  DAILY_SET = true;
  UI.mapDay = 0;
  syncMapMonth();
  loadDaily();
  Seam.emit("daymonth", [y, m]);
  return true;
}

// ---------- day by day (S02) ----------
let DAILY = null, DREQ = 0, DCTRL = null, DAILY_SET = false, DAILY_PASSES = false, DAILY_SETTLED = false;
// A day with no number shows a mark and says why (Opus review of S02, 5 Nov): never a bare zero.
const NOVAL = {
  outside_record: ["–", "no data: outside this satellite's record"],
  provider_missing: ["–", "no data: FIRMS lists this day as missing"],
  nothing_anywhere: ["?", "unknown: no row anywhere in Pakistan that day"],
  not_supported: ["n/a", "no value: this area failed the calibration support check"],
  held_out: ["·", "held out until a frozen test runs"],
};

function dailyBody() {
  const p = RESULT.request;
  const body = { region: p.region, model: p.model, day_month: [Number($("daily-year").value), Number($("daily-month").value)] };
  if (p.bbox) body.bbox = p.bbox;
  return body;
}

// The buttons stay focusable at the ends of the range (aria-disabled), so keyboard focus is never lost.
function dailyNav() {
  if (!META) return;
  const y = Number($("daily-year").value), mo = Number($("daily-month").value);
  const atStart = String(y === META.years[0] && mo === 1);
  const atEnd = String(y === META.years[1] && mo === 12);
  $("daily-prev").setAttribute("aria-disabled", atStart);
  $("daily-next").setAttribute("aria-disabled", atEnd);
  if ($("map-prev-m")) $("map-prev-m").setAttribute("aria-disabled", atStart);
  if ($("map-next-m")) $("map-next-m").setAttribute("aria-disabled", atEnd);
}

async function loadDaily() {
  if (!RESULT) return;
  const id = ++DREQ;  // only the newest reply is drawn, as for /api/analyze
  if (DCTRL) DCTRL.abort();
  DCTRL = new AbortController();
  DAILY = null;
  DAILY_SETTLED = false;
  dailyNav();
  $("daily").setAttribute("aria-busy", "true");
  const m = $("daily-msg");
  m.classList.remove("error");
  m.textContent = "Loading the days…";
  try {
    const res = await (await post("/api/daily", dailyBody(), DCTRL.signal)).json();
    if (id !== DREQ) return;
    DAILY = res;
    renderDaily();
    m.textContent = "";
    syncUrl();
  } catch (e) {
    if (id !== DREQ || e.name === "AbortError") return;
    // Never leave the previous month on screen under the newly chosen one.
    DAILY = null;
    $("daily").innerHTML = "";
    $("daily-notes").innerHTML = "";
    $("daily-title").textContent = "Day by day";
    m.textContent = `The days could not be loaded. ${e.message}`;
    m.classList.add("error");
  } finally {
    if (id === DREQ) {
      DAILY_SETTLED = true;
      $("daily").setAttribute("aria-busy", "false");
      Seam.emit("daily", DAILY);
    }
  }
}

function stepDaily(delta) {
  let y = Number($("daily-year").value), mo = Number($("daily-month").value) + delta;
  if (mo < 1) { mo = 12; y -= 1; }
  if (mo > 12) { mo = 1; y += 1; }
  if (y < META.years[0] || y > META.years[1]) return;  // the end of the range: focus stays on the button
  $("daily-year").value = String(y);
  $("daily-month").value = String(mo);
  loadDaily();
}

function dayCell(r, i, seq, dark, max) {
  const s = r.status[i], v = r.values[i];
  const attrs = `class="d-${s}" data-r="${r.key}" data-i="${i}"`;
  if (v != null) {
    // Square-root steps: on a log scale most days of a busy month land in the darkest step.
    const b = Math.min(6, Math.floor(Math.sqrt(v / max) * 7));
    const style = ` style="background:${seq[b]};color:${(b >= 4) !== dark ? "#ffffff" : "#0b0b0b"}"`;
    const split = r.D && r.D[i] != null && r.N && r.N[i] != null ? `, day pass ${fmt(r.D[i])}, night pass ${fmt(r.N[i])}`
      : s === "modelled" ? ", converted from Aqua" : "";
    return `<td ${attrs}${style}>${fmt(v)}${split ? `<span class="sr">${split}</span>` : ""}</td>`;
  }
  let glyph, said;
  if (s === "pass_missing") {
    const lo = r.at_least ? r.at_least[i] : null;
    const which = r.D ? `the ${r.D[i] == null ? "day" : "night"} pass` : "a pass it needs";
    said = lo != null ? `at least ${fmt(lo)}: ${which} has no data anywhere in Pakistan that day`
      : `unknown: ${which} has no data anywhere in Pakistan that day`;
    glyph = lo != null ? `≥${fmt(lo)}` : "?";
  } else {
    [glyph, said] = NOVAL[s] || ["–", "no data"];
  }
  return `<td ${attrs} aria-label="${esc(said)}"><span aria-hidden="true">${glyph}</span><span class="sr">${esc(said)}</span></td>`;
}

function passRows(r) {  // optional rows under a satellite: its day-pass and night-pass counts
  return ["D", "N"].map((dn) => {
    const cells = r.status.map((s, i) => {
      const v = r[dn][i];
      if (v != null) return `<td class="d-pass">${fmt(v)}</td>`;
      if (s === "pass_missing") return `<td class="d-pass" aria-label="unknown: no data anywhere in Pakistan on this pass"><span aria-hidden="true">?</span><span class="sr">unknown</span></td>`;
      return `<td class="d-pass" aria-label="no value (see the row above)"></td>`;
    }).join("");
    return `<tr class="pass-row"><th scope="row"><span class="sr">${esc(r.label)}, </span>${PASSES[dn]} pass</th>${cells}<td class="d-total"></td></tr>`;
  }).join("");
}

function rowLabel(label) {  // "Terra MODIS (morning and late-evening passes)": the bracket goes on a smaller line
  const i = label.indexOf(" (");
  return i < 0 ? esc(label) : `${esc(label.slice(0, i))} <span class="lbl-note">${esc(label.slice(i + 1))}</span>`;
}

function renderDaily() {
  const D = DAILY;
  const [y, mo] = D.month.split("-").map(Number);
  const when = `${MONTH_FULL[mo - 1]} ${y}`;
  $("daily-title").textContent = `Day by day: ${D.region}, ${when}`;
  dailyNav();
  const dark = css("color-scheme") === "dark";
  const seq = [...Array(7).keys()].map((i) => css(`--seq-${i}`));
  const held = new Set(D.held_out.days);
  const allHeld = held.size === D.days.length;
  let h = "";
  if (allHeld) {
    h = `<p class="warnbox">Every day of ${esc(when)} is held out here for a frozen test, until it runs: ${esc(D.held_out.why.join("; "))}.</p>`;
  } else {
    h = `<table class="daily"><caption class="sr">Detections per UTC day in ${esc(D.region)}, ${esc(when)}, each satellite separately; dates with a link open NASA Worldview</caption><thead><tr><th scope="col">Satellite</th>`;
    D.days.forEach((day, i) => {
      const n = Number(day.slice(8));
      // No link into a held-out day, nor onto a map that would show a held province that day.
      h += held.has(day) || !D.worldview[i] ? `<th scope="col">${n}</th>`
        : `<th scope="col"><a href="${esc(D.worldview[i])}" target="_blank" rel="noopener" aria-label="${n} ${esc(when)} in NASA Worldview (opens in a new tab)">${n}</a></th>`;
    });
    h += `<th scope="col">Month</th></tr></thead><tbody>`;
    for (const r of D.rows) {
      // Each row has its own colour scale: the satellites' counts differ by design.
      const max = Math.max(1, ...r.values.filter((v) => v != null));
      h += `<tr${r.key === "H" ? ' class="harm"' : ""}><th scope="row">${rowLabel(r.label)}</th>`;
      r.values.forEach((_, i) => { h += dayCell(r, i, seq, dark, max); });
      const t = r.month_total;
      const empty = r.status.includes("not_supported") ? "n/a" : "–";
      const part = t.days_used < t.days_in_month ? `<br><span class="muted">${t.days_used} of ${t.days_in_month} days</span>` : "";
      const info = t.value != null || empty === "n/a" ? ` ${infoBtn("daily", r.key, `${r.label}, ${when} total`)}` : "";
      h += `<td class="d-total">${t.value == null ? empty : fmt(t.value)}${info}${part}</td></tr>`;
      if (DAILY_PASSES && r.D) h += passRows(r);
    }
    h += "</tbody></table>";
  }
  $("daily").innerHTML = h;
  const tbl = $("daily").querySelector("table");
  if (tbl) {
    tbl.addEventListener("mousemove", (evt) => {
      const td = evt.target.closest("td[data-r]");
      if (!td) { hideTip(); return; }
      const r = D.rows.find((q) => q.key === td.dataset.r), i = Number(td.dataset.i);
      const day = D.days[i], v = r.values[i], s = r.status[i];
      let body = v == null ? "" : `${fmt(v, r.key === "H" && s === "modelled" ? 1 : 0)} detections`;
      if (v == null && s === "pass_missing" && r.at_least && r.at_least[i] != null) body = `at least ${fmt(r.at_least[i], r.key === "H" ? 1 : 0)} detections`;
      if (r.D && (r.D[i] != null || r.N[i] != null)) body += ` (day pass ${r.D[i] == null ? "unknown" : fmt(r.D[i])}, night pass ${r.N[i] == null ? "unknown" : fmt(r.N[i])})`;
      const quiet = (r.empty_everywhere && r.empty_everywhere[i]) || [];
      if (quiet.length) body += `<br>The ${quiet.map((p) => PASSES[p]).join(" and ")} pass had no detection anywhere in Pakistan, as usual for MODIS at night, so it counts as zero.`;
      const zero = v === 0 ? "<br>None here. No detection is not no fire." : "";
      showTip(`<b>${esc(r.label)}, ${esc(day)} (UTC)</b><br>${body}${body ? "<br>" : ""}<span style="color:var(--muted)">${esc(D.status_text[s])}</span>${zero}`, evt);
    });
    tbl.addEventListener("mouseleave", hideTip);
    // Keep a focused date link clear of the sticky satellite names when tabbing backwards.
    tbl.addEventListener("focusin", (evt) => {
      const th = evt.target.closest("thead th");
      if (!th || th === tbl.querySelector("thead th")) return;
      const edge = tbl.querySelector("thead th").getBoundingClientRect().right;
      const left = th.getBoundingClientRect().left;
      if (left < edge) $("daily").scrollLeft -= edge - left + 4;
    });
  }
  // The key lists only the marks this month uses.
  const used = new Set(D.rows.flatMap((r) => r.status));
  const keys = [`<span><i style="background:linear-gradient(90deg,${seq[0]},${seq[6]})"></i>fewer → more detections (each row on its own scale)</span>`];
  if (used.has("outside_record") || used.has("provider_missing")) keys.push(`<span><i style="background:var(--nodata)"></i>– no data (outside the record, or FIRMS lists the day missing)</span>`);
  if (used.has("nothing_anywhere")) keys.push(`<span><i class="key-q"></i>? unknown: this satellite has no row anywhere in Pakistan that day (an outage or a quiet day)</span>`);
  if (used.has("pass_missing")) keys.push(`<span><i class="key-part"></i>≥ partial day: a pass this row needs has no row anywhere in Pakistan, so only the other pass is shown (? if it shows nothing here)</span>`);
  if (used.has("not_supported")) keys.push(`<span><i class="key-na"></i>n/a in the harmonised row: no value, because this area failed the calibration support check (Aqua's own counts are in its row)</span>`);
  if (used.has("held_out")) keys.push(`<span><i class="key-held"></i>held out for a frozen test</span>`);
  if (used.has("modelled")) keys.push(`<span><i style="background:var(--surface)"></i><em>italic</em>: converted from Aqua</span>`);
  const heldNote = D.held_out.days.length && !allHeld
    ? `<div class="warnbox">${D.held_out.days.length} day${D.held_out.days.length === 1 ? " is" : "s are"} held out until a frozen test runs: ${esc(D.held_out.why.join("; "))}. Nothing is counted for those days.</div>` : "";
  const wv = D.worldview_withheld || { days: [], provinces: [] };
  const open = D.days.length - D.held_out.days.length;
  const provs = wv.provinces.length > 1 ? `${wv.provinces.slice(0, -1).join(", ")} and ${wv.provinces[wv.provinces.length - 1]}` : wv.provinces.join("");
  let links = "Each date opens NASA Worldview for this area and day, with the MODIS and VIIRS fire layers (needs internet).";
  if (!open) links = "";
  else if (wv.days.length && wv.days.length >= open) {
    links = `No date links to NASA Worldview this month: its map would also show ${esc(provs)}, held out for P04's frozen tests on these days. The links return once those tests have run.`;
  } else if (wv.days.length) {
    links += ` ${wv.days.length} date${wv.days.length === 1 ? " has" : "s have"} no link, because the map would also show ${esc(provs)}, held out for P04's frozen tests on ${wv.days.length === 1 ? "that day" : "those days"}.`;
  }
  $("daily-notes").innerHTML = `<div class="daily-key">${keys.join("")}</div>` + heldNote +
    `<ul class="note">${D.notes.map((t) => `<li>${esc(t)}</li>`).join("")}${links ? `<li>${links}</li>` : ""}</ul>`;
}

// The story panel's preview of the month on screen: one strip per satellite, marks for unknown days.
function renderDaysPreview() {
  const host = $("days-preview"), D = DAILY;
  if (!host) return;
  if (!D) { host.innerHTML = `<p class="note">The days could not be loaded.</p>`; return; }
  const [y, mo] = D.month.split("-").map(Number);
  $("days-eyebrow").textContent = `${D.region} · ${MONTH_FULL[mo - 1]} ${y} · detections per UTC day`;
  const total = Math.max(320, Math.round(host.clientWidth || 600));
  const n = D.days.length, L = total < 480 ? 92 : 150, cw = Math.max(6, Math.floor((total - L) / n)), ch = 20, W = L + cw * n + 2, H = D.rows.length * (ch + 3) + 18;
  const dark = css("color-scheme") === "dark", seq = [...Array(7).keys()].map((i) => css(`--seq-${i}`));
  host.innerHTML = "";
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `Preview of ${MONTH_FULL[mo - 1]} ${y} in ${D.region}: one row per satellite, shaded by detections per day on each row's own scale; question marks and dashes are days with no usable data. The full table is in Calendar, Day by day.` }, host);
  svg.style.width = "100%";
  D.rows.forEach((r, j) => {
    const y0 = j * (ch + 3);
    const lab = r.label.split(" (")[0];
    el("text", { x: 0, y: y0 + 14, style: `fill:${css("--ink2")};font:${r.key === "H" ? 700 : 500} 12px ${css("--font")}` }, svg).textContent = lab.length > (L < 120 ? 14 : 24) ? lab.slice(0, L < 120 ? 13 : 23) + "…" : lab;
    const max = Math.max(1, ...r.values.filter((v) => v != null));
    r.values.forEach((v, i) => {
      const x = L + cw * i;
      if (v != null) {
        el("rect", { x, y: y0, width: cw - 1, height: ch, rx: 2, fill: seq[Math.min(6, Math.floor(Math.sqrt(v / max) * 7))] }, svg);
      } else {
        el("rect", { x, y: y0, width: cw - 1, height: ch, rx: 2, fill: css("--nodata") }, svg);
        const s = r.status[i], g = s === "pass_missing" ? "≥" : (NOVAL[s] || ["–"])[0];
        el("text", { x: x + (cw - 1) / 2, y: y0 + 14, "text-anchor": "middle", style: `fill:${dark ? "#fff" : "#0b0b0b"};font:700 11px ${css("--font")}` }, svg).textContent = g === "n/a" ? "·" : g;
      }
    });
  });
  [1, 10, 20, n].forEach((d) => el("text", { x: L + cw * (d - 1) + (cw - 1) / 2, y: H - 3, "text-anchor": "middle", style: `fill:${css("--muted")};font:11px ${css("--font")}` }, svg).textContent = d);
}
const renderDailyBase = renderDaily;
renderDaily = function () {
  if (UI.ws === "calendar" && UI.sub === "days") renderDailyBase();
  if (UI.ws === "overview" && UI.story === "days") renderDaysPreview();
  syncMapMonth();
};  // eslint-disable-line no-func-assign

// The month on screen as a CSV file: exactly the reply drawn above, with each number's status and source.
function dailyCsv() {
  const D = DAILY;
  if (!D) { toast("Open a month in Calendar, Day by day, first.", { error: true }); return; }
  const q = (v) => (v == null ? "" : /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v));
  const head = ["area", "date_utc", "row", "label", "value", "at_least", "day_pass", "night_pass", "status", "status_text",
                "harmonised_source", "model", "units", "detections_sha256", "data_identity"];
  const lines = [head.join(",")];
  const ident = RESULT && RESULT.data_identity ? RESULT.data_identity : META.data_identity || "";
  for (const r of D.rows) {
    D.days.forEach((day, i) => {
      lines.push([D.region, day, r.key, r.label, r.values[i], r.at_least ? r.at_least[i] : null,
        r.D ? r.D[i] : null, r.N ? r.N[i] : null, r.status[i], D.status_text[r.status[i]],
        r.key === "H" ? r.source : "", D.model, D.units, META.detections_sha256, ident].map(q).join(","));
    });
  }
  const name = `seamline_${D.region.replace(/\W+/g, "_")}_${D.month}_daily.csv`;
  save(new Blob([lines.join("\n") + "\n"], { type: "text/csv" }), name);
  toast(`Saved ${name}: the ${D.days.length} days on screen, one row per satellite and day; days with no number say why.`);
}

function renderCompare() {
  const c = RESULT.comparison;
  const [y, m] = c.month.split("-").map(Number);
  const name = MONTH_FULL[m - 1];
  $("compare-title").textContent = `${name} ${y} versus a normal ${name} (${RESULT.years[0]}–${RESULT.years[1]})`;
  const rows = Object.entries(c.series).map(([key, s]) => {
    let body;
    if (s.status && s.status.startsWith("compared")) {
      body = `<b>${fmt(s.value)}</b> detections; median of ${s.baseline_n} other years ${fmt(s.median)} (range ${fmt(s.baseline_min)}–${fmt(s.baseline_max)}).
        Higher than ${s.rank - 1} of ${s.of - 1} other ${name}s. <span class="cls ${s.cls}">${s.cls}</span>`;
      if (s.status !== "compared") body += `<div class="warnbox">${esc(s.status)}</div>`;
    } else {
      body = `${s.value == null ? "No value." : `<b>${fmt(s.value)}</b> detections.`} <div class="warnbox">${esc(s.status)}</div>`;
    }
    return `<div class="cmp-row"><div class="cmp-label">${esc(s.label)} ${infoBtn("compare", key, `${s.label}, ${name} ${y}`)}</div><div>${body}</div></div>`;
  });
  const h = c.series.H, n = c.series.naive, ns = c.series.naive_snpp;
  let sentence = "";
  if (h.cls && n.cls && h.cls !== n.cls && ns && ns.cls === h.cls) {
    // Say why: from April 2018 the naive record also adds NOAA-20, a second VIIRS satellite.
    sentence = `<p><b>The naive record disagrees here because it adds NOAA-20:</b> the all-satellite naive record calls this month <i>${n.cls}</i>, the harmonised record <i>${h.cls}</i>. Joining MODIS to S-NPP alone also gives <i>${ns.cls}</i>, so the difference comes from adding a second VIIRS satellite in 2018, not from the MODIS-to-VIIRS change.</p>`;
  } else if (h.cls && n.cls && h.cls !== n.cls) sentence = `<p><b>Harmonisation changes the answer here:</b> the naive record calls this month <i>${n.cls}</i>, the harmonised record calls it <i>${h.cls}</i>.</p>`;
  else if (h.cls && n.cls) sentence = `<p>The harmonised and naive records agree: <i>${h.cls}</i>.</p>`;
  $("compare").innerHTML = sentence + rows.join("") + `<p class="note">"Above"/"below" use the same rule as the calendar. This compares with the area's own past; it is not a forecast or a risk level.</p>`;
  syncMapMonth();
}

function renderLatest() {
  const L = RESULT.latest;
  if (!L || !L.available) { $("latest").innerHTML = "<p>No near-real-time files cached.</p>"; return; }
  const names = { SNPP: "S-NPP VIIRS", NOAA20: "NOAA-20 VIIRS" };
  const them = (n) => (n === 1 ? "that day is" : "those days are");
  const rows = Object.entries(L.platforms).map(([p, v]) => {
    // Days and years that cannot be compared fairly are left out, never counted as zero.
    const notes = [];
    if (v.days_without_data.length) notes.push(`No ${names[p]} data on ${esc(v.days_without_data.join(", "))}; ${them(v.days_without_data.length)} left out on both sides.`);
    if (v.days_partial.length) notes.push(`One of the two daily ${names[p]} passes had no detections anywhere in Pakistan on ${esc(v.days_partial.join(", "))} (an outage, or a quiet pass), so ${them(v.days_partial.length)} left out on both sides too.`);
    if (v.leap_day_left_out.length) notes.push("29 February is left out: most past years have no such day.");
    const why = v.years_left_out_why || {};
    if (Object.keys(why).length) notes.push(`Past years left out, because the archive does not cover all the compared days: ${Object.entries(why).map(([y, r]) => `${esc(y)} (${esc(r)})`).join("; ")}.`);
    const warn = notes.map((t) => `<div class="warnbox">${t}</div>`).join("");
    if (v.status === "no_data" || v.status === "only_29_february") {
      const ended = p === "SNPP" && L.window_utc[0] > "2026-11-02" ? " (S-NPP stopped sending new data on 2 Nov 2026)" : "";
      const what = v.status === "no_data" ? `<b>No usable data</b> in this download${ended}. Missing data is not low burning, so it is not compared.`
        : "<b>Only 29 February</b> has both passes in this download, and most past years have no such day, so it is not compared.";
      return `<div class="cmp-row"><div class="cmp-label">${names[p]}</div><div>${what}${warn}</div></div>`;
    }
    const span = v.days_used === L.n_days ? `${v.days_used} day${v.days_used === 1 ? "" : "s"}` : `${v.days_used} of the ${L.n_days} days`;
    const head = `<b>${fmt(v.now)}</b> detections on ${span} (${L.window_utc[0]} to ${L.window_utc[1]})`;
    const label = `<div class="cmp-label">${names[p]} ${infoBtn("latest", p, `${names[p]}, latest days`)}</div>`;
    if (v.status === "too_few_years") {
      return `<div class="cmp-row">${label}<div>${head}. Fewer than 3 past years cover these dates, so it is not compared.${warn}</div></div>`;
    }
    const yrs = Object.keys(v.years);
    return `<div class="cmp-row">${label}<div>
      ${head}; the same dates in ${yrs.length} past years (${yrs[0]}–${yrs[yrs.length - 1]}): median ${fmt(v.median)}, range ${fmt(v.min)}–${fmt(v.max)}.
      <span class="cls ${v.cls}">${v.cls}</span>${warn}</div></div>`;
  }).join("");
  const older = L.older_batches_not_counted ? ` ${L.older_batches_not_counted} older download${L.older_batches_not_counted === 1 ? " is" : "s are"} kept but not counted.` : "";
  const age = L.age_days != null ? ` (${esc(L.freshness || "cached")}, ${L.age_days} day${L.age_days === 1 ? "" : "s"} old${L.as_of_utc ? ` as of ${esc(L.as_of_utc.slice(0, 10))} UTC` : ""})` : "";
  $("latest").innerHTML = `<p>${L.n_days} complete UTC days in the NRT files fetched ${esc(L.retrieved_utc)}${age}.</p>${rows}<p class="note">${esc(L.note)}${older} Partial days are left out. A refresh needs internet: <code>python -m c08.acquire --nrt</code>, then restart the local server so the input identity reloads.</p>`;
}

function renderCalibration() {
  const c = RESULT.calibration;
  if (!c.supported) {
    $("calibration").innerHTML = `<div class="ev-framing"><p><b>Question:</b> Can Aqua MODIS (2003–2011) be harmonised to the S-NPP VIIRS scale in ${esc(RESULT.region)}?</p><p><b>Result:</b> Unsupported (${esc(c.reasons.join("; "))}). Only observed S-NPP values (from Feb 2012) are shown as harmonised.</p><p><b>Source:</b> Area-specific overlap check (2012–2017).</p></div>`;
    return;
  }
  const a = c.cv_agreement, q = c.interval_log_quantiles;
  const pct = (q) => `${sfmt((Math.exp(q.lo) - 1) * 100)}% to ${sfmt((Math.exp(q.hi) - 1) * 100)}%`;
  $("calibration").innerHTML = `
    <div class="ev-framing">
      <p><b>Question:</b> How accurately does ${esc(c.model)} convert ${esc(RESULT.region)}'s Aqua MODIS counts onto the S-NPP VIIRS scale?</p>
      <p><b>Result:</b> Supported (${c.fit_months} overlap months, Feb 2012–Dec 2017); 2014–2017 cross-validation WAPE is <b>${pct100(a.model.wape)}%</b> (bias ${sfmt(a.model.bias == null ? null : a.model.bias * 100, 1)}%).</p>
      <p><b>Scoped limitations:</b> Tested on monthly totals against S-NPP (another satellite, not ground truth); nominal 80% error bounds come from small seasonal samples.</p>
      <p><b>Source:</b> ${esc(RESULT.region)} own overlap calibration (${esc(c.passes.map((p) => PASSES[p]).join(" and "))} passes).</p>
    </div>
    <div class="table-wrap"><table><thead><tr><th scope="col">Cross-validation 2014–2017, this area</th><th scope="col">WAPE</th><th scope="col">Bias</th><th scope="col">Months</th></tr></thead><tbody>
    <tr><td>${esc(c.model)} (shown)</td><td>${pct100(a.model.wape)}%</td><td>${sfmt(a.model.bias == null ? null : a.model.bias * 100, 1)}%</td><td>${a.model.n_months}</td></tr>
    ${c.model !== "M1" ? `<tr><td>M1 single ratio</td><td>${pct100(a.M1.wape)}%</td><td>${sfmt(a.M1.bias == null ? null : a.M1.bias * 100, 1)}%</td><td>${a.M1.n_months}</td></tr>` : ""}
    </tbody></table></div>
    <p>WAPE = total monthly error ÷ total detections, against S-NPP (another satellite, not ground truth). Passes: ${esc(c.passes.map((p) => PASSES[p]).join(" and "))}.</p>
    <p>Spread of this area's cross-validated errors, observed S-NPP relative to the modelled value (10th to 90th percentile; these limits make the nominal 80% range): Oct–Nov ${pct(q.OctNov)} (${q.OctNov.n} months), Apr–May ${pct(q.AprMay)} (${q.AprMay.n} months), other months ${pct(q.other)} (${q.other.n} months). With so few months the limits are rough, and they ignore which calibration years were used.</p>`;
}

function renderEvidence() {
  const e = META.evidence;
  if (!e || !e.available) { $("evidence").innerHTML = "<p>Experiment files not found.</p>"; return; }
  const row = (m, s, t) => `<tr><td>${m}${m === e.selected ? " (selected)" : ""}</td><td>${fmt(s.wape * 100, 1)}%</td><td>${t ? fmt(t.wape * 100, 1) + "%" : "not tested"}</td></tr>`;
  const range = (k) => { const v = Object.values(e.drift).map((d) => d[k]); return `${sfmt(Math.min(...v) * 100)}% to ${sfmt(Math.max(...v) * 100)}%`; };
  const sd = e.sindh, w = (x) => fmt(x.wape * 100, 1) + "%", b = (x) => sfmt(x.bias * 100) + "%";
  $("evidence").innerHTML = `
    <div class="ev-framing">
      <p><b>Question:</b> Do frozen Aqua → S-NPP models hold on held-out years (2012–2013), later MODIS collections (2018–2025), and across provinces?</p>
      <p><b>Result:</b> Selected <b>${esc(e.selected)}</b> had the lowest 2014–2017 selection error (${fmt(e.selection[e.selected].wape * 100, 1)}%), but single-ratio <b>M1</b> did better on the held-out 2012–2013 test (${fmt(e.temporal_test.M1.wape * 100, 1)}% vs ${fmt(e.temporal_test.M2.wape * 100, 1)}%).</p>
      <p><b>Scoped limitations:</b> Nominal 80% intervals covered only ${fmt(e.interval_coverage * 100)}% of held-out months; no universal multiplier holds across MODIS collection updates or across provinces.</p>
      <p><b>Source:</b> Frozen protocol <code>experiments/PROTOCOL_P01.md</code> (${e.files.map(esc).join(", ")}).</p>
    </div>
    <div class="table-wrap"><table><thead><tr><th scope="col">Model (Aqua → S-NPP, Punjab)</th><th scope="col">Selection WAPE 2014–17</th><th scope="col">Test WAPE 2012–13</th></tr></thead><tbody>
    ${Object.entries(e.selection).map(([m, s]) => row(m, s, e.temporal_test[m])).join("")}</tbody></table></div>
    <ul>
      <li><b>Negative result kept:</b> the selected M2 did worse than the single ratio M1 on the held-out 2012–13 test (WAPE ${fmt(e.temporal_test.M2.wape * 100, 1)}% vs ${fmt(e.temporal_test.M1.wape * 100, 1)}%). Its nominal 80% ranges covered only ${fmt(e.interval_coverage * 100)}% of test months.</li>
      <li>No universal multiplier: applied to 2018–2025, the 2014–17 fit over-predicted every year (M1 bias ${range("M1_bias")}, M2 ${range("M2_bias")}), as MODIS files moved to versions 6.03 and 61.03.</li>
      <li>Sindh, own calibration: M1 ${w(sd.method_transfer.M1)} (bias ${b(sd.method_transfer.M1)}), M2 ${w(sd.method_transfer.M2)} (bias ${b(sd.method_transfer.M2)}). Reusing Punjab's numbers: M1 ${w(sd.parameter_transfer.M1)} (bias ${b(sd.parameter_transfer.M1)}), M2 ${w(sd.parameter_transfer.M2)} (bias ${b(sd.parameter_transfer.M2)}). Punjab's numbers under-count Sindh; total error is mixed (better for M1, worse for M2). Each area is calibrated on its own to avoid that bias.</li>
      <li>NOAA-20 → S-NPP bridge (2024–25 test): total error (WAPE) ${fmt(e.bridge_test.M1 * 100, 1)}% with ${esc(e.bridge_selected)}; raw NOAA-20 ${fmt(e.bridge_test.M0 * 100, 1)}%. Single months differ more than this total (see docs/VALIDATION.md).</li>
      <li>Punjab Oct–Nov change: naive ${fmt(e.differentiator.OctNov.naive, 1)}× (it adds NOAA-20 from 2018; MODIS joined to S-NPP alone gives about 11×), harmonised ${fmt(e.differentiator.OctNov.harmonised, 2)}× (rough range ${fmt(e.differentiator.OctNov.interval[0], 2)}–${fmt(e.differentiator.OctNov.interval[1], 2)}), Aqua only ${fmt(e.differentiator.OctNov.aqua, 2)}× (a consistency check: the early harmonised years are calculated from Aqua).${e.sensitivity_octnov ? ` All four frozen models give ${Object.entries(e.sensitivity_octnov).map(([m, v]) => `${m} ${fmt(v.ratio, 2)}×`).join(", ")} (E03); the selected M2 is the highest.` : ""} Given the sensor change, the naive figure was bound to be far larger, so this comparison is a demonstration rather than a test.</li>
    </ul>
    <p class="note">Files: ${e.files.map(esc).join(", ")}. Protocol frozen before results: experiments/PROTOCOL_P01.md.</p>`;
}

// ---------- "Where did this number come from?" ----------
const FILTERS = "Quality rule: MODIS confidence 30 or more; VIIRS nominal or high confidence (low left out). " +
  "Type 0 only: presumed vegetation fires (volcanoes, other static land sources and offshore detections left out). " +
  "Standard (archive) processing.";

function provModel(model) {
  const c = RESULT.calibration, e = META.evidence;
  if (!c.supported) return [["Model", `None: this area failed the calibration support check (${c.reasons.join("; ")}), so it has no values before February 2012.`]];
  const out = [["Model", `${model}: ${model === "M1" ? "one Aqua-to-S-NPP factor per pass" : "an Aqua-to-S-NPP factor for each calendar month"}, fitted on this area's own complete months, February 2012 to December 2017 (${c.fit_months} months).`]];
  let t = `This area's cross-validation, 2014–2017: total error (WAPE) ${pct100(c.cv_agreement.model.wape)}% against S-NPP, another satellite, not ground truth.`;
  if (e && e.available && e.temporal_test[model]) {
    const m1 = e.temporal_test.M1, mine = e.temporal_test[model].wape;
    t += ` Held-out test, Punjab, 2012–2013: WAPE ${fmt(mine * 100, 1)}% for ${model}` +
      (model !== "M1" && m1 && m1.wape < mine ? ` (the single ratio M1 did better: ${fmt(m1.wape * 100, 1)}%)` : "") +
      `. Its rough ranges caught ${fmt(e.interval_coverage * 100)}% of test months, so they are too narrow.`;
  }
  out.push(["Tested", t]);
  return out;
}

function provData() {
  const out = [["Data", `Processed detections table built ${META.built_utc}: ${fmt(META.rows)} rows from ${META.files} hash-checked files (reports/c08/ingest_report.json). Sources: ${META.sources}.`],
               ["SHA-256", META.detections_sha256, true]];
  const ident = RESULT && RESULT.data_identity ? RESULT.data_identity : META.data_identity;
  if (ident) out.push(["Data identity", ident, true]);
  if (META.current_record) {
    const cr = META.current_record;
    out.push(["2026 supplement", `API acquisition through ${cr.api_acquisition_end || "2026-10-31"}, latest cached observation ${(cr.latest_observed_acquisition_utc || "").slice(0, 10)} UTC (fetched ${(cr.latest_retrieved_utc || "").slice(0, 10)} UTC).`]);
  }
  return out;
}

function provFor(kind, key) {
  const r = RESULT, passes = r.passes;
  const items = [];
  let title = "";
  if (kind === "change") {
    const season = key === "OctNov" ? "October–November" : "April–May";
    title = `${season} change, ${r.region}`;
    items.push(["What", `The average ${season} total in 2012–2021 divided by the average in 2003–2011, on one scale (S-NPP-equivalent).`],
      ["Satellites", "S-NPP VIIRS, observed, from February 2012; before that, Aqua MODIS converted to S-NPP-equivalent. One satellite at a time, never added together."],
      ["Other lines", "Naive stitch: Terra and Aqua added together until 2011, then S-NPP and NOAA-20 (from April 2018) added together, shown only for comparison. Aqua MODIS only: its own counts, with no conversion."],
      ["Passes", passes], ["Filters", FILTERS], ...provModel(r.model));
  } else if (kind === "compare") {
    const s = r.comparison.series[key], m = r.comparison.month, mo = r.months.find((x) => x.month === m);
    const [y, mm] = m.split("-").map(Number);
    const when = `${MONTH_FULL[mm - 1]} ${y}`;
    title = `${s.label}, ${when}`;
    const base = `Compared with the median of ${when.split(" ")[0]} in the other years of ${r.years[0]}–${r.years[1]} with full coverage (${s.baseline_n} years).`;
    if (key === "H") {
      const src = mo ? mo.H_source : "";
      items.push(["What", `Harmonised detections in ${when}. ${base}`],
        ["Satellite", src.startsWith("observed S-NPP") ? `S-NPP VIIRS, observed (${src}).` : src.startsWith("modelled") ? `Aqua MODIS, converted to S-NPP-equivalent (${src}).` : src.startsWith("NOAA-20 converted") ? `NOAA-20 VIIRS, converted to S-NPP-equivalent (${src}; no uncertainty range).` : `None: ${src}.`],
        ["Passes", passes], ["Filters", y >= 2026 && mo && mo.H_flag && mo.H_flag.includes("nrt_untyped") ? "Quality rule: VIIRS nominal or high confidence. Untyped NRT supplement (no type screen)." : FILTERS]);
      if (r.years[0] < 2012) items.push(...provModel(r.model));
      else items.push(["Model", src.startsWith("NOAA-20 converted") ? "Frozen P04 G03 Punjab no-type NOAA-20 bridge (k_day, k_night); no new fit." : "None: observed S-NPP."]);
    } else if (key === "aqua") {
      items.push(["What", `Aqua MODIS detections in ${when}, counted, with no conversion. ${base}`], ["Satellite", "Aqua MODIS alone."],
        ["Passes", passes], ["Filters", FILTERS], ["Model", "None: counted detections."]);
    } else {
      const after = key === "naive" ? "S-NPP and NOAA-20 (from April 2018) added together" : "S-NPP alone";
      items.push(["What", `A naive record: Terra and Aqua added together until December 2011, then ${after}. Satellites are added on purpose here, to show what joining raw downloads does; it is not comparable across years. ${base}`],
        ["Passes", passes], ["Filters", FILTERS], ["Model", "None: counted detections."]);
    }
  } else if (kind === "latest") {
    const L = r.latest, v = L.platforms[key], name = key === "SNPP" ? "S-NPP VIIRS" : "NOAA-20 VIIRS";
    title = `${name}, latest complete days`;
    items.push(["What", `${name} detections on ${v.days_used} complete UTC days (${L.window_utc[0]} to ${L.window_utc[1]}), compared with the same dates in past years of the standard archive.`],
      ["Satellite", `${name} alone.`],
      ["Passes", "Day and night. A day counts only if both passes have rows somewhere in Pakistan, on both sides of the comparison."],
      ["Filters", "Quality rule: VIIRS nominal or high confidence. No type screen on either side: near-real-time (NRT) files have no type field."],
      ["Download", `Newest NRT download only: batch ${L.batch}, fetched ${L.retrieved_utc}${L.age_days != null ? ` (${L.freshness || "cached"}, ${L.age_days}d old as of ${(L.as_of_utc || "").slice(0, 10)} UTC)` : ""}.${L.older_batches_not_counted ? ` ${L.older_batches_not_counted} older download(s) kept but not counted.` : ""}`],
      ["Model", "None: counted detections. NRT and archive processing differ, and this is not corrected."],
      ["Tested", "Not a test result. 'Above' or 'below' means unusual compared with the same dates in past years, not a forecast."]);
  } else if (kind === "daily" && DAILY) {
    const row = DAILY.rows.find((x) => x.key === key), t = row.month_total;
    const [y, mm] = DAILY.month.split("-").map(Number);
    title = `${row.label}, ${MONTH_FULL[mm - 1]} ${y}`;
    items.push(["What", `Sum of the daily values in ${DAILY.region} over ${t.days_used} of ${t.days_in_month} UTC days. Days with no data, partial days${t.days_partial ? ` (${t.days_partial})` : ""} and held-out days${t.days_held_out ? ` (${t.days_held_out})` : ""} are left out.${t.calendar_observed_subtotal != null && t.calendar_observed_subtotal !== t.value ? ` Monthly cached-row subtotal: ${fmt(t.calendar_observed_subtotal)}.` : ""}`]);
    if (key === "H") {
      items.push(["Source", row.source], ["Passes", row.passes_used.map((p) => PASSES[p]).join(" and ")], ["Filters", FILTERS]);
      if (String(row.source).startsWith("NOAA-20 converted")) {
        items.push(["Model", "Frozen P04 G03 Punjab no-type NOAA-20 bridge (k_day, k_night); no new fit."],
                   ["Daily values", "Each day uses the saved monthly bridge factor per pass. Only monthly values were tested; daily accuracy and uncertainty are untested."]);
      } else if (row.status.includes("modelled") || row.status.includes("not_supported")) {
        items.push(...provModel(DAILY.model), ["Daily values", "Each day is Aqua's count times the fitted factor. Only monthly values were tested; daily accuracy is untested."]);
      } else items.push(["Model", "None: observed S-NPP."]);
    } else {
      items.push(["Satellite", `${row.label} alone; satellites are never added together.`],
        ["Passes", `Day and night. A day counts when ${row.passes_needed.length === 2 ? "both passes have" : "the day pass has"} rows somewhere in Pakistan.`],
        ["Filters", FILTERS], ["Model", "None: counted detections."]);
    }
  }
  items.push(...provData());
  return { title, items };
}

let POP_BTN = null;
function popEl() {
  let p = $("prov-pop");
  if (p) return p;
  p = document.createElement("div");
  p.id = "prov-pop";
  p.className = "pop";
  p.hidden = true;
  p.tabIndex = -1;
  p.setAttribute("role", "dialog");
  p.setAttribute("aria-labelledby", "prov-pop-title");
  p.innerHTML = `<div class="pop-head"><h3 id="prov-pop-title"></h3><button type="button" class="pop-close" aria-label="Close">×</button></div><div class="pop-body"></div>`;
  document.body.appendChild(p);
  p.querySelector(".pop-close").addEventListener("click", () => closePop(true));
  p.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); closePop(true); }
    // Tabbing out of the popover returns to its button, as if the popover sat right after it.
    else if (e.key === "Tab" && ((!e.shiftKey && document.activeElement === p.querySelector(".pop-close")) || (e.shiftKey && document.activeElement === p))) {
      e.preventDefault();
      closePop(true);
    }
  });
  return p;
}
function openPop(btn) {
  if (!RESULT || !META) return;
  const { title, items } = provFor(btn.dataset.prov, btn.dataset.key);
  const p = popEl();
  if (POP_BTN && POP_BTN !== btn) POP_BTN.setAttribute("aria-expanded", "false");
  p.querySelector("h3").textContent = title;
  p.querySelector(".pop-body").innerHTML = `<dl>${items.map(([k, v, code]) => `<dt>${esc(k)}</dt><dd>${code ? `<code>${esc(v)}</code>` : esc(v)}</dd>`).join("")}</dl>`;
  p.hidden = false;
  const vw = document.documentElement.clientWidth, b = btn.getBoundingClientRect();
  p.style.width = Math.min(440, vw - 16) + "px";
  p.style.left = (Math.min(Math.max(8, b.left - 12), vw - p.offsetWidth - 8) + window.scrollX) + "px";
  p.style.top = (b.bottom + window.scrollY + 6) + "px";
  btn.setAttribute("aria-expanded", "true");
  POP_BTN = btn;
  hideTip();
  p.focus();
}
function closePop(refocus) {
  const p = IN_BROWSER ? $("prov-pop") : null;
  if (!p || p.hidden) return;
  p.hidden = true;
  if (POP_BTN) {
    POP_BTN.setAttribute("aria-expanded", "false");
    if (refocus && document.contains(POP_BTN)) POP_BTN.focus();
  }
  POP_BTN = null;
}

// ---------- tour (presentation mode) ----------
// Each step opens the right workspace and story, so its key number, qualifier and chart are on screen together.
// The first four steps are the 30-second demo (headline first); the rest make the two-minute version.
function tourSteps() {
  const ch = RESULT && RESULT.change && RESULT.change.OctNov;
  const rec = ch && ch.defined ? `Joined raw, the records show ${fmt(ch.naive, 2)}× in ${RESULT.region}'s October–November; on one scale it is ${ch.point_in_interval ? fmt(ch.H, 2) + "×" : `${fmt(ch.H_interval[0], 2)}–${fmt(ch.H_interval[1], 2)}×`}.`
    : "The long record, joined raw and on one scale.";
  return [
    { ws: "overview", story: "headline", title: "This October's headline, taken apart", text: "The press count for Pakistani Punjab, reproduced within 20%, then taken apart satellite by satellite: more satellites flying means more detections, even with the same burning.",
      pose: { mode: "3d", vmode: "points", orbit: false, seam: false, psf: false } },
    { ws: "overview", story: "seam", title: "The handover", text: "S-NPP, the reference, stopped on 2 Nov 2026. A test frozen before the 2026 download shows whether converted NOAA-20 can carry Punjab's record.",
      pose: { mode: "3d", vmode: "points", orbit: true, seam: true, psf: false, center: [72.6, 30.8], zoom: 5.5, pitch: 56, bearing: 18 } },
    { ws: "overview", story: "clock", title: "The clock", text: "Satellites pass at different times of day. Terra's pass moved earlier, and in Punjab its autumn share fell against S-NPP's. No cause is claimed.",
      pose: { mode: "globe", vmode: "points", orbit: true, seam: false, psf: false, center: [71.5, 29.0], zoom: 2.35, pitch: 26, bearing: -14 } },
    { ws: "calendar", sub: "days", title: "Day by day", text: "Every day of one month, one row per satellite. Missing days are marked, never shown as zero; each date opens NASA Worldview (needs internet)." },
    { ws: "overview", story: "record", title: "The long record", text: rec + " The naive line is a comparison only.",
      pose: { mode: "3d", vmode: "towers", orbit: false, seam: false, psf: false, center: [72.7, 31.1], zoom: 5.8, pitch: 54, bearing: -12 } },
    { ws: "overview", story: "season", title: "Season dates", text: "When half, then 90%, of a season's detections had been seen, per satellite. Which pairs hold, fail or could not be tested is in Evidence.",
      pose: { mode: "3d", vmode: "density", orbit: false, seam: false, psf: false, center: [71.2, 30.2], zoom: 5.0, pitch: 44, bearing: 0 } },
    { ws: "explore", title: "The observed points", text: "The map shows the detections behind the counts for one satellite and month. A point is one fire pixel on one pass, not a fire or a burned area.",
      pose: { mode: "3d", vmode: "footprints", orbit: false, seam: false, psf: true, center: [73.65, 31.45], zoom: 8.6, pitch: 48, bearing: 12 } },
    { ws: "evidence", ev: "limits", title: "Limits", text: "Read these limits before using any number. S-NPP is a reference satellite, not ground truth; no detection is not no burning." },
  ];
}
let TOUR_I = -1, TOUR_BACKUP = null;
function openTour() {
  if (!RESULT) { toast("The tour needs the first results on screen.", { second: true }); return; }
  closePop(false); hideTip(); closeSheet(); closeDialog();
  TOUR_BACKUP = { ws: UI.ws, story: UI.story, sub: UI.sub, ev: UI.ev, mode: UI.mode, focus: document.activeElement };
  $("tour").hidden = false;
  document.body.classList.add("touring");
  showTour(0, true);
}
function showTour(i, focusTitle) {
  const steps = tourSteps();
  TOUR_I = Math.max(0, Math.min(steps.length - 1, i));
  const s = steps[TOUR_I];
  go(s.ws, { story: s.story, sub: s.sub, ev: s.ev, quiet: true });
  if (s.pose && window.innerWidth >= 700 && window.SeamMap && window.SeamMap.flyPose) {
    window.SeamMap.flyPose(s.pose);
  }
  $("tour-step").textContent = `Step ${TOUR_I + 1} of ${steps.length}`;
  $("tour-title").textContent = s.title;
  $("tour-text").textContent = s.text;
  $("tour-back").setAttribute("aria-disabled", String(TOUR_I === 0));
  $("tour-next").textContent = TOUR_I === steps.length - 1 ? "Finish" : "Next";
  if (focusTitle) $("tour-title").focus();
  else $("tour-live").textContent = `Step ${TOUR_I + 1} of ${steps.length}: ${s.title}. ${s.text}`;
}
function moveTour(delta) {
  const j = TOUR_I + delta;
  if (j >= tourSteps().length) { closeTour(); return; }
  if (j < 0) return;
  showTour(j, false);
}
function closeTour() {
  if ($("tour").hidden) return;
  $("tour").hidden = true;
  document.body.classList.remove("touring");
  $("tour-live").textContent = "";
  TOUR_I = -1;
  const b = TOUR_BACKUP;
  TOUR_BACKUP = null;
  if (b) {
    if (window.SeamMap && window.SeamMap.flyPose) {
      window.SeamMap.flyPose({ mode: b.mode || UI.mode, vmode: "points", orbit: false, seam: false, psf: false });
      const eng = window.SeamMap.engine();
      if (eng) eng.fit(window.SeamMap.bounds(), false);
    }
    go(b.ws, { story: b.story, sub: b.sub, ev: b.ev, quiet: true });  // the view from before the tour comes back
  }
  syncUrl();
  Seam.emit("resize");
  $("tour-btn").focus();
}
function tourKeys(e) {
  if (e.key === "Escape") {
    if (POP_BTN || e.defaultPrevented || !$("dialog").hidden || !$("controls").hidden) return;  // an open box closes first
    e.preventDefault(); closeTour(); return;
  }
  // Arrow keys inside a form control, a chart, the map or a tab list keep their own meaning.
  const own = e.target && e.target.closest && e.target.closest('input, select, textarea, svg, .map-view, [role="tab"]');
  if (e.key === "ArrowRight" && !own) { e.preventDefault(); moveTour(1); return; }
  if (e.key === "ArrowLeft" && !own) { e.preventDefault(); moveTour(-1); }
}

// ---------- theme, motion and printing ----------
const THEMES = ["auto", "light", "dark"], MOTIONS = ["auto", "full", "reduced", "off"];
function setTheme(t, redraw) {
  if (t === "auto") delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = t;
  $("theme-label").textContent = `Theme: ${t === "auto" ? "automatic" : t}`;
  $("theme-btn").setAttribute("aria-label", `Colour theme: ${t === "auto" ? "automatic, follows the computer" : t}. Press to change.`);
  try { localStorage.setItem("seamline-theme", t); } catch (_) { /* storage blocked: the choice lasts for this visit */ }
  if (redraw) { if (RESULT) redrawCharts(); Seam.emit("theme", t); }
}
function setMotion(m, announce) {
  if (m === "auto") delete document.documentElement.dataset.motion; else document.documentElement.dataset.motion = m;
  const eff = motionMode();
  $("motion-label").textContent = `Motion: ${m === "auto" ? `${eff} (system)` : m}`;
  $("motion-btn").setAttribute("aria-label", `Motion: ${m === "auto" ? `follows the computer, now ${eff}` : m}. Full plays transitions and camera moves; Reduced keeps short fades only; Off updates instantly. Press to change.`);
  try { if (m === "auto") localStorage.removeItem("seamline-motion"); else localStorage.setItem("seamline-motion", m); } catch (_) { /* storage blocked */ }
  Seam.emit("motion", eff);
  if (announce) toast(`Motion: ${m === "auto" ? `automatic (${eff})` : m}.`, { second: true });
}
function redrawCharts() {
  renderWorkspaceResults();
}
let PRINT_BACKUP = null;
function beforePrint() {
  // The print summary is one short page set: the opening result, a top-down map and the limits, in the light theme.
  PRINT_BACKUP = { theme: document.documentElement.dataset.theme, ws: UI.ws, story: UI.story, ev: UI.ev, mode: UI.mode };
  document.documentElement.dataset.theme = "light";
  const stamp = new Date().toISOString().slice(0, 16).replace("T", " ");
  $("print-link").textContent = RESULT ? `Seamline print summary. This view: ${shareUrl()} (printed ${stamp} UTC).` : "";
  closePop(false); hideTip(); closeSheet(); closeDialog();
  if (RESULT) { go("overview", { story: "record", quiet: true }); Seam.emit("print", true); Seam.emit("theme", "light"); }
}
function afterPrint() {
  const b = PRINT_BACKUP;
  if (!b) return;
  PRINT_BACKUP = null;
  if (b.theme) document.documentElement.dataset.theme = b.theme; else delete document.documentElement.dataset.theme;
  Seam.emit("print", false);
  if (RESULT) { go(b.ws, { story: b.story, ev: b.ev, quiet: true }); redrawCharts(); Seam.emit("theme", b.theme || "auto"); }
}

// ---------- exports ----------
function renderExport() {
  const x = RESULT.export;
  const btns = document.querySelectorAll('[data-export="detections.csv"]');
  if (!x || !btns.length) return;
  const count = x.detections_rows == null ? "" : `${fmt(x.detections_rows)} rows; `;
  const txt = x.detections_format === "zip"
    ? `Detections, one row each (${count}CSV inside a ZIP)`
    : `Detections, one row each (${count}CSV)`;
  btns.forEach((b) => { b.textContent = txt; });
  const held = $("export-held");
  held.hidden = !x.rows_held_out;
  held.textContent = x.rows_held_out
    ? "Rows inside the test windows of Protocol P04 (G01 and G02) are left out of the detections file until those tests run, and no row count is shown meanwhile." : "";
}

// Exports use one stable snapshot: the selection on screen. While a new selection is loading they wait,
// so a file is never labelled with one selection and filled from another. Success is said only once the file exists.
async function doExport(kind, btn) {
  if (!RESULT) { toast("Nothing to export yet: wait for the first results.", { error: true }); return; }
  if (PENDING) { toast("A new selection is still loading. Export again when it has finished, so the file matches the screen.", { error: true }); return; }
  const snapshot = RESULT.request;
  const big = kind === "detections.csv" && RESULT.export && RESULT.export.detections_format === "zip";
  const rows = RESULT.export && RESULT.export.detections_rows != null ? `${fmt(RESULT.export.detections_rows)} rows` : "the rows";
  if (btn) btn.classList.add("is-pending");
  toast(big ? `Preparing ${rows} as a ZIP; this can take up to half a minute…` : "Preparing the export…", { sticky: true });
  try {
    const r = await post(`/api/export/${kind}`, snapshot);
    const blob = await r.blob();
    const name = (r.headers.get("Content-Disposition") || "").match(/filename="?([^";]+)"?/);
    save(blob, name ? name[1] : `seamline_${kind}`);
    toast(`Saved ${name ? name[1] : kind} (${RESULT.region}, ${snapshot.years[0]}–${snapshot.years[1]}).`);
    if (btn) { btn.classList.add("is-done"); setTimeout(() => btn.classList.remove("is-done"), 1600); }
  } catch (e) { showError(`The export failed: ${e.message}`); }
  finally { if (btn) btn.classList.remove("is-pending"); }
}
function save(blob, name) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
}
function exportSvg() {
  if (!RESULT) { toast("Nothing to export yet: wait for the first results.", { error: true }); return; }
  if (PENDING) { toast("A new selection is still loading. Export again when it has finished, so the file matches the screen.", { error: true }); return; }
  if (!$("series").querySelector("svg")) renderSeries();
  const svg = $("series").querySelector("svg");
  if (!svg) { toast("The record chart has no detections to export for this selection.", { error: true }); return; }
  const snapshot = RESULT, view = $("view").value, viewName = $("view").selectedOptions[0].text, LOG = UI.scale !== "lin";
  const pts = aggregate(view), runs = relRuns(pts);
  const said = ["observed", "converted", "mixed", "gap"].map((c) => {
    const rs = runs.filter((r) => r.c === c);
    if (!rs.length) return "";
    const spans = rs.slice(0, 4).map((r) => (r.from === r.to ? r.from : `${r.from}–${r.to}`));
    return `${REL_TEXT[c].split(" (")[0]}: ${spans.join(", ")}${rs.length > 4 ? ` (+${rs.length - 4})` : ""}`;
  }).filter(Boolean).join("; ");
  const vb = (svg.getAttribute("viewBox") || "0 0 760 372").split(/\s+/).map(Number);
  const W = vb[2] || 760, H = vb[3] || 372;
  const measure = document.createElement("canvas").getContext("2d");
  const wrap = (text, font = "10.5px system-ui,sans-serif") => {
    if (measure) measure.font = font;
    const lines = []; let current = "";
    for (const word of text.split(/\s+/)) {
      const next = current ? `${current} ${word}` : word;
      if (current && (measure ? measure.measureText(next).width : next.length * 6) > W - 24) {
        lines.push(current); current = word;
      } else current = next;
    }
    if (current) lines.push(current);
    return lines;
  };
  const titleLines = wrap(`${snapshot.region} (${snapshot.years[0]}–${snapshot.years[1]}): ${viewName} · ${LOG ? "log scale" : "linear scale"} · model ${snapshot.model}`, "600 13px system-ui,sans-serif");
  const unitLines = wrap(`Units: ${snapshot.units} · Passes: ${snapshot.passes} · Reference: S-NPP VIIRS (cross-sensor agreement, not ground truth)`);
  const ident = snapshot.data_identity || (META && META.data_identity) || "";
  const sha = (META && META.detections_sha256) || "";
  const footerLines = [
    `Source band — Solid: observed S-NPP · Hatched: converted from Aqua (${snapshot.model}) or NOAA-20 (Punjab Nov 2026 bridge) · Grey: missing/partial/untyped (${said || "none"})`,
    `${snapshot.years[1] >= 2026 ? "Standard archive through Dec 2025 (type 0); 2026 cached supplement (May 2026 missing; Aug–Nov 2026 NRT untyped)." : "Standard archive through Dec 2025 (type 0)."} Missing is not zero; no detection is not no burning.`,
    "Seamline · NASA FIRMS / LANCE / ESDIS data (provided as is; not for safety-of-life decisions)",
    `data_identity ${ident}`, `Historical SHA-256 ${sha}`,
  ].flatMap((text) => wrap(text));
  const topPad = titleLines.length * 17 + unitLines.length * 14 + 4 * 15 + 22;
  const botPad = footerLines.length * 14 + 24;
  const copy = svg.cloneNode(true);
  copy.setAttribute("xmlns", NS);
  copy.setAttribute("viewBox", `0 ${-topPad} ${W} ${H + topPad + botPad}`);
  copy.removeAttribute("tabindex");
  const ink = css("--ink"), ink2 = css("--ink2"), muted = css("--muted"), surface = css("--surface");
  const cH = css("--harm"), cNaive = css("--naive"), cAqua = css("--aqua");
  copy.querySelectorAll("text").forEach((t) => { if (!t.getAttribute("style")) t.setAttribute("style", `fill:${ink2};font:11px system-ui,sans-serif`); });
  copy.insertBefore(el("rect", { x: 0, y: -topPad, width: W, height: H + topPad + botPad, fill: surface }), copy.firstChild);
  const line = (x, y, text, fill = ink2, font = "11px system-ui,sans-serif") => {
    const t = el("text", { x, y, style: `fill:${fill};font:${font}` });
    t.textContent = text;
    copy.appendChild(t);
  };
  let textY = -topPad + 19;
  titleLines.forEach((text) => { line(12, textY, text, ink, "600 13px system-ui,sans-serif"); textY += 17; });
  unitLines.forEach((text) => { line(12, textY, text, muted, "10.5px system-ui,sans-serif"); textY += 14; });
  [[`● Harmonised, S-NPP-equivalent (${snapshot.model}, solid)`, cH],
   ["◆ Naive stitch, diagnostic only (adds NOAA-20 from Apr 2018, dashed)", cNaive],
   ["■ Aqua MODIS only (thin)", cAqua],
   ["▮ Grey band: rough range before Feb 2012 (covered 59% of 2012–13 Punjab test months)", muted]]
    .forEach(([text, color]) => { line(12, textY, text, color); textY += 15; });
  footerLines.forEach((text, i) => line(12, H + 18 + i * 14, text, muted, "10.5px system-ui,sans-serif"));
  const name = `seamline_${snapshot.region.replace(/\W+/g, "_")}_${snapshot.years[0]}-${snapshot.years[1]}_${view}_${snapshot.model}.svg`;
  save(new Blob([new XMLSerializer().serializeToString(copy)], { type: "image/svg+xml" }), name);
  toast(`Saved ${name} (${snapshot.region}, ${snapshot.years[0]}–${snapshot.years[1]}, ${viewName}).`);
}

// ---------- init ----------
function resetSelection() {
  const defCalYear = Math.min(2025, META.years[1]);
  $("region").value = "Punjab";
  $("use-box").checked = false;
  ["bw", "bs", "be", "bn"].forEach((k) => { $(k).value = ""; });
  $("y0").value = String(META.years[0]); $("y1").value = String(META.years[1]);
  $("cy").value = String(defCalYear); $("cm").value = "11";
  const r = document.querySelector(`input[name="model"][value="${META.default_model}"]`);
  if (r) r.checked = true;
  $("view").value = "OctNov"; $("cal-src").value = "H";
  Object.assign(UI, JSON.parse(JSON.stringify(UI_DEFAULT)), { ws: UI.ws, mode: UI.mode });  // theme, motion and the 2D/3D choice are preferences: they stay
  DAILY_SET = false;
  syncScale();
  Seam.emit("reset");
  run();
  toast(`Selection reset: Punjab, ${META.years[0]}–${META.years[1]}, November ${defCalYear}, model ${META.default_model}.`, { second: true });
}
function syncScale() {
  for (const b of $("scale-seg").querySelectorAll("button")) b.setAttribute("aria-pressed", String(b.dataset.scale === UI.scale));
}

async function init() {
  let saved = "auto", motion = "auto";
  try { saved = localStorage.getItem("seamline-theme") || localStorage.getItem("firebridge-theme") || "dark"; motion = localStorage.getItem("seamline-motion") || "auto"; } catch (_) { /* storage blocked */ }
  setTheme(THEMES.includes(saved) ? saved : "auto", false);
  setMotion(MOTIONS.includes(motion) ? motion : "auto", false);
  placeInk();
  async function startupJson(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }
  const boundaries = startupJson("/api/boundaries").catch(() => null);
  try {
    [META, AREAS] = await Promise.all(["/api/meta", "/api/areas"].map(startupJson));
  } catch (e) {
    LAST_ERROR = "Could not reach the analysis service. Check your connection and press Try again.";
    showError(LAST_ERROR); renderSummary(); window.SeamIntro?.dismiss(true);
    Seam.emit("analysis-error", LAST_ERROR);
    return;
  }
  if (!META || !Array.isArray(META.regions) || !Array.isArray(META.years) || !AREAS?.areas) {
    LAST_ERROR = "The analysis service responded without its startup tables. Press Try again to reload.";
    showError(LAST_ERROR); renderSummary(); window.SeamIntro?.dismiss(true);
    Seam.emit("analysis-error", LAST_ERROR);
    return;
  }
  fillSelect($("region"), META.regions.map((r) => [r, r]), "Punjab");
  $("area-list").innerHTML = META.regions.map((r) => `<button type="button" data-area="${esc(r)}" aria-pressed="false">${esc(r)}</button>`).join("");
  const years = [];
  for (let y = META.years[0]; y <= META.years[1]; y++) years.push([y, y]);
  const months = MONTH_FULL.map((n, i) => [i + 1, n]);
  const defCalYear = Math.min(2025, META.years[1]);
  fillSelect($("y0"), years, META.years[0]);
  fillSelect($("y1"), years, META.years[1]);
  fillSelect($("cy"), years, defCalYear);
  fillSelect($("cm"), months, 11);
  fillSelect($("daily-year"), years, defCalYear);
  fillSelect($("daily-month"), months, 11);
  fillSelect($("map-year"), years, defCalYear);
  fillSelect($("map-month"), months, 11);
  const cleanStatus = String(META.status || "").replace(/Pre-event work with true dates\.?\s*/i, "").replace(/Local research prototype\.?\s*/i, "Cross-sensor active-fire harmonisation (MCD14ML C6.1 ↔ VNP14IMG C2). ").trim();
  $("status-chip").textContent = cleanStatus;
  $("foot-status").textContent = cleanStatus;
  Seam.on("points-loaded", () => { if (RESULT && UI.ws === "overview") renderInsight(); });
  $("foot-meta").textContent = `${fmt(META.rows)} detections from ${META.files} hash-checked files; processed table built ${META.built_utc} (SHA-256 ${META.detections_sha256.slice(0, 12)}…${META.data_identity ? `, data identity ${META.data_identity.slice(0, 12)}…` : ""}).`;
  // A shared link restores its view; anything in it that is not valid is left at the default and named.
  const { state, ignored } = parseState(location.search, META);
  // On a phone the simpler top-down map is the default; 3D stays one tap away (and a link can ask for it).
  if (window.innerWidth < 700) UI.mode = "2d";
  applyState(state);
  if (ignored.length) toast(`Some parts of the link were not valid and were left at their defaults: ${ignored.join(", ")}.`, { second: true, sticky: true });
  syncScale();
  syncMapMonth();
  go(UI.ws, { story: UI.story, sub: UI.sub, ev: UI.ev, quiet: true });

  // selection: every control applies at once; a late reply never overwrites a newer choice (see run)
  $("controls").addEventListener("submit", (e) => { e.preventDefault(); run(); });
  for (const id of ["region", "y0", "y1", "cm", "cy"]) $(id).addEventListener("change", () => { if (id === "region") $("use-box").checked = false; run(); });
  document.querySelectorAll('input[name="model"]').forEach((r) => r.addEventListener("change", run));
  $("use-box").addEventListener("change", () => { if (!$("use-box").checked || !boxProblem(["bw", "bs", "be", "bn"].map((k) => $(k).value))) run(); else showError(boxProblem(["bw", "bs", "be", "bn"].map((k) => $(k).value))); });
  $("area-list").addEventListener("click", (e) => { const b = e.target.closest("button[data-area]"); if (b) Seam.selectArea(b.dataset.area); });
  $("reset-btn").addEventListener("click", resetSelection);
  $("ctx-open").addEventListener("click", (e) => openSheet(null, e.currentTarget));
  document.querySelectorAll(".chip-btn[data-open]").forEach((b) => b.addEventListener("click", () => openSheet(b.dataset.open, b)));
  $("controls-close").addEventListener("click", closeSheet);
  $("sheet-shade").addEventListener("click", closeSheet);
  $("controls").addEventListener("keydown", (e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); closeSheet(); } else trapTab($("controls"), e); });
  $("dialog-close").addEventListener("click", closeDialog);
  $("dialog-shade").addEventListener("click", closeDialog);
  $("dialog").addEventListener("keydown", (e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); closeDialog(); } else trapTab($("dialog"), e); });

  // navigation
  $("ws-nav").addEventListener("click", (e) => { const b = e.target.closest("button[data-ws]"); if (b) go(b.dataset.ws); });
  $("story-tabs").addEventListener("click", (e) => { const b = e.target.closest("[data-story]"); if (b) setStory(b.dataset.story); });
  $("cal-subnav").addEventListener("click", (e) => { const b = e.target.closest("[data-sub]"); if (b) setSub(b.dataset.sub); });
  $("ev-nav").addEventListener("click", (e) => { const b = e.target.closest("[data-ev]"); if (b) setEv(b.dataset.ev); });
  for (const id of ["story-tabs", "cal-subnav", "ev-nav"]) $(id).addEventListener("keydown", tabKeys);
  window.addEventListener("popstate", () => {  // Back and Forward restore the view, and the selection if it changed
    const before = JSON.stringify(payload());
    Object.assign(UI, JSON.parse(JSON.stringify(UI_DEFAULT)));
    applyState(parseState(location.search, META).state);
    syncScale(); syncMapMonth();
    go(UI.ws, { story: UI.story, sub: UI.sub, ev: UI.ev, quiet: true });
    Seam.emit("filters");
    if (JSON.stringify(payload()) !== before) run();
  });
  window.addEventListener("resize", placeInk);
  let rsz = 0;
  window.addEventListener("resize", () => { clearTimeout(rsz); rsz = setTimeout(() => { if (RESULT) redrawCharts(); }, 160); });
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(placeInk);

  // charts and calendar
  $("view").addEventListener("change", () => { if (RESULT) { renderSeries(); syncUrl(); } });
  $("cal-src").addEventListener("change", () => { if (RESULT) { renderCalendar(); syncUrl(); } });
  $("scale-seg").addEventListener("click", (e) => { const b = e.target.closest("[data-scale]"); if (!b) return; UI.scale = b.dataset.scale; syncScale(); if (RESULT) { renderSeries(); syncUrl(); } });
  $("daily-month").addEventListener("change", () => setDayMonth(Number($("daily-year").value), Number($("daily-month").value)));
  $("daily-year").addEventListener("change", () => setDayMonth(Number($("daily-year").value), Number($("daily-month").value)));
  $("daily-prev").addEventListener("click", () => { stepDaily(-1); UI.mapDay = 0; syncMapMonth(); Seam.emit("daymonth"); });
  $("daily-next").addEventListener("click", () => { stepDaily(1); UI.mapDay = 0; syncMapMonth(); Seam.emit("daymonth"); });
  if ($("map-prev-m")) $("map-prev-m").addEventListener("click", () => { stepDaily(-1); UI.mapDay = 0; syncMapMonth(); Seam.emit("daymonth"); });
  if ($("map-next-m")) $("map-next-m").addEventListener("click", () => { stepDaily(1); UI.mapDay = 0; syncMapMonth(); Seam.emit("daymonth"); });
  if ($("ex-sheet-toggle")) {
    $("ex-sheet-toggle").addEventListener("click", () => {
      const side = $("ex-side");
      if (!side) return;
      const open = side.hidden;
      side.hidden = !open;
      side.classList.toggle("is-collapsed", !open);
      $("ex-sheet-toggle").setAttribute("aria-expanded", String(open));
      $("ex-sheet-toggle").textContent = open ? "Hide Layers & Filters" : "View, Layers & Filters";
    });
  }
  const syncDailyToCompare = () => {
    if (!RESULT || !RESULT.request || !RESULT.request.month) return;
    const [cy, cm] = RESULT.request.month;
    setDayMonth(cy, cm);
    toast(`Map & daily view synced to compare month (${MONTH_FULL[cm - 1]} ${cy}).`, { second: true });
  };
  if ($("map-sync-compare")) $("map-sync-compare").addEventListener("click", syncDailyToCompare);
  if ($("daily-sync-compare")) $("daily-sync-compare").addEventListener("click", syncDailyToCompare);
  if ($("compare-to-map")) {
    $("compare-to-map").addEventListener("click", () => {
      if (!RESULT || !RESULT.request || !RESULT.request.month) return;
      const [cy, cm] = RESULT.request.month;
      if (setDayMonth(cy, cm)) go("explore");
    });
  }
  if ($("util-more-btn") && $("util-drawer")) {
    $("util-more-btn").addEventListener("click", () => {
      const open = $("util-drawer").classList.toggle("is-open");
      $("util-more-btn").setAttribute("aria-expanded", String(open));
    });
  }
  if ($("play-transition-btn")) {
    $("play-transition-btn").addEventListener("click", () => {
      if (window.SeamMap && window.SeamMap.playTransition) window.SeamMap.playTransition();
    });
  }
  const nav = document.querySelector("#daily-card .daily-nav");
  if (nav && !$("daily-passes")) {  // show each satellite's day and night passes as rows, without a mouse
    nav.insertAdjacentHTML("beforeend", `<label class="inline daily-passes"><input type="checkbox" id="daily-passes"> Day and night passes</label>` +
      `<button type="button" class="btn" id="daily-csv">Download this month (CSV)</button>`);
    $("daily-passes").addEventListener("change", (e) => { DAILY_PASSES = e.target.checked; if (DAILY) renderDaily(); });
    $("daily-csv").addEventListener("click", dailyCsv);
  }
  const head = document.querySelector("#series-card .card-head");
  if (head && !$("series-table-btn")) {  // the record chart's numbers as a table (keyboard and screen readers)
    head.insertAdjacentHTML("beforeend", `<button type="button" class="btn" id="series-table-btn" aria-expanded="false" aria-controls="series-table">Show as table</button>`);
    $("series-table-btn").addEventListener("click", () => {
      const t = $("series-table");
      if (!t) return;
      const show = t.hidden;
      t.hidden = !show;
      $("series-table-btn").setAttribute("aria-expanded", String(show));
      $("series-table-btn").textContent = show ? "Hide table" : "Show as table";
    });
  }
  $("cal-table-btn").addEventListener("click", () => {
    const t = $("cal-table"), show = t.hidden;
    t.hidden = !show;
    $("cal-table-btn").setAttribute("aria-expanded", String(show));
    $("cal-table-btn").textContent = show ? "Hide table" : "Show as table";
  });

  // one listener for buttons that are drawn again with each result
  document.addEventListener("click", (e) => {
    const t = e.target.closest ? e.target : null;
    if (!t) return;
    const info = t.closest("button.info");
    const p = $("prov-pop");
    if (info) { if (POP_BTN === info && p && !p.hidden) closePop(true); else openPop(info); return; }
    if (p && !p.hidden && !p.contains(t)) closePop(false);
    const goBtn = t.closest("[data-go]");
    if (goBtn) { const [ws, part] = goBtn.dataset.go.split(":"); go(ws, ws === "calendar" ? { sub: part } : ws === "evidence" ? { ev: part } : {}); return; }
    const season = t.closest("[data-season]");
    if (season) { UI.season = season.dataset.season; renderInsight(); syncUrl(); return; }
    if (t.closest("#summary-more")) { summaryDialog(t.closest("#summary-more")); return; }
    if (t.closest("#retry-btn")) { if (META) run(); else init(); return; }
    const cal = t.closest("[data-cal-act]");
    if (cal) {
      const box = $("cal-detail-month"), y = Number(box.dataset.y), m = Number(box.dataset.m);
      if (cal.dataset.calAct === "month") { $("cy").value = String(y); $("cm").value = String(m); run(); }
      else if (setDayMonth(y, m)) go(cal.dataset.calAct === "map" ? "explore" : "calendar", cal.dataset.calAct === "map" ? {} : { sub: "days" });
      return;
    }
    const ex = t.closest("[data-export]");
    if (ex) { $("export-menu").hidden = true; $("export-btn").setAttribute("aria-expanded", "false"); doExport(ex.dataset.export, ex.closest(".menu") ? $("export-btn") : ex); return; }
    const act = t.closest("[data-act]");
    if (act) {
      $("export-menu").hidden = true; $("export-btn").setAttribute("aria-expanded", "false");
      if (act.dataset.act === "svg") { go("calendar", { sub: "months" }); exportSvg(); }
      else if (act.dataset.act === "daily-csv") dailyCsv();
      else Seam.emit("export-map");
      return;
    }
    if (!$("export-menu").hidden && !t.closest("#export-menu") && !t.closest("#export-btn")) { $("export-menu").hidden = true; $("export-btn").setAttribute("aria-expanded", "false"); }
    if ($("util-drawer") && $("util-drawer").classList.contains("is-open") && !t.closest("#util-drawer") && !t.closest("#util-more-btn")) {
      $("util-drawer").classList.remove("is-open");
      if ($("util-more-btn")) $("util-more-btn").setAttribute("aria-expanded", "false");
    }
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && POP_BTN) { e.preventDefault(); closePop(true); return; }
    if (e.key === "Escape" && !$("export-menu").hidden) { $("export-menu").hidden = true; $("export-btn").setAttribute("aria-expanded", "false"); $("export-btn").focus(); return; }
    if (!$("tour").hidden) tourKeys(e);
  });
  document.addEventListener("scroll", (e) => { if (POP_BTN && e.target !== $("prov-pop") && !(e.target.closest && e.target.closest("#prov-pop"))) closePop(false); }, true);
  $("export-btn").addEventListener("click", () => {
    const m = $("export-menu"), show = m.hidden;
    m.hidden = !show;
    $("export-btn").setAttribute("aria-expanded", String(show));
    if (show) m.querySelector("button").focus();
  });
  $("svg-export").addEventListener("click", exportSvg);
  $("tour-btn").addEventListener("click", openTour);
  $("tour-btn-2").addEventListener("click", openTour);
  $("tour-next").addEventListener("click", () => moveTour(1));
  $("tour-back").addEventListener("click", () => { if ($("tour-back").getAttribute("aria-disabled") !== "true") moveTour(-1); });
  $("tour-close").addEventListener("click", closeTour);
  $("copy-link").addEventListener("click", copyLink);
  $("print-btn").addEventListener("click", () => window.print());
  $("theme-btn").addEventListener("click", () => {
    const now = document.documentElement.dataset.theme || "auto";
    setTheme(THEMES[(THEMES.indexOf(now) + 1) % THEMES.length], true);
  });
  $("motion-btn").addEventListener("click", () => {
    const now = document.documentElement.dataset.motion || "auto";
    setMotion(MOTIONS[(MOTIONS.indexOf(now) + 1) % MOTIONS.length], true);
  });
  window.addEventListener("beforeprint", beforePrint);
  window.addEventListener("afterprint", afterPrint);
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { if (RESULT) redrawCharts(); Seam.emit("theme", "auto"); });
  window.matchMedia("(prefers-reduced-motion: reduce)").addEventListener("change", () => setMotion(document.documentElement.dataset.motion || "auto", false));
  run();
  GEO = await boundaries;
  if (!GEO || !Array.isArray(GEO.features)) {
    LAST_ERROR = "The province boundaries could not be loaded. Reload the workspace to restore maps and related views.";
    showError(LAST_ERROR);
    window.SeamIntro?.dismiss(true);
    Seam.emit("map-error", LAST_ERROR);
    return;
  }
  Seam.emit("ready");
}

Object.assign(Seam, {
  UI, SATS, SAT_INFO, MONTHS, MONTH_FULL, fmt, sfmt, esc, css, el, post, showTip, hideTip, toast, motionMode, go, setStory, setSub, setEv,
  openDialog, closeDialog, openSheet, summaryDialog, retryAnalysis: run, exportData: doExport, setDayMonth, syncUrl, infoBtn, boxProblem, trapTab, drawIn,
  save: (blob, name) => save(blob, name),
  meta: () => META, geo: () => GEO, areas: () => AREAS, result: () => RESULT, daily: () => DAILY, pending: () => PENDING,
  selectedRequest: payload,
  initialMapMonth: (request) => DAILY_SET ? Seam.dayMonth() : request.month,
  dailySettled: () => DAILY_SETTLED,
  dayMonth: () => [Number($("daily-year").value), Number($("daily-month").value)],
  selectArea(name) {
    if (!META || !META.regions.includes(name)) return;
    $("region").value = name;
    $("use-box").checked = false;
    run();
  },
  selectModel(name) {
    if(!META?.models.includes(name))return false;
    const input=document.querySelector(`input[name="model"][value="${name}"]`);
    if(!input)return false;input.checked=true;run();return true;
  },
  selectBox(b) {
    ["bw", "bs", "be", "bn"].forEach((k, i) => { $(k).value = String(Math.round(b[i] * 1000) / 1000); });
    $("use-box").checked = true;
    $("box-details").open = true;
    run();
  },
});
if (IN_BROWSER) { window.Seam = Seam; init(); }
if (typeof module !== "undefined" && module.exports) module.exports = { parseState, stateQuery, relClass, relRuns, VIEWS, CAL_SOURCES };
