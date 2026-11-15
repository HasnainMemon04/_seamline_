"""Protocol P04 runner: tests G01, G02, G03 and G04, each run once (G05 is withdrawn).

    python -m c08.p04 preflight                      checks the inputs only; counts no detection
    python -m c08.p04 g01g02 --approved "<text>"    G01 and G02 in one invocation (change log, item 5)
    python -m c08.p04 g03g04 --approved "<text>"    after the 2026 download
    python -m c08.p04 punjab-check                   practice on Punjab only (the development area): G01's and
                                                     G02's own functions, compared with reports/c08/p04_devcheck.json;
                                                     writes nothing and is never a test

The rules are experiments/PROTOCOL_P04.md: its body plus change-log entry 1, which governs where
the two differ. Runs start only after the checker's CHECK REPORT P04-CL or Hasnain's go-ahead; the
--approved text is that permission, and every result records it. A run also refuses while c08/ has
uncommitted changes (ingest.code_state()), so every result names the code that made it. Results go to
experiments/P04_G01_terra_step, P04_G02_season_dates, P04_G03_bridge_2026 and P04_G04_headline
(result.json each), each pair written together or not at all. Nothing is ever overwritten. Writing the
G01 and G02 results also lifts the app's P04 lock (c08/analysis.py), as that lock intends.

Every result records the platforms, streams, filters, days and months used, the eligible years
with each exclusion's reason, the input hashes, ingest.code_state() and ingest.protocol_state().
The processed detections file is hashed as it is read and must match
reports/c08/ingest_report.json. Every comparison uses unrounded values; rounding is for display.

Words: a detection is one fire pixel on one satellite pass (detected burning activity, never
"fires"). Satellites are never added together, except in G04's sum, which is labelled as the press
method (a naive sum). Missing data is reported as missing, never as zero.

2026 inputs for G03 and G04 (the downloader writes them):
  - data/raw/firms_api/<SOURCE>/<START>_<DAYS>d.csv, SOURCE one of VIIRS_SNPP_SP, VIIRS_SNPP_NRT,
    VIIRS_NOAA20_SP, VIIRS_NOAA20_NRT, VIIRS_NOAA21_NRT;
  - data/manifest.json "files" entries of kind "firms_api_csv" (id, path, source, start, days, bbox,
    sha256, retrieved_utc, url_redacted). Each file is hash-checked before it is read;
  - research/metadata/firms_data_availability_<YYYY-MM-DD>.json, FIRMS's availability answer;
  - research/metadata/provider_missing_dates_<YYYY-MM-DD>.json, the refreshed missing-days list
    (same rows as research/metadata/provider_missing_dates.json).
The newest dated file of each kind is used unless --availability or --missing names one.
G01 and G02 use the committed list research/metadata/provider_missing_dates.json only.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import platform as _platform
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import acquire, config, harmonize as hz, ingest, p01, p02_posthoc, series

PROTOCOL = "experiments/PROTOCOL_P04.md"
RESULTS = {"G01": "P04_G01_terra_step", "G02": "P04_G02_season_dates",
           "G03": "P04_G03_bridge_2026", "G04": "P04_G04_headline"}
TESTED = ("Sindh", "Khyber Pakhtunkhwa")  # held out: P04's test provinces
DEV_AREA = "Punjab"  # P04's development area: its numbers were seen before the tests
NAMES = {"Terra": "Terra", "Aqua": "Aqua", "SNPP": "S-NPP", "NOAA20": "NOAA-20", "NOAA21": "NOAA-21"}
QUALITY_RULE = (f"MODIS confidence >= {config.MODIS_MIN_CONFIDENCE}; VIIRS confidence nominal or high "
                f"({'/'.join(config.VIIRS_KEEP_CONFIDENCE)})")
ARCHIVE_FILTERS = f"standard stream; quality rule ({QUALITY_RULE}); type-0 screen; day passes only (daynight D)"

# ---------- G01: Terra's fall outside Punjab (entry 1, item 3) ----------
G01_YEARS = tuple(range(2018, 2026))
G01_BEFORE, G01_AFTER, STEP_YEAR = (2018, 2019, 2020, 2021), (2023, 2024, 2025), 2022
G01_WINDOWS = {"OctNov": ("10-01", "11-30"), "Nov": ("11-01", "11-30")}
S_FLOOR, T_FLOOR = 300, 20  # S-NPP day-pass detections; expected Terra detections
FALL_DELTA, FALL_P, STEP_FACTOR = -0.40, 0.10, 0.6
MIN_BEFORE, MIN_AFTER, MIN_STEP_BASE = 3, 2, 3
FALL_CLAUSE = {"present": "Terra's fall is also seen",
               "large_not_significant": "a large fall, not significant with these years",
               "not_seen": "Terra's fall is not seen; this does not rule out the clock, because burning "
                           "hours may differ between provinces"}
FALL_SHORT = {"present": "Terra's fall is also seen", "large_not_significant": "a large fall, not significant",
              "not_seen": "Terra's fall is not seen", "not_testable": "the fall is not testable"}
STEP_CLAUSE = {"present": "a 2022 step is seen", "absent": "no 2022 step is seen"}
BOTH_PRESENT = ("This is consistent with a satellite-side cause (the pass time, the October 2022 orbit change, "
                "or both); a Pakistan-wide change in burning hours would give the same result; untested.")
STRIP_TITLE = "Morning and afternoon passes see different shares"

# ---------- G02: season dates (entry 1, item 4) ----------
G02_WINDOWS = {"rice": ("09-15", "12-31"), "spring": ("03-15", "06-30")}
WINDOW_TEXT = {"rice": "rice season (15 Sep–31 Dec)", "spring": "spring season (15 Mar–30 Jun)"}
G02_PROVINCES = {"rice": TESTED, "spring": ("Punjab",) + TESTED}  # Punjab's rice dates were seen: not tested
PAIRS = {"Aqua-SNPP": ("Aqua", "SNPP", tuple(range(2012, 2026))),
         "NOAA20-SNPP": ("NOAA20", "SNPP", tuple(range(2018, 2026)))}
G02_MIN_DAYS, G02_FLOOR, MID_TOL, END_TOL, G02_MIN_YEARS = 100, 200, 3, 4, 6
SAME_LABEL = "the same on the older and newer satellites (Aqua and S-NPP)"
DEV_LABEL = "development area (dates seen before the test)"
BAND_TITLE = "the season's middle and end dates (detected burning activity)"

# ---------- G03 and G04: 2026 (entry 1, items 6 and 7) ----------
# FIRMS area-API source -> (platform, stream, the c08.ingest source key whose expected platform it shares).
API_SOURCES = {"VIIRS_SNPP_SP": ("SNPP", "SP", "SNPP_NRT"), "VIIRS_SNPP_NRT": ("SNPP", "NRT", "SNPP_NRT"),
               "VIIRS_NOAA20_SP": ("NOAA20", "SP", "NOAA20_NRT"), "VIIRS_NOAA20_NRT": ("NOAA20", "NRT", "NOAA20_NRT"),
               "VIIRS_NOAA21_NRT": ("NOAA21", "NRT", "NOAA21_NRT")}
G03_MONTHS = tuple(f"2026-{m:02d}" for m in range(1, 11))  # November and December are never scored
G03_MIN_DAYS, G03_MIN_MONTHS = 20, 6
WAPE_MARK, MONTH_MARK, MONTH_FLOOR = 0.10, 0.20, 300
REPORTED = ("Pakistan", "Sindh", "Khyber Pakhtunkhwa")  # reported, not held to the pass mark
SEAM_LABEL = "S-NPP ended 2 Nov 2026, 15:40 UTC (NOAA NESDIS Update #4)"
G03_READING = {
    "pass": ("Pass: from November 2026 Punjab's harmonised record continues on NOAA-20, converted by the primary "
             "bridge, in whole months only (no month mixes satellites). After October 2026 NOAA-20's files are "
             "near-real-time with no type field, so the primary bridge fitted without the type screen is used. The "
             f"seam is drawn and labelled '{SEAM_LABEL}'. NOAA-21 appears only as its own labelled series, never "
             "summed. Other areas show NOAA-20 in its own units after S-NPP's end, labelled 'bridge tested in Punjab "
             "only'."),
    "fail": ("Fail: the harmonised record stops at October 2026, the last full S-NPP month, and the app says that "
             "the NOAA-20 bridge failed its frozen test. NOAA-20 is shown in its own units."),
    "not_testable": ("Not testable: the harmonised record stops at October 2026, the app says 'the NOAA-20 bridge "
                     "was not tested (too few months with matched data)', and NOAA-20 is shown in its own units."),
}
M0_NOTE = ("M0 (no conversion) is reported beside the bridge: a pass shows that converted NOAA-20 tracks S-NPP "
           "within the marks, not that M1 beats no conversion.")
G04_MONTH, G04_DAYS = "2026-10", ("2026-10-01", "2026-10-29")
PRESS_SUM, PRESS_SNPP, PRESS_TOL = 13241, 4562, 0.20
G04_READING = {
    (True, True): "Reproduced",
    (True, False): ("The three-satellite sum matches the press figure, S-NPP alone does not: the published "
                    "single-satellite count may use another method"),
    (False, True): "S-NPP alone matches; the sum does not: the press may have summed other satellites or streams",
    (False, False): "Not reproduced; the published method may differ (area, filters or stream)",
}
NAIVE_LABEL = "a naive sum of satellites, not comparable across years"
# Contract failures that mean this code misreads a 2026 file (an unknown satellite code or spelling): refuse,
# rather than let a format mismatch decide a run-once result. Rows outside the Pakistan box are normal.
FORMAT_REASONS = ("bad_platform", "bad_confidence", "bad_daynight", "bad_time", "bad_type", "bad_version")
_KEYLIKE = re.compile(r"(?<![0-9A-Za-z])[0-9A-Fa-f]{32}(?![0-9A-Za-z])")  # FIRMS MAP_KEYs are 32 hex digits
# Item 6.2 chooses each month's stream from these two ranges; without either, every month would silently be NRT.
SP_SOURCES = ("VIIRS_SNPP_SP", "VIIRS_NOAA20_SP")
# Item 6.3 reads the refreshed list's standard and NRT rows for the VIIRS satellites. Any other stream label, or a
# VIIRS name this code cannot map, would drop listed days without a word, so a run refuses instead.
STREAM_LABELS = ("standard", "nrt")  # compared case-insensitively
VIIRS_PLATFORMS = ("SNPP", "NOAA20", "NOAA21")
_VIIRS_NAME = re.compile(r"viirs|npp|noaa|jpss|suomi", re.I)
# The rows each count is made of (G03 and G04 filters).
POLYGONS_TEXT = ("'Pakistan' means all seven geoBoundaries ADM1 polygons (Azad Kashmir, Balochistan, Gilgit-Baltistan, "
                 "Islamabad Capital Territory, Khyber Pakhtunkhwa, Punjab, Sindh)")
ROWS_2026_TEXT = ("rows that pass c08.ingest.parse_frame's data contract, with exact duplicates removed (same platform, "
                  "UTC time, latitude, longitude and version), from the FIRMS area-API download box recorded with each "
                  "file (data/manifest.json, bbox) intersected with the province polygons")
ROWS_ARCHIVE_TEXT = ("FIRMS's Pakistan country file (standard stream, c08.ingest) intersected with the same province "
                     "polygons")


# ---------- shared helpers ----------

def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _iso(t: pd.Timestamp) -> str:
    return t.strftime("%Y-%m-%d")


def _n(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _rel(p: Path) -> str:
    try:
        return Path(p).resolve().relative_to(config.ROOT.resolve()).as_posix()
    except ValueError:
        return Path(p).as_posix()


def _redact(url) -> str | None:
    """A stored URL never carries the MAP_KEY (entry 1, item 6.1)."""
    return None if url is None else _KEYLIKE.sub("<MAP_KEY>", str(url))


def _ranges(days) -> str:
    """Compact text for a list of days: 2026-03-01..2026-03-09, 2026-04-02."""
    days = sorted(pd.Timestamp(t) for t in days)
    out, start, prev = [], None, None
    for t in days:
        if start is None:
            start = prev = t
        elif (t - prev).days == 1:
            prev = t
        else:
            out.append(_iso(start) if start == prev else f"{_iso(start)}..{_iso(prev)}")
            start = prev = t
    if start is not None:
        out.append(_iso(start) if start == prev else f"{_iso(start)}..{_iso(prev)}")
    return ", ".join(out)


def _jsonable(x):
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, set):
        return [_jsonable(v) for v in sorted(x)]
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, (float, np.floating)):
        v = float(x)
        return v if math.isfinite(v) else None
    if isinstance(x, pd.Timestamp):
        return _iso(x) if x == x.normalize() else x.isoformat()
    if isinstance(x, Path):
        return x.as_posix()
    return x


def window_days(year: int, a: str, b: str) -> pd.DatetimeIndex:
    return pd.date_range(f"{year}-{a}", f"{year}-{b}", freq="D")


def month_days(month: str) -> pd.DatetimeIndex:
    p = pd.Period(month, freq="M")
    return pd.date_range(p.start_time.normalize(), p.end_time.normalize(), freq="D")


def matched_days(days, plats, spans: dict, miss: dict) -> list[pd.Timestamp]:
    """Entry 1, item 2: days inside every compared satellite's archive record and listed missing for none."""
    return [t for t in days
            if all(p in spans and spans[p][0] <= t <= spans[p][1] and t not in miss.get(p, ()) for p in plats)]


