"""Seven-slide deck: reports/c08/slides.html (+ slides.pdf via Edge). python -m c08.slides

The story, one slide each: 1 the relay of satellites; 2 this October's headline taken apart (P04 G04);
3 the record after 2 Nov 2026 (P04 G03); 4 one scale for 2003-2025 (P01: E02, E03); 5 morning and
afternoon passes (P04 G01, with P02's pass times); 6 season dates (P04 G02); 7 limits and tests.

Every number is read from saved, committed files when the deck is built, never typed in:
experiments/*/result.json, reports/c08/p02_posthoc.json and reports/c08/ingest_report.json. The one
exception is the naive stitch without NOAA-20 (11.1x), which the app's own analysis function computes
from the processed table, as before. Readings are quoted in the protocol's words, as the result files
store them. Each slide names its source files in small print. Charts are inline SVG drawn here from
those numbers, so the deck stays offline; the one picture is reports/c08/figures/slide_compare_octnov.png.
Seven slides because the 2025 Space Apps rule allowed seven; recheck the 2026 guide before submitting.
"""
from __future__ import annotations

import base64
import html
import io
import json
import re
from datetime import date

from PIL import Image

from . import analysis, config, report

OUT_HTML = config.REPORTS / "slides.html"
OUT_PDF = config.REPORTS / "slides.pdf"
N_SLIDES = 7
MINUS = "−"
MON = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
SAT = {"SNPP": "S-NPP", "NOAA20": "NOAA-20", "NOAA21": "NOAA-21", "Aqua": "Aqua", "Terra": "Terra"}
# The app's satellite colours (c08/web/showcase.css, light theme), so slides and app match.
COL = {"SNPP": "#0b0b0b", "NOAA20": "#6e6c66", "NOAA21": "#6da7ec", "Aqua": "#2a78d6", "Terra": "#e34948"}
# Slide 1 has the dark title background, so it uses the app's dark-theme colours.
DARK = {"Terra": "#e66767", "Aqua": "#3987e5", "SNPP": "#f0efec", "NOAA20": "#a3a29b", "NOAA21": "#6da7ec"}
PROVINCES = ("Punjab", "Sindh", "Khyber Pakhtunkhwa")
WIN = {"rice": "Rice season", "spring": "Spring season"}
WIN_DATES = {"rice": "15 Sep–31 Dec", "spring": "15 Mar–30 Jun"}
PAIRS = (("NOAA20-SNPP", "NOAA-20 vs S-NPP"), ("Aqua-SNPP", "Aqua vs S-NPP"))


# ---------- small helpers ----------
def _load(rel: str) -> dict:
    return json.loads((config.ROOT / rel).read_text(encoding="utf-8"))


def _b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _fig(name: str) -> str:
    return _b64(Image.open(config.REPORTS / "figures" / name))


e = html.escape


def n0(v: float) -> str:
    return f"{round(v):,}"


def pc(v: float, d: int = 0, signed: bool = True) -> str:
    """-0.8125 -> '−81%'. Display only: every comparison was made unrounded, in the result files."""
    x = round(abs(v) * 100, d)
    s = f"{x:.{d}f}%"
    if not signed or x == 0:
        return s
    return (MINUS if v < 0 else "+") + s


def xx(v: float, d: int = 1) -> str:
    return f"{v:.{d}f}×"


def p_text(p: float, splits: int | None) -> str:
    """The smallest possible p of a whole-year permutation is shown as a fraction (1/35); others as decimals."""
    if splits and abs(p * splits - 1) < 1e-9:
        return f"1/{splits}"
    return f"{p:.2f}"


def years_text(ys: list[int]) -> str:
    ys = sorted(ys)
    if ys and ys == list(range(ys[0], ys[-1] + 1)) and len(ys) > 2:
        return f"{ys[0]}–{str(ys[-1])[2:]}"
    return ", ".join(map(str, ys))


def frac_year(iso: str) -> float:
    d = date.fromisoformat(iso[:10])
    return d.year + (d.timetuple().tm_yday - 1) / 365.0


def short_date(d: date) -> str:
    return f"{d.day} {MON[d.month - 1]} {d.year}"


def src_line(files: list[str], page: int) -> str:
    return (f'<p class="src"><span>Source: {"; ".join(e(f) for f in files)}.</span>'
            f'<span class="pg">{page} / {N_SLIDES}</span></p>')


def snpp_end(g03: dict) -> date:
    """S-NPP's end date, read from G03's seam label ('S-NPP ended 2 Nov 2026, 15:40 UTC (...)')."""
    m = re.search(r"ended (\d{1,2}) (\w{3}) (\d{4})", g03["seam_label"])
    if not m:
        raise ValueError("G03's seam label has no end date")
    return date(int(m.group(3)), MON.index(m.group(2)) + 1, int(m.group(1)))


def svg_open(w: int, h: int, label: str) -> str:
    return f'<svg class="chart" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{e(label)}">'


