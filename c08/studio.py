"""Comparison Studio: two selections side by side (two areas over one period, or one area over two periods).

Every number comes from c08.analysis.analyse for that pane's own selection: each area keeps its own calibration,
its own seasonal baseline and its own reference-scale statement. The summary never ranks areas by raw totals, and
it says plainly when a numerical difference is not available.
"""
from __future__ import annotations

import pandas as pd

from . import analysis, points

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")
SEASONS = {"OctNov": ("October–November", (10, 11)), "AprMay": ("April–May", (4, 5))}
PER_AREA_NOTE = ("Detections per 1,000 km² divides by the polygon's (or rectangle's) whole area. It does not correct "
                 "for how often or how clearly the area was observed, nor for sensor sensitivity.")
COVERAGE_NOTE = ("Known: which months each satellite's record covers, and the days the provider lists as missing. "
                 "Unknown: whether this area was seen through clear sky on a given pass.")


def _season(r: dict, key: str, year: int) -> dict:
    """The harmonised season total for one year against this area's own other years."""
    name, months = SEASONS[key]
    by_year: dict[int, list] = {}
    for m in r["months"]:
        y, mo = (int(v) for v in m["month"].split("-"))
        if mo in months:
            by_year.setdefault(y, []).append(m)
    def total(rows):
        return None if len(rows) != len(months) or any(x["H"] is None for x in rows) else sum(x["H"] for x in rows)
    def clean(rows):
        for x in rows:
            if x["H_flag"]:
                return False
            if int(x["month"][:4]) >= 2026:
                support = x.get("H_support") or {}
                if (support.get("flags") or support.get("stream") != "standard"
                        or support.get("type_screen") != "type0"
                        or support.get("declared_days") != support.get("days_in_month")
                        or not support.get("days_in_month")
                        or support.get("missing_dates") or support.get("no_row_dates")):
                    return False
        return True
    selected = by_year.get(year, [])
    value = total(selected)
    others = sorted((y, total(rows)) for y, rows in by_year.items() if y != year and total(rows) is not None and clean(rows))
    out = {"season": name, "year": year, "value": None if value is None else round(value, 1),
           "baseline_years": [y for y, _ in others], "baseline_n": len(others)}
    if value is None:
        out["status"] = "unavailable: no harmonised value for every month of this season"
    elif year >= 2026 and not clean(selected):
        out["status"] = ("not compared: the selected current season has partial, missing, untyped, unsupported or "
                         "incompatible processing support; a subtotal is not a complete historical season")
        out["support"] = [{"month": x["month"], "flag": x["H_flag"], "details": x.get("H_support")}
                          for x in selected]
    elif len(others) < 3:
        out["status"] = "not compared: fewer than 3 baseline years"
    else:
        med = float(pd.Series([v for _, v in others]).median())
        out.update(status="compared", median=round(med, 1), ratio=round((value + 1) / (med + 1), 2))
    return out


def pane(sel: dict) -> dict:
    """One side of the comparison: the analysis for its own selection, plus the facts a fair reading needs."""
    r = analysis.analyse(region=sel.get("region"), bbox=sel.get("bbox"), years=sel["years"], month=sel["month"],
                         model=sel.get("model", analysis.MODEL_DEFAULT))
    year, month = (int(v) for v in r["comparison"]["month"].split("-"))
    if sel.get("bbox"):
        area_km2, area_kind = points.box_area_km2(r["box"]["bbox"]), "rectangle (whole box, including any part outside Pakistan)"
    else:
        area_km2, area_kind = points.areas()["areas"][r["region"]]["area_km2"], "geoBoundaries ADM1 polygon"
    cal = r["calibration"]
    h = r["comparison"]["series"]["H"]
    mrow = next((m for m in r["months"] if m["month"] == r["comparison"]["month"]), None)
    flags = [m for m in r["months"] if m["H_flag"]]
    scope = ("This area's own calibration (Aqua to S-NPP, February 2012 to December 2017). The frozen held-out tests "
             "were run for Punjab; this area has cross-validation only." if cal["supported"] and r["region"] != "Punjab"
             else "This area's own calibration; Punjab is also the area of the frozen held-out tests." if cal["supported"]
             else "No calibration: " + "; ".join(cal.get("reasons", [])) + ". Only observed S-NPP months (from February 2012) have a value.")
    if sel.get("bbox"):
        scope += " A drawn rectangle has no test of its own: its conversion is fitted on its own overlap months and is not validated."
    per_area = None if h.get("value") is None or not area_km2 else round(h["value"] / area_km2 * 1000, 2)
    return {
        "region": r["region"], "bbox": r["box"]["bbox"] if r.get("box") else None, "box": r.get("box"),
        "years": r["years"], "month": r["comparison"]["month"], "month_name": f"{MONTHS[month - 1]} {year}",
        "model": r["model"], "units": r["units"], "reference": r["reference"], "passes": r["passes"],
        "supported": bool(cal["supported"]), "calibration_scope": scope,
        "cv_wape": cal["cv_agreement"]["model"]["wape"] if cal["supported"] else None,
        "area_km2": area_km2, "area_kind": area_kind,
        "month_value": h, "month_source": mrow["H_source"] if mrow else None,
        "per_1000_km2": per_area, "per_area_note": PER_AREA_NOTE,
        "seasons": {k: _season(r, k, year) for k in SEASONS},
        "coverage": {"note": COVERAGE_NOTE, "months_with_a_coverage_flag": len(flags), "months_total": len(r["months"]),
                     "selected_month_flag": mrow["H_flag"] if mrow else None},
        "warnings": r["warnings"],
        "calendar": r["calendar"]["H"],
        "series": [{"month": m["month"], "H": m["H"], "H_lo": m["H_lo"], "H_hi": m["H_hi"], "source": m["H_source"],
                    "flag": m["H_flag"], **({"support": m["H_support"]} if "H_support" in m else {})}
                   for m in r["months"]],
        "export": r["export"],
    }


