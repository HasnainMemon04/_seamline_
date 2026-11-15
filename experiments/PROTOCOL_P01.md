# Protocol P01: harmonisation experiments, frozen before fitting

Written 2 Nov 2026, about 17:20 PKT, by Claude, **before any Pakistan count series, ratio or model result was computed.** What had been seen beforehand: file-level metadata in the acquisition log (rows per national annual file, version strings, first and last dates). Those national row totals were visible; no regional, monthly or cross-sensor figure was. Any later change to this file is logged at the bottom with its reason; results obtained before a change are kept.

## 1. Quantity (estimand)

**H(r, m)** = harmonised monthly detected burning activity for region r and month m, in **S-NPP-VIIRS-equivalent detections**: the number of quality-filtered Suomi NPP VIIRS 375 m fire pixels (day and night passes, each calibrated separately, then summed) that S-NPP recorded, or is estimated to have recorded, in region r during month m (UTC dates).

- It counts fire-affected pixels on satellite passes. It is not a count of fires, burned area, emissions or smoke.
- Reference convention: S-NPP VIIRS 375 m, Collection 2, standard processing, nominal or high confidence, FIRMS type 0 where the type field exists.
- Why S-NPP: VIIRS is the continuing sensor family; S-NPP has the longest VIIRS archive (2012–2026) and overlaps both Aqua MODIS (2012–) and NOAA-20 (2018–). MODIS is ending, so a MODIS-based reference would not stay observable.

## 2. Sources per period

| Period | Source of H | Status label |
|---|---|---|
| 2003-01 to 2011-12, and 2012-01 (S-NPP starts 20 Jan) | Aqua MODIS (plus Terra in model M4) converted to S-NPP-equivalent | modelled |
| 2012-02 to 2025-12 | S-NPP standard-processing archive | observed (reference sensor) |
| 2026 onward | S-NPP NRT while it lasts; afterwards NOAA-20 converted to S-NPP-equivalent | observed / bridged; NRT labelled |
| before 2003 | Terra only | not supported in v0.2 |

NOAA-21 has no archive in the FIRMS country files; it is shown raw only until a calibration can be fitted.

## 3. Regions

- Primary: Punjab province, Pakistan (geoBoundaries gbOpen PAK ADM1, public domain, 2019 boundaries). Chosen because rice- and wheat-residue burning is a documented seasonal practice there and Pakistani users have a smog-season question. This is a reversible default.
- Geographic test: Sindh province (same protocol, never used for selection).
- App: any province or rectangle inside Pakistan; harmonisation is calibrated on that region's own overlap years (section 5), with a support check.

## 4. Filters and processing (fixed)

- MODIS confidence ≥ 30; VIIRS confidence n or h. FIRMS type 0 only when the type field exists.
- Exact duplicate rows (same platform, time, position, version) dropped; no clustering into "fires".
- Day and night separated by the FIRMS daynight flag; months by UTC date.
- Platforms never summed as if they were one sensor.

## 5. Splits (from metadata only)

MODIS version strings in the country archive: "6.2" for 2000–2017, "6.03" for 2018–2022, "61.03" for 2023–2025. The backcast target (2003–2011) is "6.2", so calibration uses the version-matched overlap **2012–2017**.

| Role | Years | Use |
|---|---|---|
| Selection | 2014, 2015, 2016, 2017 | leave-one-year-out cross-validation chooses the model |
| Final temporal test | 2012 (Feb–Dec), 2013 | touched once, after selection; mimics backcasting into the past |
| Version and orbit-drift diagnostic | 2018–2025 | the 2014–2017 model applied across the MODIS version changes; never used for selection |
| Geographic test | Sindh, same years | method transfer (Sindh's own calibration) and parameter transfer (Punjab's parameters) |
| Deployment fit | 2012-02 to 2017-12 | refit after testing; test scores always come from the 2014–2017 fit |

Forward bridge NOAA-20 to S-NPP: selection by leave-one-year-out over 2019–2023; final test 2024–2025; deployment fit 2018-04 to 2025-12.

## 6. Candidate models (each fitted separately for day and night, monthly region totals)

- **M0 naive stitch:** H = Aqua count (what concatenating raw records gives).
- **M1 single ratio:** H = k·A, k = ΣV/ΣA over training months.
- **M2 monthly ratio with shrinkage:** k_m = (ΣV_m + 30k)/(ΣA_m + 30), 30 pseudo-detections toward k.
- **M3 Poisson log-linear:** log E[V] = α + β·log(A+1) + γ_season, seasons Apr–May, Oct–Nov, other.
- **M4 two-satellite:** M3 plus β₂·log(T+1) for Terra.

