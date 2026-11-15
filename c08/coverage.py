"""Observation coverage example: "Was this area actually observed?"

    python -m c08.coverage probe    # try the access routes once, record exactly what each returned (no secret printed)
    python -m c08.coverage fetch    # bounded download through LP DAAC (needs the Earthdata token in the ignored env file)
    python -m c08.coverage check    # class mapping, counts and overlay alignment against the FIRMS detections

What it is: for one satellite (Aqua MODIS), a bounded area (central and eastern Pakistani Punjab north of 30 N, the
part inside MODIS tile h24v05) and a few real dates, the product's own fire-mask class of every 1 km grid cell:
hotspot detected, usable land with no hotspot detected, cloud, or unknown / not processed.

Source: MYD14A1 Collection 6.1 (MODIS/Aqua Thermal Anomalies/Fire Daily L3 Global 1 km, LP DAAC). It is NASA's own
daily gridding of the Level-2 swath fire masks, on the MODIS sinusoidal grid, so each cell's position is known from
the grid itself. The class codes and QA bits are read from each file's own legend attributes, never assumed, and
are saved in the manifest.

Time support: one UTC day per layer. A cell's class is the product's daily composite of that day's Aqua overpasses;
it is not one pass and not a continuous watch. "Usable land, no hotspot detected" is the instrument's classification,
not proof that nothing burned: small, cool or short burning, and burning between overpasses, is not seen.
Coverage shares are cells of a class divided by the area's land cells that day. They are never used to scale counts.

The Level-2 swath route (MYD14 with MYD03 geolocation) is probed and recorded: MYD03 is served by LAADS, which did not
accept token downloads in this project on 3 Nov 2026 (see `probe`).
"""
from __future__ import annotations

import base64
import hashlib
import json
import sys
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache

import numpy as np

from . import config

DIR = config.DATA / "coverage"
MANIFEST = DIR / "manifest.json"
CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
PRODUCT = {"short_name": "MYD14A1", "version": "061", "platform": "Aqua", "instrument": "MODIS",
           "long_name": "MODIS/Aqua Thermal Anomalies/Fire Daily L3 Global 1km SIN Grid, Collection 6.1",
           "doi": "10.5067/MODIS/MYD14A1.061", "provider": "NASA LP DAAC", "processing": "standard (science-quality archive)"}
TILE = "h24v05"
PERIODS = ("2025-11-01", "2025-08-05")   # first day of two 8-day files: the rice season, and the monsoon
BBOX = (72.6, 30.05, 75.4, 32.6)         # west, south, east, north; cut again by the Punjab polygon
AREA_NAME = "Central and eastern Punjab north of 30°N (the part of Pakistani Punjab inside MODIS tile h24v05)"
R_EARTH, TILE_M, N = 6371007.181, 1111950.5197665, 1200   # MODIS sinusoidal sphere, tile width, 1 km cells per tile
STEP = TILE_M / N
DISPLAY_DEG = 0.01
# Display classes. The product codes each one covers are read from the file legend and checked in `fetch`.
CLASSES = [
    {"key": "fire", "label": "Hotspot detected", "codes": [7, 8, 9]},
    {"key": "clear", "label": "Usable land observation, no hotspot detected", "codes": [5]},
    {"key": "cloud", "label": "Cloud-obscured", "codes": [4]},
    {"key": "unknown", "label": "Unknown, not processed or unavailable", "codes": [0, 1, 2, 6]},
    {"key": "water", "label": "Water or coast (not counted as land)", "codes": [3]},
]
EXPECTED_LEGEND = {0: "missing input", 1: "not processed", 2: "not processed", 3: "non-fire water", 4: "cloud", 5: "non-fire land",
                   6: "unknown", 7: "fire", 8: "fire", 9: "fire"}
QA_SOURCE = ("QA bits 0-1 are the land/water state (0 water, 1 coast, 2 land) and bit 2 is day (1) or night (0), as given in the "
             "MODIS Collection 6 and 6.1 Active Fire Product User's Guide for the Level-3 daily product. The file itself only "
             "declares a bit field with valid range 0-6, which fits; `check` also confirms on the cached files that every "
             "land-class cell (5, 7, 8, 9) carries state 2 and every 'non-fire water' cell carries state 0 or 1 (water or coast).")
