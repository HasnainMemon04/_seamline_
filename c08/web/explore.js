// Seamline map controller and the plain-canvas 2D engine.
// One map instance serves Overview and Explore (it is moved, never duplicated). The controller owns the filters,
// legend, per-satellite counts, date scrubber, historical playback, inspector and rectangle drawing; the engine
// (MapLibre in map3d.js, or the canvas engine below when WebGL is missing or low power is chosen) only draws.
// Filters change what is drawn, never the analysis: totals and exports always cover the whole selected area.
(function () {
  "use strict";
  if (typeof window === "undefined" || !window.Seam) return;
  const S = window.Seam, $ = (id) => document.getElementById(id);
  const { fmt, esc, css, SATS, SAT_INFO, MONTH_FULL } = S;
  // Approximate city positions, for orientation only (name, lon, lat, smallest zoom at which the 3D map shows the name).
  const CITIES = [["Karachi", 67.01, 24.86, 0], ["Lahore", 74.34, 31.55, 0], ["Quetta", 66.98, 30.18, 0], ["Multan", 71.47, 30.2, 5.4], ["Islamabad", 73.05, 33.69, 5.8], ["Peshawar", 71.58, 34.01, 5.8], ["Hyderabad", 68.37, 25.39, 5.8]];
  const D2R = Math.PI / 180;
  const mercY = (lat) => Math.log(Math.tan(Math.PI / 4 + (lat * D2R) / 2)) / D2R;      // degrees of "mercator latitude"
  const unmercY = (m) => (2 * Math.atan(Math.exp(m * D2R)) - Math.PI / 2) / D2R;

  function colors() {
    const dark = css("color-scheme") === "dark";
    return { sky: css("--map-sky"), ocean: css("--map-ocean") || css("--map-sky"), river: css("--map-river") || css("--accent"),
             land: css("--map-land"), landDim: css("--map-land-dim") || css("--map-land"), sel: css("--map-sel"), line: css("--map-line"), lineSel: css("--map-line-sel"),
             terra: css("--terra"), aqua: css("--aqua"), snpp: css("--snpp"), n20: css("--n20"), n21: css("--n21"), ink: css("--ink"), halo: css("--surface"), muted: css("--muted"),
             heat1: css("--heat-1"), heat2: css("--heat-2"), heat3: css("--heat-3"), heat4: css("--heat-4"),
             shadow: dark ? "#000000" : "#4d5357", highlight: dark ? "#42555b" : "#ffffff", font: css("--font"), dark };
  }
  const SAT_COLOR = (c, p) => [c.terra, c.aqua, c.snpp, c.n20, c.n21][p];

  // ---------------------------------------------------------------------------------------------------------
  // Canvas engine: a complete top-down map without WebGL. Same projection family (Web Mercator), same data,
  // same filters and picking as the 3D engine. Also used for the paired maps in the Comparison Studio.
  // ---------------------------------------------------------------------------------------------------------
  function createCanvas(container, opts) {
    const cv = document.createElement("canvas");
    cv.className = "fallback";
    cv.tabIndex = opts.focusable === false ? -1 : 0;
    cv.setAttribute("role", "img");
    cv.setAttribute("aria-label", opts.label || "Top-down map of observed detections. Arrow keys pan, plus and minus zoom. The list of detections is the keyboard alternative for inspecting points.");
    container.appendChild(cv);
    const ctx = cv.getContext("2d");
    let c = opts.colors, W = 1, H = 1, dpr = 1, cx = 69.5, cm = mercY(30.3), k = 30, raf = 0, dead = false;
    let sel = { region: "", bbox: null }, P = null, F = { sats: [2], dn: "DN", day: 0 }, picked = null, overlay = null, interactive = true;
    let vmode = opts.vmode || "points", psfOn = false;
    const paths = [];
    const px = (lon) => W / 2 + (lon - cx) * k, py = (lat) => H / 2 - (mercY(lat) - cm) * k;
    function build() {
      paths.length = 0;
      for (const f of (opts.geo || { features: [] }).features) {
        const polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
        paths.push({ name: f.properties.shapeName, polys });
      }
    }
    const shown = (i) => F.sats.includes(P.p[i]) && (F.dn === "DN" || (F.dn === "N") === (P.dn[i] === 1)) && (!F.day || P.day[i] === F.day);
    function draw() {
      raf = 0;
      if (dead) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.fillStyle = c.sky; ctx.fillRect(0, 0, W, H);
      const all = sel.region === "Pakistan" && !sel.bbox;
      for (const pass of ["fill", "line", "sel"]) for (const f of paths) {
        const on = !sel.bbox && (all || f.name === sel.region);
        if (pass === "sel" && !on) continue;
        ctx.beginPath();
        for (const poly of f.polys) for (const ring of poly) { ring.forEach(([x, y], i) => (i ? ctx.lineTo(px(x), py(y)) : ctx.moveTo(px(x), py(y)))); ctx.closePath(); }
        if (pass === "fill") { ctx.fillStyle = on ? c.sel : c.land; ctx.fill("evenodd"); f.path = null; }
        else { ctx.lineJoin = "round"; ctx.strokeStyle = pass === "sel" ? c.lineSel : c.line; ctx.lineWidth = pass === "sel" ? 2.6 : 1; ctx.stroke(); }
        if (pass === "fill" && overlay && overlay.img.complete && f === paths[paths.length - 1]) {
          const [w, s, e, n] = overlay.wsen;
          ctx.globalAlpha = overlay.opacity; ctx.imageSmoothingEnabled = false;
          ctx.drawImage(overlay.img, px(w), py(n), px(e) - px(w), py(s) - py(n));
          ctx.globalAlpha = 1;
        }
      }
      if (sel.bbox) {
        const [w, s, e, n] = sel.bbox;
        ctx.fillStyle = c.sel; ctx.globalAlpha = 0.4; ctx.fillRect(px(w), py(n), px(e) - px(w), py(s) - py(n)); ctx.globalAlpha = 1;
        ctx.setLineDash([7, 5]); ctx.strokeStyle = c.lineSel; ctx.lineWidth = 2.4; ctx.strokeRect(px(w), py(n), px(e) - px(w), py(s) - py(n)); ctx.setLineDash([]);
      }
      if (opts.labels !== false) {
        ctx.textAlign = "center"; ctx.textBaseline = "middle";
        for (const [name, a] of Object.entries(opts.areas || {})) {
          if (name === "Pakistan" || name === "Islamabad Capital Territory") continue;
          ctx.font = `600 11.5px ${c.font}`; ctx.fillStyle = name === sel.region ? c.lineSel : c.muted;
          ctx.fillText(name.toUpperCase(), px(a.centre[0]), py(a.centre[1]));
        }
        ctx.textAlign = "left"; ctx.font = `500 11.5px ${c.font}`; ctx.fillStyle = c.muted;
        for (const [name, lon, lat] of CITIES) { ctx.beginPath(); ctx.arc(px(lon), py(lat), 2, 0, 7); ctx.fill(); ctx.fillText(name, px(lon) + 6, py(lat)); }
      }
      if (P) {
        const baseR = Math.max(2.2, Math.min(6, k / 14));
        const r = vmode === "density" ? Math.max(5.5, baseR * 2.1) : baseR;
        for (const sat of F.sats) {            // one pass per satellite keeps each colour's points together
          const col = SAT_COLOR(c, sat);
          if (vmode === "footprints") {
            ctx.strokeStyle = col; ctx.fillStyle = col;
            for (let i = 0; i < P.lon.length; i++) {
              if (P.p[i] !== sat || !shown(i)) continue;
              const x = px(P.lon[i]), y = py(P.lat[i]);
              if (x < -18 || y < -18 || x > W + 18 || y > H + 18) continue;
              const sw = Math.max(3, (P.scan[i] || (sat < 2 ? 1.0 : 0.375)) * (k / 111.32));
              const tr = Math.max(3, (P.track[i] || (sat < 2 ? 1.0 : 0.375)) * (k / 110.57));
              ctx.globalAlpha = 0.35; ctx.fillRect(x - sw * 0.5, y - tr * 0.5, sw, tr);
              ctx.globalAlpha = 0.9; ctx.lineWidth = 1; ctx.strokeRect(x - sw * 0.5, y - tr * 0.5, sw, tr);
              if (psfOn && sat < 2) {
                ctx.globalAlpha = 0.25; ctx.strokeRect(x - sw, y - tr * 0.5, sw * 2, tr);
              }
            }
            ctx.globalAlpha = 1;
            continue;
          }
          ctx.beginPath();
          for (let i = 0; i < P.lon.length; i++) {
            if (P.p[i] !== sat || !shown(i)) continue;
            const x = px(P.lon[i]), y = py(P.lat[i]);
            if (x < -12 || y < -12 || x > W + 12 || y > H + 12) continue;
            ctx.moveTo(x + r, y); ctx.arc(x, y, r, 0, 6.2832);
          }
          if (vmode === "density") {
            ctx.fillStyle = col; ctx.globalAlpha = 0.16; ctx.fill(); ctx.globalAlpha = 1;
          } else if (sat < 2) { ctx.fillStyle = c.halo; ctx.globalAlpha = 0.55; ctx.fill(); ctx.globalAlpha = 1; ctx.strokeStyle = col; ctx.lineWidth = 1.8; ctx.stroke(); }
          else { ctx.fillStyle = col; ctx.globalAlpha = 0.92; ctx.fill(); ctx.globalAlpha = 1; ctx.strokeStyle = c.halo; ctx.lineWidth = 0.8; ctx.stroke(); }
        }
        if (picked != null && picked < P.lon.length) { ctx.beginPath(); ctx.arc(px(P.lon[picked]), py(P.lat[picked]), 11, 0, 7); ctx.strokeStyle = c.ink; ctx.lineWidth = 2.5; ctx.stroke(); }
      }
      if (opts.scale !== false) {          // scale bar: true at the centre latitude of the view
        const kmPerPx = (111.32 * Math.cos(unmercY(cm) * D2R)) / k;
        const nice = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000].filter((v) => v / kmPerPx <= 150).pop() || 1;
        const len = nice / kmPerPx, x0 = W - len - 16, y0 = H - 14;
        ctx.strokeStyle = c.ink; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(x0, y0 - 5); ctx.lineTo(x0, y0); ctx.lineTo(x0 + len, y0); ctx.lineTo(x0 + len, y0 - 5); ctx.stroke();
        ctx.fillStyle = c.ink; ctx.font = `500 11.5px ${c.font}`; ctx.textAlign = "right"; ctx.textBaseline = "alphabetic"; ctx.fillText(`${nice} km · north is up`, W - 16, y0 - 8);
      }
    }
    const invalidate = () => { if (!raf && !dead) raf = requestAnimationFrame(draw); };
    function resize() {
      const r = container.getBoundingClientRect();
      if (!r.width || !r.height) return;
      W = r.width; H = r.height; dpr = Math.min(2, window.devicePixelRatio || 1);
      cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
      cv.style.width = W + "px"; cv.style.height = H + "px";
      draw();
    }
    function nearest(x, y) {
      if (!P) return null;
      let best = null, bd = 81;
      for (let i = 0; i < P.lon.length; i++) {
        if (!shown(i)) continue;
        const d = (px(P.lon[i]) - x) ** 2 + (py(P.lat[i]) - y) ** 2;
        if (d < bd) { bd = d; best = i; }
      }
      return best;
    }
    function areaAt(x, y) {
      for (const f of paths) {
        ctx.beginPath();
        for (const poly of f.polys) for (const ring of poly) { ring.forEach(([a, b], i) => (i ? ctx.lineTo(px(a), py(b)) : ctx.moveTo(px(a), py(b)))); ctx.closePath(); }
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        const hit = ctx.isPointInPath(x, y, "evenodd");
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        if (hit) return f.name;
      }
      return null;
    }
    const zoomAt = (factor, x, y) => {
      const lon = cx + (x - W / 2) / k, m = cm - (y - H / 2) / k;
      k = Math.max(8, Math.min(2600, k * factor));
      cx = lon - (x - W / 2) / k; cm = m + (y - H / 2) / k;
      invalidate();
    };
    const ptrs = new Map();
    let moved = 0, pinch = 0;
    const local = (e) => { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
    cv.addEventListener("pointerdown", (e) => { if (!interactive) return; cv.setPointerCapture(e.pointerId); ptrs.set(e.pointerId, local(e)); moved = 0; pinch = 0; opts.onUser && opts.onUser(); });
    cv.addEventListener("pointermove", (e) => {
      const [x, y] = local(e);
      if (!ptrs.has(e.pointerId)) {
        if (opts.onHover) { const i = nearest(x, y); cv.style.cursor = i != null ? "pointer" : ""; opts.onHover(i, e); }
        return;
      }
      const prev = ptrs.get(e.pointerId);
      ptrs.set(e.pointerId, [x, y]);
      if (ptrs.size === 1) { cx -= (x - prev[0]) / k; cm += (y - prev[1]) / k; moved += Math.abs(x - prev[0]) + Math.abs(y - prev[1]); invalidate(); }
      else if (ptrs.size === 2) {
        const [a, b] = [...ptrs.values()], d = Math.hypot(a[0] - b[0], a[1] - b[1]);
        if (pinch) zoomAt(d / pinch, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2);
        pinch = d; moved = 99;
      }
    });
    const up = (e) => {
      if (!ptrs.has(e.pointerId)) return;
      const [x, y] = local(e);
      ptrs.delete(e.pointerId);
      if (moved < 5 && !(opts.drawing && opts.drawing())) {
        const i = nearest(x, y);
        if (i != null) opts.onPick && opts.onPick(i);
        else { const a = areaAt(x * dpr, y * dpr); if (a && opts.onArea) opts.onArea(a); }
      }
    };
    cv.addEventListener("pointerup", up);
    cv.addEventListener("pointercancel", (e) => ptrs.delete(e.pointerId));
    cv.addEventListener("pointerleave", () => opts.onHover && opts.onHover(null));
    cv.addEventListener("wheel", (e) => { if (!interactive) return; e.preventDefault(); const [x, y] = local(e); zoomAt(Math.exp(-e.deltaY * 0.0016), x, y); opts.onUser && opts.onUser(); }, { passive: false });
    cv.addEventListener("keydown", (e) => {
      const step = 60 / k;
      if (e.key === "ArrowLeft") cx -= step; else if (e.key === "ArrowRight") cx += step; else if (e.key === "ArrowUp") cm += step; else if (e.key === "ArrowDown") cm -= step;
      else if (e.key === "+" || e.key === "=") return void zoomAt(1.3, W / 2, H / 2); else if (e.key === "-" || e.key === "_") return void zoomAt(1 / 1.3, W / 2, H / 2);
      else return;
      e.preventDefault(); invalidate();
    });
    build();
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(resize) : null;
    if (ro) ro.observe(container);
    resize();
    return {
      kind: "canvas", exaggeration: 0,
      setTheme(colors2) { c = colors2; invalidate(); },
      setSelection(s) { sel = { region: s.bbox ? "" : s.region, bbox: s.bbox || null }; invalidate(); },
      setPoints(p) { P = p; picked = null; invalidate(); },
      setFilter(f) { F = f; invalidate(); },
      select(i) { picked = i; invalidate(); },
      fit(b) {
        if (W < 2) resize();
        const padX = 40, padTop = opts.padTop == null ? 70 : opts.padTop, padBottom = 28;
        k = Math.max(8, Math.min(2600, Math.min((W - padX * 2) / Math.max(0.01, b[2] - b[0]), (H - padTop - padBottom) / Math.max(0.01, mercY(b[3]) - mercY(b[1])))));
        cx = (b[0] + b[2]) / 2; cm = (mercY(b[1]) + mercY(b[3])) / 2 + (padTop - padBottom) / 2 / k;
        invalidate();
      },
      flyTo(lon, lat) { cx = lon; cm = mercY(lat); k = Math.max(k, 260); invalidate(); },
      camera(act) { if (act === "zoom-in") zoomAt(1.5, W / 2, H / 2); else if (act === "zoom-out") zoomAt(1 / 1.5, W / 2, H / 2); },
      setMode() {}, mode: () => "2d",
      setViewMode(vm) { vmode = vm || "points"; invalidate(); }, viewMode: () => vmode,
      viewMeta: () => {
        if (!P) return { total: 0, shown: 0, limited: false };
        let n = 0;
        for (let i = 0; i < P.lon.length; i++) if (shown(i)) n++;
        return { total: n, shown: n, limited: false };
      },
      setPsf(on) { psfOn = !!on; invalidate(); }, setOrbit() {}, setSeam() {}, setPlayback() {},
      satBadges: () => [], flyPose() {},
      whenIdle(cb) { draw(); cb && cb(); },
      view: () => ({ cx, cm, k }), setView(v) { cx = v.cx; cm = v.cm; k = v.k; invalidate(); },
      project: (lon, lat) => [px(lon), py(lat)],
      unproject: (x, y) => [cx + (x - W / 2) / k, unmercY(cm - (y - H / 2) / k)],
      setInteractive(on) { interactive = on; },
      setOverlay(url, wsen, opacity) { if (!url) { overlay = null; invalidate(); return; } const img = new Image(); img.onload = invalidate; img.src = url; overlay = { img, wsen, opacity: opacity == null ? 0.8 : opacity }; },
      resize, png: () => { draw(); return cv; }, bearing: () => 0, focus() { cv.focus(); },
      destroy() { dead = true; if (ro) ro.disconnect(); cv.remove(); },
    };
  }
  window.SeamMap2D = { create: createCanvas, colors, mercY };

  // ---------------------------------------------------------------------------------------------------------
  // Controller
  // ---------------------------------------------------------------------------------------------------------
  const UI = S.UI;
  let host = null, engine = null, POINTS = null, PKEY = "", PREQ = 0, PCTRL = null, PERR = "", picked = null, play = null, drawing = false, started = false;
  let lowPower = false, glProblem = "", listShown = 100, printBackup = null, COUNTS = null, pointsPending = false;
  let rowBuckets = null, matchedKey = "", matchedRows = [], frpKey = "", frpValue = null;
  let pointsRequestKey = "", pointsTask = null, preloadedPoints = null, scrubFrame = 0, scrubArtKey = "", scrubWidth = 0, fitKey = "";
  let listTimer = 0, legendMarkup = "";
  let mapLibraryPending = false, mapLibraryFailed = false, webglLost = false;
  const mapWorkspace = () => UI.ws === "overview" || UI.ws === "explore";
  let vmode = "points", orbitOn = false, psfOn = false, satPicked = null;
  const satPinNodes = new Map();
  try { lowPower = localStorage.getItem("seamline-lowpower") === "1"; } catch (_) { /* storage blocked */ }
  const ic = (id) => `<svg class="ic"><use href="#i-${id}"/></svg>`;
  const tool = (act, icon, label) => `<button type="button" class="icon-btn" data-cam="${act}" aria-label="${label}" title="${label}">${ic(icon)}</button>`;

  function buildHost() {
    host = document.createElement("div");
    host.className = "map"; host.id = "map-host";
    host.innerHTML = `<div class="map-view" id="map-view"></div><div class="map-draft" id="map-draft" hidden></div><div class="sat-pins" id="sat-pins" hidden></div>
      <div class="map-top-wrap">
        <div class="map-top">
          <div class="seg" role="group" aria-label="Map view">
            <button type="button" data-mode="globe" id="mode-globe">Globe</button>
            <button type="button" data-mode="3d" id="mode-3d">3D</button>
            <button type="button" data-mode="2d" id="mode-2d">2D</button>
          </div>
          <div class="map-title" id="map-title" aria-live="polite"></div>
        </div>
        <div class="map-subbar" role="toolbar" aria-label="Layer and orbit overlays">
          <div class="seg" role="group" aria-label="Detection representation">
            <button type="button" data-vmode="points" aria-pressed="true" title="Fixed point per detection (never scaled)">Pixels</button>
            <button type="button" data-vmode="towers" aria-pressed="false" title="3D FRP radiant power towers seated on relief">FRP 3D</button>
            <button type="button" data-vmode="footprints" aria-pressed="false" title="Oriented along-scan x along-track sensor footprints">scan×track</button>
            <button type="button" data-vmode="density" aria-pressed="false" title="Macro detection concentration (fades to pixels on zoom)">Density</button>
          </div>
          <button type="button" class="map-chip-btn" id="orbit-btn" aria-pressed="false" title="Toggle illustrative sun-synchronous orbital tracks and scan swaths">${ic("orbit")}<span>Orbits</span></button>
          <button type="button" class="map-chip-btn" id="psf-btn" aria-pressed="false" hidden title="Toggle MODIS 2x1 km triangular PSF kernel halo (25/50/25%)">${ic("psf")}<span>PSF 2×1</span></button>
          <span class="map-render-pill" id="map-render-pill" hidden role="status" aria-live="polite"></span>
        </div>
      </div>
      <div class="map-banner" id="map-banner" role="status"></div>
      <div class="map-tools" role="toolbar" aria-label="Map camera" aria-orientation="vertical">
        ${tool("zoom-in", "plus", "Zoom in")}${tool("zoom-out", "minus", "Zoom out")}<span class="sep"></span>
        <button type="button" class="icon-btn" data-cam="north" id="north-btn" aria-label="Reset north (north up)" title="Reset north">${ic("north")}</button>
        ${tool("rot-l", "rotl", "Rotate left")}${tool("rot-r", "rotr", "Rotate right")}${tool("tilt-up", "up", "Tilt the view more")}${tool("tilt-dn", "dn", "Tilt the view less")}<span class="sep"></span>
        ${tool("fit", "fit", "Fit the selected area")}${tool("reset", "reset", "Reset the camera")}</div>
      <div class="map-legend" id="map-legend"></div>
      <div class="map-card" id="map-card" hidden></div>
      <div class="map-card sat-card" id="sat-card" hidden></div>
      <div class="map-msg" id="map-msg" role="status" aria-live="polite"></div>
      <div class="map-scrub" id="map-scrub">
        <button type="button" class="icon-btn" id="play-btn" aria-pressed="false" aria-label="Play this month day by day (historical playback of past observations)" title="Play this month day by day (past observations)">${ic("play")}</button>
        <div class="scrub-track"><canvas id="scrub-canvas"></canvas><span id="scrub-selection" aria-hidden="true"></span><input type="range" id="scrub" min="0" max="30" step="1" value="0" aria-label="Day shown on the map; 0 shows the whole month"><span class="scrub-focus"></span></div>
        <div class="scrub-date" id="scrub-date"></div></div>`;
  }
  function mount() {
    const stage = $(UI.ws === "explore" ? "stage-explore" : "stage-overview");
    if (engine?.setActive) engine.setActive(mapWorkspace() && !document.hidden);
    if (!mapWorkspace()) return;
    if (host.parentElement !== stage) stage.appendChild(host);
    enableMapLibrary();
    requestAnimationFrame(() => {
      if (engine) engine.resize();
      if (engine && !window.SeamIntro?.ownsCamera() && $("map-view").clientWidth > 50) fitSelection(false);
      drawScrub();
    });
  }
  const selection = () => { const r = S.result(); return r ? { region: r.region, bbox: r.request.bbox ? r.request.bbox.map(Number) : null } : null; };
  function selBounds() {
    const s = selection() || (S.meta() ? S.selectedRequest() : null), A = S.areas();
    if (!s || !A) return [60.8, 23.6, 77.9, 37.1];
    return s.bbox?.map(Number) || (A.areas[s.region] || A.areas.Pakistan).bounds;
  }

  // A fit made while the map has no size (its workspace is hidden) is wrong, so it is made again the first time the
  // map is on screen.
  let fittedVisible = false;
  function fitNow(animate) {
    if (!engine) return;
    const visible = $("map-view").clientWidth > 50;
    engine.fit(selBounds(), animate && visible);
    fittedVisible = visible;
  }
  function fitSelection(animate) {
    const key = selBounds().join(",");
    if (fittedVisible && key === fitKey) return;
    fitNow(animate);
    fitKey = key;
  }
  function fitAfterIntro(regional = false) {
    if (regional) {
      UI.mode = "3d";
      setOrbit(true);
      S.emit("map-mode", UI.mode);
      S.syncUrl();
    }
    fitNow(false);
    fitKey = selBounds().join(",");
  }
  function renderSatPins(badges) {
    const wrap = host && $("sat-pins");
    if (!wrap) return;
    const gl = engine && engine.kind === "gl";
    const show = !!(gl && badges && badges.length && (orbitOn || UI.story === "seam") && (UI.ws === "overview" || UI.ws === "explore"));
    if (!show) {
      if (!wrap.hidden) {
        wrap.hidden = true;
        for (const el of satPinNodes.values()) {
          if (!el.hidden) el.hidden = true;
          if (el._st) el._st.vis = false;
        }
      }
      return;
    }
    if (wrap.hidden) wrap.hidden = false;
    const viewEl = $("map-view") || wrap;
    const W = Math.max(240, viewEl.clientWidth || 640);
    const H = Math.max(220, viewEl.clientHeight || 420);
    const PIN_W = 116, PIN_H = 24;
    const minX = 8, maxX = Math.max(minX, W - PIN_W - 44);
    const minY = 88, maxY = Math.max(minY, H - 76);
    const placed = [];
    const ordered = badges.slice().sort((a, b) => (Number(!!b.selected) - Number(!!a.selected)) || ((a.sy || 0) - (b.sy || 0)));
    const placedCoords = new Map();
    for (const b of ordered) {
      if (!b.visible) continue;
      const rawX = Math.round(b.sx) + 8;
      const rawY = Math.round(b.sy);
      const baseX = Math.max(minX, Math.min(maxX, rawX));
      const baseY = Math.max(minY, Math.min(maxY, rawY));
      const leftX = Math.max(minX, Math.min(maxX, Math.round(b.sx) - PIN_W - 8));
      const candidates = [
        [baseX, baseY],
        [baseX, Math.max(minY, Math.min(maxY, baseY + 26))],
        [baseX, Math.max(minY, Math.min(maxY, baseY - 26))],
        [leftX, baseY],
        [baseX, Math.max(minY, Math.min(maxY, baseY + 52))],
        [baseX, Math.max(minY, Math.min(maxY, baseY - 52))],
        [leftX, Math.max(minY, Math.min(maxY, baseY + 26))],
        [leftX, Math.max(minY, Math.min(maxY, baseY - 26))],
      ];
      let chosen = candidates[0];
      for (const [cx, cy] of candidates) {
        const collides = placed.some((p) => Math.abs(cx - p.x) < PIN_W && Math.abs(cy - p.y) < PIN_H);
        if (!collides) { chosen = [cx, cy]; break; }
      }
      placed.push({ x: chosen[0], y: chosen[1] });
      placedCoords.set(b.key, chosen);
    }
    const alive = new Set();
    for (const b of badges) {
      alive.add(b.key);
      let el = satPinNodes.get(b.key);
      if (!el) {
        el = document.createElement("button");
        el.type = "button";
        el.className = "sat-pin";
        el.dataset.satPin = b.key;
        const info = SAT_INFO[b.key] || { cls: "snpp", short: b.short };
        el.innerHTML = `<span class="dot ${info.cls}"></span><span class="name">${esc(b.short)}</span><span class="tag"></span>`;
        el._tag = el.querySelector(".tag");
        el._st = { sx: -9999, sy: -9999, vis: null, dim: null, ended: null, tag: "" };
        satPinNodes.set(b.key, el);
        wrap.appendChild(el);
      }
      const st = el._st;
      const isDim = !b.selected, isEnded = !!b.ended;
      if (st.dim !== isDim) { el.classList.toggle("is-dim", isDim); st.dim = isDim; }
      if (st.ended !== isEnded) { el.classList.toggle("is-ended", isEnded); st.ended = isEnded; }
      const tagText = isEnded ? "ended" : b.handedOver ? "bridge" : `${b.swathKm} km`;
      if (st.tag !== tagText) { el._tag.textContent = tagText; st.tag = tagText; }
      if (!b.visible) {
        if (st.vis !== false) { el.hidden = true; st.vis = false; }
      } else {
        const [px, py] = placedCoords.get(b.key) || [Math.round(b.sx) + 8, Math.round(b.sy)];
        if (st.vis !== true) { el.hidden = false; st.vis = true; }
        if (st.sx !== px || st.sy !== py) {
          st.sx = px; st.sy = py;
          el.style.transform = `translate3d(${px}px, ${py}px, 0) translateY(-50%)`;
        }
      }
    }
    for (const [k, el] of satPinNodes.entries()) {
      if (!alive.has(k) && !el.hidden) {
        el.hidden = true;
        if (el._st) el._st.vis = false;
      }
    }
  }

  function showSatCard(key) {
    const badges = engine && engine.satBadges ? engine.satBadges() : [];
    const b = badges.find((x) => x.key === key);
    const card = $("sat-card");
    if (!b || !card) { if (card) card.hidden = true; return; }
    satPicked = key;
    inspect(null);
    const info = SAT_INFO[key] || { cls: "snpp", label: b.label, round: true };
    const status = b.ended ? "Ended 2 Nov 2026 (15:40 UTC); shown dimmed"
      : b.handedOver ? "Carries Punjab Nov 2026 continuity bridge (P04 G03)"
      : b.selected ? "Included in map filter" : "Constellation context (not selected in map filter)";
    card.innerHTML = `<button type="button" class="icon-btn card-x" data-sat-close aria-label="Close telemetry details">${ic("close")}</button>
      <h4><span class="mk ${info.cls}${info.round ? " round" : " ring"}"></span>${esc(b.label)}</h4>
      <dl>
        <dt>Model</dt><dd>${b.model ? "Supplied spacecraft model" : "Schematic spacecraft (no matching model supplied)"}</dd><dt>Orbit</dt><dd>${b.kind === "MODIS" ? "98.2° sun-synchronous · 705 km" : "98.7° sun-synchronous · 824–834 km"}</dd>
        <dt>Overpass</dt><dd>${esc(b.lst)}</dd>
        <dt>Swath</dt><dd>${fmt(b.swathKm)} km${b.kind === "MODIS" ? " (~9.7 km² off-nadir bowtie)" : " (3:1→2:1→1:1 aggregation)"}</dd>
        <dt>Status</dt><dd>${esc(status)}</dd>
      </dl>
      <p class="note">${esc(b.note)} Orbits and swaths are schematic visualizations; they never alter detection counts.</p>`;
    card.hidden = false;
  }

  function makeEngine() {
    if (engine) { engine.destroy(); engine = null; }
    fittedVisible = false;
    $("map-view").innerHTML = "";
    satPinNodes.clear();
    if ($("sat-pins")) $("sat-pins").innerHTML = "";
    const tryGl = mapWorkspace() && !lowPower && !webglLost && !!window.maplibregl;
    glProblem = webglLost ? "The 3D view lost its graphics context." : tryGl ? window.SeamGL.available() : "";
    const A = S.areas();
    const opts = {
      colors: colors(), geo: S.geo(), areas: A ? A.areas : {}, cities: CITIES, mode: UI.mode, vmode,
      openingBounds: window.SeamIntro?.coldScene() ? selBounds() : null,
      motion: S.motionMode, drawing: () => drawing,
      onPick: pick, onArea: (name) => { const s = selection(); if (!drawing && s && (s.bbox || s.region !== name)) S.selectArea(name); },
      onHover: hover, onUser: () => stopPlay("You moved the map"), onBearing: (b) => { $("north-btn").firstElementChild.style.transform = `rotate(${-b}deg)`; },
      onSatTick: renderSatPins,
      matchingRows,
      onPolyMeta: () => { updateRenderPill(); legend(); S.emit("map-geometry"); },
      onLost: () => { glProblem = "The 3D view lost its graphics context."; lowPower = false; fallback(); },
      onReady: () => { if (mapWorkspace() && !window.SeamIntro?.ownsCamera()) fitSelection(false); },
    };
    let usingGl = false;
    if (tryGl && !glProblem) {
      try { engine = window.SeamGL.create($("map-view"), opts); usingGl = true; } catch (e) { glProblem = `The 3D view could not start (${e.message}).`; $("map-view").innerHTML = ""; }
    }
    if (!usingGl) {
      engine = createCanvas($("map-view"), opts);
      if (vmode === "towers") vmode = "points";
    }
    host.classList.toggle("is-canvas", !usingGl);
    $("map-banner").textContent = usingGl ? "" : lowPower ? "Low-power map: a flat top-down view. Areas, filters, dates, counts and inspection are the same as in 3D."
      : glProblem || mapLibraryFailed ? `${glProblem || "The map library did not load."} The map is drawn as a flat top-down view instead; areas, filters, dates, counts and inspection are the same.`
      : "Preparing terrain and 3D view…";
    syncMode();
    const s = selection();
    if (s) { engine.setSelection(s); if (mapWorkspace() && !window.SeamIntro?.ownsCamera()) fitSelection(false); }
    engine.setViewMode(vmode);
    engine.setPsf(psfOn);
    engine.setOrbit(orbitOn);
    engine.setSeam(UI.story === "seam");
    if (POINTS) { engine.setPoints(POINTS); applyFilter(); engine.select(picked); }
    if (window.SeamCoverage) window.SeamCoverage.redraw();
    S.emit("map-engine");
  }
  function fallback() {
    webglLost = true;
    makeEngine();
  }
  function enableMapLibrary() {
    if (engine?.kind === "gl" || lowPower || webglLost || mapLibraryPending || mapLibraryFailed || glProblem) return;
    mapLibraryPending = true;
    window.loadSeamMapLibrary().then(available => {
      mapLibraryPending = false;
      mapLibraryFailed = !available;
      if (mapWorkspace() && !lowPower) makeEngine();
    });
  }
  function syncMode() {
    const gl = engine && engine.kind === "gl";
    for (const b of host.querySelectorAll("[data-mode]")) {
      const m = b.dataset.mode;
      b.setAttribute("aria-pressed", String(gl ? m === UI.mode : m === "2d"));
      if (m === "3d" || m === "globe") {
        b.setAttribute("aria-disabled", String(!gl));
        b.title = gl ? "" : "WebGL is not available in this view; the 2D map has the same data";
      }
    }
    for (const b of host.querySelectorAll("[data-vmode]")) {
      const vm = b.dataset.vmode;
      b.setAttribute("aria-pressed", String(vm === vmode));
      if (vm === "towers") {
        b.setAttribute("aria-disabled", String(!gl));
        b.title = gl ? "3D FRP radiant power towers seated on relief" : "Requires WebGL 3D view";
      }
    }
    const ob = $("orbit-btn"), pb = $("psf-btn");
    if (ob) { ob.hidden = !gl; ob.setAttribute("aria-pressed", String(gl && orbitOn)); }
    if (pb) { pb.hidden = vmode !== "footprints"; pb.setAttribute("aria-pressed", String(psfOn)); }
    $("map-view").classList.toggle("is-globe", gl && UI.mode === "globe");
    const rotatable = gl && UI.mode !== "2d";
    for (const b of host.querySelectorAll('[data-cam="rot-l"],[data-cam="rot-r"],[data-cam="tilt-up"],[data-cam="tilt-dn"],[data-cam="north"]')) b.hidden = !rotatable;
    if (!orbitOn && UI.story !== "seam" && $("sat-pins")) $("sat-pins").hidden = true;
    updateRenderPill();
    legend();
  }
  function updateRenderPill() {
    const pill = $("map-render-pill");
    if (!pill) return;
    if (vmode !== "towers" && vmode !== "footprints") {
      pill.hidden = true;
      pill.textContent = "";
      pill.classList.remove("is-sampled");
      return;
    }
    const vmMeta = engine && engine.viewMeta ? engine.viewMeta() : { total: 0, shown: 0, limited: false };
    pill.hidden = false;
    pill.classList.toggle("is-sampled", !!vmMeta.limited);
    pill.textContent = vmMeta.pending ? "Updating 3D geometry…" : `Rendered ${fmt(vmMeta.shown)} of ${fmt(vmMeta.total)}`;
    if (vmMeta.pending) { pill.title = "The previous geometry is visible while the selected view loads."; return; }
    pill.title = vmMeta.limited
      ? `3D geometry is capped at ${fmt(vmMeta.shown)} detections (top FRP + uniform spatial sample) out of ${fmt(vmMeta.total)} matching detections. Full counts and exports remain exact.`
      : `All ${fmt(vmMeta.total)} matching detections are rendered as 3D geometry.`;
  }

  // ---------- data ----------
  function pointRequest(request, month, identity) {
    const r = S.result();
    const p = request || r?.request;
    if (!p) return null;
    const body = { region: p.region, day_month: month || S.dayMonth() };
    if (p.bbox) body.bbox = p.bbox;
    identity ||= r?.data_identity || S.meta()?.data_identity;
    if (identity) body.data_identity = identity;
    return body;
  }
  function fetchPoints(body, signal) {
    return S.post("/api/points", body, signal).then(r => r.json());
  }
  function preloadPoints(request) {
    if (!mapWorkspace()) return;
    const body = pointRequest(request, S.initialMapMonth(request));
    const key = JSON.stringify(body);
    if (preloadedPoints?.key === key) return;
    preloadedPoints?.controller.abort();
    const controller = new AbortController();
    // Keep a failed preload retryable through the ordinary map request.
    const response = fetchPoints(body, controller.signal).catch(() => null);
    preloadedPoints = { key, controller, response };
  }
  S.on("initial-selection", preloadPoints);
  S.on("analysis-error", () => { preloadedPoints?.controller.abort(); preloadedPoints = null; });
  function loadPoints() {
    if (!mapWorkspace() || !engine) return;
    const body = pointRequest();
    if (!body) return;
    const [y, m] = body.day_month;
    const key = JSON.stringify(body);
    if (key === pointsRequestKey && pointsPending) return pointsTask;
    if (key === PKEY && POINTS && !PERR && !pointsPending) { applyFilter(); return; }
    engine.setDate?.(`${y}-${String(m).padStart(2, "0")}`);
    if ($("sat-card")) $("sat-card").hidden = true;
    satPicked = null;
    const id = ++PREQ;       // only the newest reply is drawn
    if (PCTRL) PCTRL.abort();
    PCTRL = new AbortController();
    const { signal } = PCTRL;
    const preload = preloadedPoints;
    preloadedPoints = null;
    if (preload?.key === key) signal.addEventListener("abort", () => preload.controller.abort(), { once: true });
    else preload?.controller.abort();
    pointsRequestKey = key;
    pointsPending = true;
    stopPlay();
    host.classList.add("is-stale");
    PERR = "";
    $("map-msg").textContent = `Loading the detections for ${MONTH_FULL[m - 1]} ${y}…`;
    title(true);
    S.emit("map-filter");
    pointsTask = applyPointResponse(body, key, preload, id, signal);
    return pointsTask;
  }
  async function applyPointResponse(body, key, preload, id, signal) {
    try {
      const prefetched = preload?.key === key ? await preload.response : null;
      if (id !== PREQ || signal.aborted) return;
      const res = prefetched || await fetchPoints(body, signal);
      if (id !== PREQ) return;
      if (body.data_identity && res.data_identity && body.data_identity !== res.data_identity) {
        throw new Error("The cached inputs changed after this result loaded. Reload the selection before exporting its map.");
      }
      res.day = res.minute.map((v) => Math.floor(v / 1440) + 1);
      POINTS = res; PKEY = key; picked = null; listShown = 100;
      if (UI.mapDay > res.days_in_month) UI.mapDay = 0;
      count();
      engine.setPoints(POINTS); engine.select(null);
      $("map-msg").textContent = "";
      host.classList.remove("is-stale");
      $("scrub").max = String(res.days_in_month);
      pointsPending = false;
      applyFilter();
      inspect(null);
      S.emit("points-loaded");
    } catch (e) {
      if (id !== PREQ || e.name === "AbortError") return;
      PERR = e.message;
      pointsPending = false;
      host.classList.remove("is-stale");
      POINTS = null; PKEY = ""; COUNTS = null;
      rowBuckets = null; matchedKey = ""; frpKey = ""; scrubArtKey = "";
      engine.setPoints(null);
      $("map-msg").innerHTML = `The detections could not be loaded. ${esc(e.message)} <button type="button" class="btn" id="map-retry">Try again</button>`;
      title(); legend(); drawScrub(); platList(); pointList();
      S.emit("map-filter");
    }
  }
  // Per-satellite, per-pass, per-day counts of the month, straight from the rows on the map.
  function count() {
    const n = POINTS.days_in_month;
    COUNTS = SATS.map(() => [new Int32Array(n + 1), new Int32Array(n + 1)]);
    rowBuckets = SATS.map(() => [0, 1].map(() => Array.from({ length: n + 1 }, () => [])));
    matchedKey = ""; frpKey = ""; scrubArtKey = "";
    for (let i = 0; i < POINTS.lon.length; i++) {
      const p = POINTS.p[i], pass = POINTS.dn[i], day = POINTS.day[i];
      COUNTS[p][pass][day]++;
      COUNTS[p][pass][0]++;
      rowBuckets[p][pass][day].push(i);
      rowBuckets[p][pass][0].push(i);
    }
    SATS.forEach((s, p) => {   // the server's own counts must agree with the rows it sent
      const d = COUNTS[p][0][0], nn = COUNTS[p][1][0];
      if (d !== POINTS.counts[s].D || nn !== POINTS.counts[s].N) console.error("Seamline: map counts differ from the server's", s, d, nn, POINTS.counts[s]);
    });
  }
  function shownCount(p, day) {
    if (!COUNTS) return null;
    const one = (dn) => COUNTS[p][dn][day];
    return UI.dn === "DN" ? one(0) + one(1) : one(UI.dn === "N" ? 1 : 0);
  }
  const currentFilter = () => ({ sats: UI.sats.map(s => SATS.indexOf(s)), dn: UI.dn, day: UI.mapDay });
  const filterKey = f => `${f.sats.join(",")}|${f.dn}|${f.day}`;
  const exactCount = () => COUNTS && !pointsPending ? UI.sats.reduce((n, s) => n + shownCount(SATS.indexOf(s), UI.mapDay), 0) : null;
  const pointStatus = () => PERR ? "error" : pointsPending || !POINTS ? "loading" : "ready";
  function mergeIds(a, b) {
    if (!a.length) return b;
    if (!b.length) return a;
    const out = new Array(a.length + b.length);
    let i = 0, j = 0, next = 0;
    while (i < a.length && j < b.length) out[next++] = a[i] < b[j] ? a[i++] : b[j++];
    while (i < a.length) out[next++] = a[i++];
    while (j < b.length) out[next++] = b[j++];
    return out;
  }
  function matchingRows(f, firstDay = f.day) {
    if (!rowBuckets) return [];
    const key = `${filterKey(f)}|${firstDay}`;
    if (key === matchedKey) return matchedRows;
    const passes = f.dn === "DN" ? [0, 1] : [f.dn === "N" ? 1 : 0];
    const groups = f.sats.flatMap(p => passes.flatMap(pass => rowBuckets[p][pass].slice(firstDay, f.day + 1)));
    // Row IDs are the stable UTC order of the server response.
    matchedRows = groups.reduce(mergeIds, []);
    matchedKey = key;
    return matchedRows;
  }
  function isInitialViewReady() {
    return !pointsPending && !!(POINTS || PERR);
  }
  const inRecord = (sat) => !POINTS || !POINTS.record || !["outside_record", "unavailable"].includes(POINTS.record[sat].status);
  const recordNote = (sat) => {
    const r = POINTS && POINTS.record && POINTS.record[sat];
    return r && r.note ? r.note : `${SAT_INFO[sat].label} has no record in this month${r && r.first ? ` (the record begins ${r.first})` : ""}. Missing data, not zero.`;
  };

  // ---------- filters, legend, title ----------
  function applyFilter(scrubbing = false) {
    if (!engine) return;
    engine.setFilter(currentFilter());
    $("scrub").value = String(UI.mapDay);
    updateRenderPill();
    title(); legend(); platList(); drawScrub();
    clearTimeout(listTimer);
    if (scrubbing && $("point-list-wrap")?.open) listTimer = setTimeout(pointList, 120);
    else pointList();
    for (const b of $("map-dn").querySelectorAll("button")) b.setAttribute("aria-pressed", String(b.dataset.dn === UI.dn));
    const empty = POINTS && UI.sats.every((s) => !shownCount(SATS.indexOf(s), UI.mapDay));
    if (POINTS && !PERR) {
      const out = UI.sats.filter((s) => !inRecord(s));
      $("map-msg").innerHTML = !UI.sats.length ? "No satellite is selected. Choose one in the filters."
        : out.length === UI.sats.length ? out.map((s) => esc(recordNote(s))).join(" ") +
          (inRecord("Aqua") ? ` <button type="button" class="btn" id="map-use-aqua">Show Aqua MODIS instead</button>` : "")
        : empty ? `No detections from ${UI.sats.map((s) => SAT_INFO[s].short).join(", ")} here ${UI.mapDay ? "on this day" : "in this month"}. No detection is not no burning.` : "";
    }
    S.emit("map-filter");
  }
  const EOSDIS_SPEC = {
    Terra: "MCD14ML C6.1 (1 km · ~4–40 MW floor)",
    Aqua: "MCD14ML C6.1 (1 km · ~4–40 MW floor)",
    SNPP: "VNP14IMG C2 (375 m I-band vs VNP14 750 m · ~0.5 MW)",
    NOAA20: "VJ114IMG C2 (375 m I-band · ~0.5 MW)",
    NOAA21: "VJ214IMGTDL_NRT C2 (375 m I-band · ~0.5 MW)",
  };
  function frpSummary() {
    if (!POINTS || !POINTS.frp || !UI.sats.length) return null;
    const filter = currentFilter(), key = filterKey(filter);
    if (key === frpKey) return frpValue;
    const vals = [];
    let sumMw = 0;
    for (const i of matchingRows(filter)) {
      const v = POINTS.frp[i];
      if (v != null && v > 0) { vals.push(v); sumMw += v; }
    }
    frpKey = key;
    vals.sort((a, b) => a - b);
    const medMw = vals[Math.floor(vals.length * 0.5)] ?? 0;
    const p90Mw = vals[Math.floor(vals.length * 0.9)] ?? 0;
    frpValue = {
      count: vals.length,
      sumMw,
      medMw,
      p90Mw,
      label: `${UI.sats.map((k) => SAT_INFO[k].short).join("+")} · ${when()}`,
    };
    return frpValue;
  }
  function when() {
    const [y, m] = POINTS ? POINTS.month.split("-").map(Number) : S.dayMonth();
    return UI.mapDay ? `${UI.mapDay} ${MONTH_FULL[m - 1]} ${y}` : `${MONTH_FULL[m - 1]} ${y}`;
  }
  function title(loading) {
    const s = selection();
    const sats = UI.sats.map((k) => SAT_INFO[k].short).join(" · ") || "No satellite";
    const prodCodes = UI.sats.map((k) => (POINTS && POINTS.products && POINTS.products[k]) || (k === "SNPP" ? "VNP14IMG" : k === "NOAA20" ? "VJ114IMG" : k === "NOAA21" ? "VJ214IMG" : "MCD14ML")).join("/");
    $("map-title").innerHTML = `<b>${esc(sats)}</b> (<code>${esc(prodCodes)}</code>) · ${esc(s ? s.region : "")} · ${esc(when())}${loading ? " · loading…" : ""}` +
      `<span class="note">Each satellite separately; ${UI.dn === "DN" ? "day and night passes" : UI.dn === "D" ? "day passes" : "night passes"}; UTC dates</span>`;
    const fs = $("filter-sum");
    if (fs) fs.textContent = `Showing: ${sats}; ${UI.dn === "DN" ? "day and night passes" : UI.dn === "D" ? "day passes only" : "night passes only"}; ${UI.mapDay ? when() : "the whole month"}.`;
  }
  function legend() {
    if (!host) return;
    const rows = UI.sats.map((k) => {
      const p = SATS.indexOf(k), n = shownCount(p, UI.mapDay), info = SAT_INFO[k];
      const val = !inRecord(k) ? (POINTS.record[k].status === "unavailable" ? "no usable data" : "no record") : n == null ? "…" : fmt(n);
      return `<div class="lg-row"><span class="mk ${info.cls}${info.round ? " round" : " ring"}"></span>${esc(info.label)}<b>${val}</b></div>`;
    }).join("");
    const frp = frpSummary();
    const specLine = UI.sats.map((k) => EOSDIS_SPEC[k] || k).join(" · ");
    const telemHtml = POINTS && UI.sats.length
      ? `<div class="lg-telem"><div><b>EOSDIS:</b> <code>${esc(specLine)}</code></div>` +
        (frp && frp.count > 0 ? `<div><b>FRP:</b> Σ ${fmt(frp.sumMw, 0)} MW · med ${fmt(frp.medMw, 1)} MW · p90 ${fmt(frp.p90Mw, 1)} MW</div>` : "") +
        `</div>`
      : "";
    const gl = engine && engine.kind === "gl";
    const surface = gl && UI.mode === "globe"
      ? "3D globe projection with South Asia rivers and NOAA elevation."
      : gl && UI.mode === "3d"
        ? `Surface: NOAA elevation, heights stretched ×${engine.exaggeration}.`
        : gl ? "Flat top-down view; shading from NOAA elevation." : "Flat top-down view.";
    const vmMeta = engine && engine.viewMeta ? engine.viewMeta() : { total: 0, shown: 0, limited: false };
    const c = colors();
    let extra = "";
    if (vmMeta.pending && (vmode === "towers" || vmode === "footprints")) {
      extra = "Updating 3D geometry for the selected detections…";
    } else if (vmode === "towers") {
      extra = `<b>Rendered ${fmt(vmMeta.shown)} of ${fmt(vmMeta.total)}</b>${vmMeta.limited ? " (sampled: top FRP + uniform grid)" : ""}. Tower height ∝ √FRP (MW, capped ~54 km); shows radiative power per detection, never burned area.`;
    } else if (vmode === "footprints") {
      extra = `<b>Rendered ${fmt(vmMeta.shown)} of ${fmt(vmMeta.total)}</b>${vmMeta.limited ? " (sampled: top FRP + uniform grid)" : ""}. Oriented scan × track ground footprints (MODIS bowtie off-nadir vs 3:1→1:1 VIIRS).${psfOn ? " Faint outer box: MODIS 2×1 km PSF kernel (25/50/25%)." : ""}`;
    } else if (vmode === "density") {
      const rampBg = `linear-gradient(90deg, ${c.heat1}, ${c.heat2}, ${c.heat3}, ${c.heat4})`;
      extra = `<div class="lg-ramp-row"><span class="lg-ramp-lbl">Low</span><div class="lg-ramp" style="background:${rampBg}"></div><span class="lg-ramp-lbl">High</span></div><span>Macro density weighted by FRP (fades to raw detections on zoom). Cross-sensor aid only; detections are never added across sensors.</span>`;
    }
    if (orbitOn || UI.story === "seam") {
      extra += (extra ? "<br>" : "") + (UI.story === "seam"
        ? "Illustrative orbits: S-NPP data delivery ended 2 Nov 2026; bridge eligibility is defined by the selected data, not by these orbits."
        : "Illustrative orbits & swaths (launch-date filtered, 20× altitude scale, enlarged spacecraft). Not live tracking or measured coverage. Click a satellite for details.");
    }
    const open = $("lg-more") && $("lg-more").open;
    const markup = (rows || `<div class="lg-row">No satellite selected</div>`) +
      telemHtml +
      `<div class="lg-note">Detections ${UI.mapDay ? "on this UTC day" : "this month"}, per satellite, never added together.</div>` +
      (extra ? `<div class="lg-extra">${extra}</div>` : "") +
      (POINTS ? `<div class="lg-note">${esc(POINTS.source_summary || "NASA FIRMS standard archive; quality rule; type 0.")}</div>` : "") +
      `<details id="lg-more"${open ? " open" : ""}><summary>Legend and map options</summary>` +
      `<div class="lg-note"><span class="mk snpp round"></span> filled dot: VIIRS (375 m, opacity/radius ∝ FRP MW) · <span class="mk ring aqua"></span> ring: MODIS (1 km).</div>` +
      `<div class="lg-note">A point is one fire pixel on one pass at its reported centre, not a fire or a burned area. ${surface} City names are for orientation.</div>` +
      (POINTS ? UI.sats.map((s) => POINTS.record[s] && POINTS.record[s].support ? `<div class="lg-note">${esc(SAT_INFO[s].short)}: ${esc(recordNote(s))}</div>` : "").join("") : "") +
      `<label class="inline lg-low"><input type="checkbox" id="low-power"${lowPower ? " checked" : ""}> Low-power 2D map (no WebGL)</label></details>`;
    if (markup !== legendMarkup) {
      legendMarkup = markup;
      $("map-legend").innerHTML = markup;
    }
  }
  function platList() {
    const box = $("map-plats");
    if (!box) return;
    if (!box.firstElementChild) box.innerHTML = SATS.map((k) => {
      const info = SAT_INFO[k];
      return `<label><input type="checkbox" data-sat="${k}"><span class="mk ${info.cls}${info.round ? " round" : " ring"}"></span>${esc(info.label)}${k === "SNPP" ? " <small>(reference)</small>" : ""}<b></b></label>`;
    }).join("");
    SATS.forEach((k, i) => {
      const row = box.children[i];
      row.firstElementChild.checked = UI.sats.includes(k);
      const n = shownCount(i, UI.mapDay);
      const val = !inRecord(k) ? `<small>${POINTS.record[k].status === "unavailable" ? "no usable data" : "no record this month"}</small>` : n == null ? "…" : fmt(n);
      const value = row.lastElementChild;
      if (value.dataset.value !== val) { value.dataset.value = val; value.innerHTML = val; }
    });
  }

  // ---------- date scrubber and historical playback ----------
  function dayStatus(sat, d) {
    const support = POINTS && POINTS.record && POINTS.record[sat] && POINTS.record[sat].support;
    if (support) {
      const date = `${POINTS.month}-${String(d).padStart(2, "0")}`;
      if ((support.unrequested_dates || []).includes(date)) return "outside_record";
      if ((support.missing_dates || []).includes(date)) return "provider_missing";
      if ((support.no_row_dates || []).includes(date)) return "nothing_anywhere";
    } else if (POINTS && POINTS.month >= "2026-01" && !inRecord(sat)) return "outside_record";
    const D = S.daily();
    if (!D || !POINTS || D.month !== POINTS.month) return null;   // both replies are always for the selection on screen
    const row = D.rows.find((r) => r.key === sat);
    return row ? row.status[d - 1] : null;
  }
  function drawScrub() {
    const cv = $("scrub-canvas");
    if (!cv || !cv.clientWidth) return;
    const W = cv.clientWidth, H = cv.clientHeight, dpr = Math.min(2, window.devicePixelRatio || 1);
    const artKey = `${W}:${H}:${dpr}|${UI.sats.join(",")}|${UI.dn}`;
    if (scrubArtKey === artKey) { updateScrubDay(); return; }
    scrubArtKey = artKey;
    scrubWidth = W;
    cv.width = W * dpr; cv.height = H * dpr;
    const g = cv.getContext("2d"), c = colors();
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, W, H);
    const n = POINTS ? POINTS.days_in_month : 30, col = W / (n + 1), base = H - 13;
    g.font = `600 10.5px ${c.font}`; g.textAlign = "center"; g.fillStyle = c.muted;
    g.fillText("All", col / 2, H - 2);
    for (const d of [1, 5, 10, 15, 20, 25, n]) g.fillText(String(d), col * (d + 0.5), H - 2);
    g.fillStyle = css("--line"); g.fillRect(0, base, W, 1);
    const sats = UI.sats.map((k) => SATS.indexOf(k));
    let max = 1;
    if (COUNTS) for (const p of sats) for (let d = 1; d <= n; d++) max = Math.max(max, shownCount(p, d));
    const noDataInk = css("--nodata");
    for (let d = 1; d <= n; d++) {
      const x0 = col * d + 1, w = Math.max(1, (col - 2) / Math.max(1, sats.length));
      sats.forEach((p, j) => {
        const st = dayStatus(SATS[p], d);
        const missing = st && !["ok", "modelled"].includes(st);
        if (missing) {           // no usable data that day: a hatched block, never an empty (zero) bar
          g.fillStyle = noDataInk; g.fillRect(x0 + j * w, base - 12, w - 0.5, 12);
          g.strokeStyle = c.muted; g.lineWidth = 1; g.beginPath(); g.moveTo(x0 + j * w, base); g.lineTo(x0 + j * w + w - 0.5, base - 12); g.stroke();
        } else if (COUNTS) {
          const v = shownCount(p, d), h = v ? Math.max(2.6, Math.sqrt(v / max) * (base - 2)) : 0;
          g.fillStyle = SAT_COLOR(c, p); g.fillRect(x0 + j * w, base - h, Math.max(1, w - 0.5), h);
        }
      });
    }
    updateScrubDay();
  }
  function updateScrubDay() {
    const col = scrubWidth / ((POINTS?.days_in_month || 30) + 1);
    const mark = $("scrub-selection");
    if (mark && col > 0) {
      mark.style.width = `${Math.max(0, col - 2)}px`;
      mark.style.transform = `translateX(${col * UI.mapDay}px)`;
    }
    const lab = $("scrub-date");
    if (!POINTS) { lab.innerHTML = ""; return; }
    let small = play ? "Historical playback · past observations" : "Past observations · √-scale daily bars (hatched = provider gap)";
    if (UI.mapDay) {
      const gaps = UI.sats.map((k) => [k, dayStatus(k, UI.mapDay)]).filter(([, st]) => st && !["ok", "modelled"].includes(st));
      if (gaps.length) small = gaps.map(([k]) => `${SAT_INFO[k].short}: no usable data this day`).join("; ");
    }
    lab.innerHTML = `${esc(UI.mapDay ? when() + " (UTC)" : "Whole month: " + when())}<small>${esc(small)}</small>`;
  }
  function setDay(d, fromPlay = false) {
    UI.mapDay = Math.max(0, Math.min(POINTS ? POINTS.days_in_month : 31, d));
    if (!fromPlay) stopPlay(false);
    updateScrubDay();
    if (!scrubFrame) scrubFrame = requestAnimationFrame(() => commitDay(true));
  }
  function commitDay(scrubbing) {
    cancelAnimationFrame(scrubFrame);
    scrubFrame = 0;
    applyFilter(scrubbing);
    engine?.setPlayback?.(UI.mapDay, !!play);
    if (!scrubbing) S.syncUrl();
  }
  function startPlay() {
    if (!POINTS || play) return;
    if (UI.mapDay >= POINTS.days_in_month) UI.mapDay = 0;
    const tick = () => {
      if (!POINTS || UI.mapDay >= POINTS.days_in_month) { stopPlay("Playback finished"); return; }
      setDay(UI.mapDay + 1, true);
    };
    const stepMs = S.motionMode() === "off" ? 500 : 750;
    play = setInterval(tick, stepMs);
    $("play-btn").setAttribute("aria-pressed", "true");
    $("play-btn").innerHTML = ic("pause");
    $("play-btn").setAttribute("aria-label", "Pause the historical playback");
    if (engine && engine.setPlayback) engine.setPlayback(UI.mapDay || 1, true);
    tick();
  }
  function playTransition() {
    if (!engine) return;
    if (engine.kind !== "gl" || S.motionMode() !== "full") {
      if (engine.kind === "gl") { setMapMode("3d", false); setOrbit(true); }
      fitNow(false);
      S.toast(engine.kind === "gl" ? "Motion is reduced: jumped straight to the regional view." : "2D map: fitted the selected region.");
      return;
    }
    window.SeamIntro.open(true, true);
  }
  function stopPlay(sync = true) {
    if (!play) return;
    clearInterval(play); play = null;
    $("play-btn").setAttribute("aria-pressed", "false");
    $("play-btn").innerHTML = ic("play");
    $("play-btn").setAttribute("aria-label", "Play this month day by day (historical playback of past observations)");
    if (engine && engine.setPlayback) engine.setPlayback(UI.mapDay, false);
    updateScrubDay();
    if (sync) S.syncUrl();
  }

  // ---------- inspector (the same content wherever a detection is opened) ----------
  function timeOf(i) {
    const [y, m] = POINTS.month.split("-").map(Number);
    const t = new Date(Date.UTC(y, m - 1, 1) + POINTS.minute[i] * 60000);
    return t.toISOString().slice(0, 16).replace("T", " ");
  }
  function inspectHtml(i) {
    const P = POINTS, sat = SATS[P.p[i]], info = SAT_INFO[sat], modis = P.p[i] < 2;
    const conf = modis ? `${esc(P.conf[i])} of 100 (the product's own score, not a probability; 30 or more kept)`
      : `${{ n: "nominal", h: "high", l: "low" }[P.conf[i]] || esc(P.conf[i])} (the product's own class, not a probability)`;
    const na = "<i>unavailable</i>";
    const stream = P.streams && P.stm ? P.streams[P.stm[i]] : "standard";
    const screened = P.type_screen ? P.type_screen[i] === "type0" : true;
    const areaKm2 = (P.scan[i] != null && P.track[i] != null) ? P.scan[i] * P.track[i] : null;
    const geomNote = areaKm2 == null ? "" : modis
      ? ` (~${fmt(areaKm2, 2)} km²; MODIS nadir ≈ 1.0 km², stretching off-nadir toward ~9.7 km² bowtie footprint)`
      : ` (~${fmt(areaKm2, 2)} km²; VIIRS nadir ≈ 0.14 km² via 3:1→2:1→1:1 aggregation, edge < 0.8 km)`;
    const frpNote = P.frp[i] == null ? na : `${fmt(P.frp[i], 1)} MW (${modis ? "MODIS floor ~3.7–40 MW; linear MIR FRP" : "VIIRS floor ~0.5 MW; I4 367 K saturation uses M13 hybrid FRP"})`;
    return `<h4><span class="mk ${info.cls}${info.round ? " round" : " ring"}"></span>${esc(info.label)} detection</h4><dl>
      <dt>Acquired</dt><dd>${timeOf(i)} UTC, ${P.dn[i] ? "night" : "day"} pass</dd>
      <dt>Position</dt><dd>${fmt(P.lat[i], 4)}°N, ${fmt(P.lon[i], 4)}°E (reported pixel centre)</dd>
      <dt>Product</dt><dd>${esc(P.products[sat])}; file version ${esc(P.versions[P.ver[i]])}</dd>
      <dt>Confidence</dt><dd>${conf}</dd>
      <dt>Fire radiative power</dt><dd>${frpNote}</dd>
      <dt>Pixel at this scan angle</dt><dd>${P.scan[i] == null ? na : `${fmt(P.scan[i], 2)} km along scan × ${fmt(P.track[i], 2)} km along track${geomNote}`}</dd>
      <dt>Source</dt><dd>NASA FIRMS ${stream === "nrt" ? "near-real-time (NRT)" : esc(stream) + " processing"}: ${esc(P.sources[P.src[i]])}</dd>
      <dt>Filters passed</dt><dd>quality rule; ${screened ? "type 0 (presumed vegetation burning)" : "untyped NRT stream: static industrial/volcanic sources (type 2 gas flares, brick kilns, smelters) cannot be excluded with this field"}</dd>
      <dt>Selection</dt><dd>${esc(P.region)}${P.bbox ? ` (${P.bbox.map((v) => fmt(v, 2)).join(", ")})` : ""}</dd></dl>
      <p class="note">One fire pixel on one satellite pass. Not a fire, a burned area or an emission estimate. This row is in the detections export for the same area.</p>
      <div class="btn-row"><button type="button" class="btn" data-insp="zoom">Zoom to it</button><button type="button" class="btn" data-insp="clear">Clear</button>${UI.ws === "overview" ? `<button type="button" class="btn" data-go="explore">Open in Explore</button>` : ""}</div>`;
  }
  function inspect(i) {
    picked = i;
    if (i != null && $("sat-card")) { $("sat-card").hidden = true; satPicked = null; }
    if (engine) engine.select(i);
    const side = $("inspector"), card = $("map-card");
    if (i == null || !POINTS) {
      if (side) side.innerHTML = `<p class="note">Click a point on the map, or pick a row from the list below.</p>`;
      card.hidden = true; card.innerHTML = "";
      return;
    }
    const html = inspectHtml(i);
    if (side) side.innerHTML = html;
    card.innerHTML = `<button type="button" class="icon-btn card-x" data-insp="clear" aria-label="Close the detection details">${ic("close")}</button>` + html;
    card.hidden = UI.ws !== "overview";
  }
  function pick(i) {
    stopPlay();
    inspect(i);
    if (UI.ws === "explore" && $("inspector")) { $("inspector").focus({ preventScroll: true }); $("inspector-block").scrollIntoView({ block: "nearest", behavior: S.motionMode() === "full" ? "smooth" : "auto" }); }
  }
  function hover(i, evt) {
    if (i == null || !POINTS || !evt) { S.hideTip(); return; }
    const sat = SATS[POINTS.p[i]];
    const confidence=POINTS.p[i]<2?`${esc(POINTS.conf[i])}/100 product score`:({n:'nominal',h:'high',l:'low'}[POINTS.conf[i]]||esc(POINTS.conf[i]));
    S.showTip(`<b>${esc(SAT_INFO[sat].label)}</b><br>${timeOf(i)} UTC · ${POINTS.dn[i] ? "night" : "day"} pass<br>${POINTS.frp[i] == null ? "FRP unavailable" : `FRP: ${fmt(POINTS.frp[i], 1)} MW`}<br>Confidence: ${confidence}<br>Sensor product: ${esc(POINTS.products[sat])}<br><span style="opacity:.8">Click for details</span>`, evt);
  }
  function pointList() {
    const box = $("point-list");
    if (!box || UI.ws !== "explore" || !$("point-list-wrap").open) return;
    if (!POINTS) { box.innerHTML = `<p class="note">No detections loaded.</p>`; return; }
    const matching = matchingRows(currentFilter()), total = matching.length, rows = matching.slice(0, listShown);
    box.innerHTML = `<table><caption class="note" style="caption-side:top;text-align:left">${fmt(total)} detections match the filters${total > rows.length ? `; the first ${rows.length} by time are listed` : ""}. This is a list of rows per satellite, not a count of fires.</caption>
      <thead><tr><th scope="col">Time (UTC)</th><th scope="col">Satellite</th><th scope="col">Pass</th><th scope="col">Lat</th><th scope="col">Lon</th><th scope="col">FRP, MW</th></tr></thead><tbody>` +
      rows.map((i) => `<tr><th scope="row"><button type="button" data-pt="${i}">${timeOf(i).slice(5)}</button></th><td>${SAT_INFO[SATS[POINTS.p[i]]].short}</td><td>${POINTS.dn[i] ? "night" : "day"}</td><td>${fmt(POINTS.lat[i], 3)}</td><td>${fmt(POINTS.lon[i], 3)}</td><td>${POINTS.frp[i] == null ? "–" : fmt(POINTS.frp[i], 1)}</td></tr>`).join("") +
      `</tbody></table>${total > rows.length ? `<button type="button" class="btn" id="list-more">Show 100 more</button>` : ""}`;
  }

  // ---------- rectangle drawing (top-down, north up, so the drawn box is a true west-south-east-north box) ----------
  function startDraw() {
    if (drawing) { endDraw(); return; }
    drawing = true;
    if (engine.kind === "gl") { UI.mode = "2d"; engine.setMode("2d", false); syncMode(); }
    engine.setInteractive(false);
    $("map-view").classList.add("drawing");
    $("draw-rect").setAttribute("aria-pressed", "true");
    $("map-banner").textContent = "Drag on the map to draw a rectangle (north is up). Esc cancels. The typed west, south, east and north fields in Selection update to match.";
  }
  function endDraw() {
    drawing = false;
    engine.setInteractive(true);
    $("map-view").classList.remove("drawing");
    $("draw-rect").setAttribute("aria-pressed", "false");
    $("map-draft").hidden = true;
    if (engine.kind === "gl") $("map-banner").textContent = "";
  }
  function wireDraw() {
    const view = $("map-view"), draft = $("map-draft");
    let a = null;
    const at = (e) => { const r = view.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
    view.addEventListener("pointerdown", (e) => { if (!drawing) return; e.preventDefault(); e.stopPropagation(); a = at(e); view.setPointerCapture(e.pointerId); }, true);
    view.addEventListener("pointermove", (e) => {
      if (!drawing || !a) return;
      const b = at(e);
      Object.assign(draft.style, { left: Math.min(a[0], b[0]) + "px", top: Math.min(a[1], b[1]) + "px", width: Math.abs(a[0] - b[0]) + "px", height: Math.abs(a[1] - b[1]) + "px" });
      draft.hidden = false;
    }, true);
    view.addEventListener("pointerup", (e) => {
      if (!drawing || !a) return;
      const b = at(e), p = engine.unproject(Math.min(a[0], b[0]), Math.max(a[1], b[1])), q = engine.unproject(Math.max(a[0], b[0]), Math.min(a[1], b[1]));
      a = null;
      const box = [p[0], p[1], q[0], q[1]].map((v) => Math.round(v * 1000) / 1000);
      endDraw();
      if (box[2] - box[0] < 0.02 || box[3] - box[1] < 0.02) { S.toast("That rectangle is too small. Drag a larger one.", { error: true }); return; }
      const why = S.boxProblem(box);
      if (why) { S.toast(why, { error: true }); return; }
      S.selectBox(box);
    }, true);
  }

  // ---------- export: the real rendered view, with what it shows written on it ----------
  async function exportPng() {
    if (!mapWorkspace() && S.result() && !S.pending()) {
      S.go("explore");
      await loadPoints();
      if (mapLibraryPending) await window.loadSeamMapLibrary();
      if (!mapWorkspace()) return;
      await new Promise(requestAnimationFrame);
      if (engine?.kind === "gl" && !engine.map.loaded()) {
        engine.whenIdle(() => {
          if (mapWorkspace() && engine?.kind === "gl" && engine.map.loaded()) exportPng();
          else S.toast("The map is still drawing. Export again when it has finished.", { error: true });
        });
        return;
      }
    }
    if (S.pending() || pointsPending || PERR || PKEY !== JSON.stringify(pointRequest())) {
      S.toast("The map selection is still loading or unavailable. Export again when its detections have finished loading.", { error: true }); return;
    }
    if (!engine || !POINTS) { S.toast("The map has no detections loaded to export.", { error: true }); return; }
    if (engine.kind === "gl" && (!engine.map.loaded()
      || (vmode === "towers" || vmode === "footprints") && engine.viewMeta().pending)) {
      S.toast("The map is still drawing. Export again when it has finished.", { error: true }); return;
    }
    capturePng();
  }
  function capturePng() {
    if (!engine || !POINTS) return;
    try {
      // Everything below describes this one synchronous canvas snapshot. A later selection or filter change
      // while toBlob encodes it cannot change the saved image's name, counts, date or annotation.
      const snapshot = { region: selection().region, month: POINTS.month, day: UI.mapDay, dn: UI.dn,
        sats: UI.sats.slice(), when: when(), mode: UI.mode, vmode, kind: engine.kind, exaggeration: engine.exaggeration,
        counts: UI.sats.map((sat) => shownCount(SATS.indexOf(sat), UI.mapDay)),
        source: POINTS.source_summary || "NASA FIRMS standard archive; quality rule; type 0.",
        identity: POINTS.data_identity || "", support: UI.sats.map((sat) => POINTS.record && POINTS.record[sat] && POINTS.record[sat].support ? `${SAT_INFO[sat].short}: ${recordNote(sat)}` : "").filter(Boolean).join(" ") };
      const name = `seamline_map_${snapshot.region.replace(/\W+/g, "_")}_${snapshot.month}${snapshot.day ? "-" + String(snapshot.day).padStart(2, "0") : ""}.png`;
      const src = engine.png(), out = document.createElement("canvas");
      const k = src.clientWidth ? src.width / src.clientWidth : 1, g = out.getContext("2d"), c = colors();
      const lines = [], width = src.width / k - 24;
      const wrap = (text, strong = false) => {
        g.font = `${strong ? "600 14" : "400 12"}px ${c.font}`;
        const measure = (t) => g.measureText ? g.measureText(t).width : t.length * 7;
        let line = "";
        for (const word of text.split(/\s+/)) {
          if (measure(word) > width) { // Keep a full hash or long rectangle coordinate visible on a narrow map.
            if (line) { lines.push({ text: line, strong }); line = ""; }
            for (const letter of word) {
              if (line && measure(line + letter) > width) { lines.push({ text: line, strong }); line = ""; }
              line += letter;
            }
            continue;
          }
          const candidate = line ? `${line} ${word}` : word;
          const measured = measure(candidate);
          if (line && measured > width) { lines.push({ text: line, strong }); line = word; } else line = candidate;
        }
        if (line) lines.push({ text: line, strong });
      };
      wrap(`Seamline · ${snapshot.sats.map((x) => SAT_INFO[x].label).join(", ")} observed detections · ${snapshot.region} · ${snapshot.when} (UTC)`, true);
      wrap(`${snapshot.sats.map((x, i) => `${SAT_INFO[x].short}: ${fmt(snapshot.counts[i])}`).join("; ")} · each satellite counted separately · ${snapshot.dn === "DN" ? "day and night" : snapshot.dn === "D" ? "day" : "night"} passes.`);
      wrap(snapshot.source);
      if (snapshot.support) wrap(snapshot.support);
      const viewDesc = snapshot.kind === "gl" && snapshot.mode === "globe" ? "3D globe view (NOAA elevation)"
        : snapshot.kind === "gl" && snapshot.mode === "3d" ? `3D view (NOAA elevation ×${snapshot.exaggeration})`
        : "2D view";
      const layerDesc = snapshot.vmode === "towers" ? " · FRP 3D towers" : snapshot.vmode === "footprints" ? " · scan×track footprints" : snapshot.vmode === "density" ? " · macro density" : "";
      wrap(`Screen capture of the ${viewDesc}${layerDesc}; a point is one fire pixel on one pass. Exported ${new Date().toISOString().slice(0, 16).replace("T", " ")} UTC.`);
      if (snapshot.identity) wrap(`Input identity: ${snapshot.identity}`);
      out.width = src.width; out.height = Math.round(src.height + (20 + lines.length * 18) * k);
      g.fillStyle = css("--surface"); g.fillRect(0, 0, out.width, out.height);
      g.drawImage(src, 0, 0);
      g.scale(k, k);
      const y0 = src.height / k;
      g.textBaseline = "top";
      lines.forEach((line, i) => {
        g.fillStyle = line.strong ? c.ink : c.muted; g.font = `${line.strong ? "600 14" : "400 12"}px ${c.font}`;
        g.fillText(line.text, 12, y0 + 10 + i * 18);
      });
      out.toBlob((blob) => {
        if (!blob) { S.toast("The map image could not be made.", { error: true }); return; }
        S.save(blob, name);
        S.toast(`Saved ${name}: the map as shown, with its date and source line.`);
      }, "image/png");
    } catch (e) { S.toast(`The map image could not be made (${e.message}).`, { error: true }); }
  }

  function setMapMode(m, animate) {
    UI.mode = ["globe", "3d", "2d"].includes(m) ? m : "3d";
    if (engine && engine.kind === "gl") engine.setMode(UI.mode, animate !== false);
    syncMode();
    S.emit("map-mode",UI.mode);
  }
  function setViewMode(vm) {
    const gl = engine && engine.kind === "gl";
    vmode = ["points", "towers", "footprints", "density"].includes(vm) ? vm : "points";
    if (!gl && vmode === "towers") vmode = "points";
    if (engine && engine.setViewMode) engine.setViewMode(vmode);
    syncMode();
    S.emit("map-filter");
  }
  function setOrbit(on) {
    orbitOn = !!on;
    if (!orbitOn && $("sat-card")) { $("sat-card").hidden = true; satPicked = null; }
    if (engine && engine.setOrbit) engine.setOrbit(orbitOn);
    syncMode();
    S.emit("map-filter");
  }
  function setSeam(on) {
    if (engine && engine.setSeam) engine.setSeam(!!on);
  }
  function flyPose(pose) {
    if (!pose || !engine) return;
    if (pose.mode && pose.mode !== UI.mode) UI.mode = pose.mode;
    if (pose.vmode && pose.vmode !== vmode) { vmode = pose.vmode; if (engine.setViewMode) engine.setViewMode(vmode); }
    if (pose.orbit != null) { orbitOn = !!pose.orbit; if (engine.setOrbit) engine.setOrbit(orbitOn); }
    if (pose.seam != null && engine.setSeam) engine.setSeam(!!pose.seam);
    if (pose.psf != null) { psfOn = !!pose.psf; if (engine.setPsf) engine.setPsf(psfOn); }
    syncMode();
    if (engine.flyPose) engine.flyPose(pose);
  }

  // ---------- start ----------
  function start() {
    if (started) return;
    started = true;
    buildHost();
    $("stage-overview").appendChild(host);
    makeEngine();
    wireDraw();
    mount();
    host.addEventListener("click", (e) => {
      const satPin = e.target.closest("[data-sat-pin]");
      if (satPin) { showSatCard(satPin.dataset.satPin); return; }
      if (e.target.closest("[data-sat-close]")) { if ($("sat-card")) $("sat-card").hidden = true; satPicked = null; return; }
      const cam = e.target.closest("[data-cam]");
      if (cam) {
        const act = cam.dataset.cam;
        if (act === "fit") fitNow(true);
        else if (act === "reset") { if (engine.kind === "gl") { engine.camera("north"); } fitNow(true); }
        else engine.camera(act);
        return;
      }
      const mode = e.target.closest("[data-mode]");
      if (mode) {
        if (mode.getAttribute("aria-disabled") === "true") { S.toast("WebGL 3D is not available here; the 2D map shows the same data.", { second: true }); return; }
        setMapMode(mode.dataset.mode, true);
        S.syncUrl();
        return;
      }
      const vm = e.target.closest("[data-vmode]");
      if (vm) {
        if (vm.getAttribute("aria-disabled") === "true") { S.toast("FRP 3D towers require WebGL 3D view; the 2D layers show the same data.", { second: true }); return; }
        setViewMode(vm.dataset.vmode);
        return;
      }
      if (e.target.closest("#orbit-btn")) { setOrbit(!orbitOn); return; }
      if (e.target.closest("#psf-btn")) { psfOn = !psfOn; if (engine && engine.setPsf) engine.setPsf(psfOn); syncMode(); return; }
      if (e.target.closest("#play-btn")) { play ? stopPlay() : startPlay(); return; }
      if (e.target.closest("#map-retry")) { loadPoints(); return; }
      if (e.target.closest("#map-use-aqua")) { UI.sats = ["Aqua"]; applyFilter(); S.syncUrl(); return; }
    });
    host.addEventListener("change", (e) => {
      if (e.target.id === "low-power") {
        lowPower = e.target.checked;
        if (!lowPower) webglLost = false;
        try { localStorage.setItem("seamline-lowpower", lowPower ? "1" : "0"); } catch (_) { /* storage blocked */ }
        stopPlay(); makeEngine(); enableMapLibrary();
      }
    });
    $("scrub").addEventListener("input", (e) => setDay(Number(e.target.value)));
    $("scrub").addEventListener("change", () => commitDay(false));
    $("point-list-wrap").addEventListener("toggle", pointList);
    document.addEventListener("click", (e) => {
      const insp = e.target.closest("[data-insp]");
      if (insp) { if (insp.dataset.insp === "clear") inspect(null); else if (picked != null && POINTS) engine.flyTo(POINTS.lon[picked], POINTS.lat[picked]); return; }
      const pt = e.target.closest("[data-pt]");
      if (pt) { const i = Number(pt.dataset.pt); inspect(i); engine.flyTo(POINTS.lon[i], POINTS.lat[i]); $("inspector").focus(); return; }
      if (e.target.closest("#list-more")) { listShown += 100; pointList(); return; }
      if (e.target.closest("#draw-rect")) { startDraw(); return; }
      if (e.target.closest("#map-reset-filters")) { UI.sats = ["SNPP"]; UI.dn = "DN"; UI.mapDay = 0; stopPlay(); applyFilter(); S.syncUrl(); return; }
      const dn = e.target.closest("#map-dn [data-dn]");
      if (dn) { UI.dn = dn.dataset.dn; applyFilter(); S.syncUrl(); }
    });
    document.addEventListener("change", (e) => {
      const sat = e.target.closest && e.target.closest("#map-plats [data-sat]");
      if (sat) { UI.sats = SATS.filter((k) => (k === sat.dataset.sat ? sat.checked : UI.sats.includes(k))); applyFilter(); S.syncUrl(); return; }
      if (e.target.id === "map-month" || e.target.id === "map-year") S.setDayMonth(Number($("map-year").value), Number($("map-month").value));
    });
    $("map-prev").addEventListener("click", () => $("daily-prev").click());
    $("map-next").addEventListener("click", () => $("daily-next").click());
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && drawing) { e.preventDefault(); endDraw(); } });
    document.addEventListener("visibilitychange", () => {
      if (engine?.setActive) engine.setActive(!document.hidden && (UI.ws === "explore" || UI.ws === "overview"));
      if (document.hidden) {
        stopPlay();
        if (engine && engine.fx && engine.fx.stopIdle) engine.fx.stopIdle();
      } else if (orbitOn && engine && engine.kind === "gl" && engine.map) {
        engine.map.triggerRepaint();
      }
    });
    window.addEventListener("resize", () => { if (engine) engine.resize(); drawScrub(); });

    S.on("selection", () => {
      engine.setSelection(selection());
      if (mapWorkspace() && !window.SeamIntro?.ownsCamera()) fitSelection(true);
      inspect(null);
      loadPoints();
    });
    S.on("daymonth", () => { inspect(null); loadPoints(); });
    S.on("daily", () => { scrubArtKey = ""; drawScrub(); });
    S.on("ws", () => {
      stopPlay();
      if (drawing) endDraw();
      mount();
      if (mapWorkspace()) { loadPoints(); pointList(); }
      if (picked != null) inspect(picked);
      if (!mapWorkspace() && $("sat-card")) $("sat-card").hidden = true;
    });
    S.on("story", (key) => { setSeam(key === "seam"); if (key !== "seam" && !orbitOn && $("sat-card")) { $("sat-card").hidden = true; satPicked = null; } syncMode(); S.emit("map-filter"); });
    S.on("theme", () => { engine.setTheme(colors()); scrubArtKey = ""; drawScrub(); legend(); });
    S.on("motion", () => {
      if (engine && engine.fx && S.motionMode() !== "full") engine.fx.stopIdle();
      if (engine && engine.kind === "gl" && engine.map) engine.map.triggerRepaint();
    });
    S.on("filters", applyFilter);
    S.on("reset", () => { stopPlay(); inspect(null); setOrbit(false); setViewMode("points"); setSeam(false); });
    S.on("resize", () => { if (mapWorkspace()) { engine?.resize(); drawScrub(); } });
    S.on("export-map", exportPng);
    S.on("print", (on) => {        // print a readable top-down view, then put the camera back
      if (engine.kind !== "gl") return;
      if (on) { printBackup = UI.mode; engine.setMode("2d", false); fitNow(false); }
      else if (printBackup) { UI.mode = printBackup; engine.setMode(printBackup, false); syncMode(); fitNow(false); printBackup = null; }
    });
    if (S.result()) { engine.setSelection(selection()); if (mapWorkspace() && !window.SeamIntro?.ownsCamera()) fitSelection(false); loadPoints(); }
    title(); legend(); platList();
  }
  window.SeamMap = { engine: () => engine, points: () => POINTS, bounds: selBounds, colors, start, setMode: setMapMode, setViewMode, setOrbit, setSeam, flyPose, playTransition, frpSummary, exactCount, pointStatus, isInitialViewReady, fitAfterIntro, mapLibraryPending: () => mapLibraryPending };
  if (S.meta() && S.geo()) start(); else S.on("ready", start);
})();
