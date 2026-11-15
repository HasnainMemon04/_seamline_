"""Protocol P02 D1 and D2: a camera model (forward observation operator) and the clock test.

python -m c08.observe fit      # F00: fit p(F) for Aqua and Terra on Punjab 2014-2017
python -m c08.observe camera   # F01: held-out tests T1-T3, run once
python -m c08.observe clock    # F02: Aqua versus Terra clock test, run once

The camera model predicts how many day-pass detections a MODIS satellite reported
from the fire cells S-NPP saw: A_hat = alpha * sum p(F) over cells, where
p(F) = logistic(b0 + b1 ln F) is an effective probability (sensor sensitivity,
coverage, clouds, the time between passes and geolocation together). It is
compared with one multiplier fitted on the same data. experiments/PROTOCOL_P02.md
fixes every choice here; F01 and F02 refuse to overwrite their results.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from . import config, ingest, p01, series

CELL_DEG = 0.01
MATCH_KM = 1.5
KM_PER_DEG = 111.0
COS_LAT = np.cos(np.radians(31.0))
FIT_YEARS = (2014, 2015, 2016, 2017)
T1_MONTHS = [("2012-02", "2013-12"), ("2018-01", "2021-12")]
TEST_REGIONS = ("Sindh", "Khyber Pakhtunkhwa")
TRANSFER_MONTHS = ("2012-02", "2021-12")
CLOCK_BEFORE, CLOCK_AFTER = (2018, 2019, 2020, 2021), (2023, 2024, 2025)
SEED, N_BOOT = 20261103, 1000
OUT = {k: config.EXPERIMENTS / v for k, v in
       {"fit": "P02_F00_fit", "camera": "P02_F01_camera", "clock": "P02_F02_clock"}.items()}


def day_detections(d: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Standard-stream, quality-filtered, type-0 day-pass detections of one platform (all Pakistan)."""
    q = series.select(d)
    return q[(q.platform == platform) & (q.daynight == "D")]


def fire_cells(d: pd.DataFrame, region: str) -> pd.DataFrame:
    """S-NPP day-pass detections grouped into 0.01 degree cells per UTC date, with summed FRP."""
    v = day_detections(d, "SNPP")
    v = v[v.province == region]
    g = v.assign(cx=np.floor(v.longitude / CELL_DEG), cy=np.floor(v.latitude / CELL_DEG))
    cells = g.groupby(["date_utc", "cx", "cy"], observed=True).agg(
        frp=("frp", "sum"), lon=("longitude", "mean"), lat=("latitude", "mean"), pixels=("frp", "size")).reset_index()
    cells["month"] = cells.date_utc.dt.to_period("M").dt.start_time
    return cells


def mark_hits(cells: pd.DataFrame, modis: pd.DataFrame) -> np.ndarray:
    """True where a MODIS detection lies within MATCH_KM of the cell on the same UTC date."""
    hit = np.zeros(len(cells), dtype=bool)
    radius = MATCH_KM / KM_PER_DEG
    by_day = {pd.Timestamp(k): g for k, g in modis.groupby("date_utc")}  # same key type on both sides
    for day, idx in cells.groupby("date_utc").indices.items():
        m = by_day.get(pd.Timestamp(day))
        if m is None or m.empty:
            continue
        tree = cKDTree(np.c_[m.longitude.to_numpy() * COS_LAT, m.latitude.to_numpy()])
        c = cells.iloc[idx]
        dist, _ = tree.query(np.c_[c.lon.to_numpy() * COS_LAT, c.lat.to_numpy()], k=1)
        hit[idx] = dist <= radius
    return hit


def logistic_irls(x: np.ndarray, y: np.ndarray, *, iters: int = 100, tol: float = 1e-10) -> np.ndarray:
    """Logistic regression with intercept by iteratively reweighted least squares."""
    X = np.column_stack([np.ones(len(x)), x])
    beta = np.zeros(2)
    for _ in range(iters):
        eta = X @ beta
        p = 1 / (1 + np.exp(-np.clip(eta, -30, 30)))
        w = np.clip(p * (1 - p), 1e-9, None)
        z = eta + (y - p) / w
        xtw = X.T * w
        new = np.linalg.solve(xtw @ X, xtw @ z)
        if np.max(np.abs(new - beta)) < tol:
            return new
        beta = new
    return beta


def p_detect(frp: np.ndarray, beta) -> np.ndarray:
    return 1 / (1 + np.exp(-(beta[0] + beta[1] * np.log(np.clip(frp, 1e-3, None)))))