NOTES = [
    "A class is the instrument's classification for that UTC day, from Aqua's overpasses only. It is not a continuous watch.",
    "'Usable land, no hotspot detected' does not prove that nothing burned: small, cool or short burning, and burning between overpasses, is not seen.",
    "Cloud-obscured cells are unknown for burning, not zero.",
    "Shares are cells of a class divided by the area's land cells. They are never used to scale detection counts into 'true' activity.",
    "MODIS and VIIRS masks use different codes and confidence rules; this example covers Aqua MODIS only.",
]


def _rowcol(lon, lat):
    """Row and column (fractional) of a point in the tile's 1 km sinusoidal grid."""
    h, v = int(TILE[1:3]), int(TILE[4:6])
    lat_r, lon_r = np.radians(lat), np.radians(lon)
    x, y = R_EARTH * lon_r * np.cos(lat_r), R_EARTH * lat_r
    return ((9 - v) * TILE_M - y) / STEP, (x - (h - 18) * TILE_M) / STEP


def _cell_lonlat(rows, cols):
    h, v = int(TILE[1:3]), int(TILE[4:6])
    y = (9 - v) * TILE_M - (rows + 0.5) * STEP
    x = (h - 18) * TILE_M + (cols + 0.5) * STEP
    lat = np.degrees(y / R_EARTH)
    return np.degrees(x / (R_EARTH * np.cos(np.radians(lat)))), lat


@lru_cache(maxsize=1)
def window() -> dict:
    """The tile rows and columns that cover the box, and which of those cells lie inside Pakistani Punjab."""
    import shapely

    from . import boundaries
    w, s, e, n = BBOX
    rr, cc = [], []
    for lon, lat in ((w, s), (w, n), (e, s), (e, n)):
        r, c = _rowcol(lon, lat)
        rr.append(r), cc.append(c)
    r0, r1 = max(0, int(np.floor(min(rr)))), min(N, int(np.ceil(max(rr))) + 1)
    c0, c1 = max(0, int(np.floor(min(cc)))), min(N, int(np.ceil(max(cc))) + 1)
    rows, cols = np.meshgrid(np.arange(r0, r1), np.arange(c0, c1), indexing="ij")
    lon, lat = _cell_lonlat(rows, cols)
    geom = boundaries.provinces()["Punjab"]
    shapely.prepare(geom)
    inside = shapely.contains_xy(geom, lon, lat) & (lon >= w) & (lon <= e) & (lat >= s) & (lat <= n)
    return {"r0": r0, "r1": r1, "c0": c0, "c1": c1, "inside": inside}


def _load_manifest() -> dict:
    if MANIFEST.is_file():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"schema": "seamline-coverage-1", "product": PRODUCT, "tile": TILE, "bbox_wsen": list(BBOX), "area": AREA_NAME,
            "files": {}, "attempts": []}


def _save_manifest(m: dict) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, indent=1, default=str), encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _cmr(short_name: str, version: str, day: str, extra: dict | None = None) -> list[dict]:
    import requests

    from . import acquire
    w, s, e, n = BBOX
    q = {"short_name": short_name, "version": version, "temporal": f"{day}T00:00:00Z,{day}T23:59:59Z",
         "bounding_box": f"{w},{s},{e},{n}", "page_size": 50} | (extra or {})
    r = acquire._retry(lambda: requests.get(CMR, params=q, timeout=60))
    r.raise_for_status()
    return r.json()["feed"]["entry"]


def _data_url(entry: dict, suffix: str) -> str | None:
    return next((l["href"] for l in entry.get("links", []) if l["href"].startswith("https") and l["href"].endswith(suffix)), None)


