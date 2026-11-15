"""Methods and evidence report: reports/c08/methods_report.html (+ .pdf via Edge, if installed).

python -m c08.report

Every number is read from the saved experiment and ingest files at build time,
so the report cannot drift from the evidence. Figures come from c08.figures.
"""
from __future__ import annotations

import base64
import html
import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from . import analysis, config

OUT_HTML = config.REPORTS / "methods_report.html"
OUT_PDF = config.REPORTS / "methods_report.pdf"
EDGE = (Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"))


def _load(rel: str) -> dict:
    return json.loads((config.ROOT / rel).read_text(encoding="utf-8"))


def _img(name: str, alt: str) -> str:
    data = base64.b64encode((config.REPORTS / "figures" / name).read_bytes()).decode()
    return f'<figure><img src="data:image/png;base64,{data}" alt="{html.escape(alt)}"><figcaption>{html.escape(alt)}</figcaption></figure>'


def pct(v: float, d: int = 1) -> str:
    return f"{v * 100:.{d}f}%"


def sgn(v: float, d: int = 1) -> str:
    return f"{v * 100:+.{d}f}%".replace("-", "−")


e = html.escape
MON = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
PROVS = ("Punjab", "Sindh", "Khyber Pakhtunkhwa")
SATS = {"SNPP": "S-NPP", "NOAA20": "NOAA-20", "NOAA21": "NOAA-21", "Aqua": "Aqua"}


def _p(p: float, splits: int | None) -> str:
    """A whole-year permutation p: the smallest possible value as a fraction (1/35), others as decimals."""
    return f"1/{splits}" if splits and abs(p * splits - 1) < 1e-9 else f"{p:.2f}"


def _per100(r: float | None) -> str:
    return "–" if r is None else f"{100 * r:.2f}"


def _g01_table(g01: dict) -> str:
    """Terra ÷ S-NPP day-pass detections (per 100) by year, October-November, with eligibility and the tests."""
    cols = [("Punjab", g01["development_area"]["Punjab"], "Punjab (development area)")] + \
           [(p, g01["provinces"][p], p) for p in ("Sindh", "Khyber Pakhtunkhwa")]
    years = sorted({int(y) for _, v, _ in cols for y in v["years"]})
    rows, reasons = [], {}
    for y in years:
        cells = []
        for name, v, _ in cols:
            o = v["years"][str(y)]["OctNov"]
            if o["eligible"]:
                cells.append(f"<td>{_per100(o['R'])}</td>")
            else:
                cells.append(f'<td class="muted">({_per100(o["R"])})</td>')
                who = f"{'KP' if name == 'Khyber Pakhtunkhwa' else name} {y}"
                if "days matched" in o["exclusion"]:
                    reasons.setdefault(f"too few days matched ({o['days_matched']} of {o['days_in_window']}, "
                                       f"{o['days_needed']} needed)", []).append(who)
                if "below 300" in o["exclusion"] or "below 20" in o["exclusion"]:
                    reasons.setdefault("too few detections (S-NPP below 300, or expected Terra below 20)", []).append(who)
        rows.append(f"<tr><td>{y}</td>{''.join(cells)}</tr>")
    def stat(v: dict) -> tuple[str, str, str]:
        f = v["fall"]
        if f["status"] == "not_testable":
            return "–", "–", f"not testable ({e(f['reason'])})"
        return (_per100(f["mean_R_before"]), _per100(f["mean_R_after"]),
                f"{sgn(f['delta'], 0)}, p = {_p(f['p'], f['splits'])}")
    st = [stat(v) for _, v, _ in cols]
    rows.append("<tr class='sep'><td>Mean, eligible 2018–21</td>" + "".join(f"<td>{a}</td>" for a, _, _ in st) + "</tr>")
    rows.append("<tr><td>Mean, eligible 2023–25</td>" + "".join(f"<td>{b}</td>" for _, b, _ in st) + "</tr>")
    rows.append("<tr><td><b>Fall test</b></td>" + "".join(f"<td><b>{c}</b></td>" for _, _, c in st) + "</tr>")
    step = []
    for _, v, _ in cols:
        s = v["step"]
        step.append(f"{s['ratio_to_mean']:.2f}× the mean; present" if s["status"] == "present"
                    else f"not testable ({e(s['reason'].split(' (')[0])})" if s["status"] == "not_testable" else e(s["status"]))
    rows.append("<tr><td><b>Step, November 2022</b></td>" + "".join(f"<td>{t}</td>" for t in step) + "</tr>")
    head = "<tr><th>Year (October–November)</th>" + "".join(f"<th>{e(lab)}</th>" for _, _, lab in cols) + "</tr>"
    why = "; ".join(f"{e(k)}: {', '.join(v)}" for k, v in reasons.items())
    rem = sorted(g01["development_area"]["Punjab"]["years"]["2022"]["OctNov"]["days_removed"])
    gap = f" The days removed in 2022 are {int(rem[0][8:])}–{int(rem[-1][8:])} October, when FIRMS lists Terra as missing." if rem else ""
    return (f'<table class="p04"><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table>'
            f'<p class="note">Terra detections per 100 S-NPP detections, day passes, summed over the days both satellites '
            f'were observing. In brackets, not eligible: {why}.{gap}</p>')


def _gaps(years: dict) -> tuple[int | None, int | None]:
    ok = [v for v in years.values() if v.get("eligible") and v.get("d_mid") is not None]
    if not ok:
        return None, None
    return max(abs(v["d_mid"]) for v in ok), max(abs(v["d_end"]) for v in ok)


def _g02_table(g02: dict) -> str:
    out = []
    for prov in PROVS:
        for win, wname in (("rice", "rice"), ("spring", "spring")):
            for pair in ("NOAA20-SNPP", "Aqua-SNPP"):
                sat = SATS[pair.split("-")[0]]
                if prov == "Punjab" and win == "rice":
                    r = g02["development_area"]["Punjab"]["rice"][pair]
                    gm, ge = _gaps(r["years"])
                    out.append(f"<tr class='muted'><td>{prov}</td><td class='l'>{wname}</td><td class='l'>{sat}</td>"
                               f"<td>{len(r['eligible_years'])}</td><td>–</td><td>{gm} / {ge}</td>"
                               f"<td class='l'>development area: dates seen before the test, not tested</td></tr>")
                    continue
                r = g02["results"][prov][win][pair]
                n = len(r["eligible_years"])
                gm, ge = _gaps(r["years"]) if n else (None, None)
                gap = f"{gm} / {ge}" if gm is not None else "–"
                if r["status"] == "not_testable":
                    miss, outcome = "–", f"not testable ({e(r['reason'])})"
                else:
                    miss = f"{r['middle_misses']} / {r['end_misses']} ({r['misses_allowed']} allowed)"
                    outcome = "<b>holds</b>" if r["status"] == "holds" else "<b>fails</b>"
                out.append(f"<tr><td>{prov}</td><td class='l'>{wname}</td><td class='l'>{sat}</td><td>{n}</td><td>{miss}</td>"
                           f"<td>{gap}</td><td class='l'>{outcome}</td></tr>")
    head = ("<tr><th>Province</th><th class='l'>Season</th><th class='l'>Against S-NPP</th><th>Eligible years</th>"
            "<th>Years outside, middle / end</th><th>Largest gap, middle / end (matched days)</th><th class='l'>Outcome</th></tr>")
    return f'<table class="p04"><thead>{head}</thead><tbody>{"".join(out)}</tbody></table>'


def _g03_table(g03: dict) -> str:
    rows = []
    skipped = {m["month"]: m for m in g03["months_not_scored"]}
    scored = {m["month"]: m for m in g03["months"]}
    months = sorted(set(scored) | set(skipped))
    for ym in months:
        name = MON[int(ym[5:7]) - 1]
        if ym in skipped:
            m = skipped[ym]
            rows.append(f"<tr class='muted'><td>{name}</td><td class='l'>{m['stream']}</td><td>{m['matched_days']}</td>"
                        f"<td colspan='5' class='l'>not scored: {e(m['reason'])}</td></tr>")
            continue
        m = scored[ym]
        held = "yes" if m["held_to_month_rule"] else "no (under 300 S-NPP)"
        rows.append(f"<tr><td>{name}</td><td class='l'>{m['stream']}</td><td>{m['matched_days']}</td><td>{m['observed_snpp']:,}</td>"
                    f"<td>{m['predicted']:,.0f}</td><td>{sgn(m['error'])}</td><td>{sgn(m['m0_error'])}</td><td>{held}</td></tr>")
    head = (f"<tr><th>Month ({months[0][:4]})</th><th class='l'>Stream</th><th>Matched days</th><th>S-NPP observed</th>"
            "<th>NOAA-20 converted</th><th>Error</th><th>No conversion (M0)</th><th>Held to the 20% rule</th></tr>")
    return f'<table class="p04"><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table>'


def _g04_tables(g04: dict) -> str:
    t, s, n = g04["test_counts_all_rows"], g04["sum"], g04["snpp"]
    yn = lambda b: "yes" if b else "no"
    test = (f"<tr><td>S-NPP</td><td>{t['SNPP']:,}</td><td>{n['target']:,}</td><td>{yn(n['within'])}</td></tr>"
            f"<tr><td>NOAA-20</td><td>{t['NOAA20']:,}</td><td>–</td><td>–</td></tr>"
            f"<tr><td>NOAA-21</td><td>{t['NOAA21']:,}</td><td>–</td><td>–</td></tr>"
            f"<tr><td><b>Sum of the three</b></td><td><b>{s['value']:,}</b></td><td>{s['target']:,}</td><td>{yn(s['within'])}</td></tr>")
    per, fl = g04["per_satellite"], g04["satellites_flying"]
    demo = "".join(f"<tr><td>{y}</td>" + "".join(
        f"<td>{per[y][k]:,}</td>" if k in per[y] else "<td>not flying</td>" for k in ("SNPP", "NOAA20", "NOAA21"))
        + f"<td>{fl[y]}</td></tr>" for y in sorted(per))
    return (f'<table class="p04"><thead><tr><th>The test: 1–29 Oct 2026, all rows</th><th>Our count</th><th>Press figure</th>'
            f'<th>Within ±20%</th></tr></thead><tbody>{test}</tbody></table>'
            f'<table class="p04"><thead><tr><th>Demonstration: 1–29 Oct, quality rule</th><th>S-NPP</th><th>NOAA-20</th>'
            f'<th>NOAA-21</th><th>VIIRS satellites flying</th></tr></thead><tbody>{demo}</tbody></table>')


def build() -> Path:
    ing = _load("reports/c08/ingest_report.json")
    e00 = _load("experiments/E00_first_run/result.json")
    e01 = _load("experiments/E01_selection/result.json")
    e02 = _load("experiments/E02_evaluation/result.json")
    e03 = _load("experiments/E03_sensitivity/result.json")
    rep = _load("reports/c08/reproduction_check.json")
    f01 = _load("experiments/P02_F01_camera/result.json")
    f02 = _load("experiments/P02_F02_clock/result.json")
    f03 = _load("experiments/P02_F03_burned_area/result.json")
    post = _load("reports/c08/p02_posthoc.json")
    g01 = _load("experiments/P04_G01_terra_step/result.json")
    g02 = _load("experiments/P04_G02_season_dates/result.json")
    g03 = _load("experiments/P04_G03_bridge_2026/result.json")
    g04 = _load("experiments/P04_G04_headline/result.json")
    sel, br = e01["backcast"], e01["bridge"]
    tt = e02["temporal_test"]
    dif = e02["differentiator"]
    std_rows = sum(f["raw_rows"] for f in ing["files"] if f["stream"] == "standard")

    def score_rows(scores: dict, test: dict | None = None) -> str:
        out = []
        for m, s in scores.items():
            t = test.get(m) if test else None
            mark = " (selected)" if m == sel["selected"] else ""
            out.append(f"<tr><td>{m}{mark}</td><td>{pct(s['wape'])}</td><td>{s['log_mae']:.3f}</td><td>{sgn(s['bias'])}</td>"
                       f"<td>{pct(t['wape']) if t else '–'}</td></tr>")
        return "".join(out)

    drift = "".join(f"<tr><td>{y}</td><td>{', '.join(v['aqua_versions'])}</td><td>{sgn(v['M1']['bias'])}</td>"
                    f"<td>{sgn(v['M2']['bias'])}</td><td>{pct(v['M2']['wape'])}</td></tr>"
                    for y, v in e02["drift_diagnostic"].items())

    def dif_row(season: str, label: str) -> str:
        v = dif[season]
        iv = v["harmonised_interval"]["ratio_late_early"]
        return (f"<tr><td>{label}</td><td>{v['naive_stitch']['ratio_late_early']:.2f}×</td>"
                f"<td>{v['aqua_only']['ratio_late_early']:.2f}×</td>"
                f"<td><b>{v['harmonised']['ratio_late_early']:.2f}×</b> ({iv['lo']:.2f}–{iv['hi']:.2f})</td>"
                f"<td>{'supported' if v['claim_raw_exaggerates_change'] else 'not supported'}</td></tr>")

    sens = "".join(
        f"<tr><td>{m}</td>" + "".join(
            f"<td>{v[s]['ratio_late_early']:.2f}× ({v[s]['ratio_interval'][0]:.2f}–{v[s]['ratio_interval'][1]:.2f})</td>"
            for s in ("OctNov", "AprMay")) + "</tr>"
        for m, v in e03["by_model"].items())
    sindh = e02["geographic_test_sindh"]
    sens_on = [v["OctNov"]["ratio_late_early"] for v in e03["by_model"].values()]
    naive_snpp = analysis.analyse(region="Punjab", model=sel["selected"])["change"]["OctNov"]["naive_snpp"]
    built = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")

    # Protocol P02 (3 Nov), for context: the camera model, the clock test and burned area.
    p2_terra, p2_aqua = (f02["results"]["periods"]["OctNov"]["delta"][s] for s in ("Terra", "Aqua"))
    p2_pt, p2_pa = (post["D2"][s]["permutation_OctNov"]["p_two_sided"] for s in ("Terra", "Aqua"))
    # Protocol P04 (8 Nov): the four result files.
    files26 = g03["inputs"]["raw_2026_files"]
    by_src: dict[str, int] = {}
    for f in files26:
        by_src[f["source"]] = by_src.get(f["source"], 0) + 1
    streams = g03["stream_by_month"]
    sp_months = [m for m, s in streams.items() if s == "SP"]
    nrt_months = [m for m, s in streams.items() if s == "NRT"]
    mname = lambda ym: f"{MON[int(ym[5:7]) - 1]}"
    worst = sorted(g03["months"], key=lambda m: -abs(m["error"]))[:2]
    rp = g03["reported"]
    sd, kp = g01["provinces"]["Sindh"], g01["provinces"]["Khyber Pakhtunkhwa"]
    pj = g01["development_area"]["Punjab"]
    pjs = g02["results"]["Punjab"]["spring"]["Aqua-SNPP"]
    n20 = {(p, w): g02["results"][p][w]["NOAA20-SNPP"] for p in g02["results"] for w in g02["results"][p]}
    n20_hold = [f"{p} ({w})" for (p, w), r in n20.items() if r["status"] == "holds"]
    hold_by: dict[str, list[str]] = {}
    for (p, w), r in n20.items():
        if r["status"] == "holds":
            hold_by.setdefault(p, []).append(w)
    n20_hold_txt = ", ".join(f"{p} ({' and '.join(ws)})" for p, ws in hold_by.items())
    moved = lambda v: f"{'rose' if v >= 0 else 'fell'} {pct(abs(v), 0)}"
    n20_nt = [f"{p} ({w}; {r['reason']})" for (p, w), r in n20.items() if r["status"] == "not_testable"]
    # NOAA-20's "holds" uses the one outside year in five the rule allows; name those years (REVIEW_P04-RUN, R4).
    n20_miss = [f"{p} {w} {y}" for (p, w), r in n20.items() if r["status"] == "holds" for y in r["eligible_years"]
                if abs(r["years"][str(y)]["d_mid"]) > 3 or abs(r["years"][str(y)]["d_end"]) > 4]
    n20_miss_txt = f", except in {', '.join(n20_miss)}, which the rule allows" if n20_miss else ""
    # The largest miss among held months, beside the pass (REVIEW_P04-RUN, R5).
    g03_held = [m for m in g03["months"] if m.get("held_to_month_rule")]
    g03_close = max(g03_held, key=lambda m: abs(m["error"])) if g03_held else None
    rng = g04["snpp_range_2018_2025"]
    gaps = g04["gap_days"]
    one_pass = "; ".join(f"{SATS[k]} {', '.join(str(int(d[8:])) for d in v['one_pass_only'])} Oct"
                         for k, v in gaps.items() if v["one_pass_only"])
    approved = g01["approved"].split(" (")[0]
    ptt = post["pass_times"]["by_season"]["Terra"]["OctNov"]
    early = sorted(ptt[str(y)]["median"] for y in range(2018, 2022))
    terra_t0, terra_t1, terra_t25 = early[0], early[-1], ptt["2025"]["median"]
    may_bits = []
    for m in g03["months_not_scored"]:
        d = next(x for x in g03["days_by_month"] if x["month"] == m["month"])
        why = list(d["removed_days"].values())
        every = len(why) == d["days_in_month"] and all("S-NPP is on a FIRMS missing-days list" in w for w in why)
        may_bits.append(f"{MON[int(m['month'][5:7]) - 1]} {m['month'][:4]} was not scored: {m['matched_days']} matched days"
                        + (", because FIRMS lists S-NPP as missing on every day of the month" if every else "") + ".")
    may_text = " ".join(may_bits)

    body = f"""
<header>
<h1>Seamline: putting MODIS and VIIRS fire detections on one scale for Pakistan</h1>
<p class="meta">Methods and evidence report · NASA Space Apps 2026, challenge C08 · Muhammad Hasnain Memon (Karachi), with AI coding assistants · built {built}</p>
<p class="status">Local research prototype. Pre-event work with true dates; not submitted. Agreement is measured against another satellite, not ground truth.</p>
</header>

<h2>1. Question</h2>
<p>Every autumn, during Punjab's smog season, people ask whether the burning seen this year is unusual, and whether it has grown over the decades. NASA FIRMS gives satellite fire detections back to 2000, but the instruments changed. MODIS (Terra 2000–, Aqua 2002–) has 1 km pixels; VIIRS (S-NPP 2012–, NOAA-20 2018–) has 375 m pixels and sees many small patches of burning that MODIS misses. Joining the two records makes burning appear to jump in 2012 because the observing system changed. Seamline puts the record on one declared scale and shows, for any province or rectangle in Pakistan, a seasonal calendar and how a month compares with that area's own normal.</p>
<p>Four newer questions were tested under Protocol P04 (section 7): does this October's press count for Pakistani Punjab reproduce, and how much of its rise since 2019 comes from added satellites? Can NOAA-20 carry the record after S-NPP's end on 2 November 2026? Does Terra's fall in Punjab's autumn share, seen under P02, also appear in Sindh and Khyber Pakhtunkhwa? And do the older and newer satellites agree on the season's middle and end dates (when half, and then 90%, of its detections were in)?</p>

<h2>2. Quantity</h2>
<p><b>H(region, month)</b> = detected burning activity in <b>S-NPP-VIIRS-equivalent detections</b>: the number of quality-filtered S-NPP VIIRS 375 m fire pixels (Collection 2, standard processing; nominal or high confidence; FIRMS type 0) that S-NPP recorded, or is estimated to have recorded, in the region during the UTC month, day and night passes calibrated separately and summed. A detection is one fire pixel on one satellite pass: not a fire, not burned area, not emissions. No detection does not mean no fire: clouds, smoke and gaps between passes hide burning, and a hotspot-only record cannot see it.</p>
<p>Sources: Aqua MODIS converted to S-NPP-equivalent for 2003-01 to 2012-01; observed S-NPP from 2012-02 to 2025-12. {e(g03['seam_label'])}: its data delivery stopped then. NOAA-20 is the bridge: P01 tested it on 2024–25 (total error {pct(e02['bridge_test']['scores']['M1']['wape'])}), and it passed P04's frozen test on January–October 2026 (G03, section 7). By that test's rule, Punjab's record continues on converted NOAA-20 from November 2026, in whole months; other areas show NOAA-20 in its own units ("{e(g03['other_areas_label'])}"). The app's cached record still ends in December 2025, so 2026 months are not yet on its chart.</p>

<h2>3. Data</h2>
<p>{len(ing['files'])} NASA FIRMS files for Pakistan (MODIS MCD14ML 2000–2025, listed by the provider as C6.1, with file versions 6.2, 6.03 and 61.03; VIIRS C2 VNP14IMG 2012–2025 and VJ114IMG 2018–2025; 7-day NRT files of 2 Nov 2026), each with URL, SHA-256 and row count in <code>data/manifest.json</code>; province boundaries from geoBoundaries gbOpen PAK ADM1 (2019). A typed data contract checks platform, coordinates, time, file year, confidence (MODIS 0–100; VIIRS l/n/h), day/night flag, FRP and pixel size, version and type. Result: {std_rows:,} archive rows, {e00['archive_rows_rejected']} rejected, {e00['archive_exact_duplicates']} exact duplicates; {ing['standard_rows_outside_all_provinces']:,} rows (0.85%) lie outside every province polygon along borders. In Punjab every satellite pass falls 05–10 UTC (day) or 16–22 UTC (night), so UTC-day months never split a pass. Months are labelled complete, partial, provider-missing (FIRMS missing-data table) or outside a satellite's record; missing is never shown as zero.</p>
<p>For P04's 2026 tests, {len(files26)} files from the FIRMS area API for Pakistan, in 5-day chunks ({', '.join(f'{v} {e(k)}' for k, v in sorted(by_src.items()))}), each hashed in <code>data/manifest.json</code> without the MAP_KEY, which is stored in no file. FIRMS's availability answer of 8 Nov set the stream: standard (SP) for {mname(sp_months[0])}–{mname(sp_months[-1])} 2026 and near-real-time (NRT, no type field) for {mname(nrt_months[0])}–{mname(nrt_months[-1])}, never mixed within a month. A refreshed missing-days list ({g03['inputs']['missing_days_list_2026']['entries']} entries, 8 Nov) was saved beside the committed one; P01, P02, G01 and G02 keep using the committed list.</p>
{_img("punjab_platform_series.png", "Punjab monthly detections by satellite, raw (quality-filtered, type 0). Shaded: before each satellite's record.")}

<h2>4. Method and test plan (frozen before results)</h2>
<p>Protocol P01 (<code>experiments/PROTOCOL_P01.md</code>) fixed the quantity, filters, regions, splits, candidate models, metrics and the selection rule before any Pakistan series was computed; six gap-filling clarifications were logged before the first experiment ran. That order is recorded in the session transcript, not in git: the code and the log were committed only after the experiments (docs/VALIDATION.md explains what can be verified). Candidates, each fitted for day and night passes separately on monthly region totals: <b>M0</b> raw Aqua (what concatenation gives); <b>M1</b> one ratio; <b>M2</b> one ratio per calendar month shrunk towards M1 with 30 pseudo-detections; <b>M3</b> Poisson log-linear with season terms; <b>M4</b> M3 plus Terra. Selection: leave-one-year-out over 2014–2017 (Punjab), primary metric WAPE (total absolute error ÷ total detections); a model replaces M1 only if it beats it. Test: 2012-02 to 2013-12, run once after the selection was written to disk. Diagnostics: 2018–2025 (MODIS version changes, orbit drift) and Sindh (geographic transfer). Months with provider-reported missing days for any compared satellite are excluded from every score.</p>
<p>Later protocols follow the same pattern: P02 (camera model, clock test and burned area; section 6) and P04 (section 7). From P04 on, each protocol is committed on its own before any of its data is opened, every change is logged before the result it affects, and each result file records the code commit and the protocol's SHA-256.</p>

<h2>5. Results</h2>
<h3>Selection and held-out test (Punjab, Aqua → S-NPP)</h3>
<table><thead><tr><th>Model</th><th>CV WAPE 2014–17</th><th>CV log-MAE</th><th>CV bias</th><th>Test WAPE 2012–13</th></tr></thead>
<tbody>{score_rows(sel['scores'], tt['scores'])}</tbody></table>
<p class="note">{sel['scored_months']} cross-validation months, {tt['scored_months']} test months. M3 and M4 were not test-scored (only the selected model and the baselines are).</p>
<p><b>Negative result.</b> M2 won cross-validation but the simple ratio M1 did better on the held-out years ({pct(tt['scores']['M1']['wape'])} vs {pct(tt['scores']['M2']['wape'])} WAPE; M2 had the lower log-scale error, {tt['scores']['M2']['log_mae']:.3f} vs {tt['scores']['M1']['log_mae']:.3f}). M2 stays the default because the choice was fixed before the test; the app offers M1. The 80% intervals covered {pct(tt['interval_80_coverage'], 0)} of test months: they are too narrow.</p>

<h3>No universal multiplier</h3>
<table><thead><tr><th>Year</th><th>MODIS file version</th><th>M1 bias</th><th>M2 bias</th><th>M2 WAPE</th></tr></thead><tbody>{drift}</tbody></table>
<p class="note">The 2014–17 fit applied to later years over-predicts S-NPP every year. Because observed S-NPP is used from 2012, this drift affects only the modelled years. The ratio also differs by pass: about {e00['m1_ratio_all_selection_years']['D']:.1f} S-NPP detections per Aqua detection by day and {e00['m1_ratio_all_selection_years']['N']:.0f} at night (2014–17). Whether a separate ratio per calendar month helps is not settled: M2 won cross-validation but lost the test.</p>
{_img("punjab_ratio_drift.png", "S-NPP detections per Aqua detection (day passes) by season and year in Punjab.")}
<p><b>Geography.</b> Sindh calibrated on its own data: M1 {pct(sindh['method_transfer']['M1']['wape'])} (bias {sgn(sindh['method_transfer']['M1']['bias'])}), M2 {pct(sindh['method_transfer']['M2']['wape'])} (bias {sgn(sindh['method_transfer']['M2']['bias'])}). Reusing Punjab's parameters: M1 {pct(sindh['parameter_transfer']['M1']['wape'])} (bias {sgn(sindh['parameter_transfer']['M1']['bias'])}), M2 {pct(sindh['parameter_transfer']['M2']['wape'])} (bias {sgn(sindh['parameter_transfer']['M2']['bias'])}). Total error is mixed; the clear difference is that Punjab's parameters under-count Sindh. The app therefore calibrates every area on its own 2012–2017 overlap, with a support check.</p>
<p><b>Bridge.</b> NOAA-20 → S-NPP: M1 kept (CV WAPE {pct(br['scores']['M1']['wape'])}); test 2024–25 WAPE {pct(e02['bridge_test']['scores']['M1']['wape'])} (raw NOAA-20 {pct(e02['bridge_test']['scores']['M0']['wape'])}). WAPE is a total; single months differ more (docs/VALIDATION.md). The same model (M1), fitted on all of Punjab's complete months from April 2018 to December 2025, was then tested once on 2026 (P04 G03, section 7).</p>

<h3>Does the apparent change survive harmonisation?</h3>
<table><thead><tr><th>Season (2012–21 ÷ 2003–11)</th><th>Naive stitch</th><th>Aqua only</th><th>Harmonised (rough range, nominal 80%)</th><th>"Raw exaggerates change"</th></tr></thead>
<tbody>{dif_row('OctNov', 'October–November')}{dif_row('AprMay', 'April–May')}</tbody></table>
<p class="note">A demonstration rather than a test that could fail: given the sensor change, the naive figure was bound to be far larger. The naive stitch, frozen in P01 section 8, sums every VIIRS satellite, so it adds NOAA-20 from April 2018 (about a third of the 2012–21 naive total); joining MODIS to S-NPP alone gives {naive_snpp:.2f}× for October–November. Aqua alone is a consistency check, not independent evidence: the harmonised early years are calculated from Aqua.</p>
{_img("punjab_differentiator.png", "Season totals in Punjab: naive stitch, Aqua only and harmonised (S-NPP-equivalent).")}
<p>Sensitivity (declared after the test; selects nothing):</p>
<table><thead><tr><th>Model</th><th>Oct–Nov ratio</th><th>Apr–May ratio</th></tr></thead><tbody>{sens}</tbody></table>
<p><b>Reading.</b> The naive record's 17-fold October–November rise is mostly a change of instruments: VIIRS replaced MODIS in 2012, and NOAA-20 joined in 2018. On one scale the rise is about {min(sens_on):.1f}–{max(sens_on):.1f} times under every frozen model. The selected {sel['selected']} gives the highest value; its early years extrapolate below the calibration range (most early October–November seasons had fewer Aqua detections than any calibration season, and it under-predicted both October–November test seasons), so the lower end is more plausible. Aqua alone gives a similar ratio. An April–May rise is not established.</p>

<h2>6. Protocol P02 (3 Nov 2026): camera model, clock test and burned area</h2>
<p>In brief, from <code>docs/P02_RESULTS.md</code>; the separate checking session recomputed every P02 number (<code>docs/REVIEW_P02_2026-11-03.md</code>). <b>Camera model:</b> a model in which the chance of detection rises with fire power {"beat" if f01['results']['decision']['supported'] else "did not beat"} one multiplier on held-out years and provinces; the negative result is kept. <b>Clock test (Punjab):</b> relative to what S-NPP's detections predict (P02's Q), Terra's October–November detections {"fell" if p2_terra < 0 else "rose"} {pct(abs(p2_terra), 0)} from 2018–21 to 2023–25 (whole years as the unit, p = {p2_pt:.3f}) as its pass moved earlier, from {terra_t0}–{terra_t1} to {terra_t25} local solar time; Aqua's, moving later, showed no clear change ({sgn(p2_aqua, 0)}, p = {p2_pa:.2f}). The test cannot tell whether burning moved, and no cause is claimed. <b>Burned area:</b> MODIS burned area rose {f03['burned_area']['ratio_late_early']:.2f}× (2012–21 against 2003–11). The reading fixed in advance: "{e(f03['reading'])}". It is not independent of MODIS.</p>

<h2>7. Protocol P04 (run 8 Nov 2026): four more tests, each run once</h2>
<p>Protocol P04 (<code>experiments/PROTOCOL_P04.md</code>) was committed on its own on 5 Nov 2026, before any of the quantities it tests were computed; its section 0 lists what had already been seen (Punjab's numbers, a few late-October 2026 days and the press figures). Change-log entry 1 (headed 5 Nov, committed 8 Nov at 20:48, before the 2026 files were downloaded) answered the checker's report on the protocol and governs where it differs from the body; entry 2 (8 Nov, 22:20, after the 2026 download but before any run) recorded facts, closed five definitions, and changed no threshold, window or reading. Each test ran once on 8 Nov ({g01['run_utc'][11:16]} and {g03['run_utc'][11:16]} UTC; code {e(g01['code_state']['revision'])}, protocol SHA-256 {g01['protocol_sha256'][:12]}…), and the runner refuses to overwrite a result. The runs went ahead before the checker's report on the change log arrived, on Hasnain's go-ahead, which every result records: "{e(approved)}". On 9 Nov the checker recomputed all four tests without seeing these results, and every value matched (docs/REVIEW_P04-RUN_2026-11-09.md); its wording corrections are applied here. <b>Punjab is P04's development area:</b> its numbers were seen before the protocol was written, so Punjab is shown but is never part of a test. G05, a positive control on Indian Punjab, was withdrawn before any Indian data was opened. Comparisons used unrounded values; the numbers below are rounded for display.</p>
<table class="p04 glance"><thead><tr><th>Test</th><th>Rule fixed before the run</th><th>Result</th><th>Reading (the protocol's words)</th></tr></thead><tbody>
<tr><td><b>G01</b> Terra's autumn fall outside Punjab</td><td>Terra ÷ S-NPP day-pass detections on matched days, October–November. Fall seen if 2023–25 is at least 40% below 2018–21 and the whole-year permutation p ≤ 0.10; a November 2022 step if below every 2018–21 November and at most 0.6× their mean.</td><td>Sindh {sgn(sd['fall']['delta'], 0)}, p = {_p(sd['fall']['p'], sd['fall']['splits'])}. Khyber Pakhtunkhwa: {e(kp['fall']['reason'])}. November 2022 not eligible in either.</td><td>"{e(g01['seen_outside_punjab_reading'])}" Each province's own reading adds: "this does not rule out the clock, because burning hours may differ between provinces".</td></tr>
<tr><td><b>G02</b> season middle and end dates</td><td>Middle date: 50% of a season's day-pass detections; end date: 90%; each satellite on the pair's matched days. Holds if within 3 days (middle) and 4 days (end) in at least four-fifths of at least 6 eligible years (200 or more detections per satellite).</td><td>NOAA-20 holds in {len(n20_hold)} of {len(n20)} cases; Aqua fails in Punjab's spring ({pjs['end_misses']} of {len(pjs['eligible_years'])} end dates outside) and is not testable in Sindh and Khyber Pakhtunkhwa.</td><td>Punjab, spring, Aqua: "both dates fail; each satellite's band is shown side by side, with no 'same on both' label". NOAA-20: "matched S-NPP's dates within the tolerance".</td></tr>
<tr><td><b>G03</b> NOAA-20 bridge on 2026</td><td>P01's bridge (M1), fitted on Punjab's 2018–2025 months, applied unchanged to January–October 2026. Pass if total error (WAPE) ≤ 10% and every month with 300 or more S-NPP detections within 20%; at least 6 scored months.</td><td>{e(g03['status']).capitalize()}: {pct(g03['wape'])} over {g03['scored_months']} months (no conversion {pct(g03['m0_wape'])}); largest month errors {", ".join(f"{sgn(m['error'])} ({MON[int(m['month'][5:7]) - 1]})" for m in sorted(worst, key=lambda m: m['month']))}.</td><td>"{e(g03['reading'].split('. ')[0])}."</td></tr>
<tr><td><b>G04</b> this October's headline</td><td>Every row (no quality or type filter), Pakistani Punjab, every UTC day of 1–29 Oct 2026. The three-satellite sum within ±20% of {g04['sum']['target']:,}; S-NPP alone within ±20% of {g04['snpp']['target']:,}.</td><td>{g04['sum']['value']:,} and {g04['snpp']['value']:,}: both within.</td><td>"{e(g04['reading'])}"</td></tr>
</tbody></table>

<h3>G01: is Terra's autumn fall also seen in Sindh and Khyber Pakhtunkhwa?</h3>
<p><b>Result.</b> Sindh: {sgn(sd['fall']['delta'], 0)} (2023–25 against 2018–21), p = {_p(sd['fall']['p'], sd['fall']['splits'])} over {len(sd['fall']['years_before'])} and {len(sd['fall']['years_after'])} eligible years, so the fall is not seen. Khyber Pakhtunkhwa: {e(kp['fall']['reason'])}, so the fall is not testable. The November 2022 step was not testable in either province, because November 2022 had too few S-NPP detections. Punjab, the development area, shows what the test looks for: {sgn(pj['fall']['delta'], 0)}, p = {_p(pj['fall']['p'], pj['fall']['splits'])}, with November 2022 at {pj['step']['ratio_to_mean']:.2f}× the 2018–21 mean.</p>
<p><b>Readings.</b> "{e(sd['reading'])}" "{e(kp['reading'])}" Punjab, outside the test: "{e(pj['reading'])}"</p>
{_g01_table(g01)}

<h3>G02: season middle and end dates on the older and newer satellites</h3>
<p><b>Result.</b> NOAA-20 matched S-NPP's dates in {e(n20_hold_txt)}{e(n20_miss_txt)}; it was not testable in {"; ".join(e(x) for x in n20_nt)}. Aqua failed in Punjab's spring: the end date was outside 4 days in {pjs['end_misses']} of {len(pjs['eligible_years'])} eligible years and the middle date outside 3 days in {pjs['middle_misses']} ({pjs['misses_allowed']} allowed for each). Outside Punjab, Aqua had too few detections to test (0 or 1 eligible years against the 6 needed). That is the cost of the floor of 200 detections, set from the checker's simulation: at the earlier floor of 100, Sindh and Khyber Pakhtunkhwa would have had 11 and 7 eligible years, but with so few detections two satellites with identical timing fail the tolerance about two times in three, so neither outcome would show that the dates disagree (docs/REVIEW_P04-CL_2026-11-09.md). Outside Punjab, all of G02's evidence comes from NOAA-20 against S-NPP. Not part of the rule, read from the same file: in Punjab's spring Aqua's end date came before S-NPP's in every eligible year, by {min(abs(v['d_end']) for v in pjs['years'].values() if v['eligible'])} to {max(abs(v['d_end']) for v in pjs['years'].values() if v['eligible'])} matched days; the protocol claims nothing about why.</p>
{_g02_table(g02)}
<p class="note">Gaps are counted in matched days (days on which both satellites of the pair were observing), so a removed day never counts as disagreement. Readings saved by the test include: {" ".join('"' + e(r) + '"' for r in g02['readings'] if r.startswith(("Rice season, Aqua", "Punjab, spring season (15 Mar–30 Jun), Aqua", "After S-NPP", "Historical")))}</p>

<h3>G03: the record past 2 Nov 2026 (the NOAA-20 bridge on January–October 2026)</h3>
<p><b>Result: {e(g03['status'])}.</b> Total error (WAPE) {pct(g03['wape'])} over {g03['scored_months']} scored months, against {pct(g03['m0_wape'])} with no conversion (M0); E02's tested 2019–2023 fit, reported beside it, {pct(g03['secondary_e02_fit']['wape'])}. Every month held to the 20% rule was inside it{f"; the largest miss was {MON[int(g03_close['month'][5:7]) - 1]}, {sgn(g03_close['error'], 1)} on {g03_close['observed_snpp']:,} S-NPP detections" if g03_close else ""}. The rule that a day counts only with both of its passes present removed 12 days that FIRMS does not list; without it July is +10.3% instead of +14.9%, and the outcome is a pass either way (the checker's recomputation, docs/REVIEW_P04-RUN_2026-11-09.md). {may_text} Reported, not tested (each area on its own fit, never Punjab's factor): {"; ".join(f"{e(k)} {pct(v['wape'])} (no conversion {pct(v['m0_wape'])})" for k, v in rp.items())}.</p>
<p><b>Reading.</b> "{e(g03['reading'])}"</p>
{_g03_table(g03)}

<h3>G04: reproducing this October's headline for Pakistani Punjab</h3>
<p><b>Result: {e(g04['reading'])}.</b> Our counts, all rows: {g04['sum']['value']:,} summed over S-NPP, NOAA-20 and NOAA-21 against the press's {g04['sum']['target']:,}, and {g04['snpp']['value']:,} for S-NPP alone against {g04['snpp']['target']:,}. Gap days are counted as they are, not removed: only one of the two daily passes on {e(one_pass)} 2026. <b>Demonstration, not a test</b> (true by construction): S-NPP alone {moved(g04['changes']['snpp_only'])} from 2019 to 2026, while the summed count {moved(g04['changes']['naive_sum'])}, "{e(g04['changes']['naive_sum_label'])}": {g04['satellites_flying']['2019']} VIIRS satellites were flying in 2019 and {g04['satellites_flying']['2026']} in 2026. 2019, the press's comparison year, had S-NPP's lowest 1–29 October count of 2018–25 ({", ".join(f"{y}: {v:,}" for y, v in rng['by_year'].items())}).</p>
{_g04_tables(g04)}

<h3>What P04 does not show</h3>
<ul>
<li>G01 claims no cause. A fall in Sindh or Khyber Pakhtunkhwa would only have made a satellite-side cause more likely; "not seen" in Sindh does not rule out the clock.</li>
<li>G02's dates describe past seasons only; they are not forecasts. Its tolerances equal the extremes of Punjab's earlier probe, so they have no headroom.</li>
<li>G03: a pass shows that converted NOAA-20 tracks S-NPP within the marks, not that the conversion beats no conversion. Only Punjab was scored.</li>
<li>G04 reproduces a press count; it does not make a sum of satellites comparable across years.</li>
</ul>

<h2>8. The application</h2>
<p>A local web app (<code>python -m c08 serve</code>, no internet needed) lets a user pick a province on a map or draw a rectangle, choose years and a month, and see: the change-survives card; the record over time (naive, Aqua only, harmonised with interval); a year-by-month calendar marking months above or below the median of the same month in other years (factor 1.5); the selected month against normal for all three series, plus the naive stitch without NOAA-20; the latest complete days of near-real-time data against the same dates in earlier years; the area's own calibration quality; and every limitation. Exports: monthly values (CSV), the underlying detections (CSV, inside a ZIP when a selection has more than {analysis.EXPORT_PLAIN_MAX:,} rows), method and provenance (JSON), chart (SVG). Areas whose Aqua night detections are too few switch to day passes only. Display rules chosen after seeing results: areas with cross-validated WAPE above 50% are flagged as weakly supported, and an area is warned when its range spans more than {analysis.WIDE_RANGE:g} times or when M1 beat the selected model in its cross-validation.</p>
<p><b>Added on 8 Nov.</b></p>
<ul>
<li><b>Five story cards</b>, read only from saved result files and the same for every area: this October's headline taken apart (G04, each satellite's bar side by side, never stacked); S-NPP's end and the NOAA-20 bridge (G03); "Morning and afternoon passes see different shares" (P02 for Punjab, G01 for Sindh and Khyber Pakhtunkhwa); the season's middle and end dates as bands per satellite (G02); and a log of mistakes caught and facts with the date they were read. While a test had no result file, its card said so and showed none of its data.</li>
<li><b>A day-by-day view:</b> one month, one row per satellite plus the harmonised row; "–" for no data and "?" for a day with nothing anywhere in Pakistan, never zero. Daily values in the MODIS years use the monthly conversion and are untested. Each date links to NASA Worldview for that area and day (internet needed).</li>
<li><b>A reliability band</b> under the record chart: where each harmonised value comes from (observed S-NPP, converted from Aqua, or missing or partly covered).</li>
<li><b>"Where did this number come from?"</b> buttons beside the main numbers; <b>share links</b> that keep the view in the address (Copy link); a <b>30-second Tour</b>; a <b>printable summary</b>; light and dark themes.</li>
<li><b>The P04 lock:</b> until G01 and G02 had result files, the app withheld their test data (daily values, Worldview links, Terra's October–November columns and detection rows inside the test windows). It lifted when the results were written on 8 Nov.</li>
</ul>

<h2>9. Limitations</h2>
<ul>
<li>S-NPP is a reference convention, not truth. No ground-truth, burned-area or field validation was done.</li>
<li>Exposure (clear-sky observation) is unknown; zero detections is not zero fire.</li>
<li>The rough ranges (nominal 80%) are too narrow ({pct(tt['interval_80_coverage'], 0)} test coverage) and ignore which calibration years were used; the ratio drifts over time and by season.</li>
<li>The held-out test (2012–13) sits next to the calibration years, so nothing tests the 2003–11 levels directly; the agreement of all four models supports the size of the change, not the modelled counts.</li>
<li>Small or mountainous areas have weak support; Balochistan's October–November range excludes its own point estimate, so the app leads with the range there.</li>
<li>The app's record ends in December 2025. The NOAA-20 bridge passed its frozen test on 2026 (G03), but 2026 months are not yet on the record chart; by the test's rule they are added in whole months, with converted NOAA-20 from November 2026 in Punjab only.</li>
<li>P04's results (8 Nov) were run before the checker's report on the change log and have not yet been reviewed by the checker. Punjab's G01 and G02 numbers are development numbers, seen before the test.</li>
<li>G03 mixes streams by month: standard January–July 2026, near-real-time with no type screen August–October; May had no matched days.</li>
<li>Bowtie overlap within a pass is not measured or removed, and a few S-NPP outage days are missing from the provider's list (for example 31 October 2019), which leaves those months slightly low.</li>
<li>Near-real-time files differ in processing from the archive and lack the type field; the latest-days panel compares like with like but does not correct this.</li>
<li>No forecast, risk, smoke attribution, crop type or emissions claims.</li>
</ul>

<h2>10. Reproduction and sources</h2>
<p><code>python -m c08 check</code> runs the test suite and re-runs E01–E03 in a temporary folder; last check: {"identical" if rep['identical'] else "DIFFERENT"} ({rep['checked_utc']}). P04's tests are never re-run: each result file (<code>experiments/P04_G01_terra_step</code>, <code>P04_G02_season_dates</code>, <code>P04_G03_bridge_2026</code>, <code>P04_G04_headline</code>) records its code commit, the protocol's SHA-256 and the hash of every input, and <code>python -m c08.p04 punjab-check</code> repeats Punjab's development numbers without writing anything. Code licence: Apache-2.0. Data: NASA FIRMS (we acknowledge the use of data and imagery from NASA's Fire Information for Resource Management System, part of NASA's ESDIS); geoBoundaries (Runfola et al. 2020, PLoS ONE 15(4): e0231866). Prior art: sensor fusion and FRP-based harmonisation of MODIS and VIIRS (for example Zheng et al.) is not new; this work contributes a tested, region-calibrated calendar for Pakistan with an audit trail.</p>
"""
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Seamline methods report</title>
<meta name="viewport" content="width=device-width, initial-scale=1"><style>
@page {{ size: A4; margin: 16mm 15mm; }}
body {{ font: 10.5pt/1.45 "Segoe UI", system-ui, sans-serif; color: #0b0b0b; background: #ffffff; max-width: 190mm; margin: 0 auto; padding: 0 4mm; }}
h1 {{ font-size: 18pt; margin: 0 0 4px; }} h2 {{ font-size: 13pt; margin: 18px 0 6px; border-bottom: 1px solid #e1e0d9; padding-bottom: 2px; }}
h3 {{ font-size: 11pt; margin: 12px 0 4px; }} .meta {{ color: #52514e; margin: 0; }}
.status {{ background: #f0efec; padding: 6px 10px; border-radius: 6px; }}
table {{ border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; margin: 6px 0; break-inside: avoid; }}
th, td {{ border-bottom: 1px solid #e1e0d9; padding: 3px 6px; text-align: right; }} th:first-child, td:first-child {{ text-align: left; }}
th {{ color: #52514e; font-weight: 600; }} .note {{ color: #6e6c66; font-size: 9pt; }}
figure {{ margin: 8px 0; break-inside: avoid; }} img {{ width: 100%; }} figcaption {{ color: #52514e; font-size: 9pt; }}
code {{ font-size: 9.5pt; }}
table.p04 {{ font-size: 9pt; break-inside: auto; }} table.p04 tr {{ break-inside: avoid; }}
table.p04 th {{ vertical-align: bottom; }} table.p04 td {{ vertical-align: top; }}
table.p04 th.l, table.p04 td.l {{ text-align: left; }} table.p04 td:first-child {{ white-space: nowrap; }}
table.glance td:first-child {{ white-space: normal; }}
h3 {{ break-after: avoid; }}
table.glance td, table.glance th {{ text-align: left; }} table.glance td:first-child {{ width: 17%; }}
table.glance td:nth-child(2) {{ width: 33%; }} table.glance td:nth-child(3) {{ width: 25%; }}
table.p04 tr.muted td, table.p04 td.muted {{ color: #6e6c66; }} table.p04 tr.sep td {{ border-top: 1.5px solid #c3c2b7; }}
table.p04.half {{ width: 49%; display: inline-table; vertical-align: top; margin-right: 1%; }}
ul {{ padding-left: 20px; }} li {{ margin-bottom: 3px; }}
</style></head><body>{body}</body></html>"""
    OUT_HTML.write_text(page, encoding="utf-8")
    return OUT_HTML


def print_pdf(edge: Path, src: Path, out: Path, timeout: float = 120) -> None:
    """Print src to out with headless Edge. Edge 156 returns before the file is written,
    so wait until a new PDF exists and has stopped growing."""
    before = out.stat().st_mtime if out.exists() else None
    subprocess.run([str(edge), "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={out}", src.resolve().as_uri()], check=True, timeout=timeout,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    start, last = time.time(), -1
    while time.time() - start < timeout:
        if out.exists() and out.stat().st_mtime != before:
            size = out.stat().st_size
            if size > 0 and size == last:
                return
            last = size
        time.sleep(0.5)
    raise RuntimeError(f"Edge did not write a new {out.name} within {timeout:.0f} s")


def to_pdf(src: Path) -> Path | None:
    edge = next((p for p in EDGE if p.is_file()), None) or (shutil.which("msedge") and Path(shutil.which("msedge")))
    if not edge:
        print("Microsoft Edge not found; HTML only.")
        return None
    print_pdf(edge, src, OUT_PDF)
    return OUT_PDF


if __name__ == "__main__":
    h = build()
    p = to_pdf(h)
    print(h, p)
