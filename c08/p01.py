"""Protocol P01 experiments: E00 first-run proof, E01 selection, E02 held-out evaluation.

Run in order:  python -m c08.p01 e00 | e01 | e02
Each experiment writes experiments/<ID>/result.json with code revision, input
hashes, configuration, runtime and hardware. E02 refuses to run until E01 has
written its selection, so test years cannot influence the choice of model.
"""
from __future__ import annotations

import json
import os
import platform
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import config, harmonize as hz, ingest, series

SELECTION_YEARS = (2014, 2015, 2016, 2017)
TEST_MONTHS = ("2012-02", "2013-12")
DIAGNOSTIC_YEARS = tuple(range(2018, 2026))
BRIDGE_SELECTION = (2019, 2020, 2021, 2022, 2023)
BRIDGE_TEST = (2024, 2025)
DEPLOY_BACKCAST = ("2012-02", "2017-12")
DEPLOY_BRIDGE = ("2018-04", "2025-12")
OUT = {k: config.EXPERIMENTS / v for k, v in
       {"e00": "E00_first_run", "e01": "E01_selection", "e02": "E02_evaluation", "e03": "E03_sensitivity"}.items()}


def _env() -> dict:
    import psutil
    return {"python": sys.version.split()[0], "pandas": pd.__version__, "numpy": np.__version__,
            "os": platform.platform(), "cpu_count": os.cpu_count(),
            "ram_total_gb": round(psutil.virtual_memory().total / 1e9, 1)}


def _inputs(rep: dict) -> dict:
    return {"detections_parquet_sha256": rep["output_sha256"], "ingest_schema": rep["schema"],
            "raw_files": {f["id"]: f["sha256"] for f in rep["files"]},
            "boundaries": {b["id"]: b["sha256"] for b in rep["boundaries"]},
            "provider_missing_dates": "research/metadata/provider_missing_dates.json"}


def _save(key: str, result: dict) -> None:
    OUT[key].mkdir(parents=True, exist_ok=True)
    (OUT[key] / "result.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")


def load_inputs(rebuild: bool = False) -> tuple[pd.DataFrame, dict]:
    if rebuild or not ingest.DETECTIONS.is_file() or not ingest.INGEST_REPORT.is_file():
        return ingest.build(log=lambda *_: None)
    rep = json.loads(ingest.INGEST_REPORT.read_text(encoding="utf-8"))
    if ingest.acquire.sha256_file(ingest.DETECTIONS) != rep["output_sha256"]:
        return ingest.build(log=lambda *_: None)
    return pd.read_parquet(ingest.DETECTIONS), rep


def region_table(d: pd.DataFrame, region: str) -> pd.DataFrame:
    spans = series.record_spans(d)
    return series.wide(series.monthly(series.select(d, region=region), spans))


def scored_months(w: pd.DataFrame, platforms: tuple[str, ...]) -> pd.Series:
    """P01 change-log item 2: every platform used must be 'complete' in the month."""
    ok = pd.Series(True, index=w.index)
    for p in platforms:
        ok &= w[f"{p}_status"].eq("complete")
    return ok


def obs_total(w: pd.DataFrame, ref: str = "SNPP", passes=("D", "N")) -> pd.Series:
    return w[[f"{ref}_{dn}" for dn in passes]].sum(axis=1, min_count=len(passes))


def loyo(w: pd.DataFrame, years, model: str, *, src="Aqua", ref="SNPP", platforms=("Aqua", "Terra", "SNPP"),
         passes=("D", "N")):
    """Leave-one-year-out predictions over the given years (scored months only)."""
    ok = scored_months(w, platforms)
    preds = []
    for y in years:
        train = w[ok & w.index.year.isin([v for v in years if v != y])]
        held = w[ok & (w.index.year == y)]
        preds.append(hz.predict(held, hz.fit(train, model, src=src, ref=ref, passes=passes)))
    return pd.concat(preds).sort_index()