def monthly_counts(d: pd.DataFrame, region: str, platform: str) -> pd.Series:
    q = day_detections(d, platform)
    q = q[q.province == region]
    return q.groupby(q.date_utc.dt.to_period("M").dt.start_time).size()


def complete_months(d: pd.DataFrame, region: str, pair: tuple[str, str]) -> pd.Index:
    w = p01.region_table(d, region)
    return w.index[p01.scored_months(w, pair)]


def fit(d: pd.DataFrame) -> dict:
    """F00: p(F), alpha and the one-multiplier k for Aqua and Terra on Punjab 2014-2017."""
    cells = fire_cells(d, "Punjab")
    snpp = monthly_counts(d, "Punjab", "SNPP")
    out = {}
    for sat in ("Aqua", "Terra"):
        months = complete_months(d, "Punjab", (sat, "SNPP"))
        months = months[months.year.isin(FIT_YEARS)]
        c = cells[cells.month.isin(months)].reset_index(drop=True)
        hit = mark_hits(c, day_detections(d, sat))
        beta = logistic_irls(np.log(np.clip(c.frp.to_numpy(), 1e-3, None)), hit.astype(float))
        a = monthly_counts(d, "Punjab", sat).reindex(months, fill_value=0)
        s = snpp.reindex(months, fill_value=0)
        alpha = float(a.sum() / p_detect(c.frp.to_numpy(), beta).sum())
        out[sat] = {"b0": float(beta[0]), "b1": float(beta[1]), "alpha": alpha, "k": float(s.sum() / a.sum()),
                    "fit_months": int(len(months)), "cells": int(len(c)), "hit_rate": float(hit.mean()),
                    "modis_detections": int(a.sum()), "snpp_detections": int(s.sum()),
                    "p_at_MW": {str(f): float(p_detect(np.array([f]), beta)[0]) for f in (1, 2, 5, 10, 20, 50, 100)}}
    return out


def predict_months(d: pd.DataFrame, region: str, sat: str, prm: dict, months: pd.Index) -> pd.DataFrame:
    cells = fire_cells(d, region)
    cells = cells[cells.month.isin(months)]
    cam = cells.assign(p=p_detect(cells.frp.to_numpy(), (prm["b0"], prm["b1"]))).groupby("month").p.sum() * prm["alpha"]
    out = pd.DataFrame(index=months)
    out["actual"] = monthly_counts(d, region, sat).reindex(months, fill_value=0)
    out["snpp"] = monthly_counts(d, region, "SNPP").reindex(months, fill_value=0)
    out["camera"] = cam.reindex(months, fill_value=0.0)
    out["baseline"] = out["snpp"] / prm["k"]
    return out


def scores(t: pd.DataFrame) -> dict:
    res = {}
    for m in ("camera", "baseline"):
        yearly = t.groupby(t.index.year).apply(lambda g: g[m].sum() / g.actual.sum() - 1 if g.actual.sum() else np.nan)
        res[m] = {"wape": float((t[m] - t.actual).abs().sum() / t.actual.sum()),
                  "bias": float(t[m].sum() / t.actual.sum() - 1),
                  "yearly_bias": {int(k): round(float(v), 4) for k, v in yearly.items()},
                  "yearly_bias_sd": float(np.nanstd(yearly.to_numpy(), ddof=1))}
    res["n_months"] = int(len(t))
    return res


def _window(months: pd.Index, spans) -> pd.Index:
    keep = np.zeros(len(months), dtype=bool)
    for a, b in spans:
        keep |= (months >= pd.Timestamp(a)) & (months <= pd.Timestamp(b))
    return months[keep]


def camera(d: pd.DataFrame, prm: dict) -> dict:
    """F01: held-out tests T1 (Punjab other years), T2 Sindh, T3 Khyber Pakhtunkhwa, Aqua only."""
    a = prm["Aqua"]
    res = {}
    t1 = _window(complete_months(d, "Punjab", ("Aqua", "SNPP")), T1_MONTHS)
    res["T1_Punjab"] = scores(predict_months(d, "Punjab", "Aqua", a, t1))
    for key, region in zip(("T2_Sindh", "T3_KP"), TEST_REGIONS):
        mo = _window(complete_months(d, region, ("Aqua", "SNPP")), [TRANSFER_MONTHS])
        res[key] = scores(predict_months(d, region, "Aqua", a, mo))
    better = {k: res[k]["camera"]["wape"] < res[k]["baseline"]["wape"] for k in ("T1_Punjab", "T2_Sindh", "T3_KP")}
    stable = res["T1_Punjab"]["camera"]["yearly_bias_sd"] < res["T1_Punjab"]["baseline"]["yearly_bias_sd"]
    res["decision"] = {"lower_wape": better, "more_stable_T1": stable,
                       "supported": bool(better["T1_Punjab"] and (better["T2_Sindh"] or better["T3_KP"]) and stable)}
    return res


