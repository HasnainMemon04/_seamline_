"""Candidate harmonisation models and metrics from Protocol P01 (sections 6-7).

Each model maps a source sensor's monthly detections (Aqua MODIS, or NOAA-20 for
the forward bridge) to S-NPP-VIIRS-equivalent detections, fitted separately for
day and night passes. Inputs are wide monthly tables from c08.series.wide().
Scores compare against S-NPP, another sensor, not ground truth.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import theilslopes

MODELS = ("M0", "M1", "M2", "M3", "M4")
PSEUDO = 30.0  # M2 shrinkage: pseudo-detections toward the pooled ratio (fixed in P01)
ANOMALY_BAND = 1.5  # P01 change log item 5


def season_of(month: pd.Series) -> np.ndarray:
    m = month.to_numpy()
    return np.where(np.isin(m, (4, 5)), "AprMay", np.where(np.isin(m, (10, 11)), "OctNov", "other"))


def _design(df: pd.DataFrame, src: str, dn: str, model: str) -> np.ndarray:
    s = season_of(df.index.month.to_series())
    cols = [np.ones(len(df)), np.log1p(df[f"{src}_{dn}"].to_numpy(float)),
            (s == "AprMay").astype(float), (s == "OctNov").astype(float)]
    if model == "M4":
        cols.append(np.log1p(df[f"Terra_{dn}"].to_numpy(float)))
    return np.column_stack(cols)


def poisson_irls(X: np.ndarray, y: np.ndarray, *, iters: int = 100, tol: float = 1e-10) -> np.ndarray:
    """Poisson GLM with log link by iteratively reweighted least squares."""
    beta = np.zeros(X.shape[1])
    beta[0] = np.log(y.mean() + 0.5)
    for _ in range(iters):
        mu = np.exp(np.clip(X @ beta, -30, 30))
        z = X @ beta + (y - mu) / mu
        xtw = X.T * mu
        new = np.linalg.solve(xtw @ X + 1e-9 * np.eye(X.shape[1]), xtw @ z)
        if np.max(np.abs(new - beta)) < tol:
            return new
        beta = new
    return beta


def fit(train: pd.DataFrame, model: str, *, src: str = "Aqua", ref: str = "SNPP",
        passes: tuple[str, ...] = ("D", "N")) -> dict:
    """Fit one model on training months, separately for day (D) and night (N) passes."""
    params = {"model": model, "src": src, "ref": ref, "n_months": len(train), "passes": tuple(passes)}
    for dn in passes:
        x = train[f"{src}_{dn}"].to_numpy(float)
        y = train[f"{ref}_{dn}"].to_numpy(float)
        if model == "M0":
            p = {}
        elif model in ("M1", "M2"):
            if x.sum() <= 0:
                raise ValueError(f"no {src} {dn} detections in training months; ratio undefined")
            k = y.sum() / x.sum()
            p = {"k": k}
            if model == "M2":
                mo = train.index.month
                p["k_month"] = {int(m): (y[mo == m].sum() + PSEUDO * k) / (x[mo == m].sum() + PSEUDO)
                                for m in range(1, 13)}
        else:
            p = {"beta": poisson_irls(_design(train, src, dn, model), y).tolist()}
        params[dn] = p
    return params


def predict(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Columns pred_<pass> and pred (sum over the fitted passes) in reference-sensor units."""
    model, src = params["model"], params["src"]
    passes = params.get("passes", ("D", "N"))
    out = pd.DataFrame(index=df.index)
    for dn in passes:
        x = df[f"{src}_{dn}"].to_numpy(float)
        p = params[dn]
        if model == "M0":
            v = x
        elif model == "M1":
            v = p["k"] * x
        elif model == "M2":
            v = np.array([p["k_month"][m] for m in df.index.month]) * x
        else:
            v = np.exp(_design(df, src, dn, model) @ np.asarray(p["beta"]))
        out[f"pred_{dn}"] = v
    out["pred"] = out[[f"pred_{dn}" for dn in passes]].sum(axis=1)
    return out