def e00() -> dict:
    """First-run proof: re-ingest, check observation times and confidence, M0/M1 on selection years."""
    t0 = time.perf_counter()
    d, rep = ingest.build(log=lambda *_: None)
    pun = series.select(d, region="Punjab")
    passes = {}
    for (p, dn), g in pun.groupby(["platform", "daynight"], observed=True):
        hm = g["time_utc"].dt.hour + g["time_utc"].dt.minute / 60
        passes[f"{p}_{dn}"] = {"n": len(g), "utc_hour_p01": round(float(hm.quantile(.01)), 2),
                               "utc_hour_median": round(float(hm.median()), 2),
                               "utc_hour_p99": round(float(hm.quantile(.99)), 2)}
    allq = d[d.stream.eq("standard") & d.province.eq("Punjab")]
    conf = {}
    for p, g in allq.groupby("platform", observed=True):
        if p in ("Terra", "Aqua"):
            c = pd.to_numeric(g["confidence_raw"].astype(str))
            conf[str(p)] = {"below_30": round(float((c < 30).mean()), 4), "30_79": round(float(c.between(30, 79).mean()), 4),
                            "80_up": round(float((c >= 80).mean()), 4)}
        else:
            conf[str(p)] = {k: round(float(v), 4) for k, v in g["confidence_raw"].astype(str).value_counts(normalize=True).items()}
    w = region_table(d, "Punjab")
    sel = w[w.index.year.isin(SELECTION_YEARS)]
    ok = scored_months(sel, ("Aqua", "Terra", "SNPP"))
    obs = obs_total(sel)[ok]
    res = {}
    for m in ("M0", "M1"):
        p = loyo(w, SELECTION_YEARS, m)
        res[m] = hz.metrics(obs, p["pred"].reindex(obs.index))
    k_full = hz.fit(sel[ok], "M1")
    result = {
        "experiment": "E00 first-run proof", "protocol": "experiments/PROTOCOL_P01.md",
        "run_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "code_revision": rep["code_revision"], "code_state": ingest.code_state(), "environment": _env(), "inputs": _inputs(rep),
        "ingest_summary": {k: rep[k] for k in ("rows", "rows_by_platform_stream", "standard_rows_outside_all_provinces",
                                                 "nrt_rows_outside_pakistan_dropped")},
        "archive_rows_rejected": sum(f["rejected_total"] for f in rep["files"] if f["stream"] == "standard"),
        "archive_exact_duplicates": sum(f["exact_duplicates_removed"] for f in rep["files"] if f["stream"] == "standard"),
        "punjab_pass_times_utc": passes, "punjab_confidence_shares_unfiltered": conf,
        "selection_years": SELECTION_YEARS, "scored_months": int(ok.sum()),
        "excluded_months": [str(i.date()) for i in sel.index[~ok]],
        "m1_ratio_all_selection_years": {dn: k_full[dn]["k"] for dn in ("D", "N")},
        "loyo_metrics": res,
        "scope_note": "Selection-year baseline only (E00). Not a model selection or final evaluation.",
        "runtime_s": round(time.perf_counter() - t0, 1),
    }
    sel.to_csv(OUT_DIR("e00") / "punjab_monthly_selection_years.csv")
    _save("e00", result)
    return result


def OUT_DIR(key: str):
    OUT[key].mkdir(parents=True, exist_ok=True)
    return OUT[key]


def choose(scores: dict) -> tuple[str, str]:
    """P01 section 7 and change-log item 6."""
    m1 = scores["M1"]["wape"]
    pool = {m: s for m, s in scores.items() if m == "M1" or s["wape"] < m1}
    best = min(s["wape"] for s in pool.values())
    tied = {m: s for m, s in pool.items() if (s["wape"] - best) / best <= 0.02}
    pick = min(tied, key=lambda m: tied[m]["log_mae"])
    why = (f"lowest WAPE among M1 and models beating it; tie set {sorted(tied)} broken by log-MAE"
           if len(tied) > 1 else "lowest WAPE among M1 and models beating it")
    return pick, why


