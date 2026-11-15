"""Validated ingestion of the cached FIRMS files into one tidy detection table.

Input: raw CSVs listed in data/manifest.json (hash-checked before reading).
Output: data/processed/pak_detections.parquet (rebuilt, git-ignored) and
reports/c08/ingest_report.json (per-file audit, committed).

Every valid row is kept with flags (quality_pass, type0, province), so later
steps filter explicitly and the app can show what a filter removed. Rows that
break the data contract are dropped and counted by reason. Only exact
duplicate deliveries are removed; repeat detections on other passes are real
observations and stay. See docs/DATA_CONTRACT.md.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import acquire, boundaries, config

SCHEMA_VERSION = "c08-detections-1"
DETECTIONS = config.PROCESSED / "pak_detections.parquet"
INGEST_REPORT = config.REPORTS / "ingest_report.json"

# FIRMS satellite codes differ between the archive and NRT files.
PLATFORM_CODES = {"Terra": "Terra", "T": "Terra", "Aqua": "Aqua", "A": "Aqua",
                  "N": "SNPP", "N20": "NOAA20", "N21": "NOAA21"}
INSTRUMENT_OF = {"Terra": "MODIS", "Aqua": "MODIS", "SNPP": "VIIRS", "NOAA20": "VIIRS", "NOAA21": "VIIRS"}
EXPECTED_PLATFORMS = {"modis": {"Terra", "Aqua"}, "viirs-snpp": {"SNPP"}, "viirs-jpss1": {"NOAA20"},
                      "MODIS_NRT": {"Terra", "Aqua"}, "SNPP_NRT": {"SNPP"},
                      "NOAA20_NRT": {"NOAA20"}, "NOAA21_NRT": {"NOAA21"}}
# NRT VIIRS files spell confidence out; the archive uses one letter.
VIIRS_CONFIDENCE = {"l": "l", "n": "n", "h": "h", "low": "l", "nominal": "n", "high": "h"}
REQUIRED = ("latitude", "longitude", "scan", "track", "acq_date", "acq_time",
            "satellite", "confidence", "version", "frp", "daynight")
# Generous box around Pakistan; finer assignment is the province polygon test.
PAK_BBOX = (60.0, 23.0, 78.5, 37.5)

# Output columns and dtypes: the data contract (docs/DATA_CONTRACT.md).
COLUMNS = {
    "platform": "category", "instrument": "category", "stream": "category", "version": "category",
    "source_id": "category", "time_utc": "datetime64[ns, UTC]", "date_utc": "datetime64[ns]",
    "year": "int16", "month": "int8", "latitude": "float64", "longitude": "float64",
    "confidence_raw": "category", "quality_pass": "bool", "type": "Int8", "type0": "bool",
    "daynight": "category", "frp": "float32", "scan": "float32", "track": "float32",
    "bt_mir": "float32", "bt_tir": "float32", "province": "category",
}


class IngestError(ValueError):
    pass


def parse_frame(raw: pd.DataFrame, *, source: str, source_id: str, stream: str,
                file_year: int | None) -> tuple[pd.DataFrame, dict]:
    """Validate one raw FIRMS table (all columns as strings). Returns (rows, audit)."""
    missing = [c for c in REQUIRED if c not in raw.columns]
    if missing:
        raise IngestError(f"{source_id}: missing FIRMS columns {missing}")
    d = raw.copy()
    n_raw = len(d)
    num = {c: pd.to_numeric(d[c], errors="coerce") for c in ("latitude", "longitude", "frp", "scan", "track")}
    t = d["acq_time"].astype(str).str.zfill(4)
    hh = pd.to_numeric(t.str[:2], errors="coerce")
    mm = pd.to_numeric(t.str[2:], errors="coerce")
    good_time = t.str.fullmatch(r"\d{4}") & hh.between(0, 23) & mm.between(0, 59)
    time_utc = pd.to_datetime(d["acq_date"] + " " + t, format="%Y-%m-%d %H%M", errors="coerce", utc=True)
    platform = d["satellite"].map(PLATFORM_CODES)
    instrument = platform.map(INSTRUMENT_OF)
    if "instrument" in d.columns:  # archive files carry it; it must agree with the satellite code
        instrument = instrument.where(d["instrument"].str.upper().eq(instrument))
    conf = d["confidence"].astype(str).str.strip().str.lower()
    conf_modis = pd.to_numeric(conf, errors="coerce")
    conf_viirs = conf.map(VIIRS_CONFIDENCE)
    is_modis = instrument.eq("MODIS")
    is_viirs = instrument.eq("VIIRS")
    if "type" in d.columns:
        ftype = pd.to_numeric(d["type"], errors="coerce")
        bad_type = ~ftype.isin([0, 1, 2, 3])
    else:
        ftype = pd.Series(np.nan, index=d.index)
        bad_type = pd.Series(False, index=d.index)

    w, s, e, n = PAK_BBOX
    checks = {  # first failing reason is recorded for each rejected row
        "bad_platform": platform.isna() | ~platform.isin(EXPECTED_PLATFORMS[source]) | instrument.isna(),
        "bad_coordinates": ~(np.isfinite(num["latitude"]) & np.isfinite(num["longitude"])),
        "outside_pakistan_box": ~(num["longitude"].between(w, e) & num["latitude"].between(s, n)),
        "bad_time": ~good_time | time_utc.isna(),
        "date_outside_file_year": (time_utc.dt.year != file_year) if file_year else pd.Series(False, index=d.index),
        "bad_confidence": ~((is_modis & conf_modis.between(0, 100)) | (is_viirs & conf_viirs.notna())),
        "bad_daynight": ~d["daynight"].isin(["D", "N"]),
        "bad_measurement": ~(np.isfinite(num["frp"]) & num["frp"].ge(0) & num["scan"].gt(0) & num["track"].gt(0)),
        "bad_version": d["version"].astype(str).str.strip().eq(""),
        "bad_type": bad_type,
    }
    rejected = pd.Series(False, index=d.index)
    reasons = {}
    for name, fail in checks.items():
        fail = fail.fillna(True) & ~rejected
        reasons[name] = int(fail.sum())
        rejected |= fail
    keep = ~rejected

    out = pd.DataFrame({
        "platform": platform[keep], "instrument": instrument[keep], "stream": stream,
        "version": d.loc[keep, "version"].astype(str), "source_id": source_id,
        "time_utc": time_utc[keep], "latitude": num["latitude"][keep], "longitude": num["longitude"][keep],
        "confidence_raw": conf[keep].where(is_modis[keep], conf_viirs[keep]),
        "type": ftype[keep], "daynight": d.loc[keep, "daynight"],
        "frp": num["frp"][keep], "scan": num["scan"][keep], "track": num["track"][keep],
        "bt_mir": pd.to_numeric(d.loc[keep, "brightness" if "brightness" in d else "bright_ti4"], errors="coerce"),
        "bt_tir": pd.to_numeric(d.loc[keep, "bright_t31" if "bright_t31" in d else "bright_ti5"], errors="coerce"),
    })
    # Product-specific quality rules; neither confidence field is a probability.
    out["quality_pass"] = np.where(out["instrument"].eq("MODIS"),
                                   pd.to_numeric(out["confidence_raw"], errors="coerce").ge(config.MODIS_MIN_CONFIDENCE),
                                   out["confidence_raw"].isin(config.VIIRS_KEEP_CONFIDENCE))
    # Type 0 = presumed vegetation fire. NRT files have no type field, so their rows cannot be screened.
    out["type0"] = out["type"].isna() | out["type"].eq(0)

    # Exact duplicate deliveries only (Protocol P01 section 4); repeat passes are kept.
    key = ["platform", "time_utc", "latitude", "longitude", "version"]
    dup_key = out.duplicated(key)
    dup_full = out.duplicated()
    out = out[~dup_key]
    audit = {"raw_rows": n_raw, "rejected": reasons, "rejected_total": int(rejected.sum()),
             "exact_duplicates_removed": int(dup_key.sum()),
             "full_row_duplicates": int(dup_full.sum()), "rows": len(out)}
    return out, audit


def _git_head() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=config.ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return None


def code_state() -> dict:
    """Commit, whether c08/ has uncommitted changes, and a hash of the c08 sources that actually ran.

    A commit id alone does not identify the code when the tree is dirty (the 2 Nov
    E00-E03 runs recorded edee712 while their modules were not yet committed).
    """
    h = hashlib.sha256()
    for f in sorted((config.ROOT / "c08").rglob("*.py")):
        h.update(f.relative_to(config.ROOT).as_posix().encode())
        h.update(f.read_bytes().replace(b"\r\n", b"\n"))  # same hash whatever git's line-ending setting
    try:
        dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", "c08"], cwd=config.ROOT,
                                    capture_output=True, text=True, check=True).stdout.strip())
    except Exception:
        dirty = None
    return {"revision": _git_head(), "c08_uncommitted_changes": dirty, "c08_sources_sha256": h.hexdigest()}


def protocol_state(rel: str) -> dict:
    """The protocol a result was computed under: its path and a hash of its text.

    Added 3 Nov 2026 after CHECK REPORT P02: git alone could not show that the P02
    change log was written before the results, and no result file recorded which
    protocol text it followed.
    """
    text = (config.ROOT / rel).read_bytes().replace(b"\r\n", b"\n")
    return {"protocol": rel, "protocol_sha256": hashlib.sha256(text).hexdigest()}


def build(*, log=print) -> tuple[pd.DataFrame, dict]:
    """Hash-check every cached FIRMS file in the manifest, validate, assign provinces, save."""
    m = acquire.load_manifest()
    frames, audits = [], []
    for fid, entry in sorted(m["files"].items()):
        if entry.get("kind") not in ("firms_country_annual", "firms_nrt_7d_region"):
            continue
        path = config.ROOT / entry["path"]
        if not path.is_file():
            raise IngestError(f"{fid}: cached file missing ({entry['path']}); run python -m c08.acquire")
        digest = acquire.sha256_file(path)
        if digest != entry["sha256"]:
            raise IngestError(f"{fid}: SHA-256 differs from manifest; the raw file changed")
        raw = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        if len(raw) != entry["rows"]:
            raise IngestError(f"{fid}: {len(raw)} rows read, manifest says {entry['rows']}")
        stream = "standard" if entry["kind"] == "firms_country_annual" else "nrt"
        frame, audit = parse_frame(raw, source=entry["source"], source_id=fid, stream=stream,
                                   file_year=entry.get("year"))
        frames.append(frame)
        audits.append({"id": fid, "path": entry["path"], "sha256": digest, "stream": stream,
                       "url": entry["url"], "retrieved_utc": entry["retrieved_utc"], **audit})
        log(f"{fid}: {audit['raw_rows']} raw, {audit['rejected_total']} rejected, "
            f"{audit['exact_duplicates_removed']} duplicates, {audit['rows']} kept")

    d = pd.concat(frames, ignore_index=True)
    d["province"] = boundaries.province_of(d["longitude"].to_numpy(), d["latitude"].to_numpy())
    # NRT files cover all of South Asia; keep only points inside a Pakistan province.
    outside_nrt = d["stream"].eq("nrt") & d["province"].eq("")
    d = d[~outside_nrt].copy()
    d["date_utc"] = d["time_utc"].dt.tz_localize(None).dt.floor("D")
    d["year"] = d["time_utc"].dt.year
    d["month"] = d["time_utc"].dt.month
    d = d[list(COLUMNS)].astype(COLUMNS).sort_values(["time_utc", "platform"]).reset_index(drop=True)

    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    d.to_parquet(DETECTIONS, index=False)
    bdy = {k: v for k, v in m["files"].items() if v.get("kind") == "boundary_geojson"}
    report = {
        "schema": SCHEMA_VERSION, "built_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "code_revision": _git_head(), "output": DETECTIONS.relative_to(config.ROOT).as_posix(),
        "output_sha256": acquire.sha256_file(DETECTIONS), "rows": len(d),
        "nrt_rows_outside_pakistan_dropped": int(outside_nrt.sum()),
        "standard_rows_outside_all_provinces": int((d["stream"].eq("standard") & d["province"].eq("")).sum()),
        "rows_by_platform_stream": {f"{k[0]}/{k[1]}": int(v) for k, v in
                                    d.groupby(["platform", "stream"], observed=True).size().items()},
        "rows_by_province": {k or "(outside polygons)": int(v) for k, v in d["province"].value_counts().items()},
        "quality_pass_share": {k: round(float(v), 4) for k, v in
                               d.groupby("platform", observed=True)["quality_pass"].mean().items()},
        "type_counts": {f"{k[0]}/type{'NA' if pd.isna(k[1]) else int(k[1])}": int(v) for k, v in
                        d.groupby(["platform", "type"], observed=True, dropna=False).size().items()},
        "boundaries": [{"id": k, "sha256": v["sha256"], "license": v.get("license"),
                        "source": v.get("source"), "year_represented": v.get("year_represented")}
                       for k, v in bdy.items()],
        "files": audits,
    }
    config.REPORTS.mkdir(parents=True, exist_ok=True)
    INGEST_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return d, report


def load() -> pd.DataFrame:
    """Read the processed detection table, rebuilding it if absent."""
    if not DETECTIONS.is_file():
        return build(log=lambda *_: None)[0]
    return pd.read_parquet(DETECTIONS)


if __name__ == "__main__":
    _, rep = build()
    print(json.dumps({k: v for k, v in rep.items() if k != "files"}, indent=1))
