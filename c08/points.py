"""Read-only display path for the map: the observed detections of one month, and facts about each area.

The rows are exactly the ones the detections export gives for the same area (c08.analysis.detection_rows),
cut to one calendar month. Historical rows are standard/type 0; the current supplement names each row's
actual stream and type screen, including untyped NRT. Nothing is modelled
here and no point is moved: there are no "harmonised locations". Counts stay per satellite and per pass.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from . import analysis, boundaries, continuity, series

PLATFORMS = ("Terra", "Aqua", "SNPP", "NOAA20", "NOAA21")
LABELS = {"Terra": "Terra MODIS", "Aqua": "Aqua MODIS", "SNPP": "S-NPP VIIRS", "NOAA20": "NOAA-20 VIIRS",
          "NOAA21": "NOAA-21 VIIRS"}
PRODUCTS = {"Terra": "MODIS Collection 6.1 active fire (MCD14ML), 1 km", "Aqua": "MODIS Collection 6.1 active fire (MCD14ML), 1 km",
            "SNPP": "VIIRS 375 m active fire, Collection 2 (VNP14IMG)", "NOAA20": "VIIRS 375 m active fire, Collection 2 (VJ114IMG)",
            "NOAA21": "VIIRS 375 m active fire, Collection 2 (VJ214IMG)"}
EXTENT = (60.0, 23.0, 78.5, 37.5)  # the map's supported extent: west, south, east, north
ROW_KIND = ("observation: one fire pixel on one satellite pass (quality filtered; stream and type screen stated per row); "
            "the same rows as the detections export for this area and month")


def _area(region, bbox):
    if bbox is not None:
        return None, tuple(analysis.check_box(bbox)["bbox"])
    if region not in ("Pakistan",) + analysis.SUPPORTED_PROVINCES:
        raise analysis.AnalysisError("Choose Pakistan, a province, or a box")
    return region, None


@lru_cache(maxsize=2)
def _spans(data_identity: str) -> dict:
    return series.record_spans(analysis.detections())


def _record(start: pd.Timestamp, end: pd.Timestamp, data_identity: str, current: dict | None = None) -> dict:
    """Historical record spans or actual cached current support; neither establishes clear-sky exposure."""
    out = {}
    spans = _spans(data_identity)
    plans = (current or {}).get("selected_months", [])
    for p in PLATFORMS:
        if start.year >= continuity.FIRST_YEAR:
            mine = [s for s in plans if s["platform"] == p]
            plan = next((s for s in mine if s["month"] == start.strftime("%Y-%m")), None)
            first = str(spans[p][0].date()) if p in spans else min((s["declared_start"] for s in mine), default=None)
            last = max((s["declared_end"] for s in mine), default=str(spans[p][1].date()) if p in spans else None)
            status = ("outside_record" if not plan else "unavailable" if "no_platform_rows" in plan["flags"] else
                      "partial_record" if plan["declared_days"] < plan["days_in_month"] else "in_record")
            out[p] = {"first": first, "last": last, "status": status, "support": plan,
                      "note": ("No cached product for this platform and month; missing, not zero." if not plan else
                               f"Cached {plan['stream']} {plan['type_screen']} observations: "
                               f"{plan['declared_start']} to {plan['declared_end']}; {plan['status']}. Exposure unknown.")}
            continue
        if p not in spans:
            out[p] = {"first": None, "last": None, "status": "outside_record"}
            continue
        first, last = spans[p]
        status = ("outside_record" if end < first or start > last else
                  "partial_record" if first > start or last < end else "in_record")
        out[p] = {"first": str(first.date()), "last": str(last.date()), "status": status}
    return out


def month_points(*, region="Punjab", bbox=None, year: int, month: int) -> dict:
    """Every exported detection of one month in the area, as columns (one entry per detection)."""
    region, bbox = _area(region, bbox)
    try:
        year, month = int(year), int(month)
    except (TypeError, ValueError):
        raise analysis.AnalysisError("The month needs a year and a month number") from None
    if not (analysis.FIRST_YEAR <= year <= analysis.LAST_YEAR and 1 <= month <= 12):
        raise analysis.AnalysisError(f"Choose a month from {analysis.FIRST_YEAR} to {analysis.LAST_YEAR}")
    data_identity = analysis.data_identity()
    q, passes = analysis.detection_rows(region=region, bbox=bbox, years=(year, year))
    q = q[(q["year"] == year) & (q["month"] == month)]
    rows_held_out = bool(q.attrs.get("rows_held_out"))
    q = q[q["platform"].isin(PLATFORMS)].sort_values("time_utc", kind="stable")
    plat = q["platform"].astype(str)
    versions = sorted(q["version"].astype(str).unique())
    sources = sorted(q["source_id"].astype(str).unique())
    streams = sorted(q["stream"].astype(str).unique())
    type_screen = (q["type_screen"].astype(str) if "type_screen" in q else
                   pd.Series(np.where(q["type"].notna(), "type0", "untyped"), index=q.index))
    current = continuity.metadata() if year >= continuity.FIRST_YEAR else None
    files = {f["id"]: f for f in [*analysis.ingest_report()["files"], *(current or {}).get("files", [])]}
    source_details = [{k: files[s].get(k) for k in ("id", "path", "sha256", "retrieved_utc", "stream",
                                                   "declared_start", "declared_end", "has_type")}
                      if s in files else {"id": s} for s in sources]
    stream_note = ", ".join("near-real-time (NRT)" if s == "nrt" else "standard processing" if s == "standard" else s
                            for s in streams) or "no observed rows"
    screen_note = ("type 0 where a type field is available; untyped rows have no type screen" if "untyped" in set(type_screen)
                   else "type 0 (presumed vegetation burning)" if len(q) else "no type screening can be inferred from an empty result")
    source_summary = f"NASA FIRMS {stream_note}; quality rule; {screen_note}."
    counts = {p: {"D": 0, "N": 0} for p in PLATFORMS}
    for (p, dn), n in q.groupby([plat, q["daynight"].astype(str)]).size().items():
        counts[p][dn] = int(n)
    t = q["time_utc"]
    start = pd.Timestamp(year=year, month=month, day=1, tz="UTC")
    n_days = (start + pd.offsets.MonthEnd(0)).day
    return {
        "region": region or "Selected rectangle", "bbox": list(bbox) if bbox else None,
        "month": f"{year}-{month:02d}", "days_in_month": int(n_days), "time_standard": "UTC",
        "rows": int(len(q)), "rows_held_out": rows_held_out, "row_kind": ROW_KIND, "data_identity": data_identity,
        "platforms": list(PLATFORMS), "labels": LABELS, "products": PRODUCTS, "counts": counts,
        "versions": versions, "sources": sources, "source_details": source_details, "streams": streams,
        "source_summary": source_summary, "harmonised_passes": list(passes),
        "record": _record(start.tz_localize(None), (start + pd.offsets.MonthEnd(0)).tz_localize(None).normalize(),
                          data_identity, current),
        "lon": np.round(q["longitude"].to_numpy(), 5).tolist(),
        "lat": np.round(q["latitude"].to_numpy(), 5).tolist(),
        "minute": ((t - start).dt.total_seconds() // 60).astype(int).tolist(),  # minutes after the month began (UTC)
        "p": plat.map({p: i for i, p in enumerate(PLATFORMS)}).astype(int).tolist(),
        "dn": (q["daynight"].astype(str) == "N").astype(int).tolist(),  # 0 day pass, 1 night pass
        "frp": [None if pd.isna(v) else round(float(v), 1) for v in q["frp"]],
        "conf": q["confidence_raw"].astype(str).tolist(),
        "scan": [None if pd.isna(v) else round(float(v), 2) for v in q["scan"]],
        "track": [None if pd.isna(v) else round(float(v), 2) for v in q["track"]],
        "ver": q["version"].astype(str).map({v: i for i, v in enumerate(versions)}).astype(int).tolist(),
        "src": q["source_id"].astype(str).map({v: i for i, v in enumerate(sources)}).astype(int).tolist(),
        "stm": q["stream"].astype(str).map({v: i for i, v in enumerate(streams)}).astype(int).tolist(),
        "type_screen": type_screen.tolist(),
        "type": [None if pd.isna(v) else int(v) for v in q["type"]],
        "notes": ["Each point is one fire pixel on one satellite pass at the product's reported pixel centre. It is not "
                  "a fire, a burned area or a footprint.",
                  "Satellites are shown and counted separately. Their counts are never added into one total, and a "
                  "point on two satellites is two detections, not two fires.",
                  "Confidence is the product's own field: MODIS 0-100 (30 or more kept), VIIRS low/nominal/high "
                  "(nominal and high kept). Neither is a probability.", source_summary,
                  "Current-period support names requested dates, provider gaps and days without platform rows; "
                  "it is not a clear-sky exposure denominator. NOAA-21 is shown only in its own raw units and never enters H."],
    }


@lru_cache(maxsize=1)
def areas() -> dict:
    """Bounds, size and centre of each selectable area (geoBoundaries ADM1 polygons, full resolution)."""
    from pyproj import Geod
    from shapely.ops import unary_union

    geod = Geod(ellps="WGS84")
    shapes = dict(boundaries.provinces())
    shapes["Pakistan"] = unary_union(list(shapes.values()))
    out = {}
    for name, g in shapes.items():
        w, s, e, n = g.bounds
        c = g.representative_point()
        out[name] = {"bounds": [round(w, 4), round(s, 4), round(e, 4), round(n, 4)],
                     "area_km2": round(abs(geod.geometry_area_perimeter(g)[0]) / 1e6),
                     "centre": [round(c.x, 4), round(c.y, 4)]}
    return {"areas": out, "extent": list(EXTENT),
            "area_method": "geodesic area on the WGS84 ellipsoid of the geoBoundaries gbOpen PAK ADM1 (2019) polygons",
            "note": "Area is the polygon's size, not the land that was observed; it does not correct for sampling or "
                    "sensor sensitivity."}


def box_area_km2(bbox) -> float:
    from pyproj import Geod
    from shapely.geometry import box

    w, s, e, n = map(float, bbox)
    return round(abs(Geod(ellps="WGS84").geometry_area_perimeter(box(w, s, e, n))[0]) / 1e6)