def e01() -> dict:
    """Model selection: leave-one-year-out over 2014-2017 (Punjab), and the NOAA-20 bridge over 2019-2023."""
    t0 = time.perf_counter()
    d, rep = load_inputs()
    w = region_table(d, "Punjab")
    out = {"experiment": "E01 selection", "protocol": "experiments/PROTOCOL_P01.md",
           "run_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
           "code_revision": rep["code_revision"], "code_state": ingest.code_state(), "environment": _env(), "inputs": _inputs(rep)}
    for name, years, src, plats, models in (
            ("backcast", SELECTION_YEARS, "Aqua", ("Aqua", "Terra", "SNPP"), hz.MODELS),
            ("bridge", BRIDGE_SELECTION, "NOAA20", ("NOAA20", "SNPP"), ("M0", "M1", "M2", "M3"))):
        part = w[w.index.year.isin(years)]
        ok = scored_months(part, plats)
        obs = obs_total(part)[ok]
        scores, resid = {}, {}
        for m in models:
            p = loyo(w, years, m, src=src, platforms=plats)["pred"].reindex(obs.index)
            scores[m] = hz.metrics(obs, p)
            resid[m] = pd.DataFrame({"r": np.log1p(obs) - np.log1p(p), "season": hz.season_of(obs.index.month.to_series())})
        pick, why = choose(scores)
        out[name] = {"years": years, "source": src, "scored_months": int(ok.sum()),
                     "excluded_months": [str(i.date()) for i in part.index[~ok]],
                     "scores": scores, "selected": pick, "reason": why,
                     "interval_log_quantiles": hz.interval_quantiles(resid[pick]),
                     "negative_result": pick == "M1"}
    _save("e01", out)
    (OUT["e01"] / "selection.json").write_text(json.dumps(
        {k: {"selected": out[k]["selected"], "interval_log_quantiles": out[k]["interval_log_quantiles"]}
         for k in ("backcast", "bridge")} | {"written_utc": out["run_utc"]}, indent=2), encoding="utf-8")
    out["runtime_s"] = round(time.perf_counter() - t0, 1)
    _save("e01", out)
    return out


def _window(w, a, b):
    return w[(w.index >= pd.Timestamp(a)) & (w.index <= pd.Timestamp(b))]


