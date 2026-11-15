"""Protocol O01 runner: an experimental, retrospective outlook for detected burning activity.

    python -m c08.outlook audit       # the daily series, its gaps and the eligible origins (no fitting)
    python -m c08.outlook validate    # benchmarks and both candidates on 2021-2024; writes validation.json (repeatable)
    python -m c08.outlook holdout     # the held-out year 2025, read once; writes holdout.json and refuses to overwrite

Everything here follows experiments/PROTOCOL_O01.md, which was written and committed before this file. The target is
one satellite's detections (NOAA-20 VIIRS) in one area (Punjab) over the next seven complete UTC days. It is not a
forecast of fires, area, emissions or danger. The app (GET /api/outlook) only reads the saved results: nothing is
fitted on request, and no outlook is shown unless the protocol's release rule holds.
"""
from __future__ import annotations

import hashlib
import json
import platform as _platform
import sys
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

from . import analysis, config, ingest, series

PROTOCOL = "experiments/PROTOCOL_O01.md"
OUT = config.EXPERIMENTS / "O01_outlook"
AREA, SAT = "Punjab", "NOAA20"
START, END = pd.Timestamp("2018-04-01"), pd.Timestamp("2025-12-31")
GRID0 = pd.Timestamp("2018-04-28")
C = 7.0                               # offset: one detection a day
UP, DOWN = 1.25, 0.80                 # the meaningful-change band
VAL_YEARS, TEST_YEAR = (2021, 2022, 2023, 2024), 2025
RIDGE_GRID, ROUNDS_GRID = (0.1, 1.0, 10.0, 100.0), (50, 100, 200)
LEARNING_RATE, N_CUTS, MIN_LEAF = 0.1, 16, 5
BOOT_BLOCK, BOOT_N, BOOT_SEED = 4, 2000, 20261112
FRESH_DAYS = 3
FEATURES = ("ln_prev7", "ln_week2", "ln_mean28", "ln_last_day", "ln_normal_next", "ln_normal_prev", "sin1", "cos1", "sin2", "cos2")
APPROVED = ("Hasnain, Seamline redesign brief Revision 1.3, section 4D: 'run the baseline, bounded candidate fits and actual "
            "evaluation' (prompts/Seamline_3D_UI_UX_Redesign_Master_Prompt_r1.3.md)")


# ---------- the daily series ----------
def daily_series(d: pd.DataFrame | None = None) -> pd.Series:
    """Retained NOAA-20 detections per UTC day in Punjab; NaN on a day that is not complete (never zero)."""
    d = analysis.detections() if d is None else d
    q = d[(d["platform"] == SAT) & (d["stream"] == "standard")]
    days = pd.date_range(START, END, freq="D")
    has_d = set(q.loc[q["daynight"] == "D", "date_utc"].unique())
    has_n = set(q.loc[q["daynight"] == "N", "date_utc"].unique())
    miss = series.provider_missing()
    listed = set(miss.loc[(miss["platform"] == SAT) & (miss["stream"] == "standard"), "date"])
    keep = q[q["quality_pass"] & q["type0"] & (q["province"].astype(str) == AREA)]
    y = keep.groupby("date_utc").size().reindex(days, fill_value=0).astype(float)
    complete = np.array([(t in has_d) and (t in has_n) and (t not in listed) for t in days])
    y[~complete] = np.nan
    return y


def _doy365(days: pd.DatetimeIndex) -> np.ndarray:
    """Day of the year on a 365-day calendar: 29 February is read as 28 February."""
    m, dd = days.month.to_numpy(), days.day.to_numpy()
    dd = np.where((m == 2) & (dd == 29), 28, dd)
    return pd.to_datetime({"year": 2019, "month": m, "day": dd}).dt.dayofyear.to_numpy() - 1


