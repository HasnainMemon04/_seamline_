"""Read-only, hash-checked 2026+ cached observations. See CURRENT_RECORD_CONTRACT.md.

This module never fits, rebuilds the historical table, or executes an experiment.
Source support is a cached acquisition period, not clear-sky observation exposure.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
from functools import lru_cache

import numpy as np
import pandas as pd

from . import acquire, boundaries, config, ingest, series

SCHEMA = "c08-current-record-1"
FIRST_YEAR = 2026
PLATFORMS = ("Terra", "Aqua", "SNPP", "NOAA20", "NOAA21")
KINDS = ("firms_api_csv", "firms_nrt_7d_region")
API_SOURCES = {
    "VIIRS_SNPP_SP": ("SNPP_NRT", "standard"),
    "VIIRS_SNPP_NRT": ("SNPP_NRT", "nrt"),
    "VIIRS_NOAA20_SP": ("NOAA20_NRT", "standard"),
    "VIIRS_NOAA20_NRT": ("NOAA20_NRT", "nrt"),
    "VIIRS_NOAA21_NRT": ("NOAA21_NRT", "nrt"),
}
BRIDGE = config.EXPERIMENTS / "P04_G03_bridge_2026" / "result.json"
ROW_KEY = ["platform", "time_utc", "latitude", "longitude", "version"]


class ContinuityError(ValueError):
    """A cached input cannot substantiate the current-record contract."""


def _iso(t):
    return pd.Timestamp(t).strftime("%Y-%m-%d")


def _stat(path):
    if not path.is_file():
        raise ContinuityError(f"Cached current-record input missing: {path.name}")
    s = path.stat()
    return (str(path), s.st_size, s.st_mtime_ns)


def _missing_path():
    dated = sorted((config.ROOT / "research" / "metadata").glob("provider_missing_dates_????-??-??.json"))
    return dated[-1] if dated else series.MISSING_DATES


def _signature():
    """A changed manifest, source, boundary, missing list or saved bridge reloads atomically."""
    blob = config.MANIFEST.read_bytes()
    manifest = json.loads(blob)
    paths = [config.ROOT / e["path"] for e in manifest["files"].values() if e.get("kind") in KINDS]
    paths += [boundaries.FULL, _missing_path(), BRIDGE]
    filters = (config.MODIS_MIN_CONFIDENCE, tuple(config.VIIRS_KEEP_CONFIDENCE), SCHEMA)
    return (hashlib.sha256(blob).hexdigest(), tuple(_stat(p) for p in sorted(set(paths))), filters)


def _read_entry(e, root):
    path = root / e["path"]
    if not path.is_file() or acquire.sha256_file(path) != e.get("sha256"):
        raise ContinuityError(f"{e['id']}: cached file missing or SHA-256 differs from manifest")
    blob = path.read_bytes()
    try:
        raw = pd.read_csv(io.BytesIO(blob), dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except pd.errors.EmptyDataError:
        raw = pd.DataFrame(columns=[*ingest.REQUIRED, "bright_ti4", "bright_ti5"])
    if "rows" in e and len(raw) != e["rows"]:
        raise ContinuityError(f"{e['id']}: row count differs from manifest")
    if e["kind"] == "firms_api_csv":
        if e["source"] not in API_SOURCES:
            raise ContinuityError(f"{e['id']}: unsupported area-API source")
        key, stream = API_SOURCES[e["source"]]
        lo = pd.Timestamp(e["start"])
        hi = lo + pd.Timedelta(days=int(e["days"]) - 1)
        # Distinct boxes never silently share a delivery family.
        family = ("api", e["source"], tuple(e.get("bbox", [])))
    else:
        key, stream = e["source"], "nrt"
        lo, hi = e.get("min_acq_date"), e.get("max_acq_date")
        lo, hi = (pd.Timestamp(lo), pd.Timestamp(hi)) if lo and hi else (None, None)
        family = ("snapshot", e["id"])
    if key not in ingest.EXPECTED_PLATFORMS:
        raise ContinuityError(f"{e['id']}: unsupported satellite source")
    try:
        frame, audit = ingest.parse_frame(raw, source=key, source_id=e["id"], stream=stream, file_year=None)
    except (ingest.IngestError, KeyError) as exc:
        raise ContinuityError(f"{e['id']}: invalid FIRMS schema: {exc}") from exc
    # A format change must fail visibly instead of presenting discarded data as no activity.
    fatal = ("bad_platform", "bad_time", "bad_confidence", "bad_daynight", "bad_version", "bad_type")
    if any(audit["rejected"][k] for k in fatal):
        raise ContinuityError(f"{e['id']}: rows fail platform/time/confidence/type format contract")
    frame["date_utc"] = frame["time_utc"].dt.tz_localize(None).dt.floor("D")
    frame["has_type"] = "type" in raw.columns
    if lo is not None and len(frame) and not frame.date_utc.between(lo, hi).all():
        raise ContinuityError(f"{e['id']}: acquisition dates outside recorded cached support")
    info = {k: e.get(k) for k in ("id", "path", "sha256", "kind", "source", "retrieved_utc", "bbox")}
    for k in ("license", "product", "doi", "server_last_modified", "bytes", "url_redacted"):
        if k in e:
            info[k] = e[k]
    if e["kind"] == "firms_nrt_7d_region":
        info["url"] = e.get("url")  # public regional URL; API credentials are never copied
    info.update(stream=stream, has_type="type" in raw.columns, declared_start=_iso(lo) if lo is not None else None,
                declared_end=_iso(hi) if hi is not None else None, sha256_matches_manifest=True, audit=audit,
                observed_acquisition_start=_iso(frame.date_utc.min()) if len(frame) else None,
                observed_acquisition_end=_iso(frame.date_utc.max()) if len(frame) else None)
    return frame, info, family, sorted(ingest.EXPECTED_PLATFORMS[key])


def _build(manifest, root, assign, missing_rows, bridge):
    """Pure read-only builder; injectable geographic assignment enables small isolated tests."""
    entries = [dict(e, id=fid) for fid, e in sorted(manifest["files"].items()) if e.get("kind") in KINDS]
    frames, files, candidates = {}, [], {}
    for e in entries:
        f, info, family, platforms = _read_entry(e, root)
        frames[e["id"]] = f
        files.append(info)
        if info["declared_start"] is None:
            continue  # An empty snapshot without acquisition bounds certifies no supported period.
        dates = pd.date_range(info["declared_start"], info["declared_end"], freq="D")
        dates = dates[dates.year >= FIRST_YEAR]
        for mo in sorted(set(dates.to_period("M"))):
            mdays = set(dates[dates.to_period("M") == mo])
            for p in platforms:
                key = (mo, p, family)
                c = candidates.setdefault(key, {"month": str(mo), "platform": p, "family": family,
                                               "stream": info["stream"], "entries": [], "dates": set()})
                c["entries"].append(info)
                c["dates"].update(mdays)
    by_month = {}
    for (mo, p, _), c in candidates.items():
        full_standard = c["stream"] == "standard" and len(c["dates"]) == mo.days_in_month
        rank = (full_standard, len(c["dates"]), c["stream"] == "standard", c["family"][0] == "api",
                max(e.get("retrieved_utc") or "" for e in c["entries"]), str(c["family"]))
        if (mo, p) not in by_month or rank > by_month[(mo, p)][0]:
            by_month[(mo, p)] = (rank, c)

    missing = {}
    for r in missing_rows:
        p = series.PROVIDER_NAMES.get(r.get("satellite"))
        if p:
            missing.setdefault((p, str(r.get("stream", "")).lower()), set()).add(pd.Timestamp(r["date"]))
    selected, plans = [], {}
    for (mo, p), (_, c) in sorted(by_month.items()):
        # On an overlapping request date, one deterministic newest delivery owns that date.
        owners = {}
        for info in sorted(c["entries"], key=lambda e: (e.get("retrieved_utc") or "", e["id"])):
            for t in pd.date_range(info["declared_start"], info["declared_end"]):
                if t.to_period("M") == mo:
                    owners[t] = info["id"]
        parts = []
        for fid in sorted(set(owners.values())):
            f = frames[fid]
            owned_dates = [t for t, owner in owners.items() if owner == fid]
            keep = f["platform"].eq(p) & f["date_utc"].isin(owned_dates)
            parts.append(f[keep])
        f = pd.concat(parts, ignore_index=True).drop_duplicates(ROW_KEY) if parts else pd.DataFrame()
        if len(f):
            selected.append(f)
        all_dates = set(pd.date_range(mo.start_time.normalize(), mo.end_time.normalize()))
        declared = c["dates"]
        no_rows = declared - set(f["date_utc"]) if len(f) else declared
        listed = declared & missing.get((p, c["stream"]), set())
        has_type = all(e["has_type"] for e in c["entries"])
        flags = []
        if len(declared) < mo.days_in_month:
            flags.append("partial_period")
        if c["stream"] != "standard" or not has_type:
            flags.append("nrt_untyped" if c["stream"] == "nrt" and not has_type else "incompatible_processing_or_type")
        if listed:
            flags.append("provider_missing_days")
        if declared and declared <= listed:
            flags.append("no_usable_support")
        if len(no_rows) == len(declared):
            flags.append("no_platform_rows")
        elif no_rows:
            flags.append("no_platform_rows_days")
        plan = {"month": str(mo), "platform": p, "stream": c["stream"],
                "type_screen": "type0" if has_type else "untyped", "flags": flags,
                "status": ";".join(flags) if flags else "complete_standard_type0",
                "source_ids": sorted(set(owners.values())),
                "declared_start": _iso(min(declared)), "declared_end": _iso(max(declared)),
                "declared_days": len(declared), "days_in_month": mo.days_in_month,
                "not_listed_missing_days": len(declared - listed),
                "declared_dates": [_iso(t) for t in sorted(declared)],
                "unrequested_dates": [_iso(t) for t in sorted(all_dates - declared)],
                "missing_dates": [_iso(t) for t in sorted(listed)],
                "no_row_dates": [_iso(t) for t in sorted(no_rows)],
                "exposure": "unknown; cached support is not clear-sky exposure"}
        plans[(mo, p)] = plan
    if selected:
        d = pd.concat(selected, ignore_index=True).drop_duplicates(ROW_KEY)
        d["province"] = assign(d.longitude.to_numpy(float), d.latitude.to_numpy(float))
        d = d[d["province"].ne("")].copy()
        d["year"], d["month"] = d.time_utc.dt.year, d.time_utc.dt.month
        d = d.astype(ingest.COLUMNS).sort_values(["time_utc", "platform"]).reset_index(drop=True)
    else:
        d = pd.DataFrame({c: pd.Series(dtype=t) for c, t in ingest.COLUMNS.items()})
        d["has_type"] = pd.Series(dtype=bool)
    return {"rows": d, "plans": plans, "files": files, "bridge": bridge}


@lru_cache(maxsize=1)
def _cached(signature):
    manifest = json.loads(config.MANIFEST.read_text(encoding="utf-8"))
    be = manifest["files"].get("boundaries/pak_adm1.geojson")
    if not be or acquire.sha256_file(boundaries.FULL) != be["sha256"]:
        raise ContinuityError("Province boundary SHA-256 differs from manifest")
    # Do not reuse an older geometry after a manifest/input refresh.
    boundaries.provinces.cache_clear()
    missing_path = _missing_path()
    missing = json.loads(missing_path.read_text(encoding="utf-8"))
    saved = json.loads(BRIDGE.read_text(encoding="utf-8"))
    result = _build(manifest, config.ROOT, boundaries.province_of, missing, saved)
    result["input_identity"] = {"manifest_sha256": signature[0], "boundary_sha256": be["sha256"],
                                "filters": {"MODIS_min_confidence": config.MODIS_MIN_CONFIDENCE,
                                            "VIIRS_keep_confidence": list(config.VIIRS_KEEP_CONFIDENCE),
                                            "typed_rows": "type0", "untyped_rows": "retained and flagged"},
                                "missing_days_path": missing_path.relative_to(config.ROOT).as_posix(),
                                "missing_days_sha256": acquire.sha256_file(missing_path),
                                "bridge_path": BRIDGE.relative_to(config.ROOT).as_posix(),
                                "bridge_sha256": acquire.sha256_file(BRIDGE)}
    if _signature() != signature:
        raise ContinuityError("Current-record inputs changed during loading; retry the request")
    return result


def _bundle():
    return _cached(_signature())


def clear_cache():
    _cached.cache_clear()


def rows() -> pd.DataFrame:
    """All validated Pakistan observations from the deterministic platform/month plan."""
    return _bundle()["rows"].copy()


def _select(d, region, bbox, years, passes):
    if not passes or len(set(passes)) != len(passes) or any(dn not in ("D", "N") for dn in passes):
        raise ContinuityError("Choose day, night, or both passes once each")
    mask = d["quality_pass"] & d["type0"] & d["daynight"].isin(passes)
    if bbox is not None:
        if len(bbox) != 4:
            raise ContinuityError("A box needs west, south, east, north")
        w, s, e, n = map(float, bbox)
        if not all(np.isfinite([w, s, e, n])) or not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
            raise ContinuityError("Use west < east and south < north in degrees")
        mask &= d.longitude.between(w, e) & d.latitude.between(s, n)
    elif region and region != "Pakistan":
        mask &= d.province.eq(region)
    if years is not None:
        mask &= d.year.between(int(years[0]), int(years[1]))
    return d[mask].copy()


def selection(region=None, bbox=None, years=None, passes=("D", "N")) -> pd.DataFrame:
    """Quality observations, with type 0 where available; defaults retain both passes."""
    return _select(_bundle()["rows"], region, bbox, years, passes)


def monthly(region=None, bbox=None, passes=("D", "N")) -> pd.DataFrame:
    """Cached-period counts and observed/reference-equivalent H, with explicit unsafe flags."""
    b = _bundle()
    d = _select(b["rows"], region, bbox, None, passes)
    last = max((mo.year for mo, _ in b["plans"]), default=FIRST_YEAR)
    index = pd.date_range(f"{FIRST_YEAR}-01-01", f"{last}-12-01", freq="MS", name="month")
    counts = d.groupby([d.date_utc.dt.to_period("M"), "platform", "daynight"], observed=True).size()
    out = []
    for t in index:
        mo, row = t.to_period("M"), {}
        for p in PLATFORMS:
            plan = b["plans"].get((mo, p))
            available = plan is not None and "no_platform_rows" not in plan["flags"]
            for dn in ("D", "N"):
                row[f"{p}_{dn}"] = int(counts.get((mo, p, dn), 0)) if available and dn in passes else np.nan
            row[f"{p}_status"] = plan["status"] if plan else "outside_record"
            row[f"{p}_stream"] = plan["stream"] if plan else None
            row[f"{p}_type_screen"] = plan["type_screen"] if plan else None
            row[f"{p}_declared_days"] = plan["declared_days"] if plan else 0
            row[f"{p}_missing_days"] = len(plan["missing_dates"]) if plan else 0
            row[f"{p}_no_row_days"] = len(plan["no_row_dates"]) if plan else 0
            row[f"{p}_source_ids"] = plan["source_ids"] if plan else []
        total = lambda p: sum(row[f"{p}_{dn}"] for dn in passes)
        flags = lambda p: ";".join(b["plans"].get((mo, p), {}).get("flags", ["outside_record"]))
        row["aqua"], row["aqua_flag"] = total("Aqua"), flags("Aqua")
        row["naive_snpp"], row["naive_snpp_flag"] = total("SNPP"), flags("SNPP")
        values = [total(p) for p in ("SNPP", "NOAA20")]
        row["naive"] = sum(v for v in values if pd.notna(v)) if any(pd.notna(v) for v in values) else np.nan
        row["naive_flag"] = ";".join(sorted(set(flags("SNPP").split(";") + flags("NOAA20").split(";")) - {""}))
        ref = "SNPP" if t < pd.Timestamp("2026-11-01") else "NOAA20"
        support = copy.deepcopy(b["plans"].get((mo, ref), {"month": str(mo), "platform": ref,
                                                       "flags": ["outside_record"], "status": "outside_record"}))
        row["H"] = row["H_lo"] = row["H_hi"] = np.nan
        if ref == "SNPP":
            if "no_usable_support" not in support["flags"]:
                row["H"] = row["H_lo"] = row["H_hi"] = total(ref)
            row["H_source"] = "observed S-NPP (cached current supplement)"
        else:
            saved = b["bridge"]
            primary = saved.get("bridge", {}).get("primary", {}).get("none", {})
            approved = (region == "Punjab" and bbox is None and str(saved.get("status", "")).lower() == "pass"
                        and support.get("stream") == "nrt" and support.get("type_screen") == "untyped"
                        and all(np.isfinite(primary.get(k, np.nan)) for k in ("k_day", "k_night")))
            if approved and "no_usable_support" not in support["flags"]:
                row["H"] = sum(row[f"NOAA20_{dn}"] * primary["k_day" if dn == "D" else "k_night"] for dn in passes)
                row["H_source"] = "NOAA-20 converted to S-NPP equivalent (frozen G03 Punjab no-type bridge)"
                support["bridge"] = "saved G03 primary none; no fit; interval unavailable"
            else:
                support["flags"] = [*support["flags"], "unsupported_bridge"]
                row["H_source"] = "unavailable (requires passing Punjab-only NOAA-20 no-type NRT bridge and usable support)"
        row["H_flag"] = ";".join(support["flags"])
        row["H_support"] = support
        out.append(row)
    return pd.DataFrame(out, index=index)


def metadata() -> dict:
    """Self-contained input/support identities; retrieval time is never acquisition time."""
    b = _bundle()
    files = copy.deepcopy(b["files"])
    selected = [copy.deepcopy(v) for _, v in sorted(b["plans"].items())]
    for f in files:
        f["selected_for_months"] = sorted({p["month"] for p in selected if f["id"] in p["source_ids"]})
        f["selected_for_record"] = bool(f["selected_for_months"])
    starts = [v["declared_start"] for v in selected]
    ends = [v["declared_end"] for v in selected]
    api_ends = [f["declared_end"] for f in files if f["kind"] == "firms_api_csv" and f["declared_end"]]
    saved = b["bridge"]
    return {"schema": SCHEMA, "acquisition_start": min(starts) if starts else None,
            "acquisition_end": max(ends) if ends else None, "api_acquisition_end": max(api_ends) if api_ends else None,
            "latest_observed_acquisition_utc": b["rows"].time_utc.max().isoformat() if len(b["rows"]) else None,
            "latest_retrieved_utc": max((f.get("retrieved_utc") or "" for f in files), default=None),
            "supported_years": sorted({int(v["month"][:4]) for v in selected}),
            "selected_months": selected, "files": files, "input_identity": copy.deepcopy(b.get("input_identity", {})),
            "bridge": {"status": saved.get("status"), "area": "Punjab", "after": "2026-10",
                       "factors": saved.get("bridge", {}).get("primary", {}).get("none"),
                       "no_new_fit": True, "uncertainty_interval": "unavailable"},
            "limitations": ["Hotspot support is not clear-sky exposure; no detection is not no fire.",
                            "Partial periods are observed subtotals, never completed or proportionally filled.",
                            "NRT/untyped counts are incompatible with historical standard type-0 comparisons.",
                            "Daily saved-factor use is experimental; daily accuracy and uncertainty are untested.",
                            "No global-platform rows means unavailable, never observed zero."]}


def daily(region=None, bbox=None, year=FIRST_YEAR, month=1, passes=("D", "N"), model="M2") -> dict:
    """Observed daily support and a labelled, untested daily use of saved monthly factors.

    Complete-pass daily totals intentionally exclude provider-missing and unknown-pass
    days. The monthly observed subtotal retains actual cached rows and is supplied
    alongside the daily total, so an excluded day never silently becomes zero.
    """
    from . import analysis  # drawing/link helpers only; never calibration or experiment execution

    try:
        year, month = int(year), int(month)
        if year < FIRST_YEAR or not 1 <= month <= 12:
            raise ValueError
        mo = pd.Period(f"{year}-{month:02d}", freq="M")
    except (ValueError, TypeError):
        raise ContinuityError("Choose a current-record year and month") from None
    b = _bundle()
    days = pd.date_range(mo.start_time.normalize(), mo.end_time.normalize())
    q = _select(b["rows"], region, bbox, (year, year), ("D", "N"))
    seen = b["rows"][b["rows"].date_utc.isin(days)]
    present = set(zip(seen.platform.astype(str), seen.date_utc, seen.daynight.astype(str)))
    count = q.groupby(["platform", "date_utc", "daynight"], observed=True).size()
    w = monthly(region, bbox, passes)
    monthly_row = w.loc[mo.start_time] if mo.start_time in w.index else None
    all_w = w if tuple(passes) == ("D", "N") else monthly(region, bbox, ("D", "N"))
    all_monthly_row = all_w.loc[mo.start_time] if mo.start_time in all_w.index else None
    labels = dict(analysis.DAILY_LABELS, NOAA21="NOAA-21 VIIRS (separate observations)")
    out = []
    for p in PLATFORMS:
        plan = b["plans"].get((mo, p))
        declared = set(plan["declared_dates"]) if plan else set()
        missing = set(plan["missing_dates"]) if plan else set()
        r = {"key": p, "label": labels[p], "values": [], "D": [], "N": [], "status": [],
             "at_least": [], "empty_everywhere": [[] for _ in days], "passes_needed": ["D", "N"],
             "support": copy.deepcopy(plan)}
        for t in days:
            date = _iso(t)
            status = "outside_record" if date not in declared else "provider_missing" if date in missing else "ok"
            dd, nn = None, None
            if status == "ok":
                dd = int(count.get((p, t, "D"), 0)) if (p, t, "D") in present else None
                nn = int(count.get((p, t, "N"), 0)) if (p, t, "N") in present else None
                status = "nothing_anywhere" if dd is None and nn is None else "pass_missing" if dd is None or nn is None else "ok"
            known = [v for v in (dd, nn) if v is not None]
            r["D"].append(dd)
            r["N"].append(nn)
            r["values"].append(sum(known) if status == "ok" else None)
            r["at_least"].append(sum(known) if status == "pass_missing" and sum(known) > 0 else None)
            r["status"].append(status)
        out.append(r)
    ref = "SNPP" if mo < pd.Period("2026-11", freq="M") else "NOAA20"
    src = next(r for r in out if r["key"] == ref)
    support = copy.deepcopy(monthly_row.H_support) if monthly_row is not None else {"flags": ["outside_record"]}
    factors = b["bridge"].get("bridge", {}).get("primary", {}).get("none", {})
    bridge_ok = (ref == "SNPP" or (region == "Punjab" and bbox is None
                 and str(b["bridge"].get("status", "")).lower() == "pass"
                 and support.get("stream") == "nrt" and support.get("type_screen") == "untyped"
                 and all(np.isfinite(factors.get(k, np.nan)) for k in ("k_day", "k_night"))))
    h = {"key": "H", "label": labels["H"] + (" (day only)" if tuple(passes) == ("D",) else ""),
         "values": [], "status": [], "at_least": [], "passes_used": list(passes),
         "source": str(monthly_row.H_source) if monthly_row is not None else "unavailable (outside cached record)",
         "support": support}
    raw_h = []
    for i, _ in enumerate(days):
        status = src["status"][i]
        known = [(1. if ref == "SNPP" else factors.get("k_day" if dn == "D" else "k_night", np.nan))
                 * src[dn][i] for dn in passes if src[dn][i] is not None]
        if not bridge_ok:
            status, value, low = "not_supported", None, None
        elif status in ("outside_record", "provider_missing", "nothing_anywhere"):
            value, low = None, None
        elif len(known) < len(passes):
            status, value, low = "pass_missing", None, sum(known) if known and sum(known) > 0 else None
        else:
            status, value, low = "ok" if ref == "SNPP" else "modelled", sum(known), None
        raw_h.append(value)
        h["values"].append(round(value, 2) if value is not None else None)
        h["status"].append(status)
        h["at_least"].append(round(low, 2) if low is not None else None)
    out.append(h)
    for r in out:
        vals = raw_h if r["key"] == "H" else r["values"]
        used = [v for v in vals if v is not None]
        if r["key"] == "H":
            observed = monthly_row.H if monthly_row is not None else np.nan
        else:
            observed = (all_monthly_row[f"{r['key']}_D"] + all_monthly_row[f"{r['key']}_N"]) if all_monthly_row is not None else np.nan
        r["month_total"] = {"value": round(sum(used), 2) if used else None, "days_used": len(used),
                            "days_in_month": len(days), "days_held_out": 0,
                            "days_partial": r["status"].count("pass_missing"),
                            "calendar_observed_subtotal": round(float(observed), 2) if pd.notna(observed) else None,
                            "scope": "complete-pass eligible daily subtotal; differs from monthly cached-row subtotal when support is missing"}
    chosen_region = region or ("Pakistan" if bbox is None else None)
    bounds = analysis.area_bounds(chosen_region, tuple(bbox) if bbox is not None else None)
    declared_any = {date for p in PLATFORMS for date in b["plans"].get((mo, p), {}).get("declared_dates", [])}
    return {"status": "success", "region": region or ("Pakistan" if bbox is None else "Box " + ", ".join(map(str, bbox))),
            "box": analysis.check_box(bbox) if bbox is not None else None, "month": str(mo), "model": model,
            "days": [_iso(t) for t in days], "passes": list(passes), "rows": out,
            "worldview": [analysis.worldview_url(t, bounds) if _iso(t) in declared_any else None for t in days],
            "worldview_withheld": {"days": [], "why": [], "provinces": []}, "held_out": {"days": [], "why": []},
            "status_text": dict(analysis.DAY_STATUS),
            "units": "detections per UTC day: fire pixels on satellite passes; quality rule, type 0 when available; standard/NRT and untyped seams are explicit",
            "notes": ["Each platform is separate. H uses S-NPP before November 2026 and the saved Punjab-only NOAA-20 bridge thereafter; satellites are never summed for H.",
                      "No row for a platform/pass anywhere in Pakistan means unknown, never zero. A zero here requires cached rows for that same platform/pass elsewhere in Pakistan; exposure remains unknown.",
                      "Provider-missing days and incomplete passes are excluded from daily totals. The calendar_observed_subtotal field retains the monthly actual-row count, so daily totals can be lower; no day is proportionally filled.",
                      "Current monthly flags and type/processing seams also apply to every daily value. NRT/untyped observations do not establish historical comparability.",
                      "Only the monthly bridge was tested. Its daily factor use is experimental and daily conversion accuracy is untested; no daily uncertainty interval is available.",
                      "Month totals sum unrounded eligible daily values, then round once to two decimals. Dates are UTC; Pakistan is five hours ahead."]}
