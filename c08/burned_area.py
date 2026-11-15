"""Protocol P02 D3: MODIS burned area (MCD64A1 Collection 6.1) for Punjab, October-November 2003-2025.

python -m c08.burned_area check     # token present? reader installed? disk free? (prints no secret)
python -m c08.burned_area fetch     # download, hash, crop to Punjab, delete each original
python -m c08.burned_area analyse   # F03: yearly burned area and the P01 section 8 statistics, run once

A burn scar stays visible for days, so unlike hotspots this does not depend on
the time of day of burning. It misses small fields, so it is a cross-check, not
ground truth. Files come from NASA LP DAAC (found through the public CMR search),
because LAADS sends token downloads to an interactive licence page. The Earthdata token comes from EARTHDATA_TOKEN (environment, or the
git-ignored local env file) and is never printed, logged or stored elsewhere.
Because drive C: is nearly full, each HDF file is deleted after its Punjab crop
(the "Burn Date" layer, unchanged values) is saved; its URL, size and SHA-256 are
kept in data/burned_area_manifest.json, so a re-download can be verified.
"""
from __future__ import annotations

import codecs
import json
import os
import shutil
import sys
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import requests
import shapely

from . import acquire, boundaries, config, ingest

CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"  # public search; files come from LP DAAC
PUNJAB_BBOX = "69.3,27.7,75.4,34.1"
TILES = ("h23v05", "h24v05", "h24v06")  # h23v06 has no Punjab pixels (PROTOCOL_P02 change log)
YEARS = range(2003, 2026)
MONTHS = (10, 11)
RAW = config.DATA / "raw" / "burned_area"
MANIFEST = config.DATA / "burned_area_manifest.json"
OUT = config.EXPERIMENTS / "P02_F03_burned_area"
R_EARTH = 6371007.181
TILE_M = 1111950.5197665
N_PIX = 2400
PIXEL_KM2 = (TILE_M / N_PIX / 1000) ** 2  # about 0.2147 km2 per 463 m pixel


def _env_lines() -> list[str]:
    """Lines of the git-ignored local env file, whatever encoding Notepad saved it in."""
    f = config.ROOT / ".env"
    if not f.is_file():
        return []
    raw = f.read_bytes()
    boms = (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)
    text = raw.decode("utf-16") if raw[:2] in boms else raw.decode("utf-8-sig", errors="replace")
    return text.splitlines()


def _key(line: str) -> str:
    k = line.partition("=")[0].strip()
    return k[7:].strip() if k.startswith("export ") else k


def token() -> str | None:
    """EARTHDATA_TOKEN from the environment, else from the ignored local env file. Never printed."""
    if os.environ.get("EARTHDATA_TOKEN", "").strip():
        return os.environ["EARTHDATA_TOKEN"].strip()
    for line in _env_lines():
        if _key(line) == "EARTHDATA_TOKEN":
            v = line.partition("=")[2].strip().strip('"').strip("'")
            if v:
                return v
    return None


def env_diagnostics() -> list[str]:
    """Yes/no facts about where the token could be. Prints no value and no other key name."""
    f = config.ROOT / ".env"
    out = [f"local env file (.env in the project folder): {'found' if f.is_file() else 'not found'}"]
    if (config.ROOT / ".env.txt").is_file():
        out.append("a file named .env.txt exists: Notepad added .txt; rename it to .env")
    if f.is_file():
        keys = [_key(l) for l in _env_lines() if "=" in l]
        out.append(f"EARTHDATA_TOKEN line in it: {'found' if 'EARTHDATA_TOKEN' in keys else 'not found'}"
                   f"; other keys containing TOKEN: {sum('TOKEN' in k and k != 'EARTHDATA_TOKEN' for k in keys)}")
        if "EARTHDATA_TOKEN" in keys:
            out.append("its value after '=': empty (paste the token right after the '=' and save)")
        loose = [l for l in _env_lines() if l.strip() and "=" not in l and not l.lstrip().startswith("#")]
        if any(len(l.strip()) > 100 for l in loose):
            out.append("a long line without '=' was found: the token may be on its own line; "
                       "move it up so the line reads EARTHDATA_TOKEN=eyJ...")
    out.append(f"EARTHDATA_TOKEN in this program's environment: {'yes' if os.environ.get('EARTHDATA_TOKEN') else 'no'}")
    return out


