"""Showcase cards: the project's story, read from saved result files only (GET /api/showcase).

Five cards, in story order:
  headline  this October's press headline taken apart (Protocol P04, test G04);
  seam      S-NPP's end and whether NOAA-20 can carry the record (P04 G03; E02's earlier test);
  clock     morning and afternoon passes (P02 for Punjab; P04 G01 for Sindh and Khyber Pakhtunkhwa);
  season    the season's middle and end dates (Punjab's development check; P04 G02 elsewhere);
  log       mistakes caught, and facts with the date they were read (reports/c08/verification_log.json).

Rules kept here:
- Only saved files are read: experiments/*/result.json, reports/c08/p02_posthoc.json,
  reports/c08/p04_devcheck.json (Punjab, the development area, plus dates) and
  reports/c08/verification_log.json. No detection row is read and no test quantity is computed.
  The only arithmetic is for display: rounding, and the headline card's 2026-against-2019 changes,
  worked out from the per-satellite counts G04 saves and labelled as such.
- While a P04 test has no result file, its card says "Waiting for the frozen test P04 G0x" and what
  it needs, and shows nothing from that test's data.
- Satellites are never added together, except in the headline's naive sum, which says so.
- Missing values stay None (shown as unknown), never zero. Every card lists the files it read.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import date, datetime, timezone
from pathlib import Path

from . import config

ORDER = ("headline", "seam", "clock", "season", "log")
TITLES = {
    "headline": "This October's headline, taken apart",
    "seam": "S-NPP stopped on 2 Nov 2026; can NOAA-20 carry the record?",
    "clock": "Morning and afternoon passes see different shares",
    "season": "The season's middle and end dates",
    "log": "Mistakes we caught, and facts with the date we read them",
}
CARD_IDS = {k: f"{k}-card" for k in ORDER}

P04_TESTS = {"G01": "P04_G01_terra_step", "G02": "P04_G02_season_dates",
             "G03": "P04_G03_bridge_2026", "G04": "P04_G04_headline"}
WAITING = {
    "G01": ("Terra's autumn fall in Sindh and Khyber Pakhtunkhwa",
            "one run of the P04 code (c08/p04.py) on the 2018–2025 archive already in hand"),
    "G02": ("the season's middle and end dates in Sindh and Khyber Pakhtunkhwa (rice season) "
            "and in all three provinces (spring season)",
            "one run of the P04 code (c08/p04.py) on the 2012–2025 archive already in hand"),
    "G03": ("the NOAA-20 bridge on January–October 2026",
            "the 2026 FIRMS files for S-NPP and NOAA-20 (1 January–31 October 2026), then one run of "
            "the P04 code (c08/p04.py)"),
    "G04": ("reproducing the press figures for 1–29 October 2026",
            "the 1–29 October 2026 FIRMS files for S-NPP, NOAA-20 and NOAA-21, then one run of the "
            "P04 code (c08/p04.py)"),
}

SAT_NAMES = {"SNPP": "S-NPP", "NOAA20": "NOAA-20", "NOAA21": "NOAA-21", "Aqua": "Aqua", "Terra": "Terra"}
VIIRS = ("SNPP", "NOAA20", "NOAA21")
# First calendar year with data (launches: S-NPP Oct 2011, NOAA-20 Nov 2017, NOAA-21 Nov 2022).
VIIRS_FIRST_YEAR = {"SNPP": 2012, "NOAA20": 2018, "NOAA21": 2023}

PRESS = {
    "area": "Pakistani Punjab", "period": "1–29 October 2026",
    "sum": 13241, "sum_label": "Three satellites summed",
    "sum_what": "detections summed over three VIIRS satellites (S-NPP, NOAA-20 and NOAA-21)",
    "snpp": 4562, "snpp_label": "S-NPP alone",
    "snpp_what": "detections from one satellite, S-NPP",
    "sources": ["Daily Pakistan, 2 November 2026", "Minute Mirror, 31 October 2026"],
    "seen": "Both figures were read before Protocol P04 was written (its section 0).",
}
G04_READINGS = {  # PROTOCOL_P04.md, change log entry 1, item 7.2
    "reproduced": "Reproduced",
    "sum_only": "The three-satellite sum matches the press figure, S-NPP alone does not: the published "
                "single-satellite count may use another method",
    "snpp_only": "S-NPP alone matches; the sum does not: the press may have summed other satellites or streams",
    "not_reproduced": "Not reproduced; the published method may differ (area, filters or stream)",
}
G04_BADGES = {"reproduced": ("Reproduced", "pass"), "sum_only": ("Partly reproduced: the sum only", "mixed"),
              "snpp_only": ("Partly reproduced: S-NPP only", "mixed"), "not_reproduced": ("Not reproduced", "fail"),
              "unknown": ("Reading not recognised", "mixed")}
NAIVE_LABEL = "naive sum of satellites, not comparable across years"

SNPP_END = {
    "text": "S-NPP's data delivery stopped at 15:40 UTC on 2 November 2026.",
    "source": "NOAA NESDIS, S-NPP Update #4",
    "also": "NASA's catalogue, checked on 3 and 5 November 2026: the newest standard-processing file is "
            "from 13:54 UTC and the newest near-real-time file from 15:24 UTC, both on 2 November.",
}
G03_STATUS = {  # PROTOCOL_P04.md section 3 and change log items 6.5-6.7
    "pass": ("Passed its frozen test", "pass",
             "By the rule fixed before the test, Punjab's harmonised record continues on NOAA-20 from November "
             "2026, converted by the tested bridge, in whole months only: no month mixes satellites. Other areas "
             "show NOAA-20 in its own units, labelled \"bridge tested in Punjab only\". NOAA-21 appears only as its "
             "own labelled series, never added."),
    "fail": ("Failed its frozen test", "fail",
             "By the rule fixed before the test, the harmonised record stops at October 2026, the last full "
             "S-NPP month, and NOAA-20 is shown in its own units."),
    "not_testable": ("Not tested: too few months with matched data", "mixed",
                     "The NOAA-20 bridge was not tested (too few months with matched data). The harmonised record "
                     "stops at October 2026, and NOAA-20 is shown in its own units."),
}
G03_PASS_MARK = ("Pass mark, fixed before the test: total error (WAPE) at most 10% over the scored months, and "
                 "every month with at least 300 S-NPP detections within 20%. Scored months are January–October "
                 "2026 months with at least 20 matched days (days on which both satellites were observing); "
                 "fewer than 6 means \"not testable\". Only Punjab is scored.")

FALL_CLAUSES = {  # PROTOCOL_P04.md, change log item 3.6
    "present": "Terra's fall is also seen",
    "large_not_significant": "a large fall, not significant with these years",
    "not_seen": "Terra's fall is not seen; this does not rule out the clock, because burning hours may differ "
                "between provinces",
    "not_testable": "the fall is not testable",
}
STEP_CLAUSES = {"present": "a 2022 step is seen", "absent": "no 2022 step is seen",
                "not_testable": "the 2022 step is not testable"}
CAUSE_NOTE = ("This is consistent with a satellite-side cause (the pass time, the October 2022 orbit change, or "
              "both); a Pakistan-wide change in burning hours would give the same result; untested.")

WINDOWS = {
    "rice": {"name": "rice season", "label": "15 September–31 December", "start": [9, 15], "end": [12, 31]},
    "spring": {"name": "spring season", "label": "15 March–30 June", "start": [3, 15], "end": [6, 30]},
}
PAIRS = {"Aqua-SNPP": ("Aqua", "SNPP"), "NOAA20-SNPP": ("NOAA20", "SNPP")}
SEASON_DEFINITION = ("The season's middle and end dates (detected burning activity): the middle date is the first "
                     "day by which half of the season's day-pass detections had been seen, the end date the first "
                     "day by which 90% had. Each satellite is dated on its own, over the days both satellites of a "
                     "pair were observing, so dates are compared, not counts.")
PAST_ONLY = "Past seasons only: these dates describe what happened, not what will happen."

DETECTION = "A detection is one fire pixel seen on one satellite pass."
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")


# ---------- small helpers ----------
def _num(v) -> float | None:
    """A finite number, or None. Missing stays missing (never zero); strings and booleans are not numbers."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v) if math.isfinite(v) else None


