"""Checks CHECK REPORT P04 asks for before any P04 test data is opened (B2, B3, B5, B6).

Punjab is P04's development area and is already seen (PROTOCOL_P04.md, section 0). This
module reads detection counts for Punjab only:
  - G01: Punjab's raw Terra/S-NPP ratio, November and October-November, 2018-2025 (B5);
  - G02: Punjab's rice-season (15 Sep-31 Dec) middle and end dates, Aqua and NOAA-20
    against S-NPP (B6; tolerances and floors).
It never reads another province, never a spring window, never 2026 counts and never India.
For those, it reports availability from the FIRMS missing-days lists and each platform's archive
span (the first and last day of its record in the whole Pakistan table): dates, never counts.

Second version, 5 Nov evening (after the Opus check of change-log entry 1): G02's date gap is also
counted in matched days, dates use whole-number cumulative counts, and the detections file read is
hashed and compared with the ingest report.

Two day rules are compared, so the change log can show what each does on Punjab:
  - "months": P04 as written, only months complete for both satellites (P01 change log, item 2);
  - "matched": every day of the window that neither satellite's record lists as missing.

    python -m c08.p04_devcheck      ->  reports/c08/p04_devcheck.json
"""
from __future__ import annotations

import hashlib
import json
import sys

import numpy as np
import pandas as pd

from . import config, ingest, p02_posthoc, series

OUT = config.REPORTS / "p04_devcheck.json"
PROTOCOL = "experiments/PROTOCOL_P04.md"
AREA = "Punjab"  # the development area; nothing else is counted here
G01_YEARS, G01_BEFORE, G01_AFTER = tuple(range(2018, 2026)), (2018, 2019, 2020, 2021), (2023, 2024, 2025)
S_FLOOR, T_FLOOR = 300, 20  # G01 floors (PROTOCOL_P04.md section 1)
RICE = ("09-15", "12-31")
SPRING = ("03-15", "06-30")  # availability only: no spring count is ever read here
PAIRS = {"Aqua-SNPP": ("Aqua", "SNPP", range(2012, 2026)), "NOAA20-SNPP": ("NOAA20", "SNPP", range(2018, 2026))}
MID_TOL, END_TOL = 3, 4


def _missing(stream: str = "standard") -> dict[str, set]:
    m = series.provider_missing()
    m = m[m["stream"] == stream]
    return {p: set(g["date"]) for p, g in m.groupby("platform")}


def _days(y: int, a: str, b: str) -> pd.DatetimeIndex:
    return pd.date_range(f"{y}-{a}", f"{y}-{b}", freq="D")


def _covered(days, plats, spans, miss) -> list[pd.Timestamp]:
    """Days inside every satellite's archive record and listed missing for none of them."""
    out = []
    for t in days:
        if all(p in spans and spans[p][0] <= t <= spans[p][1] and t not in miss.get(p, set()) for p in plats):
            out.append(t)
    return out


def _complete_month_days(days, plats, spans, miss) -> list[pd.Timestamp]:
    """P04 as written: keep a whole month only if every day of it is covered for both satellites."""
    keep = []
    for _, g in pd.Series(days, index=days).groupby(days.to_period("M")):
        month_days = pd.date_range(g.index[0].to_period("M").start_time, g.index[0].to_period("M").end_time.normalize())
        if len(_covered(month_days, plats, spans, miss)) == len(month_days):
            keep.extend(g.index)
    return keep


def _punjab_day_rows(d: pd.DataFrame) -> pd.DataFrame:
    q = series.select(d, region=AREA)  # standard stream, quality rule, type-0 screen
    return q[q["daynight"] == "D"]


