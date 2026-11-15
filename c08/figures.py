"""Sanity and result figures for Punjab (reports/c08/figures/*.png).

Colours follow the platform everywhere (validated categorical slots; low-contrast
slots are direct-labelled). Run after p01 e02:  python -m c08.figures
"""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import config, harmonize as hz, p01

FIG = config.REPORTS / "figures"
COLOR = {"Aqua": "#2a78d6", "SNPP": "#eb6834", "Terra": "#1baf7a", "NOAA20": "#eda100", "NOAA21": "#e87ba4"}
LABEL = {"Aqua": "Aqua MODIS", "SNPP": "S-NPP VIIRS", "Terra": "Terra MODIS", "NOAA20": "NOAA-20 VIIRS"}
INK, INK2, MUTED, GRID, BAND = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#d6d5cf"
NAIVE = "#e34948"


def _style(ax):
    ax.set_facecolor("#fcfcfb")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#c3c2b7")
    ax.tick_params(colors=INK2, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def _save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / name, dpi=150, facecolor="#fcfcfb")
    plt.close(fig)


def platform_series(w: pd.DataFrame):
    plats = ("Terra", "Aqua", "SNPP", "NOAA20")
    fig, axes = plt.subplots(len(plats), 1, figsize=(11, 7.4), sharex=True, sharey=True)
    for ax, p in zip(axes, plats):
        _style(ax)
        v = (w[f"{p}_D"] + w[f"{p}_N"]).where(w[f"{p}_status"] != "outside_record")
        ax.plot(v.index, v.clip(lower=0.8), color=COLOR[p], linewidth=1.3)
        rec = v.dropna().index
        ax.axvspan(pd.Timestamp("2000-11-01"), rec[0], color="#f0efec", zorder=0)
        ax.set_title(f"{LABEL[p]}   (record from {rec[0]:%b %Y})", loc="left", color=INK, fontsize=9.5, pad=3)
        ax.set_yscale("log")
        ax.set_ylim(1, 3e4)
    axes[-1].set_xlim(pd.Timestamp("2000-11-01"), pd.Timestamp("2026-01-01"))
    fig.supylabel("Detections per month (log scale)", color=INK2, fontsize=10)
    fig.suptitle("Punjab: monthly detected burning activity by satellite, raw (quality-filtered, type 0)",
                 x=0.01, ha="left", color=INK, fontsize=11)
    fig.text(0.01, 0.01, "Each count is fire pixels on satellite passes, not fires. Shaded = before that satellite's record "
             "(missing, not zero). Source: NASA FIRMS country archive.", color=MUTED, fontsize=8)
    fig.tight_layout(rect=(0.01, 0.03, 1, 0.96))
    _save(fig, "punjab_platform_series.png")


def _noaa20_mark(ax, size: float, label: bool = True):
    """Dashed line where the naive stitch starts adding NOAA-20 (archive from April 2018)."""
    from matplotlib import patheffects
    ax.axvline(2017.5, color=NAIVE, linewidth=1, linestyle=(0, (4, 3)), zorder=1)
    if not label:
        return
    # Bottom of the panel: the naive line runs near the top after 2018, so a label there would cross it.
    ax.text(2017.65, 0.04, "NOAA-20 added\nto the naive stitch", transform=ax.get_xaxis_transform(), color=NAIVE,
            fontsize=size, va="bottom", zorder=5,
            path_effects=[patheffects.withStroke(linewidth=3, foreground="#f0efec")])