def _text(v, limit: int = 2000) -> str | None:
    return v.strip()[:limit] if isinstance(v, str) and v.strip() else None


def _bool(v) -> bool | None:
    return v if isinstance(v, bool) else None


def _norm(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _iso(v) -> str | None:
    if not isinstance(v, str) or not DATE_RE.match(v):
        return None
    try:
        date.fromisoformat(v)
    except ValueError:
        return None
    return v


def _pct(v: float | None, digits: int = 0, signed: bool = True) -> str:
    """-0.7897 -> '−79%'; with signed=False only the size, '79%' (for "fell 79%" and for errors).
    Display only: the comparisons themselves were made unrounded, in the result files."""
    if v is None:
        return "unknown"
    x = round(abs(v) * 100, digits)
    body = f"{x:.{digits}f}%"
    if x == 0 or not signed:
        return body
    return ("−" if v < 0 else "+") + body


def _p(v: float | None) -> str:
    return "unknown" if v is None else f"{v:.2g}"


def _int(v: float | None) -> str:
    return "unknown" if v is None else f"{round(v):,}"


def _times(v: float | None, digits: int = 2) -> str:
    return "unknown" if v is None else f"{v:.{digits}f}"


def _years_text(years: list[int]) -> str:
    """[2018, 2019, 2020, 2021] -> '2018–2021'; gaps listed separately."""
    years = sorted(set(years))
    runs, start = [], None
    for i, y in enumerate(years):
        if start is None:
            start = y
        if i == len(years) - 1 or years[i + 1] != y + 1:
            runs.append(str(start) if start == y else f"{start}–{y}")
            start = None
    return ", ".join(runs)


def _runs(years: list[int]) -> list[list[int]]:
    out: list[list[int]] = []
    for y in sorted(set(years)):
        if out and y == out[-1][1] + 1:
            out[-1][1] = y
        else:
            out.append([y, y])
    return out


def _read(path: Path, shown: str) -> tuple[dict | None, dict | None]:
    """A saved JSON object and where it came from (path, short SHA-256, when written), or (None, None)."""
    if not path.is_file():
        return None, None
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{shown} is not a JSON object")
    src = {"path": shown, "sha256": hashlib.sha256(raw).hexdigest()[:12]}
    for k in ("run_utc", "updated", "written_utc", "generated_utc"):
        if isinstance(data.get(k), str):
            src["written"] = data[k][:40]
            break
    cs = data.get("code_state")
    if isinstance(cs, dict) and isinstance(cs.get("revision"), str):
        src["code_revision"] = cs["revision"][:40]
    if isinstance(data.get("protocol_sha256"), str):  # ingest.protocol_state(): the frozen text it followed
        src["protocol"] = (_text(data.get("protocol"), 120) or "protocol").rsplit("/", 1)[-1]
        src["protocol_sha256"] = data["protocol_sha256"][:12]
    return data, src


def _experiment(name: str) -> tuple[dict | None, dict | None]:
    return _read(config.EXPERIMENTS / name / "result.json", f"experiments/{name}/result.json")


def _report(fname: str) -> tuple[dict | None, dict | None]:
    return _read(config.REPORTS / fname, f"reports/c08/{fname}")


def _dig(d, *keys):
    """d[k1][k2]... or None when any step is missing."""
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def _first(d: dict, *names):
    """The first of several spellings of a key that is present and not None (result files differ in naming)."""
    for n in names:
        if isinstance(d, dict) and d.get(n) is not None:
            return d[n]
    return None


def _short_date(iso: str) -> str:
    """'2026-10-05' -> '5 Oct'."""
    return f"{int(iso[8:10])} {MONTHS[int(iso[5:7]) - 1][:3]}"


def _waiting(test: str) -> dict:
    what, needs = WAITING[test]
    return {"test": f"P04 {test}", "text": f"Waiting for the frozen test P04 {test}", "what": what,
            "needs": needs, "file": f"experiments/{P04_TESTS[test]}/result.json",
            "rule": "Each P04 test runs once, and nothing from its test data is shown before it has run."}


def _card(key: str) -> dict:
    return {"key": key, "id": CARD_IDS[key], "title": TITLES[key], "sources": []}


def _add_source(card: dict, src: dict | None) -> None:
    if src and src not in card["sources"]:
        card["sources"].append(src)


def _safe(builder, key: str) -> dict:
    """One unreadable file must not take the other cards down: the card says what went wrong instead."""
    try:
        return builder()
    except Exception as e:  # noqa: BLE001 - shown on the card, never hidden
        card = _card(key)
        card.update(state="error", error=f"A saved file could not be read ({type(e).__name__}: {str(e)[:300]}).")
        return card


# ---------- 1. headline (G04) ----------
def _sat_key(k) -> str | None:
    return {"snpp": "SNPP", "suominpp": "SNPP", "npp": "SNPP", "noaa20": "NOAA20", "j1": "NOAA20",
            "jpss1": "NOAA20", "noaa21": "NOAA21", "j2": "NOAA21", "jpss2": "NOAA21"}.get(_norm(k))


def _g04_key(sum_within, snpp_within) -> str:
    if not isinstance(sum_within, bool) or not isinstance(snpp_within, bool):
        return "unknown"
    return {(True, True): "reproduced", (True, False): "sum_only", (False, True): "snpp_only",
            (False, False): "not_reproduced"}[(sum_within, snpp_within)]


def _rel_change(new: float | None, old: float | None) -> float | None:
    if new is None or old is None or old <= 0:
        return None
    return new / old - 1


def _headline_years(per: dict, flying: dict) -> list[dict]:
    years = sorted((y for y in per if str(y).isdigit()), key=int) or ["2019", "2026"]
    out = []
    for y in years:
        given = per.get(y) if isinstance(per.get(y), dict) else {}
        row = {_sat_key(k): v for k, v in given.items() if _sat_key(k)}
        bars = []
        for key in VIIRS:
            if key in row:
                v = _num(row[key])
                why = None if v is not None else "no value in the result file"
            else:
                v, why = None, "not flying" if int(y) < VIIRS_FIRST_YEAR[key] else "not in the result file"
            bars.append({"key": key, "label": SAT_NAMES[key], "value": v, "why": why})
        n_flying = _num(flying.get(y)) if isinstance(flying, dict) else None
        if n_flying is None:
            n_flying = float(sum(b["why"] != "not flying" for b in bars))
        out.append({"year": str(y), "flying": int(n_flying), "bars": bars})
    return out


def _headline_changes(data: dict, years: list[dict]) -> list[dict]:
    saved = data.get("changes") if isinstance(data.get("changes"), dict) else data.get("change")
    saved = saved if isinstance(saved, dict) else {}
    by_year = {y["year"]: y for y in years}
    old, new = by_year.get("2019"), by_year.get("2026")

    def value(year_row, key):
        b = next((b for b in year_row["bars"] if b["key"] == key), None) if year_row else None
        return b["value"] if b else None

    def flying_sum(year_row):
        if not year_row:
            return None
        vals = [b["value"] for b in year_row["bars"] if b["why"] != "not flying"]
        return None if not vals or any(v is None for v in vals) else sum(vals)  # an unknown member makes the sum unknown

    one = _num(_first(saved, "snpp_only", "snpp"))
    one_src = "saved in the result file"
    if one is None:
        one, one_src = _rel_change(value(new, "SNPP"), value(old, "SNPP")), \
            "worked out here from the saved per-satellite counts (display only)"
    naive = _num(_first(saved, "naive_sum", "sum"))
    naive_src = "saved in the result file"
    if naive is None:
        naive, naive_src = _rel_change(flying_sum(new), flying_sum(old)), \
            "worked out here from the saved per-satellite counts (display only)"
    n_old = old["flying"] if old else None
    n_new = new["flying"] if new else None
    return [
        {"kind": "one_satellite", "label": "S-NPP's own detections, one satellite: 1–29 October 2026 against 2019",
         "value": one, "text": _pct(one), "from": one_src,
         "note": "The same instrument compared with itself, so this change is not inflated by added satellites."},
        {"kind": "naive", "label": NAIVE_LABEL[0].upper() + NAIVE_LABEL[1:], "value": naive, "text": _pct(naive),
         "from": naive_src,
         "note": (f"{n_old} VIIRS satellites were flying in 2019 and {n_new} in 2026. A sum grows when a satellite "
                  "is added, even if burning does not change." if n_old and n_new else
                  "A sum grows when a satellite is added, even if burning does not change.")},
    ]


def headline_card() -> dict:
    card = _card("headline")
    card["press"] = PRESS
    card["lede"] = (f"Press reports gave {PRESS['sum']:,} for Pakistani Punjab, 1–29 October 2026: VIIRS detections "
                    f"summed over three satellites. S-NPP alone gave {PRESS['snpp']:,}. A total summed over "
                    "satellites grows whenever another satellite is launched, even if burning does not change. This "
                    f"card checks both figures against our own copy of the data and takes the sum apart. {DETECTION}")
    card["flying_fact"] = ("VIIRS satellites flying: 2 in October 2019 (S-NPP and NOAA-20), 3 in October 2026 "
                           "(S-NPP, NOAA-20 and NOAA-21).")
    card["readings_fixed"] = [G04_READINGS[k] for k in ("reproduced", "sum_only", "snpp_only", "not_reproduced")]
    data, src = _experiment(P04_TESTS["G04"])
    if data is None:
        card.update(state="waiting", waiting=_waiting("G04"))
        card["waiting_points"] = [
            "The test: our count for Pakistani Punjab, 1–29 October 2026, all rows (no quality or type filter, as a "
            "press count may use), must be within ±20% of each press figure.",
            "Then the card shows each satellite's count for 1–29 October 2019 and 2026 side by side (never "
            "stacked), and the S-NPP-only change beside the summed change.",
        ]
        return card
    _add_source(card, src)
    s, n = data.get("sum") or {}, data.get("snpp") or {}
    s, n = (s if isinstance(s, dict) else {}), (n if isinstance(n, dict) else {})
    key = _g04_key(s.get("within"), n.get("within"))
    reading = _text(data.get("reading")) or G04_READINGS.get(key, "The result file gives no reading.")
    badge, kind = G04_BADGES[key]
    per = data.get("per_satellite") if isinstance(data.get("per_satellite"), dict) else {}
    flying = data.get("satellites_flying") if isinstance(data.get("satellites_flying"), dict) else {}
    years = _headline_years(per, flying)
    rng = data.get("snpp_range_2018_2025") if isinstance(data.get("snpp_range_2018_2025"), dict) else {}
    lo, hi = _num(rng.get("min")), _num(rng.get("max"))
    streams = data.get("streams") if isinstance(data.get("streams"), dict) else {}
    stream_text = ", ".join(f"{SAT_NAMES[k]} {_text(streams[k], 10)}" for k in VIIRS if _text(streams.get(k), 10))
    result = {
        "reading": reading, "reading_key": key, "badge": badge, "badge_kind": kind,
        "sum": {"label": "S-NPP + NOAA-20 + NOAA-21 (three satellites summed)", "value": _num(s.get("value")),
                "target": _num(s.get("target")) or float(PRESS["sum"]), "within": _bool(s.get("within"))},
        "snpp": {"label": "S-NPP alone", "value": _num(n.get("value")),
                 "target": _num(n.get("target")) or float(PRESS["snpp"]), "within": _bool(n.get("within"))},
        "count_rule": ("Our counts: Pakistani Punjab (geoBoundaries outline), every UTC day of 1–29 October 2026, "
                       "all rows with no quality or type filter, as a press count may use"
                       + (f"; streams: {stream_text}" if stream_text else "") + ". \"Within\" means within ±20% of "
                       "the press figure."),
        "years": years,
        "bars_caption": ("Each satellite's own count for 1–29 October in Pakistani Punjab, side by side, never "
                         "stacked: nominal- and high-confidence detections, with no type screen in either year "
                         "(the 2026 near-real-time files carry no type field). 2019 comes from FIRMS's standard "
                         "archive and 2026 from its near-real-time files, so the two years are processed differently. "
                         "An empty dashed slot means the satellite was not flying, not zero."
                         + _bars_vs_test_text(per, n)),
        "changes": _headline_changes(data, years),
        "snpp_range": {"min": lo, "max": hi},
        "snpp_range_text": (f"For scale: S-NPP's own 1–29 October count in 2018–2025, under the same rule, ranged "
                            f"from {_int(lo)} to {_int(hi)}." + _lowest_year_text(rng, lo)
                            if lo is not None and hi is not None else None),
        "gap_text": _g04_gaps(data.get("gap_days", data.get("listed_gap_days"))),
    }
    card.update(state="result", result=result)
    return card


def _g04_gaps(g) -> str | None:
    """The 1-29 Oct 2026 gap days, which G04 reports beside its counts instead of removing them."""
    head = "Gaps in 1–29 October 2026, counted as they are, not removed: "
    if isinstance(g, list):  # one list of dates
        days = [d for d in map(_iso, g) if d]
        return head + ", ".join(_short_date(d) for d in days) + "." if days else None
    if not isinstance(g, dict):
        return None
    parts = []
    for key in VIIRS:
        v = g.get(key)
        if not isinstance(v, dict):
            continue
        bits = []
        for field, words in (("listed_missing", "FIRMS lists as missing"),
                             ("no_row_in_pakistan", "no detection anywhere in Pakistan"),
                             ("one_pass_only", "only one of the two daily passes")):
            days = [d for d in map(_iso, v.get(field) or []) if d] if isinstance(v.get(field), list) else []
            if days:
                bits.append(f"{words}: {', '.join(_short_date(d) for d in days)}")
        stream = _text(v.get("stream"), 10)
        parts.append(f"{SAT_NAMES[key]}{f' ({stream})' if stream else ''}: " + ("; ".join(bits) if bits else "none"))
    return head + ". ".join(parts) + "." if parts else None


# ---------- 2. seam (G03, with E02's earlier test) ----------
def _g03_status(v) -> str:
    n = _norm(v)
    return {"pass": "pass", "passed": "pass", "fail": "fail", "failed": "fail", "nottestable": "not_testable",
            "untestable": "not_testable", "nottested": "not_testable"}.get(n, "unknown")


def _availability_text(dev: dict | None) -> str | None:
    av = _dig(dev, "availability", "G03_2026")
    if not isinstance(av, dict) or not av:
        return None
    ok, short = [], []
    for m, v in sorted(av.items()):
        days = _num(v.get("days_matched")) if isinstance(v, dict) else None
        if days is None:
            continue
        (ok if days >= 20 else short).append((m, int(days)))
    if not ok and not short:
        return None
    total = len(ok) + len(short)

    def name(m):
        try:
            return f"{MONTHS[int(m[5:7]) - 1]} {m[:4]}"
        except (ValueError, IndexError):
            return m
    tail = "; ".join(f"{name(m)} has {'none' if d == 0 else f'only {d}'}" for m, d in short)
    return (f"On the 27 October missing-days list, {len(ok)} of these {total} months have at least 20 matched days"
            + (f" ({tail})" if tail else "") + ". The list is refreshed when the 2026 files are downloaded, so "
            "the final number of scored months can be lower.")


def _g03_months(rows) -> list[dict]:
    out = []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        out.append({"month": _text(str(r.get("month", "")), 20) or "unknown", "stream": _text(r.get("stream"), 40),
                    "matched_days": _num(r.get("matched_days")), "observed_snpp": _num(r.get("observed_snpp")),
                    "predicted": _num(r.get("predicted")), "error": _num(r.get("error")),
                    "held_to_month_rule": _bool(r.get("held_to_month_rule")),
                    "within_month_rule": _bool(r.get("within_month_rule"))})
    return out[:24]


def _g03_not_scored(rows) -> str | None:
    items = []
    for r in rows if isinstance(rows, list) else []:
        if isinstance(r, dict) and _text(str(r.get("month", "")), 20):
            m = str(r["month"])
            try:
                name = f"{MONTHS[int(m[5:7]) - 1]} {m[:4]}"
            except (ValueError, IndexError):
                name = m[:20]
            why = _text(r.get("reason"), 120)
            items.append(name + (f" ({why})" if why else ""))
    return ("Not scored: " + "; ".join(items) + ".") if items else None


def _g03_reported(rep) -> list[dict]:
    out = []
    for area, v in (rep.items() if isinstance(rep, dict) else []):
        if isinstance(v, dict) and (_num(v.get("wape")) is not None):
            out.append({"area": str(area)[:60], "wape": _num(v.get("wape")), "m0_wape": _num(v.get("m0_wape")),
                        "text": f"{str(area)[:60]}: {_pct(_num(v.get('wape')), 1, signed=False)}"
                                + (f" (no conversion: {_pct(_num(v.get('m0_wape')), 1, signed=False)})"
                                   if _num(v.get("m0_wape")) is not None else "")})
    return out


def seam_card() -> dict:
    card = _card("seam")
    card["lede"] = ("From 2012 Seamline's record is built on S-NPP. NOAA-20 carries the same kind of instrument "
                    "(VIIRS), and its detections cluster at about the same time of day as S-NPP's (about 1:05 pm "
                    "each year, P02), so it is the natural successor, if its counts can be put on S-NPP's scale.")
    card["facts"] = [SNPP_END]
    e2, e2src = _experiment("E02_evaluation")
    bt = _dig(e2, "bridge_test")
    if isinstance(bt, dict):
        _add_source(card, e2src)
        m1, m0 = _num(_dig(bt, "scores", "M1", "wape")), _num(_dig(bt, "scores", "M0", "wape"))
        yrs = [y for y in (bt.get("years") or []) if isinstance(y, int)]
        months = _num(bt.get("scored_months"))
        card["earlier_test"] = {
            "label": f"The earlier test: {_years_text(yrs) or 'unknown years'}, Punjab"
                     + (f", {int(months)} months" if months is not None else "") + " (Protocol P01, experiment E02)",
            "wape_m1": m1, "wape_m0": m0,
            "text": (f"Converted NOAA-20 missed S-NPP's monthly totals by {_pct(m1, 1, signed=False)} of the total "
                     f"(WAPE); unconverted NOAA-20 (M0) by {_pct(m0, 1, signed=False)}."),
            "note": ("A total, not a per-month bound: single months differed by a median of 5.3%, up to 12.4% "
                     "(docs/VALIDATION.md). Not drawn yet: the record chart ends in December 2025, and 2026 "
                     "months are added after the event."),
        }
    else:
        card["earlier_test"] = None
    card["pass_mark"] = G03_PASS_MARK
    data, src = _experiment(P04_TESTS["G03"])
    if data is None:
        dev, dsrc = _report("p04_devcheck.json")
        avail = _availability_text(dev)
        if avail:
            _add_source(card, dsrc)
        card.update(state="waiting", waiting=_waiting("G03"), availability_text=avail)
        return card
    _add_source(card, src)
    status = _g03_status(data.get("status"))
    head, kind, means = G03_STATUS.get(status, (f"Status not recognised: {str(data.get('status'))[:40]}", "mixed",
                                                "Read the result file for what this means."))
    wape, m0 = _num(data.get("wape")), _num(data.get("m0_wape"))
    m1_e2 = card["earlier_test"]["wape_m1"] if card["earlier_test"] else None
    m0_e2 = card["earlier_test"]["wape_m0"] if card["earlier_test"] else None
    unscored = "not scored" if status == "not_testable" else "unknown"
    n_scored = _num(data.get("scored_months"))
    worst = _num(data.get("worst_held_month_error"))
    sec = data.get("secondary_e02_fit") if isinstance(data.get("secondary_e02_fit"), dict) else {}
    sec_label = (_text(sec.get("label"), 120) or "Reported: E02's tested fit").rstrip(".")
    sec_wape, sec_m0 = _num(sec.get("wape")), _num(sec.get("m0_wape"))
    reason = _text(data.get("reason"), 300)
    facts = [t for t in (
        f"Reason: {reason}." if reason else None,
        f"Scored months: {int(n_scored)}." if n_scored is not None else None,
        _g03_not_scored(data.get("months_not_scored")),
        f"Largest error in a month held to the 20% rule: {_pct(worst, 1, signed=False)}." if worst is not None else None,
        (f"{sec_label[0].upper()}{sec_label[1:]}: total error {_pct(sec_wape, 1, signed=False)}"
         + (f" (no conversion: {_pct(sec_m0, 1, signed=False)})" if sec_m0 is not None else "")
         + "; not held to the pass mark.") if sec_wape is not None else None,
    ) if t]
    reading = _text(data.get("reading"))
    m0_note = ("M0, no conversion at all, is shown beside the bridge's error. "
               + (f"In the earlier test it scored almost the same ({_pct(m0_e2, 1, signed=False)} against "
                  f"{_pct(m1_e2, 1, signed=False)}), so " if m1_e2 is not None and m0_e2 is not None else "So ")
               + "a pass shows that converted NOAA-20 tracks S-NPP within the marks, not that the conversion "
                 "beats no conversion.")
    result = {
        # The test's own reading already states what happens to the record (and, from c08/p04.py, the M0 note),
        # so the protocol's wording here is shown only when the file has no reading.
        "status": status, "status_text": head, "badge_kind": kind, "means": None if reading else means,
        "reading": reading,
        # The saved reading is the rule for when 2026 months are added; say what is drawn today (readiness check, FE-1).
        "reading_note": ("The reading above is the rule for when 2026 months are added, after the event. The record "
                         "chart still ends in December 2025, so neither the seam label nor \"bridge tested in Punjab "
                         "only\" is drawn yet. M1 is the bridge: one fixed factor for NOAA-20's day passes and one for "
                         "its night passes.") if reading else None,
        "wape": wape, "m0_wape": m0, "facts": facts,
        "wape_text": _pct(wape, 1, signed=False) if wape is not None else unscored,
        "m0_text": _pct(m0, 1, signed=False) if m0 is not None else unscored,
        "m0_note": None if reading and "M0" in reading else m0_note,
        "months": _g03_months(data.get("months")),
        "months_caption": ("Each scored month of 2026 in Punjab: S-NPP as observed beside NOAA-20 converted to "
                           "S-NPP's scale (the bridge's prediction), side by side, never stacked. Months with fewer "
                           "than 300 S-NPP detections are shown but not held to the 20% month rule."),
        "reported": _g03_reported(data.get("reported")),
        "reported_note": ("Reported, not tested: each area on its own bridge, never with Punjab's factor; not held "
                          "to the pass mark."),
    }
    card.update(state="result", result=result)
    return card


# ---------- 3. clock (P02 for Punjab; G01 for Sindh and Khyber Pakhtunkhwa) ----------
def _fall_status(v) -> str | None:
    if isinstance(v, bool):
        return "present" if v else "not_seen"
    n = _norm(v)
    if n in ("present", "seen", "alsoseen", "fallpresent", "yes"):
        return "present"
    if n in ("largenotsignificant", "notsignificant", "large", "largefallnotsignificant"):
        return "large_not_significant"
    if n in ("notseen", "absent", "none", "no", "fallnotseen"):
        return "not_seen"
    if n in ("nottestable", "untestable", "nottested"):
        return "not_testable"
    return None


def _step_status(v) -> str | None:
    if isinstance(v, bool):
        return "present" if v else "absent"
    n = _norm(v)
    if n in ("present", "seen", "yes", "steppresent"):
        return "present"
    if n in ("absent", "notseen", "none", "no", "stepabsent"):
        return "absent"
    if n in ("nottestable", "untestable", "nottested"):
        return "not_testable"
    return None


def _status_of(p: dict, name: str, parse) -> tuple[str | None, dict]:
    part = p.get(name)
    detail = part if isinstance(part, dict) else {}
    for v in (detail.get("status"), detail.get("result"), detail.get("present"), p.get(f"{name}_status"),
              p.get(f"{name}_present"), part if not isinstance(part, dict) else None):
        s = parse(v) if v is not None else None
        if s:
            return s, detail
    return None, detail


def _g01_provinces(data: dict) -> list[dict]:
    provs = data.get("provinces")
    if not isinstance(provs, dict):
        return []
    names = [n for n in ("Sindh", "Khyber Pakhtunkhwa") if n in provs] + \
            [n for n in provs if n not in ("Sindh", "Khyber Pakhtunkhwa")]
    out = []
    for name in names:
        p = provs[name] if isinstance(provs[name], dict) else {}
        fall, fd = _status_of(p, "fall", _fall_status)
        step, sd = _status_of(p, "step", _step_status)
        reading = _text(p.get("reading"))
        if reading is None and (fall or step):
            fc = FALL_CLAUSES.get(fall, "the fall's result is not recognised")
            if fall == "not_testable" and _text(fd.get("reason")):
                fc += f" ({_text(fd.get('reason'), 200)})"
            sc = STEP_CLAUSES.get(step, "the step's result is not recognised")
            if step == "not_testable" and _text(sd.get("reason")):
                sc += f" ({_text(sd.get('reason'), 200)})"
            reading = f"{name}: {fc}; {sc}."
        both = _bool(p.get("both_present"))
        if both is None:
            both = fall == "present" and step == "present"
        details = []
        delta = _num(fd.get("delta"))
        pv = next((_num(fd.get(k)) for k in ("p", "p_one_sided_as_low", "p_value") if _num(fd.get(k)) is not None), None)
        if delta is not None:
            details.append(f"Fall, 2023–25 against 2018–21 (Terra ÷ S-NPP day passes): {_pct(delta)}"
                           + (f", p = {_p(pv)}" if pv is not None else ""))
        ratio = _num(sd.get("ratio_to_mean"))
        if ratio is not None:
            details.append(f"November 2022: {_times(ratio)} times the 2018–21 mean")
        out.append({"name": str(name)[:60], "reading": reading or "The result file gives no reading for this province.",
                    "fall": fall, "step": step, "both_present": bool(both),
                    "cause_note": CAUSE_NOTE if both and "satellite-side" not in (reading or "") else None,
                    "details": details})
    return out


def _hhmm(v) -> float | None:
    """'10:54' -> 654.0 minutes after midnight (local solar time); anything else -> None."""
    if not isinstance(v, str) or not re.match(r"^\d{1,2}:\d{2}$", v):
        return None
    h, m = v.split(":")
    return int(h) * 60 + int(m)


def _clock_punjab(card: dict) -> dict | None:
    f02, fsrc = _experiment("P02_F02_clock")
    post, psrc = _report("p02_posthoc.json")
    dev, dsrc = _report("p04_devcheck.json")
    if f02 is None and post is None and dev is None:
        return None
    out: dict = {"label": "Punjab (the development area; Protocol P02, checked on 3 November 2026)"}
    points = []
    # Pass times: median local solar time of October-November day-pass detections.
    by = _dig(post, "pass_times", "by_season")
    if isinstance(by, dict):
        _add_source(card, psrc)
        series = {}
        for sat in ("Terra", "Aqua", "SNPP", "NOAA20"):
            yrs = _dig(by, sat, "OctNov")
            if isinstance(yrs, dict):
                series[sat] = [{"year": int(y), "time": v.get("median"), "minutes": _hhmm(v.get("median"))}
                               for y, v in sorted(yrs.items()) if str(y).isdigit() and isinstance(v, dict)
                               and _hhmm(v.get("median")) is not None]
        out["pass_times"] = {
            "series": series,
            "caption": ("When each satellite sees Punjab's burning: the median local solar time of its "
                        "October–November day-pass detections. These are times of the detections, so they mix the "
                        "orbit with the hours when burning happens."),
        }
    # Q per year (P02 F02) with the months each year used (post-hoc file).
    yq = _dig(f02, "results", "yearly_Q", "OctNov")
    if isinstance(yq, dict):
        _add_source(card, fsrc)
        missing_22 = [d for d in (_dig(post, "terra_2022", "firms_missing_days_OctNov_2022") or []) if _iso(d)]
        snpp_incomplete = {m for y in (_dig(post, "snpp_octnov", "yearly") or {}).values() if isinstance(y, dict)
                           for m in (y.get("incomplete_months") or []) if isinstance(m, str)}
        series = {}
        for sat in ("Terra", "Aqua"):
            used = _dig(post, "D2", sat, "OctNov_months_used") or {}
            pts = []
            for y, q in sorted((yq.get(sat) or {}).items()):
                if not str(y).isdigit() or _num(q) is None:
                    continue
                note = None
                months = used.get(y) if isinstance(used, dict) else None
                if isinstance(months, list) and months and sorted(months) != [10, 11]:
                    only = " and ".join(MONTHS[m - 1] for m in months if isinstance(m, int) and 1 <= m <= 12)
                    note = f"{only} only"
                    if sat == "Terra" and y == "2022" and missing_22:
                        note += f": FIRMS lists Terra as missing {missing_22[0][8:].lstrip('0')}–" \
                                f"{missing_22[-1][8:].lstrip('0')} October 2022"
                    elif f"{y}-11" in snpp_incomplete:
                        note += f": S-NPP's November {y} is incomplete"
                pts.append({"year": int(y), "q": _num(q), "note": note})
            series[sat] = pts
        yu = _dig(f02, "results", "periods", "OctNov", "years_used", "Terra") or []
        out["q"] = {
            "series": series,
            "periods": _runs([y for y in yu if isinstance(y, int)]),
            "caption": ("Q, per year: the detections each MODIS satellite reported in October–November, divided by "
                        "the number expected from what S-NPP detected on the same days (P02's model). A fall in Q "
                        "means the satellite saw a smaller share. Log scale; shaded: the two periods compared."),
        }
    # The P02 headline numbers (whole years as the unit, from the post-hoc file).
    per = _dig(f02, "results", "periods", "OctNov")
    terra_d, aqua_d = _num(_dig(per, "delta", "Terra")), _num(_dig(per, "delta", "Aqua"))
    terra_p = _num(_dig(post, "D2", "Terra", "permutation_OctNov", "p_two_sided"))
    aqua_p = _num(_dig(post, "D2", "Aqua", "permutation_OctNov", "p_two_sided"))
    t_times = {p["year"]: p for p in _dig(out, "pass_times", "series", "Terra") or []}
    if terra_d is not None:
        _add_source(card, fsrc)
        early = sorted((t_times[y]["minutes"], t_times[y]["time"]) for y in range(2018, 2022) if y in t_times)
        moved = (f", from {early[0][1]}–{early[-1][1]} in 2018–21 to {t_times[2025]['time']} am in 2025"
                 if early and 2025 in t_times else "")
        points.append({"lead": f"Relative to S-NPP, Terra's October–November detections fell by about "
                               f"{'four-fifths' if -0.85 <= terra_d <= -0.75 else _pct(terra_d, signed=False)}",
                       "text": f" ({_pct(terra_d)} in P02's Q units, 2023–25 against 2018–21; whole years as the "
                               f"unit, p = {_p(terra_p)}) as its pass moved earlier{moved}."})
    if aqua_d is not None:
        points.append({"lead": "Aqua, whose pass moved later, showed no clear change",
                       "text": f" ({_pct(aqua_d)}, p = {_p(aqua_p)})."})
    step = _num(_dig(post, "terra_2022", "november_Q_change_2021_to_2022"))
    nt = _dig(post, "terra_2022", "november_median_time") or {}
    if step is not None:
        _add_source(card, psrc)
        points.append({"lead": "Terra fell in a step",
                       "text": f": November to November it fell {_pct(step, signed=False)} from 2021 to 2022, while "
                               f"its November pass moved only from {nt.get('2021', 'unknown')} to "
                               f"{nt.get('2022', 'unknown')}."})
    raw = _dig(dev, "G01_punjab", "matched")
    if isinstance(raw, dict):
        _add_source(card, dsrc)
        fall = _num(_dig(raw, "OctNov", "fall", "delta"))
        p_low = _num(_dig(raw, "OctNov", "fall", "p_one_sided_as_low"))
        splits = _num(_dig(raw, "OctNov", "fall", "splits"))
        p_text = _p(p_low)
        if p_low is not None and splits and abs(p_low * splits - round(p_low * splits)) < 1e-9:
            p_text = f"{int(round(p_low * splits))}/{int(splits)}"
        ratio = _num(_dig(raw, "Nov", "step", "ratio_to_mean"))
        below = _bool(_dig(raw, "Nov", "step", "below_every"))
        out["raw"] = {"fall": fall, "p": p_low, "p_text": p_text, "nov_2022_to_mean": ratio, "below_every": below}
        if fall is not None:
            points.append({"lead": "The raw ratio tells the same story",
                           "text": f": under P04's own rules (Terra ÷ S-NPP day-pass detections, on days both were "
                                   f"observing) Punjab's ratio fell {_pct(fall, signed=False)} (p = {p_text})"
                                   + (f", and November 2022 was {_times(ratio)} times the 2018–21 mean"
                                      + (", below every year of 2018–21" if below else "") if ratio is not None else "")
                                   + ". These Punjab numbers were seen before P04 was written, so Punjab is not "
                                     "part of the test."})
    out["points"] = points
    out["caution"] = ("What this does not show is the cause. The earlier pass time fits, but so does burning that "
                      "starts at a fixed hour late in the morning, and so does a change in Terra itself in 2022 (its "
                      "orbit was lowered in October 2022). Aqua's later pass gave no clear gain. Do not read this as "
                      "farmers changing their burning hours.")
    return out


def clock_card() -> dict:
    card = _card("clock")
    card["lede"] = ("Terra passes over Pakistan in the morning; Aqua, S-NPP and NOAA-20 in the early afternoon. "
                    "Terra and Aqua have been drifting (Terra earlier, Aqua later), while S-NPP and NOAA-20 keep "
                    "their time. If burning is bunched into certain hours, a satellite passing at a different hour "
                    "sees a different share of it.")
    card["punjab"] = _clock_punjab(card)
    data, src = _experiment(P04_TESTS["G01"])
    if data is None:
        card["provinces"] = {"state": "waiting", "waiting": _waiting("G01"),
                             "title": "Sindh and Khyber Pakhtunkhwa (frozen test P04 G01)"}
    else:
        _add_source(card, src)
        items = _g01_provinces(data)
        seen = [i["name"] for i in items if i["fall"] == "present"]
        card["provinces"] = {
            "state": "result", "title": "Sindh and Khyber Pakhtunkhwa (frozen test P04 G01)", "items": items,
            # The test's own summary line when it saved one; otherwise the same rule (item 3.6) applied here.
            "summary": _g01_summary(_text(data.get("seen_outside_punjab_reading"), 600)
                                    or (f"Terra's fall is also seen outside Punjab, in {' and '.join(seen)}."
                                        if seen else None)),
            "reading": _text(data.get("reading")),
        }
    card["state"] = "result" if card["punjab"] else "missing_files"
    if not card["punjab"]:
        card["text"] = ("Punjab's saved P02 results were not found (experiments/P02_F02_clock/result.json, "
                        "reports/c08/p02_posthoc.json, reports/c08/p04_devcheck.json).")
    return card


# ---------- 4. season dates (Punjab development check; G02) ----------
def _band(mid, end) -> dict | None:
    m, e = _iso(mid), _iso(end)
    return {"mid": m, "end": e} if m and e else None


def _window_key(k) -> str | None:
    n = _norm(k)
    if n.startswith(("rice", "autumn", "kharif")):
        return "rice"
    if n.startswith(("spring", "wheat", "rabi")):
        return "spring"
    return None


def _pair_key(k) -> str | None:
    n = _norm(k)
    if n.startswith("aqua"):
        return "Aqua-SNPP"
    if n.startswith(("noaa20", "n20", "j1", "jpss1")):
        return "NOAA20-SNPP"
    return None


def _pair_band(r: dict, side: str) -> dict | None:
    """One satellite's dates from a pair's year record; side 'src' (Aqua or NOAA-20) or 'ref' (S-NPP).
    p04_devcheck.json spells them mid_src/end_src, c08/p04.py src_mid/src_end."""
    return _band(_first(r, f"mid_{side}", f"{side}_mid"), _first(r, f"end_{side}", f"{side}_end"))


def _season_rows(pairs: dict[str, dict]) -> list[dict]:
    """Per-year bands for Aqua, S-NPP and NOAA-20 from the pairs' saved dates (src = first satellite, ref = S-NPP)."""
    a = _dig(pairs.get("Aqua-SNPP"), "years") or {}
    n = _dig(pairs.get("NOAA20-SNPP"), "years") or {}
    a, n = (a if isinstance(a, dict) else {}), (n if isinstance(n, dict) else {})
    rows = []
    for y in sorted({y for y in (*a, *n) if str(y).isdigit()}, key=int):
        ra = a.get(y) if isinstance(a.get(y), dict) else {}
        rn = n.get(y) if isinstance(n.get(y), dict) else {}
        snpp_a, snpp_n = _pair_band(ra, "ref"), _pair_band(rn, "ref")
        bands = {"Aqua": _pair_band(ra, "src"), "SNPP": snpp_a or snpp_n, "NOAA20": _pair_band(rn, "src")}
        if not any(bands.values()):
            continue
        row = {"year": int(y), "bands": bands}
        el = [v for v in (ra.get("eligible"), rn.get("eligible")) if isinstance(v, bool)]
        row["eligible"] = all(el) if el else None
        why = "; ".join(t for t in (_text(ra.get("exclusion"), 200), _text(rn.get("exclusion"), 200)) if t)
        if row["eligible"] is False and why:
            row["why_not_eligible"] = why
        if snpp_a and snpp_n and snpp_a != snpp_n:
            row["snpp_on_noaa20_days"] = snpp_n  # S-NPP dated over the NOAA-20 pair's matched days
        rows.append(row)
    return rows


def _season_punjab(card: dict) -> dict | None:
    dev, src = _report("p04_devcheck.json")
    g = _dig(dev, "G02_punjab_rice")
    if not isinstance(g, dict):
        return None
    _add_source(card, src)
    rows = _season_rows(g)
    gaps = []
    for pair in PAIRS:  # the frozen rule: floor 200, gaps in matched days (change log items 4.1-4.2)
        s = _dig(g, pair, "summary", "floor200_matched")
        if isinstance(s, dict):
            gaps.append({"pair": pair, "eligible_years": _num(s.get("eligible_years")),
                         "max_mid": _num(s.get("max_abs_d_mid")), "max_end": _num(s.get("max_abs_d_end"))})
    gtext = "; ".join(f"{SAT_NAMES[PAIRS[x['pair']][0]]} against S-NPP: {_int(x['max_mid'])} for the middle date and "
                      f"{_int(x['max_end'])} for the end, over {_int(x['eligible_years'])} years" for x in gaps)
    return {
        "title": "Punjab, rice season (15 September–31 December), 2012–2025",
        "badge": "development area (dates seen before the test)",
        "window": WINDOWS["rice"], "rows": rows, "sats": ["Aqua", "SNPP", "NOAA20"],
        "points": [
            {"lead": "Shown, not tested.",
             "text": " Punjab's rice dates were looked at before Protocol P04 was written, and its earlier probe set "
                     "the test's tolerances (3 days for the middle date, 4 for the end). So Punjab only shows what "
                     "the test will look for elsewhere."},
            *([{"lead": "Largest gaps, in matched days", "text": f" (days both satellites were observing): {gtext}."}]
              if gtext else []),
        ],
        "caption": ("Each satellite's band runs from its middle date (dot) to its end date, per year, side by side; "
                    "NOAA-20 starts in 2018. Day passes; standard archive; quality rule and type-0 screen."),
    }


def _g02_groups(data: dict) -> list[tuple[str, str, str, dict]]:
    """(province, window, pair, result) for every pair result in a G02 file, nested or listed."""
    out = []
    container = next((data[k] for k in ("provinces", "results", "groups", "items") if k in data), None)
    if isinstance(container, list):
        for it in container:
            if isinstance(it, dict):
                p = it.get("province") or it.get("area")
                w, pr = _window_key(it.get("window") or it.get("season") or ""), _pair_key(it.get("pair") or "")
                if p and w and pr:
                    out.append((str(p)[:60], w, pr, it))
    elif isinstance(container, dict):
        for p, wins in container.items():
            if not isinstance(wins, dict):
                continue
            wins = wins["windows"] if isinstance(wins.get("windows"), dict) else wins
            for w, pairs in wins.items():
                prov, wk = p, _window_key(w)
                if wk is None and _window_key(p):  # nested window first, then province
                    prov, wk = w, _window_key(p)
                if not wk or not isinstance(pairs, dict):
                    continue
                pairs = pairs["pairs"] if isinstance(pairs.get("pairs"), dict) else pairs
                for pr, res in pairs.items():
                    pk = _pair_key(pr)
                    if pk and isinstance(res, dict):
                        out.append((str(prov)[:60], wk, pk, res))
    return out


G01_CAVEAT = ("This does not rule out the clock, because burning hours may differ between provinces "
              "(the protocol's caveat, which each province's own reading carries).")


def _g01_summary(summary: str | None) -> str | None:
    """The saved summary line drops the caveat the province readings carry; add it back (REVIEW_P04-RUN, R3)."""
    if summary and summary.startswith("Seen outside Punjab: no") and "rule out" not in summary:
        return f"{summary} {G01_CAVEAT}"
    return summary


def _bars_vs_test_text(per: dict, snpp: dict) -> str:
    """Why S-NPP's 2026 bar differs from the test's every-row count shown above it (readiness check, demo-5)."""
    bar = _num((per.get("2026") or {}).get("SNPP")) if isinstance(per, dict) else None
    test = _num(snpp.get("value")) if isinstance(snpp, dict) else None
    if bar is None or test is None or bar == test:
        return ""
    return (f" The bars use this quality rule, so they are lower than the test's counts above, which keep every row: "
            f"S-NPP in 2026 is {_int(bar)} here and {_int(test)} above.")


def _lowest_year_text(rng: dict, lo: float | None) -> str:
    """Say 2019 was the lowest year only when the saved per-year counts show it (REVIEW_FEATURES-1108, F4)."""
    by_year = rng.get("by_year") if isinstance(rng.get("by_year"), dict) else {}
    lowest = [y for y, v in by_year.items() if lo is not None and _num(v) == lo]
    return " 2019, the comparison year the press used, was the lowest of these years." if lowest == ["2019"] else ""


def _g02_outcome(res: dict) -> str | None:
    for k in ("outcome", "status", "result", "holds"):
        v = res.get(k)
        if isinstance(v, bool):
            return "holds" if v else "fails"
        n = _norm(v) if v is not None else ""
        if n in ("holds", "hold", "pass", "passed", "true"):
            return "holds"
        if n in ("fails", "fail", "failed", "false"):
            return "fails"
        if n in ("nottestable", "untestable", "nottested"):
            return "not_testable"
    return None


def _g02_missed(res: dict) -> list[int] | None:
    """Eligible years with either date outside the tolerance, from the result's per-year gaps."""
    ey, yrs = res.get("eligible_years"), res.get("years")
    if not (isinstance(ey, list) and isinstance(yrs, dict)):
        return None
    return [y for y in ey if isinstance(y, int) and isinstance(yrs.get(str(y)), dict) and (
        abs(_num(yrs[str(y)].get("d_mid")) or 0) > 3 or abs(_num(yrs[str(y)].get("d_end")) or 0) > 4)]


def _g02_outside(res: dict) -> tuple[int, int] | None:
    """(years with either date outside the tolerance, eligible years)."""
    missed = _g02_missed(res)
    return None if missed is None else (len(missed), len(res["eligible_years"]))


def _g02_label(pair: str, outcome: str | None, res: dict) -> str:
    saved = _text(res.get("label")) or _text(res.get("reading"))
    if saved:
        # The protocol's "holds" label lists every eligible year, including the misses the rule allows. Name only the
        # matched years, and the outside ones apart (REVIEW_P04-RUN, R4: "or list only the years that matched").
        missed = _g02_missed(res) if outcome == "holds" else None
        if missed:
            ey = [y for y in res["eligible_years"] if isinstance(y, int)]
            kept = [y for y in ey if y not in missed]
            return (f"matched S-NPP's dates within the tolerance in {_years_text(kept)}; {_years_text(missed)} "
                    f"outside, which the rule allows ({len(missed)} of {len(ey)} years)")
        return saved
    ey = res.get("eligible_years")
    n = len(ey) if isinstance(ey, list) else _num(ey)
    k = _num(_first(res, "years_outside_tolerance", "misses", "k"))
    kn = f"{int(k)} of {int(n)} eligible years outside the tolerance" if k is not None and n is not None else None
    if pair == "Aqua-SNPP":
        return {"holds": "the same on the older and newer satellites (Aqua and S-NPP)",
                "fails": "dates differ between Aqua and S-NPP" + (f": {kn}" if kn else ""),
                "not_testable": "not tested: too few years with enough detections"}.get(
            outcome, "outcome not recognised in the result file")
    yrs = _years_text([y for y in ey if isinstance(y, int)]) if isinstance(ey, list) else None
    return {"holds": "NOAA-20 matched S-NPP's dates within the tolerance" + (f" in {yrs}" if yrs else ""),
            "fails": "NOAA-20 did not match S-NPP's dates within the tolerance" + (f" ({kn})" if kn else ""),
            "not_testable": "NOAA-20: not tested"}.get(outcome, "outcome not recognised in the result file")


def _season_tests(data: dict) -> dict:
    groups: dict[tuple[str, str], dict[str, dict]] = {}
    for prov, win, pair, res in _g02_groups(data):
        groups.setdefault((prov, win), {})[pair] = res
    order = {"Sindh": 0, "Khyber Pakhtunkhwa": 1, "Punjab": 2}
    items = []
    for (prov, win), pairs in sorted(groups.items(), key=lambda kv: (kv[0][1] != "rice", order.get(kv[0][0], 9),
                                                                    kv[0][0])):
        labels = []
        for pair in PAIRS:
            if pair in pairs:
                oc = _g02_outcome(pairs[pair])
                labels.append({"pair": pair, "satellites": f"{SAT_NAMES[PAIRS[pair][0]]} and S-NPP",
                               "outcome": oc, "label": _g02_label(pair, oc, pairs[pair]),
                               "reason": _text(pairs[pair].get("reason"), 300) if oc == "not_testable" else None})
        w = WINDOWS[win]
        items.append({"province": prov, "window": w, "title": f"{prov}, {w['name']} ({w['label']})",
                      "rows": _season_rows(pairs), "sats": ["Aqua", "SNPP", "NOAA20"], "labels": labels})
    reading = _first(data, "readings", "reading")
    readings = [r for r in ([reading] if isinstance(reading, str) else reading if isinstance(reading, list) else [])
                if _text(r)]
    return {"state": "result" if items else "unparsed", "items": items,
            "readings": [_text(r, 600) for r in readings][:30],
            "unparsed_note": None if items else ("The G02 result file was found, but its layout was not recognised, "
                                                 "so only its readings are shown; the dates are in the file.")}


def season_card() -> dict:
    card = _card("season")
    card["lede"] = SEASON_DEFINITION
    card["punjab"] = _season_punjab(card)
    data, src = _experiment(P04_TESTS["G02"])
    title = "Sindh, Khyber Pakhtunkhwa and the spring season (frozen test P04 G02)"
    if data is None:
        card["tests"] = {"state": "waiting", "waiting": _waiting("G02"), "title": title}
    else:
        _add_source(card, src)
        card["tests"] = {"title": title} | _season_tests(data)
    card["past_only"] = PAST_ONLY
    card["state"] = "result" if card["punjab"] else "waiting"
    return card


# ---------- 5. verification log ----------
def _rows(items, fields: tuple[str, ...], limit: int = 200) -> list[dict]:
    """The log's entries as plain strings (numbers and dates are kept as written; nothing else is passed on)."""
    out = []
    for it in items if isinstance(items, list) else []:
        if isinstance(it, dict):
            row = {f: _text(None if it.get(f) is None else str(it.get(f)), 1200) for f in fields}
            if any(row.values()):
                out.append(row)
    return out[:limit]


def log_card() -> dict:
    card = _card("log")
    data, src = _report("verification_log.json")
    if data is None:
        card.update(state="missing", text="Not written yet: the verification log (reports/c08/verification_log.json) "
                                          "has not been written.")
        return card
    _add_source(card, src)
    urdu = data.get("urdu_summary_draft") if isinstance(data.get("urdu_summary_draft"), dict) else {}
    utext = _text(urdu.get("text"), 4000)
    card.update(
        state="result", updated=_text(data.get("updated"), 40),
        mistakes=_rows(data.get("mistakes"), ("date", "what", "found_by", "fixed_in", "source")),
        satellite_status=_rows(data.get("satellite_status"), ("fact", "date_read", "source")),
        # Shown only once Hasnain has checked the wording ("approved": true in the log file); a draft is never shown.
        urdu=({"text": utext, "lang": "ur", "dir": "rtl", "note": _text(urdu.get("note"), 600),
               "approved": urdu.get("approved") is True,
               "check": "Draft: Hasnain checks the Urdu wording before it is used."} if utext else None),
    )
    return card


# ---------- all cards ----------
BUILDERS = {"headline": headline_card, "seam": seam_card, "clock": clock_card, "season": season_card, "log": log_card}


def cards() -> dict:
    """Every showcase card, each read fresh from the saved files (a new result file shows on the next load)."""
    return {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "order": list(ORDER),
        "note": "Read from saved result files only; nothing here is computed from detection rows.",
        "cards": {k: _safe(BUILDERS[k], k) for k in ORDER},
    }