def daily_normal(y: pd.Series, years) -> np.ndarray:
    """Mean of y on each day of the year over the given years, then a centred 15-day circular mean."""
    part = y[y.index.year.isin(list(years))]
    raw = pd.Series(part.to_numpy(), index=_doy365(part.index)).groupby(level=0).mean().reindex(range(365))
    wide = np.concatenate([raw.to_numpy()[-7:], raw.to_numpy(), raw.to_numpy()[:7]])
    sm = np.array([np.nanmean(wide[i:i + 15]) if np.isfinite(wide[i:i + 15]).any() else np.nan for i in range(365)])
    return pd.Series(sm).interpolate(limit_direction="both").to_numpy()


def origins(y: pd.Series) -> pd.DataFrame:
    """Every origin on the weekly grid, with its target, comparison and eligibility (no seasonal normal yet)."""
    rows, v = [], y.to_numpy()
    pos = {t: i for i, t in enumerate(y.index)}
    t = GRID0
    while t + pd.Timedelta(days=7) <= END:
        i = pos[t]
        nxt, prev, w2, m28 = v[i + 1:i + 8], v[i - 6:i + 1], v[i - 13:i - 6], v[i - 27:i + 1]
        ok = (np.isfinite(nxt).all() and np.isfinite(prev).all() and np.isfinite(w2).sum() >= 5 and np.isfinite(m28).sum() >= 20)
        why = None if ok else ("target week not complete" if not np.isfinite(nxt).all() else "comparison week not complete"
                               if not np.isfinite(prev).all() else "too few complete days in the earlier windows")
        rows.append({"origin": t, "target_start": t + pd.Timedelta(days=1), "target_end": t + pd.Timedelta(days=7),
                     "eligible": bool(ok), "why_not": why,
                     "y_next": float(nxt.sum()) if ok else np.nan, "y_prev": float(prev.sum()) if ok else np.nan,
                     "week2": float(np.nanmean(w2) * 7) if ok else np.nan, "mean28": float(np.nanmean(m28) * 7) if ok else np.nan,
                     "last_day": float(v[i]) if ok else np.nan})
        t += pd.Timedelta(days=7)
    return pd.DataFrame(rows)


def with_features(o: pd.DataFrame, normal: np.ndarray) -> pd.DataFrame:
    """Add the seasonal normals (from the given training years' normal) and the model inputs."""
    o = o.copy()
    n_next, n_prev = [], []
    for t in o["origin"]:
        n_next.append(normal[_doy365(pd.date_range(t + pd.Timedelta(days=1), periods=7))].sum())
        n_prev.append(normal[_doy365(pd.date_range(t - pd.Timedelta(days=6), periods=7))].sum())
    o["normal_next"], o["normal_prev"] = n_next, n_prev
    ang = 2 * np.pi * (o["target_start"].dt.dayofyear.to_numpy() - 1) / 365.25
    o["ln_prev7"], o["ln_week2"], o["ln_mean28"] = np.log(o["y_prev"] + C), np.log(o["week2"] + C), np.log(o["mean28"] + C)
    o["ln_last_day"] = np.log(o["last_day"] + 1)
    o["ln_normal_next"], o["ln_normal_prev"] = np.log(o["normal_next"] + C), np.log(o["normal_prev"] + C)
    o["sin1"], o["cos1"], o["sin2"], o["cos2"] = np.sin(ang), np.cos(ang), np.sin(2 * ang), np.cos(2 * ang)
    o["z"] = np.log(o["y_next"] + C)
    return o


# ---------- benchmarks and candidates (all predict z = ln(Y_next + 7)) ----------
def bench(f: pd.DataFrame) -> dict[str, np.ndarray]:
    return {"B0": f["ln_prev7"].to_numpy(), "B1": f["ln_normal_next"].to_numpy(),
            "B2": (f["ln_prev7"] + f["ln_normal_next"] - f["ln_normal_prev"]).to_numpy()}


def ridge_fit(X: np.ndarray, z: np.ndarray, lam: float) -> dict:
    mu, sd = X.mean(axis=0), X.std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    Xs = (X - mu) / sd
    beta = np.linalg.solve(Xs.T @ Xs + lam * np.eye(X.shape[1]), Xs.T @ (z - z.mean()))
    return {"kind": "ridge", "lambda": lam, "mean": mu.tolist(), "sd": sd.tolist(), "beta": beta.tolist(), "intercept": float(z.mean())}