def clock(d: pd.DataFrame, prm: dict) -> dict:
    """F02: yearly Q = actual / camera prediction for Aqua and Terra, and the Aqua-minus-Terra contrast."""
    cells = fire_cells(d, "Punjab")
    rng = np.random.default_rng(SEED)
    per_day, out = {}, {"yearly_Q": {}, "periods": {}}
    for sat in ("Aqua", "Terra"):
        b = (prm[sat]["b0"], prm[sat]["b1"])
        months = complete_months(d, "Punjab", (sat, "SNPP"))
        months = months[(months.year >= 2012) & (months.year <= 2025)]
        c = cells[cells.month.isin(months)]
        pred = c.assign(p=p_detect(c.frp.to_numpy(), b)).groupby("date_utc").p.sum() * prm[sat]["alpha"]
        mod = day_detections(d, sat)
        mod = mod[(mod.province == "Punjab") & mod.date_utc.dt.to_period("M").dt.start_time.isin(months)]
        act = mod.groupby("date_utc").size()
        days = pd.DataFrame({"pred": pred, "act": act}).fillna(0.0)
        days["year"], days["month"] = days.index.year, days.index.month
        per_day[sat] = days
    for season, mset in (("OctNov", (10, 11)), ("other", tuple(m for m in range(1, 13) if m not in (10, 11)))):
        yq, boots = {}, {}
        for sat, days in per_day.items():
            s = days[days.month.isin(mset)]
            yq[sat] = {int(y): float(g.act.sum() / g.pred.sum()) for y, g in s.groupby("year") if g.pred.sum() > 0}
            reps = np.zeros((N_BOOT, 2))
            for j, years in enumerate((CLOCK_BEFORE, CLOCK_AFTER)):
                groups = [s[s.year == y][["act", "pred"]].to_numpy() for y in years if y in yq[sat]]
                for i in range(N_BOOT):
                    qs = []
                    for g in groups:
                        r = g[rng.integers(0, len(g), len(g))]
                        if r[:, 1].sum() > 0:
                            qs.append(r[:, 0].sum() / r[:, 1].sum())
                    reps[i, j] = np.mean(qs) if qs else np.nan
            boots[sat] = reps[:, 1] / reps[:, 0] - 1
        delta = {sat: float(np.mean([yq[sat][y] for y in CLOCK_AFTER if y in yq[sat]])
                            / np.mean([yq[sat][y] for y in CLOCK_BEFORE if y in yq[sat]]) - 1) for sat in per_day}
        cboot = boots["Aqua"] - boots["Terra"]
        out["yearly_Q"][season] = yq
        out["periods"][season] = {
            "delta": delta, "delta_90": {s: [float(np.nanquantile(boots[s], .05)), float(np.nanquantile(boots[s], .95))] for s in boots},
            "contrast": delta["Aqua"] - delta["Terra"],
            "contrast_90": [float(np.nanquantile(cboot, .05)), float(np.nanquantile(cboot, .95))],
            "years_used": {s: sorted(y for y in yq[s] if y in CLOCK_BEFORE + CLOCK_AFTER) for s in yq}}
    on, ot = out["periods"]["OctNov"], out["periods"]["other"]
    out["reading"] = {"contrast_octnov_above_0": on["contrast_90"][0] > 0,
                      "octnov_exceeds_other": on["contrast"] > ot["contrast"],
                      "consistent_with_later_burning": bool(on["contrast_90"][0] > 0 and on["contrast"] > ot["contrast"])}
    return out