def probe(log=print) -> dict:
    """One bounded try of each route. Records status codes and content types only; never the token."""
    from . import acquire, burned_area
    m = _load_manifest()
    tok = burned_area.token()
    out = {"at_utc": _now(), "token_present": bool(tok), "routes": []}
    day = PERIODS[0]
    s = acquire._session()
    for name, short, ver, suffix, why in (
            ("Level-3 daily grid (used)", "MYD14A1", "061", ".hdf", "fire mask and QA on the sinusoidal grid; position known from the grid"),
            ("Level-2 swath fire mask", "MYD14", "061", ".hdf", "per-pass fire mask; has no latitude or longitude arrays of its own"),
            ("Level-2 swath geolocation", "MYD03", "6.1", ".hdf", "the latitude and longitude of every swath pixel; needed to place a Level-2 mask")):
        rec = {"route": name, "product": f"{short} v{ver}", "why": why}
        try:
            entries = _cmr(short, ver, day)
            rec["cmr_granules_found"] = len(entries)
            url = _data_url(entries[0], suffix) if entries else None
            rec["host"] = url.split("/")[2] if url else None
            if url and tok:
                first = s.get(url, headers={"Authorization": f"Bearer {tok}"}, timeout=60, allow_redirects=False, stream=True)
                rec["first_status"] = first.status_code
                loc = first.headers.get("Location", "")
                rec["redirects_to_host"] = loc.split("/")[2] if loc.startswith("http") else None
                target = s.get(loc, timeout=60, stream=True) if loc.startswith("http") else first
                head = next(target.iter_content(8), b"")
                rec["final_status"] = target.status_code
                rec["content_type"] = target.headers.get("Content-Type")
                rec["is_hdf"] = head[:4] in (b"\x0e\x03\x13\x01", b"\x89HDF")
                target.close()
            elif not tok:
                rec["note"] = "no Earthdata token available, so no download was tried"
        except Exception as e:  # noqa: BLE001 - a probe records what happened
            rec["error"] = f"{type(e).__name__}: {str(e)[:200]}"
        out["routes"].append(rec)
        log(json.dumps(rec))
    m["attempts"].append(out)
    _save_manifest(m)
    return out


def _legend(sds) -> dict:
    return {k: (v if isinstance(v, (int, float, str)) else str(v)) for k, v in sds.attributes().items()
            if k.lower() in ("legend", "long_name", "units", "valid_range", "_fillvalue", "description")}


def _check_legend(text: str) -> list[str]:
    """The file's own class list must say what CLASSES assumes, or the download is refused."""
    lines, bad = {}, []
    for ln in str(text).lower().replace(";", "\n").split("\n"):
        head, _, rest = ln.strip().partition(" ")
        if head.isdigit():
            lines[int(head)] = rest
    for code, word in EXPECTED_LEGEND.items():
        if word not in lines.get(code, ""):
            bad.append(f"class {code}: expected '{word}', the file says '{lines.get(code)}'")
    return bad


