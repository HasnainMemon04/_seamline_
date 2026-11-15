"""Post-hoc checks of Protocol P02, added 3 Nov 2026 after the checker's report.

python -m c08.p02_posthoc     # writes reports/c08/p02_posthoc.json

These checks were chosen after the P02 results and docs/REVIEW_P02_2026-11-03.md
had been seen, so they only describe how solid the P02 numbers are. They change
no frozen verdict.
- D2: Q per year (rebuilt, and checked against F02), an exact permutation test
  over years, leave-one-year-out, October alone, and median detection times.
- D3: the burned-area ratio across years, without 2021, with unmapped pixels at
  their extremes, and the slope with ln(area) and with ln(area + 1).
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from itertools import combinations

import numpy as np
import pandas as pd
from scipy.stats import theilslopes

from . import burned_area as ba, config, ingest, observe, p01, series

OUT = config.ROOT / "reports" / "c08" / "p02_posthoc.json"
PROTOCOL = "experiments/PROTOCOL_P02.md"
SEED, N_BOOT = 20261103, 10000
OCTNOV, OTHER = (10, 11), tuple(m for m in range(1, 13) if m not in (10, 11))
BEFORE, AFTER = observe.CLOCK_BEFORE, observe.CLOCK_AFTER


def clock_days(d: pd.DataFrame, prm: dict) -> dict[str, pd.DataFrame]:
    """Daily reported and predicted detections in Punjab, built exactly as observe.clock builds them."""
    cells = observe.fire_cells(d, "Punjab")
    out = {}
    for sat in ("Aqua", "Terra"):
        months = observe.complete_months(d, "Punjab", (sat, "SNPP"))
        months = months[(months.year >= 2012) & (months.year <= 2025)]
        c = cells[cells.month.isin(months)]
        pred = c.assign(p=observe.p_detect(c.frp.to_numpy(), (prm[sat]["b0"], prm[sat]["b1"]))).groupby("date_utc").p.sum()
        mod = observe.day_detections(d, sat)
        mod = mod[(mod.province == "Punjab") & mod.date_utc.dt.to_period("M").dt.start_time.isin(months)]
        days = pd.DataFrame({"pred": pred * prm[sat]["alpha"], "act": mod.groupby("date_utc").size()}).fillna(0.0)
        days["year"], days["month"] = days.index.year, days.index.month
        out[sat] = days
    return out


def yearly_q(days: pd.DataFrame, months: tuple[int, ...]) -> pd.Series:
    g = days[days.month.isin(months)].groupby("year")[["act", "pred"]].sum()
    g = g[g.pred > 0]
    return g.act / g.pred


def change(q: pd.Series, before=BEFORE, after=AFTER) -> float | None:
    b, a = [q[y] for y in before if y in q.index], [q[y] for y in after if y in q.index]
    return float(np.mean(a) / np.mean(b) - 1) if a and b else None


def permutation(q: pd.Series, before=BEFORE, after=AFTER) -> dict:
    """Exact test with whole years as the unit: every way to call len(after) of the pooled years 'after'."""
    b = np.array([q[y] for y in before if y in q.index])
    a = np.array([q[y] for y in after if y in q.index])
    pool, obs, tol = np.r_[b, a], a.mean() - b.mean(), 1e-12
    diffs = np.array([pool[list(i)].mean() - np.delete(pool, list(i)).mean()
                      for i in combinations(range(len(pool)), len(a))])
    return {"years_before": len(b), "years_after": len(a), "splits": int(len(diffs)),
            "difference_of_means": float(obs), "p_two_sided": float(np.mean(np.abs(diffs) >= abs(obs) - tol)),
            "p_as_low": float(np.mean(diffs <= obs + tol)), "p_as_high": float(np.mean(diffs >= obs - tol))}


def _hhmm(hours: float) -> str:
    m = int(round(hours * 60))
    return f"{m // 60}:{m % 60:02d}"


def pass_times(d: pd.DataFrame) -> dict:
    """Median local solar time of Punjab day-pass detections (mixes the orbit with when fires burn)."""
    q = series.select(d, region="Punjab")
    q = q[(q.daynight == "D") & (q.year >= 2014)]
    lst = (q.time_utc.dt.hour + q.time_utc.dt.minute / 60 + q.longitude / 15) % 24
    season = pd.Series(np.where(q.date_utc.dt.month.isin(OCTNOV), "OctNov", "other"), index=q.index)
    out = {}
    for key, grouped in (("all_months", lst.groupby([q.platform, q.year], observed=True)),
                         ("by_season", lst.groupby([q.platform, season, q.year], observed=True))):
        res = {}
        for k, v in grouped:
            node = res
            for part in [str(x) for x in k[:-1]]:
                node = node.setdefault(part, {})
            node[str(int(k[-1]))] = {"median": _hhmm(v.median()), "n": int(len(v))}
        out[key] = res
    # Month by month for the drifting satellites: shows how much the orbit moves within one year.
    late = q.year >= 2021
    mo = lst[late].groupby([q.platform[late], q.year[late], q.date_utc[late].dt.month], observed=True).median()
    out["monthly_2021_2025"] = {p: {str(y): {str(m): _hhmm(mo[(p, y, m)]) for m in range(1, 13) if (p, y, m) in mo.index}
                                    for y in range(2021, 2026)} for p in ("Terra", "Aqua")}
    return out


def snpp_octnov(d: pd.DataFrame) -> dict:
    """S-NPP Oct-Nov day-pass detections in Punjab per year, and the 2022-25 against 2018-21 change three ways."""
    n = observe.monthly_counts(d, "Punjab", "SNPP")
    ok = observe.complete_months(d, "Punjab", ("SNPP",))
    rows = {int(y): {"OctNov": int(n[(n.index.year == y) & n.index.month.isin(OCTNOV)].sum()),
                     "Oct": int(n[(n.index.year == y) & (n.index.month == 10)].sum()),
                     "incomplete_months": [str(m.date())[:7] for m in n.index
                                           if m.year == y and m.month in OCTNOV and m not in ok]}
            for y in range(2018, 2026)}
    later, earlier = (2022, 2023, 2024, 2025), (2018, 2019, 2020, 2021)

    def rel(key, years_late):
        return float(np.mean([rows[y][key] for y in years_late]) / np.mean([rows[y][key] for y in earlier]) - 1)
    return {"yearly": rows, "change_2022_25_vs_2018_21": {"all_detections": rel("OctNov", later),
                                                          "without_2024": rel("OctNov", (2022, 2023, 2025)),
                                                          "october_only": rel("Oct", later)}}


def clock_checks(d: pd.DataFrame) -> dict:
    prm = json.loads((observe.OUT["fit"] / "result.json").read_text(encoding="utf-8"))["params"]
    stored = json.loads((observe.OUT["clock"] / "result.json").read_text(encoding="utf-8"))["results"]["yearly_Q"]
    out = {}
    for sat, days in clock_days(d, prm).items():
        q, oct_, nov, other = (yearly_q(days, m) for m in (OCTNOV, (10,), (11,), OTHER))
        diff = max(abs(q[y] - stored["OctNov"][sat][str(y)]) for y in q.index)
        base = np.mean([q[y] for y in BEFORE])
        out[sat] = {
            "rebuilt_max_difference_from_F02": float(diff),  # float summation order only (about 1e-7)
            "rebuilt_matches_F02": bool(diff < 1e-6),
            "yearly_Q_OctNov": {int(y): round(float(v), 4) for y, v in q.items()},
            # Which autumn months each yearly value contains (a month drops out when either satellite is incomplete).
            "OctNov_months_used": {int(y): sorted(int(m) for m in g.month.unique())
                                   for y, g in days[days.month.isin(OCTNOV)].groupby("year")},
            "yearly_Q_October": {int(y): round(float(v), 4) for y, v in oct_.items()},
            "yearly_Q_November": {int(y): round(float(v), 4) for y, v in nov.items()},
            "each_later_year_vs_2018_21_mean": {y: round(float(q[y] / base - 1), 3) for y in (2022,) + AFTER},
            "step_2021_to_2022": round(float(q[2022] / q[2021] - 1), 3),
            "relative_to_2014_17_mean": {y: round(float(q[y] / np.mean([q[x] for x in observe.FIT_YEARS])), 3)
                                         for y in (2021, 2022, 2025)},
            "change_OctNov": change(q),
            "permutation_OctNov": permutation(q),
            "leave_one_year_out_OctNov": {int(y): change(q.drop(y)) for y in BEFORE + AFTER},
            "october_only": {"change": change(oct_), "permutation": permutation(oct_)},
            "november_only": {"change": change(nov), "years_after_used": [y for y in AFTER if y in nov.index]},
            "other_months": {"change": change(other), "permutation": permutation(other)}}
    return out


def terra_2022(d2: dict, times: dict) -> dict:
    """Terra's 2022 step, like for like: November only, because October 2022 is not scored.

    Terra was lowered out of the morning constellation in October 2022, and its MODIS
    science data stopped from about 12 October (NASA notices); FIRMS lists the days.
    """
    miss = series.provider_missing()
    m = miss[(miss.platform == "Terra") & (miss.stream == "standard") & (miss.date.dt.year == 2022)
             & miss.date.dt.month.isin(OCTNOV)]
    nov = d2["Terra"]["yearly_Q_November"]
    return {"firms_missing_days_OctNov_2022": sorted(m.date.dt.strftime("%Y-%m-%d").unique().tolist()),
            "november_Q_change_2021_to_2022": round(nov[2022] / nov[2021] - 1, 3),
            "november_median_time": {y: times["monthly_2021_2025"]["Terra"][y]["11"] for y in ("2021", "2022")},
            "other_months_Q_change_2023_25_vs_2018_21": d2["Terra"]["other_months"]["change"]}


def burned_months() -> pd.DataFrame:
    """Burned, unmapped and water km2 and Punjab's area per year and month, from the stored crops."""
    m, rows = ba._load_manifest(), []
    masks = {t: ba.punjab_window(t)["mask"] for t in ba.TILES}
    for year in ba.YEARS:
        for month in ba.MONTHS:
            doy = date(year, month, 1).timetuple().tm_yday
            r = {"year": year, "month": month, "burned": 0, "unmapped": 0, "water": 0, "inside": 0}
            for tile in ba.TILES:
                b = np.load(config.ROOT / m["files"][f"MCD64A1/{year}/{doy:03d}/{tile}"]["crop"])["burn"]
                inside = masks[tile]
                for key, sel in (("burned", b >= 1), ("unmapped", b == -1), ("water", b == -2), ("inside", True)):
                    r[key] += int((sel & inside).sum())
            rows.append(r)
    t = pd.DataFrame(rows)
    cols = ["burned", "unmapped", "water", "inside"]
    t[cols] = t[cols] * ba.PIXEL_KM2
    return t


