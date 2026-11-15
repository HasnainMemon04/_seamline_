"""Monthly detected-burning-activity counts per region, platform and pass.

A count is the number of quality-filtered, type-0 FIRMS detections (fire pixels
on satellite passes) in a region during a UTC calendar month. Platforms are
never summed here. Each platform-month also carries a coverage status, so a
zero inside the record is "no retained detection, exposure unknown" and a month
outside the record is missing, never zero.
"""
from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import pandas as pd

from . import config

PLATFORMS = ("Terra", "Aqua", "SNPP", "NOAA20", "NOAA21")
PROVIDER_NAMES = {"Terra (MODIS)": "Terra", "Aqua (MODIS)": "Aqua", "Suomi NPP (VIIRS)": "SNPP",
                  "NOAA-20 (VIIRS)": "NOAA20", "NOAA-21 (VIIRS)": "NOAA21"}
MISSING_DATES = config.ROOT / "research" / "metadata" / "provider_missing_dates.json"
# Archive files run to the end of their last year; ARCHIVE_END is the last cached day.
ARCHIVE_END = pd.Timestamp("2025-12-31")


class SelectionError(ValueError):
    pass


@lru_cache(maxsize=1)
def provider_missing() -> pd.DataFrame:
    """FIRMS-reported missing processing days (global), standard and NRT streams."""
    rows = json.loads(MISSING_DATES.read_text(encoding="utf-8"))
    d = pd.DataFrame(rows)
    d["platform"] = d["satellite"].map(PROVIDER_NAMES)
    d["date"] = pd.to_datetime(d["date"])
    d["stream"] = d["stream"].str.lower()
    return d[["platform", "stream", "date"]].dropna()


def record_spans(d: pd.DataFrame, stream: str = "standard") -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    """First and last day each platform's cached record covers, per stream."""
    q = d[d["stream"] == stream]
    out = {}
    for p, g in q.groupby("platform", observed=True):
        first = g["date_utc"].min()
        last = ARCHIVE_END if stream == "standard" else g["date_utc"].max()
        out[str(p)] = (first, last)
    return out


def select(d: pd.DataFrame, *, region: str | None = None, bbox: tuple | None = None,
           stream: str = "standard", quality: bool = True, type0: bool = True) -> pd.DataFrame:
    """Rows for one province ("Pakistan" = every row in the country files) or a lon/lat box."""
    mask = d["stream"].eq(stream)
    if quality:
        mask &= d["quality_pass"]
    if type0:
        mask &= d["type0"]
    if bbox is not None:
        w, s, e, n = map(float, bbox)
        if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
            raise SelectionError("Use west < east and south < north in degrees")
        mask &= d["longitude"].between(w, e) & d["latitude"].between(s, n)
    elif region and region != "Pakistan":
        if region not in set(d["province"].cat.categories):
            raise SelectionError(f"Unknown province {region!r}")
        mask &= d["province"].eq(region)
    return d[mask]


def monthly(rows: pd.DataFrame, spans: dict, *, start: str = "2000-11", end: str = "2025-12",
            stream: str = "standard") -> pd.DataFrame:
    """Long table: month, platform, daynight, count, status, record_days, missing_days."""
    months = pd.period_range(start, end, freq="M")
    miss = provider_missing()
    miss = miss[miss["stream"] == stream]
    counts = (rows.assign(m=rows["date_utc"].dt.to_period("M"))
              .groupby(["m", "platform", "daynight"], observed=True).size())
    out = []
    for p, (first, last) in spans.items():
        mdates = miss.loc[miss["platform"] == p, "date"]
        for mo in months:
            m0, m1 = mo.start_time.normalize(), mo.end_time.normalize()
            lo, hi = max(m0, first), min(m1, last)
            rec = max(0, (hi - lo).days + 1)
            ndays = (m1 - m0).days + 1
            nmiss = int(((mdates >= lo) & (mdates <= hi)).sum()) if rec else 0
            if rec == 0:
                status = "outside_record"
            elif rec < ndays:
                status = "partial_record"
            elif nmiss:
                status = "provider_missing_days"
            else:
                status = "complete"
            for dn in ("D", "N"):
                c = counts.get((mo, p, dn), 0) if rec else np.nan
                out.append((mo.start_time, p, dn, c, status, rec, nmiss))
    t = pd.DataFrame(out, columns=["month", "platform", "daynight", "count", "status", "record_days", "missing_days"])
    return t.sort_values(["month", "platform", "daynight"]).reset_index(drop=True)


def wide(series: pd.DataFrame) -> pd.DataFrame:
    """One row per month: <platform>_<D|N> counts plus <platform>_status."""
    c = series.pivot_table(index="month", columns=["platform", "daynight"], values="count", aggfunc="first")
    c.columns = [f"{p}_{dn}" for p, dn in c.columns]
    s = series.drop_duplicates(["month", "platform"]).pivot(index="month", columns="platform", values="status")
    s.columns = [f"{p}_status" for p in s.columns]
    return c.join(s)
