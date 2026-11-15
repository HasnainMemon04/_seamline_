"""Region analysis behind the app and its exports (one function, so screen = export).

For a province, Pakistan or a lon/lat box inside Pakistan, analyse():
  1. builds monthly per-satellite counts with coverage status (c08.series);
  2. calibrates the chosen model on that region's own overlap months
     (2012-02..2017-12) after a support check, with 80% intervals from the
     region's own leave-one-year-out residuals (Protocol P01);
  3. returns raw, naive-stitch and harmonised records, a year x month calendar
     with anomaly classes, a month-versus-normal comparison, the P01 section 8
     change statistics, and a latest-days NRT comparison on matching dates.
Nothing here forecasts; "above/below" means compared with this area's own normal.
"""
from __future__ import annotations

import copy
import hashlib
import json
from functools import lru_cache

import numpy as np
import pandas as pd
import shapely
from shapely.geometry import box as shp_box

from . import acquire, boundaries, config, continuity, harmonize as hz, ingest, p01, series

MODEL_DEFAULT = "M2"  # selected in E01 (experiments/E01_selection/selection.json)
MODELS_OFFERED = ("M2", "M1")  # M1 shown as the alternative the 2012-13 test favoured
FIRST_YEAR, LAST_YEAR = 2003, 2026
MIN_SRC, MIN_SRC_MONTHS = 10, 5  # support check: detections and non-zero months per pass
WEAK_CV_WAPE = 0.5  # display rule (DECISIONS.md): above this, modelled years carry a weak-support warning
WIDE_RANGE = 3.0  # display rule (DECISIONS.md, 3 Nov): a season range whose ends differ more than 3x gets a warning
EXPORT_PLAIN_MAX = 300_000  # detections exports above this many rows are streamed as a ZIP
NOAA20_START = "2018-04"  # first month of the cached NOAA-20 archive, which the naive stitch adds
PASS_NAME = {"D": "day", "N": "night"}
SUPPORTED_PROVINCES = ("Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan", "Azad Kashmir",
                       "Gilgit-Baltistan", "Islamabad Capital Territory")


class AnalysisError(ValueError):
    pass


_RUNTIME = None


def _runtime_signature():
    paths = [ingest.DETECTIONS, ingest.INGEST_REPORT, config.MANIFEST, boundaries.FULL,
             config.ROOT / "experiments/PROTOCOL_P01.md", config.ROOT / "experiments/PROTOCOL_P04.md"]
    paths += sorted((config.ROOT / "c08").rglob("*.py"))
    return tuple((str(p), p.stat().st_size, p.stat().st_mtime_ns) for p in paths if p.is_file())


def clear_caches() -> None:
    """Clear all in-process analysis caches so changed inputs reload with a verified identity."""
    global _RUNTIME
    _RUNTIME = None
    for fn in (detections, ingest_report, pakistan_shape, _table, _inputs, _analyse, _daily,
               _latest_inputs, _latest_days_cached, _export_meta):
        if hasattr(fn, "cache_clear"):
            fn.cache_clear()
    continuity.clear_cache()


def data_identity() -> str:
    """Verified inputs for this process; invalidates caches atomically when inputs change."""
    global _RUNTIME
    current = continuity.metadata()["input_identity"]
    signature = (_runtime_signature(), json.dumps(current, sort_keys=True))
    code_signature = tuple(item for item in signature[0] if item[0].endswith(".py"))
    if _RUNTIME is not None and code_signature != _RUNTIME["code_signature"]:
        raise AnalysisError("Application code or configuration changed. Restart the local server before analyzing or exporting.")
    if _RUNTIME is not None and signature == _RUNTIME["signature"]:
        return _RUNTIME["identity"]
    if _RUNTIME is not None:
        clear_caches()
        current = continuity.metadata()["input_identity"]
        signature = (_runtime_signature(), json.dumps(current, sort_keys=True))
    rep = ingest_report()
    if not ingest.DETECTIONS.is_file() or acquire.sha256_file(ingest.DETECTIONS) != rep["output_sha256"]:
        raise AnalysisError("Historical detections SHA-256 differs from the ingest report. Restore the verified cache before restarting.")
    ident = hashlib.sha256(json.dumps({"historical": rep["output_sha256"], "current": current}, sort_keys=True).encode()).hexdigest()
    _RUNTIME = {"signature": signature, "code_signature": code_signature, "identity": ident, "code": ingest.code_state(),
                "protocols": [ingest.protocol_state(p) for p in ("experiments/PROTOCOL_P01.md", "experiments/PROTOCOL_P04.md")]}
    return ident


def provenance_contract() -> dict:
    ident = data_identity()
    return {"schema": "seamline-result-2", "data_identity": ident,
            "code": _RUNTIME["code"], "protocols": _RUNTIME["protocols"],
            "historical": ingest_report(), "current_record": continuity.metadata(),
            "refresh_policy": "Changed data clear analysis caches and are hash-verified before use. Restart after code/configuration changes; do not replace inputs during an active request.",
            "filters": "MODIS confidence >=30; VIIRS nominal/high. Historical standard type 0; current stream/type screen stated per row.",
            "acknowledgment": "NASA FIRMS, part of NASA LANCE and ESDIS. Data provided as is; not for tactical decisions.",
            "resource_review": "docs/RESOURCE_RELEASE_2026-11-13.md"}


@lru_cache(maxsize=1)
def detections() -> pd.DataFrame:
    if not ingest.DETECTIONS.is_file():
        raise AnalysisError("Processed detections are missing. Run: python -m c08.ingest")
    return pd.read_parquet(ingest.DETECTIONS)