## 7. Metrics (declared before results)

- **Primary (selection):** WAPE = Σ|pred − obs| / Σobs over held-out months, day+night summed.
- **Secondary (reported, used only to break a primary tie within 2%):** log-scale MAE |log(pred+1) − log(obs+1)|; bias Σpred/Σobs − 1; peak-month agreement per year; anomaly agreement (each month classed below/typical/above against the median of the other years' same month, predicted vs observed).
- **Uncertainty:** 80% prediction intervals from pooled leave-one-year-out log residuals by season; coverage reported on test years.
- A model is promoted over M1 only if it beats M1 on the primary metric in cross-validation. Otherwise M1 is used and the result is reported as negative.

## 8. Differentiator test (declared before results)

Question: does an apparent change in Punjab's burning survive harmonisation? For the Oct–Nov and Apr–May seasons, compare three records: (a) naive all-satellite stitch (all MODIS rows to 2011, all VIIRS rows from 2012); (b) Aqua only, all years; (c) harmonised H with intervals. Report the 2012–2021 versus 2003–2011 mean-season ratio and the 2003–2025 Theil–Sen trend on log scale for each. The claim "raw records exaggerate change" is made only if (a) and (c) differ beyond (c)'s interval.

## 9. Not validated by this protocol

Cross-sensor agreement is not fire-detection accuracy. No independent ground truth (burned area, field data) is used in v0.2. Clouds, smoke and missed passes are not observed in hotspot-only data.

## Change log
- **2026-11-02 ~17:55 PKT, Claude (clarifications, before any monthly, regional-per-sensor or ratio figure was computed).** What had been seen at this point: the ingest audit (all archive rows pass the data contract; no exact duplicates), national row totals per platform and type summed over all years, and province row totals summed over all platforms and years. No monthly series, regional per-sensor total, ratio or model output. These rules fill gaps P01 left open; none changes a model, metric, split or filter above.
  1. *Region membership.* A detection belongs to a province when its coordinates fall inside that province's geoBoundaries polygon (data/raw/boundaries, hash in the manifest). Points outside every polygon (0.85% of archive rows, along borders) belong to no province.
  2. *Provider-reported missing days.* The FIRMS missing-data table (research/metadata/provider_missing_dates.json) is applied per platform and month. A month is excluded from every metric when any platform used by any candidate (Aqua, Terra, S-NPP; for the bridge, NOAA-20 and S-NPP) has at least one standard-stream missing day in it, so all candidates are scored on the same months. The month stays in the displayed record with a flag.
  3. *Forward bridge candidates.* M0–M3 with the NOAA-20 count in place of the Aqua count, fitted day and night separately; same WAPE rule, M1 kept unless beaten.
  4. *Section 8 interval.* Season totals are Apr+May and Oct+Nov sums of H. For each statistic (2012–2021 vs 2003–2011 mean-season ratio; Theil–Sen slope of log(season total + 1) on year), the interval for (c) is the range obtained by setting every modelled month to its lower 80% bound and then to its upper bound (perfectly correlated errors, a conservative choice). Observed S-NPP months have no interval. "Raw records exaggerate change" is claimed only if (a)'s statistic lies outside that range.
  5. *Anomaly classes (secondary metric and app display use the same rule).* For a month's day+night total v and the median m of the same calendar month in the comparison years, compute r = (v + 1)/(m + 1): "above" if r > 1.5, "below" if r < 1/1.5, otherwise "typical". The +1 keeps empty months defined.
  6. *Selection arithmetic.* "Beats M1" means a strictly lower pooled cross-validation WAPE. Among M1 and the models that beat it, the lowest WAPE wins; a model whose WAPE is within 2% (relative) of the lowest counts as tied, and ties go to the lowest log-scale MAE. The selection is written to experiments/E01_selection/selection.json before any test-year score is computed.
- **2026-11-02 ~18:05 PKT, Claude (after E02; nothing above changed).** E01 selected M2 for the backcast and kept M1 for the bridge. E02 was run once: on 2012–13 M1 beat M2 (WAPE 0.175 vs 0.231). M2 stays selected; the result is reported as negative. E03 (declared after E02, selects nothing) re-ran section 8 under M1–M4. App-level rules added later (day-pass fallback for areas failing the night support check; weak-support warning above WAPE 0.5) are display and coverage rules in c08/analysis.py, not part of these experiments.