def tile_latlon(tile: str) -> tuple[np.ndarray, np.ndarray]:
    """Pixel-centre longitude and latitude (degrees) of one MODIS sinusoidal 500 m tile."""
    h, v = int(tile[1:3]), int(tile[4:6])
    step = TILE_M / N_PIX
    x = (h - 18) * TILE_M + (np.arange(N_PIX) + 0.5) * step
    y = (9 - v) * TILE_M - (np.arange(N_PIX) + 0.5) * step
    lat = np.degrees(y / R_EARTH)[:, None] * np.ones((1, N_PIX))
    lon = np.degrees(x[None, :] / (R_EARTH * np.cos(np.radians(lat))))
    return lon, lat


def punjab_window(tile: str) -> dict:
    """Rows/columns of the tile that touch Punjab, and the in-Punjab mask inside that window (cached)."""
    RAW.mkdir(parents=True, exist_ok=True)
    cache = RAW / f"mask_{tile}.npz"
    if cache.is_file():
        z = np.load(cache)
        return {"r0": int(z["r0"]), "c0": int(z["c0"]), "mask": z["mask"]}
    lon, lat = tile_latlon(tile)
    geom = boundaries.provinces()["Punjab"]
    w, s, e, n = geom.bounds
    box = (lon >= w) & (lon <= e) & (lat >= s) & (lat <= n)
    if not box.any():
        np.savez_compressed(cache, r0=0, c0=0, mask=np.zeros((0, 0), bool))
        return {"r0": 0, "c0": 0, "mask": np.zeros((0, 0), bool)}
    rows, cols = np.where(box.any(axis=1))[0], np.where(box.any(axis=0))[0]
    r0, r1, c0, c1 = rows[0], rows[-1] + 1, cols[0], cols[-1] + 1
    shapely.prepare(geom)
    mask = shapely.contains_xy(geom, lon[r0:r1, c0:c1], lat[r0:r1, c0:c1])
    np.savez_compressed(cache, r0=r0, c0=c0, mask=mask)
    return {"r0": int(r0), "c0": int(c0), "mask": mask}


def _load_manifest() -> dict:
    if MANIFEST.is_file():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"schema": "c08-burned-area-manifest-1", "files": {}}


