"""Resumable, hashed downloads of public FIRMS files (no key or login needed).

Every file goes to data/raw/ and gets a manifest entry (URL, bytes, SHA-256, rows,
version strings, observed date range, server Last-Modified). Raw files are never
edited. If the server copy changes, the old copy is kept under _previous/.
A missing file (HTTP 404) is recorded as absent; it is never treated as "no fire".
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

from . import config

PKT_OFFSET = "+05:00"


def disk_floor_text() -> str:
    """The disk reserve as words, built from config.MIN_FREE_DISK_BYTES (never typed by hand)."""
    b = config.MIN_FREE_DISK_BYTES
    return f"{b / 1024**3:g} GB" if b >= 1024**3 else f"{b / 1024**2:g} MB"


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = config.USER_AGENT
    return s  # TLS verification stays on (requests default, certifi bundle).


def _retry(fn, *, tries: int = 4, base_delay: float = 2.0):
    """Call fn(); retry network errors and 5xx/429 with exponential backoff."""
    last = None
    for attempt in range(tries):
        try:
            r = fn()
            if r.status_code in (429, 500, 502, 503, 504):
                last = RuntimeError(f"HTTP {r.status_code}")
            else:
                return r
        except requests.RequestException as e:  # timeouts, resets
            last = e
        time.sleep(base_delay * 2**attempt)
    raise RuntimeError(f"gave up after {tries} attempts: {last}")


def load_manifest() -> dict:
    if config.MANIFEST.is_file():
        return json.loads(config.MANIFEST.read_text(encoding="utf-8"))
    return {"schema": "c08-manifest-1", "files": {}, "absent": {}, "runs": []}


def save_manifest(m: dict) -> None:
    config.MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = config.MANIFEST.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(m, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(config.MANIFEST)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def summarize_csv(path: Path) -> dict:
    """Cheap content summary used in the manifest (full validation is in ingest)."""
    rows = 0
    versions, satellites, instruments = set(), set(), set()
    dmin = dmax = None
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        for row in reader:
            rows += 1
            versions.add(row.get("version", ""))
            satellites.add(row.get("satellite", ""))
            instruments.add(row.get("instrument", ""))
            d = row.get("acq_date", "")
            if d:
                dmin = d if dmin is None or d < dmin else dmin
                dmax = d if dmax is None or d > dmax else dmax
    return {"rows": rows, "fields": fields, "versions": sorted(versions),
            "satellites": sorted(satellites), "instruments": sorted(instruments),
            "min_acq_date": dmin, "max_acq_date": dmax}


def country_targets() -> list[dict]:
    out = []
    for src in config.COUNTRY_SOURCES:
        for year in range(src.first_year, src.last_year + 1):
            name = f"{src.key}_{year}_{config.COUNTRY}.csv"
            out.append({
                "id": f"country/{src.key}/{year}",
                "url": f"{config.FIRMS_COUNTRY_BASE}/{src.key}/{year}/{name}",
                "path": config.RAW_COUNTRY / src.key / name,
                "kind": "firms_country_annual", "source": src.key, "year": year,
                "product": src.product, "doi": src.doi,
            })
    return out


def nrt_targets(stamp: str) -> list[dict]:
    """NRT 7-day files change constantly, so each retrieval is stored under its UTC stamp."""
    out = []
    for key, url in config.NRT_SOURCES.items():
        out.append({
            "id": f"nrt/{key}/{stamp}", "url": url,
            "path": config.RAW_NRT / stamp / Path(url).name,
            "kind": "firms_nrt_7d_region", "source": key, "year": None,
            "product": f"FIRMS NRT 7-day South Asia file ({key})", "doi": None,
        })
    return out


def _free_bytes(path: Path) -> int:
    path.mkdir(parents=True, exist_ok=True)
    return shutil.disk_usage(path).free


def fetch(targets: list[dict], *, log=print, budget: int = config.DOWNLOAD_BUDGET_BYTES) -> dict:
    """Download targets that are new or changed. Returns a run summary."""
    m = load_manifest()
    s = _session()
    run = {"started_utc": _now_utc(), "downloaded": [], "unchanged": [], "absent": [], "errors": []}

    # 1. HEAD everything first, so the size budget is checked before any download.
    heads = {}
    for t in targets:
        try:
            r = _retry(lambda: s.head(t["url"], timeout=60, allow_redirects=True))
        except Exception as e:  # network failure: record, keep going
            run["errors"].append({"id": t["id"], "error": str(e)})
            continue
        if r.status_code == 404:
            m["absent"][t["id"]] = {"url": t["url"], "checked_utc": _now_utc(), "http_status": 404}
            run["absent"].append(t["id"])
            continue
        if r.status_code != 200:
            run["errors"].append({"id": t["id"], "error": f"HEAD HTTP {r.status_code}"})
            continue
        heads[t["id"]] = {"length": int(r.headers.get("Content-Length") or 0),
                          "last_modified": r.headers.get("Last-Modified"),
                          "etag": r.headers.get("ETag")}

    todo = []
    for t in targets:
        h = heads.get(t["id"])
        if not h:
            continue
        prev = m["files"].get(t["id"])
        path: Path = t["path"]
        if (prev and path.is_file() and prev.get("bytes") == path.stat().st_size
                and prev.get("server_last_modified") == h["last_modified"]
                and (not h["length"] or h["length"] == prev.get("bytes"))):
            run["unchanged"].append(t["id"])
            continue
        todo.append(t)
    planned = sum(heads[t["id"]]["length"] for t in todo)
    log(f"planned downloads: {len(todo)} files, {planned / 1e6:.1f} MB "
        f"(unchanged {len(run['unchanged'])}, absent {len(run['absent'])}, errors {len(run['errors'])})")
    if planned > budget:
        raise RuntimeError(f"planned {planned} bytes exceeds the {budget}-byte budget; narrow the request")
    if _free_bytes(config.DATA) - planned < config.MIN_FREE_DISK_BYTES:
        raise RuntimeError(f"download would leave less than the {disk_floor_text()} disk reserve")

    # 2. Download to .part, hash, summarise, then move into place.
    for t in todo:
        path: Path = t["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_suffix(path.suffix + ".part")
        t0 = time.perf_counter()
        try:
            def get():
                return s.get(t["url"], timeout=120, stream=True)
            r = _retry(get)
            if r.status_code != 200:
                raise RuntimeError(f"GET HTTP {r.status_code}")
            with part.open("wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
            digest = sha256_file(part)
            summary = summarize_csv(part)
            if "latitude" not in summary["fields"] or "acq_date" not in summary["fields"]:
                raise RuntimeError("response is not a FIRMS CSV (unexpected columns)")
            prev = m["files"].get(t["id"])
            if path.is_file() and prev and prev.get("sha256") != digest:
                keep = path.parent / "_previous" / f"{path.stem}_{prev['sha256'][:12]}{path.suffix}"
                keep.parent.mkdir(exist_ok=True)
                shutil.move(str(path), keep)
            part.replace(path)
            entry = {
                "id": t["id"], "url": t["url"], "path": path.relative_to(config.ROOT).as_posix(),
                "kind": t["kind"], "source": t["source"], "year": t["year"],
                "product": t["product"], "doi": t["doi"], "bytes": path.stat().st_size,
                "sha256": digest, "retrieved_utc": _now_utc(),
                "server_last_modified": heads[t["id"]]["last_modified"],
                "elapsed_s": round(time.perf_counter() - t0, 2), **summary,
                "license": "NASA FIRMS data: open, no restriction on use; cite FIRMS and product DOI",
            }
            m["files"][t["id"]] = entry
            run["downloaded"].append(t["id"])
            log(f"ok {t['id']}: {entry['rows']} rows, {entry['bytes'] / 1e6:.2f} MB, "
                f"versions {entry['versions']}, {entry['min_acq_date']}..{entry['max_acq_date']}")
        except Exception as e:
            part.unlink(missing_ok=True)
            run["errors"].append({"id": t["id"], "error": str(e)})
            log(f"ERROR {t['id']}: {e}")
        save_manifest(m)  # checkpoint after every file

    run["finished_utc"] = _now_utc()
    m["runs"].append(run)
    save_manifest(m)
    return run


# ---------------------------------------------------------------------------------------------
# FIRMS area API (needs a private MAP_KEY) for Protocol P04, G03 and G04.
# The key is read from the ignored .env only when a real download runs. It is never printed,
# logged, raised in an error or stored: every URL that is printed or saved goes through redact().
# Unlike the public files above, a 2026 file's manifest entry records no rows and no bytes (manifest_entry).
# ---------------------------------------------------------------------------------------------
API_BASE = "https://firms.modaps.eosdis.nasa.gov/api"
KEY_PLACEHOLDER = "<MAP_KEY>"
PAKISTAN_BBOX = (60.5, 23.5, 77.9, 37.2)  # west, south, east, north (a box around Pakistan)
API_MAX_DAYS = 5  # FIRMS answered "Invalid day range. Expects [1..5]" to 10 on 8 Nov 2026
API_PAUSE_S = 1.5  # pause between requests, well inside FIRMS's transaction limit
RAW_API = config.DATA / "raw" / "firms_api"
META = config.ROOT / "research" / "metadata"
MISSING_DATA_URL = f"{API_BASE}/missing_data/?action=fetch_data"  # public page, no key needed
_KEY_IN_URL = re.compile(r"(/api/(?:area|data_availability|country|missing_data)/csv/)[^/\s?]+")

# Satellite -> (standard-stream source, near-real-time source); NOAA-21 has NRT only.
API_SATELLITES = {"SNPP": ("VIIRS_SNPP_SP", "VIIRS_SNPP_NRT"), "NOAA20": ("VIIRS_NOAA20_SP", "VIIRS_NOAA20_NRT")}
API_PLAN = {"first": date(2026, 1, 1), "last": date(2026, 10, 31),
            "noaa21": ("VIIRS_NOAA21_NRT", date(2026, 10, 1), date(2026, 10, 29))}


def redact(text, key: str | None = None) -> str:
    """Hide the MAP_KEY in any text: the key itself, and whatever sits in the key slot of a FIRMS API URL."""
    out = _KEY_IN_URL.sub(lambda m: m.group(1) + KEY_PLACEHOLDER, str(text))
    if key:
        out = out.replace(key, KEY_PLACEHOLDER)
    return out


def map_key() -> str | None:
    """FIRMS_MAP_KEY from the environment, else from the ignored .env. Never printed."""
    import os
    if os.environ.get("FIRMS_MAP_KEY", "").strip():
        return os.environ["FIRMS_MAP_KEY"].strip()
    from . import burned_area  # reuses its encoding-safe .env reader
    for line in burned_area._env_lines():
        if burned_area._key(line) == "FIRMS_MAP_KEY":
            v = line.partition("=")[2].strip().strip('"').strip("'")
            if v:
                return v
    return None


def api_url(key: str, source: str, bbox, days: int, start: str) -> str:
    if not 1 <= days <= API_MAX_DAYS:
        raise ValueError(f"days must be 1..{API_MAX_DAYS}")
    box = ",".join(f"{v:g}" for v in bbox)
    return f"{API_BASE}/area/csv/{key}/{source}/{box}/{days}/{start}"


def _month_end(d: date) -> date:
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def month_chunks(first: date, last: date) -> list[tuple[date, int]]:
    """Split first..last into pieces of at most 10 days that never cross a month boundary."""
    out, d = [], first
    while d <= last:
        end = min(_month_end(d), last, d + timedelta(days=API_MAX_DAYS - 1))
        out.append((d, (end - d).days + 1))
        d = end + timedelta(days=1)
    return out


def parse_availability(text: str) -> dict[str, tuple[date, date]]:
    """FIRMS data_availability CSV (data_id,min_date,max_date) -> {data_id: (first, last)}."""
    out = {}
    for row in csv.DictReader(io.StringIO(text)):
        try:
            out[row["data_id"].strip()] = (date.fromisoformat(row["min_date"].strip()),
                                           date.fromisoformat(row["max_date"].strip()))
        except (KeyError, ValueError, AttributeError):
            continue
    return out


def month_streams(availability: dict | None) -> dict[str, str | None]:
    """P04 G03 line 2: a month uses SP only if the availability range covers the whole month for BOTH
    satellites; otherwise both use NRT. None for every month when availability is not known (dry run)."""
    out = {}
    for d, _ in month_chunks(API_PLAN["first"], API_PLAN["last"]):
        ym = d.strftime("%Y-%m")
        if availability is None:
            out[ym] = None
            continue
        first = d.replace(day=1)
        last = _month_end(d)
        ok = all(sp in availability and availability[sp][0] <= first and availability[sp][1] >= last
                 for sp, _ in API_SATELLITES.values())
        out[ym] = "SP" if ok else "NRT"
    return out


def plan_requests(availability: dict | None = None) -> list[dict]:
    """Every request to make. With availability=None (dry run) both streams are listed for each month
    as candidates; the real run keeps one stream per month."""
    streams = month_streams(availability)
    plan = []
    for d, n in month_chunks(API_PLAN["first"], API_PLAN["last"]):
        stream = streams[d.strftime("%Y-%m")]
        for sp, nrt in API_SATELLITES.values():
            for src, tag in ((sp, "SP"), (nrt, "NRT")):
                if stream in (None, tag):
                    plan.append({"source": src, "start": d.isoformat(), "days": n,
                                 "stream": tag, "candidate": stream is None})
    src, a, b = API_PLAN["noaa21"]
    for d, n in month_chunks(a, b):
        plan.append({"source": src, "start": d.isoformat(), "days": n, "stream": "NRT", "candidate": False})
    for r in plan:
        r["path"] = RAW_API / r["source"] / f"{r['start']}_{r['days']}d.csv"
        r["id"] = f"firms_api/{r['source']}/{r['start']}_{r['days']}d"
    return plan


def _api_get(s: requests.Session, url: str, key: str, *, timeout: int = 120):
    """GET with retries. Any error text is re-raised with the key removed."""
    def once():
        try:
            return s.get(url, timeout=timeout)
        except requests.RequestException as e:
            raise requests.ConnectionError(redact(e, key)) from None
    try:
        return _retry(once)
    except RuntimeError as e:
        raise RuntimeError(redact(e, key)) from None


def manifest_entry(req: dict, key: str, bbox, content: bytes, path: Path) -> dict:
    """The manifest record of one 2026 file. It has no row count and no byte count: before P04's run-once G03 and
    G04, either would show how many 2026 detections a file holds (the size grows with the rows). The SHA-256 is
    what c08/p04.py checks before it reads a file."""
    url = api_url(key, req["source"], bbox, req["days"], req["start"])
    return {"id": req["id"], "path": path.relative_to(config.ROOT).as_posix(), "kind": "firms_api_csv",
            "source": req["source"], "start": req["start"], "days": req["days"], "bbox": list(bbox),
            "sha256": hashlib.sha256(content).hexdigest(), "retrieved_utc": _now_utc(),
            "url_redacted": redact(url, key)}


def save_manifest_safe(m: dict, key: str) -> None:
    """Write the manifest only if the key appears nowhere in it."""
    if key and key in json.dumps(m):
        raise RuntimeError("refusing to write the manifest: it would contain the MAP_KEY")
    save_manifest(m)


def fetch_availability(s, key: str, stamp: str) -> dict:
    url = f"{API_BASE}/data_availability/csv/{key}/all"
    r = _api_get(s, url, key)
    if r.status_code != 200:
        raise RuntimeError(f"data_availability: HTTP {r.status_code}")
    av = parse_availability(r.text)
    if not av:
        raise RuntimeError("data_availability: the answer was not the expected CSV (is the MAP_KEY valid?)")
    META.mkdir(parents=True, exist_ok=True)
    out = META / f"firms_data_availability_{stamp}.json"
    out.write_text(json.dumps({
        "retrieved_utc": _now_utc(), "url_redacted": redact(url, key),
        "ranges": {k: [v[0].isoformat(), v[1].isoformat()] for k, v in sorted(av.items())}},
        indent=2), encoding="utf-8")
    return av


_TR = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_TD = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)


def _parse_missing_html(html: str) -> list[dict]:
    """The page's answer as of 8 Nov 2026: {"success", "html", "rowCount"}, where each <tr> holds two pairs of
    cells under the headers "Standard Data" and "Near Real Time Data": date missing, then satellite (sensor).
    The near-real-time pair is empty when that list is shorter."""
    out = []
    for tr in _TR.findall(html):
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in _TD.findall(tr)]
        for (d, sat), stream in zip((cells[0:2], cells[2:4]), ("standard", "NRT")):
            if len(d) >= 10 and sat:
                out.append({"date": d[:10], "satellite": sat, "stream": stream})
    return out


def parse_missing_data(payload) -> list[dict]:
    """FIRMS missing-data page answer -> [{date, satellite, stream}] (the shape of the committed file)."""
    if isinstance(payload, dict) and isinstance(payload.get("html"), str):
        return _parse_missing_html(payload["html"])
    rows = payload.get("data", payload) if isinstance(payload, dict) else payload
    out = []
    for r in rows if isinstance(rows, list) else []:
        if isinstance(r, dict):
            d, sat, st = r.get("date"), r.get("satellite"), r.get("stream")
        elif isinstance(r, (list, tuple)) and len(r) >= 3:
            d, sat, st = r[0], r[1], r[2]
        else:
            continue
        if d and sat:
            out.append({"date": str(d)[:10], "satellite": str(sat), "stream": str(st or "")})
    return out


def fetch_missing_dates(s, stamp: str) -> list[dict]:
    """Refreshed missing-days list from FIRMS's public page (no key). The committed
    research/metadata/provider_missing_dates.json is never overwritten: the copy is dated."""
    r = _retry(lambda: s.get(MISSING_DATA_URL, timeout=60))
    if r.status_code != 200:
        raise RuntimeError(f"missing_data: HTTP {r.status_code}")
    rows = parse_missing_data(r.json())
    if not rows:
        raise RuntimeError("missing_data: no rows parsed; the page format may have changed")
    META.mkdir(parents=True, exist_ok=True)
    (META / f"provider_missing_dates_{stamp}.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return rows


def run_api2026(*, dry_run: bool = False, log=print, pause: float = API_PAUSE_S) -> int:
    free = _free_bytes(config.DATA)
    floor = config.MIN_FREE_DISK_BYTES
    if dry_run:
        plan = plan_requests(None)
        log(f"DRY RUN: no network call and the key is not read. {len(plan)} candidate requests "
            f"(the real run first fetches data availability, then keeps SP or NRT per month for both satellites).")
        for r in plan:
            url = api_url(KEY_PLACEHOLDER, r["source"], PAKISTAN_BBOX, r["days"], r["start"])
            log(f"  {r['stream']:3} {redact(url)}  ->  {r['path'].relative_to(config.ROOT).as_posix()}")
        log(f"disk: {free / 1e9:.2f} GB free, reserve {disk_floor_text()}: {'OK' if free > floor else 'TOO LOW'}")
        return 0 if free > floor else 1
    key = map_key()
    if not key:
        log("FIRMS_MAP_KEY is missing; add it to the ignored .env first.")
        return 2
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    s = _session()
    try:
        av = fetch_availability(s, key, stamp)
        fetch_missing_dates(s, stamp)
        plan = plan_requests(av)
        m = load_manifest()
        done = skipped = 0
        for r in plan:
            path: Path = r["path"]
            prev = m["files"].get(r["id"])
            if path.is_file() and prev and prev.get("sha256") == sha256_file(path):
                skipped += 1
                continue
            if _free_bytes(config.DATA) - (5 << 20) < floor:
                log(f"Stopping: the next file would leave less than the {disk_floor_text()} disk reserve.")
                return 1
            time.sleep(pause)
            resp = _api_get(s, api_url(key, r["source"], PAKISTAN_BBOX, r["days"], r["start"]), key)
            if resp.status_code != 200:
                log(f"Stopping at {r['id']}: HTTP {resp.status_code}. Files already saved are kept.")
                return 1
            if "latitude" not in resp.content[:300].decode("utf-8", "replace").lower():
                log(f"Stopping at {r['id']}: the answer was not a FIRMS CSV (key invalid or limit reached).")
                return 1
            path.parent.mkdir(parents=True, exist_ok=True)
            part = path.with_suffix(".csv.part")
            part.write_bytes(resp.content)
            part.replace(path)
            m["files"][r["id"]] = manifest_entry(r, key, PAKISTAN_BBOX, resp.content, path)
            save_manifest_safe(m, key)
            done += 1
            log(f"ok {r['id']} ({r['stream']})")
        log(f"finished: {done} downloaded, {skipped} already present")
        return 0
    except Exception as e:  # shown only after the key is removed
        log(f"Stopping: {redact(e, key)}")
        return 1


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="Download public FIRMS files for Pakistan")
    p.add_argument("--nrt", action="store_true", help="also fetch the public 7-day NRT South Asia files")
    p.add_argument("--only", help="comma-separated source keys, e.g. modis,viirs-snpp")
    p.add_argument("--api2026", action="store_true",
                   help="P04: download the 2026 FIRMS area-API files (needs FIRMS_MAP_KEY in the ignored .env)")
    p.add_argument("--dry-run", action="store_true",
                   help="with --api2026: list the planned requests (key hidden) and check the disk; no network call")
    a = p.parse_args(argv)
    if a.api2026:
        return run_api2026(dry_run=a.dry_run)
    if a.dry_run:
        p.error("--dry-run is only for --api2026")
    targets = country_targets()
    if a.only:
        keys = set(a.only.split(","))
        targets = [t for t in targets if t["source"] in keys]
    if a.nrt:
        targets += nrt_targets(datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ"))
    run = fetch(targets)
    print(json.dumps({k: len(v) if isinstance(v, list) else v for k, v in run.items()}, indent=1))
    return 1 if run["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