def days_needed(n_days: int) -> int:
    """At least 90% of a G01 window's days: 55 of 61, 27 of 30."""
    return -(-9 * n_days // 10)


def days_rule_met(n_matched: int, n_days: int) -> bool:
    return 10 * n_matched >= 9 * n_days


def misses_allowed(n_years: int) -> int:
    """G02: floor(0.2 x n) eligible years may miss a date's tolerance (1 at 6-9 years, 2 at 10-14)."""
    return n_years // 5


def season_dates(counts) -> tuple[int, int]:
    """Positions of the middle and end dates in a matched-day sequence, in whole numbers (entry 1, item 4.1):
    middle = first day with 2 x cumulative >= total; end = first day with 10 x cumulative >= 9 x total."""
    c = np.asarray(counts, dtype=np.int64)
    total = int(c.sum())
    if total <= 0:
        raise ValueError("no detections in the window: no date")
    cum = np.cumsum(c)
    return int(np.argmax(2 * cum >= total)), int(np.argmax(10 * cum >= 9 * total))


def load_archive(detections=None, report=None) -> tuple[pd.DataFrame, dict, str]:
    """Read the processed detections, hashing the very bytes that are read; refuse if the ingest report differs."""
    detections, report = Path(detections or ingest.DETECTIONS), Path(report or ingest.INGEST_REPORT)
    if not detections.is_file() or not report.is_file():
        raise SystemExit("Refusing to run: the processed detections or the ingest report is missing; "
                         "run python -m c08.ingest first")
    rep = json.loads(report.read_text(encoding="utf-8"))
    raw = detections.read_bytes()
    sha = _sha(raw)
    if sha != rep.get("output_sha256"):
        raise SystemExit("Refusing to run: the processed detections file's SHA-256 differs from the ingest report; "
                         "rebuild it with python -m c08.ingest")
    return pd.read_parquet(io.BytesIO(raw)), rep, sha


def load_missing(path) -> tuple[dict, dict]:
    """A FIRMS missing-days list -> {"standard": {platform: {days}}, "nrt": {...}}, plus its path and hash."""
    path = Path(path)
    raw = path.read_bytes()
    rows = json.loads(raw.decode("utf-8-sig"))
    lists: dict[str, dict[str, set]] = {"standard": {}, "nrt": {}}
    unused = set()
    for r in rows:
        p = series.PROVIDER_NAMES.get(r.get("satellite"))
        if p is None:
            unused.add(str(r.get("satellite")))
            continue
        lists.setdefault(str(r.get("stream", "")).lower(), {}).setdefault(p, set()).add(pd.Timestamp(r["date"]).normalize())
    # The labels as written, so a run can refuse one it would otherwise skip without a word (missing_label_problems).
    labels = sorted({str(r.get("stream", "")) for r in rows})
    viirs_unmapped = sorted({str(r.get("satellite")) for r in rows if _VIIRS_NAME.search(str(r.get("satellite", "")))
                             and series.PROVIDER_NAMES.get(r.get("satellite")) not in VIIRS_PLATFORMS})
    return lists, {"path": _rel(path), "sha256": _sha(raw), "entries": len(rows), "satellites_not_used": sorted(unused),
                   "stream_labels": labels, "viirs_names_not_mapped": viirs_unmapped}


def missing_label_problems(meta: dict) -> list[str]:
    """G03/G04 (item 6.3) read the refreshed list's standard and NRT rows for S-NPP, NOAA-20 and NOAA-21. A stream
    label other than standard/NRT (any case), or a VIIRS satellite name that maps to none of the three, would leave
    listed days out silently (a missing day read as present), so the run refuses instead."""
    out = []
    bad = [s for s in meta.get("stream_labels", []) if s.lower() not in STREAM_LABELS]
    if bad:
        out.append(f"the refreshed missing-days list has stream labels other than standard and NRT: {bad}")
    if meta.get("viirs_names_not_mapped"):
        out.append("the refreshed missing-days list has VIIRS satellite names that map to none of S-NPP, NOAA-20 and "
                   f"NOAA-21: {meta['viirs_names_not_mapped']}")
    return out


def day_pass_counts(d: pd.DataFrame, provinces) -> dict:
    """{(province, platform, day): day-pass detections}, standard stream, quality rule, type-0 screen.
    Only the named provinces are counted."""
    q = series.select(d)  # standard stream, quality rule, type-0 screen
    q = q[q["daynight"].astype(str).eq("D") & q["province"].astype(str).isin(list(provinces))]
    s = q.groupby([q["province"].astype(str), q["platform"].astype(str), q["date_utc"]]).size()
    return {(a, b, pd.Timestamp(t)): int(v) for (a, b, t), v in s.items()}


def _count(counts: dict, prov: str, plat: str, days) -> int:
    return int(sum(counts.get((prov, plat, t), 0) for t in days))


# ---------- G01 ----------

def g01_window(counts: dict, prov: str, window: str, spans: dict, miss: dict) -> tuple[dict, float | None]:
    """Per year: matched days, Terra and S-NPP day-pass detections on them, R, and both floors (items 3.1, 3.2)."""
    a, b = G01_WINDOWS[window]
    what = "October–November" if window == "OctNov" else "November"
    rows = {}
    for y in G01_YEARS:
        days = window_days(y, a, b)
        use = matched_days(days, ("Terra", "SNPP"), spans, miss)
        kept = set(use)
        t, s = _count(counts, prov, "Terra", use), _count(counts, prov, "SNPP", use)
        rows[y] = {"days_in_window": len(days), "days_matched": len(use), "days_needed": days_needed(len(days)),
                   "days_removed": [_iso(x) for x in days if x not in kept],
                   "days_rule_met": days_rule_met(len(use), len(days)),
                   "terra": t, "snpp": s, "R": (t / s) if s else None, "snpp_floor_met": s >= S_FLOOR}
    # The expected-Terra floor uses the mean R of the 2018-21 window-years that count (90% of days) and pass the
    # S-NPP floor (open choice 1; for the step test, November counts alone).
    base = [rows[y]["R"] for y in G01_BEFORE if rows[y]["days_rule_met"] and rows[y]["snpp_floor_met"]]
    base_mean = float(np.mean(base)) if base else None
    for y, r in rows.items():
        r["expected_terra"] = None if base_mean is None else r["snpp"] * base_mean
        r["terra_floor_met"] = r["expected_terra"] is not None and r["expected_terra"] >= T_FLOOR
        r["eligible"] = bool(r["days_rule_met"] and r["snpp_floor_met"] and r["terra_floor_met"])
        why = []
        if not r["days_rule_met"]:
            why.append(f"only {r['days_matched']} of {r['days_in_window']} days matched, below the "
                       f"{r['days_needed']} needed")
        if not r["snpp_floor_met"]:
            why.append(f"S-NPP has {r['snpp']} day-pass detections on the matched days, below {S_FLOOR}")
        if base_mean is None:
            why.append(f"no {what} of 2018–21 counts and passes the S-NPP floor, so the expected Terra count "
                       "is undefined")
        elif not r["terra_floor_met"]:  # two decimals: 19.96 must never read "20.0, below 20"
            why.append(f"the expected Terra count is {r['expected_terra']:.2f}, below {T_FLOOR}")
        r["exclusion"] = ", ".join(why) or None
    return rows, base_mean


def g01_fall(rows: dict, base_mean: float | None) -> dict:
    """Test 1, October-November: delta and the exact whole-year permutation p (items 3.1, 3.2, 3.5)."""
    before = [y for y in G01_BEFORE if rows[y]["eligible"]]
    after = [y for y in G01_AFTER if rows[y]["eligible"]]
    out = {"status": "not_testable", "delta": None, "p": None, "years_before": before, "years_after": after,
           "reason": None, "baseline_mean_R": base_mean, "mean_R_before": None, "mean_R_after": None,
           "splits": None, "difference_of_means": None,
           "rule": "present if delta <= -0.40 and one-sided p <= 0.10 (both inclusive)"}
    why = []
    if base_mean is None:
        why.append("no 2018–21 year has 90% of its days matched and at least 300 S-NPP day-pass detections")
    elif base_mean == 0:
        why.append("the mean R of 2018–21 is 0, so no year can pass the expected-Terra floor")
    else:
        if len(before) < MIN_BEFORE:
            why.append(f"only {_n(len(before), 'eligible year')} in 2018–21, below {MIN_BEFORE}")
        if len(after) < MIN_AFTER:
            why.append(f"only {_n(len(after), 'eligible year')} in 2023–25, below {MIN_AFTER}")
    if not why:
        mb = float(np.mean([rows[y]["R"] for y in before]))
        ma = float(np.mean([rows[y]["R"] for y in after]))
        out.update(mean_R_before=mb, mean_R_after=ma)
        if mb == 0:
            why.append("the mean R of the eligible 2018–21 years is 0")
    if why:
        out["reason"] = ", ".join(why)
        return out
    delta = ma / mb - 1
    perm = p02_posthoc.permutation(pd.Series({y: rows[y]["R"] for y in before + after}),
                                   before=tuple(before), after=tuple(after))
    p = perm["p_as_low"]
    status = ("present" if delta <= FALL_DELTA and p <= FALL_P else
              "large_not_significant" if delta <= FALL_DELTA else "not_seen")
    out.update(status=status, delta=delta, p=p, splits=perm["splits"], difference_of_means=perm["difference_of_means"])
    return out


def g01_step(rows: dict, base_mean: float | None) -> dict:
    """Test 2, November only: R(Nov 2022) below every eligible 2018-21 November and at most 0.6 x their mean."""
    base = [y for y in G01_BEFORE if rows[y]["eligible"]]
    r22 = rows[STEP_YEAR]
    out = {"status": "not_testable", "ratio_to_mean": None, "reason": None, "R_2022": r22["R"],
           "mean_R_2018_21": None, "below_every": None, "years_in_baseline": base, "baseline_mean_R": base_mean,
           "rule": "present if R(Nov 2022) is below every eligible R(Nov 2018–21) and at most 0.6 x their mean"}
    why = []
    if base_mean is None:
        why.append("no November of 2018–21 has 27 of 30 days matched and at least 300 S-NPP day-pass detections")
    elif base_mean == 0:
        why.append("the mean November R of 2018–21 is 0, so no November can pass the expected-Terra floor")
    else:
        if not r22["eligible"]:
            why.append(f"November 2022 is not eligible ({r22['exclusion']})")
        if len(base) < MIN_STEP_BASE:
            why.append(f"only {_n(len(base), 'eligible November')} in 2018–21, below {MIN_STEP_BASE}")
    if not why:
        m = float(np.mean([rows[y]["R"] for y in base]))
        out["mean_R_2018_21"] = m
        if m == 0:
            why.append("the mean R of the eligible 2018–21 Novembers is 0")
    if why:
        out["reason"] = ", ".join(why)
        return out
    r = r22["R"]
    below = all(r < rows[y]["R"] for y in base)
    out.update(status="present" if below and r <= STEP_FACTOR * m else "absent", ratio_to_mean=r / m,
               below_every=below)
    return out


def g01_reading(name: str, fall: dict, step: dict) -> str:
    """Item 3.6: '<province>: <fall clause>; <step clause>.' (plus one sentence only when both are present)."""
    f = (f"the fall is not testable ({fall['reason']})" if fall["status"] == "not_testable"
         else FALL_CLAUSE[fall["status"]])
    s = (f"the 2022 step is not testable ({step['reason']})" if step["status"] == "not_testable"
         else STEP_CLAUSE[step["status"]])
    text = f"{name}: {f}; {s}."
    if fall["status"] == "present" and step["status"] == "present":
        text += " " + BOTH_PRESENT
    return text


def _g01_use(window: str, y: int) -> str | None:
    if window == "OctNov":
        return ("fall test, 2018–21 group" if y in G01_BEFORE else
                "fall test, 2023–25 group" if y in G01_AFTER else None)
    return ("step test, 2018–21 Novembers" if y in G01_BEFORE else
            "step test, November 2022" if y == STEP_YEAR else None)


def g01_province(counts: dict, prov: str, spans: dict, miss: dict, *, name: str | None = None) -> dict:
    octnov, base_on = g01_window(counts, prov, "OctNov", spans, miss)
    nov, base_n = g01_window(counts, prov, "Nov", spans, miss)
    fall, step = g01_fall(octnov, base_on), g01_step(nov, base_n)
    years = {str(y): {"OctNov": {**octnov[y], "used_in": _g01_use("OctNov", y)},
                      "Nov": {**nov[y], "used_in": _g01_use("Nov", y)}} for y in G01_YEARS}
    return {"fall": fall, "step": step, "reading": g01_reading(name or prov, fall, step), "years": years}


def build_g01(counts: dict, spans: dict, miss: dict) -> dict:
    provs = {p: g01_province(counts, p, spans, miss) for p in TESTED}
    seen = [p for p in TESTED if provs[p]["fall"]["status"] == "present"]
    step_only = [p for p in TESTED if provs[p]["step"]["status"] == "present" and p not in seen]
    if seen:
        text = f"Seen outside Punjab: yes, Terra's fall is also seen in {' and '.join(seen)}."
    else:
        text = "Seen outside Punjab: no (" + "; ".join(
            f"{p}: {FALL_SHORT[provs[p]['fall']['status']]}" for p in TESTED) + ")."
    if step_only:
        text += (f" {' and '.join(step_only)} {'shows' if len(step_only) == 1 else 'show'} a 2022 step without "
                 "Terra's fall; that is reported as a step, not as 'seen'.")
    dev = g01_province(counts, DEV_AREA, spans, miss, name="Punjab (development area, seen before the test)")
    dev["label"] = "development area (seen before the test); not part of the test"
    return {"provinces": provs, "seen_outside_punjab": bool(seen), "seen_in": seen,
            "step_without_fall_in": step_only, "seen_outside_punjab_reading": text,
            "development_area": {DEV_AREA: dev}, "strip_title": STRIP_TITLE}


# ---------- G02 ----------

def g02_label(pair: str, status: str, outside: int, n: int, years: list[int]) -> str:
    """Item 4.5 labels."""
    if pair == "Aqua-SNPP":
        return {"holds": SAME_LABEL,
                "fails": f"each satellite's dates side by side; {outside} of {n} eligible years outside the tolerance",
                "not_testable": "not tested: too few years with enough detections"}[status]
    return {"holds": "matched S-NPP's dates within the tolerance in " + ", ".join(str(y) for y in years),
            "fails": f"did not match S-NPP's dates within the tolerance ({outside} of {n} eligible years outside)",
            "not_testable": "not tested"}[status]


def g02_pair(counts: dict, prov: str, window: str, pair: str, spans: dict, miss: dict) -> dict:
    """One province, window and pair: dates per year on the pair's matched days, then 'holds' (items 4.1-4.3)."""
    src, ref, years = PAIRS[pair]
    a, b = G02_WINDOWS[window]
    per, elig = {}, []
    for y in years:
        days = window_days(y, a, b)
        use = matched_days(days, (src, ref), spans, miss)
        kept = set(use)
        cs = [counts.get((prov, src, t), 0) for t in use]
        cr = [counts.get((prov, ref, t), 0) for t in use]
        rec = {"days_in_window": len(days), "days_matched": len(use),
               "days_removed": [_iso(x) for x in days if x not in kept],
               "n_src": int(sum(cs)), "n_ref": int(sum(cr)),
               "src_mid": None, "src_end": None, "ref_mid": None, "ref_end": None,
               "d_mid": None, "d_end": None, "d_mid_calendar": None, "d_end_calendar": None}
        if rec["n_src"] > 0 and rec["n_ref"] > 0:
            (ms, es), (mr, er) = season_dates(cs), season_dates(cr)
            rec.update(src_mid=_iso(use[ms]), src_end=_iso(use[es]), ref_mid=_iso(use[mr]), ref_end=_iso(use[er]),
                       # The test's gap: positions in the matched-day sequence (removed days never count).
                       d_mid=ms - mr, d_end=es - er,
                       # Shown beside it only: the same gap in calendar days.
                       d_mid_calendar=(use[ms] - use[mr]).days, d_end_calendar=(use[es] - use[er]).days)
        why = []
        if len(use) < G02_MIN_DAYS:
            why.append(f"only {len(use)} of {len(days)} days matched, below {G02_MIN_DAYS}")
        for sat, n in ((src, rec["n_src"]), (ref, rec["n_ref"])):
            if n < G02_FLOOR:
                why.append(f"{NAMES[sat]} has {n} day-pass detections on the matched days, below {G02_FLOOR}")
        rec["eligible"] = not why
        rec["exclusion"] = ", ".join(why) or None
        rec["middle_within"] = rec["end_within"] = None
        if rec["eligible"]:
            rec["middle_within"] = abs(rec["d_mid"]) <= MID_TOL
            rec["end_within"] = abs(rec["d_end"]) <= END_TOL
            elig.append(y)
        per[str(y)] = rec
    n = len(elig)
    allowed = misses_allowed(n)
    rows = [per[str(y)] for y in elig]
    mid_miss = sum(not r["middle_within"] for r in rows)
    end_miss = sum(not r["end_within"] for r in rows)
    outside = sum(not (r["middle_within"] and r["end_within"]) for r in rows)
    if n < G02_MIN_YEARS:
        status, mid_holds, end_holds = "not_testable", None, None
        reason = f"only {_n(n, 'eligible year')}, below {G02_MIN_YEARS}"
    else:
        mid_holds, end_holds = mid_miss <= allowed, end_miss <= allowed
        status, reason = ("holds" if mid_holds and end_holds else "fails"), None
    return {"status": status, "label": g02_label(pair, status, outside, n, elig), "reason": reason,
            "satellites": [src, ref], "eligible_years": elig,
            "excluded_years": {y: r["exclusion"] for y, r in per.items() if not r["eligible"]},
            "middle_misses": mid_miss, "end_misses": end_miss, "misses_allowed": allowed,
            "years_outside_tolerance": outside, "middle_holds": mid_holds, "end_holds": end_holds,
            "max_abs_d_mid": max((abs(r["d_mid"]) for r in rows), default=None),
            "max_abs_d_end": max((abs(r["d_end"]) for r in rows), default=None),
            "years": per}


def _aqua_reading(prov: str, window: str, r: dict) -> str:
    head = f"{prov}, {WINDOW_TEXT[window]}, Aqua and S-NPP"
    n = len(r["eligible_years"])
    if r["status"] == "holds":
        return (f"{head}: both dates hold in {n} eligible years ({r['misses_allowed']} misses allowed); the band is "
                f"labelled '{SAME_LABEL}'.")
    if r["status"] == "fails":
        which = ("both dates fail" if not r["middle_holds"] and not r["end_holds"] else
                 "the middle date fails" if not r["middle_holds"] else "the end date fails")
        return (f"{head}: {which}; each satellite's band is shown side by side, with no 'same on both' label "
                f"({r['years_outside_tolerance']} of {n} eligible years outside the tolerance).")
    return (f"{head}: not tested ({_n(n, 'eligible year')}, below {G02_MIN_YEARS}); each satellite's band is shown for "
            "its eligible years, labelled 'not tested: too few years with enough detections'.")


def _rice_other(prov: str, r: dict) -> str:
    """A tested province where the rice pair does not hold, with its own status: 'fails' and 'not tested' differ."""
    if r["status"] == "fails":
        return f"in {prov} the pair fails, so each satellite's band is shown side by side"
    return (f"{prov} was not tested ({r['reason']}), so each satellite's band is shown for its eligible years, "
            "labelled 'not tested: too few years with enough detections'")


def g02_readings(results: dict) -> list[str]:
    """Item 4.5's readings, in plain sentences."""
    rice = {p: results[p]["rice"]["Aqua-SNPP"] for p in TESTED}
    holds = [p for p in TESTED if rice[p]["status"] == "holds"]
    others = "; ".join(_rice_other(p, rice[p]) for p in TESTED if p not in holds)
    if len(holds) == len(TESTED):
        out = [f"Rice season, Aqua and S-NPP: both dates hold in Sindh and in Khyber Pakhtunkhwa, so each "
               f"province's band is labelled '{SAME_LABEL}'."]
    elif holds:
        out = [f"Rice season, Aqua and S-NPP: the pair holds in {holds[0]} only, so the label is limited to "
               f"{holds[0]}; {others}."]
    else:
        out = ["Rice season, Aqua and S-NPP: the pair holds in neither tested province, so no band carries the "
               f"'same on both' label: {others}."]
    for window in G02_WINDOWS:
        for p in G02_PROVINCES[window]:
            out.append(_aqua_reading(p, window, results[p][window]["Aqua-SNPP"]))
    for window in G02_WINDOWS:
        for p in G02_PROVINCES[window]:
            out.append(f"{p}, {WINDOW_TEXT[window]}: NOAA-20's dates are labelled "
                       f"'{results[p][window]['NOAA20-SNPP']['label']}'.")
    out += [f"Punjab, rice season, both pairs: each satellite's band is shown side by side, labelled '{DEV_LABEL}'. "
            "Punjab's rice dates are not tested.",
            "Spring is read the same way, province by province (Punjab included), and independently of rice: only "
            "a pair that holds gets the label.",
            "After S-NPP's end, NOAA-20's own dates are shown only for complete windows, each labelled with its "
            "pair's outcome and its stream; the first is rice 2026, complete on 31 Dec 2026.",
            "Historical dates only, never a forecast."]
    return out


def build_g02(counts: dict, spans: dict, miss: dict) -> dict:
    results: dict = {}
    for p in ("Punjab",) + TESTED:
        for window, provs in G02_PROVINCES.items():
            if p in provs:
                results.setdefault(p, {})[window] = {pair: g02_pair(counts, p, window, pair, spans, miss)
                                                     for pair in PAIRS}
    dev = {}
    for pair in PAIRS:
        r = g02_pair(counts, DEV_AREA, "rice", pair, spans, miss)
        dev[pair] = {"status": "not_tested", "label": DEV_LABEL, "eligible_years": r["eligible_years"],
                     "excluded_years": r["excluded_years"], "years": r["years"]}
    return {"results": results, "development_area": {DEV_AREA: {"rice": dev}}, "readings": g02_readings(results),
            "band_title": BAND_TITLE}


# ---------- G03 and G04: the 2026 files ----------

def latest_dated(prefix: str, folder=None) -> Path | None:
    """Newest research/metadata/<prefix>_<YYYY-MM-DD>.json (the dated copies saved at download time)."""
    folder = Path(folder or (config.ROOT / "research" / "metadata"))
    pat = re.compile(rf"^{re.escape(prefix)}_(\d{{4}}-\d{{2}}-\d{{2}})\.json$")
    found = sorted((m.group(1), p) for p in folder.glob(f"{prefix}_*.json") if (m := pat.match(p.name)))
    return found[-1][1] if found else None


def availability_ranges(obj) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    """data_id -> (min_date, max_date) from FIRMS's availability answer, saved as rows, a dict or CSV text."""
    found: dict = {}

    def norm(x) -> dict:
        return {str(k).strip().lower(): v for k, v in x.items()}

    def visit(x, key=None):
        if isinstance(x, dict):
            low = norm(x)
            if {"min_date", "max_date"} <= set(low) and ("data_id" in low or key is not None):
                ident = str(low.get("data_id", key)).strip()
                found[ident] = (pd.Timestamp(str(low["min_date"]).strip()[:10]),
                                pd.Timestamp(str(low["max_date"]).strip()[:10]))
                return
            for k, v in x.items():
                visit(v, k)
        elif isinstance(x, list):
            # The downloader's saved shape (c08/acquire.py, 8 Nov): {"ranges": {data_id: [min_date, max_date]}}
            if (key is not None and len(x) == 2 and all(isinstance(v, str) and len(v.strip()) >= 10 for v in x)
                    and all(v.strip()[:4].isdigit() and v.strip()[4] == "-" for v in x)):
                found[str(key).strip()] = (pd.Timestamp(x[0].strip()[:10]), pd.Timestamp(x[1].strip()[:10]))
                return
            for v in x:
                visit(v)
        elif isinstance(x, str) and "data_id" in x and "min_date" in x:
            for row in csv.DictReader(io.StringIO(x.strip())):
                visit(row)

    visit(obj)
    return found


def load_availability(path) -> tuple[dict, dict]:
    path = Path(path)
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig")
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        obj = text  # the CSV answer saved as it came
    ranges = availability_ranges(obj)
    return ranges, {"path": _rel(path), "sha256": _sha(raw),
                    "ranges": {k: [_iso(a), _iso(b)] for k, (a, b) in sorted(ranges.items())}}


def availability_problems(ranges: dict) -> list[str]:
    """Item 6.2 needs both standard-stream ranges. Without one, month_streams() would make every month NRT without a
    word, so a run refuses and the preflight reports it."""
    return [f"FIRMS's availability answer has no {src} range, so no month's stream can be chosen (every month "
            "would silently become NRT)" for src in SP_SOURCES if src not in ranges]


def month_streams(ranges: dict, months=G03_MONTHS) -> dict[str, str]:
    """Entry 1, item 6.2: SP only if FIRMS's availability covers the whole month for both S-NPP and NOAA-20."""
    out = {}
    for mo in months:
        days = month_days(mo)
        sp = all(src in ranges and ranges[src][0] <= days[0] and ranges[src][1] >= days[-1]
                 for src in ("VIIRS_SNPP_SP", "VIIRS_NOAA20_SP"))
        out[mo] = "SP" if sp else "NRT"
    return out


def api_entries(manifest=None) -> list[dict]:
    path = Path(manifest or config.MANIFEST)
    if not path.is_file():
        return []
    m = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for fid, e in sorted(m.get("files", {}).items()):
        if e.get("kind") != "firms_api_csv":
            continue
        if e.get("source") not in API_SOURCES:
            raise SystemExit(f"Refusing to run: {fid} has an unknown FIRMS source {e.get('source')!r}")
        try:
            pd.Timestamp(e["start"]), int(e["days"])
        except (KeyError, TypeError, ValueError):
            raise SystemExit(f"Refusing to run: {fid} needs a start date and a day count in the manifest")
        if not e.get("path") or not e.get("sha256"):
            raise SystemExit(f"Refusing to run: {fid} needs a path and a SHA-256 in the manifest")
        out.append({**e, "id": e.get("id", fid)})
    return out


def _covered(entries: list[dict], source: str) -> set:
    days = set()
    for e in entries:
        if e["source"] == source:
            days.update(pd.date_range(pd.Timestamp(e["start"]), periods=int(e["days"]), freq="D"))
    return days


def needed_days(streams: dict) -> dict[str, set]:
    """Every day each FIRMS source must cover: G03's months in their stream, and NOAA-21 NRT for G04."""
    need: dict[str, set] = {}
    for mo, st in streams.items():
        for sat in ("SNPP", "NOAA20"):
            need.setdefault(f"VIIRS_{sat}_{st}", set()).update(month_days(mo))
    need.setdefault("VIIRS_NOAA21_NRT", set()).update(pd.date_range(*G04_DAYS, freq="D"))
    return need


def coverage_gaps(entries: list[dict], streams: dict) -> list[str]:
    """Days a needed source was never downloaded for (dates only). Running then would treat no data as zero."""
    gaps = []
    for src, days in sorted(needed_days(streams).items()):
        miss = sorted(days - _covered(entries, src))
        if miss:
            gaps.append(f"{src}: {len(miss)} day(s) not downloaded ({_ranges(miss)})")
    return gaps


def coverage_overlaps(entries: list[dict]) -> list[str]:
    """Days one source has in more than one file (a re-download, say): rows that differ between the copies would be
    counted twice, so a run refuses until one copy per day is left."""
    out = []
    for src in sorted({e["source"] for e in entries}):
        seen, twice = set(), set()
        for e in entries:
            if e["source"] == src:
                days = set(pd.date_range(pd.Timestamp(e["start"]), periods=int(e["days"]), freq="D"))
                twice |= seen & days
                seen |= days
        if twice:
            out.append(f"{src}: {len(twice)} day(s) in more than one file ({_ranges(twice)})")
    return out


def _format_problems(raw: pd.DataFrame) -> list[str]:
    """Values this code cannot read (codes and spellings only, no counts)."""
    out = []
    if "satellite" in raw:
        bad = sorted(set(raw["satellite"].astype(str)) - set(ingest.PLATFORM_CODES))
        if bad:
            out.append(f"unknown satellite codes {bad}")
    if "confidence" in raw:
        bad = sorted(set(raw["confidence"].astype(str).str.strip().str.lower()) - set(ingest.VIIRS_CONFIDENCE))
        if bad:
            out.append(f"unknown VIIRS confidence values {bad[:10]}")
    if "daynight" in raw:
        bad = sorted(set(raw["daynight"].astype(str)) - {"D", "N"})
        if bad:
            out.append(f"unknown day/night flags {bad}")
    return out


def _read_csv(raw_bytes: bytes) -> pd.DataFrame:
    try:
        return pd.read_csv(io.BytesIO(raw_bytes), dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except pd.errors.EmptyDataError:  # an empty chunk: no rows, never zero burning (the pass check removes its days)
        return pd.DataFrame(columns=list(ingest.REQUIRED) + ["bright_ti4", "bright_ti5"], dtype=str)


def load_api_rows(entries: list[dict], *, root=None, assign=None) -> tuple[pd.DataFrame, list[dict]]:
    """Hash-check, then parse each 2026 file with c08.ingest's own contract, quality rule and type flag; keep rows
    inside a Pakistan province (geoBoundaries polygons, as the archive). Rows outside Pakistan are dropped uncounted."""
    root = Path(root or config.ROOT)
    if assign is None:
        from . import boundaries
        assign = boundaries.province_of
    frames: dict[str, list[pd.DataFrame]] = {}
    audits = []
    for e in entries:
        path = root / e["path"]
        if not path.is_file():
            raise SystemExit(f"Refusing to run: {e['id']} is in the manifest but its file is missing ({e['path']})")
        raw_bytes = path.read_bytes()
        sha = _sha(raw_bytes)
        if sha != e.get("sha256"):
            raise SystemExit(f"Refusing to run: {e['id']}'s SHA-256 differs from the manifest (the raw file changed)")
        plat, stream, key = API_SOURCES[e["source"]]
        raw = _read_csv(raw_bytes)
        try:
            frame, audit = ingest.parse_frame(raw, source=key, source_id=e["id"],
                                              stream="standard" if stream == "SP" else "nrt", file_year=None)
        except ingest.IngestError as err:
            raise SystemExit(f"Refusing to run: {err}")
        bad = [k for k in FORMAT_REASONS if audit["rejected"].get(k)]
        if bad:
            raise SystemExit(f"Refusing to run: {e['id']} has rows this code cannot read ({', '.join(bad)}"
                             + (f"; {'; '.join(_format_problems(raw))}" if _format_problems(raw) else "")
                             + "). Fix the parsing before the run-once tests.")
        start = pd.Timestamp(e["start"])
        end = start + pd.Timedelta(days=int(e["days"]) - 1)
        frame = frame.assign(date_utc=frame["time_utc"].dt.tz_localize(None).dt.floor("D"),
                             api_source=e["source"], api_stream=stream, has_type="type" in raw.columns)
        audits.append({"id": e["id"], "path": e["path"], "source": e["source"], "start": e["start"],
                       "days": int(e["days"]), "bbox": e.get("bbox"), "sha256": sha,
                       "sha256_matches_manifest": True, "retrieved_utc": e.get("retrieved_utc"),
                       "url_redacted": _redact(e.get("url_redacted")), "fields": list(raw.columns),
                       "has_type_field": "type" in raw.columns, "contract": audit,
                       "rows_dated_outside_chunk": int((~frame["date_utc"].between(start, end)).sum()),
                       "source_duplicates_removed": 0})
        if len(frame):
            frames.setdefault(e["source"], []).append(frame)
    cols = ["platform", "api_source", "api_stream", "time_utc", "date_utc", "daynight", "quality_pass", "type0",
            "has_type", "latitude", "longitude", "version"]
    parts = []
    for src, fs in sorted(frames.items()):
        f = pd.concat(fs, ignore_index=True)
        dup = f.duplicated(["platform", "time_utc", "latitude", "longitude", "version"])
        for a in audits:  # rows delivered twice by overlapping chunks are one observation
            if a["source"] == src:
                a["source_duplicates_removed"] = int(dup.sum())
        parts.append(f.loc[~dup, cols])
    if not parts:
        return pd.DataFrame({c: pd.Series(dtype=object) for c in cols + ["province", "stream"]}), audits
    api = pd.concat(parts, ignore_index=True)
    api["platform"] = api["platform"].astype(str)
    api["daynight"] = api["daynight"].astype(str)
    api["quality_pass"] = api["quality_pass"].astype(bool)
    api["type0"] = api["type0"].astype(bool)
    api["province"] = np.asarray(assign(api["longitude"].to_numpy(float), api["latitude"].to_numpy(float)), dtype=object)
    api["province"] = api["province"].astype(str)
    api["stream"] = api["api_stream"]
    api = api[api["province"].ne("")].reset_index(drop=True)
    return api, audits


def two_pass_days(rows: pd.DataFrame) -> set:
    """UTC days with at least one day-pass row and at least one night-pass row."""
    return set(rows.loc[rows["daynight"] == "D", "date_utc"]) & set(rows.loc[rows["daynight"] == "N", "date_utc"])


def listed_2026(lists: dict, plats) -> dict[str, set]:
    """Entry 1, item 6.3: a day listed on either refreshed list, standard or NRT, is missing."""
    return {p: set(lists.get("standard", {}).get(p, set())) | set(lists.get("nrt", {}).get(p, set())) for p in plats}


def month_plan(api: pd.DataFrame, streams: dict, listed: dict) -> list[dict]:
    """Per 2026 month: its stream, matched days (both lists and the both-pass presence check), and whether it is
    scored (at least 20 matched days). The presence check uses every row, before the quality rule."""
    plan = []
    for mo in G03_MONTHS:
        st, days = streams[mo], month_days(mo)
        rows = api[api["stream"].eq(st) & api["platform"].isin(["SNPP", "NOAA20"])
                   & api["date_utc"].between(days[0], days[-1])]
        present = {p: two_pass_days(rows[rows["platform"].eq(p)]) for p in ("SNPP", "NOAA20")}
        matched, removed = [], {}
        for t in days:
            why = []
            for p in ("SNPP", "NOAA20"):
                if t in listed.get(p, set()):
                    why.append(f"{NAMES[p]} is on a FIRMS missing-days list")
                if t not in present[p]:
                    why.append(f"{NAMES[p]} has no row in Pakistan on its day pass or its night pass")
            if why:
                removed[_iso(t)] = ", ".join(why)
            else:
                matched.append(t)
        screen = bool(len(rows)) and bool(rows["has_type"].all())
        plan.append({"month": mo, "stream": st, "days_in_month": len(days), "matched_days": len(matched),
                     "scored": len(matched) >= G03_MIN_DAYS, "type0_screen": screen, "removed_days": removed,
                     "matched": matched})
    return plan


def _area(prov: pd.Series, area: str) -> pd.Series:
    prov = prov.astype(str)
    return prov.ne("") if area == "Pakistan" else prov.eq(area)


def _archive_rows(d: pd.DataFrame, area: str, *, type0: bool = True) -> pd.DataFrame:
    """Standard-stream archive rows, quality rule, optional type-0 screen, in one province or all of Pakistan's
    provinces (the same polygons the 2026 rows are assigned with)."""
    q = series.select(d, quality=True, type0=type0)
    return q[_area(q["province"], area)]


def bridge_fits(d: pd.DataFrame, area: str, spans: dict, years=None) -> dict:
    """M1 (and M0) for NOAA-20 -> S-NPP on the area's complete months: 2018-04..2025-12 (p01.DEPLOY_BRIDGE), or
    the given years (E02's 2019-2023 fit). Once with the type-0 screen, once without it for months with no type
    field (entry 1, items 6.6-6.7). Nothing is fitted on 2026."""
    out = {}
    for key, screen in (("type0", True), ("none", False)):
        w = series.wide(series.monthly(_archive_rows(d, area, type0=screen), spans))
        win = p01._window(w, *p01.DEPLOY_BRIDGE) if years is None else w[w.index.year.isin(list(years))]
        ok = p01.scored_months(win, ("NOAA20", "SNPP"))
        train = win[ok]
        out[key] = {"M1": hz.fit(train, "M1", src="NOAA20"), "M0": hz.fit(train, "M0", src="NOAA20"),
                    "training_months": [m.strftime("%Y-%m") for m in train.index],
                    "type0_screen": screen}
    return out


def _fit_record(fits: dict) -> dict:
    return {k: {"model": "M1", "src": "NOAA20", "ref": "SNPP", "k_day": v["M1"]["D"]["k"], "k_night": v["M1"]["N"]["k"],
                "type0_screen": v["type0_screen"], "n_months": len(v["training_months"]),
                "training_months": v["training_months"]} for k, v in fits.items()}


def month_counts(api: pd.DataFrame, area: str, m: dict) -> dict:
    """Quality-filtered day and night detections on the month's matched days (type-0 screen where typed)."""
    sel = (api["stream"].eq(m["stream"]) & api["platform"].isin(["SNPP", "NOAA20"]) & api["quality_pass"]
           & api["date_utc"].isin(m["matched"]) & _area(api["province"], area))
    if m["type0_screen"]:
        sel &= api["type0"]
    c = api[sel].groupby(["platform", "daynight"]).size()
    return {f"{p}_{dn}": int(c.get((p, dn), 0)) for p in ("SNPP", "NOAA20") for dn in ("D", "N")}


def score_area(api: pd.DataFrame, area: str, scored: list[dict], fits: dict) -> dict:
    """Predicted against observed S-NPP (day + night) for each scored month, then WAPE for M1 and M0."""
    months, obs, pred, pred0 = [], {}, {}, {}
    for m in scored:
        c = month_counts(api, area, m)
        fit = fits["type0" if m["type0_screen"] else "none"]
        idx = pd.Timestamp(m["month"] + "-01")
        frame = pd.DataFrame([c], index=pd.DatetimeIndex([idx]))
        p1 = float(hz.predict(frame, fit["M1"])["pred"].iloc[0])
        p0 = float(hz.predict(frame, fit["M0"])["pred"].iloc[0])
        o = c["SNPP_D"] + c["SNPP_N"]
        err = (p1 - o) / o if o else None
        held = o >= MONTH_FLOOR
        months.append({"month": m["month"], "stream": m["stream"], "matched_days": m["matched_days"],
                       "observed_snpp": o, "predicted": p1, "error": err, "held_to_month_rule": held,
                       "within_month_rule": (abs(err) <= MONTH_MARK) if held else None,
                       "m0_predicted": p0, "m0_error": (p0 - o) / o if o else None,
                       "snpp_day": c["SNPP_D"], "snpp_night": c["SNPP_N"],
                       "noaa20_day": c["NOAA20_D"], "noaa20_night": c["NOAA20_N"],
                       "type0_screen": m["type0_screen"],
                       "bridge_used": ("M1 fitted with the type-0 screen" if m["type0_screen"] else
                                       "M1 fitted without the type screen (this month's files have no type field)")})
        obs[idx], pred[idx], pred0[idx] = o, p1, p0
    wape = m0 = None
    if months:
        o = pd.Series(obs).sort_index()
        wape = hz.metrics(o, pd.Series(pred).sort_index())["wape"]
        m0 = hz.metrics(o, pd.Series(pred0).sort_index())["wape"]
    return {"months": months, "wape": wape, "m0_wape": m0}


def g03_decide(n_scored: int, wape: float | None, months: list[dict]) -> tuple[str, str | None]:
    """Entry 1, items 6.5-6.6: pass or fail by the primary bridge alone; 'not testable' below 6 scored months."""
    if n_scored < G03_MIN_MONTHS:
        return "not_testable", f"only {_n(n_scored, 'scored month')}, below {G03_MIN_MONTHS}"
    if wape is None:
        return "not_testable", "S-NPP has no detections in the scored months"
    big = [r for r in months if r["held_to_month_rule"]]
    ok = wape <= WAPE_MARK and all(r["within_month_rule"] for r in big)
    return ("pass" if ok else "fail"), None


def build_g03(d: pd.DataFrame, api: pd.DataFrame, plan: list[dict], spans: dict) -> dict:
    scored = [m for m in plan if m["scored"]]
    fits = {"Punjab": bridge_fits(d, "Punjab", spans)}
    prim = score_area(api, "Punjab", scored, fits["Punjab"])
    status, reason = g03_decide(len(scored), prim["wape"], prim["months"])
    tested = status != "not_testable"
    reported = {}
    for a in REPORTED:  # each area on its own fit; Punjab's factor is never applied elsewhere
        try:
            fits[a] = bridge_fits(d, a, spans)
        except ValueError as err:  # recorded, so one reported area cannot stop the run-once test
            reported[a] = {"label": "reported, not tested", "wape": None, "m0_wape": None, "months": [],
                           "bridge": None, "note": f"no bridge could be fitted: {err}"}
            continue
        r = score_area(api, a, scored, fits[a])
        reported[a] = {"label": "reported, not tested", "wape": r["wape"] if tested else None,
                       "m0_wape": r["m0_wape"] if tested else None, "months": r["months"],
                       "bridge": _fit_record(fits[a])}
    e02 = bridge_fits(d, "Punjab", spans, years=p01.BRIDGE_SELECTION)
    sec = score_area(api, "Punjab", scored, e02)
    big = [r for r in prim["months"] if r["held_to_month_rule"]]
    return {
        "status": status, "reason": reason,
        "reading": G03_READING[status] + (" " + M0_NOTE if tested else ""),
        "wape": prim["wape"] if tested else None, "m0_wape": prim["m0_wape"] if tested else None,
        "worst_held_month_error": max((abs(r["error"]) for r in big), default=None) if tested else None,
        "scored_months": len(scored), "months": prim["months"],
        "months_not_scored": [{"month": m["month"], "stream": m["stream"], "matched_days": m["matched_days"],
                               "reason": f"fewer than {G03_MIN_DAYS} matched days"} for m in plan if not m["scored"]],
        "days_by_month": [{k: v for k, v in m.items() if k != "matched"} for m in plan],
        "stream_by_month": {m["month"]: m["stream"] for m in plan},
        "bridge": {"area": "Punjab", "primary": _fit_record(fits["Punjab"]),
                   "for_the_record_after_october_2026": "primary bridge fitted without the type screen (NRT files)"},
        "secondary_e02_fit": {"label": "reported: E02's tested fit on 2019–2023",
                              "wape": sec["wape"] if tested else None, "m0_wape": sec["m0_wape"] if tested else None,
                              "months": sec["months"], "bridge": _fit_record(e02)},
        "reported": reported,
        "seam_label": SEAM_LABEL,
        "other_areas_label": "bridge tested in Punjab only",
    }


def g04_reading(total: int, snpp: int) -> tuple[bool, bool, str]:
    """Entry 1, item 7.2: each count within +-20% of its press figure (unrounded), and the four readings."""
    sum_in = abs(total - PRESS_SUM) <= PRESS_TOL * PRESS_SUM
    snpp_in = abs(snpp - PRESS_SNPP) <= PRESS_TOL * PRESS_SNPP
    return sum_in, snpp_in, G04_READING[(sum_in, snpp_in)]


def build_g04(d: pd.DataFrame, api: pd.DataFrame, streams: dict, lists: dict, committed: dict) -> dict:
    """Entry 1, item 7: Punjab, every UTC day of 1-29 Oct 2026, all rows; readings; the demonstration numbers."""
    days = pd.date_range(*G04_DAYS, freq="D")
    st = streams[G04_MONTH]
    src = {"SNPP": st, "NOAA20": st, "NOAA21": "NRT"}
    win = api["date_utc"].between(days[0], days[-1])
    pun = api[win & api["province"].eq("Punjab")]
    all_rows, quality = {}, {}
    for p, s in src.items():
        sel = pun["platform"].eq(p) & pun["stream"].eq(s)
        all_rows[p], quality[p] = int(sel.sum()), int((sel & pun["quality_pass"]).sum())
    total = sum(all_rows.values())  # the press method: a naive sum of satellites
    sum_in, snpp_in, reading = g04_reading(total, all_rows["SNPP"])
    listed = listed_2026(lists, src)
    gaps = {}
    for p, s in src.items():  # reported beside the counts, never removed
        rows = api[win & api["platform"].eq(p) & api["stream"].eq(s)]
        seen, both = set(rows["date_utc"]), two_pass_days(rows)
        gaps[p] = {"stream": s, "listed_missing": [_iso(t) for t in days if t in listed[p]],
                   "no_row_in_pakistan": [_iso(t) for t in days if t not in seen],
                   "one_pass_only": [_iso(t) for t in days if t in seen and t not in both]}
    arch = _archive_rows(d, "Punjab", type0=False)  # the quality rule, no type screen (NRT has no type field)
    plat = arch["platform"].astype(str)

    def oct_count(p: str, y: int) -> int:
        return int((plat.eq(p) & arch["date_utc"].between(pd.Timestamp(f"{y}-10-01"),
                                                          pd.Timestamp(f"{y}-10-29"))).sum())

    by_year = {str(y): oct_count("SNPP", y) for y in range(2018, 2026)}
    y19 = {"SNPP": oct_count("SNPP", 2019), "NOAA20": oct_count("NOAA20", 2019)}
    arch_gaps = {str(y): [_iso(t) for t in pd.date_range(f"{y}-10-01", f"{y}-10-29")
                          if t in committed.get("standard", {}).get("SNPP", set())] for y in range(2018, 2026)}
    s19, s26 = sum(y19.values()), sum(quality.values())
    return {
        "sum": {"value": total, "within": sum_in, "target": PRESS_SUM, "tolerance": PRESS_TOL,
                "label": "S-NPP + NOAA-20 + NOAA-21, all rows: the press method (" + NAIVE_LABEL + ")"},
        "snpp": {"value": all_rows["SNPP"], "within": snpp_in, "target": PRESS_SNPP, "tolerance": PRESS_TOL},
        "reading": reading,
        "card_note": "The card shows our counts either way.",
        "test_counts_all_rows": all_rows,
        "per_satellite": {"2019": y19, "2026": quality},
        "per_satellite_filter": "quality rule, no type screen in either year (NRT files have no type field); "
                                "1–29 Oct, Punjab; shown side by side, never stacked",
        "snpp_range_2018_2025": {"min": min(by_year.values()), "max": max(by_year.values()), "by_year": by_year,
                                 "listed_missing_days": arch_gaps},
        "satellites_flying": {"2019": 2, "2026": 3},
        "changes": {"snpp_only": (quality["SNPP"] / y19["SNPP"] - 1) if y19["SNPP"] else None,
                    "naive_sum": (s26 / s19 - 1) if s19 else None, "naive_sum_label": NAIVE_LABEL,
                    "note": "2019 is the press's comparison year; the S-NPP 2018–25 range is shown beside it"},
        "streams": src, "days_utc": [G04_DAYS[0], G04_DAYS[1]], "days_counted": len(days),
        "gap_days": gaps,
        "wording": "Neutral wording, Pakistan only, no country comparison.",
    }


# ---------- records, refusal and the runs ----------

def _target(test: str, out_root=None) -> Path:
    return Path(out_root or config.EXPERIMENTS) / RESULTS[test] / "result.json"


def _refuse_existing(paths) -> None:
    have = [p for p in paths if Path(p).exists()]
    if have:
        raise SystemExit("Refusing to run: P04's tests run once, and these results already exist: "
                         + ", ".join(_rel(p) for p in have))


def _check_approved(text) -> str:
    if text is None or not str(text).strip():
        raise SystemExit("Refusing to run: P04's tests start only after the checker's CHECK REPORT P04-CL or "
                         "Hasnain's go-ahead. Pass that text with --approved \"<text>\"; it is recorded in the result.")
    return str(text).strip()


def _dump(obj: dict) -> str:
    return json.dumps(_jsonable(obj), indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def _write_once(path: Path, obj) -> None:
    """Create the result file; never replace one ('x' mode fails if it exists, even if made a moment ago)."""
    text = obj if isinstance(obj, str) else _dump(obj)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as f:
            f.write(text)
    except FileExistsError:
        raise SystemExit(f"Refusing to overwrite {_rel(path)}: P04's tests run once")


def _free_bytes(path: Path) -> int:
    """Free bytes on the disk that holds path, asked of its nearest existing folder (nothing is created to ask)."""
    p = Path(path).resolve()
    while not p.exists() and p.parent != p:
        p = p.parent
    return shutil.disk_usage(p).free


def _disk_room(paths, need: int = 0) -> None:
    """Refuse before writing anything if `need` more bytes would leave less than config.MIN_FREE_DISK_BYTES free."""
    free = min(_free_bytes(Path(p).parent) for p in paths)
    if free - need < config.MIN_FREE_DISK_BYTES:
        raise SystemExit(f"Refusing to write the results: the disk would keep less than the "
                         f"{acquire.disk_floor_text()} reserve (config.MIN_FREE_DISK_BYTES); nothing was written")


def _write_pair(targets: dict, results: dict) -> None:
    """Both results or neither: check the disk, serialise both, write both as result.json.tmp in exclusive-create
    mode, then rename both to result.json. A failure before the renames removes the tmp files this call made and
    leaves no result; a failed second rename also takes back the first, so a pair is never left half written."""
    paths = list(targets.values())
    _refuse_existing(paths)
    _disk_room(paths)  # first: below the reserve, nothing is attempted
    texts = {t: _dump(results[t]) for t in targets}  # an error here has written nothing
    _disk_room(paths, sum(len(s.encode("utf-8")) for s in texts.values()))  # and the two files fit above it
    tmps = {t: p.with_name(p.name + ".tmp") for t, p in targets.items()}
    made: list[Path] = []
    try:
        for t, p in targets.items():
            p.parent.mkdir(parents=True, exist_ok=True)
            try:
                f = tmps[t].open("x", encoding="utf-8", newline="\n")
            except FileExistsError:
                raise SystemExit(f"Refusing to write: {_rel(tmps[t])} is left from an earlier attempt; look at it, "
                                 "delete it, then run again") from None
            made.append(tmps[t])
            with f:
                f.write(texts[t])
                f.flush()
                os.fsync(f.fileno())
        _refuse_existing(paths)  # a result that appeared meanwhile is never replaced
    except BaseException:
        for tmp in made:
            tmp.unlink(missing_ok=True)
        raise
    renamed: list[Path] = []
    try:
        for t, p in targets.items():
            os.rename(tmps[t], p)  # on Windows a rename never replaces an existing file
            renamed.append(p)
    except BaseException as err:
        for p in renamed:  # only files this call created a moment ago
            p.unlink(missing_ok=True)
        for tmp in made:
            tmp.unlink(missing_ok=True)
        raise SystemExit(f"Refusing to keep half a pair: a rename failed ({type(err).__name__}); no result was "
                         "kept") from None


def _environment() -> dict:
    return {"python": sys.version.split()[0], "pandas": pd.__version__, "numpy": np.__version__,
            "os": _platform.platform()}


def _boundary_input(rep: dict, path=None) -> dict:
    """The polygons that assign 2026 rows to provinces must be the ones the archive was assigned with."""
    if path is None:
        from . import boundaries
        path = boundaries.FULL
    path = Path(path)
    if not path.is_file():
        raise SystemExit(f"Refusing to run: the province boundaries file is missing ({_rel(path)})")
    sha = _sha(path.read_bytes())
    want = {b.get("id"): b.get("sha256") for b in rep.get("boundaries", [])}.get("boundaries/pak_adm1.geojson")
    if want != sha:
        raise SystemExit("Refusing to run: the province boundaries differ from those the archive was built with "
                         "(SHA-256 mismatch with the ingest report)")
    return {"path": _rel(path), "sha256": sha, "matches_ingest_report": True}


def _inputs(rep: dict, det_path, report_path, det_sha: str, spans: dict) -> dict:
    return {"detections": {"path": _rel(det_path), "sha256": det_sha, "matches_ingest_report": True,
                           "ingest_report": _rel(report_path), "ingest_schema": rep.get("schema"),
                           "ingest_built_utc": rep.get("built_utc")},
            "boundaries_at_ingest": rep.get("boundaries", []),
            "archive_spans": {p: [_iso(a), _iso(b)] for p, (a, b) in sorted(spans.items())}}


def _committed_code(required: bool) -> dict:
    """ingest.code_state(), refusing unless c08/ is committed (c08_uncommitted_changes is False): a run-once result
    must name the code that made it. Only the unit tests pass required=False, on made-up data in a temporary
    folder."""
    state = ingest.code_state()
    if required and state.get("c08_uncommitted_changes") is not False:
        why = ("c08/ has uncommitted changes" if state.get("c08_uncommitted_changes")
               else "git could not tell whether c08/ has uncommitted changes")
        raise SystemExit(f"Refusing to run: {why}, so the result could not name the code that made it. Commit c08/ "
                         "first, then run again.")
    return state


def _provenance(approved: str, state: dict) -> dict:
    return {"approved": approved, **ingest.protocol_state(PROTOCOL), "code_state": state,
            "run_utc": _now(), "environment": _environment(), "runner": "python -m c08.p04"}


def run_g01g02(approved, *, out_root=None, detections=None, report=None, missing=None,
               require_committed: bool = True) -> dict:
    """G01 and G02 in one invocation, on the archive and the committed 27 Oct missing-days list."""
    approved = _check_approved(approved)
    targets = {t: _target(t, out_root) for t in ("G01", "G02")}
    _refuse_existing(targets.values())
    state = _committed_code(require_committed)
    det_path, rep_path = Path(detections or ingest.DETECTIONS), Path(report or ingest.INGEST_REPORT)
    d, rep, det_sha = load_archive(det_path, rep_path)
    miss_path = Path(missing or series.MISSING_DATES)
    lists, miss_meta = load_missing(miss_path)
    miss = lists.get("standard", {})
    spans = series.record_spans(d)
    counts = day_pass_counts(d, ("Punjab",) + TESTED)
    inputs = _inputs(rep, det_path, rep_path, det_sha, spans) | {"missing_days_list": miss_meta | {
        "stream_used": "standard"}}
    common = _provenance(approved, state)
    g01 = {"test": "G01", "title": "Terra's autumn fall outside Punjab (Sindh and Khyber Pakhtunkhwa)",
           **build_g01(counts, spans, miss), **common,
           "platforms": ["Terra", "SNPP"], "streams": ["standard"], "filters": ARCHIVE_FILTERS,
           "quantity": "R = Terra day-pass detections / S-NPP day-pass detections, summed over the window's matched "
                       "days (UTC days inside both archive records and on neither satellite's FIRMS missing-days list)",
           "windows": {"OctNov": "1 Oct–30 Nov (fall test)", "Nov": "1–30 Nov (step test)"},
           "rules": {"days": "a window-year counts only with at least 90% of its days matched (55 of 61, 27 of 30)",
                     "floors": f"S-NPP >= {S_FLOOR}; expected Terra = S-NPP x the mean R of the 2018–21 window-years "
                               f"that count and pass the S-NPP floor, >= {T_FLOOR} (November counts alone for the "
                               "step test)",
                     "fall": "delta = mean R(2023–25) / mean R(2018–21) - 1 over eligible years; exact one-sided "
                             "permutation p with whole years (c08.p02_posthoc.permutation, p_as_low); present if "
                             "delta <= -0.40 and p <= 0.10; not testable with fewer than 3 and 2 eligible years",
                     "step": "present if R(Nov 2022) is below every eligible R(Nov 2018–21) and at most 0.6 x their "
                             "mean; not testable unless November 2022 and at least 3 Novembers of 2018–21 pass",
                     "zero_mean": "a zero mean R of the 2018–21 years makes the test not testable",
                     "comparisons": "unrounded values"},
           "inputs": inputs}
    g02 = {"test": "G02", "title": "Season middle and end dates on the older and newer satellites",
           **build_g02(counts, spans, miss), **common,
           "platforms": ["Aqua", "NOAA20", "SNPP"], "streams": ["standard"], "filters": ARCHIVE_FILTERS,
           "pairs": {k: {"satellites": [v[0], v[1]], "years": [v[2][0], v[2][-1]]} for k, v in PAIRS.items()},
           "windows": {k: WINDOW_TEXT[k] for k in G02_WINDOWS},
           "rules": {"days": f"dates on the pair's matched days, in calendar order; a province-year needs at least "
                             f"{G02_MIN_DAYS} of the window's 108 matched days",
                     "floor": f"each satellite >= {G02_FLOOR} day-pass detections on the pair's matched days",
                     "dates": "middle = first matched day with 2 x cumulative >= total; end = first with 10 x "
                              "cumulative >= 9 x total (whole numbers)",
                     "gap": "counted in matched-day positions; removed days never count as disagreement",
                     "holds": f"|gap| <= {MID_TOL} (middle) and <= {END_TOL} (end) in all but floor(0.2 x n) "
                              f"eligible years; the pair holds only if both dates hold; not testable below "
                              f"{G02_MIN_YEARS} eligible years",
                     "punjab_rice": "development area: dates shown, not tested",
                     "comparisons": "unrounded values"},
           "inputs": inputs}
    _write_pair(targets, {"G01": g01, "G02": g02})
    return {"G01": _rel(targets["G01"]), "G02": _rel(targets["G02"]),
            "G01 reading": " ".join(g01["provinces"][p]["reading"] for p in TESTED),
            "G02 reading": g02["readings"][0]}


def run_g03g04(approved, *, out_root=None, detections=None, report=None, manifest=None, availability=None,
               missing=None, root=None, assign=None, boundary=None, require_committed: bool = True) -> dict:
    """G03 and G04 on the 2026 download (refreshed lists, FIRMS availability), with the archive for the bridge."""
    approved = _check_approved(approved)
    targets = {t: _target(t, out_root) for t in ("G03", "G04")}
    _refuse_existing(targets.values())
    state = _committed_code(require_committed)
    avail_path = Path(availability) if availability else latest_dated("firms_data_availability")
    miss_path = Path(missing) if missing else latest_dated("provider_missing_dates")
    if avail_path is None or not avail_path.is_file():
        raise SystemExit("Refusing to run: FIRMS's data-availability answer is missing "
                         "(research/metadata/firms_data_availability_<YYYY-MM-DD>.json)")
    if miss_path is None or not miss_path.is_file():
        raise SystemExit("Refusing to run: the refreshed missing-days list is missing "
                         "(research/metadata/provider_missing_dates_<YYYY-MM-DD>.json)")
    ranges, avail_meta = load_availability(avail_path)
    if not ranges:
        raise SystemExit("Refusing to run: no data_id / min_date / max_date rows in the availability answer")
    bad = availability_problems(ranges)
    if bad:
        raise SystemExit("Refusing to run: " + "; ".join(bad))
    lists, miss_meta = load_missing(miss_path)
    bad = missing_label_problems(miss_meta)
    if bad:
        raise SystemExit("Refusing to run: " + "; ".join(bad) + ". Those days would be left out without a word; fix "
                         "the reading (c08/p04.py load_missing, c08/series.py PROVIDER_NAMES) before the run-once "
                         "tests.")
    streams = month_streams(ranges)
    entries = api_entries(manifest)
    gaps = coverage_gaps(entries, streams) + coverage_overlaps(entries)
    if gaps:
        raise SystemExit("Refusing to run: the 2026 download must cover every day the tests need exactly once "
                         "(no data is never zero, and no day is counted twice):\n  " + "\n  ".join(gaps))
    det_path, rep_path = Path(detections or ingest.DETECTIONS), Path(report or ingest.INGEST_REPORT)
    d, rep, det_sha = load_archive(det_path, rep_path)
    bnd = _boundary_input(rep, boundary)
    # The committed 27 Oct list: series.monthly() reads this same file for the bridge's complete training months.
    committed, committed_meta = load_missing(series.MISSING_DATES)
    api, audits = load_api_rows(entries, root=root, assign=assign)
    plan = month_plan(api, streams, listed_2026(lists, ("SNPP", "NOAA20")))
    spans = series.record_spans(d)
    retrieved = sorted(a["retrieved_utc"] for a in audits if a.get("retrieved_utc"))
    inputs = _inputs(rep, det_path, rep_path, det_sha, spans) | {
        "availability": avail_meta, "missing_days_list_2026": miss_meta | {"streams_used": "standard and NRT"},
        "missing_days_list_archive": committed_meta | {"used_for": "the bridge's complete training months (P01 "
                                                                    "rule) and G04's archive gap days"},
        "boundaries_2026": bnd, "raw_2026_files": audits,
        "download_utc": {"first": retrieved[0] if retrieved else None, "last": retrieved[-1] if retrieved else None}}
    common = _provenance(approved, state)
    g03 = {"test": "G03", "title": "The record past 2 Nov 2026: the NOAA-20 bridge on Jan–Oct 2026",
           **build_g03(d, api, plan, spans), **common,
           "platforms": ["SNPP", "NOAA20"], "streams": "per month: SP if FIRMS's availability covers the whole month "
                                                       "for both satellites, otherwise NRT for both",
           "filters": f"quality rule ({QUALITY_RULE}); type-0 screen only in months whose files carry a type field; "
                      f"geoBoundaries province polygons; day and night passes. 2026 rows: {ROWS_2026_TEXT}. The "
                      f"bridge's training rows: {ROWS_ARCHIVE_TEXT}. {POLYGONS_TEXT}.",
           "rules": {"matched_days": "neither satellite on either refreshed list, and each satellite has at least one "
                                     "row anywhere in Pakistan on its day pass and on its night pass that UTC day "
                                     "(every row, before the quality rule). 'Anywhere in Pakistan' means rows of the "
                                     "month's chosen stream (SP or NRT) that passed c08.ingest.parse_frame's data "
                                     "contract and fall inside a province polygon (any of the seven), counted before "
                                     "the quality rule and before the type screen",
                     "scored_months": f"January–October 2026 months with at least {G03_MIN_DAYS} matched days; "
                                      f"not testable below {G03_MIN_MONTHS}",
                     "pass_mark": f"primary bridge only: WAPE <= {WAPE_MARK} and every scored month with at least "
                                  f"{MONTH_FLOOR} S-NPP detections within {MONTH_MARK:.0%} of observed",
                     "bridge": "M1 (hz.fit(..., 'M1', src='NOAA20')) on Punjab's complete months of 2018-04 to "
                               "2025-12 (p01.DEPLOY_BRIDGE), refitted without the type screen for months with no type "
                               "field; nothing refitted on 2026",
                     "regions": "Pakistan, Sindh and Khyber Pakhtunkhwa: each on its own fit, reported, not tested",
                     "comparisons": "unrounded values"},
           "inputs": inputs}
    g04 = {"test": "G04", "title": "Reproducing the 1–29 Oct 2026 headline for Pakistani Punjab",
           **build_g04(d, api, streams, lists, committed), **common,
           "platforms": ["SNPP", "NOAA20", "NOAA21"],
           "filters": "test counts: every row (no quality or type filter), Punjab polygon, every UTC day of 1–29 Oct "
                      f"2026, where 'all rows' means {ROWS_2026_TEXT}. Demonstration counts (2019 and 2018–25): "
                      f"quality rule, no type screen, from {ROWS_ARCHIVE_TEXT} (the same source as G03's bridge "
                      f"training rows). {POLYGONS_TEXT}.",
           "rules": {"within": f"|count - press figure| <= {PRESS_TOL:.0%} of the press figure (13,241 for the sum, "
                               "4,562 for S-NPP), unrounded",
                     "gap_days": "listed gap days and days with no row are reported beside the counts, not removed"},
           "inputs": inputs}
    _write_pair(targets, {"G03": g03, "G04": g04})
    return {"G03": _rel(targets["G03"]), "G04": _rel(targets["G04"]),
            "G03 reading": g03["reading"], "G04 reading": g04["reading"]}


def preflight(*, out_root=None, detections=None, report=None, manifest=None, availability=None, missing=None,
              root=None, require_committed: bool = True) -> dict:
    """What a run would use and whether it could start. Metadata only: no detection is counted, nothing is written.
    Every reason a G03/G04 run would refuse is listed under "problems"."""
    out: dict = {"note": "Metadata only: no detection is counted and nothing is written.",
                 "results_present": {t: _target(t, out_root).is_file() for t in RESULTS}}
    problems: list[str] = []
    state = ingest.code_state()
    code_ok = not require_committed or state.get("c08_uncommitted_changes") is False
    out["code"] = {"revision": state.get("revision"), "c08_uncommitted_changes": state.get("c08_uncommitted_changes"),
                   "runs_need_committed_c08": bool(require_committed)}
    if not code_ok:
        problems.append("c08/ has uncommitted changes (or git could not tell): the runs refuse until c08/ is committed")
    det, rp = Path(detections or ingest.DETECTIONS), Path(report or ingest.INGEST_REPORT)
    det_ok = False
    if det.is_file() and rp.is_file():
        rep = json.loads(rp.read_text(encoding="utf-8"))
        det_ok = _sha(det.read_bytes()) == rep.get("output_sha256")
        out["detections"] = {"present": True, "sha256_matches_ingest_report": det_ok}
    else:
        out["detections"] = {"present": False}
    out["committed_missing_list"] = {"path": _rel(series.MISSING_DATES), "present": series.MISSING_DATES.is_file()}
    avail_path = Path(availability) if availability else latest_dated("firms_data_availability")
    miss_path = Path(missing) if missing else latest_dated("provider_missing_dates")
    streams = None
    if avail_path is not None and avail_path.is_file():
        ranges, meta = load_availability(avail_path)
        bad = availability_problems(ranges)
        problems += bad
        streams = month_streams(ranges) if ranges and not bad else None
        out["availability"] = meta | {"stream_by_month": streams}
    else:
        out["availability"] = {"present": False}
    if miss_path is not None and miss_path.is_file():
        lists, meta = load_missing(miss_path)
        problems += missing_label_problems(meta)
        listed = listed_2026(lists, ("SNPP", "NOAA20"))
        out["refreshed_missing_list"] = meta | {"days_not_listed_by_month": {
            mo: sum(1 for t in month_days(mo) if not any(t in listed[p] for p in listed)) for mo in G03_MONTHS}}
    else:
        out["refreshed_missing_list"] = {"present": False}
    files_ok = True
    try:
        entries = api_entries(manifest)
    except SystemExit as err:
        entries, files_ok = [], False
        problems.append(str(err))
    rootp = Path(root or config.ROOT)
    files = []
    for e in entries:
        path = rootp / e["path"]
        rec = {"id": e["id"], "source": e["source"], "start": e.get("start"), "days": e.get("days"),
               "present": path.is_file(), "url_redacted": _redact(e.get("url_redacted"))}
        if rec["present"]:
            raw_bytes = path.read_bytes()
            rec["sha256_matches_manifest"] = _sha(raw_bytes) == e.get("sha256")
            raw = _read_csv(raw_bytes)
            rec["has_type_field"] = "type" in raw.columns
            rec["missing_columns"] = [c for c in ingest.REQUIRED if c not in raw.columns]
            rec["format_problems"] = _format_problems(raw)
            if len(raw) and "acq_date" in raw:
                dates = pd.to_datetime(raw["acq_date"], errors="coerce")
                start = pd.Timestamp(e["start"])
                end = start + pd.Timedelta(days=int(e["days"]) - 1)
                rec["acq_dates_inside_chunk"] = bool(dates.between(start, end).all())
            files_ok &= rec["sha256_matches_manifest"] and not rec["missing_columns"] and not rec["format_problems"]
        else:
            files_ok = False
        files.append(rec)
    out["raw_2026_files"] = files
    gaps = (coverage_gaps(entries, streams) if streams
            else ["no usable availability answer: the stream per month is unknown"])
    gaps += coverage_overlaps(entries)
    out["coverage_gaps"] = gaps
    out["problems"] = problems
    out["ready"] = {
        "g01g02": bool(code_ok and det_ok and series.MISSING_DATES.is_file()
                       and not any(out["results_present"][t] for t in ("G01", "G02"))),
        "g03g04": bool(det_ok and streams and miss_path is not None and miss_path.is_file() and entries
                       and files_ok and not gaps and not problems
                       and not any(out["results_present"][t] for t in ("G03", "G04")))}
    return out


# ---------- practice: Punjab only (P04's development area), never a test ----------
PRACTICE_WINDOWS = ("OctNov", "Nov", "rice")  # G01's two windows (2018-25) and G02's rice window (each pair's years)
PRACTICE_TEXT = {"OctNov": "October–November 2018–25 (G01 fall)", "Nov": "November 2018–25 (G01 step)",
                 "rice": "rice season, 15 Sep–31 Dec (G02: Aqua and S-NPP 2012–25, NOAA-20 and S-NPP 2018–25)"}
DEVCHECK = config.REPORTS / "p04_devcheck.json"


def _practice_scope(area, windows) -> tuple[str, ...]:
    """punjab-check counts Punjab's October-November, November and rice windows only. Any other area or window (a
    test province, spring, 2026, India) is refused before anything is read."""
    if area != DEV_AREA:
        raise SystemExit(f"Refusing: punjab-check counts {DEV_AREA} only (P04's development area, seen before the "
                         f"tests); {area!r} is not allowed")
    windows = (windows,) if isinstance(windows, str) else tuple(windows)
    if not windows:
        raise SystemExit("Refusing: punjab-check needs a window: OctNov, Nov or rice")
    bad = [w for w in windows if w not in PRACTICE_WINDOWS]
    if bad:
        raise SystemExit("Refusing: punjab-check uses October–November (OctNov), November (Nov) and the rice window "
                         f"(rice) only; {bad} is not allowed")
    return windows


def practice_days(windows=PRACTICE_WINDOWS) -> pd.DatetimeIndex:
    """Every UTC day punjab-check may count: G01's windows in 2018-25 and the rice window in each pair's years."""
    days: set = set()
    for w in _practice_scope(DEV_AREA, windows):
        if w in G01_WINDOWS:
            for y in G01_YEARS:
                days.update(window_days(y, *G01_WINDOWS[w]))
        else:
            for y in sorted({y for _, _, ys in PAIRS.values() for y in ys}):
                days.update(window_days(y, *G02_WINDOWS[w]))
    return pd.DatetimeIndex(sorted(days))


def punjab_numbers(d: pd.DataFrame, spans: dict, miss: dict, windows=PRACTICE_WINDOWS) -> dict:
    """Punjab's G01 and G02 numbers from run_g01g02's own functions (day_pass_counts, g01_window, g01_fall, g01_step,
    g02_pair). Only Punjab's rows on the practice days reach the count."""
    windows = _practice_scope(DEV_AREA, windows)
    keep = d["province"].astype(str).eq(DEV_AREA) & d["date_utc"].isin(practice_days(windows))
    counts = day_pass_counts(d[keep], (DEV_AREA,))
    out: dict = {}
    if "OctNov" in windows:
        out["fall"] = g01_fall(*g01_window(counts, DEV_AREA, "OctNov", spans, miss))
    if "Nov" in windows:
        out["step"] = g01_step(*g01_window(counts, DEV_AREA, "Nov", spans, miss))
    if "rice" in windows:
        out["rice"] = {pair: g02_pair(counts, DEV_AREA, "rice", pair, spans, miss) for pair in PAIRS}
    return out


def _same(a, b) -> bool:
    """Unrounded: equal whole numbers, or floats equal to 1e-9 relative (both sides come from unrounded JSON)."""
    if a is None or b is None:
        return a is None and b is None
    try:
        return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-12)
    except (TypeError, ValueError):
        return a == b


def punjab_compare(ours: dict, dev: dict) -> list[dict]:
    """Each practice number beside reports/c08/p04_devcheck.json's: G01_punjab.matched (the fall's delta and p, the
    step's ratio) and G02_punjab_rice floor200_matched (eligible years, misses, largest gaps). A number one side lacks
    matches only if the other side lacks it too."""
    items: list[dict] = []

    def add(name: str, a, b) -> None:
        items.append({"item": name, "runner": a, "devcheck": b, "match": _same(a, b)})

    g01 = (dev.get("G01_punjab") or {}).get("matched") or {}
    if "fall" in ours:
        fall = (g01.get("OctNov") or {}).get("fall") or {}
        add("G01 fall, October–November 2018–25: delta", ours["fall"]["delta"], fall.get("delta"))
        add("G01 fall: one-sided permutation p", ours["fall"]["p"], fall.get("p_one_sided_as_low"))
    if "step" in ours:
        step = (g01.get("Nov") or {}).get("step") or {}
        add("G01 step: R(Nov 2022) / mean R(Nov 2018–21)", ours["step"]["ratio_to_mean"], step.get("ratio_to_mean"))
    for pair, r in (ours.get("rice") or {}).items():
        s = ((((dev.get("G02_punjab_rice") or {}).get(pair) or {}).get("summary") or {}).get("floor200_matched")
             or {})
        add(f"G02 rice, {pair}: eligible years", len(r["eligible_years"]), s.get("eligible_years"))
        add(f"G02 rice, {pair}: middle-date misses", r["middle_misses"], s.get("middle_misses"))
        add(f"G02 rice, {pair}: end-date misses", r["end_misses"], s.get("end_misses"))
        add(f"G02 rice, {pair}: largest middle-date gap (matched days)", r["max_abs_d_mid"], s.get("max_abs_d_mid"))
        add(f"G02 rice, {pair}: largest end-date gap (matched days)", r["max_abs_d_end"], s.get("max_abs_d_end"))
    return items


def _show(v, full: bool = False) -> str:
    if v is None:
        return "none"
    if isinstance(v, float):
        return repr(v) if full else f"{v:.6g}"
    return str(v)


def punjab_check(*, area=DEV_AREA, windows=PRACTICE_WINDOWS, detections=None, report=None, missing=None,
                 devcheck=None, out=print) -> int:
    """Practice on Punjab, P04's development area (its numbers were seen before the tests): run_g01g02's own
    functions on Punjab's October-November, November and rice windows with the committed missing-days list,
    compared with reports/c08/p04_devcheck.json. Prints match or MISMATCH per item with Punjab's numbers, writes
    nothing, and returns 0 only if every item matches. It is never a test: no test province, spring window, 2026
    day or Indian row is counted."""
    windows = _practice_scope(area, windows)  # refused before anything is read
    dev_path = Path(devcheck or DEVCHECK)
    if not dev_path.is_file():
        raise SystemExit(f"Refusing: {_rel(dev_path)} is missing (python -m c08.p04_devcheck writes it)")
    dev = json.loads(dev_path.read_text(encoding="utf-8"))
    d, _, det_sha = load_archive(Path(detections or ingest.DETECTIONS), Path(report or ingest.INGEST_REPORT))
    lists, miss_meta = load_missing(missing or series.MISSING_DATES)
    items = punjab_compare(punjab_numbers(d, series.record_spans(d), lists.get("standard", {}), windows), dev)
    seen = dev.get("inputs") or {}
    out(f"Punjab practice check ({DEV_AREA} only, P04's development area, seen before the tests): "
        + "; ".join(PRACTICE_TEXT[w] for w in windows) + ". Nothing is written; this is not a test.")
    out("Inputs: the detections file is " + ("the same as" if seen.get("detections_sha256") == det_sha else "NOT")
        + " the devcheck's; the committed missing-days list is "
        + ("the same as" if seen.get("missing_days_sha256") == miss_meta["sha256"] else "NOT") + " the devcheck's.")
    for it in items:
        full = not it["match"]  # a mismatch shows every digit
        out(f"{'match' if it['match'] else 'MISMATCH'}: {it['item']}: runner {_show(it['runner'], full)}, "
            f"devcheck {_show(it['devcheck'], full)}")
    bad = sum(not it["match"] for it in items)
    out(f"All {len(items)} items match." if not bad else f"{bad} of {len(items)} items MISMATCH.")
    return 0 if not bad else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m c08.p04",
                                 description="Protocol P04 runner: G01-G04, each run once (G05 is withdrawn); "
                                             "punjab-check is practice on Punjab only.")
    ap.add_argument("command", choices=("preflight", "g01g02", "g03g04", "punjab-check"))
    ap.add_argument("--approved", help="CHECK REPORT P04-CL text or Hasnain's go-ahead; recorded in each result")
    ap.add_argument("--availability", help="FIRMS availability answer (G03/G04; default: newest dated file)")
    ap.add_argument("--missing", help="refreshed missing-days list (G03/G04; default: newest dated file)")
    ap.add_argument("--area", help="punjab-check only: Punjab (any other area is refused)")
    ap.add_argument("--window", action="append",
                    help="punjab-check only: OctNov, Nov or rice (repeat it; default all three; others are refused)")
    a = ap.parse_args(argv)
    if a.command == "punjab-check":
        if a.approved is not None or a.availability is not None or a.missing is not None:
            raise SystemExit("punjab-check is practice on Punjab with the committed missing-days list: it takes no "
                             "--approved, --availability or --missing")
        return punjab_check(area=DEV_AREA if a.area is None else a.area,
                            windows=PRACTICE_WINDOWS if a.window is None else tuple(a.window))
    if a.area is not None or a.window is not None:
        raise SystemExit("--area and --window belong to punjab-check only")
    if a.command == "preflight":
        print(json.dumps(_jsonable(preflight(availability=a.availability, missing=a.missing)), indent=1,
                         ensure_ascii=False))
        return 0
    if a.command == "g01g02":
        if a.availability or a.missing:
            raise SystemExit("G01 and G02 use the committed missing-days list only; drop --availability/--missing")
        out = run_g01g02(a.approved)
    else:
        out = run_g03g04(a.approved, availability=a.availability, missing=a.missing)
    for k, v in out.items():
        print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