def _reading(a: dict, b: dict) -> dict:
    """What may be said about the pair, and why a number is missing when it is."""
    same_area = a["region"] == b["region"] and a["bbox"] == b["bbox"]
    same_month = a["month"] == b["month"]
    mode = ("the same selection twice" if same_area and same_month and a["years"] == b["years"]
            else "one area, two periods" if same_area else "two areas, the same period" if same_month
            else "two areas and two periods")
    ha, hb = a["month_value"], b["month_value"]
    out = {"mode": mode, "notes": [], "difference": None, "ratio_of_normals": None}
    why = []
    for name, p, h in (("A", a, ha), ("B", b, hb)):
        if h.get("value") is None:
            why.append(f"pane {name} has no harmonised value for {p['month_name']} ({p['month_source'] or 'no value'})")
        elif not str(h.get("status", "")).startswith("compared"):
            why.append(f"pane {name}: {h.get('status')}")
    if a["model"] != b["model"]:
        why.append(f"the panes use different models ({a['model']} and {b['model']}), so their converted values are not on one footing")
    if why:
        out["unavailable"] = "A numerical difference is not shown: " + "; ".join(why) + "."
        return out
    out["ratio_of_normals"] = {"a": ha["ratio"], "b": hb["ratio"],
                               "definition": "(detections + 1) ÷ (median of the same month in the pane's other years + 1)"}
    if same_area:
        out["difference"] = {"value": round(hb["value"] - ha["value"], 1), "ratio": round((hb["value"] + 1) / (ha["value"] + 1), 2),
                             "definition": f"{b['month_name']} minus {a['month_name']}, harmonised detections (S-NPP-equivalent), same area"}
        srcs = {a["month_source"], b["month_source"]}
        if len(srcs) > 1:
            out["notes"].append("One month is observed S-NPP and the other is converted from Aqua. Converted months were "
                                "tested on whole months only, and their rough ranges were too narrow in testing.")
    else:
        out["notes"].append("Raw totals are not compared across areas: a larger or more often observed area yields more "
                            "detections for the same burning. Each area is read against its own normal instead.")
        word = {"above": "above", "below": "below", "typical": "typical for"}
        out["notes"].append(f"Pane A is {word[ha['cls']]} its own normal ({ha['ratio']}×); pane B is {word[hb['cls']]} its own normal "
                            f"({hb['ratio']}×).")
    out["notes"].append("Both values are on the S-NPP-equivalent scale. S-NPP is a reference satellite, not ground truth.")
    return out


def compare(a: dict, b: dict) -> dict:
    pa, pb = pane(a), pane(b)
    return {"a": pa, "b": pb, "reading": _reading(pa, pb),
            "definitions": {"units": pa["units"], "reference": pa["reference"],
                            "baseline": "each pane's own: the median of the same month (or season) in the other years "
                                        "of its range that have full coverage; at least 3 years",
                            "above_below": "above: more than 1.5 times that median; below: less than two-thirds of it (+1 "
                                           "on both sides so empty months count)",
                            "per_area": PER_AREA_NOTE, "coverage": COVERAGE_NOTE}}