def e02() -> dict:
    """Held-out evaluation once: temporal test, drift diagnostic, Sindh, bridge test, differentiator."""
    sel_path = OUT["e01"] / "selection.json"
    if not sel_path.is_file():
        raise SystemExit("Run e01 first: the selection must exist before any test-year score.")
    sel = json.loads(sel_path.read_text(encoding="utf-8"))
    t0 = time.perf_counter()
    d, rep = load_inputs()
    pun, sin = region_table(d, "Punjab"), region_table(d, "Sindh")
    bk, br = sel["backcast"]["selected"], sel["bridge"]["selected"]
    plats = ("Aqua", "Terra", "SNPP")
    out = {"experiment": "E02 held-out evaluation (run once after E01)", "selection_file": str(sel_path.relative_to(config.ROOT) if sel_path.is_relative_to(config.ROOT) else sel_path),
           "selection_written_utc": sel["written_utc"], "selected": {"backcast": bk, "bridge": br},
           "run_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
           "code_revision": rep["code_revision"], "code_state": ingest.code_state(), "environment": _env(), "inputs": _inputs(rep)}

    def score(w, train_w, test_w, models, *, src="Aqua", platforms=plats, params_from=None):
        ok_tr, ok_te = scored_months(train_w, platforms), scored_months(test_w, platforms)
        obs = obs_total(test_w)[ok_te]
        res = {}
        for m in models:
            prm = params_from[m] if params_from else hz.fit(train_w[ok_tr], m, src=src)
            res[m] = hz.metrics(obs, hz.predict(test_w[ok_te], prm)["pred"])
        return res, int(ok_te.sum()), [str(i.date()) for i in test_w.index[~ok_te]]

    train = pun[pun.index.year.isin(SELECTION_YEARS)]
    test = _window(pun, *TEST_MONTHS)
    models = sorted({"M0", "M1", bk})
    s, n, exc = score(pun, train, test, models)
    qs = sel["backcast"]["interval_log_quantiles"]
    okt = scored_months(test, plats)
    fit_sel = hz.fit(train[scored_months(train, plats)], bk)
    pt = hz.predict(test[okt], fit_sel)["pred"]
    iv = hz.apply_interval(pt, qs)
    obs = obs_total(test)[okt]
    out["temporal_test"] = {"months": TEST_MONTHS, "scored_months": n, "excluded": exc, "scores": s,
                            "interval_80_coverage": float(((obs >= iv.lo) & (obs <= iv.hi)).mean())}

    diag = {}
    for y in DIAGNOSTIC_YEARS:
        part = pun[pun.index.year == y]
        sc, n, _ = score(pun, train, part, models)
        versions = sorted(d.loc[(d.platform == "Aqua") & (d.year == y) & d.stream.eq("standard"), "version"].astype(str).unique())
        diag[y] = {"aqua_versions": versions, "scored_months": n, **{m: {k: sc[m][k] for k in ("wape", "bias")} for m in models}}
    out["drift_diagnostic"] = diag

    sin_train = sin[sin.index.year.isin(SELECTION_YEARS)]
    sin_test = _window(sin, *TEST_MONTHS)
    method, n, _ = score(sin, sin_train, sin_test, models)
    punjab_params = {m: hz.fit(train[scored_months(train, plats)], m) for m in models}
    transfer, _, _ = score(sin, sin_train, sin_test, models, params_from=punjab_params)
    out["geographic_test_sindh"] = {"scored_months": n, "method_transfer": method, "parameter_transfer": transfer}

    bplats = ("NOAA20", "SNPP")
    btrain = pun[pun.index.year.isin(BRIDGE_SELECTION)]
    btest = pun[pun.index.year.isin(BRIDGE_TEST)]
    bs, n, exc = score(pun, btrain, btest, sorted({"M0", "M1", br}), src="NOAA20", platforms=bplats)
    out["bridge_test"] = {"years": BRIDGE_TEST, "scored_months": n, "excluded": exc, "scores": bs}

    out["differentiator"] = differentiator(pun, bk, qs)
    out["runtime_s"] = round(time.perf_counter() - t0, 1)
    _save("e02", out)
    return out


def harmonised_record(w: pd.DataFrame, model: str, qs: dict) -> pd.DataFrame:
    """H(m) for 2003-01..2025-12: modelled from Aqua before 2012-02, observed S-NPP after."""
    plats = ("Aqua", "Terra", "SNPP")
    dep = _window(w, *DEPLOY_BACKCAST)
    prm = hz.fit(dep[scored_months(dep, plats)], model)
    rec = _window(w, "2003-01", "2025-12").copy()
    modelled = rec.index < pd.Timestamp("2012-02")
    p = hz.predict(rec[modelled], prm)["pred"]
    iv = hz.apply_interval(p, qs)
    rec["H"] = obs_total(rec)
    rec["H_lo"] = rec["H"]
    rec["H_hi"] = rec["H"]
    rec.loc[modelled, "H"] = p
    rec.loc[modelled, "H_lo"] = iv["lo"]
    rec.loc[modelled, "H_hi"] = iv["hi"]
    rec["H_source"] = np.where(modelled, f"modelled from Aqua ({model})", "observed S-NPP")
    return rec


