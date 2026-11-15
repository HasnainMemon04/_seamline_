/* Native orbital boot. The live workspace prepares and paints behind its cover. */
(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const intro = $("satellite-intro"), button = $("intro-skip"), status = $("intro-status");
  if (!intro) return;

  const query = new URLSearchParams(location.search);
  const seenKey = "seamline-native-intro-v1";
  const minIntroMs = 2700, maxIntroMs = 7200, descentMs = 1600;
  const mapWorkspace = S => S.UI.ws === "overview" || S.UI.ws === "explore";
  const full = () => window.Seam ? Seam.motionMode() === "full"
    : !matchMedia("(prefers-reduced-motion: reduce)").matches && !["off", "reduced"].includes(document.documentElement.dataset.motion);
  let session = null, frame = 0, fade = 0, mesh = null;
  let seen = false;
  try { seen = sessionStorage.getItem(seenKey) === "seen"; } catch (_) { /* storage unavailable */ }
  const coldScene = () => !!session && !session.manual && window.Seam?.UI.ws === "overview"
    && !query.has("map") && !query.has("basemap") && full();

  function drawSpacecraft(now) {
    if (!mesh) {
      const model = window.SeamSatelliteModels?.models.get("Terra");
      if (!model) return;
      const canvas = document.createElement("canvas");
      canvas.width = 720; canvas.height = 352;
      const context = canvas.getContext("2d");
      if (!context) return;
      $("intro-model").appendChild(canvas);
      const vertices = model.vertices, coords = new Float32Array(vertices.length / 11 * 3);
      const faces = [];
      for (let i = 0; i < model.indices.length; i += 3) {
        const a = model.indices[i], row = a * 11;
        const rgb = [3, 4, 5].map(channel => Math.round(vertices[row + channel] * 255));
        faces.push({ a: a * 3, b: model.indices[i + 1] * 3, c: model.indices[i + 2] * 3, depth: 0, color: `rgb(${rgb.join(",")})` });
      }
      mesh = { canvas, context, vertices, coords, faces };
    }
    const { canvas, context, vertices, coords, faces } = mesh;
    const angle = 0.35 + (now - session.started) * 0.00017;
    const cs = Math.cos(angle), sn = Math.sin(angle);
    for (let i = 0, j = 0; i < vertices.length; i += 11, j += 3) {
      const x = vertices[i], y = vertices[i + 1], z = vertices[i + 2];
      const yy = x * sn + y * cs;
      coords[j] = 360 + (x * cs - y * sn) * 192;
      coords[j + 1] = 176 + yy * 72 - z * 192;
      coords[j + 2] = z + yy * 0.4;
    }
    for (const f of faces) f.depth = coords[f.a + 2] + coords[f.b + 2] + coords[f.c + 2];
    faces.sort((a, b) => a.depth - b.depth);
    context.clearRect(0, 0, canvas.width, canvas.height);
    for (const { a, b, c, color } of faces) {
      context.beginPath();
      context.moveTo(coords[a], coords[a + 1]);
      context.lineTo(coords[b], coords[b + 1]);
      context.lineTo(coords[c], coords[c + 1]);
      context.closePath();
      context.fillStyle = color;
      context.fill();
    }
  }

  function caption(text) {
    if (status.textContent !== text) status.textContent = text;
  }

  function startScene(s, engine) {
    const map = engine.map;
    const { lng, lat } = map.getCenter();
    s.scene = {
      engine, mode: session.manual ? engine.mode() : Seam.UI.mode,
      orbit: engine.fx?.orbitActive(), seam: engine.fx?.seamActive(),
      pose: { center: [lng, lat], zoom: map.getZoom(), pitch: map.getPitch(), bearing: map.getBearing(), padding: map.getPadding() },
    };
    const [west, south, east, north] = SeamMap.bounds();
    if (!engine.openingGlobe()) {
      engine.setIntroMode("globe", { center: [(west + east) / 2, (south + north) / 2], zoom: 1.8, pitch: 0, bearing: -8, padding: { top: 0, right: 0, bottom: 0, left: 0 } });
    }
    engine.fx?.setSeam(false);
    engine.fx?.setOrbit(false);
    window.SeamBasemap?.preview("satellite");
  }

  function freezeScene(s) {
    if (!intro.classList.contains("has-live-earth")) return;
    const source = s.scene.engine.map.getCanvas();
    const box = source.getBoundingClientRect();
    const image = document.createElement("canvas");
    image.width = source.width; image.height = source.height;
    const context = image.getContext("2d");
    if (!context || !image.width || !image.height) return;
    context.drawImage(source, 0, 0);
    image.className = "intro-landing-frame";
    image.setAttribute("aria-hidden", "true");
    Object.assign(image.style, { left: `${box.left}px`, top: `${box.top}px`, width: `${box.width}px`, height: `${box.height}px` });
    intro.prepend(image);
    s.snapshot = image;
  }

  function restoreScene(s, showSnapshot, landRegional = false) {
    const scene = s.scene;
    if (!scene || s.restored) return;
    s.restored = true;
    if (scene.engine === window.SeamMap?.engine()) {
      if (showSnapshot) freezeScene(s);
      const regional = landRegional && s.regional;
      scene.engine.setIntroMode(regional ? "3d" : scene.mode, s.manual && !regional ? scene.pose : undefined);
      if (!s.manual || regional) SeamMap.fitAfterIntro(regional);
      if (!regional) scene.engine.fx?.setOrbit(scene.orbit);
      scene.engine.fx?.setSeam(scene.seam);
      Seam.emit("map-filter");
    } else {
      intro.classList.remove("has-live-earth");
    }
    window.SeamBasemap?.preview(null);
  }

  function finish(immediate = false) {
    const s = session;
    if (!s) return;
    restoreScene(s, false, !immediate);
    const engine = window.SeamMap?.engine();
    if (!s.scene && engine?.openingGlobe?.()) {
      engine.setIntroMode(Seam.UI.mode);
      SeamMap.fitAfterIntro();
      window.SeamBasemap?.preview(null);
    }
    session = null;
    if (s.regional) $("play-transition-btn")?.setAttribute("aria-pressed", "false");
    cancelAnimationFrame(frame);
    document.documentElement.dataset.nativeBoot = "off";
    for (const [node, inert] of s.background) node.inert = inert;
    try { sessionStorage.setItem(seenKey, "seen"); } catch (_) { /* storage unavailable */ }
    seen = true;
    const complete = () => {
      s.snapshot?.remove();
      intro.hidden = true;
      intro.classList.remove("has-live-earth", "is-leaving");
      fade = 0;
    };
    if (immediate || !full()) complete();
    else {
      intro.classList.add("is-leaving");
      document.body.classList.add("instrument-dock");
      setTimeout(() => document.body.classList.remove("instrument-dock"), 850);
      fade = setTimeout(complete, 240);
    }
    const focus = s.previous?.getClientRects().length && s.previous !== document.body ? s.previous : $("main");
    if (intro.contains(document.activeElement)) focus?.focus({ preventScroll: true });
    window.dispatchEvent(new CustomEvent("seam-intro-dismissed", { detail: { skipped: immediate, native: true, manual: s.manual, ready: s.ready } }));
    // Keep the scan effect available after the handoff without competing with the flight.
    if (!immediate && !s.manual && s.ready && s.scene) {
      setTimeout(() => {
        if (!session && full() && !document.hidden && mapWorkspace(Seam)) Seam.emit("scan-reveal-request", { temporary: true });
      }, 850);
    }
  }

  function tick(now) {
    const s = session;
    if (!s || document.hidden) return;
    if (!full()) { finish(true); return; }
    const elapsed = now - s.started;
    const S = window.Seam, M = window.SeamMap, engine = M?.engine();
    const onMap = S && mapWorkspace(S);
    const eligible = onMap && (s.manual || coldScene());
    if (!s.scene && eligible && engine?.kind === "gl" && engine.ready() && elapsed < maxIntroMs - descentMs - 1200) {
      startScene(s, engine);
    }
    if (s.scene && !s.restored) {
      const map = s.scene.engine.map;
      if (engine !== s.scene.engine || !onMap) restoreScene(s, false);
      else if (!s.descent && map.loaded()) {
        intro.classList.add("has-live-earth");
        document.documentElement.dataset.nativeBoot = "on";
        s.scene.engine.fx?.setOrbit(true);
        s.descent = now + 220;
      } else if (s.descent && !s.inFlight && now >= s.descent) {
        s.scene.engine.fit(M.bounds(), descentMs);
        s.inFlight = now;
      } else if (s.inFlight && now - s.inFlight >= descentMs && !map.isMoving()) {
        restoreScene(s, true, true);
        s.landed = now;
      }
    }
    const landed = !s.scene || (s.restored && (!s.landed || now - s.landed >= 32));
    const mapReady = !onMap || (M?.isInitialViewReady() && S.dailySettled() && !M.mapLibraryPending()
      && (engine?.kind === "canvas" || (engine?.ready() && engine.map.loaded() && !engine.map.isMoving())));
    const contentReady = window.SeamShowcase?.ready() && (S?.UI.ws !== "calendar" || S.UI.sub !== "days" || S.dailySettled());
    s.ready = !!(landed && S?.result() && mapReady && contentReady);
    if (elapsed >= minIntroMs && s.ready) { finish(); return; }
    if (elapsed >= maxIntroMs) { finish(); return; }
    if (elapsed >= minIntroMs && !s.ready) caption("Preparing the workspace…");
    drawSpacecraft(now);
    frame = requestAnimationFrame(tick);
  }

  function open(manual = true, regional = false) {
    if (session || fade) return;
    const background = [...document.querySelectorAll("#top,#main,#navigation-drawer,#navigation-shade")].map(node => [node, node.inert]);
    session = { manual, regional, started: performance.now(), previous: document.activeElement, background };
    if (regional) $("play-transition-btn")?.setAttribute("aria-pressed", "true");
    if (!full()) { finish(true); return; }
    intro.hidden = false;
    intro.classList.add("is-native");
    caption("Loading the observation record…");
    for (const [node] of background) node.inert = true;
    button.focus({ preventScroll: true });
    frame = requestAnimationFrame(tick);
  }

  button.addEventListener("click", () => finish(true));
  intro.addEventListener("keydown", e => {
    if (e.key === "Escape") { e.preventDefault(); finish(true); }
    if (e.key === "Tab") { e.preventDefault(); button.focus(); }
  });
  document.addEventListener("visibilitychange", () => {
    cancelAnimationFrame(frame);
    if (!document.hidden && session) frame = requestAnimationFrame(tick);
  });
  window.SeamIntro = {
    open, dismiss: finish, native: true, isOpen: () => !!session,
    coldScene,
    ownsCamera: () => !!session && !session.restored && (!!session.scene || !!window.SeamMap?.engine()?.openingGlobe?.()),
  };
  document.addEventListener("DOMContentLoaded", () => {
    if (query.get("intro") === "1" || (!seen && query.get("intro") !== "0")) open(false);
  });
})();
