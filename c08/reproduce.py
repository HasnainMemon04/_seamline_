"""Re-run E01-E03 into a temporary folder and compare every number with the saved results.

python -m c08.reproduce   (exit code 0 = identical apart from timestamps/runtime)

The saved experiment files are never rewritten, so the frozen record of what was
run once (E02) stays as it was. Writes reports/c08/reproduction_check.json.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import config, p01

VOLATILE = {"run_utc", "runtime_s", "written_utc", "selection_written_utc", "environment", "selection_file", "code_revision",
            "code_state"}


def _diff(a, b, path="") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b), key=str):
            if k in VOLATILE:
                continue
            if k not in a or k not in b:
                out.append(f"{path}/{k}: present in only one")
            else:
                out += _diff(a[k], b[k], f"{path}/{k}")
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}: length {len(a)} vs {len(b)}"]
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in _diff(x, y, f"{path}[{i}]")]
    if isinstance(a, float) and isinstance(b, float):
        return [] if abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b)) else [f"{path}: {a} vs {b}"]
    return [] if a == b else [f"{path}: {a!r} vs {b!r}"]


def main() -> int:
    saved = {k: json.loads((config.EXPERIMENTS / d / "result.json").read_text(encoding="utf-8"))
             for k, d in (("e01", "E01_selection"), ("e02", "E02_evaluation"), ("e03", "E03_sensitivity"))}
    tmp = Path(tempfile.mkdtemp(prefix="c08_repro_"))
    orig = dict(p01.OUT)
    try:
        for k in ("e00", "e01", "e02", "e03"):
            p01.OUT[k] = tmp / k
        p01.e01()
        # E02 must use the selection frozen on disk, not the fresh one (they must also agree).
        fresh_sel = json.loads((tmp / "e01" / "selection.json").read_text(encoding="utf-8"))
        frozen_sel = json.loads((config.EXPERIMENTS / "E01_selection" / "selection.json").read_text(encoding="utf-8"))
        shutil.copy(config.EXPERIMENTS / "E01_selection" / "selection.json", tmp / "e01" / "selection.json")
        p01.e02()
        p01.e03()
        fresh = {k: json.loads((tmp / k / "result.json").read_text(encoding="utf-8")) for k in ("e01", "e02", "e03")}
    finally:
        p01.OUT.clear()
        p01.OUT.update(orig)
        shutil.rmtree(tmp, ignore_errors=True)
    diffs = {k: _diff(saved[k], fresh[k]) for k in saved}
    diffs["selection"] = _diff(frozen_sel, fresh_sel)
    from .ingest import code_state
    report = {"checked_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "code_state": code_state(),
              "compared": ["E01_selection", "E02_evaluation", "E03_sensitivity", "E01 selection.json"],
              "ignored_fields": sorted(VOLATILE), "identical": all(not v for v in diffs.values()),
              "differences": diffs}
    out = config.REPORTS / "reproduction_check.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"identical": report["identical"], **{k: len(v) for k, v in diffs.items()}}))
    return 0 if report["identical"] else 1


if __name__ == "__main__":
    sys.exit(main())