# ---------- slide 1: the relay of satellites ----------
def relay_svg(spans: dict, noaa21_start: str, end: date, now: str) -> str:
    """One bar per satellite over 2000-2027; S-NPP ends at its end date, the others run to the download date."""
    W, L, R, T, row = 1152, 214, 1148, 30, 50
    H = T + 5 * row + 30
    y0, y1 = 2000.0, 2027.0
    X = lambda y: round(L + (R - L) * (y - y0) / (y1 - y0), 1)
    end_y, now_y = frac_year(end.isoformat()), frac_year(now)
    rows = [("Terra", "MODIS, 1 km", spans["Terra"][0], now_y, "morning pass, drifting earlier in recent years"),
            ("Aqua", "MODIS, 1 km", spans["Aqua"][0], now_y, "early-afternoon pass, drifting later in recent years"),
            ("SNPP", "VIIRS, 375 m", spans["SNPP"][0], end_y, "about 1 pm: Seamline's reference from 2012"),
            ("NOAA20", "VIIRS, 375 m", spans["NOAA20"][0], now_y, "about 1 pm: tested as the bridge"),
            ("NOAA21", "VIIRS, 375 m", noaa21_start, now_y, "")]
    s = svg_open(W, H, "Timeline of the five satellites behind Pakistan's fire record, 2000 to 2026")
    marks = [(frac_year(spans["SNPP"][0]), "2012"), (frac_year(spans["NOAA20"][0]), "2018"),
             (frac_year(noaa21_start), str(noaa21_start[:4])), (end_y, short_date(end))]
    for i, (y, lab) in enumerate(marks):
        x = X(y)
        last = i == len(marks) - 1
        s += (f'<line x1="{x}" x2="{x}" y1="{T - 8}" y2="{T + row * 5}" stroke="#b7d3f6" stroke-width="1.2" '
              f'stroke-dasharray="4 4"/>'
              f'<text x="{x - 4 if last else x}" y="{T - 13}" text-anchor="{"end" if last else "middle"}" '
              f'class="d-mark">{e(lab)}</text>')
    for i, (key, sub, a, b, note) in enumerate(rows):
        top = T + i * row
        xa, xb = X(frac_year(a) if isinstance(a, str) else a), X(b)
        s += (f'<text x="0" y="{top + 21}" class="d-name">{e(SAT[key])}</text>'
              f'<text x="0" y="{top + 40}" class="d-sub">{e(sub)}</text>'
              f'<rect x="{xa}" y="{top + 9}" width="{round(xb - xa, 1)}" height="30" rx="4" fill="{DARK[key]}"/>')
        if note:
            s += f'<text x="{xa + 9}" y="{top + 29}" class="d-in">{e(note)}</text>'
        if key == "SNPP":
            s += (f'<line x1="{xb}" x2="{xb}" y1="{top + 3}" y2="{top + 45}" stroke="#ffffff" stroke-width="3"/>'
                  f'<text x="{xb - 9}" y="{top + 29}" text-anchor="end" class="d-in d-strong">ended {e(short_date(end))}</text>')
    for y in (2000, 2005, 2010, 2015, 2020, 2025):
        s += f'<text x="{X(y)}" y="{H - 4}" text-anchor="middle" class="d-tick">{y}</text>'
    return s + "</svg>"