def _save(key: str, result: dict, *, once: bool) -> None:
    f = OUT[key] / "result.json"
    if once and f.is_file():
        raise SystemExit(f"{f.relative_to(config.ROOT)} exists: P02 {key} is run once (see PROTOCOL_P02.md).")
    OUT[key].mkdir(parents=True, exist_ok=True)
    meta = {"protocol": "experiments/PROTOCOL_P02.md", "run_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "code_state": ingest.code_state()}
    f.write_text(json.dumps(meta | result, indent=2), encoding="utf-8")


def main(argv: list[str]) -> int:
    cmd = (argv or ["fit"])[0]
    d, _ = p01.load_inputs()
    if cmd == "fit":
        _save("fit", {"experiment": "P02 F00 camera-model fit (Punjab 2014-2017)", "params": fit(d)}, once=False)
    else:
        prm = json.loads((OUT["fit"] / "result.json").read_text(encoding="utf-8"))["params"]
        if cmd == "camera":
            _save("camera", {"experiment": "P02 F01 camera model, held-out tests", "results": camera(d, prm)}, once=True)
        elif cmd == "clock":
            _save("clock", {"experiment": "P02 F02 clock test", "results": clock(d, prm)}, once=True)
        elif cmd == "figure":
            print(figure())
            return 0
        else:
            print(__doc__)
            return 2
    print((OUT[cmd if cmd != "fit" else "fit"] / "result.json").read_text(encoding="utf-8")[:4000])
    return 0



def figure() -> str:
    """reports/c08/figures/punjab_clock.png: pass times by year, and Oct-Nov Q relative to 2014-17 (F02)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from . import figures as fg
    d, _ = p01.load_inputs()
    q = series.select(d, region="Punjab")
    q = q[q.daynight == "D"]
    lst = ((q.time_utc.dt.hour + q.time_utc.dt.minute / 60 + q.longitude / 15) % 24).groupby([q.platform, q.year], observed=True).median()
    yq = json.loads((OUT["clock"] / "result.json").read_text(encoding="utf-8"))["results"]["yearly_Q"]["OctNov"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.6))
    for ax in (a1, a2):
        fg._style(ax)
    for p, lab in (("Terra", "Terra MODIS"), ("Aqua", "Aqua MODIS"), ("SNPP", "S-NPP VIIRS"), ("NOAA20", "NOAA-20 VIIRS")):
        s = lst.loc[p]
        s = s[s.index >= 2003]
        a1.plot(s.index, s.values, color=fg.COLOR[p], linewidth=2.2, marker="o", markersize=3.5)
        a1.annotate(lab, (s.index[-1], s.values[-1]), xytext=(6, 0 if p != "NOAA20" else -9), textcoords="offset points",
                    color=fg.INK2, fontsize=8.5, va="center")
    a1.set_yticks([9, 10, 11, 12, 13, 14, 15])
    a1.set_yticklabels(["9 am", "10", "11", "noon", "1 pm", "2", "3 pm"])
    a1.set_xlim(2002.5, 2029.5)
    a1.set_title("When each satellite passes over Punjab (local solar time)", loc="left", color=fg.INK, fontsize=10.5)
    for sat in ("Terra", "Aqua"):
        ser = pd.Series({int(y): v for y, v in yq[sat].items()}).sort_index()
        base = ser.loc[list(FIT_YEARS)].mean()
        rel = ser / base
        a2.plot(rel.index, rel.values, color=fg.COLOR[sat], linewidth=2.2, marker="o", markersize=4)
        a2.annotate(f"{sat} MODIS", (rel.index[-1], rel.values[-1]), xytext=(6, 0), textcoords="offset points",
                    color=fg.INK2, fontsize=8.5, va="center")
    a2.axhline(1, color=fg.MUTED, linewidth=1, linestyle="--")
    a2.axvspan(2021.5, 2025.5, color="#f0efec", zorder=0)
    a2.text(2021.7, 0.04, "clocks drifting", transform=a2.get_xaxis_transform(), color=fg.INK2, fontsize=8.5)
    a2.set_xlim(2011.5, 2028.3)
    a2.set_ylim(0, None)
    a2.set_title("Oct–Nov detections reported, relative to what S-NPP's fires predict", loc="left", color=fg.INK, fontsize=10.5)
    a2.set_ylabel("1 = same as in 2014–17", color=fg.INK2)
    fig.text(0.01, 0.01, "Punjab, day passes, quality-filtered vegetation detections. Right: reported ÷ camera-model prediction "
             "(Protocol P02, F02), divided by its 2014–17 average. S-NPP's own pass time stayed near 1:05 pm.",
             color=fg.MUTED, fontsize=8)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    out = fg.FIG / "punjab_clock.png"
    fig.savefig(out, dpi=150, facecolor="#fcfcfb")
    plt.close(fig)
    return str(out)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