def burned_checks() -> dict:
    t = burned_months()
    rate = t.burned / (t.inside - t.water - t.unmapped)
    t["filled"] = t.burned + t.unmapped * rate
    y = t.groupby("year")[["burned", "unmapped", "filled"]].sum()
    stored = json.loads((ba.OUT / "result.json").read_text(encoding="utf-8"))["yearly"]
    diff = max(abs(round(float(y.burned[k]), 1) - stored[str(k)]["burned_km2"]) for k in y.index)
    early, late = y.loc[2003:2011], y.loc[2012:2021]
    rng = np.random.default_rng(SEED)
    e, l = early.burned.to_numpy(), late.burned.to_numpy()
    boots = np.array([rng.choice(l, len(l)).mean() / rng.choice(e, len(e)).mean() for _ in range(N_BOOT)])
    yrs, b = y.index.to_numpy(float), y.burned.to_numpy()
    return {
        "rebuilt_matches_F03": bool(diff < 0.051),
        "ratio_as_declared": float(l.mean() / e.mean()),
        "ratio_without_2021": float(late.burned.drop(2021).mean() / e.mean()),
        "ratio_of_medians": float(np.median(l) / np.median(e)),
        "ratio_of_geometric_means": float(np.exp(np.log(l).mean() - np.log(e).mean())),
        "year_bootstrap": {"seed": SEED, "resamples": N_BOOT, "median": float(np.median(boots)),
                           "interval_90": [float(np.quantile(boots, .05)), float(np.quantile(boots, .95))]},
        "unmapped_km2_mean": {"2003_11": float(early.unmapped.mean()), "2012_21": float(late.unmapped.mean()),
                              "2025": float(y.unmapped[2025])},
        "ratio_unmapped_filled_at_mapped_rate": float(late.filled.mean() / early.filled.mean()),
        "ratio_bounds_all_unmapped_burned_in_one_period": [
            float(l.mean() / (e.mean() + early.unmapped.mean())), float((l.mean() + late.unmapped.mean()) / e.mean())],
        "slope_ln_area_plus_1": float(theilslopes(np.log1p(b), yrs)[0]),
        "slope_ln_area": float(theilslopes(np.log(b), yrs)[0]),
        "burned_2022_25_vs_2018_21": float(y.burned.loc[2022:2025].mean() / y.burned.loc[2018:2021].mean() - 1)}


def run() -> dict:
    d, _ = p01.load_inputs()
    meta = {"what": "Post-hoc checks of P02 (after CHECK REPORT P02); descriptive, no frozen verdict changed",
            "run_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "code_state": ingest.code_state()} | ingest.protocol_state(PROTOCOL)
    d2, times = clock_checks(d), pass_times(d)
    res = meta | {"D2": d2, "terra_2022": terra_2022(d2, times), "pass_times": times, "snpp_octnov": snpp_octnov(d),
                  "D3": burned_checks()}
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    return res


def main(argv: list[str]) -> int:
    res = run()
    print(json.dumps({k: res[k] for k in ("terra_2022", "D3", "snpp_octnov")}, indent=1)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
