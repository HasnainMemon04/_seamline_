"""Satellite Handover Simulator: a historical sensor-withholding replay of the saved 2026 bridge test (P04 G03).

    python -m c08.handover build     # writes reports/c08/seamline/handover_replay.json (read-only on all inputs)

What it does: for January-October 2026 in Punjab it rebuilds, day by day, the three series the frozen test
compared (S-NPP observed, NOAA-20 as counted, NOAA-20 converted with the saved bridge factors), using the saved
test's own stream choice, type screen and matched-day list. It then sums the matched days per month and checks
that the saved monthly values and total error (WAPE) come out again.

What it never does: write into experiments/, refit anything (the factors are read from the saved result), or
score a day the frozen test left out. It is a replay of a past test under a withheld feed, not a simulation of
future burning and not ground-truth validation: S-NPP is another satellite, used as the reference.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import pandas as pd

from . import config, p04

SAVED = config.EXPERIMENTS / "P04_G03_bridge_2026" / "result.json"
OUT = config.REPORTS / "seamline" / "handover_replay.json"
AREA = "Punjab"
TOL_COUNT = 1e-6   # converted monthly detections: allowed absolute difference from the saved value
TOL_WAPE = 1e-9    # total error: allowed absolute difference from the saved value


def _plan_from_saved(saved: dict) -> list[dict]:
    """The frozen test's month plan (stream, type screen, matched days), rebuilt from its saved record alone."""
    plan = []
    for m in saved["days_by_month"]:
        days = p04.month_days(m["month"])
        removed = m.get("removed_days", {})
        matched = [t for t in days if p04._iso(t) not in removed]
        if len(matched) != m["matched_days"]:
            raise SystemExit(f"{m['month']}: the saved record lists {m['matched_days']} matched days, "
                             f"its removed-day list leaves {len(matched)}")
        plan.append({**m, "matched": matched, "days": days})
    return plan