def g01(d: pd.DataFrame, spans, miss) -> dict:
    """B5: Punjab's raw R = Terra / S-NPP day-pass detections under G01's rules, both day rules."""
    rows = _punjab_day_rows(d)
    daily = rows.groupby(["platform", "date_utc"], observed=True).size()
    count = lambda p, ds: int(sum(daily.get((p, t), 0) for t in ds))
    out = {}
    for rule in ("months", "matched"):
        res = {}
        for label, (a, b) in (("OctNov", ("10-01", "11-30")), ("Nov", ("11-01", "11-30"))):
            per = {}
            for y in G01_YEARS:
                days = _days(y, a, b)
                use = (_complete_month_days(days, ("Terra", "SNPP"), spans, miss) if rule == "months"
                       else _covered(days, ("Terra", "SNPP"), spans, miss))
                t, s = count("Terra", use), count("SNPP", use)
                per[y] = {"days": len(use), "of": len(days), "terra": t, "snpp": s, "R": (t / s) if s else None}
            base = [per[y]["R"] for y in G01_BEFORE if per[y]["snpp"] >= S_FLOOR and per[y]["R"] is not None]
            mean_r = float(np.mean(base)) if base else None
            for y, v in per.items():
                v["expected_terra"] = None if mean_r is None else v["snpp"] * mean_r
                v["eligible"] = bool(v["snpp"] >= S_FLOOR and mean_r is not None and v["expected_terra"] >= T_FLOOR)
            res[label] = {"years": {str(y): v for y, v in per.items()}, "mean_R_2018_21_eligible": mean_r}
            elig = {y: v["R"] for y, v in per.items() if v["eligible"]}
            q = pd.Series(elig)
            before = [y for y in G01_BEFORE if y in elig]
            after = [y for y in G01_AFTER if y in elig]
            if label == "OctNov" and len(before) >= 3 and len(after) >= 2:
                perm = p02_posthoc.permutation(q, before=tuple(before), after=tuple(after))
                res[label]["fall"] = {"delta": float(np.mean([elig[y] for y in after]) / np.mean([elig[y] for y in before]) - 1),
                                      "years_before": before, "years_after": after,
                                      "p_one_sided_as_low": perm["p_as_low"], "splits": perm["splits"]}
            if label == "Nov":
                nov_base = [elig[y] for y in G01_BEFORE if y in elig]
                if 2022 in elig and len(nov_base) >= 3:
                    res[label]["step"] = {"R_2022": elig[2022], "mean_2018_21": float(np.mean(nov_base)),
                                          "ratio_to_mean": float(elig[2022] / np.mean(nov_base)),
                                          "below_every": bool(all(elig[2022] < r for r in nov_base)),
                                          "years_in_baseline": [y for y in G01_BEFORE if y in elig]}
        out[rule] = res
    return out


def _dates(counts: pd.Series) -> tuple[int, int]:
    """Positions (in the matched-day sequence) of the middle and end dates, in whole numbers:
    middle = first day with 2 x cumulative >= total; end = first day with 10 x cumulative >= 9 x total."""
    c = counts.to_numpy(dtype=np.int64)
    cum, tot = np.cumsum(c), int(c.sum())
    return int(np.argmax(2 * cum >= tot)), int(np.argmax(10 * cum >= 9 * tot))


def g02_rice(d: pd.DataFrame, spans, miss) -> dict:
    """B6: Punjab's rice-season dates under G02's rules, both day rules, every floor of interest."""
    rows = _punjab_day_rows(d)
    daily = rows.groupby(["platform", "date_utc"], observed=True).size()
    out = {}
    for name, (src, ref, years) in PAIRS.items():
        per = {}
        for y in years:
            days = _days(y, *RICE)
            matched = _covered(days, (src, ref), spans, miss)
            listed = len(matched) < len(days)
            row = {"days_matched": len(matched), "of": len(days), "window_has_listed_or_uncovered_day": listed}
            if matched:
                cs = pd.Series([daily.get((src, t), 0) for t in matched], index=matched, dtype=float)
                cr = pd.Series([daily.get((ref, t), 0) for t in matched], index=matched, dtype=float)
                row.update(n_src=int(cs.sum()), n_ref=int(cr.sum()))
                if cs.sum() and cr.sum():
                    (ms, es), (mr, er) = _dates(cs), _dates(cr)
                    day = lambda i: matched[i]
                    row.update(mid_src=str(day(ms).date()), mid_ref=str(day(mr).date()),
                               end_src=str(day(es).date()), end_ref=str(day(er).date()),
                               # The test's gap: positions in the matched-day sequence (removed days don't count).
                               d_mid=ms - mr, d_end=es - er,
                               # For comparison: the same gap in calendar days.
                               d_mid_calendar=int((day(ms) - day(mr)).days), d_end_calendar=int((day(es) - day(er)).days))
            per[y] = row
        out[name] = {"years": {str(y): v for y, v in per.items()}, "summary": {}}
        for floor in (100, 200, 300):
            for rule in ("as_written", "matched", "matched_but_calendar_gap"):
                ok = [v for v in per.values() if "d_mid" in v and v["n_src"] >= floor and v["n_ref"] >= floor
                      and (not v["window_has_listed_or_uncovered_day"] if rule == "as_written" else v["days_matched"] >= 100)]
                n = len(ok)
                gap = (lambda v, k: v[k + "_calendar"]) if rule == "matched_but_calendar_gap" else (lambda v, k: v[k])
                mid_miss = sum(abs(gap(v, "d_mid")) > MID_TOL for v in ok)
                end_miss = sum(abs(gap(v, "d_end")) > END_TOL for v in ok)
                allow_written = 2
                allow_80 = int(np.floor(0.2 * n))
                out[name]["summary"][f"floor{floor}_{rule}"] = {
                    "eligible_years": n, "middle_misses": mid_miss, "end_misses": end_miss,
                    "holds_all_but_2": {"middle": n >= 6 and mid_miss <= allow_written, "end": n >= 6 and end_miss <= allow_written},
                    "holds_80pct": {"middle": n >= 6 and mid_miss <= allow_80, "end": n >= 6 and end_miss <= allow_80,
                                    "misses_allowed": allow_80},
                    "max_abs_d_mid": max((abs(gap(v, "d_mid")) for v in ok), default=None),
                    "max_abs_d_end": max((abs(gap(v, "d_end")) for v in ok), default=None)}
    return out