def ridge_predict(m: dict, X: np.ndarray) -> np.ndarray:
    return m["intercept"] + ((X - np.array(m["mean"])) / np.array(m["sd"])) @ np.array(m["beta"])


def stumps_fit(X: np.ndarray, z: np.ndarray, rounds: int) -> dict:
    """Gradient boosting with depth-1 trees and squared loss. Cuts are the training fold's own quantiles."""
    cuts = [np.unique(np.quantile(X[:, j], np.arange(1, N_CUTS + 1) / (N_CUTS + 1))) for j in range(X.shape[1])]
    f = np.full(len(z), z.mean())
    trees = []
    for _ in range(rounds):
        r, best = z - f, None
        for j, cj in enumerate(cuts):
            for thr in cj:
                left = X[:, j] <= thr
                nl, nr = int(left.sum()), int((~left).sum())
                if nl < MIN_LEAF or nr < MIN_LEAF:
                    continue
                ml, mr = r[left].mean(), r[~left].mean()
                gain = nl * ml * ml + nr * mr * mr
                if best is None or gain > best[0]:
                    best = (gain, j, float(thr), float(ml), float(mr))
        if best is None:
            break
        _, j, thr, ml, mr = best
        f = f + LEARNING_RATE * np.where(X[:, j] <= thr, ml, mr)
        trees.append([j, thr, LEARNING_RATE * ml, LEARNING_RATE * mr])
    return {"kind": "boosted_stumps", "rounds": rounds, "intercept": float(z.mean()), "trees": trees,
            "learning_rate": LEARNING_RATE, "cuts_per_input": N_CUTS, "min_leaf": MIN_LEAF}


def stumps_predict(m: dict, X: np.ndarray, rounds: int | None = None) -> np.ndarray:
    f = np.full(X.shape[0], m["intercept"])
    for j, thr, a, b in m["trees"][:rounds]:
        f = f + np.where(X[:, j] <= thr, a, b)
    return f


# ---------- scoring ----------
def observed_class(y_next, y_prev) -> np.ndarray:
    r = (np.asarray(y_next) + C) / (np.asarray(y_prev) + C)
    return np.where(r >= UP, "increase", np.where(r <= DOWN, "decrease", "no clear change"))


def issued(z_hat, ln_prev, q) -> np.ndarray:
    """Protocol section 7: a direction only when the point ratio clears the band and the interval excludes no change."""
    lr = np.asarray(z_hat) - np.asarray(ln_prev)
    return np.where((lr >= np.log(UP)) & (lr - q > 0), "increase", np.where((lr <= np.log(DOWN)) & (lr + q < 0), "decrease", "no clear direction"))


def _season(month: int) -> str:
    return "OctNov" if month in (10, 11) else "AprMay" if month in (4, 5) else "other"


def score(f: pd.DataFrame, z_hat: np.ndarray, q: float | None = None) -> dict:
    z, y = f["z"].to_numpy(), f["y_next"].to_numpy()
    y_hat = np.maximum(np.exp(z_hat) - C, 0)
    err = np.abs(z_hat - z)
    out = {"n": int(len(z)), "mae_z": float(err.mean()), "typical_factor": float(np.exp(err.mean())),
           "wape": float(np.abs(y_hat - y).sum() / y.sum()) if y.sum() > 0 else None, "by_season": {}}
    seasons = f["target_start"].dt.month.map(_season).to_numpy()
    for s in ("OctNov", "AprMay", "other"):
        k = seasons == s
        if k.any():
            out["by_season"][s] = {"n": int(k.sum()), "mae_z": float(err[k].mean()),
                                   "wape": float(np.abs(y_hat[k] - y[k]).sum() / y[k].sum()) if y[k].sum() > 0 else None}
    obs = observed_class(y, f["y_prev"].to_numpy())
    point = observed_class(y_hat, f["y_prev"].to_numpy())
    out["three_way_agreement_point"] = float((obs == point).mean())
    if q is not None:
        d = issued(z_hat, f["ln_prev7"].to_numpy(), q)
        on = d != "no clear direction"
        true_up = (y + C) / (f["y_prev"].to_numpy() + C) > 1
        right = ((d == "increase") & true_up) | ((d == "decrease") & ~true_up & ((y + C) / (f["y_prev"].to_numpy() + C) < 1))
        out["direction"] = {"issued": int(on.sum()), "abstained": int((~on).sum()), "right_when_issued": int(right[on].sum()),
                            "share_right_when_issued": float(right[on].mean()) if on.any() else None,
                            "issued_increase": int((d == "increase").sum()), "issued_decrease": int((d == "decrease").sum())}
        out["interval"] = {"q": float(q), "coverage": float((err <= q).mean()), "width_ratio": float(np.exp(2 * q))}
    return out