def build() -> dict:
    saved = json.loads(SAVED.read_text(encoding="utf-8"))
    entries = p04.api_entries()
    used = {f["id"]: f["sha256"] for f in saved["inputs"]["raw_2026_files"]}
    now = {e["id"]: e["sha256"] for e in entries}
    same_inputs = used == now
    api, _ = p04.load_api_rows(entries)  # hash-checks every raw 2026 file against the manifest, then parses it
    plan = _plan_from_saved(saved)
    k = {key: (v["k_day"], v["k_night"]) for key, v in saved["bridge"]["primary"].items()}
    days, months = [], []
    in_area = p04._area(api["province"], AREA)
    for m in plan:
        key = "type0" if m["type0_screen"] else "none"
        kd, kn = k[key]
        sel = api["stream"].eq(m["stream"]) & api["platform"].isin(["SNPP", "NOAA20"]) & api["quality_pass"] & in_area
        if m["type0_screen"]:
            sel &= api["type0"]
        rows = api[sel & api["date_utc"].between(m["days"][0], m["days"][-1])]
        c = rows.groupby(["date_utc", "platform", "daynight"]).size()
        matched = set(m["matched"])
        tot = {"obs": 0, "raw": 0, "conv": 0.0}
        for t in m["days"]:
            g = lambda p, dn: int(c.get((t, p, dn), 0))  # noqa: E731
            sd, sn, nd, nn = g("SNPP", "D"), g("SNPP", "N"), g("NOAA20", "D"), g("NOAA20", "N")
            ok = t in matched
            conv = kd * nd + kn * nn
            days.append({"date": p04._iso(t), "month": m["month"], "stream": m["stream"], "matched": ok,
                         "why_not": None if ok else m["removed_days"].get(p04._iso(t), "not a matched day"),
                         # A day the test left out has no usable count: never a zero.
                         "snpp": sd + sn if ok else None, "noaa20": nd + nn if ok else None,
                         "converted": round(conv, 3) if ok else None})
            if ok:
                tot["obs"] += sd + sn
                tot["raw"] += nd + nn
                tot["conv"] += conv
        months.append({"month": m["month"], "stream": m["stream"], "type0_screen": m["type0_screen"],
                       "days_in_month": m["days_in_month"], "matched_days": m["matched_days"], "scored": m["scored"],
                       "k_day": kd, "k_night": kn, "observed_snpp": tot["obs"], "noaa20_raw": tot["raw"],
                       "converted": tot["conv"],
                       "error": (tot["conv"] - tot["obs"]) / tot["obs"] if m["scored"] and tot["obs"] else None,
                       "raw_error": (tot["raw"] - tot["obs"]) / tot["obs"] if m["scored"] and tot["obs"] else None})
    scored = [m for m in months if m["scored"]]
    obs = sum(m["observed_snpp"] for m in scored)
    wape = sum(abs(m["converted"] - m["observed_snpp"]) for m in scored) / obs
    m0 = sum(abs(m["noaa20_raw"] - m["observed_snpp"]) for m in scored) / obs
    by_month = {m["month"]: m for m in saved["months"]}
    diffs = []
    for m in scored:
        s = by_month[m["month"]]
        diffs.append({"month": m["month"], "observed_same": m["observed_snpp"] == s["observed_snpp"],
                      "converted_diff": abs(m["converted"] - s["predicted"]),
                      "raw_same": m["noaa20_raw"] == round(s["m0_predicted"])})
    ok = (same_inputs and len(scored) == saved["scored_months"]
          and all(d["observed_same"] and d["raw_same"] and d["converted_diff"] <= TOL_COUNT for d in diffs)
          and abs(wape - saved["wape"]) <= TOL_WAPE and abs(m0 - saved["m0_wape"]) <= TOL_WAPE)
    out = {
        "what": "Historical sensor-withholding replay of the saved NOAA-20 bridge test (Protocol P04, test G03)",
        "not": "Not a simulation of future burning and not independent ground-truth validation. S-NPP is the "
               "reference satellite, another instrument, not the truth on the ground.",
        "area": AREA, "area_scope": "The frozen test covers Punjab only. Pakistan, Sindh and Khyber Pakhtunkhwa are "
                                    "reported, not tested; other areas have no result.",
        "test_window": ["2026-01-01", "2026-10-31"],
        "calibration_window": "April 2018 to December 2025 (the bridge's training months; nothing fitted on 2026)",
        "simulation": "S-NPP is hidden from the replay's available inputs; the record continues on NOAA-20 times the "
                      "saved bridge factors; the withheld S-NPP counts are then shown for comparison.",
        "platform_status": saved.get("seam_label"),
        "units": "detections per UTC day in Punjab (day and night passes): fire pixels on satellite passes",
        "saved": {"file": "experiments/P04_G03_bridge_2026/result.json", "status": saved["status"],
                  "wape": saved["wape"], "m0_wape": saved["m0_wape"], "scored_months": saved["scored_months"],
                  "worst_held_month_error": saved["worst_held_month_error"], "run_utc": saved["run_utc"],
                  "protocol": saved["protocol"], "protocol_sha256": saved["protocol_sha256"],
                  "pass_mark": saved["rules"]["pass_mark"], "matched_days_rule": saved["rules"]["matched_days"],
                  "bridge_rule": saved["rules"]["bridge"], "months_not_scored": saved["months_not_scored"],
                  "reported": {a: {"label": r["label"], "wape": r["wape"], "m0_wape": r["m0_wape"]}
                               for a, r in saved.get("reported", {}).items()}},
        "replay": {"wape": wape, "m0_wape": m0, "scored_months": len(scored)},
        "reproduction": {"reproduced": bool(ok), "same_raw_files_as_the_saved_run": bool(same_inputs),
                         "tolerance": {"converted_monthly_detections": TOL_COUNT, "wape": TOL_WAPE},
                         "wape_diff": abs(wape - saved["wape"]), "m0_wape_diff": abs(m0 - saved["m0_wape"]),
                         "largest_converted_diff": max(d["converted_diff"] for d in diffs), "months": diffs},
        "months": months, "days": days,
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "built_by": "python -m c08.handover build",
        "raw_files": len(entries),
    }
    return out


def load() -> dict:
    if not OUT.is_file():
        raise FileNotFoundError("The handover replay file is not built yet. Run: python -m c08.handover build")
    return json.loads(OUT.read_text(encoding="utf-8"))


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] != ["build"]:
        print(__doc__)
        return 2
    out = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    r = out["reproduction"]
    print(f"replay WAPE {out['replay']['wape']:.6f} (saved {out['saved']['wape']:.6f}); no conversion "
          f"{out['replay']['m0_wape']:.6f} (saved {out['saved']['m0_wape']:.6f}); reproduced: {r['reproduced']}; "
          f"largest monthly difference {r['largest_converted_diff']:.2e}; {len(out['days'])} days")
    return 0 if r["reproduced"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