def anomaly_class(v: np.ndarray, med: np.ndarray) -> np.ndarray:
    r = (np.asarray(v, float) + 1) / (np.asarray(med, float) + 1)
    return np.where(r > ANOMALY_BAND, "above", np.where(r < 1 / ANOMALY_BAND, "below", "typical"))


def metrics(obs: pd.Series, pred: pd.Series) -> dict:
    """P01 section 7 metrics on day+night monthly totals (index = month start)."""
    o, p = obs.to_numpy(float), pred.to_numpy(float)
    tot = o.sum()
    out = {"n_months": int(len(o)), "obs_total": float(tot), "pred_total": float(p.sum()),
           "wape": float(np.abs(p - o).sum() / tot) if tot else None,
           "log_mae": float(np.mean(np.abs(np.log1p(p) - np.log1p(o)))),
           "bias": float(p.sum() / tot - 1) if tot else None}
    years = obs.index.year
    peaks = []
    for y in np.unique(years):
        sel = years == y
        if sel.sum() >= 10:  # need most of a year for a peak month to mean anything
            peaks.append(obs.index[sel][np.argmax(o[sel])] == obs.index[sel][np.argmax(p[sel])])
    out["peak_month_agreement"] = float(np.mean(peaks)) if peaks else None
    out["peak_years"] = len(peaks)
    # Anomaly class of each month against the median of the other years' same month.
    agree = []
    frame = pd.DataFrame({"o": o, "p": p, "y": years, "m": obs.index.month})
    for i, r in frame.iterrows():
        others = frame[(frame.m == r.m) & (frame.y != r.y)]
        if len(others) >= 2:
            co = anomaly_class([r.o], [others.o.median()])[0]
            cp = anomaly_class([r.p], [others.p.median()])[0]
            agree.append(co == cp)
    out["anomaly_agreement"] = float(np.mean(agree)) if agree else None
    return out


def interval_quantiles(resid: pd.DataFrame, q=(0.10, 0.90)) -> dict:
    """Per-season quantiles of log residuals log(obs+1) - log(pred+1) (80% interval)."""
    out = {}
    for s, g in resid.groupby("season"):
        out[s] = {"lo": float(np.quantile(g["r"], q[0])), "hi": float(np.quantile(g["r"], q[1])), "n": len(g)}
    return out


def apply_interval(pred: pd.Series, qs: dict) -> pd.DataFrame:
    s = season_of(pred.index.month.to_series())
    lo = np.array([qs[x]["lo"] for x in s])
    hi = np.array([qs[x]["hi"] for x in s])
    lp = np.log1p(pred.to_numpy(float))
    return pd.DataFrame({"lo": np.maximum(np.expm1(lp + lo), 0), "hi": np.expm1(lp + hi)}, index=pred.index)


def season_stats(total: pd.Series, months: tuple[int, int], *, early=(2003, 2011), late=(2012, 2021),
                 span=(2003, 2025)) -> dict:
    """Season totals per year, late/early mean ratio and Theil-Sen slope of log(total+1)."""
    s = total[total.index.month.isin(months)]
    yearly = s.groupby(s.index.year).sum(min_count=len(months))
    yearly = yearly[(yearly.index >= span[0]) & (yearly.index <= span[1])]
    e = yearly[(yearly.index >= early[0]) & (yearly.index <= early[1])].mean()
    l = yearly[(yearly.index >= late[0]) & (yearly.index <= late[1])].mean()
    ok = yearly.dropna()
    slope = theilslopes(np.log1p(ok.to_numpy(float)), ok.index.to_numpy(float))[0] if len(ok) > 2 else None
    return {"yearly": {int(k): float(v) for k, v in yearly.items()}, "early_mean": float(e), "late_mean": float(l),
            "ratio_late_early": float(l / e) if e else None,
            "theil_sen_log_slope_per_year": float(slope) if slope is not None else None}