def availability(spans, miss, miss_nrt) -> dict:
    """Metadata only: matched days per window, from the missing-days list and archive spans. No counts."""
    out = {"G01_Terra_SNPP_OctNov": {}, "G02": {}, "G03_2026": {}}
    for y in G01_YEARS:
        out["G01_Terra_SNPP_OctNov"][str(y)] = {
            "OctNov": len(_covered(_days(y, "10-01", "11-30"), ("Terra", "SNPP"), spans, miss)),
            "Nov": len(_covered(_days(y, "11-01", "11-30"), ("Terra", "SNPP"), spans, miss))}
    for name, (src, ref, years) in PAIRS.items():
        for win, (a, b) in (("rice", RICE), ("spring", SPRING)):
            out["G02"][f"{name}_{win}"] = {str(y): len(_covered(_days(y, a, b), (src, ref), spans, miss)) for y in years}
    # 2026: both lists, either satellite; S-NPP's last day is 2 Nov 2026 (NOAA NESDIS Update #4).
    listed = {p: miss.get(p, set()) | miss_nrt.get(p, set()) for p in ("SNPP", "NOAA20")}
    for mo in range(1, 11):
        days = pd.date_range(f"2026-{mo:02d}-01", pd.Period(f"2026-{mo:02d}").end_time.normalize())
        ok = [t for t in days if not any(t in listed[p] for p in ("SNPP", "NOAA20"))]
        out["G03_2026"][f"2026-{mo:02d}"] = {"days_matched": len(ok), "of": len(days)}
    return out


def main() -> dict:
    rep = json.loads(ingest.INGEST_REPORT.read_text(encoding="utf-8"))
    read_sha = hashlib.sha256(ingest.DETECTIONS.read_bytes()).hexdigest()
    if read_sha != rep["output_sha256"]:
        raise SystemExit("The processed detections differ from the ingest report; rebuild with python -m c08.ingest")
    d = pd.read_parquet(ingest.DETECTIONS)
    spans = series.record_spans(d)
    miss, miss_nrt = _missing("standard"), _missing("nrt")
    out = {
        "purpose": "CHECK REPORT P04 items B2, B3, B5 and B6, before any P04 test data is opened. Punjab only "
                   "(P04's development area, already seen); every other place, the spring window and 2026 come "
                   "from the FIRMS missing-days lists and each platform's archive span (dates, no counts).",
        "area_counted": AREA,
        "filters": "standard stream, quality rule (MODIS confidence >= 30; VIIRS n/h), type-0 screen, day pass",
        "inputs": {"detections_sha256": read_sha, "detections_sha256_matches_ingest_report": True,
                   "missing_days_list": series.MISSING_DATES.relative_to(config.ROOT).as_posix(),
                   "missing_days_sha256": hashlib.sha256(series.MISSING_DATES.read_bytes()).hexdigest()},
        "spans": {p: [str(a.date()), str(b.date())] for p, (a, b) in spans.items()},
        "code_state": ingest.code_state(),
        **ingest.protocol_state(PROTOCOL),
        "availability": availability(spans, miss, miss_nrt),
        "G01_punjab": g01(d, spans, miss),
        "G02_punjab_rice": g02_rice(d, spans, miss),
    }
    OUT.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
    print(OUT)