# ---------- slide 2: the headline taken apart (G04) ----------
def headline_svg(g04: dict) -> str:
    per, flying = g04["per_satellite"], g04["satellites_flying"]
    years = sorted(per, key=int)
    W, H, L, R, T, B = 600, 372, 64, 8, 26, 58
    top = 1000 * (int(max(v for y in years for v in per[y].values()) // 1000) + 1)
    Y = lambda v: round(T + (H - T - B) * (1 - v / top), 1)
    s = svg_open(W, H, "Bar chart: each VIIRS satellite's own count for 1 to 29 October in Pakistani Punjab, "
                       "2019 and 2026, side by side, never stacked")
    for t in range(0, top + 1, 1000):
        s += (f'<line x1="{L}" x2="{W - R}" y1="{Y(t)}" y2="{Y(t)}" class="grid"/>'
              f'<text x="{L - 8}" y="{Y(t) + 5}" text-anchor="end" class="tick">{t:,}</text>')
    gw, bw, gap = (W - L - R) / len(years), 66, 8
    for i, y in enumerate(years):
        x0 = L + gw * i + (gw - (3 * bw + 2 * gap)) / 2
        for j, k in enumerate(("SNPP", "NOAA20", "NOAA21")):
            x = round(x0 + j * (bw + gap), 1)
            v = per[y].get(k)
            if v is None:  # not flying: an empty dashed slot, never a zero bar
                s += (f'<rect x="{x}" y="{H - B - 30}" width="{bw}" height="30" class="missing"/>'
                      f'<text x="{x + bw / 2}" y="{H - B - 38}" text-anchor="middle" class="tick">not flying</text>')
                continue
            stroke = ' stroke="#52514e" stroke-width="1"' if k == "NOAA21" else ""
            s += (f'<rect x="{x}" y="{Y(v)}" width="{bw}" height="{round(H - B - Y(v), 1)}" fill="{COL[k]}"{stroke}/>'
                  f'<text x="{x + bw / 2}" y="{Y(v) - 7}" text-anchor="middle" class="val">{v:,}</text>')
        cx = round(L + gw * i + gw / 2, 1)
        n = flying[y]
        s += (f'<text x="{cx}" y="{H - B + 24}" text-anchor="middle" class="year">{y}</text>'
              f'<text x="{cx}" y="{H - B + 46}" text-anchor="middle" class="tick">{n} satellite{"s" if n != 1 else ""} flying</text>')
    s += f'<line x1="{L}" x2="{W - R}" y1="{H - B}" y2="{H - B}" class="axis"/>'
    return s + "</svg>"


def legend(keys: list[str], extra: str = "") -> str:
    """Colour keys; NOAA-21's light blue gets an outline, as its bars do."""
    items = "".join(f'<span><i style="background:{COL[k]}'
                    f'{";box-shadow:inset 0 0 0 1px #52514e" if k == "NOAA21" else ""}"></i>{e(SAT[k])}</span>'
                    for k in keys)
    return f'<div class="legend">{items}{extra}</div>'


# ---------- slide 3: the record after 2 Nov (G03) ----------
def bridge_svg(g03: dict) -> str:
    scored = {m["month"]: m for m in g03["months"]}
    skipped = {m["month"]: m for m in g03["months_not_scored"]}
    months = sorted(set(scored) | set(skipped))
    W, H, L, R, T, B = 700, 330, 60, 86, 40, 28
    most = max(max(m["observed_snpp"], m["predicted"]) for m in scored.values())
    top = 2000 * (int(most // 2000) + 1)
    Y = lambda v: round(T + (H - T - B) * (1 - v / top), 1)
    worst = sorted(scored.values(), key=lambda m: -abs(m["error"]))[:2]
    s = svg_open(W, H, "Bar chart: S-NPP's observed monthly detections in Punjab beside NOAA-20 converted to "
                       "S-NPP's scale, January to October 2026")
    for t in range(0, top + 1, 2000):
        s += (f'<line x1="{L}" x2="{W - R}" y1="{Y(t)}" y2="{Y(t)}" class="grid"/>'
              f'<text x="{L - 8}" y="{Y(t) + 5}" text-anchor="end" class="tick">{t:,}</text>')
    gw, bw, gap = (W - L - R) / len(months), 22, 3
    for i, ym in enumerate(months):
        cx = L + gw * i + gw / 2
        x0 = cx - (2 * bw + gap) / 2
        lab = MON[int(ym[5:7]) - 1]
        s += f'<text x="{round(cx, 1)}" y="{H - B + 20}" text-anchor="middle" class="tick">{lab}</text>'
        if ym in skipped:  # not scored: empty dashed slots, never zero
            for j in range(2):
                s += f'<rect x="{round(x0 + j * (bw + gap), 1)}" y="{H - B - 24}" width="{bw}" height="24" class="missing"/>'
            s += (f'<text x="{round(cx, 1)}" y="{H - B - 46}" text-anchor="middle" class="tick">not</text>'
                  f'<text x="{round(cx, 1)}" y="{H - B - 31}" text-anchor="middle" class="tick">scored</text>')
            continue
        m = scored[ym]
        for j, (k, v) in enumerate((("SNPP", m["observed_snpp"]), ("NOAA20", m["predicted"]))):
            x = round(x0 + j * (bw + gap), 1)
            s += f'<rect x="{x}" y="{Y(v)}" width="{bw}" height="{round(H - B - Y(v), 1)}" fill="{COL[k]}"/>'
        ytxt = min(Y(m["observed_snpp"]), Y(m["predicted"])) - 8
        cls = "val strong" if m in worst else "val"
        s += f'<text x="{round(cx, 1)}" y="{ytxt}" text-anchor="middle" class="{cls}">{pc(m["error"], 1)}</text>'
    s += f'<line x1="{L}" x2="{W - R}" y1="{H - B}" y2="{H - B}" class="axis"/>'
    xs = W - R + 10
    s += (f'<line x1="{xs}" x2="{xs}" y1="{T - 30}" y2="{H - B}" stroke="#c93a39" stroke-width="2.5"/>'
          f'<text x="{xs + 8}" y="{T - 14}" class="seam">2 Nov:</text>'
          f'<text x="{xs + 8}" y="{T + 4}" class="seam">S-NPP</text>'
          f'<text x="{xs + 8}" y="{T + 22}" class="seam">ends</text>'
          f'<text x="{xs + 8}" y="{T + 58}" class="tick">from Nov:</text>'
          f'<text x="{xs + 8}" y="{T + 76}" class="tick">NOAA-20,</text>'
          f'<text x="{xs + 8}" y="{T + 94}" class="tick">converted</text>')
    return s + "</svg>"


# ---------- slide 5: morning and afternoon passes (G01) ----------
def terra_panel(name: str, p: dict, label: str) -> str:
    """Terra detections per 100 S-NPP detections (October-November day passes), 2018-2025, for one province."""
    W, H, L, R, T, B = 352, 222, 40, 10, 12, 26
    pts = []
    for y, v in sorted(p["years"].items(), key=lambda kv: int(kv[0])):
        o = v["OctNov"]
        if o.get("R") is not None:
            pts.append((int(y), 100 * o["R"], bool(o["eligible"])))
    most = max(v for _, v, _ in pts)
    top = 3 if most <= 3 else (5 if most <= 5 else 10)
    step = 1 if top <= 3 else (1 if top == 5 else 5)
    X = lambda y: round(L + (W - L - R) * (y - 2017.5) / 8, 1)
    Y = lambda v: round(T + (H - T - B) * (1 - v / top), 1)
    s = svg_open(W, H, f"{name}: Terra detections per 100 S-NPP detections, October to November day passes, "
                       f"2018 to 2025")
    for a, b in ((2018, 2021), (2023, 2025)):
        s += f'<rect x="{X(a - 0.45)}" y="{T}" width="{round(X(b + 0.45) - X(a - 0.45), 1)}" height="{H - T - B}" class="period"/>'
    for t in range(0, top + 1, step):
        s += (f'<line x1="{L}" x2="{W - R}" y1="{Y(t)}" y2="{Y(t)}" class="grid"/>'
              f'<text x="{L - 6}" y="{Y(t) + 5}" text-anchor="end" class="tick">{t}</text>')
    fall = p["fall"]
    if fall.get("mean_R_before") is not None and fall.get("mean_R_after") is not None:
        for (a, b), mv in (((2018, 2021), fall["mean_R_before"]), ((2023, 2025), fall["mean_R_after"])):
            s += (f'<line x1="{X(a - 0.4)}" x2="{X(b + 0.4)}" y1="{Y(100 * mv)}" y2="{Y(100 * mv)}" '
                  f'stroke="{COL["Terra"]}" stroke-width="1.6" stroke-dasharray="5 4"/>')
    for y, v, ok in pts:
        if ok:
            s += f'<circle cx="{X(y)}" cy="{Y(v)}" r="5" fill="{COL["Terra"]}"/>'
        else:
            s += f'<circle cx="{X(y)}" cy="{Y(v)}" r="4.5" fill="#fcfcfb" stroke="#8a8881" stroke-width="1.6"/>'
    for y in (2018, 2020, 2022, 2024):
        s += f'<text x="{X(y)}" y="{H - 6}" text-anchor="middle" class="tick">{y}</text>'
    s += f'<line x1="{L}" x2="{W - R}" y1="{H - B}" y2="{H - B}" class="axis"/>'
    return f'<p class="panel-h">{e(name)}<span>{e(label)}</span></p>' + s + "</svg>"


# ---------- slide 6: season dates (G02) ----------
def season_cell(prov: str, win: str, pair: str, g02: dict) -> str:
    if prov == "Punjab" and win == "rice":
        return '<td class="c-dev"><b>Development area</b><span>dates seen before the test; not tested</span></td>'
    r = g02["results"][prov][win][pair]
    n, k = len(r["eligible_years"]), r["years_outside_tolerance"]
    if r["status"] == "holds":
        return f'<td class="c-hold"><b>✓ Holds</b><span>{n - k} of {n} years within the tolerance</span></td>'
    if r["status"] == "fails":
        return f'<td class="c-fail"><b>✗ Fails</b><span>{k} of {n} years outside the tolerance</span></td>'
    word = "year" if n == 1 else "years"
    return f'<td class="c-nt"><b>Not testable</b><span>{n} eligible {word}; 6 needed</span></td>'


def season_table(g02: dict) -> str:
    head1 = '<tr><th rowspan="2" class="corner"></th>' + "".join(
        f'<th colspan="2">{WIN[w]} <span>({WIN_DATES[w]})</span></th>' for w in ("rice", "spring")) + "</tr>"
    head2 = "<tr>" + "".join(f"<th>{e(lab)}</th>" for _ in range(2) for _, lab in PAIRS) + "</tr>"
    body = "".join("<tr><th class=\"prov\">" + e(prov) + "</th>" + "".join(
        season_cell(prov, w, pair, g02) for w in ("rice", "spring") for pair, _ in PAIRS) + "</tr>" for prov in PROVINCES)
    return f'<table class="matrix"><thead>{head1}{head2}</thead><tbody>{body}</tbody></table>'


# ---------- the deck ----------
def build() -> None:
    e01 = _load("experiments/E01_selection/result.json")
    e02 = _load("experiments/E02_evaluation/result.json")
    e03 = _load("experiments/E03_sensitivity/result.json")
    f01 = _load("experiments/P02_F01_camera/result.json")
    post = _load("reports/c08/p02_posthoc.json")
    ing = _load("reports/c08/ingest_report.json")
    g01 = _load("experiments/P04_G01_terra_step/result.json")
    g02 = _load("experiments/P04_G02_season_dates/result.json")
    g03 = _load("experiments/P04_G03_bridge_2026/result.json")
    g04 = _load("experiments/P04_G04_headline/result.json")

    # Slide 1 facts: archive spans and NOAA-21's start (G03's inputs), S-NPP's end (G03's seam label).
    spans = g03["inputs"]["archive_spans"]
    n21 = g03["inputs"]["availability"]["ranges"]["VIIRS_NOAA21_SP"][0]
    end = snpp_end(g03)
    now = g03["inputs"]["download_utc"]["last"][:10]
    pt = post["pass_times"]["by_season"]
    snpp_times = sorted(v["median"] for v in pt["SNPP"]["OctNov"].values())
    snpp_years = years_text([int(y) for y in pt["SNPP"]["OctNov"]])
    terra_early = sorted(pt["Terra"]["OctNov"][str(y)]["median"] for y in range(2018, 2022))
    terra_2025 = pt["Terra"]["OctNov"]["2025"]["median"]
    aqua_early = sorted(pt["Aqua"]["OctNov"][str(y)]["median"] for y in range(2018, 2022))
    aqua_2025 = pt["Aqua"]["OctNov"]["2025"]["median"]

    # Slide 2 (G04).
    s4, n4 = g04["sum"], g04["snpp"]
    ch, rng = g04["changes"], g04["snpp_range_2018_2025"]
    low_year = min(rng["by_year"], key=lambda y: rng["by_year"][y])
    fl = g04["satellites_flying"]

    # Slide 3 (G03).
    worst = sorted(g03["months"], key=lambda m: -abs(m["error"]))[:2]
    worst_txt = " and ".join(f"{pc(m['error'], 1)} ({MON[int(m['month'][5:7]) - 1]})"
                             for m in sorted(worst, key=lambda m: m["month"]))
    rep = g03["reported"]
    not_scored = "; ".join(f"{MON[int(m['month'][5:7]) - 1]} not scored: {m['matched_days']} matched days"
                           for m in g03["months_not_scored"])

    # Slide 4 (P01).
    on = e02["differentiator"]["OctNov"]
    iv = on["harmonised_interval"]["ratio_late_early"]
    sens = [v["OctNov"]["ratio_late_early"] for v in e03["by_model"].values()]
    sel = e01["backcast"]["selected"]
    naive_snpp = analysis.analyse(region="Punjab", model=sel)["change"]["OctNov"]["naive_snpp"]
    cov = e02["temporal_test"]["interval_80_coverage"]

    # Slide 5 (G01): Punjab is the development area; Sindh and KP are the test.
    pj = g01["development_area"]["Punjab"]
    sd, kp = g01["provinces"]["Sindh"], g01["provinces"]["Khyber Pakhtunkhwa"]
    pj_fall, pj_step = pj["fall"], pj["step"]
    after = [pj["years"][str(y)]["OctNov"]["R"] for y in pj_fall["years_after"]]
    before = [pj["years"][str(y)]["OctNov"]["R"] for y in pj_fall["years_before"]]
    pj_sep = max(after) < min(before)  # every later year below every earlier one

    def step_clause(p: dict) -> str:
        st = p["step"]
        if st["status"] == "not_testable":
            return f"the 2022 step is not testable ({st['reason'].split(' (')[0]})"
        return "a 2022 step is seen" if st["status"] == "present" else "no 2022 step is seen"

    def fall_clause(p: dict) -> str:
        f = p["fall"]
        if f["status"] == "not_testable":
            return f"the fall is not testable ({f['reason']})"
        return {"present": "Terra's fall is also seen",
                "large_not_significant": "a large fall, not significant with these years",
                "not_seen": "Terra's fall is not seen; this does not rule out the clock, because burning hours may "
                            "differ between provinces"}[f["status"]]

    cause = pj["reading"].split(". ", 1)[1] if ". " in pj["reading"] else ""
    cap = lambda t: t[:1].upper() + t[1:]
    rem = sorted(pj["years"]["2022"]["OctNov"]["days_removed"])
    gap22 = f"{int(rem[0][8:])}–{int(rem[-1][8:])} {MON[int(rem[0][5:7]) - 1]} 2022" if rem else "some days"

    # Slide 6 (G02).
    aqua_out = [(p, w) for p in PROVINCES for w in ("rice", "spring")
                if p in g02["results"] and w in g02["results"][p] and g02["results"][p][w]["Aqua-SNPP"]["status"] == "not_testable"]
    aqua_max_elig = max(len(g02["results"][p][w]["Aqua-SNPP"]["eligible_years"]) for p, w in aqua_out)
    pjs = g02["results"]["Punjab"]["spring"]["Aqua-SNPP"]
    a0, a1 = g02["pairs"]["Aqua-SNPP"]["years"]
    aqua_ends_before = all(v["d_end"] < 0 for v in pjs["years"].values() if v["eligible"])
    # NOAA-20's "holds" uses the one outside year in five the rule allows; name those years (REVIEW_P04-RUN, R4).
    n20_miss = [f"{p} {w} {y}" for p in g02["results"] for w in g02["results"][p]
                for r in [g02["results"][p][w]["NOAA20-SNPP"]] if r["status"] == "holds"
                for y in r["eligible_years"]
                if abs(r["years"][str(y)]["d_mid"]) > 3 or abs(r["years"][str(y)]["d_end"]) > 4]

    # Slide 7: every P04 outcome at a glance, read from the four result files.
    word = {"present": "seen", "not_seen": "not seen", "large_not_significant": "large, not significant",
            "not_testable": "not testable"}
    g01_txt = "; ".join(f"{'KP' if p == 'Khyber Pakhtunkhwa' else p}: {word[v['fall']['status']]}"
                        for p, v in g01["provinces"].items())
    cells = {pair: [g02["results"][p][w][pair]["status"] for p in g02["results"] for w in g02["results"][p]]
             for pair, _ in PAIRS}

    def tally(pair: str) -> str:
        c = cells[pair]
        bits = [f"{w} in {c.count(st)}" for st, w in (("holds", "holds"), ("fails", "fails"),
                                                        ("not_testable", "not testable")) if c.count(st)]
        return ", ".join(bits)
    scorecard = "".join(f'<div><p class="t">{e(t)}</p><p>{x}</p></div>' for t, x in (
        ("G01 · Terra's fall outside Punjab", e(g01_txt)),
        ("G02 · season dates", f"Of 5 cases each. NOAA-20: {tally('NOAA20-SNPP')}. Aqua: {tally('Aqua-SNPP')}."),
        ("G03 · NOAA-20 bridge on 2026", f"{e(cap(g03['status']))} in Punjab: {pc(g03['wape'], 1, signed=False)} "
                                         f"(no conversion {pc(g03['m0_wape'], 1, signed=False)})"),
        ("G04 · this October's headline", f"{e(g04['reading'])}: {n0(s4['value'])} vs {n0(s4['target'])}; "
                                          f"S-NPP {n0(n4['value'])} vs {n0(n4['target'])}")))
    if any(len(c) != 5 for c in cells.values()):
        raise AssertionError("G02 should have five tested cases per pair")

    # Slide 7.
    tt = e02["temporal_test"]["scores"]
    std_rows = sum(v for k, v in ing["rows_by_platform_stream"].items() if k.endswith("/standard"))
    camera_supported = f01["results"]["decision"]["supported"]

    P04 = "experiments/P04_G0{}_{}/result.json"
    slides = [
        # 1 ------------------------------------------------------------------
        f"""<section class="slide dark">
<p class="kicker">NASA Space Apps 2026 · C08 Harmonization of MODIS and VIIRS Hot Spots</p>
<h1>Seamline <span>one fair scale for Pakistan's satellite burning record</span></h1>
<h2>The problem: the record is a relay of satellites</h2>
{relay_svg(spans, n21, end, now)}
<div class="callouts">
<div><h3>2012 · MODIS to VIIRS</h3><p>VIIRS's 375 m pixels see small patches of burning that MODIS's 1 km pixels miss, so a joined record jumps.</p></div>
<div><h3>2018 and {n21[:4]} · more VIIRS satellites</h3><p>NOAA-20, then NOAA-21. A count summed over satellites grows with each one, even if burning does not.</p></div>
<div><h3>{e(short_date(end))} · S-NPP ends</h3><p>Our reference since 2012 stopped. Can NOAA-20 carry the record on, on the same scale?</p></div>
</div>
<p class="who">Muhammad Hasnain Memon · Karachi · A detection is one fire pixel on one satellite pass: not a fire, not burned area.</p>
<p class="src"><span>Source: archive spans in experiments/P04_G03_bridge_2026/result.json (inputs.archive_spans; NOAA-21 from FIRMS's
availability answer, inputs.availability); S-NPP's end: the same file's seam_label ({e(g03['seam_label'])}); pass times:
reports/c08/p02_posthoc.json; pixel sizes: docs/DATA_PRODUCTS.md.</span><span class="pg">1 / {N_SLIDES}</span></p></section>""",

        # 2 ------------------------------------------------------------------
        f"""<section class="slide"><h2>This October's headline, taken apart</h2>
<p class="lead">The press: <b>{n0(s4['target'])}</b> detections in Pakistani Punjab, 1–29 Oct 2026, summed over three VIIRS satellites,
and <b>{n0(n4['target'])}</b> from S-NPP alone. Our own count, all rows: <b>{n0(s4['value'])}</b> and <b>{n0(n4['value'])}</b>,
both within ±20%. <span class="badge pass">✓ {e(g04['reading'])}</span></p>
<div class="cols">
<div class="col-chart">{legend(["SNPP", "NOAA20", "NOAA21"], '<span><i class="dash"></i>not flying</span>')}
{headline_svg(g04)}
<p class="note">Each satellite's own count, side by side, never stacked: 1–29 October, quality rule, no type screen in
either year (the 2026 near-real-time files have no type field).</p></div>
<div class="col-side">
<div class="kpi"><p class="label">S-NPP's own detections, 2019 → 2026</p><p class="big">{pc(ch['snpp_only'])}</p>
<p class="sub">The same instrument compared with itself, from its lowest year (2019 standard archive, 2026 near-real-time files).</p></div>
<div class="kpi naive"><p class="label">Naive sum of satellites, 2019 → 2026</p><p class="big red">{pc(ch['naive_sum'])}</p>
<p class="sub">{e(cap(ch['naive_sum_label'].split(', ', 1)[-1]))}: {fl['2019']} satellites were flying in 2019, {fl['2026']} in 2026.
A sum grows when a satellite is added, even if burning does not change.</p></div>
<p class="side-note">{low_year}, the press's comparison year, had S-NPP's lowest 1–29 October count of 2018–25
({n0(rng['min'])}; range {n0(rng['min'])}–{n0(rng['max'])}).</p>
</div></div>
{src_line([P04.format(4, 'headline') + " (sum, snpp, reading, per_satellite, satellites_flying, changes, snpp_range_2018_2025)",
           "press figures: Daily Pakistan, 2 Nov 2026; Minute Mirror, 31 Oct 2026 (PROTOCOL_P04.md, section 0)"], 2)}</section>""",

        # 3 ------------------------------------------------------------------
        f"""<section class="slide"><h2>S-NPP stopped on {e(short_date(end))}. Can NOAA-20 carry the record?</h2>
<div class="cols">
<div class="col-side wide3">
<p class="fact">{e(g03['seam_label'])}.</p>
<p class="small"><span class="badge pass">✓ Passed its frozen test</span><br>NOAA-20, converted to S-NPP's scale, against
S-NPP itself: Punjab, January–October 2026.</p>
<div class="kpis two">
<div class="kpi"><p class="label">Converted NOAA-20</p><p class="big">{pc(g03['wape'], 1, signed=False)}</p>
<p class="sub">total error, {g03['scored_months']} months</p></div>
<div class="kpi"><p class="label">No conversion (M0)</p><p class="big grey">{pc(g03['m0_wape'], 1, signed=False)}</p>
<p class="sub">for comparison</p></div></div>
<p class="small">Pass mark, fixed before the test: at most 10% in total (WAPE), and every month with at least 300 S-NPP
detections within 20%. Largest: {worst_txt}. {e(not_scored)} (days on which both satellites were observing).</p>
</div>
<div class="col-chart">
<div class="legend"><span><i style="background:{COL['SNPP']}"></i>S-NPP, observed</span><span><i style="background:{COL['NOAA20']}"></i>NOAA-20, converted to S-NPP's scale</span><span>numbers: each month's error</span></div>
{bridge_svg(g03)}
<p class="small"><b>By the rule fixed before the test,</b> from November 2026 Punjab's record continues on NOAA-20, converted,
in whole months only. Other areas show NOAA-20 in its own units: "{e(g03['other_areas_label'])}". "A pass shows that converted
NOAA-20 tracks S-NPP within the marks, not that M1 beats no conversion" (M1 is the conversion).</p>
<p class="note">Reported, not tested (each area on its own conversion): Pakistan {pc(rep['Pakistan']['wape'], 1, signed=False)},
Sindh {pc(rep['Sindh']['wape'], 1, signed=False)}, Khyber Pakhtunkhwa {pc(rep['Khyber Pakhtunkhwa']['wape'], 1, signed=False)}.
Earlier test, 2024–25: {pc(e02['bridge_test']['scores']['M1']['wape'], 1, signed=False)}. In the app, the record chart still
ends in December 2025.</p></div></div>
{src_line([P04.format(3, 'bridge_2026') + " (status, wape, m0_wape, months, months_not_scored, reported, reading, seam_label)",
           "experiments/E02_evaluation/result.json (bridge_test)"], 3)}</section>""",

        # 4 ------------------------------------------------------------------
        f"""<section class="slide"><h2>One scale for 2003–2025: the rise survives, much smaller</h2>
<div class="kpis">
<div class="kpi"><p class="label">Naive join (all MODIS, then all VIIRS)</p><p class="big red">{xx(on['naive_stitch']['ratio_late_early'])}</p>
<p class="sub">{xx(naive_snpp)} without NOAA-20</p></div>
<div class="kpi"><p class="label">One scale (Seamline)</p><p class="big">{min(sens):.1f}–{xx(max(sens))}</p>
<p class="sub">all four frozen models; the chosen {sel}: {xx(on['harmonised']['ratio_late_early'], 2)}</p></div>
<div class="kpi"><p class="label">Aqua MODIS alone</p><p class="big blue">{xx(on['aqua_only']['ratio_late_early'], 2)}</p>
<p class="sub">a consistency check, not separate proof</p></div></div>
<div class="cols">
<div class="col-side"><ul class="tight">
<li>Punjab, October–November: average 2012–21 ÷ average 2003–11.</li>
<li>On one scale the rise is about {min(sens):.1f}–{max(sens):.1f} times under every frozen model, not 17. The jump is mostly the change of satellites.</li>
<li>The chosen model gives the highest value, so the lower end is more plausible.</li>
<li>Our "rough ranges" are too narrow: nominally 80%, they caught {pc(cov, signed=False)} of held-out months (rough range for {sel}: {iv['lo']:.2f}–{iv['hi']:.2f}).</li></ul></div>
<img class="col-chart img" src="{_fig('slide_compare_octnov.png')}" alt="Punjab October-November detections: naive join, one scale and Aqua only, 2003 to 2025"></div>
{src_line(["experiments/E02_evaluation/result.json (differentiator.OctNov, temporal_test.interval_80_coverage)",
           "experiments/E03_sensitivity/result.json (by_model)",
           "without NOAA-20: c08/analysis.py, change.OctNov.naive_snpp (docs/CLAIMS.md)",
           "figure: reports/c08/figures/slide_compare_octnov.png"], 4)}</section>""",

        # 5 ------------------------------------------------------------------
        f"""<section class="slide"><h2>{e(g01['strip_title'])}</h2>
<p class="lead">Terra passes in the morning, S-NPP and NOAA-20 near 1 pm (local solar time). Terra's autumn pass moved earlier,
from {terra_early[0]}–{terra_early[-1]} in 2018–21 to {terra_2025} in 2025; S-NPP's stayed within {snpp_times[0]}–{snpp_times[-1]} ({snpp_years}).
Charts: Terra detections per 100 S-NPP detections, October–November day passes, on days both were observing.</p>
<div class="tri">
<div>{terra_panel("Punjab", pj, "development area")}
<p class="res">Fell {pc(pj_fall['delta'], signed=False)}, p = {p_text(pj_fall['p'], pj_fall['splits'])}{": every later year below every earlier one" if pj_sep else ""}.
November 2022 at {pj_step['ratio_to_mean']:.2f}× the 2018–21 mean.</p>
<p class="rd">Seen before the test, so not part of it. {e(fall_clause(pj))}; {e(step_clause(pj))}. {e(cause)}</p></div>
<div>{terra_panel("Sindh", sd, "tested")}
<p class="res">{pc(sd['fall']['delta'])}, p = {p_text(sd['fall']['p'], sd['fall']['splits'])}: not seen.</p>
<p class="rd">{e(cap(fall_clause(sd)))}; {e(step_clause(sd))}.</p></div>
<div>{terra_panel("Khyber Pakhtunkhwa", kp, "tested")}
<p class="res">Not testable.</p>
<p class="rd">{e(cap(fall_clause(kp)))}; {e(step_clause(kp))}.</p></div></div>
<p class="key"><i class="dot"></i>eligible year <i class="ring"></i>not eligible (too few detections, or too few days:
Terra is missing {gap22}) <i class="per"></i>periods compared <i class="mean"></i>period mean. No cause is claimed.</p>
{src_line([P04.format(1, 'terra_step') + " (provinces, development_area, strip_title)",
           "pass times: reports/c08/p02_posthoc.json (pass_times.by_season)"], 5)}</section>""",

        # 6 ------------------------------------------------------------------
        f"""<section class="slide"><h2>Season dates: do the old and new satellites agree?</h2>
<p class="lead">Middle date: the day by which half of a season's day-pass detections had been seen; end date: 90%. Each
satellite is dated on its own, on days both were observing. A pair holds if its gaps stay within 3 days (middle) and
4 days (end) in at least four-fifths of the eligible years.</p>
{season_table(g02)}
<div class="cols even">
<ul class="tight">
<li><b>NOAA-20 matched S-NPP's dates wherever it could be tested</b>{f", except in {e(', '.join(n20_miss))}, which the rule allows" if n20_miss else ""}, so the season dates can continue on NOAA-20 after S-NPP's end.</li>
<li><b>Aqua (MODIS) failed in Punjab's spring:</b> its end date was off by more than 4 days in {pjs['end_misses']} of {len(pjs['eligible_years'])}
years{", and came before S-NPP's in every eligible year" if aqua_ends_before else ""}. So each satellite's dates are shown side by side, with no "same on both" label.</li></ul>
<ul class="tight">
<li><b>Outside Punjab Aqua saw too few detections to test</b>: at most {aqua_max_elig} eligible year of {a1 - a0 + 1} (200 needed per satellite and season). There, only NOAA-20 against S-NPP carries the season-date evidence.</li>
<li>Punjab's rice dates set the tolerances, so they are shown, not tested. Past seasons only, never a forecast.</li></ul></div>
{src_line([P04.format(2, 'season_dates') + " (results, development_area, rules, readings)"], 6)}</section>""",

        # 7 ------------------------------------------------------------------
        f"""<section class="slide"><h2>How we test, and what the numbers do not say</h2>
<div class="cols even">
<div><h3>How we test</h3><ul class="tight">
<li><b>Rules first.</b> Each protocol (P01, P02, P04) was frozen before the quantities it tests were computed, and lists
what had already been seen. P04 was committed on its own on 5 Nov; its two logged changes came before any run.</li>
<li><b>Each test runs once.</b> P04's code refuses to overwrite a result; each result records the code commit and the protocol's hash.</li>
<li><b>Negative results stay.</b> The chosen model lost the held-out test to a simpler one ({pc(tt['M2']['wape'], 1, signed=False)} vs
{pc(tt['M1']['wape'], 1, signed=False)} error); a camera model {"was supported" if camera_supported else "lost to one multiplier"};
Aqua's spring dates failed in Punjab; Terra's fall was not seen in Sindh.</li>
<li><b>A separate checker.</b> A second AI session, apart from the one that builds, checks plans and results. It recomputed
every P02 number, checked P04's rules before any test quantity was computed, and on 9 Nov recomputed P04's four tests
without seeing our numbers: every value matched.</li></ul></div>
<div><h3>What the numbers do not say</h3><ul class="tight">
<li>A detection is one fire pixel on one satellite pass: not a fire, not burned area, not emissions.</li>
<li>No detection is not "no fire": clouds and smoke hide burning. Unknown stays unknown, never zero.</li>
<li>S-NPP is our reference scale, not ground truth.</li>
<li>No forecasts and no risk levels: only "unusual compared with this area's normal".</li>
<li>Pakistan only. {std_rows / 1e6:.2f} million archive detections, every file hash-checked. Built before the event with AI
coding assistants; true dates in git.</li></ul></div></div>
<p class="card-h">Protocol P04: four tests, each run once on 8 Nov. Passes, failures and "not testable" are reported alike.</p>
<div class="cards">{scorecard}</div>
<p class="foot7">G05, a control on Indian Punjab, was withdrawn before any of its data was opened. · Code: Apache-2.0 ·
Data: NASA FIRMS, geoBoundaries · Reproduce: python -m c08 check</p>
{src_line(["experiments/E02_evaluation/result.json (temporal_test)", "experiments/P02_F01_camera/result.json (decision)",
           "experiments/P04_G0[1-4]_*/result.json (approved, code_state, protocol_sha256)", "reports/c08/ingest_report.json",
           "experiments/PROTOCOL_P04.md (change log, entry 1, item 8)", "docs/REVIEW_P02_2026-11-03.md",
           "docs/REVIEW_P04_2026-11-05.md"], 7)}</section>""",
    ]
    if len(slides) != N_SLIDES:
        raise AssertionError(f"the deck must have exactly {N_SLIDES} slides")

    css = """
@page { size: 1280px 720px; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; background: #2a2a28; font-family: "Segoe UI", system-ui, sans-serif; color: #0b0b0b; }
.slide { width: 1280px; height: 720px; background: #fcfcfb; margin: 24px auto; padding: 40px 64px 0; position: relative; overflow: hidden; break-after: page; }
@media print { body { background: #fcfcfb; } .slide { margin: 0; } }
h1 { font-size: 50px; margin: 0 0 6px; } h1 span { font-size: 26px; font-weight: 400; color: #b7d3f6; margin-left: 12px; }
h2 { font-size: 36px; margin: 0 0 14px; line-height: 1.15; } h3 { font-size: 21px; margin: 6px 0; }
p, li { font-size: 20px; line-height: 1.38; }
.note { color: #52514e; font-size: 15px; margin: 4px 0 0; line-height: 1.35; }
.lead { font-size: 19px; margin: 0 0 12px; line-height: 1.38; }
.small { font-size: 16.5px; line-height: 1.38; margin: 8px 0; }
.src { position: absolute; left: 64px; right: 64px; bottom: 14px; margin: 0; display: flex; gap: 24px; justify-content: space-between;
  font-size: 12.5px; line-height: 1.3; color: #6e6c66; }
.src .pg { white-space: nowrap; align-self: flex-end; }
.cols { display: flex; gap: 32px; align-items: flex-start; } .cols.even > * { flex: 1; min-width: 0; }
.col-chart { flex: 1; min-width: 0; } .col-side { flex: 0 0 440px; } .col-side.wide3 { flex: 0 0 420px; }
.kpis.two .kpi { padding: 10px 12px; } .kpis.two .label { font-size: 16px; }
.img { width: 100%; }
.big { font-size: 50px; font-weight: 700; margin: 0; line-height: 1.1; } .red { color: #c93a39; } .blue { color: #2a78d6; } .grey { color: #52514e; }
.kpis { display: flex; gap: 20px; margin-bottom: 14px; } .kpis.two { margin: 8px 0; }
.kpi { flex: 1; border: 1px solid #e1e0d9; border-radius: 10px; padding: 12px 18px; margin-bottom: 12px; }
.kpis .kpi { margin-bottom: 0; } .kpi.naive { border: 2px dashed #c93a39; }
.kpi .label { color: #52514e; font-size: 17px; margin: 0 0 4px; font-weight: 600; } .kpi .sub { color: #52514e; font-size: 16px; margin: 4px 0 0; line-height: 1.35; }
.side-note { font-size: 16.5px; color: #52514e; margin: 4px 0 0; }
.badge { display: inline-block; font-size: 17px; font-weight: 700; padding: 2px 12px; border-radius: 999px; border: 1.5px solid #1d6b3f; color: #1d6b3f; background: #e6f2ea; white-space: nowrap; }
.fact { font-size: 18px; font-weight: 600; margin: 0 0 10px; }
ul.tight { margin: 4px 0; padding-left: 22px; } ul.tight li { margin-bottom: 8px; font-size: 18px; line-height: 1.36; }
.legend { display: flex; flex-wrap: wrap; gap: 4px 18px; font-size: 15px; color: #52514e; margin: 0 0 4px; }
.legend i { display: inline-block; width: 15px; height: 11px; border-radius: 2px; margin-right: 6px; vertical-align: -1px; }
.legend i.dash { background: transparent; border: 1.5px dashed #6e6c66; }
svg.chart { display: block; max-width: 100%; height: auto; font-family: "Segoe UI", system-ui, sans-serif; }
svg .grid { stroke: #e1e0d9; stroke-width: 1; } svg .axis { stroke: #c3c2b7; stroke-width: 1.2; }
svg .tick { fill: #52514e; font-size: 14px; } svg .val { fill: #0b0b0b; font-size: 14.5px; font-weight: 600; }
svg .val.strong { fill: #c93a39; } svg .year { fill: #0b0b0b; font-size: 18px; font-weight: 700; }
svg .missing { fill: none; stroke: #6e6c66; stroke-width: 1.4; stroke-dasharray: 4 3; }
svg .seam { fill: #c93a39; font-size: 14px; font-weight: 700; } svg .period { fill: #f0efec; }
/* slide 1: the dark title style */
.slide.dark { background: #0d366b; color: #f0efec; }
.dark .kicker { font-size: 18px; color: #b7d3f6; margin: 0 0 4px; }
.dark h2 { font-size: 30px; margin: 4px 0 10px; color: #ffffff; }
.dark svg .d-name { fill: #ffffff; font-size: 18px; font-weight: 700; } .dark svg .d-sub { fill: #b7d3f6; font-size: 14px; }
.dark svg .d-in { fill: #0b0b0b; font-size: 14px; } .dark svg .d-strong { font-weight: 700; }
.dark svg .d-mark { fill: #b7d3f6; font-size: 15px; font-weight: 600; } .dark svg .d-tick { fill: #b7d3f6; font-size: 14px; }
.callouts { display: flex; gap: 18px; margin-top: 10px; }
.callouts > div { flex: 1; border: 1px solid rgba(240, 239, 236, 0.35); border-radius: 10px; padding: 8px 14px; }
.callouts h3 { font-size: 19px; color: #ffffff; margin: 0 0 2px; } .callouts p { font-size: 17px; margin: 0; line-height: 1.35; color: #e6e5e1; }
.dark .who { font-size: 16px; color: #b7d3f6; margin: 10px 0 0; }
.dark .src { color: #9ec5f4; }
/* slide 5 */
.tri { display: flex; gap: 28px; } .tri > div { flex: 1; min-width: 0; }
.panel-h { font-size: 19px; font-weight: 700; margin: 0 0 2px; } .panel-h span { font-size: 15px; font-weight: 400; color: #52514e; margin-left: 8px; }
.res { font-size: 17px; font-weight: 700; margin: 4px 0 2px; line-height: 1.32; }
.rd { font-size: 14.5px; color: #33322f; margin: 0; line-height: 1.36; }
.key { font-size: 14px; color: #52514e; margin: 8px 0 0; }
.key i { display: inline-block; vertical-align: -1px; margin: 0 5px 0 10px; }
.key i:first-child { margin-left: 0; }
.key .dot { width: 11px; height: 11px; border-radius: 50%; background: #e34948; }
.key .ring { width: 10px; height: 10px; border-radius: 50%; border: 1.6px solid #8a8881; }
.key .per { width: 16px; height: 11px; background: #f0efec; border: 1px solid #c3c2b7; }
.key .mean { width: 18px; height: 0; border-top: 2px dashed #e34948; }
/* slide 6 */
table.matrix { border-collapse: separate; border-spacing: 6px; width: calc(100% + 12px); margin: -2px -6px 6px; table-layout: fixed; }
.matrix th { font-size: 16px; color: #52514e; font-weight: 600; text-align: center; padding: 2px 4px; line-height: 1.25; }
.matrix th span { font-weight: 400; } .matrix th.corner { width: 170px; }
.matrix th.prov { text-align: left; color: #0b0b0b; font-size: 18px; }
.matrix td { border-radius: 8px; padding: 7px 10px; vertical-align: top; height: 64px; }
.matrix td b { display: block; font-size: 17px; } .matrix td span { display: block; font-size: 14px; line-height: 1.3; margin-top: 2px; }
.c-hold { background: #e6f2ea; color: #1d6b3f; border: 1.5px solid #1d6b3f; }
.c-fail { background: #fbe4e3; color: #a12c2b; border: 1.5px solid #a12c2b; }
.c-nt { background: #f0efec; color: #52514e; border: 1.5px solid #c3c2b7; }
.c-dev { background: #fcfcfb; color: #52514e; border: 1.5px dashed #8a8881; }
.foot7 { position: absolute; left: 64px; right: 64px; bottom: 50px; margin: 0; font-size: 15px; color: #52514e; }
.card-h { font-size: 17px; font-weight: 700; margin: 14px 0 6px; }
.cards { display: flex; gap: 14px; } .cards > div { flex: 1; border: 1px solid #c3c2b7; border-radius: 10px; padding: 8px 12px; }
.cards p { font-size: 15.5px; margin: 0; line-height: 1.33; } .cards p.t { font-weight: 700; color: #52514e; margin-bottom: 3px; }
"""
    body = "".join(slides)
    for name in ("S-NPP", "NOAA-20", "NOAA-21"):  # a non-breaking hyphen keeps each name on one line
        body = body.replace(name, name.replace("-", "‑"))
    OUT_HTML.write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Seamline slides</title>
<meta name="viewport" content="width=1328"><style>{css}</style></head><body>{body}</body></html>""", encoding="utf-8")


def to_pdf() -> None:
    edge = next((p for p in report.EDGE if p.is_file()), None)
    if not edge:
        print("Microsoft Edge not found; HTML only.")
        return
    report.print_pdf(edge, OUT_HTML, OUT_PDF)


if __name__ == "__main__":
    build()
    to_pdf()
    print(OUT_HTML, OUT_PDF)