def _save_manifest(m: dict) -> None:
    tmp = MANIFEST.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(m, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(MANIFEST)


def check() -> int:
    try:
        import pyhdf.SD  # noqa: F401
        reader = "installed"
    except ImportError:
        reader = "missing (pip install pyhdf==0.11.7)"
    free = shutil.disk_usage(config.DATA).free
    print(f"token: {'present' if token() else 'missing (add EARTHDATA_TOKEN=... to the ignored env file)'}")
    if not token():
        for line in env_diagnostics():
            print("  " + line)
    print(f"HDF4 reader: {reader}")
    print(f"disk free: {free / 1e9:.2f} GB (keep {config.MIN_FREE_DISK_BYTES / 1e6:.0f} MB; each download is about 5 MB and is deleted after cropping)")
    m = _load_manifest()
    print(f"cropped files so far: {len(m['files'])} of {len(TILES) * len(MONTHS) * len(YEARS)}")
    return 0 if token() and reader == "installed" else 1


def cmr_links(year: int, month: int) -> dict:
    """tile -> (file name, LP DAAC https URL, size in bytes) for one MCD64A1 month, via the public CMR search."""
    day = date(year, month, 1).isoformat()
    q = {"short_name": "MCD64A1", "version": "061", "temporal": f"{day}T00:00:00Z,{day}T23:59:59Z",
         "bounding_box": PUNJAB_BBOX, "page_size": 50}
    r = acquire._retry(lambda: requests.get(CMR, params=q, timeout=60))
    r.raise_for_status()
    out = {}
    for e in r.json()["feed"]["entry"]:
        url = next((l["href"] for l in e.get("links", []) if l["href"].startswith("https") and l["href"].endswith(".hdf")), None)
        tile = next((t for t in TILES if f".{t}." in e.get("producer_granule_id", "")), None)
        if url and tile:
            out[tile] = (url.rsplit("/", 1)[1], url, int(float(e.get("granule_size") or 5) * 1e6))
    return out


def _download(s: requests.Session, url: str, tok: str) -> requests.Response:
    """GET from LP DAAC with the token, then follow its redirect to the CDN without the token."""
    first = acquire._retry(lambda: s.get(url, headers={"Authorization": f"Bearer {tok}"}, timeout=180,
                                         allow_redirects=False))
    loc = first.headers.get("Location")
    if first.status_code in (301, 302, 303, 307, 308) and loc:
        return acquire._retry(lambda: s.get(loc, timeout=300, stream=True))
    return first


def fetch(*, log=print, limit: int | None = None) -> dict:
    """Download each needed tile-month once, crop it to Punjab, record it, delete the original.

    limit: stop after this many new files (a trial run). A login page or HTTP 401/403
    stops everything at once, because every later request would fail the same way.
    """
    from pyhdf.SD import SD, SDC
    tok = token()
    if not tok:
        raise SystemExit("EARTHDATA_TOKEN is missing; add it to the ignored env file first.")
    s = acquire._session()  # the token is sent only to LP DAAC, never to the CDN it redirects to
    m = _load_manifest()
    windows = {t: punjab_window(t) for t in TILES}
    tmpdir = RAW / "_tmp"
    tmpdir.mkdir(parents=True, exist_ok=True)
    done, errors = 0, []
    for year in YEARS:
        for month in MONTHS:
            doy = date(year, month, 1).timetuple().tm_yday
            links = None
            for tile in TILES:
                fid = f"MCD64A1/{year}/{doy:03d}/{tile}"
                crop = RAW / f"MCD64A1_{year}_{doy:03d}_{tile}_punjab.npz"
                if fid in m["files"] and crop.is_file():
                    continue
                if links is None:
                    links = cmr_links(year, month)
                if tile not in links:
                    errors.append({"id": fid, "error": "not found in CMR search"})
                    continue
                name, url, size = links[tile]
                if shutil.disk_usage(config.DATA).free - size < config.MIN_FREE_DISK_BYTES:
                    raise SystemExit(f"Stopping: the download would leave less than the disk reserve of {config.MIN_FREE_DISK_BYTES / 1e6:.0f} MB.")
                part = tmpdir / name
                try:
                    r = _download(s, url, tok)
                    if r.status_code != 200:
                        raise RuntimeError(f"HTTP {r.status_code}")
                    with part.open("wb") as f:
                        for chunk in r.iter_content(1 << 16):
                            f.write(chunk)
                    if part.read_bytes()[:4] != b"\x0e\x03\x13\x01":
                        raise RuntimeError("not an HDF4 file (login page or error returned?)")
                    digest = acquire.sha256_file(part)
                    sd = SD(str(part), SDC.READ)
                    burn = sd.select("Burn Date").get()
                    sd.end()
                    win = windows[tile]
                    h, w = win["mask"].shape
                    np.savez_compressed(crop, burn=burn[win["r0"]:win["r0"] + h, win["c0"]:win["c0"] + w])
                    m["files"][fid] = {"id": fid, "url": url, "bytes": part.stat().st_size, "sha256": digest,
                                       "retrieved_utc": acquire._now_utc(), "product": "MCD64A1 Collection 6.1",
                                       "doi": "10.5067/MODIS/MCD64A1.061", "layer": "Burn Date",
                                       "crop": crop.relative_to(config.ROOT).as_posix(),
                                       "window": {"r0": win["r0"], "c0": win["c0"], "rows": h, "cols": w},
                                       "original": "deleted after cropping (disk space)",
                                       "license": "NASA EOSDIS data: open use; cite the MCD64A1 DOI"}
                    _save_manifest(m)
                    done += 1
                    log(f"ok {fid}: {m['files'][fid]['bytes'] / 1e6:.1f} MB")
                except Exception as e:
                    errors.append({"id": fid, "error": str(e)})
                    log(f"ERROR {fid}: {e}")
                    if any(x in str(e) for x in ("not an HDF4", "HTTP 401", "HTTP 403")):
                        raise SystemExit(f"Stopping at {fid}: {e}. The Earthdata token may be expired or not accepted; "
                                         "generate a new one (Earthdata Login, Generate Token). Nothing else was downloaded.")
                finally:
                    part.unlink(missing_ok=True)
                if limit and done >= limit:
                    return {"downloaded": done, "errors": errors, "total_recorded": len(m["files"]), "stopped": "limit"}
    return {"downloaded": done, "errors": errors, "total_recorded": len(m["files"])}


def yearly_area() -> pd.DataFrame:
    """Burned km2 inside Punjab with burn dates in October and November, per year, plus unmapped pixels."""
    m = _load_manifest()
    rows = []
    masks = {t: punjab_window(t)["mask"] for t in TILES}
    for year in YEARS:
        burned = unmapped = files = 0
        for month in MONTHS:
            doy = date(year, month, 1).timetuple().tm_yday
            for tile in TILES:
                e = m["files"].get(f"MCD64A1/{year}/{doy:03d}/{tile}")
                if not e:
                    continue
                b = np.load(config.ROOT / e["crop"])["burn"]
                inside = masks[tile]
                burned += int(((b >= 1) & inside).sum())
                unmapped += int(((b == -1) & inside).sum())
                files += 1
        rows.append({"year": year, "files": files, "burned_km2": burned * PIXEL_KM2, "unmapped_km2": unmapped * PIXEL_KM2})
    return pd.DataFrame(rows).set_index("year")


def analyse() -> dict:
    """F03: the P01 section 8 statistics for burned area, compared with the frozen E02/E03 values."""
    from . import harmonize as hz
    t = yearly_area()
    need = len(TILES) * len(MONTHS)
    if (t.files < need).any():
        raise SystemExit(f"Incomplete: years missing files {t.index[t.files < need].tolist()}; run fetch first.")
    # One value per year placed in November, so season_stats sums one month per year.
    s = pd.Series(t.burned_km2.to_numpy(), index=pd.to_datetime([f"{y}-11-01" for y in t.index]))
    st = hz.season_stats(s, (11,))
    e02 = json.loads((config.EXPERIMENTS / "E02_evaluation" / "result.json").read_text(encoding="utf-8"))["differentiator"]["OctNov"]
    e03 = json.loads((config.EXPERIMENTS / "E03_sensitivity" / "result.json").read_text(encoding="utf-8"))["by_model"]
    lo = min(v["OctNov"]["ratio_interval"][0] for v in e03.values())
    hi = max(v["OctNov"]["ratio_interval"][1] for v in e03.values())
    ratio = st["ratio_late_early"]
    reading = ("agrees with the harmonised record" if lo <= ratio <= hi else
               "agrees with the naive record" if ratio > 8 else "matches neither range; reported as it is")
    return {"yearly": {int(y): {"burned_km2": round(float(r.burned_km2), 1), "unmapped_km2": round(float(r.unmapped_km2), 1)}
                       for y, r in t.iterrows()},
            "burned_area": {"ratio_late_early": ratio, "theil_sen_log_slope_per_year": st["theil_sen_log_slope_per_year"]},
            "frozen_comparison": {"naive_ratio": e02["naive_stitch"]["ratio_late_early"],
                                  "aqua_only_ratio": e02["aqua_only"]["ratio_late_early"],
                                  "harmonised_ratio_M2": e02["harmonised"]["ratio_late_early"],
                                  "harmonised_range_M1_M4": [lo, hi]},
            "reading": reading}


def main(argv: list[str]) -> int:
    cmd = (argv or ["check"])[0]
    if cmd == "check":
        return check()
    if cmd == "fetch":
        limit = int(argv[1]) if len(argv) > 1 else None
        print(json.dumps(fetch(limit=limit), indent=1)[:3000])
        return 0
    if cmd == "analyse":
        f = OUT / "result.json"
        if f.is_file():
            raise SystemExit(f"{f.relative_to(config.ROOT)} exists: P02 F03 is run once.")
        res = analyse()
        OUT.mkdir(parents=True, exist_ok=True)
        meta = {"experiment": "P02 F03 burned-area cross-check", "protocol": "experiments/PROTOCOL_P02.md",
                "run_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "code_state": ingest.code_state()}
        f.write_text(json.dumps(meta | res, indent=2), encoding="utf-8")
        print(json.dumps(res, indent=1)[:3000])
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
