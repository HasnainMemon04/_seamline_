# Protocol P02: a camera model, a clock test and a burned-area cross-check, frozen before results

Written 3 Nov 2026 by Claude (build session) after Hasnain chose options D1–D3 in docs/DIFFERENTIATION_PLAN.md, **before any P02 model was fitted or any P02 statistic computed.** P01 and its results stay unchanged. Any later change to this file is logged at the bottom with its reason; results obtained before a change are kept.

## 0. What had already been seen (so nothing below can be called blind where it is not)

- All P01 results (E00–E03), including the province-level drift diagnostic for 2018–2025: a 2014–17 Aqua→S-NPP ratio over-predicts S-NPP in those years.
- The 3 Nov probe (Punjab, day passes, quality-filtered type 0): median local solar time of detections per platform and year (all years); S-NPP October–November median FRP and counts, 2014–2025; for October–November 2014–17, the share of S-NPP 0.01° cells with an Aqua detection within about 1.5 km on the same day, by cell FRP (3% under 2 MW to 39% over 50 MW); S-NPP/Aqua count and FRP ratios, 2014–17.
- Second review (docs/REVIEW_B05_2026-11-02.md): the S-NPP/Aqua ratio is higher in low-burning years.
- External reports: burning in Indian Punjab moved to late afternoon after 2021 (iFOREST 2025; Jethva 2026). Aqua has drifted later since December 2021 and Terra earlier.

Never computed before this protocol: any prediction of Aqua or Terra counts from S-NPP fire cells; any held-out score for such a prediction; any Sindh or Khyber Pakhtunkhwa result for 2018–2021; any burned-area statistic.

## 1. D1: the camera model (forward observation operator)

**Idea.** Instead of one multiplier, model the chance that MODIS reports a fire that VIIRS saw, as a function of the fire's power. If that physics is right, it should predict how many detections Aqua reported from what S-NPP saw, in years and provinces it was never fitted on.

**Fire cells.** For each UTC date, S-NPP day-pass detections (stream standard, quality_pass, type0) are grouped into 0.01° × 0.01° cells (about 1 km). Cell FRP F = sum of pixel FRP in the cell; cell position = mean latitude and longitude.

**Hit.** A cell is "hit" when an Aqua day-pass detection (same filters) lies within 1.5 km of the cell position on the same UTC date (distance on a plane with longitude scaled by cos 31°).

**Model.** Effective detection probability p(F) = logistic(b0 + b1·ln F), fitted by maximum likelihood (IRLS) on all Punjab cells from 2014–2017 (the P01 selection years), all months. "Effective" means it combines sensor sensitivity, swath coverage, clouds, the roughly 12 minutes between passes, and geolocation.

**Forward prediction.** For any region and month: Â = α · Σ p(F) over that month's S-NPP cells, where α = (Aqua day detections) / Σ p(F) over the fit set, so that in-sample totals match.

**Baseline (one multiplier, same data and same number of scale constants).** Â_base = S / k, where S is the month's S-NPP day-pass detection count and k = ΣS/ΣA over the fit set.

**Held-out tests (never used for fitting).**
- T1: Punjab, 2012-02 to 2013-12 and 2018-01 to 2021-12.
- T2: Sindh, 2012-02 to 2021-12, with Punjab's p and α (transfer).
- T3: Khyber Pakhtunkhwa, 2012-02 to 2021-12, with Punjab's p and α (transfer).
- Months are scored only when Aqua and S-NPP both have status "complete" (P01 change-log item 2). 2022–2025 are left out of D1 because Aqua's clock drift is a known observing change; they are D2's subject.

**Metrics.** WAPE = Σ|Â − A| / ΣA over the months of each test set; bias = ΣÂ/ΣA − 1; and the standard deviation across years of yearly bias (stability).

**Decision rule (declared now).** The camera model is "supported" if it has lower WAPE than the baseline in T1 **and** in at least one of T2 or T3, **and** a smaller yearly-bias standard deviation in T1. Otherwise the result is reported as negative, and FireBridge keeps the P01 conversion with the camera model shown only as an explanation.

**Not claimed.** p(F) is not a true detection probability of MODIS for a fire of power F; it is an effective, empirical relation. S-NPP is a reference, not ground truth.

## 2. D2: the clock test