def fetch(log=print) -> dict:
    """Download each period's tile once from LP DAAC, crop to the area, record class counts, delete the original."""
    import shutil

    from pyhdf.SD import SD, SDC

    from . import acquire, burned_area
    tok = burned_area.token()
    if not tok:
        raise SystemExit("EARTHDATA_TOKEN is missing; add it to the ignored env file first.")
    m = _load_manifest()
    win = window()
    s = acquire._session()
    tmp = DIR / "_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    for start in PERIODS:
        if start in m["files"] and (DIR / m["files"][start]["crop"]).is_file():
            log(f"have {start}")
            continue
        entries = [e for e in _cmr(PRODUCT["short_name"], PRODUCT["version"], start) if f".{TILE}." in e.get("producer_granule_id", "")]
        if not entries:
            raise SystemExit(f"{start}: tile {TILE} was not found in the CMR search")
        url = _data_url(entries[0], ".hdf")
        size = int(float(entries[0].get("granule_size") or 2) * 1e6)
        if shutil.disk_usage(config.DATA).free - size < config.MIN_FREE_DISK_BYTES:
            raise SystemExit("Stopping: the download would leave less than the disk reserve.")
        part = tmp / url.rsplit("/", 1)[1]
        try:
            r = burned_area._download(s, url, tok)
            if r.status_code != 200:
                raise SystemExit(f"{start}: HTTP {r.status_code} from the data host")
            with part.open("wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
            if part.read_bytes()[:4] != b"\x0e\x03\x13\x01":
                raise SystemExit(f"{start}: the reply is not an HDF4 file (a login page or an error was returned)")
            digest = acquire.sha256_file(part)
            sd = SD(str(part), SDC.READ)
            try:
                fm, qa = sd.select("FireMask"), sd.select("QA")
                legend = {"FireMask": _legend(fm), "QA": _legend(qa) | {"bits": QA_SOURCE}}
                g = sd.attributes()
                a, q = fm.get(), qa.get()
            finally:
                sd.end()
            bad = _check_legend(legend["FireMask"].get("legend", ""))
            if bad:
                raise SystemExit(f"{start}: the file's class legend is not the one this code maps: {bad}")
            dates = [d for d in str(g.get("Dates", "")).split() if len(d) == 10]
            if a.shape != (len(dates) or a.shape[0], N, N):
                raise SystemExit(f"{start}: unexpected FireMask shape {a.shape} for dates {dates}")
            if not dates:
                d0 = date.fromisoformat(start)
                dates = [(d0 + timedelta(days=i)).isoformat() for i in range(a.shape[0])]
            crop = f"{PRODUCT['short_name']}_{start}_{TILE}_aoi.npz"
            np.savez_compressed(DIR / crop, firemask=a[:, win["r0"]:win["r1"], win["c0"]:win["c1"]],
                                qa=q[:, win["r0"]:win["r1"], win["c0"]:win["c1"]])
            m["files"][start] = {"period_start": start, "dates": dates, "granule": part.name, "url": url, "bytes": part.stat().st_size,
                                 "sha256": digest, "retrieved_utc": acquire._now_utc(), "crop": crop,
                                 "crop_sha256": hashlib.sha256((DIR / crop).read_bytes()).hexdigest(),
                                 "window": {k: int(win[k]) for k in ("r0", "r1", "c0", "c1")}, "legend": legend,
                                 "global_attributes": {k: str(v)[:300] for k, v in g.items() if k in ("Dates", "MaxT21", "FirePix", "CloudPix", "MissingPix", "ProcessVersionNumber")},
                                 "original": "deleted after cropping (disk space); the SHA-256 above is of the original file",
                                 "licence": "NASA EOSDIS data: open use; cite the product DOI"}
            _save_manifest(m)
            log(f"ok {start}: {part.stat().st_size / 1e6:.2f} MB, dates {dates[0]} to {dates[-1]}")
        finally:
            part.unlink(missing_ok=True)
    m["days"] = _day_stats(m)
    m["built_utc"] = _now()
    _save_manifest(m)
    return m


@lru_cache(maxsize=4)
def _arrays(start: str):
    m = _load_manifest()
    z = np.load(DIR / m["files"][start]["crop"])
    return z["firemask"], z["qa"]


UNKNOWN_CODES = (0, 1, 2, 6)


def _land_day(fm_day: np.ndarray, qa_day: np.ndarray) -> np.ndarray:
    """Land cells of the area on one day: the QA land/water state says land (2). Cells the product could not class
    (missing input, not processed, unknown) stay in, so that they are counted as unknown rather than dropped."""
    state = qa_day & 0b11
    return window()["inside"] & ((state == 2) | np.isin(fm_day, UNKNOWN_CODES))


def _day_stats(m: dict) -> list[dict]:
    out = []
    for start, f in sorted(m["files"].items()):
        fm, qa = _arrays(start)
        inside = window()["inside"]
        for i, day in enumerate(f["dates"]):
            a, land = fm[i], _land_day(fm[i], qa[i])
            n_land = int(land.sum())
            counts = {c["key"]: int((np.isin(a, c["codes"]) & land).sum()) for c in CLASSES if c["key"] != "water"}
            counts["water"] = int((inside & ~land).sum())      # water and coast cells: not land, left out of the shares
            out.append({"date": day, "period_start": start, "layer": i, "cells_in_area": int(inside.sum()), "land_cells": n_land,
                        "counts": counts, "codes_seen": sorted(int(v) for v in np.unique(a[inside])),
                        "observed_share": round((counts["fire"] + counts["clear"]) / n_land, 4) if n_land else None,
                        "cloud_share": round(counts["cloud"] / n_land, 4) if n_land else None,
                        "unknown_share": round(counts["unknown"] / n_land, 4) if n_land else None,
                        "sums_to_land": counts["fire"] + counts["clear"] + counts["cloud"] + counts["unknown"] == n_land})
    return out


def check(log=print) -> dict:
    """Class sums, and overlay alignment: do FIRMS's Aqua detections of the same UTC day fall on (or next to) hotspot cells?"""
    from . import analysis
    m = _load_manifest()
    if not m["files"]:
        raise SystemExit("Nothing fetched yet. Run: python -m c08.coverage fetch")
    d = analysis.detections()
    win = window()
    w, s, e, n = BBOX
    aqua = d[(d["platform"] == "Aqua") & (d["stream"] == "standard") & d["longitude"].between(w, e) & d["latitude"].between(s, n)]
    rows = []
    for day in m["days"]:
        fm, _ = _arrays(day["period_start"])
        a = fm[day["layer"]]
        pts = aqua[aqua["date_utc"] == np.datetime64(day["date"])]
        r, c = _rowcol(pts["longitude"].to_numpy(), pts["latitude"].to_numpy())
        r, c = np.floor(r).astype(int) - win["r0"], np.floor(c).astype(int) - win["c0"]
        ok = (r >= 0) & (r < a.shape[0]) & (c >= 0) & (c < a.shape[1])
        r, c = r[ok], c[ok]
        keep = win["inside"][r, c]
        r, c = r[keep], c[keep]
        fire = np.isin(a, (7, 8, 9))
        exact = int(fire[r, c].sum())
        pad = np.pad(fire, 1)
        near = int(sum(pad[ri:ri + 3, ci:ci + 3].any() for ri, ci in zip(r, c)))
        rows.append({"date": day["date"], "firms_aqua_detections_in_area": int(len(r)), "on_a_hotspot_cell": exact,
                     "on_or_next_to_a_hotspot_cell": near, "hotspot_cells": day["counts"]["fire"],
                     "share_on_or_next": round(near / len(r), 3) if len(r) else None, "sums_to_land": day["sums_to_land"]})
        log(json.dumps(rows[-1]))
    qa_ok = True
    for start in m["files"]:
        fm, qa = _arrays(start)
        state = qa & 0b11
        inside = np.broadcast_to(window()["inside"], fm.shape)
        water_ok = bool(np.isin(state[(fm == 3) & inside], (0, 1)).all())
        land_ok = bool((state[np.isin(fm, (5, 7, 8, 9)) & inside] == 2).all())
        qa_ok = qa_ok and water_ok and land_ok
        log(f"QA land/water state against classes, {start}: water-class cells state 0 or 1: {water_ok}; land-class cells state 2: {land_ok}")
    tot = sum(x["firms_aqua_detections_in_area"] for x in rows)
    near = sum(x["on_or_next_to_a_hotspot_cell"] for x in rows)
    res = {"checked_utc": _now(), "rows": rows, "detections": tot, "on_or_next_to_a_hotspot_cell": near,
           "share": round(near / tot, 4) if tot else None, "all_days_sum_to_land": all(x["sums_to_land"] for x in rows),
           "qa_state_matches_classes": qa_ok, "qa_bits": QA_SOURCE,
           "what": "FIRMS MCD14ML Aqua detections (standard archive, every confidence and type) of the same UTC day, placed on the "
                   "MYD14A1 grid: the share that falls on a cell classed hotspot, or on one of its 8 neighbours (the swath pixel "
                   "centre and the grid cell centre differ by up to about a cell)",
           "pass_rule": "at least 90% on or next to a hotspot cell, and every day's classes sum to the land cells"}
    res["passed"] = bool(res["all_days_sum_to_land"] and qa_ok and (res["share"] or 0) >= 0.9)
    m["verification"] = res
    _save_manifest(m)
    log(f"alignment {near}/{tot} = {res['share']}; sums ok: {res['all_days_sum_to_land']}; passed: {res['passed']}")
    return res


def summary() -> dict:
    """What the app shows: the example's days and shares, or the exact reason it is not available."""
    m = _load_manifest()
    last = m["attempts"][-1] if m.get("attempts") else None
    if not m.get("files") or not m.get("days"):
        why = "No fire-mask files are cached. The layer needs gridded fire masks with QA (MYD14A1 from LP DAAC, with an Earthdata token); hotspot CSV files cannot supply it."
        return {"available": False, "reason": why, "last_attempt": last, "how": "python -m c08.coverage probe, then python -m c08.coverage fetch"}
    v = m.get("verification")
    return {"available": True, "product": m["product"], "tile": m["tile"], "area": m["area"], "bbox_wsen": m["bbox_wsen"],
            "classes": [{"key": c["key"], "label": c["label"], "product_codes": c["codes"]} for c in CLASSES],
            "time_support": "One UTC day per layer: the product's daily composite of Aqua's overpasses that day (not one pass, not a continuous watch).",
            "denominator": "That day's land cells of the area on the 1 km MODIS grid (QA land/water state 'land'; cells the product could "
                           "not class stay in, as unknown). Water and coast cells are left out.",
            "days": m["days"], "notes": NOTES, "verification": v, "verified": bool(v and v.get("passed")),
            "files": [{k: f[k] for k in ("period_start", "granule", "sha256", "retrieved_utc", "bytes")} for f in m["files"].values()],
            "legend_from_file": next(iter(m["files"].values()))["legend"], "manifest": "data/coverage/manifest.json",
            "last_attempt": last, "level2_route": _l2_note(last), "display_cell_degrees": DISPLAY_DEG}


def _l2_note(last: dict | None) -> str:
    if not last:
        return "The Level-2 swath route was not probed in this copy."
    geo = next((r for r in last["routes"] if r["product"].startswith("MYD03")), None)
    if geo and geo.get("is_hdf"):
        return (f"Per-pass (Level-2 swath) masks: at the last probe ({last['at_utc']}) both the swath fire mask (MYD14, LP DAAC) and "
                "its geolocation file (MYD03, LAADS cloud) downloaded with the token, so that route is open. It is not built yet: "
                "each pass needs a 39 MB geolocation file and swath-to-grid resampling. This example uses NASA's own daily grid "
                "instead, and says so in its time support.")
    return ("Per-pass (Level-2 swath) masks were not used: the swath fire mask has no latitude and longitude of its own, and its "
            f"geolocation file (MYD03, LAADS) did not download at the last probe ({last['at_utc']}): "
            f"{json.dumps({k: geo.get(k) for k in ('first_status', 'final_status', 'content_type', 'is_hdf', 'error', 'note') if geo and k in geo})}.")


def grid(key: str) -> dict:
    """One day's classes on a regular 0.01 degree display grid (nearest cell), for drawing over the map."""
    m = _load_manifest()
    day = next((d for d in m.get("days", []) if d["date"] == key), None)
    if day is None:
        return {"available": False, "reason": f"No cached fire mask for {key}."}
    fm, qa = _arrays(day["period_start"])
    a, win = fm[day["layer"]], window()
    land = _land_day(a, qa[day["layer"]])
    w, s, e, n = BBOX
    lons = np.arange(w + DISPLAY_DEG / 2, e, DISPLAY_DEG)
    merc = lambda v: np.log(np.tan(np.pi / 4 + np.radians(v) / 2))  # noqa: E731
    rows_n = int(round((n - s) / DISPLAY_DEG))
    edges = np.linspace(merc(n), merc(s), rows_n + 1)
    lats = np.degrees(2 * np.arctan(np.exp((edges[:-1] + edges[1:]) / 2)) - np.pi / 2)   # row centres, evenly spaced in Web Mercator
    lon, lat = np.meshgrid(lons, lats)
    r, c = _rowcol(lon, lat)
    r, c = np.floor(r).astype(int) - win["r0"], np.floor(c).astype(int) - win["c0"]
    ok = (r >= 0) & (r < a.shape[0]) & (c >= 0) & (c < a.shape[1])
    out = np.zeros(lon.shape, dtype=np.uint8)            # 0 = outside the area
    rr, cc = r[ok], c[ok]
    cls = np.zeros(rr.shape, dtype=np.uint8)
    vals, ins, ld = a[rr, cc], win["inside"][rr, cc], land[rr, cc]
    for i, cdef in enumerate(CLASSES, start=1):
        if cdef["key"] == "water":
            cls[ins & ~ld] = i
        else:
            cls[np.isin(vals, cdef["codes"]) & ins & ld] = i
    out[ok] = cls
    return {"available": True, "date": key, "bbox_wsen": [w, s, e, n], "width": int(out.shape[1]), "height": int(out.shape[0]),
            "cell_degrees": DISPLAY_DEG, "classes": [c["key"] for c in CLASSES], "row_order": "north to south",
            "data_base64": base64.b64encode(out.tobytes()).decode("ascii"),
            "note": "Nearest 1 km grid cell for each display cell (0.01 degrees wide; rows evenly spaced in Web Mercator so the picture "
                    "sits exactly on the map). Counts and shares are computed on the 1 km grid, not on this picture."}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["probe"]:
        probe()
    elif argv[:1] == ["fetch"]:
        fetch()
    elif argv[:1] == ["check"]:
        return 0 if check()["passed"] else 1
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