def bootstrap_gain(err_base: np.ndarray, err_model: np.ndarray) -> dict:
    """90% interval of (baseline error - model error), block bootstrap over consecutive origins."""
    rng = np.random.default_rng(BOOT_SEED)
    n = len(err_base)
    starts = np.arange(0, n, BOOT_BLOCK)
    blocks = [np.arange(s, min(n, s + BOOT_BLOCK)) for s in starts]
    gains = np.empty(BOOT_N)
    for b in range(BOOT_N):
        idx = np.concatenate([blocks[i] for i in rng.integers(0, len(blocks), len(blocks))])
        gains[b] = err_base[idx].mean() - err_model[idx].mean()
    return {"gain": float(err_base.mean() - err_model.mean()), "lo90": float(np.quantile(gains, 0.05)), "hi90": float(np.quantile(gains, 0.95)),
            "blocks": len(blocks), "block": BOOT_BLOCK, "resamples": BOOT_N, "seed": BOOT_SEED}


# ---------- folds ----------
def fold(y: pd.Series, o: pd.DataFrame, test_year: int) -> tuple[pd.DataFrame, pd.DataFrame, list[int]]:
    """Training and test origins for one test year: training targets end before 1 January of that year; the seasonal
    normal comes from the years before it."""
    years = [yr for yr in range(START.year, test_year)]
    f = with_features(o[o["eligible"]], daily_normal(y, years))
    cut = pd.Timestamp(year=test_year, month=1, day=1)
    train = f[f["target_end"] < cut]
    test = f[(f["target_start"] >= cut) & (f["target_end"] <= pd.Timestamp(year=test_year, month=12, day=31))]
    return train, test, years


def _X(f: pd.DataFrame) -> np.ndarray:
    return f[list(FEATURES)].to_numpy(float)


def _provenance() -> dict:
    proto = (config.ROOT / PROTOCOL).read_bytes()
    rep = analysis.ingest_report()
    return {"protocol": PROTOCOL, "protocol_sha256": hashlib.sha256(proto).hexdigest(), "code_state": ingest.code_state(),
            "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "approved": APPROVED,
            "inputs": {"detections": "data/processed/pak_detections.parquet", "detections_sha256": rep["output_sha256"],
                       "ingest_built_utc": rep["built_utc"], "missing_days_list": "research/metadata/provider_missing_dates.json"},
            "environment": {"python": _platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__},
            "runner": "python -m c08.outlook"}


def _dump(path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=str), encoding="utf-8")


def audit() -> dict:
    y = daily_series()
    o = origins(y)
    by_year = {}
    for yr in range(START.year, END.year + 1):
        part, oo = y[y.index.year == yr], o[o["target_start"].dt.year == yr]
        by_year[yr] = {"days": int(len(part)), "complete_days": int(part.notna().sum()), "zero_days": int((part == 0).sum()),
                       "detections": int(part.sum()), "origins": int(len(oo)), "eligible_origins": int(oo["eligible"].sum())}
    why = o.loc[~o["eligible"], "why_not"].value_counts().to_dict()
    out = {"what": "Audit of the daily series behind Protocol O01 (no fitting)", "area": AREA, "satellite": "NOAA-20 VIIRS",
           "series": [str(START.date()), str(END.date())], "days": int(len(y)), "complete_days": int(y.notna().sum()),
           "days_without_a_value": int(y.isna().sum()), "last_complete_day": str(y.dropna().index.max().date()),
           "origins": int(len(o)), "eligible_origins": int(o["eligible"].sum()), "ineligible_why": why, "by_year": by_year,
           "vintage": "FIRMS country archive, standard (reprocessed) stream. No as-issued near-real-time vintages are held for these years.",
           **_provenance()}
    _dump(OUT / "audit.json", out)
    return out


