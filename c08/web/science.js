// Scientific Knowledge Base, Climatology Regime Analysis (Mean vs. Median & Peak Months),
// and C08 Persona Guides — 100% offline, zero external requests on load.
(function (root) {
  "use strict";

  const MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const MONTHS_FULL = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
    }[ch]));
  }

  function fmtNum(v, d = 0) {
    if (v == null || !Number.isFinite(Number(v))) return "unavailable";
    return Number(v).toLocaleString("en-US", {
      minimumFractionDigits: d,
      maximumFractionDigits: d,
    });
  }

  function cssVar(name, fallback) {
    if (typeof document === "undefined" || typeof getComputedStyle !== "function") return fallback || "#333";
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback || "#333";
  }

  function quantileSorted(sorted, q) {
    if (!sorted || !sorted.length) return null;
    if (sorted.length === 1) return sorted[0];
    const pos = (sorted.length - 1) * q;
    const lo = Math.floor(pos);
    const hi = Math.ceil(pos);
    return lo === hi ? sorted[lo] : sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
  }

  /**
   * Compute historical 12-month climatology (Mean, Median, IQR, Peak Year) from calendar cells.
   * Flagged/partial months (e.g. partial 2026 or partial satellite overlap) are excluded from the
   * clean baseline statistics so incomplete passes never pull down historical averages.
   */
  function calendarClimatology(cells, compareYear) {
    const byMonth = Array.from({ length: 12 }, (_, idx) => ({
      month: idx + 1,
      name: MONTHS_SHORT[idx],
      fullName: MONTHS_FULL[idx],
      complete: [],
      partialCount: 0,
      selectedCell: null,
    }));

    for (const c of (cells || [])) {
      if (!c || c.month < 1 || c.month > 12) continue;
      const bucket = byMonth[c.month - 1];
      if (compareYear != null && Number(c.year) === Number(compareYear)) {
        bucket.selectedCell = c;
      }
      if (c.value == null || !Number.isFinite(Number(c.value))) continue;
      if (c.flag) {
        bucket.partialCount += 1;
      } else {
        bucket.complete.push({ year: Number(c.year), value: Number(c.value) });
      }
    }

    return byMonth.map((b) => {
      const sorted = b.complete.map((x) => x.value).sort((a, z) => a - z);
      const n = sorted.length;
      const sum = sorted.reduce((acc, x) => acc + x, 0);
      const mean = n ? sum / n : null;
      const median = quantileSorted(sorted, 0.5);
      const p25 = quantileSorted(sorted, 0.25);
      const p75 = quantileSorted(sorted, 0.75);
      let maxRow = null;
      let minRow = null;
      for (const row of b.complete) {
        if (!maxRow || row.value > maxRow.value) maxRow = row;
        if (!minRow || row.value < minRow.value) minRow = row;
      }
      const skewRatio = (mean != null && median != null) ? (mean + 1) / (median + 1) : null;
      return {
        month: b.month,
        name: b.name,
        fullName: b.fullName,
        n,
        partialCount: b.partialCount,
        mean,
        median,
        p25,
        p75,
        iqr: (p25 != null && p75 != null) ? (p75 - p25) : null,
        min: minRow ? minRow.value : null,
        minYear: minRow ? minRow.year : null,
        max: maxRow ? maxRow.value : null,
        maxYear: maxRow ? maxRow.year : null,
        skewRatio,
        selectedValue: b.selectedCell ? b.selectedCell.value : null,
        selectedYear: compareYear != null ? Number(compareYear) : null,
        selectedFlag: b.selectedCell ? (b.selectedCell.flag || "") : "",
        selectedClass: b.selectedCell ? (b.selectedCell.class || "") : "",
      };
    });
  }

  /**
   * Compute leave-one-out statistics for all OTHER unflagged complete years of the same month,
   * pairing historical Mean + IQR alongside the server-computed median_other_years.
   */
  function cellStats(cells, targetCell) {
    if (!cells || !targetCell) return null;
    const others = cells
      .filter((x) => x && x.month === targetCell.month && x.year !== targetCell.year && x.value != null && !x.flag)
      .map((x) => Number(x.value))
      .sort((a, b) => a - b);
    if (others.length < 3) return null;
    const mean = others.reduce((a, b) => a + b, 0) / others.length;
    const p25 = quantileSorted(others, 0.25);
    const p75 = quantileSorted(others, 0.75);
    const median = quantileSorted(others, 0.5);
    return {
      n: others.length,
      mean,
      median,
      p25,
      p75,
      iqr: p75 - p25,
    };
  }

  function summarizePeakMonths(climatology) {
    const valid = (climatology || []).filter((m) => m.n > 0 && m.median != null);
    const byMedian = valid.slice().sort((a, b) => (b.median - a.median) || (b.mean - a.mean));
    const topMedian = byMedian.slice(0, 3);
    const episodic = valid
      .filter((m) => m.n >= 3 && m.skewRatio != null && m.skewRatio >= 1.25)
      .sort((a, b) => b.skewRatio - a.skewRatio);
    let maxMonth = null;
    for (const m of valid) {
      if (!maxMonth || (m.max != null && m.max > maxMonth.max)) maxMonth = m;
    }
    return { topMedian, episodic, maxMonth, validCount: valid.length };
  }

  function climatologyCsv(climatology, info) {
    const q = (v) => (v == null ? "" : /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, "\"\"")}"` : String(v));
    const head = [
      "month_num", "month", "n_complete_years", "partial_years_excluded",
      "median_detections", "mean_detections", "iqr_p25", "iqr_p75",
      "min_detections", "max_detections", "max_year",
      "selected_year", "selected_year_detections", "selected_year_flag",
      "series", "region", "model", "data_identity", "derived_note",
    ];
    const lines = [head.join(",")];
    const meta = info || {};
    const note = "Derived client-side from /api/analyze calendar matrix excluding flagged partial months";
    for (const m of (climatology || [])) {
      lines.push([
        m.month,
        m.fullName,
        m.n,
        m.partialCount,
        m.median == null ? "" : m.median.toFixed(2),
        m.mean == null ? "" : m.mean.toFixed(2),
        m.p25 == null ? "" : m.p25.toFixed(2),
        m.p75 == null ? "" : m.p75.toFixed(2),
        m.min == null ? "" : m.min.toFixed(2),
        m.max == null ? "" : m.max.toFixed(2),
        m.maxYear == null ? "" : m.maxYear,
        m.selectedYear == null ? "" : m.selectedYear,
        m.selectedValue == null ? "" : Number(m.selectedValue).toFixed(2),
        m.selectedFlag || "",
        meta.series || "",
        meta.region || "",
        meta.model || "",
        meta.data_identity || "",
        note,
      ].map(q).join(","));
    }
    return lines.join("\n") + "\n";
  }

  const ROLE_PLAYBOOKS = [
    {
      id: "responder",
      title: "Emergency Responder & Early Warning",
      badge: "Near-real-time triage & gap awareness",
      goal: "Inspect the newest 7-day NRT detections alongside pass completeness, scan-angle footprint inflation, and untyped NRT static-source caveats without misreading satellite outages as zero fire.",
      steps: [
        "Open Explore (Map) to inspect individual MODIS/VIIRS pixel footprints, confidence rules, FRP (MW), and standard type=0 vs. untyped NRT status.",
        "Open Calendar -> Day by day to check whether each UTC date had both day and night passes (≥ incomplete pass, ? no Pakistan rows, – FIRMS gap).",
        "Check Calendar -> Experimental outlook (Protocol O01): release gates were pre-registered and remained 'Forecast unavailable', keeping unverified predictions off the warning workflow.",
      ],
      note: "Analytical observation record only (per NASA LANCE disclaimer): not for tactical fire-line or safety-of-life decisions.",
      actions: [
        { label: "Open Map (Explore)", ws: "explore" },
        { label: "Check Day by day passes", ws: "calendar", sub: "days" },
        { label: "Inspect Protocol O01 status", ws: "calendar", sub: "outlook" },
      ],
    },
    {
      id: "land_manager",
      title: "Land & Agricultural Manager",
      badge: "Seasonal regimes (Median vs. Mean) & peak months",
      goal: "Distinguish recurring crop-residue or forest burning seasons from episodic outlier years across provinces or a custom bounding box, eliminating fake 2012/2018/2023 sensor-switch jumps.",
      steps: [
        "Select Punjab, Sindh, KP, or draw a custom bounding box, then switch Calendar to Seasonal profile to view Jan–Dec Median, Mean, IQR (P25–P75), and Peak Months.",
        "Compare the right-skew gap where extreme burn years pull Mean above Median, then click any month cell in Heatmap to jump straight to that month on the Map or Day by day strip.",
        "Use Calendar -> Compare studio to inspect regional shifts or cross-year anomalies without mixing incompatible sensor definitions.",
      ],
      note: "Hotspot detections represent thermal anomalies per satellite overpass — not hectares burned, active fire counts, or emissions.",
      actions: [
        { label: "Open Seasonal profile", ws: "calendar", sub: "months", calMode: "profile" },
        { label: "Open Normal range (Mean & Median)", ws: "calendar", sub: "normal" },
        { label: "Open Compare studio", ws: "calendar", sub: "compare" },
      ],
    },
    {
      id: "scientist",
      title: "Earth Observation Scientist",
      badge: "Sensor physics, frozen P01–P04 & S-NPP handover",
      goal: "Verify radiative transfer, onboard aggregation, saturation rules, confidence stratification, and empirical bridge error (5.1% WAPE) behind every harmonised series.",
      steps: [
        "Inspect Evidence -> Sensor physics & literature for side-by-side MODIS C6/C6.1 vs. VIIRS C2 375 m specs (Sofiev 3.7–40 MW vs. 0.5 MW floors, Schroeder 367 K I4 fold & M13 hybrid FRP, Wooster C6 a=3.0e-9, Giglio type=0..3).",
        "Review Evidence -> Frozen experiments and Handover replay for pre-registered P01–P04 outcomes, including negative/untestable findings preserved untouched.",
        "Inspect Evidence -> Downloads and sources for SHA-256 dataset identity, methodology report, and full NASA FIRMS / LANCE / ESDIS provenance.",
      ],
      note: "Zero universal scale factors applied: Punjab day (7.6x) vs. night (~64x) proves a constant ratio collapses across fire regimes.",
      actions: [
        { label: "Frozen experiments (P01–P04)", ws: "evidence", ev: "experiments" },
        { label: "Handover replay (NOAA-20 bridge)", ws: "evidence", ev: "replay" },
        { label: "Verification log & Limits", ws: "evidence", ev: "limits" },
      ],
    },
  ];

  const SENSORS_SPEC = [
    {
      feature: "NASA FIRMS Product Codes",
      modis: "MCD14ML (archive standard C6.1), MCD14DL (NRT), MOD14A1 / MYD14A1 (1 km daily tile)",
      viirs: "VNP14IMGML / VNP14IMGTDL_NRT (S-NPP), VJ114IMGML / VJ114IMGTDL_NRT (NOAA-20), VJ214IMGTDL_NRT (NOAA-21)",
    },
    {
      feature: "Nominal & Edge Footprint Geometry",
      modis: "1 km nadir (~1.0 km²); ±45° scan over 2,330 km swath stretches off-nadir pixels up to 4.83 × 2.01 km (~9.7 km², bowtie distortion)",
      viirs: "375 m nadir (~0.14 km²); 3:1 -> 2:1 -> 1:1 onboard aggregation over ±55° (3,000 km swath) constrains off-nadir pixel edge < 0.8 km",
    },
    {
      feature: "Minimum Detection FRP Floor",
      modis: "3.7–40 MW (Sofiev & Kouznetsov 2026); misses many cool/small agricultural burns, especially off-nadir (86.2% all-size omission, Giglio 2016)",
      viirs: "~0.5 MW (Sofiev & Kouznetsov 2026); captures small smoldering/agricultural fires and active fronts missed at 1 km",
    },
    {
      feature: "FRP Formulation & Channel Saturation",
      modis: "Wooster linear MIR 3.96 µm radiance (a = 3.0 × 10^-9) in C6/C6.1 (-16.2% vs C5 T4^8); 21/22 dual-gain (21 saturates ~331 K, 22 ~500 K)",
      viirs: "I4 (3.74 µm) saturates at 367 K / folds to 208 K, triggering hybrid M13 dual-gain FRP recovery + 501×501 adaptive background",
    },
    {
      feature: "Confidence & Static Type Rules",
      modis: "Numeric 0–100 score (>=30 kept); 1.2% day global commission (Giglio 2016); archive type 0=vegetation, 1=volcano, 2=static land, 3=offshore",
      viirs: "Categorical l / n / h (nominal & high kept); May 2025 C2 v3 Type fix; untyped NRT streams flagged nrt_untyped (static flares/kilns unscreened)",
    },
    {
      feature: "Local Solar Overpass & Continuity",
      modis: "Terra ~10:30 / 22:30 (drifting), Aqua ~13:30 / 01:30; afternoon Aqua overlaps early S-NPP era for direct calibration",
      viirs: "Afternoon sun-synchronous ~13:30 / 01:30; NOAA-20 ~50 min offset; S-NPP ceased 2 Nov 2026 15:40 UTC -> NOAA-20 bridge (5.1% WAPE in Punjab)",
    },
    {
      feature: "Known Regional Artifacts",
      modis: "Bowtie duplicate overlap across scan lines; dense smoke/cloud opacity reduces detectability",
      viirs: "South Atlantic Magnetic Anomaly (SAMA: 110°W–11°E, 7°N–55°S) triggers spurious I4 single-pixel resets handled by Schroeder filters",
    },
  ];

  const PITFALLS = [
    {
      pitfall: "Universal scale factor (e.g., VIIRS = k × MODIS)",
      whyFails: "Violates regime physics: Punjab shows ~7.6x daytime vs. ~64x nighttime VIIRS/MODIS ratio because VIIRS 0.5 MW sensitivity captures cool night/stubble burns.",
      seamline: "Fits region-calibrated empirical models (P01) only on overlapping windows, tests held-out seasons (E01/E02), and withholds support where bridge assumptions fail.",
    },
    {
      pitfall: "Mixing numeric confidence with l / n / h classes",
      whyFails: "MODIS 0–100 scores and VIIRS low/nominal/high categories are algorithm-specific diagnostics — not probabilities and not cross-sensor thresholds.",
      seamline: "Enforces separate documented quality floors (MODIS >= 30; VIIRS nominal/high) and shows exact product confidence rules in the map inspector.",
    },
    {
      pitfall: "Summing overlapping satellites (Aqua + Terra + VIIRS)",
      whyFails: "Daily totals balloon whenever new satellites launch (2012 S-NPP, 2018 NOAA-20, 2023 NOAA-21) or as morning vs. afternoon orbits overlap.",
      seamline: "Never adds satellites in charts or map legends; bridges across single primary records (Aqua -> S-NPP -> NOAA-20) and exposes raw press-sum traps (P04 G04).",
    },
    {
      pitfall: "Silently blending untyped NRT with archive type=0",
      whyFails: "Standard science archives screen static land sources (type 1–3: flares, brick kilns, smelters, volcanoes); NRT CSVs lack type, adding persistent industrial noise.",
      seamline: "Separates standard type=0 archive from untyped NRT (`nrt_untyped`), annotating every affected month and individual point on inspection.",
    },
    {
      pitfall: "Treating missing satellite passes or clouds as zero fire",
      whyFails: "Telemetry outages, FIRMS missing-data days, or single-pass dropouts appear identical to zero detections unless tracked explicitly.",
      seamline: "Distinguishes true observed 0 from partial pass (≥), unconfirmed gaps (?), provider missing (–), and keeps `O01` at 'Forecast unavailable'.",
    },
    {
      pitfall: "Presenting raw hotspot pixels as burned area or tactical fire-line risk",
      whyFails: "Giglio et al. (2016) establish ~86.2% all-size omission under canopy/cloud and off-nadir ~9.7 km² MODIS footprint stretching; a hotspot is one thermal pixel on one overpass.",
      seamline: "Labels every chart, CSV, and inspector card strictly as satellite fire detections per overpass, accompanied by the official NASA FIRMS / LANCE non-tactical disclaimer.",
    },
  ];

  const LITERATURE_REFS = [
    {
      cite: "Giglio, L., Schroeder, W., & Justice, C. O. (2016)",
      title: "The Collection 6 MODIS active fire detection algorithm and fire products",
      detail: "Remote Sensing of Environment, 178, 31–41. Defines C6 contextual tests, Wooster linear MIR FRP (a=3.0×10^-9, -16.2% vs C5), 1.2% day commission / 86.2% all-size omission, and type=0..3 static masks.",
      locator: "DOI: 10.1016/j.rse.2016.02.054",
    },
    {
      cite: "Schroeder, W., Oliva, P., Giglio, L., & Csiszar, I. A. (2014)",
      title: "The New VIIRS 375 m active fire detection data product: Algorithm description and initial assessment",
      detail: "Remote Sensing of Environment, 143, 85–96. Documents 3:1->2:1->1:1 pixel aggregation (<0.8 km edge), I4 367 K saturation / 208 K fold + hybrid M13 FRP, 501×501 background, and SAMA bounds.",
      locator: "DOI: 10.1016/j.rse.2013.12.008",
    },
    {
      cite: "Sofiev, M., & Kouznetsov, R. (2026)",
      title: "Inter-calibration of MODIS and VIIRS active fire radiative power detections",
      detail: "Quantifies MODIS 3.7–40 MW vs. VIIRS 0.5 MW minimum detection floors, demonstrating why low-intensity agricultural burning requires regime-specific rather than constant scaling.",
      locator: "NASA FIRMS Bibliography & Workspace Reference",
    },
    {
      cite: "Wooster, M. J., Roberts, G., Perry, G. L. W., & Kaufman, Y. J. (2005)",
      title: "Retrieval of biomass combustion rates and totals from fire radiative power observations",
      detail: "Journal of Geophysical Research, 110, D24311. Establishes MIR-radiance FRP linearity replacing nonlinear Stefan-Boltzmann T4^8 retrievals used in MODIS C5.",
      locator: "DOI: 10.1029/2005JD006318",
    },
    {
      cite: "Justice, C. O., Giglio, L., Roy, D., Boschetti, L., Csiszar, I., et al. (2011 / 2002)",
      title: "MODIS & VIIRS Land Active Fire Product Algorithm Heritage",
      detail: "Foundational Collection 4–6 contextual fire detection heritage, EOS Rapid Response genesis (2001), and transition to VIIRS C2 (User Guide v1.2, May 2025; MODIS C6/C6.1 User Guide v1.0, 2021).",
      locator: "NASA Earthdata FIRMS User Guides",
    },
    {
      cite: "NASA FIRMS / LANCE / ESDIS & C08 Challenge Brief (CONAE / Marina Compagnucci, 2026)",
      title: "Official Challenge Brief, Data Disclaimers & MODIS/VIIRS Calibration Documentation",
      detail: "Defines C08 burning activity calendar objectives (compare median & mean, highlight peak months/years, serve emergency responders, land managers, and scientists) and mandatory FIRMS/ESDIS/LANCE attribution.",
      locator: "NASA Space Apps C08 Official Portal & Earthdata FIRMS",
    },
  ];

  // Live UI state bound cleanly via SeamScience.sync(...)
  const STATE = {
    result: null,
    calMode: "heatmap",
    calSrc: "H",
    compareYear: null,
    meta: null,
    nav: null,
    activeRole: "land_manager",
  };

  function $(id) {
    return typeof document === "undefined" ? null : document.getElementById(id);
  }

  function dispatchAction(act) {
    if (!act) return;
    if (act.calMode) STATE.calMode = act.calMode;
    const nav = STATE.nav;
    if (nav && typeof nav.go === "function") {
      nav.go(act.ws, { sub: act.sub, ev: act.ev, focus: true });
      if (act.calMode) applyCalendarMode();
      return;
    }
    const wsBtn = document.querySelector(`#ws-nav button[data-ws="${act.ws}"]`);
    if (wsBtn) wsBtn.click();
    if (act.sub) {
      const subBtn = document.querySelector(`#ws-calendar [data-sub="${act.sub}"]`);
      if (subBtn) subBtn.click();
    }
    if (act.ev) {
      const evBtn = document.querySelector(`#ev-nav button[data-ev="${act.ev}"]`);
      if (evBtn) evBtn.click();
    }
    if (act.calMode) applyCalendarMode();
  }

  function renderProfileSvg(clim, compareYear) {
    const W = 740, H = 264, L = 58, R = 18, T = 26, B = 38;
    const cw = W - L - R, ch = H - T - B;
    const maxY = Math.max(
      1,
      ...clim.map((m) => Math.max(
        m.p75 || 0,
        m.mean || 0,
        m.median || 0,
        m.selectedValue != null ? m.selectedValue : 0
      ))
    );
    const xAt = (i) => L + ((i + 0.5) / 12) * cw;
    const yAt = (v) => T + ch - (Math.min(maxY, Math.max(0, v)) / maxY) * ch;

    const cInk = cssVar("--ink", "#172026");
    const cMuted = cssVar("--muted", "#5b6770");
    const cLine = cssVar("--line", "#d7dfe4");
    const cAqua = cssVar("--aqua", "#0c7c94");
    const cSnpp = cssVar("--snpp", "#b8431b");
    const cAccent = cssVar("--accent", "#c94c1f");
    const font = cssVar("--font", "system-ui, sans-serif").replace(/"/g, "'");

    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="12-month seasonal profile showing interquartile range, historical median, historical mean, and ${compareYear || "selected year"}">`;
    // Horizontal gridlines
    for (let k = 0; k <= 4; k++) {
      const val = (maxY * k) / 4;
      const y = yAt(val);
      s += `<line x1="${L}" y1="${y.toFixed(1)}" x2="${W - R}" y2="${y.toFixed(1)}" stroke="${cLine}" stroke-width="${k === 0 ? 1.4 : 0.8}"/>`;
      s += `<text x="${L - 8}" y="${(y + 4).toFixed(1)}" text-anchor="end" style="font:500 11px ${font};fill:${cMuted}">${esc(fmtNum(val, maxY < 20 ? 1 : 0))}</text>`;
    }

    // P25-P75 shaded ribbon
    const validBands = clim.filter((m) => m.p25 != null && m.p75 != null);
    if (validBands.length >= 2) {
      const upper = clim.map((m, i) => m.p75 != null ? `${xAt(i).toFixed(1)},${yAt(m.p75).toFixed(1)}` : null).filter(Boolean);
      const lower = clim.map((m, i) => m.p25 != null ? `${xAt(i).toFixed(1)},${yAt(m.p25).toFixed(1)}` : null).filter(Boolean).reverse();
      s += `<polygon points="${upper.concat(lower).join(" ")}" fill="${cAqua}" opacity="0.16"/>`;
    }

    // Median polyline (solid)
    const medPts = clim.map((m, i) => m.median != null ? `${xAt(i).toFixed(1)},${yAt(m.median).toFixed(1)}` : null).filter(Boolean);
    if (medPts.length >= 2) {
      s += `<polyline fill="none" stroke="${cAqua}" stroke-width="2.5" points="${medPts.join(" ")}"/>`;
    }

    // Mean polyline (dashed)
    const meanPts = clim.map((m, i) => m.mean != null ? `${xAt(i).toFixed(1)},${yAt(m.mean).toFixed(1)}` : null).filter(Boolean);
    if (meanPts.length >= 2) {
      s += `<polyline fill="none" stroke="${cSnpp}" stroke-width="2.2" stroke-dasharray="6 4" points="${meanPts.join(" ")}"/>`;
    }

    // Points + Month labels
    clim.forEach((m, i) => {
      const cx = xAt(i);
      if (m.median != null) {
        s += `<circle cx="${cx.toFixed(1)}" cy="${yAt(m.median).toFixed(1)}" r="3.4" fill="${cAqua}"><title>${esc(m.fullName)} median: ${fmtNum(m.median, 1)} (${m.n} yr)</title></circle>`;
      }
      if (m.mean != null) {
        s += `<rect x="${(cx - 2.6).toFixed(1)}" y="${(yAt(m.mean) - 2.6).toFixed(1)}" width="5.2" height="5.2" fill="${cSnpp}"><title>${esc(m.fullName)} mean: ${fmtNum(m.mean, 1)} (${m.n} yr)</title></rect>`;
      }
      if (m.selectedValue != null) {
        const cy = yAt(m.selectedValue);
        const partial = !!m.selectedFlag;
        s += `<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="4.6" fill="${partial ? "transparent" : cAccent}" stroke="${cInk}" stroke-width="1.6"><title>${esc(m.fullName)} ${compareYear}: ${fmtNum(m.selectedValue, 1)}${partial ? " (" + m.selectedFlag + ")" : ""}</title></circle>`;
      }
      s += `<text x="${cx.toFixed(1)}" y="${H - 12}" text-anchor="middle" style="font:600 11px ${font};fill:${cMuted}">${esc(m.name)}</text>`;
    });

    // Top-right compact legend inside SVG
    s += `<text x="${L}" y="15" style="font:600 11.5px ${font};fill:${cMuted}">Median (solid) vs. Mean (dashed) · Shaded P25–P75 IQR${compareYear ? " · Circles = " + esc(compareYear) : ""}</text>`;
    s += `</svg>`;
    return s;
  }

  function renderProfileView() {
    const box = $("cal-profile");
    if (!box || !STATE.result) return;
    const srcSel = $("cal-src");
    const src = srcSel ? srcSel.value : STATE.calSrc;
    const cells = STATE.result.calendar && STATE.result.calendar[src];
    if (!cells || !cells.length) {
      box.innerHTML = `<p class="note">No calendar series loaded for this selection.</p>`;
      return;
    }

    const years = Array.from(new Set(cells.map((c) => Number(c.year)))).sort((a, b) => a - b);
    const cyEl = $("cy");
    const defaultYr = (cyEl && years.includes(Number(cyEl.value))) ? Number(cyEl.value) : years[years.length - 1];
    if (!STATE.compareYear || !years.includes(Number(STATE.compareYear))) {
      STATE.compareYear = defaultYr;
    }

    const clim = calendarClimatology(cells, STATE.compareYear);
    const peaks = summarizePeakMonths(clim);
    const peakList = peaks.topMedian.length
      ? peaks.topMedian.map((m) => `${m.name} (med ${fmtNum(m.median, 1)} / mean ${fmtNum(m.mean, 1)})`).join(" · ")
      : "No complete unflagged baseline months";
    const singlePeak = peaks.maxMonth && peaks.maxMonth.max != null
      ? `${peaks.maxMonth.fullName} ${peaks.maxMonth.maxYear} (${fmtNum(peaks.maxMonth.max, 1)} detections)`
      : "none";
    const skewMsg = peaks.episodic.length
      ? `Right-skewed episodic burn months (Mean >= 1.25× Median): ${peaks.episodic.slice(0, 4).map((m) => `${m.name} (${m.skewRatio.toFixed(2)}×)`).join(", ")}.`
      : "Mean closely tracks Median across complete baseline months (low single-year outlier skew).";

    const yearOptions = years.map((y) => `<option value="${y}"${y === Number(STATE.compareYear) ? " selected" : ""}>${y}</option>`).join("");

    box.innerHTML = `
      <div class="sci-profile-bar">
        <div class="sci-peaks">
          <div><b>Typical Peak Months (Median):</b> ${esc(peakList)}</div>
          <div class="note"><b>Highest single month:</b> ${esc(singlePeak)} · ${esc(skewMsg)}</div>
        </div>
        <div class="sci-profile-ctrl">
          <label class="inline">Overlay year <select id="sci-prof-year">${yearOptions}</select></label>
          <button type="button" class="btn" id="sci-prof-csv">Seasonal summary (CSV)</button>
        </div>
      </div>
      <div class="chart">${renderProfileSvg(clim, STATE.compareYear)}</div>
      <div class="table-wrap">
        <table class="daily sci-table">
          <thead>
            <tr>
              <th>Month</th>
              <th>Complete yrs</th>
              <th>Median</th>
              <th>Mean</th>
              <th>IQR (P25–P75)</th>
              <th>Record high (yr)</th>
              <th>${esc(STATE.compareYear)}</th>
            </tr>
          </thead>
          <tbody>
            ${clim.map((m) => `
              <tr>
                <td><b>${esc(m.fullName)}</b></td>
                <td>${m.n}${m.partialCount ? ` <span class="note">(${m.partialCount} partial excl.)</span>` : ""}</td>
                <td>${m.median == null ? "–" : fmtNum(m.median, 1)}</td>
                <td>${m.mean == null ? "–" : fmtNum(m.mean, 1)}</td>
                <td>${(m.p25 != null && m.p75 != null) ? `${fmtNum(m.p25, 1)}–${fmtNum(m.p75, 1)}` : "–"}</td>
                <td>${m.max == null ? "–" : `${fmtNum(m.max, 1)} (${m.maxYear})`}</td>
                <td>${m.selectedValue == null ? "–" : `${fmtNum(m.selectedValue, 1)}${m.selectedFlag ? ` <span class="note">[${esc(m.selectedFlag)}]</span>` : ""}`}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>
      <p class="note">Historical Mean, Median, and P25–P75 IQR exclude flagged partial or incomplete coverage months (such as partial 2026) so incomplete passes never depress historical climatology. Satellite hotspot detections only — not burned area or fire counts.</p>
    `;
  }

  function applyCalendarMode() {
    const seg = $("cal-mode-seg");
    const calEl = $("calendar");
    const legEl = $("cal-legend");
    const detEl = $("cal-detail-month");
    const tblBtn = $("cal-table-btn");
    const tblEl = $("cal-table");
    const profEl = $("cal-profile");
    if (!profEl || !calEl) return;
    const isProf = STATE.calMode === "profile";
    if (seg) {
      for (const b of seg.querySelectorAll("button")) {
        b.setAttribute("aria-pressed", String(b.dataset.calMode === STATE.calMode));
      }
    }
    calEl.hidden = isProf;
    if (legEl) legEl.hidden = isProf;
    if (detEl) detEl.hidden = isProf;
    if (tblEl && isProf) tblEl.hidden = true;
    if (tblBtn) tblBtn.hidden = isProf;
    profEl.hidden = !isProf;
    if (isProf) renderProfileView();
  }

  function renderNormalSummary() {
    const pane = $("pane-normal");
    if (!pane || !STATE.result) return;
    let host = $("normal-mean-summary");
    if (!host) {
      host = document.createElement("div");
      host.id = "normal-mean-summary";
      host.className = "sci-callout panel";
      pane.appendChild(host);
    }
    const srcSel = $("cal-src");
    const src = srcSel ? srcSel.value : "H";
    const cells = STATE.result.calendar && STATE.result.calendar[src];
    if (!cells) { host.innerHTML = ""; return; }
    const cmEl = $("cm"), cyEl = $("cy");
    const mo = cmEl ? Number(cmEl.value) : 11;
    const yr = cyEl ? Number(cyEl.value) : 2025;
    const clim = calendarClimatology(cells, yr);
    const cur = clim[mo - 1];
    const peaks = summarizePeakMonths(clim);
    const peakText = peaks.topMedian.map((m) => `${m.name} (med ${fmtNum(m.median, 1)} / mean ${fmtNum(m.mean, 1)})`).join(" · ");
    host.innerHTML = `
      <div><b>Climatological context — ${esc(MONTH_NAME(mo))} (${esc(srcSel ? srcSel.selectedOptions[0].text : src)})</b></div>
      <div class="note">
        ${cur && cur.n >= 3
          ? `Across ${cur.n} complete baseline years: <b>Median</b> ${fmtNum(cur.median, 1)} · <b>Mean</b> ${fmtNum(cur.mean, 1)} · <b>IQR (P25–P75)</b> ${fmtNum(cur.p25, 1)}–${fmtNum(cur.p75, 1)} · <b>Range</b> ${fmtNum(cur.min, 1)}–${fmtNum(cur.max, 1)} (peak ${cur.maxYear}). `
          : `Fewer than 3 complete unflagged years in ${esc(MONTH_NAME(mo))} for this series. `}
        ${cur && cur.skewRatio != null && cur.skewRatio >= 1.25
          ? `Extreme high-fire years pull the arithmetic Mean ${cur.skewRatio.toFixed(2)}× above the Median.`
          : ""}
      </div>
      <div class="note"><b>Top peak months across full cycle:</b> ${esc(peakText || "Unavailable")}</div>
    `;
  }

  function MONTH_NAME(m) {
    return MONTHS_FULL[(Number(m) || 1) - 1] || String(m);
  }

  function roleCardsHtml(activeId) {
    return `
      <div class="sci-roles-grid">
        ${ROLE_PLAYBOOKS.map((r) => `
          <article class="sci-role-card${r.id === activeId ? " is-active" : ""}">
            <div class="sci-role-head">
              <h3>${esc(r.title)}</h3>
              <span class="badge">${esc(r.badge)}</span>
            </div>
            <p>${esc(r.goal)}</p>
            <ol>${r.steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol>
            <p class="note">${esc(r.note)}</p>
            <div class="btn-row">
              ${r.actions.map((a, idx) => `<button type="button" class="${idx === 0 ? "btn-primary" : "btn"}" data-sci-act="${esc(JSON.stringify(a))}">${esc(a.label)}</button>`).join("")}
            </div>
          </article>`).join("")}
      </div>
    `;
  }

  function openRolesDialog(opener) {
    const html = `
      <p class="note">Choose a workflow tailored to the three core NASA Space Apps C08 audiences. All guidance honors frozen scientific rules and official LANCE/FIRMS caveats.</p>
      ${roleCardsHtml(STATE.activeRole)}
    `;
    if (typeof window !== "undefined" && window.Seam && typeof window.Seam.openDialog === "function") {
      const body = window.Seam.openDialog("Workflow guides by user role", html, opener);
      if (body) {
        body.addEventListener("click", (e) => {
          const btn = e.target.closest("[data-sci-act]");
          if (!btn) return;
          const act = JSON.parse(btn.dataset.sciAct);
          const closeBtn = $("dialog-close");
          if (closeBtn) closeBtn.click();
          else {
            const dlg = $("dialog"), shade = $("dialog-shade");
            if (dlg) dlg.hidden = true;
            if (shade) shade.hidden = true;
          }
          dispatchAction(act);
        });
      }
      return;
    }
    dispatchAction({ ws: "evidence", ev: "science" });
  }

  function renderScience() {
    const host = $("science-body");
    if (!host) return;
    host.innerHTML = `
      <p class="note">All numbers below trace directly to peer-reviewed NASA FIRMS publications and User Guides (MODIS Collection 6/6.1 and VIIRS Collection 2, 375 m). External reference links open only if clicked; every calculation and view in Seamline works offline.</p>

      <h3 class="sci-h">1. Workflows by Challenge Audience</h3>
      ${roleCardsHtml(STATE.activeRole)}

      <h3 class="sci-h">2. MODIS vs. VIIRS Sensor Physics &amp; Detection Floor Comparison</h3>
      <div class="table-wrap">
        <table class="daily sci-table">
          <thead>
            <tr>
              <th>Property</th>
              <th>MODIS (Terra &amp; Aqua — ~1 km)</th>
              <th>VIIRS (S-NPP, NOAA-20, NOAA-21 — 375 m)</th>
            </tr>
          </thead>
          <tbody>
            ${SENSORS_SPEC.map((row) => `
              <tr>
                <td><b>${esc(row.feature)}</b></td>
                <td>${esc(row.modis)}</td>
                <td>${esc(row.viirs)}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>

      <h3 class="sci-h">3. Why Naive Multi-Sensor Fixes Fail vs. Seamline Guardrails</h3>
      <div class="table-wrap">
        <table class="daily sci-table">
          <thead>
            <tr>
              <th>Common Harmonization Shortcut</th>
              <th>Why Physics &amp; Sampling Reject It</th>
              <th>How Seamline Enforces Scientific Validity</th>
            </tr>
          </thead>
          <tbody>
            ${PITFALLS.map((p) => `
              <tr>
                <td><b>${esc(p.pitfall)}</b></td>
                <td>${esc(p.whyFails)}</td>
                <td>${esc(p.seamline)}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>

      <h3 class="sci-h">4. Primary NASA FIRMS &amp; Peer-Reviewed Citations</h3>
      <ul class="sci-refs">
        ${LITERATURE_REFS.map((ref) => `
          <li>
            <b>${esc(ref.cite)}</b> — <i>${esc(ref.title)}</i>. ${esc(ref.detail)}
            <span class="note">(${esc(ref.locator)})</span>
          </li>`).join("")}
      </ul>
    `;
  }

  function exportProfileCsv() {
    if (!STATE.result) return;
    const srcSel = $("cal-src");
    const src = srcSel ? srcSel.value : "H";
    const cells = STATE.result.calendar && STATE.result.calendar[src];
    if (!cells) return;
    const clim = calendarClimatology(cells, STATE.compareYear);
    const csv = climatologyCsv(clim, {
      series: src,
      region: STATE.result.region,
      model: STATE.result.request && STATE.result.request.model,
      data_identity: STATE.result.data_identity || (STATE.meta && STATE.meta.data_identity) || "",
    });
    const safeRegion = String(STATE.result.region || "area").replace(/\W+/g, "_");
    const fname = `seamline_${safeRegion}_${src}_seasonal_climatology.csv`;
    const blob = new Blob([csv], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = fname;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      URL.revokeObjectURL(a.href);
      a.remove();
    }, 5000);
    if (STATE.nav && typeof STATE.nav.toast === "function") {
      STATE.nav.toast(`Saved ${fname}: derived Jan–Dec median, mean, IQR, and ${STATE.compareYear || "selected"} overlay.`);
    }
  }

  function wireDom() {
    if (typeof document === "undefined") return;
    renderScience();

    document.addEventListener("click", (e) => {
      const modeBtn = e.target.closest("#cal-mode-seg button[data-cal-mode]");
      if (modeBtn) {
        STATE.calMode = modeBtn.dataset.calMode;
        applyCalendarMode();
        return;
      }
      if (e.target.closest("#roles-btn") || e.target.closest("#science-roles-btn")) {
        openRolesDialog(e.target.closest("button"));
        return;
      }
      if (e.target.closest("#sci-prof-csv")) {
        exportProfileCsv();
        return;
      }
      const sciBtn = e.target.closest("#science-body [data-sci-act]");
      if (sciBtn) {
        dispatchAction(JSON.parse(sciBtn.dataset.sciAct));
      }
    });

    document.addEventListener("change", (e) => {
      if (e.target && e.target.id === "cal-src") {
        STATE.calSrc = e.target.value;
        if (STATE.calMode === "profile") renderProfileView();
        renderNormalSummary();
      } else if (e.target && e.target.id === "sci-prof-year") {
        STATE.compareYear = Number(e.target.value);
        renderProfileView();
      }
    });
  }

  function sync(result, ctx) {
    STATE.result = result || STATE.result;
    if (ctx) {
      if (ctx.calSrc) STATE.calSrc = ctx.calSrc;
      if (ctx.META) STATE.meta = ctx.META;
      if (ctx.go) STATE.nav = ctx;
    }
    if (STATE.calMode === "profile") renderProfileView();
    renderNormalSummary();
  }

  const API = {
    calendarClimatology,
    cellStats,
    summarizePeakMonths,
    climatologyCsv,
    ROLE_PLAYBOOKS,
    SENSORS_SPEC,
    PITFALLS,
    LITERATURE_REFS,
    sync,
    renderScience,
    openRolesDialog,
  };

  if (typeof window !== "undefined") {
    window.SeamScience = API;
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", wireDom);
    } else {
      wireDom();
    }
  }
  if (typeof module !== "undefined" && module.exports) {
    module.exports = API;
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