def differentiator(w: pd.DataFrame, model: str, qs: dict) -> dict:
    """P01 section 8 with change-log item 4: does the apparent change survive harmonisation?"""
    rec = harmonised_record(w, model, qs)
    modis_all = rec[["Terra_D", "Terra_N", "Aqua_D", "Aqua_N"]].sum(axis=1, min_count=1)
    viirs_all = rec[["SNPP_D", "SNPP_N", "NOAA20_D", "NOAA20_N"]].sum(axis=1, min_count=1)
    naive = pd.Series(np.where(rec.index < pd.Timestamp("2012-01"), modis_all, viirs_all), index=rec.index)
    aqua = rec["Aqua_D"] + rec["Aqua_N"]
    out = {}
    for name, months in (("OctNov", (10, 11)), ("AprMay", (4, 5))):
        a = hz.season_stats(naive, months)
        b = hz.season_stats(aqua, months)
        c = hz.season_stats(rec["H"], months)
        c_lo = hz.season_stats(rec["H_lo"], months)
        c_hi = hz.season_stats(rec["H_hi"], months)
        rng = {}
        for k in ("ratio_late_early", "theil_sen_log_slope_per_year"):
            v = sorted([c_lo[k], c_hi[k]])
            rng[k] = {"lo": v[0], "hi": v[1], "naive": a[k], "naive_outside": not (v[0] <= a[k] <= v[1])}
        out[name] = {"naive_stitch": a, "aqua_only": b, "harmonised": c, "harmonised_interval": rng,
                     "claim_raw_exaggerates_change": all(r["naive_outside"] for r in rng.values())}
    return out


def e03() -> dict:
    """Post-hoc sensitivity (declared after E02): the section 8 result under every candidate model.

    The temporal test favoured M1 over the selected M2, so this checks whether the
    differentiator conclusion depends on that choice. It selects nothing.
    """
    sel = json.loads((OUT["e01"] / "selection.json").read_text(encoding="utf-8"))
    d, rep = load_inputs()
    pun = region_table(d, "Punjab")
    e01r = json.loads((OUT["e01"] / "result.json").read_text(encoding="utf-8"))
    qs_by_model = {}
    w = pun
    for m in ("M1", "M2", "M3", "M4"):
        part = w[w.index.year.isin(SELECTION_YEARS)]
        ok = scored_months(part, ("Aqua", "Terra", "SNPP"))
        obs = obs_total(part)[ok]
        p = loyo(w, SELECTION_YEARS, m)["pred"].reindex(obs.index)
        qs_by_model[m] = hz.interval_quantiles(pd.DataFrame({"r": np.log1p(obs) - np.log1p(p),
                                                             "season": hz.season_of(obs.index.month.to_series())}))
    out = {"experiment": "E03 post-hoc sensitivity of the differentiator to the model choice",
           "declared_after": "E02 (temporal test favoured M1 over the selected M2)",
           "selected_model_unchanged": sel["backcast"]["selected"],
           "run_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
           "code_revision": rep["code_revision"], "code_state": ingest.code_state(), "inputs": _inputs(rep), "by_model": {}}
    assert e01r["backcast"]["interval_log_quantiles"] == qs_by_model[sel["backcast"]["selected"]]
    for m, qs in qs_by_model.items():
        dres = differentiator(pun, m, qs)
        out["by_model"][m] = {s: {"ratio_late_early": v["harmonised"]["ratio_late_early"],
                                  "ratio_interval": [v["harmonised_interval"]["ratio_late_early"]["lo"],
                                                     v["harmonised_interval"]["ratio_late_early"]["hi"]],
                                  "theil_sen_log_slope_per_year": v["harmonised"]["theil_sen_log_slope_per_year"],
                                  "naive_ratio": v["naive_stitch"]["ratio_late_early"],
                                  "claim_raw_exaggerates_change": v["claim_raw_exaggerates_change"]}
                              for s, v in dres.items()}
    _save("e03", out)
    return out


if __name__ == "__main__":
    key = (sys.argv[1:] or ["e00"])[0]
    r = {"e00": e00, "e01": e01, "e02": e02, "e03": e03}[key]()
    print(json.dumps(r, indent=1, default=str)[:6000])