def validate() -> dict:
    y = daily_series()
    o = origins(y)
    per, preds = {}, {}
    for V in VAL_YEARS:
        train, test, years = fold(y, o, V)
        Xtr, ztr, Xte = _X(train), train["z"].to_numpy(), _X(test)
        zs = dict(bench(test))
        for lam in RIDGE_GRID:
            zs[f"M1_ridge_{lam:g}"] = ridge_predict(ridge_fit(Xtr, ztr, lam), Xte)
        big = stumps_fit(Xtr, ztr, max(ROUNDS_GRID))
        for r in ROUNDS_GRID:
            zs[f"M2_stumps_{r}"] = stumps_predict(big, Xte, r)
        per[V] = {"train_origins": int(len(train)), "test_origins": int(len(test)), "normal_years": years,
                  "mae_z": {k: float(np.abs(v - test["z"].to_numpy()).mean()) for k, v in zs.items()}}
        for k, v in zs.items():
            preds.setdefault(k, []).append(np.abs(v - test["z"].to_numpy()))
    mean_mae = {k: float(np.mean([per[V]["mae_z"][k] for V in VAL_YEARS])) for k in per[VAL_YEARS[0]]["mae_z"]}
    best_ridge = min((k for k in mean_mae if k.startswith("M1")), key=mean_mae.get)
    best_stumps = min((k for k in mean_mae if k.startswith("M2")), key=mean_mae.get)
    carried = min((best_ridge, best_stumps), key=mean_mae.get)
    q = float(np.quantile(np.concatenate(preds[carried]), 0.80))
    out = {"what": "Protocol O01 validation on 2021-2024 (every choice is made here; 2025 is not read)", "years": list(VAL_YEARS),
           "per_year": per, "mean_mae_z": mean_mae,
           "chosen": {"ridge": best_ridge, "ridge_lambda": float(best_ridge.rsplit("_", 1)[1]), "stumps": best_stumps,
                      "stumps_rounds": int(best_stumps.rsplit("_", 1)[1]), "carried_forward": carried,
                      "rule": "lowest mean absolute error of z, averaged over the four validation years"},
           "interval_q": q, "interval_rule": "80th percentile of the carried-forward model's absolute validation errors",
           "pooled_validation_origins": int(sum(per[V]["test_origins"] for V in VAL_YEARS)), **_provenance()}
    _dump(OUT / "validation.json", out)
    return out