def differentiator(rec: pd.DataFrame, model: str):
    modis_all = rec[["Terra_D", "Terra_N", "Aqua_D", "Aqua_N"]].sum(axis=1, min_count=1)
    viirs_all = rec[["SNPP_D", "SNPP_N", "NOAA20_D", "NOAA20_N"]].sum(axis=1, min_count=1)
    naive = pd.Series(np.where(rec.index < pd.Timestamp("2012-01"), modis_all, viirs_all), index=rec.index)
    aqua = rec["Aqua_D"] + rec["Aqua_N"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
    for ax, (name, months) in zip(axes, (("October–November (rice-residue season)", (10, 11)),
                                         ("April–May (wheat-residue season)", (4, 5)))):
        _style(ax)
        yr = lambda s: s[s.index.month.isin(months)].groupby(s[s.index.month.isin(months)].index.year).sum()
        h, lo, hi, nv, aq = yr(rec["H"]), yr(rec["H_lo"]), yr(rec["H_hi"]), yr(naive), yr(aqua)
        ax.axvspan(2011.5, 2025.5, color="#f0efec", zorder=0)
        _noaa20_mark(ax, 8.5, label=ax is axes[0])  # one label is enough; the second panel's Aqua line runs low
        ax.fill_between(h.index, lo, hi, color=BAND, linewidth=0, label="Harmonised rough range (nominal 80%; modelled years)")
        ax.plot(nv.index, nv, color=NAIVE, linewidth=2, marker="o", markersize=4, label="Naive stitch: all MODIS, then all VIIRS")
        ax.plot(aq.index, aq, color=COLOR["Aqua"], linewidth=2, marker="o", markersize=4, label="Aqua MODIS only (one sensor)")
        ax.plot(h.index, h, color=INK, linewidth=2, marker="o", markersize=4, label=f"Harmonised, S-NPP-equivalent ({model})")
        ax.set_yscale("log")
        ax.set_title(name, loc="left", color=INK, fontsize=10.5)
        ax.text(2011.8, 0.03, "VIIRS era (2012–)", transform=ax.get_xaxis_transform(), color=INK2, fontsize=8.5)
        ax.set_xticks(range(2003, 2026, 2))
    axes[0].set_ylabel("Season total detections (log scale)", color=INK2)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, fontsize=8.5, ncol=4, loc="lower left", bbox_to_anchor=(0.01, 0.045))
    fig.suptitle(f"Punjab: the naive record shows a 17× jump in Oct–Nov burning activity; on one scale it is about 1.7–1.9× "
                 f"(all four frozen models; {model} shown)", x=0.01, ha="left", color=INK, fontsize=11.5)
    fig.text(0.01, 0.01, "Ratio = mean 2012–2021 ÷ mean 2003–2011, as declared in Protocol P01 before results. "
             "Harmonised years before 2012 are modelled from Aqua; from 2012 they are observed S-NPP.",
             color=MUTED, fontsize=8)
    fig.tight_layout(rect=(0, 0.09, 1, 0.94))
    _save(fig, "punjab_differentiator.png")


def ratio_drift(w: pd.DataFrame):
    part = w[(w.index.year >= 2012) & (w.index.year <= 2025)]
    seas = hz.season_of(part.index.month.to_series())
    fig, ax = plt.subplots(figsize=(11, 4.4))
    _style(ax)
    for s, col, lab in (("OctNov", "#6250d6", "Oct–Nov"), ("AprMay", "#008300", "Apr–May"), ("other", "#e87ba4", "Other months")):
        g = part[seas == s]
        r = g.groupby(g.index.year).apply(lambda x: x["SNPP_D"].sum() / x["Aqua_D"].sum())
        ax.plot(r.index, r, color=col, linewidth=2, marker="o", markersize=4, label=lab)
        ax.annotate(lab, (r.index[-1], r.iloc[-1]), xytext=(6, 0), textcoords="offset points", color=INK2, fontsize=8.5, va="center")
    for x0, x1, lab in ((2011.5, 2017.5, "MODIS file version 6.2"), (2017.5, 2022.5, "6.03"), (2022.5, 2025.5, "61.03")):
        ax.axvspan(x0, x1, color="#f0efec" if lab != "6.03" else "#fcfcfb", zorder=0)
        ax.text(x0 + 0.1, 0.98, lab, transform=ax.get_xaxis_transform(), color=MUTED, fontsize=8, va="top")
    ax.axvspan(2013.5, 2017.5, ymin=0, ymax=0.03, color=INK2)
    ax.set_xlim(2011.5, 2026.4)
    ax.set_ylim(top=18)
    ax.set_ylabel("S-NPP ÷ Aqua, day passes", color=INK2)
    ax.set_title("Punjab: how many S-NPP detections per Aqua detection, by season and year (dark bar = selection years)",
                 loc="left", color=INK, fontsize=11)
    fig.text(0.01, 0.01, "A constant multiplier would be a flat line. Ratios shift by season and over time.", color=MUTED, fontsize=8)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    _save(fig, "punjab_ratio_drift.png")


def pass_times(d: pd.DataFrame):
    from . import series
    q = series.select(d, region="Punjab")
    fig, axes = plt.subplots(1, 4, figsize=(12, 3.2), sharey=True)
    for ax, p in zip(axes, ("Terra", "Aqua", "SNPP", "NOAA20")):
        _style(ax)
        g = q[q.platform == p]
        h = g["time_utc"].dt.hour + g["time_utc"].dt.minute / 60
        ax.hist(h, bins=np.arange(0, 24.25, 0.25), color=COLOR[p], weights=np.full(len(h), 100 / len(h)))
        ax.set_title(LABEL[p], loc="left", color=INK, fontsize=10)
        ax.set_xticks(range(0, 25, 6))
        ax.set_xlabel("Hour (UTC)", color=INK2, fontsize=9)
    axes[0].set_ylabel("% of detections", color=INK2)
    fig.suptitle("Punjab: detection times. No pass crosses 00:00 UTC, so UTC-day months do not split a pass "
                 "(Pakistan time = UTC+5)", x=0.01, ha="left", color=INK, fontsize=10.5)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    _save(fig, "punjab_pass_times.png")