@lru_cache(maxsize=1)
def ingest_report() -> dict:
    return json.loads(ingest.INGEST_REPORT.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def pakistan_shape():
    return shapely.union_all(list(boundaries.provinces().values()))


def check_box(bbox) -> dict:
    try:
        w, s, e, n = (float(v) for v in bbox)
    except (TypeError, ValueError):
        raise AnalysisError("A box needs four numbers: west, south, east, north")
    if not all(np.isfinite([w, s, e, n])) or not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise AnalysisError("Use west < east and south < north, in degrees")
    b = shp_box(w, s, e, n)
    share = pakistan_shape().intersection(b).area / b.area
    if share == 0:
        raise AnalysisError("This box lies outside Pakistan. The cached data are Pakistan's FIRMS country files only.")
    return {"bbox": [w, s, e, n], "share_inside_pakistan": round(float(share), 3)}


@lru_cache(maxsize=64)
def _table(region: str | None, bbox: tuple | None) -> pd.DataFrame:
    d = detections()
    spans = series.record_spans(d)
    rows = series.select(d, region=region, bbox=bbox)
    return series.wide(series.monthly(rows, spans))


def calibrate(w: pd.DataFrame, model: str) -> dict:
    """Region-own calibration on 2012-02..2017-12 plus LOYO residual intervals and agreement.

    Support check per pass. If only the night pass fails (Aqua rarely detects
    night burning in small areas), the region switches to the day-pass-only
    quantity: P01's day component, labelled as such everywhere.
    """
    plats = ("Aqua", "Terra", "SNPP")
    dep = p01._window(w, *p01.DEPLOY_BACKCAST)
    dep = dep[p01.scored_months(dep, plats)]
    sel = w[w.index.year.isin(p01.SELECTION_YEARS)]
    sel = sel[p01.scored_months(sel, plats)]
    failed = {}
    for dn in ("D", "N"):
        a = dep[f"Aqua_{dn}"]
        why = []
        if a.sum() < MIN_SRC or (a > 0).sum() < MIN_SRC_MONTHS:
            why.append(f"Aqua {PASS_NAME[dn]}-pass detections too few for calibration "
                       f"({int(a.sum())} detections in {int((a > 0).sum())} months; need {MIN_SRC} in {MIN_SRC_MONTHS})")
        if dep[f"SNPP_{dn}"].sum() == 0:
            why.append(f"No S-NPP {PASS_NAME[dn]}-pass detections in the overlap months")
        # Every leave-one-year-out training set needs some Aqua detections, or a ratio is undefined.
        empty = [y for y in p01.SELECTION_YEARS if sel.loc[sel.index.year != y, f"Aqua_{dn}"].sum() == 0]
        if empty:
            why.append(f"No Aqua {PASS_NAME[dn]}-pass detections in the cross-validation years other than "
                       + ", ".join(map(str, empty)))
        if why:
            failed[dn] = why
    if "D" in failed:
        return {"supported": False, "passes": ["D", "N"], "reasons": failed["D"] + failed.get("N", [])}
    passes = ("D",) if "N" in failed else ("D", "N")
    params = hz.fit(dep, model, passes=passes)
    obs = p01.obs_total(sel, passes=passes)
    pred = p01.loyo(w, p01.SELECTION_YEARS, model, passes=passes)["pred"].reindex(obs.index)
    resid = pd.DataFrame({"r": np.log1p(obs) - np.log1p(pred), "season": hz.season_of(obs.index.month.to_series())})
    qs = hz.interval_quantiles(resid)
    m1 = hz.metrics(obs, p01.loyo(w, p01.SELECTION_YEARS, "M1", passes=passes)["pred"].reindex(obs.index))
    def _plain(p):
        return {k: (round(v, 4) if isinstance(v, float) else {str(a): round(b, 4) for a, b in v.items()} if isinstance(v, dict) else v)
                for k, v in p.items()}
    one_sided = [s for s, q in qs.items() if q["lo"] > 0 or q["hi"] < 0]
    # Ratio models turn a month with no Aqua detection into zero; say how often S-NPP saw burning in such months.
    src0 = dep[[f"Aqua_{dn}" for dn in passes]].sum(axis=1) == 0
    ref_pos = dep[[f"SNPP_{dn}" for dn in passes]].sum(axis=1) > 0
    return {"supported": True, "model": model, "passes": list(passes), "fit_months": int(len(dep)),
            "day_only_reason": failed.get("N"),
            "aqua_zero_snpp_positive_share": round(float((src0 & ref_pos).mean()), 3),
            "params": {dn: _plain(params[dn]) for dn in passes},
            "interval_log_quantiles": qs, "one_sided_interval_seasons": one_sided,
            "cv_agreement": {"model": hz.metrics(obs, pred), "M1": m1},
            "cv_note": "Leave-one-year-out over 2014-2017 against S-NPP (another sensor, not ground truth)"}


def _passes(cal: dict) -> tuple[str, ...]:
    return tuple(cal.get("passes", ("D", "N")))


def _deploy_fit(w: pd.DataFrame, model: str, passes: tuple[str, ...]) -> dict:
    """The fitted conversion the harmonised record uses: this area's own 2012-02..2017-12 complete months."""
    dep = p01._window(w, *p01.DEPLOY_BACKCAST)
    return hz.fit(dep[p01.scored_months(dep, ("Aqua", "Terra", "SNPP"))], model, passes=passes)


def harmonise(w: pd.DataFrame, model: str, cal: dict) -> pd.DataFrame:
    ps = _passes(cal)
    cols = lambda plats: [f"{p}_{dn}" for p in plats for dn in ps]
    rec = p01._window(w, f"{FIRST_YEAR}-01", f"{LAST_YEAR}-12").copy()
    rec["aqua"] = rec[cols(["Aqua"])].sum(axis=1, min_count=len(ps))
    modis_all = rec[cols(["Terra", "Aqua"])].sum(axis=1, min_count=1)
    viirs_all = rec[cols(["SNPP", "NOAA20"])].sum(axis=1, min_count=1)
    rec["naive"] = np.where(rec.index < pd.Timestamp("2012-01"), modis_all, viirs_all)
    # The frozen naive stitch (P01 section 8) adds NOAA-20 from April 2018. This variant keeps
    # S-NPP alone after 2011, to show how much of the naive jump is that second satellite.
    rec["naive_snpp"] = np.where(rec.index < pd.Timestamp("2012-01"), modis_all,
                                 rec[cols(["SNPP"])].sum(axis=1, min_count=1))
    rec["H"] = rec[cols(["SNPP"])].sum(axis=1, min_count=len(ps))
    rec["H_lo"], rec["H_hi"] = rec["H"], rec["H"]
    rec["H_source"] = "observed S-NPP"
    modelled = rec.index < pd.Timestamp("2012-02")
    if cal["supported"]:
        params = _deploy_fit(w, model, ps)
        pred = hz.predict(rec[modelled], params)["pred"]
        iv = hz.apply_interval(pred, cal["interval_log_quantiles"])
        rec.loc[modelled, "H"] = pred
        rec.loc[modelled, "H_lo"] = iv["lo"]
        rec.loc[modelled, "H_hi"] = iv["hi"]
        rec.loc[modelled, "H_source"] = f"modelled from Aqua ({model})"
    else:
        rec.loc[modelled, ["H", "H_lo", "H_hi"]] = np.nan
        rec.loc[modelled, "H_source"] = "not supported (calibration failed support check)"
    # Coverage flags for each displayed series.
    rec["H_flag"] = np.where(modelled, np.where(rec["Aqua_status"] == "complete", "", rec["Aqua_status"]),
                             np.where(rec["SNPP_status"] == "complete", "", rec["SNPP_status"]))
    rec["aqua_flag"] = np.where(rec["Aqua_status"] == "complete", "", rec["Aqua_status"])
    # The naive stitch switches to VIIRS in Jan 2012, so it carries the flags of the satellites it sums.
    worst = lambda *cols: rec[list(cols)].apply(
        lambda r: next((v for v in r if v not in ("complete", "outside_record")), ""), axis=1)
    rec["naive_flag"] = np.where(rec.index < pd.Timestamp("2012-01"), worst("Aqua_status", "Terra_status"),
                                 worst("SNPP_status", "NOAA20_status"))
    rec["naive_snpp_flag"] = np.where(rec.index < pd.Timestamp("2012-01"), worst("Aqua_status", "Terra_status"),
                                      worst("SNPP_status"))
    return rec


def calendar(rec: pd.DataFrame, col: str, flag: str, years: tuple[int, int]) -> list[dict]:
    """Year x month cells with the P01 anomaly class against the median of the other years' same month."""
    r = rec[(rec.index.year >= years[0]) & (rec.index.year <= years[1])]
    out = []
    cls_idx, cls_v, cls_med = [], [], []
    vals_all = pd.to_numeric(r[col], errors="coerce").to_numpy(dtype=float)
    flags_all = r[flag].tolist()
    yrs_all = r.index.year.to_numpy(dtype=int)
    mos_all = r.index.month.to_numpy(dtype=int)
    for mo in range(1, 13):
        idxs = np.flatnonzero(mos_all == mo)
        valid_pairs = sorted((float(vals_all[i]), int(i)) for i in idxs if not np.isnan(vals_all[i]) and flags_all[i] == "")
        n_valid = len(valid_pairs)
        for pos in idxs:
            i = int(pos)
            v = float(vals_all[i])
            fl = flags_all[i]
            yr = int(yrs_all[i])
            is_valid = (not np.isnan(v)) and (fl == "")
            n_others = n_valid - 1 if is_valid else n_valid
            if n_others >= 3:
                other_vals = [val for val, j in valid_pairs if j != i]
                mid = n_others // 2
                med = other_vals[mid] if (n_others & 1) else (other_vals[mid - 1] + other_vals[mid]) / 2.0
            else:
                med = None
            partial = fl in ("partial_record", "outside_record") or (yr >= 2026 and bool(fl))
            val_out = None if np.isnan(v) else round(v, 2)
            med_out = None if med is None else round(med, 1)
            if med is not None and not np.isnan(v) and not partial:
                cls_idx.append(len(out))
                cls_v.append(v)
                cls_med.append(med)
            # Keep the monthly CSV precision: rounding to tenths here and then
            # to whole detections in the browser can change 744.49 into 745.
            out.append({"year": yr, "month": mo, "value": val_out,
                        "median_other_years": med_out, "n_years": n_others,
                        "class": None, "flag": fl})
    if cls_idx:
        classes = hz.anomaly_class(np.asarray(cls_v, dtype=float), np.asarray(cls_med, dtype=float)).tolist()
        for idx, c in zip(cls_idx, classes):
            out[idx]["class"] = c
    return sorted(out, key=lambda c: (c["year"], c["month"]))


def compare_month(rec: pd.DataFrame, year: int, month: int, years: tuple[int, int]) -> dict:
    """Selected month versus the median of the same month in the other years of the range."""
    t = pd.Timestamp(year=year, month=month, day=1)
    if t not in rec.index:
        raise AnalysisError(f"{year}-{month:02d} is outside the supported record ({FIRST_YEAR}-{LAST_YEAR})")
    out = {"month": f"{year}-{month:02d}", "baseline_years": list(years), "series": {}}
    for col, flag, label in (("H", "H_flag", "Harmonised (S-NPP-equivalent)"), ("aqua", "aqua_flag", "Aqua MODIS only"),
                             ("naive", "naive_flag", "Naive all-satellite stitch"),
                             ("naive_snpp", "naive_snpp_flag", "Naive stitch without NOAA-20 (S-NPP only after 2011)")):
        v = rec.at[t, col]
        f = rec.at[t, flag]
        g = rec[(rec.index.month == month) & (rec.index.year >= years[0]) & (rec.index.year <= years[1]) & (rec.index != t)]
        base = g.loc[g[col].notna() & (g[flag] == ""), col]
        entry = {"label": label, "value": _n(v), "flag": f,
                 "baseline_n": int(len(base))}
        if pd.isna(v):
            entry["status"] = "unavailable"
        elif f in ("partial_record", "outside_record") or (year >= 2026 and bool(f)):
            entry["status"] = "not compared: incomplete coverage or incompatible processing/type screen" if year >= 2026 else "not compared: the month is only partly covered by this satellite's record"
        elif len(base) < 3:
            entry["status"] = "not compared: fewer than 3 baseline years"
        else:
            med = float(base.median())
            entry.update(status="compared" if not f else "compared, with a coverage warning: " + f,
                         median=round(med, 1), ratio=round((v + 1) / (med + 1), 2),
                         cls=hz.anomaly_class([v], [med])[0],
                         rank=int((base < v).sum()) + 1, of=int(len(base)) + 1,
                         baseline_min=round(float(base.min()), 1), baseline_max=round(float(base.max()), 1))
        out["series"][col] = entry
    return out


@lru_cache(maxsize=2)
def _latest_inputs(_identity: str):
    hist = detections()
    cur = continuity.rows()
    # Latest-days uses the newest regional snapshot, not a platform/month API selection.
    # The new snapshot is selected for November, so it is retained by the current contract.
    d = pd.concat([hist[hist.stream.eq("standard")], cur[cur.stream.eq("nrt")]], ignore_index=True)
    d["province"] = pd.Categorical(d["province"], categories=hist.province.cat.categories)
    files = tuple(f for f in [*ingest_report()["files"], *continuity.metadata()["files"]]
                  if f.get("kind") != "firms_api_csv")
    return d, files


@lru_cache(maxsize=64)
def _latest_days_cached(_identity: str, _utc_day: str, region: str | None, bbox: tuple | None,
                        done: tuple[str, ...]) -> dict:
    d, files = _latest_inputs(_identity)
    return latest_from(d, list(files), region, bbox, done)


def latest_days(region: str | None, bbox: tuple | None, done: tuple[str, ...] | None = None) -> dict:
    done = p04_lock_state() if done is None else done
    now_utc = pd.Timestamp.now(tz="UTC")
    res = copy.deepcopy(_latest_days_cached(data_identity(), str(now_utc.date()), region, bbox, done))
    if res.get("available"):
        res["as_of_utc"] = now_utc.isoformat()
    return res


LATEST_MIN_YEARS = 3  # fewer covered past years than this: not compared


def _two_pass_days(rows: pd.DataFrame) -> set:
    """UTC days with at least one day-pass row and at least one night-pass row."""
    return set(rows.loc[rows["daynight"] == "D", "date_utc"]) & set(rows.loc[rows["daynight"] == "N", "date_utc"])


def latest_from(d: pd.DataFrame, files: list[dict], region: str | None, bbox: tuple | None,
                done: tuple[str, ...] | None = None) -> dict:
    """Complete UTC days of the newest NRT batch versus the same days in past years of the archive.

    Only the newest batch is counted. Every "acquire --nrt" stores a new snapshot under
    its UTC stamp and the 7-day files overlap, so counting all snapshots would count the
    same detections twice.

    A day counts only when the satellite has both of its daily passes over Pakistan (day
    near 08 UTC, night near 21 UTC), each with at least one detection somewhere in
    Pakistan. A day with no rows is no data (an outage, or the end of the mission: S-NPP
    stopped on 2 Nov 2026), never zero burning. A day with one pass may be an outage or
    just a quiet pass (about 1 day in 10 in July and August); it is left out too, on both
    sides. 29 February is left out because most past years lack it.

    Each past year compares the same window moved back whole years, named by the year of
    its last day, so 28 Dec to 2 Jan maps to 28 Dec y-1 to 2 Jan y. A past year counts
    only if the archive covers every one of those days: the satellite had started, FIRMS
    lists none of them as missing, and each has both passes in the archive as well. The
    window's own year never enters its history. (CHECK REPORTs B05-BUILDER and B05-FIX.)
    A past year whose compared days fall in a P04 test window for this area is held out too.
    """
    done = p04_lock_state() if done is None else done
    nrt = [f for f in files if f["stream"] == "nrt"]
    if not nrt:
        return {"available": False}
    stamp = max(f["id"].rsplit("/", 1)[-1] for f in nrt)  # ids are nrt/<source>/<YYYYMMDDTHHMMZ>
    batch = [f for f in nrt if f["id"].rsplit("/", 1)[-1] == stamp]
    rows = d[d["stream"].eq("nrt") & d["source_id"].isin({f["id"] for f in batch})]
    retrieved = pd.Timestamp(max(f["retrieved_utc"] for f in batch)).tz_convert(None).normalize()
    if rows.empty:
        return {"available": False}
    # The first and the last (retrieval) day of a 7-day file are partial.
    days = pd.date_range(max(rows["date_utc"].min() + pd.Timedelta(days=1), retrieved - pd.Timedelta(days=6)), retrieved - pd.Timedelta(days=1), freq="D")
    if not len(days):
        return {"available": False}
    q = series.select(rows, region=region, bbox=bbox, stream="nrt", type0=False)
    arch = series.select(d, region=region, bbox=bbox, type0=False)  # NRT has no type field: compare like with like
    older = sorted({f["id"].rsplit("/", 1)[-1] for f in nrt} - {stamp})
    out = {"available": True, "window_utc": [str(days[0].date()), str(days[-1].date())], "n_days": len(days),
           "retrieved_utc": str(retrieved.date()), "batch": stamp, "older_batches_not_counted": len(older),
           "platforms": {},
           "note": "Near-real-time (NRT) processing versus the standard archive; type (static-source) screening "
                   "is unavailable in NRT files, so neither side applies it here. Same calendar days, same satellite. "
                   "Only the newest NRT download is counted. NOAA-21 is not shown: it has no archive years to "
                   "compare with."}
    age = max(0, (pd.Timestamp.now(tz="UTC").tz_localize(None).normalize() - retrieved).days)
    out.update(age_days=age, freshness="stale" if age > 2 else "recent cached snapshot",
               as_of_utc=pd.Timestamp.now(tz="UTC").isoformat())
    spans = series.record_spans(d)  # first and last archive day per satellite
    gaps = series.provider_missing()
    gaps = gaps[gaps["stream"] == "standard"]
    std = d[d["stream"] == "standard"]
    # Rows the P04 lock holds don't decide whether a pass "has data" for an open area either (S02 review).
    std = std[~held_rows_mask(std, done)]
    for p in ("SNPP", "NOAA20"):
        mine = rows[rows["platform"] == p]
        full = _two_pass_days(mine)
        seen = set(mine["date_utc"])
        missing = [str(t.date()) for t in days if t not in seen]
        partial = [str(t.date()) for t in days if t in seen and t not in full]
        leap = [str(t.date()) for t in days if t in full and (t.month, t.day) == (2, 29)]
        have = [t for t in days if t in full and (t.month, t.day) != (2, 29)]
        left = {"days_without_data": missing, "days_partial": partial, "leap_day_left_out": leap}
        if not have:
            out["platforms"][p] = {"status": "only_29_february" if leap else "no_data", "now": None, "cls": None,
                                   "days_used": 0} | left
            continue
        now = int(q[(q["platform"] == p) & q["date_utc"].isin(have)].shape[0])
        g = arch[arch["platform"] == p]
        hist, why = {}, {}
        if p in spans:  # a satellite with no archive has no past years at all
            start, end = spans[p]
            off = set(gaps.loc[gaps["platform"] == p, "date"])
            both = _two_pass_days(std[std["platform"] == p])  # Pakistan-wide, as for the download
            for y in range(start.year, days[-1].year):  # never the window's own year
                dts = [t - pd.DateOffset(years=days[-1].year - y) for t in have]
                quiet = [str(t.date()) for t in dts if t not in both]
                held = held_out_days(pd.DatetimeIndex(dts), region, bbox, done)[0]
                reason = (HELD_REASON if held else
                          "before the archive starts" if min(dts) < start else
                          "after the archive ends" if max(dts) > end else
                          "reaches the window" if max(dts) >= days[0] else
                          "FIRMS lists a missing day" if off.intersection(dts) else
                          "missing or quiet pass on " + ", ".join(quiet) if quiet else None)
                if reason:  # the archive does not cover every compared day: no data, not zero
                    why[y] = reason
                    continue
                hist[y] = int(g["date_utc"].isin(dts).sum())
        base = {"now": now, "days_used": len(have), "years_left_out": sorted(why),
                "years_left_out_why": {str(y): r for y, r in sorted(why.items())}} | left
        if len(hist) < LATEST_MIN_YEARS:
            out["platforms"][p] = {"status": "too_few_years", "cls": None, "years": hist} | base
            continue
        vals = np.array(list(hist.values()), float)
        med = float(np.median(vals))
        out["platforms"][p] = {"status": "compared", "median": med, "min": int(vals.min()), "max": int(vals.max()),
                               "years": hist, "cls": hz.anomaly_class([now], [med])[0],
                               "ratio": round((now + 1) / (med + 1), 2)} | base
    return out


# ---------- day by day (TASK_BOARD S02) ----------

DAILY_PLATFORMS = ("Terra", "Aqua", "SNPP", "NOAA20")
# Every row counts day plus night passes. Terra's "night" pass is in the late evening, Pakistan time
# (Opus review of S02, 5 Nov), so its label names both passes.
DAILY_LABELS = {"Terra": "Terra MODIS (morning and late-evening passes)", "Aqua": "Aqua MODIS", "SNPP": "S-NPP VIIRS",
                "NOAA20": "NOAA-20 VIIRS", "H": "Harmonised (S-NPP-equivalent)"}
DAILY_LABEL_H_DAY_ONLY = "Harmonised (S-NPP-equivalent, day passes only)"
# A satellite-day is complete only when each of these passes has at least one row somewhere in Pakistan.
# A MODIS night pass is empty everywhere in Pakistan on most days (about 83% for Aqua and 66% for Terra on
# the days the review could check), so for Terra and Aqua only the day pass must have rows.
REQUIRED_PASSES = {"Terra": ("D",), "Aqua": ("D",), "SNPP": ("D", "N"), "NOAA20": ("D", "N")}
DAY_STATUS = {
    "ok": "counted: this satellite's files have rows somewhere in Pakistan that day, on each pass this row needs",
    "modelled": "converted from Aqua with this area's fitted factor (daily accuracy untested)",
    "pass_missing": "partly unknown: a pass this row needs has no row anywhere in Pakistan that day (an outage or a "
                    "quiet pass), so the day is left out of the month total; '≥' shows the other pass alone",
    "outside_record": "no data: outside this satellite's archive record",
    "provider_missing": "no data: FIRMS lists this day as missing for this satellite",
    "nothing_anywhere": "unknown: this satellite has no row anywhere in Pakistan that day (an outage or a quiet day)",
    "not_supported": "no value: this area failed the calibration support check",
    "held_out": "held out for a frozen test until it runs (Protocol P04)",
}
DAY_VALUE_STATUSES = ("ok", "modelled")  # the only statuses that carry a number (and enter month totals)
# App rule (PROTOCOL_P04.md change log, entry 1, item 10.4): daily values inside P04's G01 and G02 test
# windows stay hidden until those tests have run, so nobody, the builder included, sees them first.
P04_LOCK_YEARS = (2012, 2025)
P04_LOCKS = (
    {"name": "rice", "areas": ("Sindh", "Khyber Pakhtunkhwa"), "start": (9, 15), "end": (12, 31),
     "needs": ("P04_G01_terra_step", "P04_G02_season_dates"),
     "why": "15 Sep–31 Dec, 2012–2025, in Sindh and Khyber Pakhtunkhwa: the test data of P04's G01 and G02"},
    {"name": "spring", "areas": ("Punjab", "Sindh", "Khyber Pakhtunkhwa"), "start": (3, 15), "end": (6, 30),
     "needs": ("P04_G02_season_dates",),
     "why": "15 Mar–30 Jun, 2012–2025, in Punjab, Sindh and Khyber Pakhtunkhwa: the test data of P04's G02"},
)
HELD_REASON = "held out until P04's frozen tests run"
# G01's quantity is Terra / S-NPP in October and November, 2018-2025, so Terra's monthly columns stay hidden
# there as well (the page never draws Terra, but the reply and the monthly CSV carry it).
TERRA_MONTH_LOCK = {"areas": ("Sindh", "Khyber Pakhtunkhwa"), "months": (10, 11), "years": (2018, 2025),
                    "needs": ("P04_G01_terra_step",)}
WORLDVIEW = "https://worldview.earthdata.nasa.gov/"
WORLDVIEW_PAD = 0.3  # degrees added around the area in a Worldview link
# Worldview fits the requested box to the reader's window, so the map can be much wider or taller than the box.
# A link is judged on the box stretched to a very wide (2.4:1) and a very tall (1:2.2) window.
WORLDVIEW_STRETCH = (2.4, 2.2)
# Worldview layer ids and start dates, read from its configuration (wv.json) on 5 Nov 2026.
WORLDVIEW_FIRE_LAYERS = (("VIIRS_NOAA20_Thermal_Anomalies_375m_All", "2020-01-01"),
                         ("VIIRS_SNPP_Thermal_Anomalies_375m_All", "2012-01-20"),
                         ("MODIS_Aqua_Thermal_Anomalies_All", "2002-07-04"),
                         ("MODIS_Terra_Thermal_Anomalies_All", "2000-11-01"))


def p04_lock_state() -> tuple[str, ...]:
    """Names of the P04 result folders that exist (a lock lifts once all its tests have results)."""
    names = {n for lock in P04_LOCKS for n in lock["needs"]}
    return tuple(sorted(n for n in names if (config.EXPERIMENTS / n / "result.json").is_file()))


def _area_overlaps(region: str | None, bbox: tuple | None, names: tuple[str, ...]) -> list[str]:
    if bbox is not None:
        b = shp_box(*bbox)
        geo = boundaries.provinces()
        return [n for n in names if n in geo and geo[n].intersection(b).area > 0]
    if region == "Pakistan":
        return list(names)
    return [region] if region in names else []


def held_out_days(days: pd.DatetimeIndex, region: str | None, bbox: tuple | None,
                  done: tuple[str, ...]) -> tuple[set, list[str]]:
    """Days of `days` that the P04 lock withholds for this area, and the reasons."""
    held, why = set(), []
    for lock in P04_LOCKS:
        if all(n in done for n in lock["needs"]):
            continue
        areas = _area_overlaps(region, bbox, lock["areas"])
        if not areas:
            continue
        hit = {t for t in days if P04_LOCK_YEARS[0] <= t.year <= P04_LOCK_YEARS[1]
               and lock["start"] <= (t.month, t.day) <= lock["end"]}
        if hit:
            held |= hit
            why.append(lock["why"])
    return held, why


def held_rows_mask(q: pd.DataFrame, done: tuple[str, ...]) -> pd.Series:
    """Observation rows inside an open P04 test window, in a protected province (row exports leave them out)."""
    mask = pd.Series(False, index=q.index)
    if q.empty:
        return mask
    md = q["date_utc"].dt.month * 100 + q["date_utc"].dt.day
    yr = q["date_utc"].dt.year
    prov = q["province"].astype(str)
    for lock in P04_LOCKS:
        if all(n in done for n in lock["needs"]):
            continue
        a, b = lock["start"][0] * 100 + lock["start"][1], lock["end"][0] * 100 + lock["end"][1]
        mask |= prov.isin(lock["areas"]) & yr.between(*P04_LOCK_YEARS) & md.between(a, b)
    return mask


def terra_months_locked(region: str | None, bbox: tuple | None, done: tuple[str, ...]) -> bool:
    lock = TERRA_MONTH_LOCK
    return not all(n in done for n in lock["needs"]) and bool(_area_overlaps(region, bbox, lock["areas"]))


def _lock_provinces(why: list[str]) -> list[str]:
    """The provinces named by the open locks behind `why` (held_out_days' reasons), in lock order."""
    out = []
    for lock in P04_LOCKS:
        if lock["why"] in why:
            out += [a for a in lock["areas"] if a not in out]
    return out


def day_status(platform: str, t: pd.Timestamp, spans: dict, missing: set, present: set, held: set) -> str:
    """Why a satellite's day has a number or not. Missing data is never shown as zero."""
    if t in held:
        return "held_out"
    if platform not in spans or not spans[platform][0] <= t <= spans[platform][1]:
        return "outside_record"
    if t in missing:
        return "provider_missing"
    if (platform, t) not in present:
        return "nothing_anywhere"
    return "ok"


def missing_passes(platform: str, t: pd.Timestamp, present_pass: set) -> list[str]:
    """Passes this satellite needs on day t that have no row anywhere in Pakistan (an outage or a quiet pass)."""
    return [dn for dn in REQUIRED_PASSES.get(platform, ("D", "N")) if (platform, t, dn) not in present_pass]


def area_bounds(region: str | None, bbox: tuple | None) -> tuple[float, float, float, float]:
    if bbox is not None:
        return tuple(float(v) for v in bbox)
    geom = pakistan_shape() if region == "Pakistan" else boundaries.provinces()[region]
    return tuple(float(v) for v in geom.bounds)


def worldview_url(t: pd.Timestamp, bounds: tuple[float, float, float, float], pad: float = WORLDVIEW_PAD) -> str:
    """NASA Worldview on this UTC day and area, with the fire layers that exist on that day (top layer first)."""
    w, s, e, n = bounds
    v = ",".join(f"{x:.2f}" for x in (max(-180, w - pad), max(-90, s - pad), min(180, e + pad), min(90, n + pad)))
    day = t.strftime("%Y-%m-%d")
    fires = [lid for lid, start in WORLDVIEW_FIRE_LAYERS if day >= start]
    layers = ["Reference_Labels_15m", "Coastlines_15m", *fires, "MODIS_Aqua_CorrectedReflectance_TrueColor"]
    return f"{WORLDVIEW}?v={v}&t={day}-T00%3A00%3A00Z&l={','.join(layers)}"


def worldview_view(bounds: tuple[float, float, float, float], pad: float = WORLDVIEW_PAD) -> tuple[float, ...]:
    """The largest map a Worldview link for these bounds can open on: the padded box, stretched both ways."""
    w, s, e, n = bounds[0] - pad, bounds[1] - pad, bounds[2] + pad, bounds[3] + pad
    cx, cy, hw, hh = (w + e) / 2, (s + n) / 2, (e - w) / 2, (n - s) / 2
    vw, vh = max(hw, WORLDVIEW_STRETCH[0] * hh), max(hh, WORLDVIEW_STRETCH[1] * hw)
    return (max(-180.0, cx - vw), max(-90.0, cy - vh), min(180.0, cx + vw), min(90.0, cy + vh))


def worldview_withheld(days: pd.DatetimeIndex, bounds: tuple[float, float, float, float],
                       done: tuple[str, ...]) -> tuple[set, list[str], list[str]]:
    """Days on which a Worldview link for this area would open on a province that the P04 lock holds that day.

    Worldview would show that province's fire layers on a held day, so such days get no link at all while the
    lock is on (Opus review of S02, 5 Nov). Returns the days, the locks' reasons and the provinces in view.
    """
    view = worldview_view(bounds)
    held, why = held_out_days(days, None, view, done)
    provs = []
    for lock in P04_LOCKS:
        if lock["why"] in why:
            provs += [a for a in _area_overlaps(None, view, lock["areas"]) if a not in provs]
    return held, why, provs


def _whole(v) -> int:
    """A whole number from JSON: 2015, 2015.0 or "2015"; never true/false, 2015.5, Infinity or NaN."""
    if isinstance(v, bool):
        raise ValueError(v)
    if isinstance(v, float):
        if not v.is_integer():  # also rejects inf and nan
            raise ValueError(v)
        return int(v)
    if isinstance(v, (int, str)):
        return int(v)
    raise TypeError(v)


def daily(*, region: str | None = "Punjab", bbox=None, year: int, month: int, model: str = MODEL_DEFAULT) -> dict:
    """One month, day by day, for one area: each satellite separately plus the harmonised series."""
    if model not in MODELS_OFFERED:
        raise AnalysisError(f"Model must be one of {MODELS_OFFERED}")
    if bbox is not None:
        bbox, region = tuple(check_box(bbox)["bbox"]), None
    elif region not in ("Pakistan",) + SUPPORTED_PROVINCES:
        raise AnalysisError("Choose Pakistan, a province, or a box")
    try:
        year, month = _whole(year), _whole(month)
    except (TypeError, ValueError, OverflowError):
        raise AnalysisError("Choose a year and a month as whole numbers, for example 2025 and 11") from None
    if not (FIRST_YEAR <= year <= LAST_YEAR and 1 <= month <= 12):
        raise AnalysisError(f"Choose a month from January {FIRST_YEAR} to December {LAST_YEAR}")
    data_identity()
    if year >= continuity.FIRST_YEAR:
        return continuity.daily(region=region, bbox=bbox, year=year, month=month,
                                passes=_passes(_inputs(region, bbox, model)[1]), model=model)
    return copy.deepcopy(_daily(region, bbox, year, month, model, p04_lock_state()))


def _and(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


DAILY_UNITS = ("detections per UTC day: fire pixels on satellite passes (not fires, not area); "
               "quality rule and type-0 screen, standard archive")


def _held_month(label: str, box: dict | None, year: int, month: int, model: str, days: pd.DatetimeIndex,
                why: list[str]) -> dict:
    """The reply for a month the P04 lock holds on every day: nothing is read, counted or calibrated."""
    k = len(days)
    blank = lambda: [None] * k
    rows = [{"key": p, "label": DAILY_LABELS[p], "values": blank(), "D": blank(), "N": blank(),
             "status": ["held_out"] * k, "at_least": blank(), "empty_everywhere": [[] for _ in days],
             "passes_needed": list(REQUIRED_PASSES[p])} for p in DAILY_PLATFORMS]
    rows.append({"key": "H", "label": DAILY_LABELS["H"], "values": blank(), "status": ["held_out"] * k,
                 "at_least": blank(), "source": HELD_REASON, "passes_used": []})
    for r in rows:
        r["month_total"] = {"value": None, "days_used": 0, "days_in_month": k, "days_held_out": k, "days_partial": 0}
    return {"status": "success", "region": label, "box": box, "month": f"{year}-{month:02d}", "model": model,
            "days": [str(t.date()) for t in days], "passes": [], "rows": rows, "worldview": blank(),
            "worldview_withheld": {"days": [], "why": [], "provinces": []},
            "held_out": {"days": [str(t.date()) for t in days], "why": why}, "status_text": dict(DAY_STATUS),
            "units": DAILY_UNITS, "notes": ["Every day of this month is held out here until P04's frozen tests run: "
                                            + "; ".join(why) + "."]}


@lru_cache(maxsize=64)
def _daily(region: str | None, bbox: tuple | None, year: int, month: int, model: str,
           done: tuple[str, ...]) -> dict:
    days = pd.date_range(f"{year}-{month:02d}-01", periods=pd.Period(f"{year}-{month:02d}").days_in_month, freq="D")
    held, why = held_out_days(days, region, bbox, done)
    label = region if region else "Box " + ", ".join(f"{v:g}" for v in bbox)
    box = check_box(bbox) if bbox is not None else None
    if len(held) == len(days):
        return _held_month(label, box, year, month, model, days, why)
    d = detections()
    open_days = [t for t in days if t not in held]  # nothing below is counted on a held-out day
    spans = series.record_spans(d)
    gaps = series.provider_missing()
    gaps = gaps[gaps["stream"] == "standard"]
    missing = {p: set(g["date"]) for p, g in gaps.groupby("platform")}
    std = d[d["stream"].eq("standard") & d["date_utc"].isin(open_days)]
    # Rows that the P04 lock holds never decide whether a satellite had data on a day, so an open area's
    # "0" versus "?" says nothing about a held province (Opus review of S02, 5 Nov). They are never counted either.
    seen = std[~held_rows_mask(std, done)]
    present = set(zip(seen["platform"].astype(str), seen["date_utc"]))  # any row anywhere in Pakistan
    present_pass = set(zip(seen["platform"].astype(str), seen["date_utc"], seen["daynight"].astype(str)))
    rows = series.select(seen, region=region, bbox=bbox)  # quality rule and type-0 screen, as the monthly record
    counts = rows.groupby(["platform", "date_utc", "daynight"], observed=True).size()
    n = lambda p, t, dn: int(counts.get((p, t, dn), 0))

    out_rows = []
    for p in DAILY_PLATFORMS:
        cells = []  # per day: status, day-pass count, night-pass count, value, lower bound, passes empty everywhere
        for t in days:
            s = day_status(p, t, spans, missing.get(p, set()), present, held)
            if s != "ok":
                cells.append((s, None, None, None, None, []))
                continue
            gone = missing_passes(p, t, present_pass)  # a pass with no row anywhere: unknown, never zero
            # A pass this satellite does not need that is empty everywhere (a MODIS night) counts as zero, and says so.
            quiet = [dn for dn in "DN" if dn not in gone and (p, t, dn) not in present_pass]
            a = None if "D" in gone else n(p, t, "D")
            b = None if "N" in gone else n(p, t, "N")
            if gone:  # partial day: the known pass is only a lower bound for the day
                cells.append(("pass_missing", a, b, None, sum(x for x in (a, b) if x is not None) or None, quiet))
            else:
                cells.append(("ok", a, b, a + b, None, quiet))
        st, dd, nn, vals, low, quiet = (list(c) for c in zip(*cells))
        out_rows.append({"key": p, "label": DAILY_LABELS[p], "values": vals, "D": dd, "N": nn, "status": st,
                         "at_least": low, "empty_everywhere": quiet, "passes_needed": list(REQUIRED_PASSES[p])})

    # Harmonised: observed S-NPP from Feb 2012, as the monthly record; before that, Aqua's day counts times
    # this area's own conversion (the same fitted factor the monthly record uses).
    w, cal, rec = _inputs(region, bbox, model)
    ps = _passes(cal)
    day_only = ps == ("D",)
    by = {r["key"]: r for r in out_rows}
    first = pd.Timestamp(year=year, month=month, day=1)
    modelled = first < pd.Timestamp("2012-02-01")
    src = by["Aqua"] if modelled else by["SNPP"]
    params = _deploy_fit(w, model, ps) if modelled and cal["supported"] else None
    k = ({dn: params[dn]["k"] if model == "M1" else params[dn]["k_month"][month] for dn in ps} if params else None)
    h_cells = []  # per day: status, shown value, unrounded value, lower bound
    for i in range(len(days)):
        s = src["status"][i]
        if s not in ("ok", "pass_missing"):
            h_cells.append((s, None, None, None))
        elif modelled and params is None:
            h_cells.append(("not_supported", None, None, None))
        else:
            known = [(k[dn] if modelled else 1) * src[dn][i] for dn in ps if src[dn][i] is not None]
            if len(known) == len(ps):  # every pass the harmonised series uses is known
                raw = sum(known)
                h_cells.append(("modelled" if modelled else "ok", round(raw, 1) if modelled else raw, raw, None))
            else:
                lo = sum(known)
                h_cells.append(("pass_missing", None, None, (round(lo, 1) if modelled else lo) if lo > 0 else None))
    h_st, h_vals, h_raw, h_low = (list(c) for c in zip(*h_cells))
    source = str(rec.at[first, "H_source"])  # the monthly record's own wording for this month
    if modelled and cal["supported"]:
        source += ", " + ("one factor per pass" if model == "M1" else "this calendar month's factor")
    if day_only:
        source += ", day passes only"
    out_rows.append({"key": "H", "label": DAILY_LABEL_H_DAY_ONLY if day_only else DAILY_LABELS["H"],
                     "values": h_vals, "status": h_st, "at_least": h_low, "source": source,
                     "passes_used": list(ps)})

    raws = {"H": h_raw}
    for r in out_rows:
        vals = raws.get(r["key"], r["values"])  # the harmonised total adds unrounded days, then rounds once
        used = [v for v, s in zip(vals, r["status"]) if s in DAY_VALUE_STATUSES]
        # Same precision as the calendar (_n): rounding to tenths here could show one detection more (F3).
        r["month_total"] = {"value": _n(sum(used)) if used else None, "days_used": len(used),
                            "days_in_month": len(days), "days_held_out": sum(s == "held_out" for s in r["status"]),
                            "days_partial": sum(s == "pass_missing" for s in r["status"])}

    bounds = area_bounds(region, bbox)
    wv_held, wv_why, wv_provs = worldview_withheld(days, bounds, done)

    # Wording that depends on this area and month (Opus review of S02, 5 Nov).
    lock_days, lock_why = held_out_days(days, "Pakistan", None, done)  # P04 windows open on these dates
    status_text = dict(DAY_STATUS)
    notes = ["Each satellite is counted on its own; satellites are never added together.",
             "A zero means this satellite's files have rows somewhere in Pakistan that day, and none here. Whether "
             "this area was seen (gaps between swaths, clouds, smoke) is unknown: no detection is not no fire.",
             "A day counts only when each pass a row needs has rows somewhere in Pakistan: both passes for S-NPP and "
             "NOAA-20, and the day pass for Terra and Aqua. A MODIS night pass is empty everywhere in Pakistan on "
             "most days, so an empty MODIS night pass counts as zero."]
    if any(s == "pass_missing" for r in out_rows for s in r["status"]):
        notes.append("'≥' on a striped cell marks a partial day: a pass the row needs has no row anywhere in Pakistan "
                     "(an outage or a quiet pass), so only the other pass is shown, as a lower bound ('?' if it shows "
                     "nothing here). Partial days are left out of the month total.")
    if set(lock_days) - held:
        provs = _and(_lock_provinces(lock_why))
        for key in ("nothing_anywhere", "pass_missing"):
            status_text[key] = status_text[key].replace(
                "anywhere in Pakistan", f"anywhere in Pakistan (outside {provs} on days held out for P04)")
        notes.append(f"On days inside P04's test windows, rows from {provs} are not used to decide whether a "
                     "satellite had data that day, so '?' and '≥' on those days can hide detections there.")
    if not cal["supported"]:
        notes.append("This area failed the calibration support check, so harmonised days before February 2012 have "
                     "no value ('n/a'): " + "; ".join(cal["reasons"]) + ". Aqua's own daily counts are in its row.")
    elif day_only:
        notes.append("Harmonised days before February 2012 are Aqua's day-pass count times this area's day-pass "
                     f"conversion ({model}, fitted on 2012–2017 months). Aqua's night detections are left out here "
                     "because they are too few to calibrate. Only monthly values were tested; daily accuracy is untested.")
    else:
        notes.append("Harmonised days before February 2012 are Aqua's daily count times this area's conversion "
                     f"({model}, fitted on 2012–2017 months; "
                     + ("one factor per pass" if model == "M1" else "a factor for each calendar month")
                     + "). Only monthly values were tested; daily accuracy is untested.")
    notes += ["From February 2012 the harmonised series is observed S-NPP"
              + (" (day passes only in this area; the satellite rows count day and night passes)." if day_only else "."),
              "Terra passes in the morning and late evening; Aqua, S-NPP and NOAA-20 in the early afternoon and after "
              "midnight (Pakistan time), so their counts differ by design. Terra's and Aqua's pass times have drifted "
              "in recent years (Terra earlier, Aqua later).",
              "Days are UTC dates; Pakistan is five hours ahead."]
    if box and box["share_inside_pakistan"] < 0.99:
        notes.append(f"Only {box['share_inside_pakistan']:.0%} of this box is inside Pakistan; detections outside "
                     "Pakistan are not in the cached country files, so the rest of the box counts nothing. Worldview "
                     "shows the whole box, including detections outside Pakistan that are not counted here.")
    return {
        "status": "success", "region": label, "box": box, "month": f"{year}-{month:02d}", "model": model,
        "days": [str(t.date()) for t in days],
        "passes": list(ps), "rows": out_rows,
        # No link into a held-out day, nor onto a map that would show a held province's fire layers that day.
        "worldview": [None if t in held or t in wv_held else worldview_url(t, bounds) for t in days],
        "worldview_withheld": {"days": sorted(str(t.date()) for t in wv_held - held), "why": wv_why,
                               "provinces": wv_provs},
        "held_out": {"days": sorted(str(t.date()) for t in held), "why": why},
        "status_text": status_text,
        "units": DAILY_UNITS + ("; in this area the harmonised row counts day passes only, while the satellite rows "
                                "count day and night passes (their D and N lists split them)" if day_only else ""),
        "notes": notes,
    }


def analyse(*, region: str | None = "Punjab", bbox=None, years=(FIRST_YEAR, LAST_YEAR),
            month: tuple[int, int] | None = None, model: str = MODEL_DEFAULT) -> dict:
    if model not in MODELS_OFFERED:
        raise AnalysisError(f"Model must be one of {MODELS_OFFERED}")
    box_info = None
    if bbox is not None:
        box_info = check_box(bbox)
        bbox, region = tuple(box_info["bbox"]), None
    elif region not in ("Pakistan",) + SUPPORTED_PROVINCES:
        raise AnalysisError("Choose Pakistan, a province, or a box")
    y0, y1 = (int(v) for v in years)
    if not (FIRST_YEAR <= y0 < y1 <= LAST_YEAR):
        raise AnalysisError(f"Years must satisfy {FIRST_YEAR} <= from < to <= {LAST_YEAR}")
    month = (y1, 11) if month is None else (int(month[0]), int(month[1]))
    # Cached per request: repeat views come back at once, which also narrows the window in
    # which a slow reply could arrive after a newer selection. Callers get their own copy.
    data_identity()
    return copy.deepcopy(_analyse(region, bbox, (y0, y1), month, model, p04_lock_state()))


@lru_cache(maxsize=32)
def _inputs(region: str | None, bbox: tuple | None, model: str):
    """Monthly table, calibration and harmonised record for one area and model (read-only)."""
    w = _table(region, bbox)
    cal = calibrate(w, model)
    rec = harmonise(w, model, cal)
    current = continuity.monthly(region=region, bbox=bbox, passes=_passes(cal))
    # Raw per-platform columns always retain both passes, also for day-only calibrated areas.
    if _passes(cal) != ("D", "N"):
        raw = continuity.monthly(region=region, bbox=bbox)
        for p in continuity.PLATFORMS:
            for dn in "DN":
                current[f"{p}_{dn}"] = raw[f"{p}_{dn}"]
    return w, cal, pd.concat([rec, current])


@lru_cache(maxsize=64)
def _export_meta(_identity: str, region: str | None, bbox: tuple | None,
                 y0: int, y1: int, done: tuple[str, ...]) -> tuple[int, int]:
    """Held-out and exportable detection row counts for one region, year span and lock state."""
    w = _table(region, bbox)
    count_cols = [c for c in w.columns if c.endswith(("_D", "_N"))]
    span = w[(w.index.year >= y0) & (w.index.year <= y1)]
    sel = series.select(detections(), region=region, bbox=bbox)
    held_rows = int(held_rows_mask(sel[(sel.year >= y0) & (sel.year <= y1)], done).sum())
    export_rows = int(span[count_cols].fillna(0).to_numpy().sum()) - held_rows
    if y1 >= continuity.FIRST_YEAR:
        export_rows += len(continuity.selection(region=region, bbox=bbox, years=(y0, y1)))
    return held_rows, export_rows


@lru_cache(maxsize=32)
def _analyse(region: str | None, bbox: tuple | None, years: tuple[int, int], month: tuple[int, int],
             model: str, done: tuple[str, ...] = ()) -> dict:
    y0, y1 = years
    box_info = check_box(bbox) if bbox is not None else None
    ident = data_identity()
    w, cal, rec = _inputs(region, bbox, model)
    terra_locked = terra_months_locked(region, bbox, done)
    tl = TERRA_MONTH_LOCK
    view = rec[(rec.index.year >= y0) & (rec.index.year <= y1)]
    months = []
    for t, r in view.iterrows():
        months.append({"month": t.strftime("%Y-%m"), "H": _n(r.H), "H_lo": _n(r.H_lo), "H_hi": _n(r.H_hi),
                       "H_source": r.H_source, "H_flag": r.H_flag, "naive": _n(r.naive), "naive_flag": r.naive_flag,
                       "naive_snpp": _n(r.naive_snpp), "naive_snpp_flag": r.naive_snpp_flag,
                       "aqua": _n(r.aqua), "aqua_flag": r.aqua_flag,
                       **{f"{p}_{dn}": _n(r[f"{p}_{dn}"]) for p in ("Terra", "Aqua", "SNPP", "NOAA20") for dn in "DN"},
                       **{f"{p}_status": r[f"{p}_status"] for p in ("Terra", "Aqua", "SNPP", "NOAA20")}})
        months[-1]["H_support"] = r.get("H_support") if isinstance(r.get("H_support"), dict) else None
        for p in continuity.PLATFORMS:
            for dn in "DN":
                months[-1][f"{p}_{dn}"] = _n(r.get(f"{p}_{dn}", np.nan))
            for suffix in ("stream", "type_screen", "declared_days", "missing_days", "no_row_days", "source_ids"):
                value = r.get(f"{p}_{suffix}")
                months[-1][f"{p}_{suffix}"] = value if isinstance(value, (str, list)) else _n(value) if value is not None else None
            st = r.get(f"{p}_status")
            months[-1][f"{p}_status"] = st if isinstance(st, str) and st else "outside_record"
        if terra_locked and t.month in tl["months"] and tl["years"][0] <= t.year <= tl["years"][1]:
            months[-1].update(Terra_D=None, Terra_N=None, Terra_status="held_out")  # P04 G01 (app rule)
    # Rows the detections export would hold: the same quality-filtered, type-0 archive rows these counts sum,
    # less the rows the P04 lock keeps out of exports until its tests have run.
    held_rows, export_rows = _export_meta(ident, region, bbox, y0, y1, done)
    change = None
    if cal["supported"] and y0 <= 2003 and y1 >= 2021:
        change = {}
        for name, mm in (("OctNov", (10, 11)), ("AprMay", (4, 5))):
            stats = {k: hz.season_stats(rec[c], mm) for k, c in
                     (("naive", "naive"), ("naive_snpp", "naive_snpp"), ("aqua", "aqua"), ("H", "H"),
                      ("H_lo", "H_lo"), ("H_hi", "H_hi"))}
            r = {k: _ratio(v) for k, v in stats.items()}
            entry = {k: None if r[k] is None else round(r[k], 2) for k in ("naive", "naive_snpp", "aqua", "H")}
            entry["yearly"] = {k: {y: (v if np.isfinite(v) else None) for y, v in stats[k]["yearly"].items()}
                               for k in ("naive", "naive_snpp", "aqua", "H")}
            if any(r[k] is None for k in ("H", "H_lo", "H_hi")):
                entry.update(defined=False, H_interval=None, point_in_interval=None,
                             reason="No detections in the 2003–2011 season average, so a ratio is undefined here.")
            else:
                lo, hi = sorted([r["H_lo"], r["H_hi"]])
                # The interval comes from one-sided residual quantiles in some areas, so it can exclude the point.
                entry.update(defined=True, H_interval=[round(lo, 2), round(hi, 2)],
                             point_in_interval=bool(lo <= r["H"] <= hi))
            change[name] = entry
    label = region if region else "Box " + ", ".join(f"{v:g}" for v in bbox)
    day_only = _passes(cal) == ("D",)
    return {
        "status": "success", "region": label, "box": box_info, "years": [y0, y1], "model": model,
        "passes": "day passes only" if day_only else "day and night passes",
        "units": ("day-pass " if day_only else "") + "detections per month: fire pixels on satellite passes (not fires, not area)"
                 + ("; H, naive and aqua count day passes only, while <platform>_N columns are raw night counts" if day_only else ""),
        "reference": "S-NPP VIIRS 375 m, Collection 2, standard processing; nominal/high confidence; type 0",
        "calibration": cal, "months": months, "data_identity": data_identity(),
        "current_record": continuity.metadata(),
        "calendar": {"H": calendar(rec, "H", "H_flag", (y0, y1)), "aqua": calendar(rec, "aqua", "aqua_flag", (y0, y1)),
                     "naive": calendar(rec, "naive", "naive_flag", (y0, y1))},
        "comparison": compare_month(rec, month[0], month[1], (y0, y1)),
        "change": change, "latest": latest_days(region, bbox, done),
        # While rows are held out, no row count is shown: with the visible monthly columns, a count would let
        # someone work out held numbers by subtraction (Opus review of S02, 5 Nov).
        "export": {"detections_rows": None if held_rows else export_rows, "rows_held_out": bool(held_rows),
                   "detections_format": "zip" if export_rows > EXPORT_PLAIN_MAX else "csv"},
        "warnings": warnings(cal, box_info, model, change),
    }


def _n(v):
    return None if pd.isna(v) else round(float(v), 2)


def _ratio(stats: dict) -> float | None:
    v = stats.get("ratio_late_early")
    return float(v) if v is not None and np.isfinite(v) else None


def warnings(cal: dict, box_info: dict | None, model: str = MODEL_DEFAULT, change: dict | None = None) -> list[str]:
    e2 = _experiment("E02_evaluation")
    sel_model = e2["selected"]["backcast"] if e2 else None
    w = ["A detection is a fire pixel seen on one satellite pass: not a fire, not burned area, not emissions.",
         "No detection does not mean no fire: clouds, smoke and gaps between passes hide fires, and this "
         "hotspot-only record cannot tell clear-sky non-detections apart (exposure unknown).",
         "Harmonised values are S-NPP-equivalent estimates. S-NPP is the reference convention, not ground truth."]
    bridge = f" (total error {e2['bridge_test']['scores']['M1']['wape']:.1%} in Punjab, E02)" if e2 else ""
    w.append(f"The record ends in December {series.ARCHIVE_END.year} for the standard country archive; 2026 months "
             "come from the cached 2026 current supplement (area-API chunks and 7-day NRT snapshots). S-NPP stopped "
             "sending new data on 2 Nov 2026 (15:40 UTC in NOAA Update #4; 13:00 UTC in NASA's 3 Nov blog). "
             "Converted NOAA-20 passed its frozen 2026 test in Punjab (P04 G03: 5.1% total error; the earlier "
             f"test{bridge} was 4.4%) and is applied only to Punjab from Nov 2026 without an uncertainty range; "
             "May 2026 is unavailable due to FIRMS-listed missing days, Aug–Oct 2026 use untyped NRT rows, and "
             "areas outside Punjab have no tested post-S-NPP bridge.")
    if e2:
        cov = e2["temporal_test"]["interval_80_coverage"]
        if model == sel_model:
            w.append(f"Before Feb 2012 values are modelled from Aqua MODIS. In Punjab, {model}'s nominal 80% range covered "
                     f"{cov:.0%} of held-out 2012-13 months (E02), so treat ranges as too narrow.")
        else:
            w.append(f"Before Feb 2012 values are modelled from Aqua MODIS. {model}'s range was not tested on held-out "
                     f"years; the selected {sel_model}'s covered only {cov:.0%} in Punjab (E02), so treat ranges as too narrow.")
        biases = [v[model]["bias"] for v in e2["drift_diagnostic"].values() if model in v]
        if biases:
            w.append(f"The Aqua-to-S-NPP ratio drifts: applied to 2018-2025 in Punjab, the 2014-17 {model} fit "
                     f"over-predicted S-NPP by {min(biases):+.0%} to {max(biases):+.0%} a year (E02). The harmonised record "
                     "uses observed S-NPP from Feb 2012, so this affects only the modelled years.")
    w.append("'Above' or 'below' means unusual compared with this area's own normal, not a forecast or risk level.")
    if not cal["supported"]:
        w.append("This region failed the calibration support check, so no harmonised values are shown before 2012: "
                 + "; ".join(cal["reasons"]))
    cv = cal.get("cv_agreement", {}).get("model", {}).get("wape")
    if cv is not None and cv > WEAK_CV_WAPE:
        w.append(f"Weak support here: in cross-validation the modelled monthly totals missed S-NPP by {cv:.0%} of the "
                 "total (WAPE). Years before 2012 are shown, but do not rely on them for this area.")
    if cal.get("day_only_reason"):
        w.append("Night passes are left out for this area, in every series, because Aqua's night detections are too "
                 "few to calibrate (" + "; ".join(cal["day_only_reason"]) + "). Values count day-pass detections only.")
    share = cal.get("aqua_zero_snpp_positive_share")
    if share is not None and share >= 0.1:
        w.append(f"In {share:.0%} of this area's 2012-17 months Aqua detected nothing while S-NPP detected some burning. "
                 "The ratio model turns such months into zero, so modelled years can under-count here.")
    if cal.get("one_sided_interval_seasons"):
        w.append("In cross-validation the model was biased in one direction here for "
                 + ", ".join(cal["one_sided_interval_seasons"]) + " months, so the range does not contain the "
                 "modelled value for those months. Prefer the range, and treat modelled years with caution.")
    m1 = cal.get("cv_agreement", {}).get("M1", {}).get("wape")
    if model != "M1" and cv is not None and m1 is not None and m1 < cv:
        w.append(f"In this area's cross-validation the single-ratio M1 did better than {model} (error {m1:.0%} vs "
                 f"{cv:.0%} of the total). Switch to M1 to see how much the answer depends on the model.")
    wide = [n for n, v in (change or {}).items() if v.get("defined")
            and (v["H_interval"][0] <= 0 or v["H_interval"][1] / v["H_interval"][0] > WIDE_RANGE)]
    if wide:
        w.append("The range for " + " and ".join({"OctNov": "October–November", "AprMay": "April–May"}[n] for n in wide)
                 + f" here spans more than {WIDE_RANGE:g} times from its low end to its high end, so the size of any "
                 "change is very uncertain.")
    if box_info and box_info["share_inside_pakistan"] < 0.99:
        w.append(f"Only {box_info['share_inside_pakistan']:.0%} of this box is inside Pakistan; detections outside "
                 "Pakistan are not in the cached country files, so the rest of the box counts nothing.")
    return w


@lru_cache(maxsize=8)
def _experiment(name: str) -> dict | None:
    f = config.EXPERIMENTS / name / "result.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None


def evidence() -> dict:
    """Saved experiment evidence shown in the app (read from experiments/, never recomputed here)."""
    out = {key: _experiment(name) for key, name in
           (("selection", "E01_selection"), ("evaluation", "E02_evaluation"), ("sensitivity", "E03_sensitivity"))}
    e1, e2 = out["selection"], out["evaluation"]
    if not (e1 and e2):
        return {"available": False}
    keep = ("wape", "log_mae", "bias", "n_months")
    return {
        "available": True,
        "selection": {m: {k: round(v[k], 3) if isinstance(v[k], float) else v[k] for k in keep}
                      for m, v in e1["backcast"]["scores"].items()},
        "selected": e1["backcast"]["selected"],
        "temporal_test": {m: {k: round(v[k], 3) if isinstance(v[k], float) else v[k] for k in keep}
                          for m, v in e2["temporal_test"]["scores"].items()},
        "interval_coverage": round(e2["temporal_test"]["interval_80_coverage"], 2),
        "bridge_selected": e1["bridge"]["selected"],
        "bridge_test": {m: round(v["wape"], 3) for m, v in e2["bridge_test"]["scores"].items()},
        "drift": {y: {"versions": v["aqua_versions"], "M1_bias": round(v["M1"]["bias"], 3),
                      "M2_bias": round(v["M2"]["bias"], 3)} for y, v in e2["drift_diagnostic"].items()},
        "sindh": {k: {m: {"wape": round(s["wape"], 3), "bias": round(s["bias"], 3)} for m, s in v.items()}
                  for k, v in e2["geographic_test_sindh"].items() if k != "scored_months"},
        "differentiator": {s: {"naive": round(v["naive_stitch"]["ratio_late_early"], 2),
                               "harmonised": round(v["harmonised"]["ratio_late_early"], 2),
                               "aqua": round(v["aqua_only"]["ratio_late_early"], 2),
                               "interval": [round(v["harmonised_interval"]["ratio_late_early"]["lo"], 2),
                                            round(v["harmonised_interval"]["ratio_late_early"]["hi"], 2)]}
                           for s, v in e2["differentiator"].items()},
        # E03 (post-hoc, selects nothing): the Punjab Oct-Nov ratio under every frozen model.
        "sensitivity_octnov": ({m: {"ratio": round(v["OctNov"]["ratio_late_early"], 2),
                                    "interval": [round(x, 2) for x in v["OctNov"]["ratio_interval"]]}
                                for m, v in out["sensitivity"]["by_model"].items()} if out["sensitivity"] else None),
        "files": ["experiments/E01_selection/result.json", "experiments/E02_evaluation/result.json",
                  "experiments/E03_sensitivity/result.json"],
    }


EXPORT_COLS = ["time_utc", "date_utc", "platform", "instrument", "stream", "version", "daynight", "latitude", "longitude",
               "confidence_raw", "type", "type_screen", "frp", "scan", "track", "province", "source_id"]


def detection_rows(*, region=None, bbox=None, years=(FIRST_YEAR, LAST_YEAR),
                   model: str = MODEL_DEFAULT) -> tuple[pd.DataFrame, tuple[str, ...]]:
    """Observation-level rows (quality-filtered, type 0 where available, archive + 2026 supplement) and the passes the record uses."""
    if model not in MODELS_OFFERED:
        raise AnalysisError(f"Model must be one of {MODELS_OFFERED}")
    if bbox is not None:
        bbox, region = tuple(check_box(bbox)["bbox"]), None
    elif region not in ("Pakistan",) + SUPPORTED_PROVINCES:
        raise AnalysisError("Choose Pakistan, a province, or a box")
    y0, y1 = (int(v) for v in years)
    if not (FIRST_YEAR <= y0 <= y1 <= LAST_YEAR):
        raise AnalysisError(f"Years must satisfy {FIRST_YEAR} <= from <= to <= {LAST_YEAR}")
    data_identity()
    parts = []
    held_any = False
    if y0 < continuity.FIRST_YEAR:
        q = series.select(detections(), region=region, bbox=bbox)
        q = q[(q.year >= y0) & (q.year <= min(y1, continuity.FIRST_YEAR - 1))]
        held = held_rows_mask(q, p04_lock_state())
        held_any = bool(held.any())
        q = q[~held].copy()  # P04 test-window rows stay out until those tests run
        q["type_screen"] = np.where(q["type"].notna(), "type0", "untyped")
        parts.append(q)
    if y1 >= continuity.FIRST_YEAR:
        cur = continuity.selection(region=region, bbox=bbox, years=(max(y0, continuity.FIRST_YEAR), y1)).copy()
        cur["type_screen"] = np.where(cur["type"].notna(), "type0", "untyped")
        parts.append(cur)
    if parts:
        out = pd.concat(parts, ignore_index=True) if len(parts) > 1 else parts[0]
    else:
        out = series.select(detections(), region=region, bbox=bbox).iloc[0:0].copy()
        out["type_screen"] = pd.Series(dtype=str)
    out.attrs["rows_held_out"] = held_any
    return out, _passes(_inputs(region, bbox, model)[1])


def detections_csv_chunks(q: pd.DataFrame, passes: tuple[str, ...], *, extra: dict | None = None,
                          chunk: int = 100_000):
    """The export as CSV bytes, one block of rows at a time, so a large selection is never copied whole."""
    if q.empty:
        yield pd.DataFrame(columns=EXPORT_COLS + ["used_in_harmonised_passes", *(extra or {})]).to_csv(
            index=False).encode("utf-8")
        return
    for i in range(0, len(q), chunk):
        part = q.iloc[i:i + chunk][EXPORT_COLS].copy()
        part["used_in_harmonised_passes"] = part["daynight"].isin(passes)
        if extra:
            part = part.assign(**extra)
        yield part.to_csv(index=False, header=i == 0).encode("utf-8")


def detections_csv(**kw) -> pd.DataFrame:
    """The whole export as one table (small selections and tests)."""
    q, passes = detection_rows(**kw)
    out = q[EXPORT_COLS].copy()
    out["used_in_harmonised_passes"] = out["daynight"].isin(passes)
    return out


def meta() -> dict:
    identity = data_identity()
    rep = ingest_report()
    cur = continuity.metadata()
    sel = json.loads((config.EXPERIMENTS / "E01_selection" / "selection.json").read_text(encoding="utf-8"))
    return {"regions": ["Pakistan", *SUPPORTED_PROVINCES], "years": [FIRST_YEAR, LAST_YEAR],
            "models": list(MODELS_OFFERED), "default_model": MODEL_DEFAULT, "selected_in_E01": sel["backcast"]["selected"],
            "rows": rep["rows"], "built_utc": rep["built_utc"], "detections_sha256": rep["output_sha256"],
            "files": len(rep["files"]), "data_identity": identity,
            "current_record": {"schema": cur["schema"], "acquisition_start": cur["acquisition_start"],
                               "acquisition_end": cur["acquisition_end"],
                               "api_acquisition_end": cur["api_acquisition_end"],
                               "latest_observed_acquisition_utc": cur["latest_observed_acquisition_utc"],
                               "latest_retrieved_utc": cur["latest_retrieved_utc"],
                               "supported_years": cur["supported_years"], "files": len(cur["files"])},
            "sources": "NASA FIRMS country archive (MODIS MCD14ML, provider heading C6.1, file versions 6.2, 6.03 and "
                       "61.03; VIIRS 375 m C2 VNP14IMG, VJ114IMG), 2026 cached FIRMS area-API & South Asia 7-day NRT "
                       "supplement (MCD14DL, VNP14IMGTDL_NRT, VJ114IMGTDL_NRT, VJ214IMGTDL_NRT), and geoBoundaries gbOpen PAK ADM1 (2019)",
            "export_plain_max": EXPORT_PLAIN_MAX,
            "status": "Local research prototype. Pre-event work with true dates. Cross-sensor agreement only; "
                      "no independent ground-truth validation."}