def holdout() -> dict:
    target = OUT / "holdout.json"
    if target.exists():
        raise SystemExit(f"Refusing to run: {target.relative_to(config.ROOT)} exists. The held-out year is read once.")
    val = json.loads((OUT / "validation.json").read_text(encoding="utf-8"))
    ch, q = val["chosen"], val["interval_q"]
    y = daily_series()
    o = origins(y)
    train, test, years = fold(y, o, TEST_YEAR)
    Xtr, ztr, Xte, z = _X(train), train["z"].to_numpy(), _X(test), test["z"].to_numpy()
    ridge = ridge_fit(Xtr, ztr, ch["ridge_lambda"])
    stumps = stumps_fit(Xtr, ztr, ch["stumps_rounds"])
    zs = dict(bench(test)) | {"M1": ridge_predict(ridge, Xte), "M2": stumps_predict(stumps, Xte)}
    carried = "M1" if ch["carried_forward"].startswith("M1") else "M2"
    scores = {k: score(test, v, q if k == carried else None) for k, v in zs.items()}
    errs = {k: np.abs(v - z) for k, v in zs.items()}
    boot = bootstrap_gain(errs["B2"], errs[carried])
    m, b2, d, iv = scores[carried], scores["B2"], scores[carried]["direction"], scores[carried]["interval"]
    rules = [
        {"rule": "1a. At least 10% lower error than the declared baseline (B2)", "value": f"{m['mae_z']:.4f} against {b2['mae_z']:.4f} ({(1 - m['mae_z'] / b2['mae_z']) * 100:+.1f}%)",
         "passed": bool(m["mae_z"] <= 0.9 * b2["mae_z"])},
        {"rule": "1b. Lower error than persistence (B0) and the seasonal normal (B1)", "value": f"B0 {scores['B0']['mae_z']:.4f}, B1 {scores['B1']['mae_z']:.4f}",
         "passed": bool(m["mae_z"] < scores["B0"]["mae_z"] and m["mae_z"] < scores["B1"]["mae_z"])},
        {"rule": "1c. The 90% bootstrap interval of the gain over B2 lies above zero", "value": f"{boot['lo90']:+.4f} to {boot['hi90']:+.4f}", "passed": bool(boot["lo90"] > 0)},
        {"rule": "2. Coverage of the 80% interval between 70% and 90%", "value": f"{iv['coverage'] * 100:.0f}%", "passed": bool(0.70 <= iv["coverage"] <= 0.90)},
        {"rule": "3. A direction issued on at least 10 origins, at least 70% of them right",
         "value": f"issued {d['issued']}, right {d['right_when_issued']}" + (f" ({d['share_right_when_issued'] * 100:.0f}%)" if d["issued"] else ""),
         "passed": bool(d["issued"] >= 10 and (d["share_right_when_issued"] or 0) >= 0.70)},
    ]
    lo, hi = np.maximum(np.exp(zs[carried] - q) - C, 0), np.exp(zs[carried] + q) - C
    dirs = issued(zs[carried], test["ln_prev7"].to_numpy(), q)
    rows = [{"origin": str(t.date()), "target_start": str(a.date()), "target_end": str(e.date()), "y_prev": float(p), "y_next": float(n),
             "predicted": float(max(np.exp(zh) - C, 0)), "lo80": float(l), "hi80": float(h), "b2": float(max(np.exp(b) - C, 0)),
             "issued": str(di), "observed": str(ob)}
            for t, a, e, p, n, zh, l, h, b, di, ob in zip(test["origin"], test["target_start"], test["target_end"], test["y_prev"], test["y_next"],
                                                          zs[carried], lo, hi, zs["B2"], dirs, observed_class(test["y_next"], test["y_prev"]))]
    names = {"B0": "Persistence", "B1": "Seasonal normal", "B2": "Seasonal-scaled persistence (declared baseline)",
             "M1": f"Ridge regression (penalty {ch['ridge_lambda']:g})", "M2": f"Boosted regression stumps ({ch['stumps_rounds']} rounds)"}
    out = {"test": "O01", "title": "Next seven days of NOAA-20 detections in Punjab: held-out year 2025 (retrospective)",
           "area": AREA, "satellite": "NOAA-20 VIIRS 375 m", "units": "retained detections summed over seven complete UTC days",
           "held_out_year": TEST_YEAR, "train_origins": int(len(train)), "test_origins": int(len(test)),
           "ineligible_test_origins": int(((o["target_start"].dt.year == TEST_YEAR) & (o["target_end"].dt.year == TEST_YEAR) & ~o["eligible"]).sum()),
           "normal_years": years, "carried_forward": carried, "names": names, "scores": scores, "bootstrap_gain_over_B2": boot,
           "interval_q": q, "release_rules_1_to_3": rules, "skill_gate_passed": bool(all(r["passed"] for r in rules)),
           "rows": rows, "last_input_day": str(END.date()),
           "note": "A retrospective test on reprocessed archive data. It is not a real-time backtest and not a current forecast.",
           **_provenance()}
    _dump(OUT / "model.json", {"ridge": ridge, "boosted_stumps": stumps, "inputs": list(FEATURES), "trained_on_origins_ending_by": "2024-12-31",
                               "normal_years": years, "carried_forward": carried, "interval_q": q})
    pd.DataFrame(rows).to_csv(OUT / "predictions_holdout.csv", index=False)
    _dump(target, out)
    return out