def slide_figures(rec: pd.DataFrame, w: pd.DataFrame, model: str):
    """Large-type single-panel versions for slides (same data as the report figures)."""
    plt.rcParams.update({"font.size": 14})
    oct_nov = lambda s: s[s.index.month.isin((10, 11))].groupby(s[s.index.month.isin((10, 11))].index.year).sum()
    modis_all = rec[["Terra_D", "Terra_N", "Aqua_D", "Aqua_N"]].sum(axis=1, min_count=1)
    viirs_all = rec[["SNPP_D", "SNPP_N", "NOAA20_D", "NOAA20_N"]].sum(axis=1, min_count=1)
    nv = oct_nov(pd.Series(np.where(rec.index < pd.Timestamp("2012-01"), modis_all, viirs_all), index=rec.index))
    for name, show_all in (("slide_naive_octnov.png", False), ("slide_compare_octnov.png", True)):
        fig, ax = plt.subplots(figsize=(7.4, 4.4))
        _style(ax)
        ax.tick_params(labelsize=12)
        ax.axvspan(2011.5, 2025.5, color="#f0efec", zorder=0)
        ax.text(2011.8, 0.04, "VIIRS era", transform=ax.get_xaxis_transform(), color=INK2, fontsize=12)
        _noaa20_mark(ax, 11)
        if show_all:
            h, lo, hi = oct_nov(rec["H"]), oct_nov(rec["H_lo"]), oct_nov(rec["H_hi"])
            ax.fill_between(h.index, lo, hi, color=BAND, linewidth=0)
            ax.plot(oct_nov(rec["Aqua_D"] + rec["Aqua_N"]), color=COLOR["Aqua"], linewidth=2.5, marker="o", markersize=5)
            ax.plot(h, color=INK, linewidth=2.5, marker="o", markersize=5)
        ax.plot(nv, color=NAIVE, linewidth=2.5, marker="o", markersize=5)
        ax.set_yscale("log")
        ax.set_ylabel("Oct–Nov detections (log scale)", color=INK2, fontsize=13)
        ax.set_xticks(range(2003, 2026, 4))
        last = nv.index[-1]
        ax.annotate("Naive join", (last, nv.iloc[-1]), xytext=(6, 0), textcoords="offset points", color=NAIVE, fontsize=13, va="center")
        if show_all:
            ax.annotate("One scale", (last, h.iloc[-1]), xytext=(6, 0), textcoords="offset points", color=INK, fontsize=13, va="center")
            aq = oct_nov(rec["Aqua_D"] + rec["Aqua_N"])
            ax.annotate("Aqua only", (last, aq.iloc[-1]), xytext=(6, 0), textcoords="offset points", color=COLOR["Aqua"], fontsize=13, va="center")
        ax.set_xlim(2002.5, 2029)
        fig.tight_layout()
        fig.savefig(FIG / name, dpi=200, facecolor="#fcfcfb")
        plt.close(fig)
    # Drift: day-pass S-NPP per Aqua detection, by season.
    part = w[(w.index.year >= 2012) & (w.index.year <= 2025)]
    seas = hz.season_of(part.index.month.to_series())
    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    _style(ax)
    ax.tick_params(labelsize=12)
    for s, col, lab in (("OctNov", "#6250d6", "Oct–Nov"), ("AprMay", "#008300", "Apr–May"), ("other", "#e87ba4", "Other")):
        g = part[seas == s]
        r = g.groupby(g.index.year).apply(lambda x: x["SNPP_D"].sum() / x["Aqua_D"].sum())
        ax.plot(r.index, r, color=col, linewidth=2.5, marker="o", markersize=5)
        ax.annotate(lab, (r.index[-1], r.iloc[-1]), xytext=(6, 0), textcoords="offset points", color=col, fontsize=13, va="center")
    ax.set_xlim(2011.5, 2028.3)
    ax.set_ylabel("S-NPP ÷ Aqua (day passes)", color=INK2, fontsize=13)
    fig.tight_layout()
    fig.savefig(FIG / "slide_ratio_drift.png", dpi=200, facecolor="#fcfcfb")
    plt.close(fig)
    plt.rcParams.update({"font.size": 10})


def main():
    d, _ = p01.load_inputs()
    w = p01.region_table(d, "Punjab")
    sel = json.loads((p01.OUT["e01"] / "selection.json").read_text(encoding="utf-8"))
    bk = sel["backcast"]["selected"]
    rec = p01.harmonised_record(w, bk, sel["backcast"]["interval_log_quantiles"])
    platform_series(w)
    differentiator(rec, bk)
    ratio_drift(w)
    pass_times(d)
    slide_figures(rec, w, bk)
    print(sorted(p.name for p in FIG.glob("*.png")))


if __name__ == "__main__":
    main()
