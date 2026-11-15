"""Pakistan province boundaries (geoBoundaries gbOpen PAK ADM1).

The full-resolution file is used for assigning detections to provinces; the
simplified file is used only for drawing the map. Both are raw inputs under
data/raw/boundaries/, recorded in the manifest with hashes; the licence and
source are copied from the geoBoundaries API response, not assumed.
"""
from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import requests
import shapely
from shapely.geometry import shape

from . import acquire, config

GB_API = "https://www.geoboundaries.org/api/current/gbOpen/PAK/ADM1/"
FULL = config.RAW_BOUNDARIES / "pak_adm1.geojson"
SIMPLE = config.RAW_BOUNDARIES / "pak_adm1_simplified.geojson"
META = config.RAW_BOUNDARIES / "pak_adm1_source.json"


def fetch() -> dict:
    """Download both boundary files once and record them in the manifest."""
    s = acquire._session()
    r = acquire._retry(lambda: s.get(GB_API, timeout=60))
    r.raise_for_status()
    meta = r.json()
    config.RAW_BOUNDARIES.mkdir(parents=True, exist_ok=True)
    m = acquire.load_manifest()
    for key, url, path in (("gjDownloadURL", meta["gjDownloadURL"], FULL),
                           ("simplifiedGeometryGeoJSON", meta["simplifiedGeometryGeoJSON"], SIMPLE)):
        r = acquire._retry(lambda: s.get(url, timeout=120))
        r.raise_for_status()
        path.write_bytes(r.content)
        m["files"][f"boundaries/{path.name}"] = {
            "id": f"boundaries/{path.name}", "url": url, "path": path.relative_to(config.ROOT).as_posix(),
            "kind": "boundary_geojson", "bytes": len(r.content), "sha256": acquire.sha256_file(path),
            "retrieved_utc": acquire._now_utc(), "product": "geoBoundaries gbOpen PAK ADM1",
            "license": meta.get("boundaryLicense"), "source": meta.get("boundarySource"),
            "year_represented": meta.get("boundaryYearRepresented"),
            "citation": "Runfola, D. et al. (2020) geoBoundaries: A global database of political "
                        "administrative boundaries. PLoS ONE 15(4): e0231866.",
        }
    META.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    acquire.save_manifest(m)
    provinces.cache_clear()
    return meta


@lru_cache(maxsize=1)
def provinces() -> dict[str, object]:
    """Province name -> shapely geometry (full resolution)."""
    gj = json.loads(FULL.read_text(encoding="utf-8"))
    out = {}
    for f in gj["features"]:
        name = f["properties"].get("shapeName")
        out[name] = shapely.make_valid(shape(f["geometry"]))
    return out


def province_of(lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    """Vectorised point-in-polygon; returns province name or '' for points outside all."""
    out = np.full(len(lon), "", dtype=object)
    for name, geom in provinces().items():
        shapely.prepare(geom)
        hit = shapely.contains_xy(geom, lon, lat) & (out == "")
        out[hit] = name
    return out


def simplified_geojson() -> dict:
    return json.loads(SIMPLE.read_text(encoding="utf-8"))