# ---------- what the app shows ----------
def summary(today: date | None = None) -> dict:
    """Saved results only. An outlook is 'released' only when rules 1-3 passed on the held-out year and the inputs are fresh."""
    today = today or datetime.now(timezone.utc).date()
    base = {"experimental": True, "protocol": PROTOCOL, "area": AREA, "satellite": "NOAA-20 VIIRS 375 m",
            "target": "The sum of NOAA-20 detections in Punjab over the next seven complete UTC days, compared with the seven days just ended.",
            "threshold": "Increase: at least 25% more. Decrease: at least 20% fewer (the same band, downward). Otherwise no clear change.",
            "not": "Not a forecast of fires, burned area, emissions or danger, and not a warning system. One satellite's detections only."}
    files = {k: OUT / f"{k}.json" for k in ("audit", "validation", "holdout")}
    if not files["holdout"].is_file():
        got = [k for k, p in files.items() if p.is_file()]
        return base | {"available": False, "state": "not_run", "reason": "Forecast unavailable: the held-out test of Protocol O01 has not been run in this copy"
                       + (f" (done so far: {', '.join(got)})." if got else ".")}
    h = json.loads(files["holdout"].read_text(encoding="utf-8"))
    v = json.loads(files["validation"].read_text(encoding="utf-8"))
    a = json.loads(files["audit"].read_text(encoding="utf-8")) if files["audit"].is_file() else None
    stale = (today - date.fromisoformat(h["last_input_day"])).days
    fresh = {"rule": f"4. The last complete input day is at most {FRESH_DAYS} days old, in the tested processing stream",
             "value": f"last input day {h['last_input_day']}, {stale} days before {today.isoformat()}", "passed": bool(stale <= FRESH_DAYS)}
    released = bool(h["skill_gate_passed"] and fresh["passed"])
    if released:
        state, reason = "released", "The release rule holds."
    elif not h["skill_gate_passed"]:
        state = "gate_failed"
        failed = [r["rule"] for r in h["release_rules_1_to_3"] if not r["passed"]]
        reason = ("Forecast unavailable: the model did not meet the release rule on the held-out year (" + "; ".join(failed) + "). "
                  "The benchmark results are shown as they came out.")
    else:
        state = "hindcast_only"
        reason = (f"Forecast unavailable today: the tested inputs end on {h['last_input_day']} ({stale} days ago). The result below is a "
                  "retrospective test (hindcast) on archive data, not a current outlook.")
    return base | {"available": True, "state": state, "released": released, "reason": reason, "holdout": h,
                   "validation": {k: v[k] for k in ("years", "mean_mae_z", "chosen", "interval_q", "pooled_validation_origins", "per_year")},
                   "audit": a and {k: a[k] for k in ("days", "complete_days", "days_without_a_value", "last_complete_day", "origins", "eligible_origins", "ineligible_why", "vintage")},
                   "rules": h["release_rules_1_to_3"] + [fresh], "files": [f"experiments/O01_outlook/{k}.json" for k in files] + ["experiments/O01_outlook/model.json", "experiments/O01_outlook/predictions_holdout.csv"]}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["audit"]:
        a = audit()
        print(json.dumps({k: a[k] for k in ("days", "complete_days", "days_without_a_value", "last_complete_day", "origins", "eligible_origins", "ineligible_why")}))
        print(json.dumps(a["by_year"]))
    elif argv[:1] == ["validate"]:
        v = validate()
        print(json.dumps({k: round(x, 4) for k, x in v["mean_mae_z"].items()}))
        print(json.dumps(v["chosen"]), "q =", round(v["interval_q"], 4))
    elif argv[:1] == ["holdout"]:
        h = holdout()
        print(json.dumps({k: {"mae_z": round(s["mae_z"], 4), "wape": s["wape"] and round(s["wape"], 3)} for k, s in h["scores"].items()}))
        for r in h["release_rules_1_to_3"]:
            print(("PASS " if r["passed"] else "FAIL ") + r["rule"] + ": " + r["value"])
        print("skill gate passed:", h["skill_gate_passed"])
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