**Question.** Aqua's pass over Punjab moved from about 13:15 (2003–2021) to 14:26 (2025) local solar time; Terra's moved from about 10:50 to 09:50. S-NPP stayed at about 13:05. Does Pakistani Punjab's burning show the late-afternoon shift reported in Indian Punjab?

**Method.** Fit the D1 model separately for Aqua and for Terra (Terra hits are Terra day-pass detections within 1.5 km of an S-NPP cell on the same UTC date), both on Punjab 2014–2017. For every year 2012–2025 and two seasons (October–November; all other months), compute Q = A_actual / Â (the ratio of what each MODIS satellite reported to what the camera model predicts from S-NPP).

**Statistics.** Δ_sat = mean(Q, 2023–2025) / mean(Q, 2018–2021) − 1, for Aqua and for Terra, per season. Contrast C = Δ_Aqua − Δ_Terra. 90% intervals by bootstrap over days within each period (1,000 resamples, seed 20261103).

**Reading, declared now.**
- If burning moved later in the day: Aqua (drifting later) should report relatively more and Terra (drifting earlier) relatively less, so C > 0, larger in October–November than in other months.
- If a MODIS processing change (files moved to version 61.03 in 2023) drove the shift, Aqua and Terra should move in the same direction, so C ≈ 0.
- "Consistent with a later burning time in Pakistani Punjab" is said only if C's 90% interval in October–November lies above 0 **and** C in October–November exceeds C in other months. Even then it is evidence, not proof: Terra and Aqua differ in other ways.

## 3. D3: burned-area cross-check

**Data.** MODIS burned area MCD64A1 Collection 6.1 (500 m, monthly), tiles h23v05, h23v06, h24v05 and h24v06, October and November, 2003–2025, from NASA LAADS with Hasnain's Earthdata token. Because only about 2.3 GB of disk is free (2 GB must stay free), each file is downloaded, hashed, recorded in the manifest, cropped to Punjab's bounding area (lossless, `Burn Date` layer only) and then deleted.

**Quantity.** Burned area in Punjab (geoBoundaries polygon) with burn date in October–November, in km², per year. Pixels marked unmapped (−1) are counted and reported separately per year.

**Comparison (declared now).** The same section 8 statistics as P01: 2012–2021 versus 2003–2011 mean ratio, and Theil–Sen slope of ln(area) over 2003–2025. They are compared with the frozen E02/E03 values for the naive stitch (16.79×), Aqua only (1.99×) and harmonised H across M1–M4 (ratio intervals spanning 1.50 to 2.07).

**Reading.** Burned area does not depend on the time of day of burning, because a scar stays for days. It misses small fields and uses MODIS reflectance (and active fires as seeds), so it is a cross-check, not ground truth. "Agrees with the harmonised record" if the burned-area ratio lies within 1.50–2.07; "agrees with the naive record" if it is above 8; otherwise it is reported as it is.

## 4. Order and records

1. Fit D1 for Aqua and Terra on 2014–2017; save parameters (experiments/P02_F00_fit/).
2. Score T1–T3 once (experiments/P02_F01_camera/), then D2 (experiments/P02_F02_clock/).
3. D3 when the token and disk space allow (experiments/P02_F03_burned_area/).
4. Results record `code_state` (commit, uncommitted-changes flag, c08 source hash).

## Change log
- 3 Nov 2026, Claude, before any P02 computation: D2 uses the same rule as D1 for which months count, namely months in which both satellites of the pair (Aqua and S-NPP, or Terra and S-NPP) have status "complete". The bootstrap resamples days within each year, so each yearly Q is recomputed and then averaged over the years of a period, as section 2 defines.
- 3 Nov 2026, Claude, before any D3 statistic: (1) **Source.** MCD64A1 files come from NASA LP DAAC (the product's official archive, data.lpdaac.earthdatacloud.nasa.gov, found through the public CMR search), not LAADS. LAADS sent token downloads to an interactive licence and sign-in page that a script cannot complete. Same product, same Collection 6.1, same files. (2) **Tiles.** h23v06 is dropped: its Punjab mask is empty (0 pixels; it ends west of 69.3°E). h23v05, h24v05 and h24v06 cover 202,123 km² of Punjab, within about 2% of the official area. Results are unaffected, and 46 needless downloads are avoided.
