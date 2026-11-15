"""Seamline command line:  python -m c08 <command>

  status   read-only diagnostic: environment, disk, raw inputs, processed table, experiments
  build    hash-check the raw files and rebuild the processed detection table (offline)
  serve    start the local app at http://127.0.0.1:8766 (--log FILE writes server output to FILE)
  check    run the test suite and the reproduction check

Data refresh (needs internet) stays separate: python -m c08.acquire --help
"""
from __future__ import annotations

import importlib.metadata as md
import json
import shutil
import subprocess
import sys

from . import config

OK, WARN, FAIL = "ok", "warn", "FAIL"


def _lock() -> dict[str, str]:
    out = {}
    for line in (config.ROOT / "requirements.lock.txt").read_text(encoding="utf-8").splitlines():
        if "==" in line:
            name, ver = line.strip().split("==", 1)
            out[name.lower()] = ver
    return out


def status() -> int:
    """Print one line per check; exit 1 if anything needed for the app is missing."""
    rows = []
    py = sys.version.split()[0]
    rows.append((OK if py.startswith("3.13") else WARN, "python", f"{py} at {sys.executable}"))
    bad = []
    for name, want in _lock().items():
        try:
            have = md.version(name)
        except md.PackageNotFoundError:
            have = None
        if have != want:
            bad.append(f"{name} {have or 'missing'} (lock {want})")
    rows.append((OK if not bad else FAIL, "packages", "match requirements.lock.txt" if not bad else "; ".join(bad)))
    free = shutil.disk_usage(config.ROOT).free
    rows.append((OK if free >= config.MIN_FREE_DISK_BYTES else WARN, "disk", f"{free / 1e9:.1f} GB free (keep {config.MIN_FREE_DISK_BYTES / 1e6:.0f} MB)"))

    from . import acquire, ingest
    files = acquire.load_manifest()["files"]
    missing = [k for k, v in files.items() if not (config.ROOT / v["path"]).is_file()]
    # 2026 API entries carry no byte size (a size would hint at a P04 test count); their SHA-256 is checked by p04.
    wrong = [k for k, v in files.items() if k not in missing and "bytes" in v
             and (config.ROOT / v["path"]).stat().st_size != v["bytes"]]
    rows.append((OK if not (missing or wrong) else FAIL, "raw inputs",
                 f"{len(files) - len(missing) - len(wrong)}/{len(files)} manifest files present with the right size"
                 + (f"; missing {missing[:3]}" if missing else "") + (f"; size differs {wrong[:3]}" if wrong else "")))
    if ingest.DETECTIONS.is_file() and ingest.INGEST_REPORT.is_file():
        rep = json.loads(ingest.INGEST_REPORT.read_text(encoding="utf-8"))
        same = acquire.sha256_file(ingest.DETECTIONS) == rep["output_sha256"]
        rows.append((OK if same else FAIL, "processed table",
                     f"{rep['rows']:,} rows, built {rep['built_utc']}" if same else "hash differs from ingest report; run: python -m c08 build"))
    else:
        rows.append((FAIL, "processed table", "missing; run: python -m c08 build"))
    for name in ("E00_first_run/result.json", "E01_selection/selection.json", "E02_evaluation/result.json",
                 "E03_sensitivity/result.json"):
        p = config.EXPERIMENTS / name
        rows.append((OK if p.is_file() else WARN, "experiment", name + ("" if p.is_file() else " missing")))
    nrt = [v for v in files.values() if v.get("kind") == "firms_nrt_7d_region"]
    if nrt:
        rows.append((OK, "latest NRT", "retrieved " + max(v["retrieved_utc"] for v in nrt)))
    for state, name, text in rows:
        print(f"[{state:>4}] {name:<16} {text}")
    return 1 if any(r[0] == FAIL for r in rows) else 0


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "status"
    if cmd == "status":
        return status()
    if cmd == "build":
        from . import ingest
        _, rep = ingest.build()
        print(f"built {rep['rows']:,} rows -> {rep['output']}")
        return 0
    if cmd == "serve":
        if len(argv) == 3 and argv[1] == "--log":
            # Log to a file instead of inherited handles, so a launcher can return immediately.
            log = open(argv[2], "a", encoding="utf-8", buffering=1)
            sys.stdout = sys.stderr = log
        from . import app
        print("Seamline: http://127.0.0.1:8766  (Ctrl+C to stop)")
        app.main()
        return 0
    if cmd == "check":
        tests = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=config.ROOT).returncode
        repro = subprocess.run([sys.executable, "-B", "-m", "c08.reproduce"], cwd=config.ROOT).returncode
        return tests or repro
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
