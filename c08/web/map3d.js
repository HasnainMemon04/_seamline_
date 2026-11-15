// Seamline map engine (MapLibre GL JS 5.24.1, bundled locally). Supports three interactive projections/views:
// Globe (3D spherical Earth with orbital arcs), 3D (tilted Web Mercator + 10x NOAA terrain relief + FRP towers),
// and 2D (orthometric top-down). Nothing here invents fire data or distorts counts: marker size is fixed in
// Pixels mode, and alternate geometry encodings (FRP 3D towers, oriented scan x track footprints, macro density)
// carry explicit scientific legends and never alter statistical totals.
(function () {
  "use strict";
  const TERRAIN_EXAGGERATION = 5;    // shown in the legend; the relief is real elevation, stretched vertically
  const PITCH_3D = 52, PITCH_GLOBE = 24, DEM_BOUNDS = [58.0, 21.0, 84.0, 40.0];
  const PAK_BOUNDS = [[48, 15], [94, 44]];
  const TILES = "/static/terrain/{z}/{x}/{y}.png";
  const MAX_POLY_FEATS = 2400;
  const D2R = Math.PI / 180;

  let LAND_PROMISE = null, RIVERS_PROMISE = null;
  function loadLand() {
    if (!LAND_PROMISE) {
      LAND_PROMISE = fetch("/static/assets/world/land.geojson").then((r) => (r.ok ? r.json() : null)).catch(() => null)
        .then((d) => d || { type: "FeatureCollection", features: [] });
    }
    return LAND_PROMISE;
  }
  function loadRivers() {
    if (!RIVERS_PROMISE) {
      RIVERS_PROMISE = fetch("/static/assets/world/rivers.geojson").then((r) => (r.ok ? r.json() : null)).catch(() => null)
        .then((d) => d || { type: "FeatureCollection", features: [] });
    }
    return RIVERS_PROMISE;
  }

  function buildGraticule() {
    const features = [];
    for (let lat = -75; lat <= 75; lat += 15) {
      const coords = [];
      for (let lon = -180; lon <= 180; lon += 6) coords.push([lon, lat]);
      features.push({ type: "Feature", properties: { eq: lat === 0 ? 1 : 0 }, geometry: { type: "LineString", coordinates: coords } });
    }
    for (let lon = -180; lon < 180; lon += 15) {
      const coords = [];
      for (let lat = -82; lat <= 82; lat += 4) coords.push([lon, lat]);
      features.push({ type: "Feature", properties: { eq: 0 }, geometry: { type: "LineString", coordinates: coords } });
    }
    return { type: "FeatureCollection", features };
  }

  function available() {
    if (typeof maplibregl === "undefined") return "The map library did not load.";
    try {
      const c = document.createElement("canvas");
      const gl = c.getContext("webgl2") || c.getContext("webgl");
      if (!gl) return "This browser or device has no WebGL.";
    } catch (e) { return "WebGL could not start."; }
    return "";
  }

  const EMPTY_FC = { type: "FeatureCollection", features: [] };
  const colorOf = (c) => ["match", ["get", "p"], 0, c.terra, 1, c.aqua, 2, c.snpp, 3, c.n20, 4, c.n21, c.ink];
  const radius = ["interpolate", ["linear"], ["zoom"], 3, 2.0, 5, 2.8, 7, 3.8, 10, 5.8];
  const viirsRadius = ["interpolate", ["linear"], ["zoom"],
    3, 1.3,
    5, ["interpolate", ["linear"], ["coalesce", ["get", "frp"], 4], 0.5, 1.5, 10, 2.3, 45, 3.6],
    7, ["interpolate", ["linear"], ["coalesce", ["get", "frp"], 4], 0.5, 2.4, 10, 3.5, 45, 5.2],
    10, ["interpolate", ["linear"], ["coalesce", ["get", "frp"], 4], 0.5, 3.8, 10, 5.4, 45, 7.6]];
  const viirsOpacity = ["interpolate", ["linear"], ["coalesce", ["get", "frp"], 4], 0.5, 0.46, 8, 0.74, 35, 0.94];

  function dotPaint(c) {
    return {
      "circle-radius": viirsRadius, "circle-color": colorOf(c), "circle-opacity": viirsOpacity,
      "circle-stroke-color": c.halo, "circle-stroke-width": 0.45,
      "circle-pitch-alignment": "viewport", "circle-pitch-scale": "viewport",
    };
  }
  function ringPaint(c) {
    return {
      "circle-radius": radius, "circle-color": c.halo, "circle-opacity": 0.55,
      "circle-stroke-color": colorOf(c), "circle-stroke-width": 1.9,
      "circle-pitch-alignment": "viewport", "circle-pitch-scale": "viewport",
    };
  }
  function hillPaint(c, mode, dn) {
    return {
      "hillshade-shadow-color": c.shadow, "hillshade-highlight-color": c.highlight, "hillshade-accent-color": c.shadow,
      "hillshade-exaggeration": mode === "3d" ? 0.62 : 0.34,
      "hillshade-illumination-direction": dn === "N" ? 135 : 315,
      "hillshade-illumination-anchor": "map",
    };
  }
  function heatPaint(c) {
    const h0 = c.dark ? "rgba(0,0,0,0)" : "rgba(255,255,255,0)";
    const h1 = c.heat1 || (c.dark ? "rgba(14,107,111,0.52)" : "rgba(14,107,111,0.45)");
    const h2 = c.heat2 || (c.dark ? "rgba(94,218,208,0.75)" : "rgba(43,104,173,0.68)");
    const h3 = c.heat3 || (c.dark ? "rgba(243,199,122,0.86)" : "rgba(138,93,11,0.82)");
    const h4 = c.heat4 || (c.dark ? "rgba(244,230,145,0.95)" : "rgba(19,24,26,0.92)");
    const ramp = ["interpolate", ["linear"], ["heatmap-density"],
      0, h0,
      0.18, h1,
      0.42, h2,
      0.70, h3,
      0.95, h4];
    return {
      "heatmap-weight": ["interpolate", ["linear"], ["coalesce", ["get", "frp"], 8], 1, 0.35, 30, 0.7, 150, 1.0],
      "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 3, 0.85, 7, 1.65],
      "heatmap-color": ramp,
      "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 3, 9, 6, 16, 9, 22],
      "heatmap-opacity": ["interpolate", ["linear"], ["zoom"], 7.5, 0.86, 9.5, 0.18],
    };
  }

  function style(c, geo, mode, dn) {
    const dem = { type: "raster-dem", tiles: [TILES], tileSize: 256, encoding: "terrarium", minzoom: 4, maxzoom: 7, bounds: DEM_BOUNDS };
    const bgCol = mode === "globe" ? c.ocean : c.sky;
    const fillOp = mode === "3d" ? 0.30 : mode === "globe" ? 0.38 : 0.56;
    const globeVis = mode === "globe" ? "visible" : "none";
    return {
      version: 8,
      sources: {
        dem, "dem-hs": { ...dem, maxzoom: 6 },
        "world-land": { type: "geojson", data: EMPTY_FC, tolerance: 1.8, maxzoom: 5, buffer: 4 },
        "world-rivers": { type: "geojson", data: EMPTY_FC, tolerance: 1.0, maxzoom: 8, buffer: 8 },
        grat: { type: "geojson", data: buildGraticule(), tolerance: 1.2, maxzoom: 5 },
        prov: { type: "geojson", data: geo },
        box: { type: "geojson", data: EMPTY_FC },
        pts: { type: "geojson", data: EMPTY_FC, tolerance: 0, buffer: 16 },
        "pts-poly": { type: "geojson", data: EMPTY_FC, tolerance: 0.75, buffer: 8 },
        "pts-psf": { type: "geojson", data: EMPTY_FC, tolerance: 0.75, buffer: 8 },
      },
      layers: [
        { id: "bg", type: "background", paint: { "background-color": bgCol } },
        { id: "graticule", type: "line", source: "grat", layout: { visibility: globeVis }, paint: { "line-color": c.line, "line-width": 0.65, "line-opacity": 0.28 } },
        { id: "world-land-fill", type: "fill", source: "world-land", layout: { visibility: globeVis }, paint: { "fill-color": c.landDim || c.land, "fill-opacity": 0.94 } },
        { id: "world-land-line", type: "line", source: "world-land", layout: { visibility: globeVis, "line-join": "round" }, paint: { "line-color": c.line, "line-width": 0.75, "line-opacity": 0.52 } },
        { id: "hills", type: "hillshade", source: "dem-hs", layout: { visibility: mode === "globe" ? "none" : "visible" }, paint: hillPaint(c, mode, dn) },
        { id: "prov-fill", type: "fill", source: "prov", paint: { "fill-color": c.land, "fill-opacity": fillOp } },
        { id: "world-rivers", type: "line", source: "world-rivers", paint: { "line-color": c.river, "line-width": ["interpolate", ["linear"], ["zoom"], 3, 0.85, 6, 1.5, 9, 2.5], "line-opacity": 0.72 }, layout: { "line-cap": "round", "line-join": "round" } },
        { id: "prov-line", type: "line", source: "prov", paint: { "line-color": c.line, "line-width": 1.0, "line-opacity": 0.82 }, layout: { "line-join": "round" } },
        { id: "prov-sel-glow", type: "line", source: "prov", filter: ["==", ["get", "shapeName"], ""], paint: { "line-color": c.lineSel, "line-width": 2.6, "line-opacity": 0.12 }, layout: { "line-join": "round", "line-cap": "round" } },
        { id: "prov-sel", type: "line", source: "prov", filter: ["==", ["get", "shapeName"], ""], paint: { "line-color": c.lineSel, "line-width": 1.65 }, layout: { "line-join": "round", "line-cap": "round" } },
        { id: "box-fill", type: "fill", source: "box", paint: { "fill-color": c.sel, "fill-opacity": 0.32 } },
        { id: "box-line", type: "line", source: "box", paint: { "line-color": c.lineSel, "line-width": 2.5, "line-dasharray": [2, 1.5] } },
        // Macro density exploration layer (optional layer mode)
        { id: "pts-heat", type: "heatmap", source: "pts", filter: ["==", ["get", "p"], -1], layout: { visibility: "none" }, paint: heatPaint(c) },
        // Oriented IFOV scan x track footprints + optional MODIS 2x1 km triangular PSF kernel halo
        { id: "pts-fp-psf", type: "fill", source: "pts-psf", layout: { visibility: "none" }, paint: { "fill-color": colorOf(c), "fill-opacity": 0.16, "fill-outline-color": colorOf(c) } },
        { id: "pts-fp", type: "fill", source: "pts-poly", layout: { visibility: "none" }, paint: { "fill-color": colorOf(c), "fill-opacity": 0.44 } },
        { id: "pts-fp-line", type: "line", source: "pts-poly", layout: { visibility: "none" }, paint: { "line-color": colorOf(c), "line-width": 1.25, "line-opacity": 0.92 } },
        // 3D Hexagonal FRP Extrusion Towers seated directly on DEM relief
        { id: "pts-towers", type: "fill-extrusion", source: "pts-poly", layout: { visibility: "none" }, paint: {
          "fill-extrusion-color": colorOf(c),
          "fill-extrusion-height": ["get", "h"],
          "fill-extrusion-base": 0,
          "fill-extrusion-opacity": 0.90,
          "fill-extrusion-vertical-gradient": true,
        } },
        // MODIS: a ring. VIIRS: a filled dot. Shape as well as colour tells the instruments apart.
        { id: "pts-modis", type: "circle", source: "pts", filter: ["==", ["get", "p"], -1], paint: ringPaint(c) },
        { id: "pts-viirs", type: "circle", source: "pts", filter: ["==", ["get", "p"], -1], paint: dotPaint(c) },
        { id: "pts-sel", type: "circle", source: "pts", filter: ["==", ["get", "i"], -1],
          paint: { "circle-radius": 11, "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": c.ink, "circle-stroke-width": 2.5, "circle-pitch-alignment": "viewport" } },
      ],
    };
  }

  function hexPolygon(lon, lat, radM) {
    const cosL = Math.max(0.25, Math.cos(lat * D2R));
    const dxDeg = radM / (111320 * cosL), dyDeg = radM / 110574;
    const ring = [];
    for (let k = 0; k < 6; k++) {
      const a = (k * 60 + 30) * D2R;
      ring.push([lon + Math.cos(a) * dxDeg, lat + Math.sin(a) * dyDeg]);
    }
    ring.push(ring[0]);
    return [ring];
  }

  function orientedFootprint(lon, lat, scanKm, trackKm, dn, isModis) {
    const sw = Math.max(0.25, scanKm || (isModis ? 1.0 : 0.375));
    const tr = Math.max(0.25, trackKm || (isModis ? 1.0 : 0.375));
    // Sun-synchronous heading ~191.5 deg descending (day) vs ~348.5 deg ascending (night)
    const trackDeg = dn === 1 ? -11.5 : 168.5;
    const fwdR = trackDeg * D2R;
    const fE = Math.sin(fwdR), fN = Math.cos(fwdR);
    const rE = fN, rN = -fE;
    const hs = (sw * 1000) * 0.5, ht = (tr * 1000) * 0.5;
    const cosL = Math.max(0.25, Math.cos(lat * D2R));
    const pt = (sSign, tSign) => {
      const eastM = rE * hs * sSign + fE * ht * tSign;
      const northM = rN * hs * sSign + fN * ht * tSign;
      return [lon + eastM / (111320 * cosL), lat + northM / 110574];
    };
    const p0 = pt(-1, -1), p1 = pt(1, -1), p2 = pt(1, 1), p3 = pt(-1, 1);
    return [[p0, p1, p2, p3, p0]];
  }

  function create(container, opts) {
    let c = opts.colors;
    let openingGlobe = !!opts.openingBounds;
    let mode = openingGlobe ? "globe" : ["globe", "3d", "2d"].includes(opts.mode) ? opts.mode : "3d";
    let vmode = ["points", "towers", "footprints", "density"].includes(opts.vmode) ? opts.vmode : "points";
    let selName = "", lost = false, labels = [];
    let rawPoints = null, activeFilter = { sats: [2], dn: "DN", day: 0 };
    let polyCacheKey = "", psfOn = false, shownPtsMeta = { total: 0, shown: 0, limited: false };
    let filterKey = "", polyTimer = 0;
    const polygonCache = new Map();
    const pointLayerFilters = new Map();
    let appliedPolygons = null, awaitingGeometry = false;

    const initPitch = openingGlobe ? 0 : mode === "globe" ? PITCH_GLOBE : mode === "3d" ? PITCH_3D : 0;
    const initZoom = openingGlobe ? 1.8 : mode === "globe" ? 2.4 : 4.4;
    const [west, south, east, north] = opts.openingBounds || [];
    const center = openingGlobe ? [(west + east) / 2, (south + north) / 2] : [69.6, 30.3];
    const map = new maplibregl.Map({
      container, style: style(c, opts.geo, mode, activeFilter.dn),
      center, zoom: initZoom, pitch: initPitch, bearing: openingGlobe ? -8 : 0,
      minZoom: mode === "globe" ? 1.35 : 3.4, maxZoom: 12.2, maxPitch: 75,
      maxBounds: mode === "globe" ? null : PAK_BOUNDS,
      attributionControl: false, renderWorldCopies: false,
      fadeDuration: 0, dragRotate: true, pixelRatio: Math.min(window.devicePixelRatio || 1, 1.5),
      canvasContextAttributes: { antialias: true, preserveDrawingBuffer: true },
    });

    const dur = () => (opts.motion() === "full" ? 620 : 0);
    const ease = (o) => { if (dur()) map.easeTo({ ...o, duration: dur(), essential: true }); else map.jumpTo(o); };
    const canvas = map.getCanvas();
    canvas.setAttribute("aria-label", "Map of observed detections. Arrow keys pan, plus and minus zoom, Shift with arrow keys rotates and tilts. The list of detections is the keyboard alternative for inspecting points.");

    const fx = window.SeamFX ? window.SeamFX.create({
      colors: c,
      isDark: !!c.dark,
      motion: opts.motion,
      matchingRows: opts.matchingRows,
      mode: () => mode,
      onTick: (badges) => { if (opts.onSatTick) opts.onSatTick(badges); },
    }) : null;

    let landLoaded = false, riversLoaded = false;
    let lastLabelZ = -99, lastLabelMode = "", moving = false, lastPickAt = 0;

    function ensureLandLoaded() {
      if (landLoaded) return;
      loadLand().then((land) => {
        if (landLoaded) return;
        landLoaded = true;
        try { if (map.getSource("world-land")) map.getSource("world-land").setData(land); } catch (_) {}
      });
    }
    function ensureRiversLoaded() {
      if (riversLoaded) return;
      loadRivers().then((rivers) => {
        if (riversLoaded) return;
        riversLoaded = true;
        try { if (map.getSource("world-rivers")) map.getSource("world-rivers").setData(rivers); } catch (_) {}
      });
    }

    function syncTerrain() {
      const z = map.getZoom();
      const wantTerrain = mode === "3d" || (mode === "globe" && z >= 4.5);
      const wantHills = mode !== "globe" || z >= 4.5;
      try {
        const cur = map.getTerrain();
        if (wantTerrain && !cur) map.setTerrain({ source: "dem", exaggeration: TERRAIN_EXAGGERATION });
        else if (!wantTerrain && cur) map.setTerrain(null);
      } catch (e) { /* terrain unsupported */ }
      if (map.getLayer("hills")) {
        const curVis = map.getLayoutProperty("hills", "visibility");
        const nextVis = wantHills ? "visible" : "none";
        if (curVis !== nextVis) map.setLayoutProperty("hills", "visibility", nextVis);
      }
    }

    function applyLight() {
      const night = activeFilter.dn === "N";
      try {
        map.setLight({
          anchor: "viewport",
          color: night ? "#8fb5d6" : "#fff7e8",
          intensity: mode === "globe" ? (night ? 0.25 : 0.45) : (night ? 0.20 : 0.38),
          position: [1.35, night ? 115 : 315, night ? 38 : 52],
        });
      } catch (_) {}
      if (map.getLayer("hills")) {
        for (const [k, v] of Object.entries(hillPaint(c, mode, activeFilter.dn))) {
          map.setPaintProperty("hills", k, v);
        }
      }
    }

    function setSky() {
      try {
        if (mode === "globe") {
          map.setSky({
            "sky-color": c.dark ? "#040810" : "#0b1a29",
            "horizon-color": c.dark ? "#174b68" : "#4b8ab5",
            "fog-color": c.ocean,
            "sky-horizon-blend": 0.56,
            "horizon-fog-blend": 0.68,
            "fog-ground-blend": 0.52,
            "atmosphere-blend": 0.90,
          });
        } else {
          map.setSky({ "sky-color": c.sky, "horizon-color": c.sky, "fog-color": c.sky, "atmosphere-blend": 0 });
        }
      } catch (e) { /* older build: no sky */ }
    }

    function applyMode(animate, pose, moveCamera = true) {
      const globe = mode === "globe";
      const three = mode === "3d";
      const rotatable = globe || three;
      try { map.setProjection({ type: globe ? "globe" : "mercator" }); } catch (_) {}
      try {
        map.setMaxBounds(globe ? null : PAK_BOUNDS);
        map.setMinZoom(globe ? 1.35 : 3.4);
      } catch (_) {}
      const globeVis = globe ? "visible" : "none";
      for (const lid of ["graticule", "world-land-fill", "world-land-line"]) {
        if (map.getLayer(lid)) map.setLayoutProperty(lid, "visibility", globeVis);
      }
      if (globe) ensureLandLoaded();
      syncTerrain();
      if (map.getLayer("bg")) {
        map.setPaintProperty("bg", "background-color", globe ? c.ocean : c.sky);
        map.setPaintProperty("prov-fill", "fill-opacity", three ? 0.30 : globe ? 0.38 : 0.56);
      }
      setSky();
      applyLight();
      thinLabels(true);
      for (const h of [map.dragRotate, map.touchPitch]) rotatable ? h.enable() : h.disable();
      rotatable ? map.touchZoomRotate.enableRotation() : map.touchZoomRotate.disableRotation();
      rotatable ? map.keyboard.enableRotation() : map.keyboard.disableRotation();

      if (!moveCamera) return;
      const o = globe
        ? { center: [69.5, 29.0], zoom: Math.min(Math.max(map.getZoom(), 2.0), 3.1), pitch: PITCH_GLOBE, bearing: -8 }
        : three
          ? { pitch: PITCH_3D, bearing: map.getBearing(), zoom: Math.max(map.getZoom(), 4.2) }
          : { pitch: 0, bearing: 0 };
      const camera = pose ? { ...o, ...pose } : o;
      if (animate) ease(camera); else map.jumpTo(camera);
    }

    function paintSelection() {
      if (!map.getLayer("prov-fill")) return;
      map.setPaintProperty("prov-fill", "fill-color", selName === "*" ? c.sel : ["case", ["==", ["get", "shapeName"], selName], c.sel, c.land]);
      const selFilt = selName === "*" ? ["has", "shapeName"] : ["==", ["get", "shapeName"], selName];
      map.setFilter("prov-sel", selFilt);
      if (map.getLayer("prov-sel-glow")) map.setFilter("prov-sel-glow", selFilt);
      for (const l of labels) l.el.classList.toggle("sel", l.name === selName);
    }

    function makeLabels() {
      for (const l of labels) l.marker.remove();
      labels = [];
      const add = (name, lonlat, cls, minZoom) => {
        const el = document.createElement("div");
        el.className = "map-lbl" + (cls ? " " + cls : "");
        el.textContent = name;
        const marker = new maplibregl.Marker({ element: el, anchor: cls === "city" ? "left" : "center", offset: cls === "city" ? [7, 0] : [0, 0] }).setLngLat(lonlat).addTo(map);
        labels.push({ name, el, marker, minZoom: minZoom || 0 });
      };
      for (const [name, a] of Object.entries(opts.areas || {})) {
        if (name === "Pakistan" || name === "Islamabad Capital Territory") continue;
        add(name, a.centre, "", name === "Azad Kashmir" ? 5.2 : 0);
      }
      for (const [name, lon, lat, z] of opts.cities || []) add(name, [lon, lat], "city", z);
      thinLabels(true);
    }

    function thinLabels(force) {
      const z = map.getZoom();
      if (!force && mode === lastLabelMode && Math.abs(z - lastLabelZ) < 0.14) return;
      lastLabelZ = z; lastLabelMode = mode;
      for (const l of labels) {
        const minZ = mode === "globe" ? Math.max(3.1, l.minZoom) : l.minZoom;
        const nextVis = z >= minZ ? "" : "hidden";
        if (l.el.style.visibility !== nextVis) l.el.style.visibility = nextVis;
      }
    }

    const geometryKey = () => `${vmode}|${vmode === "footprints" && psfOn}|${filterKey}`;
    function schedulePolygons() {
      clearTimeout(polyTimer);
      if (vmode !== "towers" && vmode !== "footprints") return;
      const key = geometryKey();
      if (key === polyCacheKey) {
        if (!awaitingGeometry && shownPtsMeta.pending) publishPolygons();
        return;
      }
      const cached = polygonCache.get(key);
      if (cached) { applyPolygons(key, cached); return; }
      shownPtsMeta = { ...shownPtsMeta, pending: true };
      opts.onPolyMeta?.(shownPtsMeta);
      polyTimer = setTimeout(() => rebuildPolySources(key), 70);
    }

    function applyPolygons(key, entry) {
      polyCacheKey = key;
      appliedPolygons = entry;
      awaitingGeometry = true;
      map.getSource("pts-poly").setData(entry.polygons);
      if (entry.halos.features.length || hasHalos) map.getSource("pts-psf").setData(entry.halos);
      hasHalos = entry.halos.features.length > 0;
      shownPtsMeta = { ...entry.meta, pending: true };
      opts.onPolyMeta?.(shownPtsMeta);
    }

    function publishPolygons() {
      awaitingGeometry = false;
      shownPtsMeta = appliedPolygons.meta;
      opts.onPolyMeta?.(shownPtsMeta);
    }

    map.on("render", () => {
      if (awaitingGeometry && polyCacheKey === geometryKey() && map.isSourceLoaded("pts-poly")
        && (!hasHalos || map.isSourceLoaded("pts-psf"))) publishPolygons();
    });

    let hasHalos = false;
    function rebuildPolySources(key) {
      if (!styleReady) return;
      const wantTowers = vmode === "towers";
      const P = rawPoints;
      const matches = P ? opts.matchingRows(activeFilter) : [];

      const total = matches.length;
      let sample = matches;
      let limited = false;
      if (total > MAX_POLY_FEATS) {
        limited = true;
        // Prioritize highest FRP anomalies plus deterministic uniform coverage
        const topK = Math.floor(MAX_POLY_FEATS * 0.35);
        const byFrp = matches.slice().sort((a, b) => (P.frp[b] || 0) - (P.frp[a] || 0));
        const chosen = new Set(byFrp.slice(0, topK));
        const rem = MAX_POLY_FEATS - chosen.size;
        const step = total / Math.max(1, rem);
        for (let k = 0; k < rem; k++) chosen.add(matches[Math.min(total - 1, Math.floor(k * step))]);
        sample = [...chosen];
      }
      const feats = [];
      const psfFeats = [];
      for (const i of sample) {
        const p = P.p[i], lon = P.lon[i], lat = P.lat[i];
        const frp = P.frp[i];
        if (wantTowers) {
          const h = frp == null ? 950 : Math.min(54000, Math.max(1400, Math.sqrt(Math.max(1, frp)) * 2800));
          const radM = p < 2 ? 1250 : 780;
          feats.push({
            type: "Feature",
            geometry: { type: "Polygon", coordinates: hexPolygon(lon, lat, radM) },
            properties: { i, p, h, cx: lon, cy: lat, frp: frp == null ? 0 : frp },
          });
        } else {
          const coords = orientedFootprint(lon, lat, P.scan[i], P.track[i], P.dn[i], p < 2);
          feats.push({
            type: "Feature",
            geometry: { type: "Polygon", coordinates: coords },
            properties: { i, p, cx: lon, cy: lat },
          });
          if (psfOn && p < 2) {
            const psfCoords = orientedFootprint(lon, lat, (P.scan[i] || 1.0) * 2.0, (P.track[i] || 1.0) * 1.0, P.dn[i], true);
            psfFeats.push({
              type: "Feature",
              geometry: { type: "Polygon", coordinates: psfCoords },
              properties: { i, p },
            });
          }
        }
      }
      const entry = {
        polygons: { type: "FeatureCollection", features: feats },
        halos: { type: "FeatureCollection", features: psfFeats },
        meta: { total, shown: sample.length, limited },
      };
      if (polygonCache.size === 4) polygonCache.delete(polygonCache.keys().next().value);
      polygonCache.set(key, entry);
      applyPolygons(key, entry);
    }

    function syncPointFilters() {
      if (vmode !== "points" && vmode !== "density") return;
      const { sats, dn, day } = activeFilter;
      const layers = [
        ["pts-modis", sats.filter(p => p < 2)],
        ["pts-viirs", sats.filter(p => p >= 2)],
      ];
      if (vmode === "density") layers.push(["pts-heat", sats]);
      for (const [id, ids] of layers) {
        const key = `${ids.join(",")}|${dn}|${day}`;
        if (pointLayerFilters.get(id) === key) continue;
        const filter = ["all", ["in", ["get", "p"], ["literal", ids.length ? ids : [-1]]]];
        if (dn !== "DN") filter.push(["==", ["get", "n"], dn === "N" ? 1 : 0]);
        if (day) filter.push(["==", ["get", "d"], day]);
        map.setFilter(id, filter);
        pointLayerFilters.set(id, key);
      }
    }
    function syncLayerVisibility() {
      if (!styleReady || !map.getLayer("pts-viirs")) return;
      const vis = (id, on) => { if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", on ? "visible" : "none"); };
      vis("pts-modis", vmode === "points" || vmode === "density");
      vis("pts-viirs", vmode === "points" || vmode === "density");
      vis("pts-towers", vmode === "towers");
      vis("pts-fp", vmode === "footprints");
      vis("pts-fp-line", vmode === "footprints");
      vis("pts-fp-psf", vmode === "footprints" && psfOn);
      vis("pts-heat", vmode === "density");
      syncPointFilters();

      if (vmode === "density") {
        const zFade = ["interpolate", ["linear"], ["zoom"], 7.5, 0.08, 9.5, 0.92];
        map.setPaintProperty("pts-viirs", "circle-opacity", zFade);
        map.setPaintProperty("pts-modis", "circle-opacity", zFade);
      } else {
        map.setPaintProperty("pts-viirs", "circle-opacity", viirsOpacity);
        map.setPaintProperty("pts-modis", "circle-opacity", 0.55);
      }
      schedulePolygons();
    }

    // Picking: active detection representation first; otherwise province polygon under pointer.
    function activePickLayers() {
      if (vmode === "towers") return ["pts-towers"];
      if (vmode === "footprints") return ["pts-fp"];
      return ["pts-viirs", "pts-modis"];
    }
    function nearest(pt) {
      if (shownPtsMeta.pending && (vmode === "towers" || vmode === "footprints")) return null;
      const fs = map.queryRenderedFeatures([[pt.x - 7, pt.y - 7], [pt.x + 7, pt.y + 7]], { layers: activePickLayers() });
      let best = null, bd = 1e9;
      for (const f of fs) {
        const ll = f.geometry.type === "Point"
          ? f.geometry.coordinates
          : [f.properties.cx, f.properties.cy];
        if (!ll || ll[0] == null) continue;
        const q = map.project(ll), d = (q.x - pt.x) ** 2 + (q.y - pt.y) ** 2;
        if (d < bd) { bd = d; best = f; }
      }
      return best ? best.properties.i : null;
    }

    map.on("click", (e) => {
      if (opts.drawing && opts.drawing()) return;
      if (shownPtsMeta.pending && (vmode === "towers" || vmode === "footprints")) return;
      const i = nearest(e.point);
      if (i != null) { opts.onPick(i); return; }
      const f = map.queryRenderedFeatures(e.point, { layers: ["prov-fill"] })[0];
      if (f && opts.onArea) opts.onArea(f.properties.shapeName);
    });
    let raf = 0;
    map.on("movestart", () => { moving = true; canvas.style.cursor = ""; opts.onHover && opts.onHover(null); });
    map.on("moveend", () => { moving = false; if (fx && map.getTerrain()) fx.refreshElevation(map); });
    map.on("mousemove", (e) => {
      if (lost || moving || (e.originalEvent && e.originalEvent.buttons)) return;
      if (raf) return;
      raf = requestAnimationFrame(() => {
        raf = 0;
        if (lost || moving) return;
        const now = performance.now();
        if (now - lastPickAt < 24) return;
        lastPickAt = now;
        const i = nearest(e.point);
        const curC = i != null ? "pointer" : "";
        if (canvas.style.cursor !== curC) canvas.style.cursor = curC;
        opts.onHover && opts.onHover(i, e.originalEvent);
      });
    });
    map.on("mouseout", () => opts.onHover && opts.onHover(null));
    map.on("dragstart", () => opts.onUser && opts.onUser());
    map.on("zoomstart", (e) => { if (e.originalEvent) opts.onUser && opts.onUser(); });
    map.on("rotate", () => opts.onBearing && opts.onBearing(map.getBearing()));
    map.on("zoom", () => { thinLabels(false); if (mode === "globe") syncTerrain(); });
    map.on("sourcedata", (e) => {
      if (e && e.sourceId === "dem" && e.isSourceLoaded && fx && map.getTerrain()) fx.refreshElevation(map);
    });
    map.on("webglcontextlost", () => { lost = true; if (fx && fx.stopIdle) fx.stopIdle(); opts.onLost && opts.onLost(); });
    map.on("error", (e) => { if (opts.onError && e && e.error) opts.onError(e.error); });

    let pendingPts = null;
    let styleReady = false;
    const queue = [];
    const flush = () => {
      if (styleReady || !map.getSource("pts")) return;
      styleReady = true;
      if (fx && !map.getLayer("seamline-fx")) {
        try { map.addLayer(fx.layer); } catch (e) { /* custom layer unsupported */ }
      }
      applyMode(false, null, false);
      ensureRiversLoaded();
      if (mode === "globe") ensureLandLoaded();
      syncLayerVisibility();
      for (const fn of queue.splice(0)) fn();
    };
    map.on("style.load", flush);
    map.on("load", () => {
      flush();
      makeLabels();
      paintSelection();
      opts.onReady && opts.onReady();
    });
    const whenLoaded = (fn) => { flush(); if (styleReady) fn(); else queue.push(fn); };

    return {
      kind: "gl", exaggeration: TERRAIN_EXAGGERATION, map, fx,
      ready: () => styleReady,
      openingGlobe: () => openingGlobe,
      setIntroMode(m, pose) {
        map.stop();
        openingGlobe = false;
        mode = m;
        whenLoaded(() => applyMode(false, pose));
      },
      setTheme(colors) {
        c = colors;
        if (fx) fx.setTheme(colors, !!colors.dark);
        whenLoaded(() => {
          map.setPaintProperty("bg", "background-color", mode === "globe" ? c.ocean : c.sky);
          map.setPaintProperty("graticule", "line-color", c.line);
          map.setPaintProperty("world-land-fill", "fill-color", c.landDim || c.land);
          map.setPaintProperty("world-land-line", "line-color", c.line);
          map.setPaintProperty("world-rivers", "line-color", c.river);
          map.setPaintProperty("prov-line", "line-color", c.line);
          if (map.getLayer("prov-sel-glow")) map.setPaintProperty("prov-sel-glow", "line-color", c.lineSel);
          map.setPaintProperty("prov-sel", "line-color", c.lineSel);
          map.setPaintProperty("box-fill", "fill-color", c.sel);
          map.setPaintProperty("box-line", "line-color", c.lineSel);
          for (const [k, v] of Object.entries(dotPaint(c))) map.setPaintProperty("pts-viirs", k, v);
          for (const [k, v] of Object.entries(ringPaint(c))) map.setPaintProperty("pts-modis", k, v);
          for (const [k, v] of Object.entries(heatPaint(c))) map.setPaintProperty("pts-heat", k, v);
          map.setPaintProperty("pts-towers", "fill-extrusion-color", colorOf(c));
          map.setPaintProperty("pts-fp", "fill-color", colorOf(c));
          map.setPaintProperty("pts-fp-line", "line-color", colorOf(c));
          map.setPaintProperty("pts-fp-psf", "fill-color", colorOf(c));
          map.setPaintProperty("pts-fp-psf", "fill-outline-color", colorOf(c));
          map.setPaintProperty("pts-sel", "circle-stroke-color", c.ink);
          setSky(); applyLight(); paintSelection();
        });
      },
      setSelection(sel) {
        selName = sel.bbox ? "" : sel.region === "Pakistan" ? "*" : sel.region;
        whenLoaded(() => {
          paintSelection();
          const b = sel.bbox;
          map.getSource("box").setData({
            type: "FeatureCollection",
            features: b ? [{
              type: "Feature", properties: {},
              geometry: { type: "Polygon", coordinates: [[[b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]], [b[0], b[1]]]] },
            }] : [],
          });
        });
      },
      setDate(month) { if (fx) fx.setDate(month); },
      setActive(on) { if (fx) fx.setActive(on); },
      setPoints(P) {
        if (P === rawPoints) return;
        rawPoints = P;
        polyCacheKey = "";
        polygonCache.clear();
        awaitingGeometry = false;
        const feats = [];
        if (P) {
          for (let i = 0; i < P.lon.length; i++) {
            feats.push({
              type: "Feature",
              geometry: { type: "Point", coordinates: [P.lon[i], P.lat[i]] },
              properties: { i, p: P.p[i], n: P.dn[i], d: P.day[i], frp: P.frp ? P.frp[i] : 0 },
            });
          }
        }
        pendingPts = { type: "FeatureCollection", features: feats };
        whenLoaded(() => {
          if (pendingPts) { map.getSource("pts").setData(pendingPts); pendingPts = null; }
          if (fx) fx.setPoints(P, map);
          schedulePolygons();
        });
      },
      setFilter(f) {
        const key = `${f.sats.join(",")}|${f.dn}|${f.day}`;
        if (key === filterKey) return;
        filterKey = key;
        const lightChanged = f.dn !== activeFilter.dn;
        activeFilter = f;
        whenLoaded(() => {
          syncPointFilters();
          if (lightChanged) applyLight();
          if (fx) fx.setFilter(f);
          schedulePolygons();
        });
      },
      setViewMode(vm) {
        const next = ["points", "towers", "footprints", "density"].includes(vm) ? vm : "points";
        if (next === vmode) return;
        vmode = next;
        whenLoaded(() => syncLayerVisibility());
      },
      viewMode: () => vmode,
      viewMeta: () => shownPtsMeta,
      setPsf(on) {
        if (psfOn === !!on) return;
        psfOn = !!on;
        if (fx) fx.setPsf(psfOn);
        whenLoaded(syncLayerVisibility);
      },
      setOrbit(on) { if (fx) fx.setOrbit(on); },
      setSeam(on) { if (fx) fx.setSeam(on); },
      setPlayback(day, playing) { if (fx) fx.setPlayback(day, playing); },
      satBadges: () => (fx ? fx.badges() : []),
      select(i) {
        if (fx) fx.select(i);
        whenLoaded(() => map.setFilter("pts-sel", ["==", ["get", "i"], i == null ? -1 : i]));
      },
      fit(b, animate) {
        whenLoaded(() => {
          const padding = { top: 58, bottom: 32, left: 36, right: 56 };
          const pitch = mode === "globe" ? PITCH_GLOBE : mode === "3d" ? PITCH_3D : 0;
          const bearing = mode === "2d" ? 0 : map.getBearing();
          const duration = typeof animate === "number" ? animate : animate ? dur() : 0;
          try { map.fitBounds([[b[0], b[1]], [b[2], b[3]]], { padding, pitch, bearing, maxZoom: 9.5, duration, essential: true }); }
          catch (e) { map.jumpTo({ center: [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2], zoom: 5 }); }
        });
      },
      flyTo(lon, lat) { ease({ center: [lon, lat], zoom: Math.max(map.getZoom(), 8.2) }); },
      flyPose(pose) {
        if (!pose) return;
        const doMove = () => {
          const cam = {};
          if (pose.center) cam.center = pose.center;
          if (pose.zoom != null) cam.zoom = pose.zoom;
          if (pose.pitch != null) cam.pitch = pose.pitch;
          if (pose.bearing != null) cam.bearing = pose.bearing;
          if (Object.keys(cam).length) ease(cam);
        };
        if (pose.mode && pose.mode !== mode) {
          mode = pose.mode;
          whenLoaded(() => { applyMode(false); doMove(); });
        } else {
          whenLoaded(doMove);
        }
      },
      camera(act) {
        if (act === "zoom-in") map.zoomIn({ duration: dur(), essential: true });
        else if (act === "zoom-out") map.zoomOut({ duration: dur(), essential: true });
        else if (act === "rot-l") ease({ bearing: map.getBearing() - 22.5 });
        else if (act === "rot-r") ease({ bearing: map.getBearing() + 22.5 });
        else if (act === "tilt-up") ease({ pitch: Math.min(75, map.getPitch() + 10) });
        else if (act === "tilt-dn") ease({ pitch: Math.max(0, map.getPitch() - 10) });
        else if (act === "north") ease({ bearing: 0 });
      },
      setMode(m, animate) {
        mode = ["globe", "3d", "2d"].includes(m) ? m : "3d";
        whenLoaded(() => applyMode(animate !== false));
      },
      mode: () => mode,
      project(lon, lat) { const p = map.project([lon, lat]); return [p.x, p.y]; },
      unproject(x, y) { const l = map.unproject([x, y]); return [l.lng, l.lat]; },
      setInteractive(on) {
        for (const h of [map.dragPan, map.boxZoom, map.doubleClickZoom, map.scrollZoom]) on ? h.enable() : h.disable();
        if (mode !== "2d") on ? map.dragRotate.enable() : map.dragRotate.disable();
      },
      setOverlay(url, wsen, opacity) {
        whenLoaded(() => {
          if (map.getLayer("cov")) map.removeLayer("cov");
          if (map.getSource("cov")) map.removeSource("cov");
          if (!url) return;
          const [w, s, e, n] = wsen;
          map.addSource("cov", { type: "image", url, coordinates: [[w, n], [e, n], [e, s], [w, s]] });
          map.addLayer({ id: "cov", type: "raster", source: "cov", paint: { "raster-opacity": opacity == null ? 0.8 : opacity, "raster-resampling": "nearest", "raster-fade-duration": 0 } }, "prov-line");
        });
      },
      whenIdle(cb) {
        if (!cb) return;
        if (map.loaded() && !map.isMoving()) { cb(); return; }
        let done = false;
        const finish = () => { if (done) return; done = true; clearTimeout(timer); cb(); };
        const timer = setTimeout(finish, 900);
        map.once("idle", finish);
        map.triggerRepaint();
      },
      resize() { try { map.resize(); } catch (e) { /* not visible yet */ } },
      png() { return canvas; },
      bearing: () => map.getBearing(),
      focus() { canvas.focus(); },
      destroy() { clearTimeout(polyTimer); try { if (fx && fx.stopIdle) fx.stopIdle(); map.remove(); } catch (e) { /* already gone */ } },
    };
  }

  window.SeamGL = { available, create, TERRAIN_EXAGGERATION };
})();
