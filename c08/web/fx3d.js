// Seamline WebGL2 Visual Effects & Orbital Constellation Engine (works seamlessly in Globe and Mercator views).
// Everything rendered here is offline, deterministic, and strictly decoupled from statistical counts H.
// Orbits depict schematic sun-synchronous inclination (98.2 deg MODIS, 98.7 deg VIIRS) and swath widths
// (2,330 km vs 3,040 km) for physical intuition; they are not live TLE telemetry or ground exposure.
(function () {
  "use strict";
  const D2R = Math.PI / 180;
  const EARTH_R_M = 6371008.8;

  // Schematic constellation synchronized cleanly to South Asia overpasses:
  // Morning AM ~10:30 LST (Terra); Afternoon PM ~13:30 LST cluster (Aqua MODIS, S-NPP, NOAA-20 -50m, NOAA-21 +25m).
  const SATELLITE_ORBITS = [
    { key: "Terra", label: "Terra MODIS", short: "Terra", kind: "MODIS", swathKm: 2330, altKm: 705, visAltKm: 560, inclDeg: 98.2,
      lst: "10:49 -> 09:40 LST", note: "Morning sun-synch orbit drifted earlier; 2,330 km swath leaves ~350 km equatorial gap.",
      raanDeg: 73.8, phase0: 19.0, speedDeg: 0.70, pIdx: 0 },
    { key: "Aqua", label: "Aqua MODIS", short: "Aqua", kind: "MODIS", swathKm: 2330, altKm: 705, visAltKm: 585, inclDeg: 98.2,
      lst: "13:16 -> 14:38 LST", note: "Afternoon orbit drifting later (~14:38 LST by 2025); 2,330 km MODIS swath.",
      raanDeg: 69.5, phase0: 14.5, speedDeg: 0.70, pIdx: 1 },
    { key: "SNPP", label: "S-NPP VIIRS", short: "S-NPP", kind: "VIIRS", swathKm: 3040, altKm: 824, visAltKm: 690, inclDeg: 98.7,
      lst: "13:30 LST (ended 2 Nov 2026)", note: "Baseline reference satellite; ended 2 Nov 2026 15:40 UTC. 3,040 km swath (3:1->2:1->1:1 aggregation).",
      raanDeg: 76.2, phase0: 17.5, speedDeg: 0.65, pIdx: 2 },
    { key: "NOAA20", label: "NOAA-20 VIIRS", short: "NOAA-20", kind: "VIIRS", swathKm: 3040, altKm: 834, visAltKm: 730, inclDeg: 98.7,
      lst: "13:30 LST (-50 min)", note: "Offset ~50 min ahead in 13:30 plane; carries Punjab Nov 2026+ continuity (P04 G03: 5.1% WAPE).",
      raanDeg: 80.2, phase0: 22.0, speedDeg: 0.65, pIdx: 3 },
    { key: "NOAA21", label: "NOAA-21 VIIRS", short: "NOAA-21", kind: "VIIRS", swathKm: 3040, altKm: 834, visAltKm: 765, inclDeg: 98.7,
      lst: "13:30 LST (separate)", note: "JPSS-2 (VJ214IMG); shown separately in raw units outside calibrated H.",
      raanDeg: 82.8, phase0: 11.5, speedDeg: 0.65, pIdx: 4 },
  ];

  function mercX(lon) { return (lon + 180) / 360; }
  function mercY(lat) {
    const s = Math.max(-0.9999, Math.min(0.9999, Math.sin(lat * D2R)));
    return 0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI);
  }
  function hexRgb(hex) {
    const h = String(hex || "#0e6b6f").trim();
    if (h.startsWith("#")) {
      const s = h.slice(1);
      const n = s.length === 3 ? s.split("").map((c) => c + c).join("") : s;
      return [parseInt(n.slice(0, 2), 16) / 255, parseInt(n.slice(2, 4), 16) / 255, parseInt(n.slice(4, 6), 16) / 255];
    }
    const m = h.match(/[\d.]+/g);
    return m ? [Number(m[0]) / 255, Number(m[1]) / 255, Number(m[2]) / 255] : [0.05, 0.42, 0.44];
  }

  // Computes spherical orbital point and local ENU heading at ascending phase angle thetaRad.
  function orbitPoint(sat, thetaDeg, out) {
    const th = thetaDeg * D2R;
    const inc = sat.inclDeg * D2R;
    // Anchor phase 0 near equatorial crossing around raanDeg, ascending northward across Pakistan (~22..36 N).
    const raan = sat.raanDeg * D2R;
    const cx = Math.cos(th), sy = Math.sin(th);
    const cosI = Math.cos(inc), sinI = Math.sin(inc);
    const cosO = Math.cos(raan), sinO = Math.sin(raan);

    const x1 = cx, y1 = sy * cosI, z1 = sy * sinI;
    const X = x1 * cosO - y1 * sinO;
    const Y = x1 * sinO + y1 * cosO;
    const Z = z1;

    // Analytic tangent dP/dtheta
    const dx1 = -sy, dy1 = cx * cosI, dz1 = cx * sinI;
    const dX = dx1 * cosO - dy1 * sinO;
    const dY = dx1 * sinO + dy1 * cosO;
    const dZ = dz1;

    const lat = Math.asin(Math.max(-0.985, Math.min(0.985, Z))) / D2R;
    const lon = Math.atan2(Y, X) / D2R;
    // Project tangent vector onto local East-North basis on unit sphere
    const lonR = lon * D2R, latR = lat * D2R;
    const ex = -Math.sin(lonR), ey = Math.cos(lonR);
    const nx = -Math.sin(latR) * Math.cos(lonR), ny = -Math.sin(latR) * Math.sin(lonR), nz = Math.cos(latR);
    const fE = dX * ex + dY * ey;
    const fN = dX * nx + dY * ny + dZ * nz;
    const mag = Math.hypot(fE, fN) || 1;
    const fwdE = fE / mag, fwdN = fN / mag;
    if (out) {
      out.lon = lon; out.lat = lat; out.fwdE = fwdE; out.fwdN = fwdN;
      out.rightE = fwdN; out.rightN = -fwdE;
      return out;
    }
    return { lon, lat, fwdE, fwdN, rightE: fwdN, rightN: -fwdE };
  }

  // Converts local East-North metric displacements around (lon, lat) into (mx, my).
  function enuOffsetToMerc(lon, lat, eastM, northM, out) {
    const cosLat = Math.max(0.18, Math.cos(lat * D2R));
    const dLon = eastM / (111320 * cosLat);
    const dLat = northM / 110574;
    const lat2 = Math.max(-84, Math.min(84, lat + dLat));
    let lon2 = lon + dLon;
    while (lon2 > 180) lon2 -= 360;
    while (lon2 < -180) lon2 += 360;
    const mx = mercX(lon2), my = mercY(lat2);
    if (out) { out[0] = mx; out[1] = my; return out; }
    return [mx, my];
  }

  function compileShader(gl, type, src) {
    const s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
      const log = gl.getShaderInfoLog(s);
      gl.deleteShader(s);
      throw new Error("SeamFX shader compile error: " + log);
    }
    return s;
  }

  function linkProgram(gl, vsSrc, fsSrc) {
    const vs = compileShader(gl, gl.VERTEX_SHADER, vsSrc);
    const fs = compileShader(gl, gl.FRAGMENT_SHADER, fsSrc);
    const p = gl.createProgram();
    gl.attachShader(p, vs);
    gl.attachShader(p, fs);
    gl.linkProgram(p);
    gl.deleteShader(vs);
    gl.deleteShader(fs);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) {
      const log = gl.getProgramInfoLog(p);
      gl.deleteProgram(p);
      throw new Error("SeamFX program link error: " + log);
    }
    return p;
  }

  function makeWriter(initCap) {
    let buf = new Float32Array(initCap);
    let len = 0;
    function ensure(need) {
      if (len + need <= buf.length) return;
      let nCap = buf.length * 2;
      while (nCap < len + need) nCap *= 2;
      const next = new Float32Array(nCap);
      next.set(buf.subarray(0, len));
      buf = next;
    }
    return {
      reset() { len = 0; },
      length() { return len; },
      push10(a0, a1, a2, a3, a4, a5, a6, a7, a8, a9) {
        ensure(10);
        buf[len++] = a0; buf[len++] = a1; buf[len++] = a2; buf[len++] = a3; buf[len++] = a4;
        buf[len++] = a5; buf[len++] = a6; buf[len++] = a7; buf[len++] = a8; buf[len++] = a9;
      },
      push11(a0, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10) {
        ensure(11);
        buf[len++] = a0; buf[len++] = a1; buf[len++] = a2; buf[len++] = a3; buf[len++] = a4; buf[len++] = a5;
        buf[len++] = a6; buf[len++] = a7; buf[len++] = a8; buf[len++] = a9; buf[len++] = a10;
      },
      view() { return buf.subarray(0, len); },
    };
  }

  // Appends 3D triangle into a preallocated Float32 writer (zero heap allocation per vertex).
  function pushTriW(w, ax, ay, az, bx, by, bz, cx, cy, cz, r, g, b, a, nx, ny, nz, lit) {
    w.push11(ax, ay, az, r, g, b, a, nx, ny, nz, lit);
    w.push11(bx, by, bz, r, g, b, a, nx, ny, nz, lit);
    w.push11(cx, cy, cz, r, g, b, a, nx, ny, nz, lit);
  }

  function pushBoxW(w, cur, altM, sc, cx, cy, cz, sx, sy, sz, rgba, lit, tmpA, tmpB, tmpC, tmpD, tmpE, tmpF, tmpG, tmpH) {
    const hx = sx * 0.5, hy = sy * 0.5, hz = sz * 0.5;
    const fillCorner = (dx, dy, dz, out) => {
      const fx = cx + dx, ry = cy + dy;
      const east = fx * cur.fwdE + ry * cur.rightE;
      const north = fx * cur.fwdN + ry * cur.rightN;
      enuOffsetToMerc(cur.lon, cur.lat, east, north, out);
      out[2] = altM + cz + dz;
    };
    fillCorner(-hx, -hy, -hz, tmpA); fillCorner(hx, -hy, -hz, tmpB); fillCorner(hx, hy, -hz, tmpC); fillCorner(-hx, hy, -hz, tmpD);
    fillCorner(-hx, -hy, hz, tmpE); fillCorner(hx, -hy, hz, tmpF); fillCorner(hx, hy, hz, tmpG); fillCorner(-hx, hy, hz, tmpH);
    const quad = (q0, q1, q2, q3, nx, ny, nz, kCol) => {
      const r = rgba[0] * kCol, g = rgba[1] * kCol, b = rgba[2] * kCol, a = rgba[3];
      pushTriW(w, q0[0], q0[1], q0[2], q1[0], q1[1], q1[2], q2[0], q2[1], q2[2], r, g, b, a, nx, ny, nz, lit);
      pushTriW(w, q0[0], q0[1], q0[2], q2[0], q2[1], q2[2], q3[0], q3[1], q3[2], r, g, b, a, nx, ny, nz, lit);
    };
    quad(tmpE, tmpF, tmpG, tmpH, 0, 0, 1, 1.18); // top
    quad(tmpA, tmpD, tmpC, tmpB, 0, 0, -1, 0.72); // bottom (nadir)
    quad(tmpB, tmpC, tmpG, tmpF, 1, 0, 0, 1.0); // forward
    quad(tmpA, tmpE, tmpH, tmpD, -1, 0, 0, 0.72); // aft
    quad(tmpD, tmpH, tmpG, tmpC, 0, 1, 0, 1.0); // right
    quad(tmpA, tmpB, tmpF, tmpE, 0, -1, 0, 0.72); // left
  }

  function create(opts) {
    let map = null, gl = null, programs = {};
    let vboSolid = null, vboTrans = null, vboLine = null, vboPulse = null;
    let vao = null;
    let repaintTimer = 0, lastRenderMs = 16, moveEndHandler = null;

    let colors = opts.colors;
    let isDark = !!opts.isDark;
    let motionFn = opts.motion || (() => "full");
    let modeFn = opts.mode || (() => "3d");
    let dnFilter = "DN";
    let satFilter = [0, 1, 2, 3, 4];
    let orbitOn = false, seamOn = false, psfOn = false;
    let playDay = 0, isPlaying = false, monthStr = null;
    let pickedIdx = null;
    let pointsData = null; // { lon, lat, mx, my, elev, p, dn, day }
    let pointsVer = 0, elevVer = 0, filterKey = "0,1,2,3,4|DN";
    let satScreenBadges = [];
    let lastOrbitKey = "", lastPulseKey = "", hadBadges = false, lastTickAt = 0;

    const startTime = performance.now();
    let animPhaseDeg = 0, lastFrameTime = startTime; // elapsed animation seconds, never wrapped
    let activeView = true;
    let drawTracks=true,drawSwaths=true,scanReveal=false,scanProgress=0,scanBounds=[0,1];
    const modelBuffers = new Map();
    const modelsReady = () => { lastOrbitKey = ""; if (map) map.triggerRepaint(); };

    // Persistent scratch buffers (zero per-frame JS/TypedArray GC allocations)
    const solidW = makeWriter(16384);
    const transW = makeWriter(8192);
    const lineW = makeWriter(16384);
    const pulseW = makeWriter(8192 * 6);
    const corners = [[-1, -1], [1, -1], [1, 1], [-1, -1], [1, 1], [-1, 1]];
    const opScratch = {}, curScratch = {};
    const m0 = [0, 0, 0], m1 = [0, 0, 0], m2 = [0, 0, 0], m3 = [0, 0, 0];
    const m4 = [0, 0, 0], m5 = [0, 0, 0], m6 = [0, 0, 0], m7 = [0, 0, 0];
    const gA = [0, 0], gB = [0, 0], gC = [0, 0], gD = [0, 0];
    const lA = [0, 0], lB = [0, 0], rA = [0, 0], rB = [0, 0], mlA = [0, 0], mrA = [0, 0], mlB = [0, 0], mrB = [0, 0];

    function locCache(prog) {
      if (!prog._loc) prog._loc = { u: Object.create(null), a: Object.create(null) };
      return prog._loc;
    }
    function uLoc(glCtx, prog, name) {
      const c = locCache(prog).u;
      if (!(name in c)) c[name] = glCtx.getUniformLocation(prog, name);
      return c[name];
    }
    function aLoc(glCtx, prog, name) {
      const c = locCache(prog).a;
      if (!(name in c)) c[name] = glCtx.getAttribLocation(prog, name);
      return c[name];
    }

    function clearRepaintTimer() {
      if (repaintTimer) { clearTimeout(repaintTimer); repaintTimer = 0; }
    }
    function scheduleRepaint(frameMs) {
      if (repaintTimer || !map || document.hidden || !activeView) return;
      // Adapt cadence to actual frame cost so animations stay smooth on fast GPUs
      // without queuing or starving input on slower software/integrated GPUs.
      const cost = Number.isFinite(frameMs) ? frameMs : lastRenderMs;
      if(cost<8){map.triggerRepaint();return;}
      const delay = Math.max(16, Math.min(100, Math.round(cost * 1.2)));
      repaintTimer = setTimeout(() => {
        repaintTimer = 0;
        if (map && !document.hidden && !(map.isMoving && map.isMoving())) map.triggerRepaint();
      }, delay);
    }

    function project3d(lon, lat, altM, pd, cssW, cssH, variantName) {
      if (!pd || !pd.mainMatrix) return { sx: -999, sy: -999, visible: false };
      const mx = mercX(lon), my = mercY(lat);
      const cLatMerc = Math.max(0.05, Math.cos(lat * D2R));
      const mercZ = altM / (40075016.6856 * cLatMerc);
      const mul4 = (m, x, y, z, w) => [
        m[0] * x + m[4] * y + m[8] * z + m[12] * w,
        m[1] * x + m[5] * y + m[9] * z + m[13] * w,
        m[2] * x + m[6] * y + m[10] * z + m[14] * w,
        m[3] * x + m[7] * y + m[11] * z + m[15] * w,
      ];
      let clip = null;
      if (variantName && variantName.includes("globe") && pd.clippingPlane) {
        const spX = Math.sin(mx * 2 * Math.PI + Math.PI);
        const latR = 2 * Math.atan(Math.exp(Math.PI - my * 2 * Math.PI)) - Math.PI * 0.5;
        const cLat = Math.cos(latR);
        const sx0 = spX * cLat, sy0 = Math.sin(latR), sz0 = Math.cos(mx * 2 * Math.PI + Math.PI) * cLat;
        const scaleR = 1 + altM / EARTH_R_M;
        const ex = sx0 * scaleR, ey = sy0 * scaleR, ez = sz0 * scaleR;
        const cp = pd.clippingPlane;
        const front = ex * cp[0] + ey * cp[1] + ez * cp[2] + cp[3];
        if ((pd.projectionTransition || 0) > 0.25 && front < -0.18) {
          return { sx: -999, sy: -999, visible: false };
        }
        const gClip = mul4(pd.mainMatrix, ex, ey, ez, 1);
        const tr = pd.projectionTransition == null ? 1 : pd.projectionTransition;
        if (tr < 0.999 && pd.fallbackMatrix) {
          const fClip = mul4(pd.fallbackMatrix, mx, my, mercZ, 1);
          clip = [0, 1, 2, 3].map((k) => fClip[k] + (gClip[k] - fClip[k]) * tr);
        } else {
          clip = gClip;
        }
      } else {
        clip = mul4(pd.mainMatrix, mx, my, mercZ, 1);
      }
      if (!clip || clip[3] <= 0.0001) return { sx: -999, sy: -999, visible: false };
      const ndcX = clip[0] / clip[3], ndcY = clip[1] / clip[3];
      const sx = (ndcX * 0.5 + 0.5) * cssW;
      const sy = (0.5 - ndcY * 0.5) * cssH;
      const visible = sx >= 16 && sx <= cssW - 108 && sy >= 92 && sy <= cssH - 88;
      return { sx, sy, visible };
    }

    function setUniforms(glCtx, prog, options) {
      const pd = options.defaultProjectionData;
      if (!pd) return;
      glCtx.uniformMatrix4fv(uLoc(glCtx, prog, "u_projection_matrix"), false, pd.mainMatrix);
      const ufb = uLoc(glCtx, prog, "u_projection_fallback_matrix");
      if (ufb && pd.fallbackMatrix) glCtx.uniformMatrix4fv(ufb, false, pd.fallbackMatrix);
      const utm = uLoc(glCtx, prog, "u_projection_tile_mercator_coords");
      if (utm && pd.tileMercatorCoords) glCtx.uniform4fv(utm, pd.tileMercatorCoords);
      const ucp = uLoc(glCtx, prog, "u_projection_clipping_plane");
      if (ucp && pd.clippingPlane) glCtx.uniform4fv(ucp, pd.clippingPlane);
      const upt = uLoc(glCtx, prog, "u_projection_transition");
      if (upt != null) glCtx.uniform1f(upt, pd.projectionTransition || 0);
    }

    const WORLD_PROJ_GLSL = `
      float mercZFromMeters(float posY, float altM) {
        float yRad = 3.14159265359 - posY * 6.28318530718;
        float cosLat = clamp(2.0 / (exp(yRad) + exp(-yRad)), 0.05, 1.0);
        return altM / (40075016.6856 * cosLat);
      }
      vec4 projectSeamWorld(vec2 pos, float altM) {
        #ifdef GLOBE
          vec3 sp = projectToSphere(pos, pos);
          vec3 ep = sp * (1.0 + altM / GLOBE_RADIUS);
          vec4 gPos = u_projection_matrix * vec4(ep, 1.0);
          if (u_projection_transition > 0.999) return gPos;
          vec4 fPos = u_projection_fallback_matrix * vec4(pos, mercZFromMeters(pos.y, altM), 1.0);
          return mix(fPos, gPos, u_projection_transition);
        #else
          return u_projection_matrix * vec4(pos, mercZFromMeters(pos.y, altM), 1.0);
        #endif
      }`;

    function getMeshProg(gl, shaderData) {
      const key = "mesh_" + shaderData.variantName;
      if (programs[key]) return programs[key];
      const vs = `#version 300 es
        ${shaderData.define || ""}
        ${shaderData.vertexShaderPrelude}
        ${WORLD_PROJ_GLSL}
        uniform float u_earth_occlude;
        uniform float u_model;
        uniform vec4 u_pose; // center Mercator xy, altitude metres, visible model width metres
        uniform vec2 u_heading; // along-track east/north
        in vec2 a_pos;
        in float a_alt;
        in vec4 a_color;
        in vec3 a_norm;
        in float a_lit;
        out vec4 v_color;
        out vec3 v_norm;
        out float v_lit;
        out float v_vis;
        void main() {
          vec2 pos = a_pos; float alt = a_alt;
          vec3 normal = a_norm;
          if (u_model > 0.5) {
            vec2 en = vec2(a_pos.x*u_heading.x + a_pos.y*u_heading.y, a_pos.x*u_heading.y - a_pos.y*u_heading.x) * u_pose.w;
            float lat = 2.0*atan(exp(3.14159265359-u_pose.y*6.28318530718))-1.57079632679;
            pos = u_pose.xy + vec2(en.x, -en.y) / (40075016.6856*max(.05, cos(lat)));
            alt = u_pose.z + a_alt*u_pose.w;
            normal = vec3(a_norm.x*u_heading.x + a_norm.y*u_heading.y, a_norm.x*u_heading.y - a_norm.y*u_heading.x, a_norm.z);
          }
          gl_Position = projectSeamWorld(pos, alt);
          v_vis = 1.0;
          #ifdef GLOBE
            vec3 sp = projectToSphere(pos, pos);
            vec3 ep = sp * (1.0 + alt / GLOBE_RADIUS);
            float front = dot(ep, u_projection_clipping_plane.xyz) + u_projection_clipping_plane.w;
            if (u_projection_transition > 0.25 && u_earth_occlude > 0.5) {
              if (alt < 5000.0 && front < -0.025) v_vis = 0.0;
              else if (alt >= 5000.0 && front < -0.18) {
                vec3 nrm = normalize(u_projection_clipping_plane.xyz);
                float axial = dot(ep, nrm);
                float perp = length(ep - axial * nrm);
                if (perp < 0.995) v_vis = 0.0;
              }
            }
          #endif
          v_color = a_color;
          v_norm = normal;
          v_lit = a_lit;
        }`;
      const fs = `#version 300 es
        precision highp float;
        uniform vec3 u_sun;
        in vec4 v_color;
        in vec3 v_norm;
        in float v_lit;
        in float v_vis;
        out vec4 fragColor;
        void main() {
          if (v_vis < 0.01 || v_color.a < 0.005) discard;
          vec3 col = v_color.rgb;
          if (v_lit > 0.5) {
            float diff = clamp(dot(normalize(v_norm), normalize(u_sun)), 0.0, 1.0);
            float rim = 1.0 - clamp(abs(v_norm.z), 0.0, 1.0);
            col = col * (0.48 + 0.65 * diff) + vec3(0.22, 0.30, 0.36) * rim * 0.25;
          }
          fragColor = vec4(col, v_color.a * v_vis);
        }`;
      return (programs[key] = linkProgram(gl, vs, fs));
    }

    function getPulseProg(gl, shaderData) {
      const key = "pulse_" + shaderData.variantName;
      if (programs[key]) return programs[key];
      const vs = `#version 300 es
        ${shaderData.define || ""}
        ${shaderData.vertexShaderPrelude}
        ${WORLD_PROJ_GLSL}
        uniform float u_scale_m;
        uniform float u_time;
        uniform float u_active_day;
        uniform float u_is_playing;
        uniform float u_scan_progress;
        uniform vec2 u_scan_bounds;
        in vec2 a_center;
        in vec2 a_corner;
        in float a_elev;
        in float a_day;
        in float a_age_mode; // 0 = picked reticle, 1 = active/trail day
        in vec3 a_color;
        out vec2 v_uv;
        out vec3 v_col;
        out float v_alpha;
        out float v_phase;
        out float v_mode;
        void main() {
          float rad = u_scale_m * (a_age_mode > 1.5 ? 1.8 : (a_age_mode < 0.5 ? 1.35 : (a_day == u_active_day ? 1.15 : 0.62)));
          float latGuess = clamp((0.5 - a_center.y) * 3.14159, -1.2, 1.2);
          float dxMerc = (a_corner.x * rad) / 40075017.0;
          float dyMerc = (a_corner.y * rad) / (40075017.0 * max(0.3, cos(latGuess)));
          vec2 pos = a_center + vec2(dxMerc, dyMerc);
          gl_Position = projectSeamWorld(pos, a_elev + 120.0);
          float vis = 1.0;
          #ifdef GLOBE
            vec3 sp = projectToSphere(a_center, a_center);
            if (u_projection_transition > 0.25 && dot(sp, u_projection_clipping_plane.xyz) + u_projection_clipping_plane.w < -0.02) vis = 0.0;
          #endif
          v_uv = a_corner;
          v_col = a_color;
          v_mode = a_age_mode;
          if(a_age_mode>1.5){
            float along=(a_center.x-u_scan_bounds.x)/max(0.000001,u_scan_bounds.y-u_scan_bounds.x);
            float age=u_scan_progress-along;
            v_phase=clamp(age*5.0,0.0,1.0);
            v_alpha=smoothstep(-0.025,0.015,age)*(1.0-v_phase*0.25)*vis;
          } else if (a_age_mode < 0.5) {
            v_phase = fract(u_time * 0.65);
            v_alpha = 0.92 * vis;
          } else {
            float diff = u_active_day - a_day;
            v_phase = fract(u_time * 0.85 + (a_center.x * 37.0 + a_center.y * 53.0));
            v_alpha = (diff == 0.0 ? 0.95 : diff == 1.0 ? 0.42 : 0.16) * vis;
          }
        }`;
      const fs = `#version 300 es
        precision highp float;
        in vec2 v_uv;
        in vec3 v_col;
        in float v_alpha;
        in float v_phase;
        in float v_mode;
        out vec4 fragColor;
        void main() {
          float r = length(v_uv);
          if (r > 1.0 || v_alpha < 0.01) discard;
          float ring = 0.0;
          if (v_mode < 0.5) {
            // Crisp dual reticle + breathing outer halo around picked detection
            float r1 = smoothstep(0.08, 0.0, abs(r - (0.36 + 0.46 * v_phase))) * (1.0 - v_phase);
            float r2 = smoothstep(0.07, 0.0, abs(r - 0.34));
            ring = max(r1 * 0.85, r2);
          } else {
            float core = exp(-r * r * 14.0) * 0.95;
            float wave = smoothstep(0.11, 0.0, abs(r - (0.18 + 0.78 * v_phase))) * (1.0 - v_phase) * 0.9;
            ring = max(core, wave);
          }
          float a = clamp(ring * v_alpha, 0.0, 1.0);
          if (a < 0.01) discard;
          vec3 hot = mix(v_col, vec3(1.0, 0.96, 0.82), ring * 0.42);
          if(v_mode>1.5)hot=mix(vec3(1.0,0.14,0.025),mix(vec3(1.0,0.62,0.05),vec3(1.0,0.97,0.80),v_phase),smoothstep(0.0,0.65,v_phase));
          fragColor = vec4(hot, a);
        }`;
      return (programs[key] = linkProgram(gl, vs, fs));
    }

    function satColorRgb(pIdx) {
      const hex = [colors.terra, colors.aqua, colors.snpp, colors.n20, colors.n21][pIdx] || colors.snpp;
      return hexRgb(hex);
    }

    // Build dynamic 3D spacecraft + swath cones + orbital tracks + optional 2 Nov seam curtain (zero-GC buffer reuse + static caching)
    let cachedBadges = [];
    function ensureOrbitGeometry(nowMs, animateNow, movingNow) {
      if (movingNow && lastOrbitKey) return false;
      const curMode = modeFn();
      const zoom = map ? map.getZoom() : 4.4;
      const zBucket = Math.round(zoom * 20);
      const motion = motionFn();
      const phaseKey = Math.round(animPhaseDeg * 4);
      const oscKey = animateNow ? Math.round((nowMs - startTime) * 0.015) : -1;
      const oKey = `${curMode}|${zBucket}|${phaseKey}|${oscKey}|${orbitOn ? 1 : 0}|${seamOn ? 1 : 0}|${monthStr}|${playDay}|${isDark ? 1 : 0}|${filterKey}|${drawTracks}|${drawSwaths}`;
      if (oKey === lastOrbitKey) return false;
      lastOrbitKey = oKey;

      solidW.reset();
      transW.reset();
      lineW.reset();
      cachedBadges = [];

      const globe = curMode === "globe";
      // Smooth continuous interpolation across zoom 2.4..6.2 so orbital tracks and spacecraft never jump at 3.6 or 5.5.
      const tZ = Math.max(0, Math.min(1, (zoom - 2.4) / 3.8));
      const smoothZ = tZ * tZ * (3 - 2 * tZ);
      const altScale = globe ? (1.0 - smoothZ * 0.76) : Math.max(0.14, 0.34 - (zoom - 4.0) * 0.045);
      const craftScale = globe ? Math.max(0.32, Math.min(1.5, 2.5 / Math.max(1.2, zoom))) : Math.max(0.18, 0.85 / Math.max(2.2, zoom - 1.5));

      const date = window.SeamSatelliteEra.dateFor(monthStr, playDay);
      const isNov2026OrSeam = !!date && date >= "2026-11-02";
      const tSec = (nowMs - startTime) * 0.001;

      for (const original of SATELLITE_ORBITS) {
        if (!window.SeamSatelliteEra.visible(original.key, monthStr, playDay)) continue;
        // Earth turns beneath the inertial orbital plane (20x illustrative clock).
        const sat = { ...original, raanDeg: original.raanDeg - animPhaseDeg * 20 * 360 / 86164 };
        const isChecked = satFilter.includes(sat.pIdx);
        const isSeamSat = seamOn && isNov2026OrSeam && (sat.key === "SNPP" || sat.key === "NOAA20");
        if (!orbitOn && !isSeamSat) continue;
        const active = isChecked || isSeamSat;
        const rgb = satColorRgb(sat.pIdx);
        const isSnppDim = sat.key === "SNPP" && isNov2026OrSeam;
        const isN20Hi = sat.key === "NOAA20" && isNov2026OrSeam;
        const altM = sat.visAltKm * 1000 * altScale;
        const halfSwathM = (sat.swathKm * 1000) * 0.5;
        const phaseNow = window.SeamSatelliteEra.phase(sat, animPhaseDeg);

        // 1. Orbital track arc (streamed directly to vertex writer)
        const span = globe ? 180 : 38;
        const step = globe ? 3 : 2;
        const trackBase = !active ? 0.26 : isSnppDim ? 0.28 : 0.68;
        let hasPrevTrack = false, pTx = 0, pTy = 0, pTa = 0;
        if(drawTracks)for (let d = -span; d <= span; d += step) {
          orbitPoint(sat, phaseNow + d, opScratch);
          const tx = mercX(opScratch.lon), ty = mercY(opScratch.lat);
          const alpha = trackBase * (0.24 + 0.76 * (1 - Math.abs(d) / span));
          if (hasPrevTrack && Math.abs(pTx - tx) <= 0.45) {
            lineW.push11(pTx, pTy, altM, rgb[0], rgb[1], rgb[2], pTa, 0, 0, 1, 0);
            lineW.push11(tx, ty, altM, rgb[0], rgb[1], rgb[2], alpha, 0, 0, 1, 0);
          }
          pTx = tx; pTy = ty; pTa = alpha; hasPrevTrack = true;
        }

        // 2. Ground swath footprint ribbon (streamed directly, zero intermediate object arrays)
        if (active&&drawSwaths) {
          const swathSteps = 5, swathHalfDeg = 11;
          const swAlpha = isSnppDim ? 0.055 : isN20Hi ? 0.145 : 0.10;
          const edgeAlpha = isSnppDim ? 0.25 : 0.58;
          const innerW = halfSwathM * 0.42;
          let hasPrevSw = false;
          for (let k = -swathSteps; k <= swathSteps; k++) {
            orbitPoint(sat, phaseNow + (k / swathSteps) * swathHalfDeg, opScratch);
            enuOffsetToMerc(opScratch.lon, opScratch.lat, -opScratch.rightE * halfSwathM, -opScratch.rightN * halfSwathM, lB);
            enuOffsetToMerc(opScratch.lon, opScratch.lat, opScratch.rightE * halfSwathM, opScratch.rightN * halfSwathM, rB);
            if (sat.kind === "VIIRS") {
              enuOffsetToMerc(opScratch.lon, opScratch.lat, -opScratch.rightE * innerW, -opScratch.rightN * innerW, mlB);
              enuOffsetToMerc(opScratch.lon, opScratch.lat, opScratch.rightE * innerW, opScratch.rightN * innerW, mrB);
            }
            if (hasPrevSw && Math.abs(lA[0] - lB[0]) <= 0.35 && Math.abs(rA[0] - rB[0]) <= 0.35) {
              pushTriW(transW, lA[0], lA[1], 120, rA[0], rA[1], 120, rB[0], rB[1], 120, rgb[0], rgb[1], rgb[2], swAlpha, 0, 0, 1, 0);
              pushTriW(transW, lA[0], lA[1], 120, rB[0], rB[1], 120, lB[0], lB[1], 120, rgb[0], rgb[1], rgb[2], swAlpha, 0, 0, 1, 0);
              lineW.push11(lA[0], lA[1], 180, rgb[0], rgb[1], rgb[2], edgeAlpha, 0, 0, 1, 0);
              lineW.push11(lB[0], lB[1], 180, rgb[0], rgb[1], rgb[2], edgeAlpha, 0, 0, 1, 0);
              lineW.push11(rA[0], rA[1], 180, rgb[0], rgb[1], rgb[2], edgeAlpha, 0, 0, 1, 0);
              lineW.push11(rB[0], rB[1], 180, rgb[0], rgb[1], rgb[2], edgeAlpha, 0, 0, 1, 0);
              if (sat.kind === "VIIRS") {
                lineW.push11(mlA[0], mlA[1], 180, rgb[0], rgb[1], rgb[2], 0.30, 0, 0, 1, 0);
                lineW.push11(mlB[0], mlB[1], 180, rgb[0], rgb[1], rgb[2], 0.30, 0, 0, 1, 0);
                lineW.push11(mrA[0], mrA[1], 180, rgb[0], rgb[1], rgb[2], 0.30, 0, 0, 1, 0);
                lineW.push11(mrB[0], mrB[1], 180, rgb[0], rgb[1], rgb[2], 0.30, 0, 0, 1, 0);
              }
            }
            lA[0] = lB[0]; lA[1] = lB[1];
            rA[0] = rB[0]; rA[1] = rB[1];
            mlA[0] = mlB[0]; mlA[1] = mlB[1];
            mrA[0] = mrB[0]; mrA[1] = mrB[1];
            hasPrevSw = true;
          }
        }

        // 3. Instantaneous satellite center + articulated 3D WebGL spacecraft mesh + scan fan cone
        orbitPoint(sat, phaseNow, curScratch);
        const sMx = mercX(curScratch.lon), sMy = mercY(curScratch.lat);
        // Roughly 42 screen pixels across; keep models readable without covering the map when zoomed in.
        const busBase = 7 * 40075016.6856 * Math.cos(curScratch.lat * D2R) / (512 * Math.pow(2, zoom));

        const dimK = !active ? 0.65 : isSnppDim ? 0.72 : 1.0;
        const busGold = [0.89 * dimK, 0.68 * dimK, 0.26 * dimK, 1.0];
        const bayTint = [Math.min(1, rgb[0] * 0.85 + 0.15) * dimK, Math.min(1, rgb[1] * 0.85 + 0.15) * dimK, Math.min(1, rgb[2] * 0.85 + 0.15) * dimK, 1.0];
        const panelBlue = isDark ? [0.16 * dimK, 0.44 * dimK, 0.78 * dimK, 1.0] : [0.12 * dimK, 0.34 * dimK, 0.62 * dimK, 1.0];
        const yokeMetal = [0.76 * dimK, 0.80 * dimK, 0.84 * dimK, 1.0];
        const sc = active ? 1.0 : 0.72;

        const model = window.SeamSatelliteModels?.models.get(sat.key);
        if (!model) {
          window.SeamSatelliteModels?.load(sat.key);
          if (sat.kind === "MODIS") {
            // EOS Terra MODIS silhouette: elongated bus + nadir scan cavity + single starboard solar array
            pushBoxW(solidW, curScratch, altM, sc, 0, 0, 0, busBase * 1.65 * sc, busBase * 0.95 * sc, busBase * 0.88 * sc, busGold, 1, m0, m1, m2, m3, m4, m5, m6, m7);
            pushBoxW(solidW, curScratch, altM, sc, busBase * 0.32 * sc, 0, -busBase * 0.58 * sc, busBase * 0.78 * sc, busBase * 0.72 * sc, busBase * 0.50 * sc, bayTint, 1, m0, m1, m2, m3, m4, m5, m6, m7);
            pushBoxW(solidW, curScratch, altM, sc, -busBase * 0.10 * sc, busBase * 2.25 * sc, 0, busBase * 1.05 * sc, busBase * 3.10 * sc, busBase * 0.08 * sc, panelBlue, 1, m0, m1, m2, m3, m4, m5, m6, m7);
            pushBoxW(solidW, curScratch, altM, sc, -busBase * 0.10 * sc, busBase * 0.85 * sc, 0, busBase * 0.16 * sc, busBase * 1.80 * sc, busBase * 0.12 * sc, yokeMetal, 1, m0, m1, m2, m3, m4, m5, m6, m7);
          } else {
            // JPSS / S-NPP VIIRS silhouette: compact octagonal bus + nadir VIIRS/CrIS instrument deck + aft solar array wing
            pushBoxW(solidW, curScratch, altM, sc, 0, 0, 0, busBase * 1.35 * sc, busBase * 0.88 * sc, busBase * 0.82 * sc, busGold, 1, m0, m1, m2, m3, m4, m5, m6, m7);
            pushBoxW(solidW, curScratch, altM, sc, busBase * 0.24 * sc, 0, -busBase * 0.54 * sc, busBase * 0.76 * sc, busBase * 0.68 * sc, busBase * 0.48 * sc, bayTint, 1, m0, m1, m2, m3, m4, m5, m6, m7);
            pushBoxW(solidW, curScratch, altM, sc, -busBase * 0.22 * sc, -busBase * 2.05 * sc, busBase * 0.12 * sc, busBase * 0.92 * sc, busBase * 2.65 * sc, busBase * 0.08 * sc, panelBlue, 1, m0, m1, m2, m3, m4, m5, m6, m7);
            pushBoxW(solidW, curScratch, altM, sc, -busBase * 0.22 * sc, -busBase * 0.75 * sc, busBase * 0.06 * sc, busBase * 0.15 * sc, busBase * 1.60 * sc, busBase * 0.12 * sc, yokeMetal, 1, m0, m1, m2, m3, m4, m5, m6, m7);
          }
        }


        if (active&&drawSwaths) {
          const coneSpanF = 160000 * altScale;
          enuOffsetToMerc(curScratch.lon, curScratch.lat, curScratch.rightE * halfSwathM + curScratch.fwdE * coneSpanF, curScratch.rightN * halfSwathM + curScratch.fwdN * coneSpanF, gA);
          enuOffsetToMerc(curScratch.lon, curScratch.lat, -curScratch.rightE * halfSwathM + curScratch.fwdE * coneSpanF, -curScratch.rightN * halfSwathM + curScratch.fwdN * coneSpanF, gB);
          enuOffsetToMerc(curScratch.lon, curScratch.lat, -curScratch.rightE * halfSwathM - curScratch.fwdE * coneSpanF, -curScratch.rightN * halfSwathM - curScratch.fwdN * coneSpanF, gC);
          enuOffsetToMerc(curScratch.lon, curScratch.lat, curScratch.rightE * halfSwathM - curScratch.fwdE * coneSpanF, curScratch.rightN * halfSwathM - curScratch.fwdN * coneSpanF, gD);
          const fanAlpha = isSnppDim ? 0.05 : 0.20;
          pushTriW(transW, sMx, sMy, altM, gA[0], gA[1], 120, gB[0], gB[1], 120, rgb[0], rgb[1], rgb[2], fanAlpha, 0, 0, 1, 0);
          pushTriW(transW, sMx, sMy, altM, gB[0], gB[1], 120, gC[0], gC[1], 120, rgb[0], rgb[1], rgb[2], fanAlpha, 0, 0, 1, 0);
          pushTriW(transW, sMx, sMy, altM, gC[0], gC[1], 120, gD[0], gD[1], 120, rgb[0], rgb[1], rgb[2], fanAlpha, 0, 0, 1, 0);
          pushTriW(transW, sMx, sMy, altM, gD[0], gD[1], 120, gA[0], gA[1], 120, rgb[0], rgb[1], rgb[2], fanAlpha, 0, 0, 1, 0);
          const scanOsc = animateNow ? Math.sin(tSec * 2.2 + sat.pIdx) : 0.2;
          enuOffsetToMerc(curScratch.lon, curScratch.lat, curScratch.rightE * halfSwathM * scanOsc, curScratch.rightN * halfSwathM * scanOsc, gA);
          const beamA = isSnppDim ? 0.25 : 0.72;
          lineW.push11(sMx, sMy, altM, rgb[0], rgb[1], rgb[2], beamA, 0, 0, 1, 0);
          lineW.push11(gA[0], gA[1], 180, rgb[0], rgb[1], rgb[2], beamA, 0, 0, 1, 0);
        }

        cachedBadges.push({
          key: sat.key, short: sat.short, label: sat.label, kind: sat.kind,
          lon: curScratch.lon, lat: curScratch.lat, alt: altM, lst: sat.lst, swathKm: sat.swathKm,
          ended: isSnppDim, handedOver: false, selected: isChecked, note: "Illustrative orbit, 20× time; not live tracking or measured exposure.", pIdx: sat.pIdx,
          model: !!model, widthM: busBase * 6 * sc, fwdE: curScratch.fwdE, fwdN: curScratch.fwdN,
          sx: -999, sy: -999, visible: false,
        });
      }


      return true;
    }

    function pointElev(i) {
      let e = pointsData.elev[i];
      if (e < -9000) {
        if (map && map.getTerrain()) {
          const q = map.queryTerrainElevation([pointsData.lon[i], pointsData.lat[i]]);
          if (q != null) { e = q; pointsData.elev[i] = e; }
          else e = 0;
        } else {
          e = 0;
          pointsData.elev[i] = 0;
        }
      }
      return e;
    }

    // Build GPU quad attributes for temporal sonar pulses (cached per filter/day/picked/elev change!)
    function ensurePulseGeometry() {
      const motion = motionFn();
      const pKey = `${pointsVer}|${elevVer}|${playDay}|${pickedIdx == null ? -1 : pickedIdx}|${filterKey}|${motion}|${scanReveal}`;
      if (pKey === lastPulseKey) return false;
      lastPulseKey = pKey;
      pulseW.reset();

      const addQuad = (mx, my, elev, day, ageMode, col) => {
        for (let c = 0; c < 6; c++) {
          pulseW.push10(mx, my, corners[c][0], corners[c][1], elev, day, ageMode, col[0], col[1], col[2]);
        }
      };

      if (pointsData && pickedIdx != null && pickedIdx < pointsData.lon.length) {
        addQuad(pointsData.mx[pickedIdx], pointsData.my[pickedIdx], pointElev(pickedIdx), pointsData.day[pickedIdx], 0.0, satColorRgb(pointsData.p[pickedIdx]));
      }
      if(pointsData&&scanReveal){
        const n=pointsData.lon.length,stride=Math.max(1,Math.ceil(n/1000));
        for(let i=0;i<n;i+=stride){
          if(!satFilter.includes(pointsData.p[i])||(dnFilter!=='DN'&&(dnFilter==='N')!==(pointsData.dn[i]===1)))continue;
          if(playDay&&pointsData.day[i]!==playDay)continue;
          addQuad(pointsData.mx[i],pointsData.my[i],pointElev(i),pointsData.day[i],2.0,[1,.32,.04]);
        }
      }
      if (pointsData && playDay > 0 && motion === "full") {
        const minD = Math.max(1, playDay - 2), nightOnly = dnFilter === "N", allDn = dnFilter === "DN";
        let matchCount = 0;
        for (let i = 0; i < pointsData.lon.length; i++) {
          const d = pointsData.day[i];
          if (d < minD || d > playDay) continue;
          if (!satFilter.includes(pointsData.p[i])) continue;
          if (!allDn && nightOnly !== (pointsData.dn[i] === 1)) continue;
          matchCount++;
        }
        const MAX_PULSES = 850;
        const stride = matchCount > MAX_PULSES ? Math.ceil(matchCount / MAX_PULSES) : 1;
        let seen = 0, emitted = 0;
        for (let i = 0; i < pointsData.lon.length && emitted < MAX_PULSES; i++) {
          const d = pointsData.day[i];
          if (d < minD || d > playDay) continue;
          if (!satFilter.includes(pointsData.p[i])) continue;
          if (!allDn && nightOnly !== (pointsData.dn[i] === 1)) continue;
          if (stride === 1 || (seen % stride === 0)) {
            addQuad(pointsData.mx[i], pointsData.my[i], pointElev(i), d, 1.0, satColorRgb(pointsData.p[i]));
            emitted++;
          }
          seen++;
        }
      }
      return true;
    }

    const bindMeshAttrs = (glCtx, prog) => {
      const stride = 11 * 4;
      const p0 = aLoc(glCtx, prog, "a_pos"), p1 = aLoc(glCtx, prog, "a_alt"), p2 = aLoc(glCtx, prog, "a_color"),
            p3 = aLoc(glCtx, prog, "a_norm"), p4 = aLoc(glCtx, prog, "a_lit");
      if (p0 >= 0) { glCtx.enableVertexAttribArray(p0); glCtx.vertexAttribPointer(p0, 2, glCtx.FLOAT, false, stride, 0); }
      if (p1 >= 0) { glCtx.enableVertexAttribArray(p1); glCtx.vertexAttribPointer(p1, 1, glCtx.FLOAT, false, stride, 8); }
      if (p2 >= 0) { glCtx.enableVertexAttribArray(p2); glCtx.vertexAttribPointer(p2, 4, glCtx.FLOAT, false, stride, 12); }
      if (p3 >= 0) { glCtx.enableVertexAttribArray(p3); glCtx.vertexAttribPointer(p3, 3, glCtx.FLOAT, false, stride, 28); }
      if (p4 >= 0) { glCtx.enableVertexAttribArray(p4); glCtx.vertexAttribPointer(p4, 1, glCtx.FLOAT, false, stride, 40); }
    };

    const layer = {
      id: "seamline-fx",
      type: "custom",
      renderingMode: "3d",
      onAdd(m, glCtx) {
        map = m;
        gl = glCtx;
        vao = gl.createVertexArray();
        window.addEventListener("satellite-models-ready", modelsReady);
        vboSolid = gl.createBuffer();
        vboTrans = gl.createBuffer();
        vboLine = gl.createBuffer();
        vboPulse = gl.createBuffer();
        moveEndHandler = () => {
          lastOrbitKey = "";
          if (map && (orbitOn || seamOn || (playDay > 0 && isPlaying))) map.triggerRepaint();
        };
        if (m && m.on) m.on("moveend", moveEndHandler);
      },
      onRemove(m, glCtx) {
        clearRepaintTimer();
        window.removeEventListener("satellite-models-ready", modelsReady);
        for (const entry of modelBuffers.values()) { glCtx.deleteBuffer(entry.buffer); glCtx.deleteBuffer(entry.indexBuffer); }
        modelBuffers.clear();
        if (vao) glCtx.deleteVertexArray(vao);
        vao = null;
        map = null;
        if (moveEndHandler && m && m.off) m.off("moveend", moveEndHandler);
        moveEndHandler = null;
        for (const k of Object.keys(programs)) {
          try { glCtx.deleteProgram(programs[k]); } catch (_) {}
        }
        programs = {};
        for (const b of [vboSolid, vboTrans, vboLine, vboPulse]) {
          if (b) try { glCtx.deleteBuffer(b); } catch (_) {}
        }
        vboSolid = vboTrans = vboLine = vboPulse = null;
      },
      render(glCtx, options) {
        if (!map || !options || !options.shaderData) return;
        if (!activeView || document.hidden) { lastFrameTime = performance.now(); clearRepaintTimer(); return; }
        const now = performance.now();
        const dt = Math.min(0.1, (now - lastFrameTime) * 0.001);
        lastFrameTime = now;
        const motion = motionFn();
        const movingNow = !!(map.isMoving && map.isMoving()) || !!(map.isZooming && map.isZooming()) || !!(map.isRotating && map.isRotating());
        if (motion === "full" && orbitOn && !movingNow) animPhaseDeg += dt;

        const needOrbit = orbitOn || seamOn;
        const needPulse = (playDay > 0 && motion === "full") || pickedIdx != null || scanReveal;
        if (!needOrbit && !needPulse) {
          clearRepaintTimer();
          if (hadBadges) {
            satScreenBadges = [];
            hadBadges = false;
            if (opts.onTick) opts.onTick(satScreenBadges);
          }
          return;
        }

        const animateNow = !document.hidden && motion === "full" && (orbitOn || (playDay > 0 && isPlaying));
        const previousVao = glCtx.getParameter(glCtx.VERTEX_ARRAY_BINDING);
        glCtx.bindVertexArray(vao);
        glCtx.enable(glCtx.BLEND);
        glCtx.blendFuncSeparate(glCtx.SRC_ALPHA, glCtx.ONE_MINUS_SRC_ALPHA, glCtx.ONE, glCtx.ONE_MINUS_SRC_ALPHA);
        glCtx.enable(glCtx.DEPTH_TEST);
        glCtx.disable(glCtx.CULL_FACE);

        const sunVec = dnFilter === "N" ? [-0.45, 0.35, 0.72] : [0.55, -0.35, 0.76];

        if (needOrbit) {
          const orbitDirty = ensureOrbitGeometry(now, animateNow, movingNow);
          const canvas = map.getCanvas();
          const cssW = canvas.clientWidth || canvas.width, cssH = canvas.clientHeight || canvas.height;
          for (let i = 0; i < cachedBadges.length; i++) {
            const b = cachedBadges[i];
            const p = project3d(b.lon, b.lat, b.alt, options.defaultProjectionData, cssW, cssH, options.shaderData.variantName);
            b.sx = p.sx; b.sy = p.sy; b.visible = p.visible;
          }
          satScreenBadges = cachedBadges;
          hadBadges = cachedBadges.length > 0;

          const prog = getMeshProg(glCtx, options.shaderData);
          glCtx.useProgram(prog);
          setUniforms(glCtx, prog, options);
          glCtx.uniform3fv(uLoc(glCtx, prog, "u_sun"), sunVec);
          glCtx.uniform1f(uLoc(glCtx, prog, "u_earth_occlude"), 1.0);
          glCtx.uniform1f(uLoc(glCtx, prog, "u_model"), 0.0);

          if (solidW.length()) {
            glCtx.depthMask(true);
            glCtx.bindBuffer(glCtx.ARRAY_BUFFER, vboSolid);
            if (orbitDirty) glCtx.bufferData(glCtx.ARRAY_BUFFER, solidW.view(), glCtx.DYNAMIC_DRAW);
            bindMeshAttrs(glCtx, prog);
            glCtx.drawArrays(glCtx.TRIANGLES, 0, solidW.length() / 11);
          }

          glCtx.uniform1f(uLoc(glCtx, prog, "u_model"), 1.0);
          for (const b of cachedBadges) {
            const model = window.SeamSatelliteModels?.models.get(b.key);
            if (!model) continue;
            let entry = modelBuffers.get(b.key);
            if (!entry) {
              const buffer = glCtx.createBuffer(); glCtx.bindBuffer(glCtx.ARRAY_BUFFER, buffer);
              glCtx.bufferData(glCtx.ARRAY_BUFFER, model.vertices, glCtx.STATIC_DRAW);
              const indexBuffer = glCtx.createBuffer(); glCtx.bindBuffer(glCtx.ELEMENT_ARRAY_BUFFER, indexBuffer);
              glCtx.bufferData(glCtx.ELEMENT_ARRAY_BUFFER, model.indices, glCtx.STATIC_DRAW);
              entry = { buffer, indexBuffer, count: model.indices.length }; modelBuffers.set(b.key, entry);
            }
            glCtx.bindBuffer(glCtx.ARRAY_BUFFER, entry.buffer); bindMeshAttrs(glCtx, prog);
            glCtx.bindBuffer(glCtx.ELEMENT_ARRAY_BUFFER, entry.indexBuffer);
            glCtx.uniform4f(uLoc(glCtx, prog, "u_pose"), mercX(b.lon), mercY(b.lat), b.alt, b.widthM);
            glCtx.uniform2f(uLoc(glCtx, prog, "u_heading"), b.fwdE, b.fwdN);
            glCtx.drawElements(glCtx.TRIANGLES, entry.count, glCtx.UNSIGNED_INT, 0);
          }
          glCtx.uniform1f(uLoc(glCtx, prog, "u_model"), 0.0);
          glCtx.depthMask(false);
          if (transW.length()) {
            glCtx.bindBuffer(glCtx.ARRAY_BUFFER, vboTrans);
            if (orbitDirty) glCtx.bufferData(glCtx.ARRAY_BUFFER, transW.view(), glCtx.DYNAMIC_DRAW);
            bindMeshAttrs(glCtx, prog);
            glCtx.drawArrays(glCtx.TRIANGLES, 0, transW.length() / 11);
          }

          if (lineW.length()) {
            glCtx.bindBuffer(glCtx.ARRAY_BUFFER, vboLine);
            if (orbitDirty) glCtx.bufferData(glCtx.ARRAY_BUFFER, lineW.view(), glCtx.DYNAMIC_DRAW);
            bindMeshAttrs(glCtx, prog);
            glCtx.drawArrays(glCtx.LINES, 0, lineW.length() / 11);
          }
        } else if (hadBadges) {
          satScreenBadges = [];
          hadBadges = false;
          if (opts.onTick) opts.onTick(satScreenBadges);
        }

        if (needPulse) {
          const pulseDirty = ensurePulseGeometry();
          if (pulseW.length()) {
            glCtx.depthMask(false);
            const pProg = getPulseProg(glCtx, options.shaderData);
            glCtx.useProgram(pProg);
            setUniforms(glCtx, pProg, options);
            const z = map.getZoom();
            const scaleM = Math.max(2200, Math.min(26000, 120000 / Math.pow(1.45, z)));
            glCtx.uniform1f(uLoc(glCtx, pProg, "u_scale_m"), scaleM);
            glCtx.uniform1f(uLoc(glCtx, pProg, "u_time"), motion === "full" && animateNow ? (now - startTime) * 0.001 : 0.28);
            glCtx.uniform1f(uLoc(glCtx, pProg, "u_active_day"), playDay);
            glCtx.uniform1f(uLoc(glCtx, pProg, "u_is_playing"), isPlaying ? 1.0 : 0.0);
            glCtx.uniform1f(uLoc(glCtx,pProg,"u_scan_progress"),scanProgress);
            glCtx.uniform2f(uLoc(glCtx,pProg,"u_scan_bounds"),scanBounds[0],scanBounds[1]);

            glCtx.bindBuffer(glCtx.ARRAY_BUFFER, vboPulse);
            if (pulseDirty) glCtx.bufferData(glCtx.ARRAY_BUFFER, pulseW.view(), glCtx.DYNAMIC_DRAW);
            const pStride = 10 * 4;
            const p0 = aLoc(glCtx, pProg, "a_center"), p1 = aLoc(glCtx, pProg, "a_corner"), p2 = aLoc(glCtx, pProg, "a_elev"),
                  p3 = aLoc(glCtx, pProg, "a_day"), p4 = aLoc(glCtx, pProg, "a_age_mode"), p5 = aLoc(glCtx, pProg, "a_color");
            if (p0 >= 0) { glCtx.enableVertexAttribArray(p0); glCtx.vertexAttribPointer(p0, 2, glCtx.FLOAT, false, pStride, 0); }
            if (p1 >= 0) { glCtx.enableVertexAttribArray(p1); glCtx.vertexAttribPointer(p1, 2, glCtx.FLOAT, false, pStride, 8); }
            if (p2 >= 0) { glCtx.enableVertexAttribArray(p2); glCtx.vertexAttribPointer(p2, 1, glCtx.FLOAT, false, pStride, 16); }
            if (p3 >= 0) { glCtx.enableVertexAttribArray(p3); glCtx.vertexAttribPointer(p3, 1, glCtx.FLOAT, false, pStride, 20); }
            if (p4 >= 0) { glCtx.enableVertexAttribArray(p4); glCtx.vertexAttribPointer(p4, 1, glCtx.FLOAT, false, pStride, 24); }
            if (p5 >= 0) { glCtx.enableVertexAttribArray(p5); glCtx.vertexAttribPointer(p5, 3, glCtx.FLOAT, false, pStride, 28); }
            glCtx.drawArrays(glCtx.TRIANGLES, 0, pulseW.length() / 10);
          }
        }
        glCtx.depthMask(true);

        glCtx.bindVertexArray(previousVao);

        const renderMs = performance.now() - now;
        lastRenderMs = lastRenderMs * 0.65 + renderMs * 0.35;

        if (opts.onTick && needOrbit && (!animateNow || now - lastTickAt >= (movingNow ? 28 : 48))) {
          lastTickAt = now;
          opts.onTick(satScreenBadges);
        }
        if (animateNow && !movingNow) scheduleRepaint(lastRenderMs);
        else clearRepaintTimer();
      },
    };

    return {
      layer,
      setDate(month) { monthStr = month || null; lastOrbitKey = ""; satScreenBadges = []; if (opts.onTick) opts.onTick([]); if (map) map.triggerRepaint(); },
      setActive(on) { activeView = !!on; lastFrameTime = performance.now(); if (!on) clearRepaintTimer(); else if (map) map.triggerRepaint(); },
      setTheme(c, dark) { colors = c; isDark = !!dark; lastOrbitKey = ""; lastPulseKey = ""; if (map) map.triggerRepaint(); },
      setPoints(P) {
        monthStr = P?.month || null; lastOrbitKey = ""; satScreenBadges = [];
        if (opts.onTick) opts.onTick([]);
        if (map) map.triggerRepaint();
        if (!P || !P.lon || !P.lon.length) { pointsData = null; pointsVer++; lastPulseKey = ""; return; }
        const n = P.lon.length;
        const mx = new Float32Array(n), my = new Float32Array(n), elev = new Float32Array(n);
        elev.fill(-99999);
        for (let i = 0; i < n; i++) {
          mx[i] = mercX(P.lon[i]);
          my[i] = mercY(P.lat[i]);
        }
        pointsData = { lon: P.lon, lat: P.lat, mx, my, elev, p: P.p, dn: P.dn, day: P.day };
        let minX=Infinity,maxX=-Infinity;for(let i=0;i<n;i++){minX=Math.min(minX,mx[i]);maxX=Math.max(maxX,mx[i]);}scanBounds=n?[minX,maxX]:[0,1];
        monthStr = P.month || "2025-11";
        pointsVer++;
        lastOrbitKey = "";
        lastPulseKey = "";
      },
      refreshElevation() {
        if (!pointsData) return;
        pointsData.elev.fill(-99999);
        elevVer++;
        lastPulseKey = "";
      },
      setFilter(f) {
        satFilter = f.sats || []; dnFilter = f.dn || "DN";
        filterKey = `${satFilter.join(",")}|${dnFilter}`;
        lastOrbitKey = ""; lastPulseKey = "";
        if (map) map.triggerRepaint();
      },
      setOrbit(on) {
        orbitOn = !!on; lastOrbitKey = "";
        if (!orbitOn && !seamOn) { clearRepaintTimer(); satScreenBadges = []; hadBadges = false; if (opts.onTick) opts.onTick(satScreenBadges); }
        if (map) map.triggerRepaint();
      },
      setSeam(on) {
        seamOn = !!on; lastOrbitKey = "";
        if (!orbitOn && !seamOn) { clearRepaintTimer(); satScreenBadges = []; hadBadges = false; if (opts.onTick) opts.onTick(satScreenBadges); }
        if (map) map.triggerRepaint();
      },
      setPsf(on) { psfOn = !!on; },
      setPlayback(day, playing) {
        playDay = day || 0; isPlaying = !!playing; lastPulseKey = ""; lastOrbitKey = "";
        if (!isPlaying && !orbitOn) clearRepaintTimer();
        if (map) map.triggerRepaint();
      },
      select(i) { pickedIdx = i == null ? null : i; lastPulseKey = ""; if (map) map.triggerRepaint(); },
      badges: () => satScreenBadges.slice(),
      setScan(progress,on=true){const changed=scanReveal!==on;scanReveal=on;scanProgress=Math.max(0,Math.min(1,progress));if(changed)lastPulseKey="";if(map)map.triggerRepaint();},
      setTracks(on){drawTracks=!!on;lastOrbitKey="";if(map)map.triggerRepaint();},
      setSwaths(on){drawSwaths=!!on;lastOrbitKey="";if(map)map.triggerRepaint();},
      layerState:()=>({tracks:drawTracks,swaths:drawSwaths,scan:scanReveal}),
      orbitActive: () => orbitOn,
      seamActive: () => seamOn,
      resetOrbitPhase() { animPhaseDeg = 0; lastOrbitKey = ""; },
      stopIdle() { clearRepaintTimer(); },
    };
  }

  window.SeamFX = { create, SATELLITE_ORBITS, mercX, mercY, orbitPoint };
})();
