# Protocol O01: experimental outlook for detected burning activity (retrospective)

Written 12 November 2026 by Claude (build session for the Seamline redesign), at Hasnain's instruction in the redesign
brief, Revision 1.3, section 4D. Written **before any model was fitted and before the held-out year was read**.
Runner: `python -m c08.outlook` (code: `c08/outlook.py`). Results: `experiments/O01_outlook/`.

This protocol is separate from P01, P02 and P04. It changes none of them and uses none of their test windows as a
tuning target. It replaces, for this one labelled feature only, the earlier project rule "no forecasts": see
DECISIONS.md, 12 Nov 2026. Every other rule stays (detections are not fires; satellites are never added; missing is
not zero; no risk levels, alerts or warnings).

## 1. Question

Can the number of detections that one satellite will record in one area over the next seven days be predicted better
than simple seasonal rules, well enough to say "increase" or "decrease" against the seven days just ended?

This is a question about **future satellite detections**, an aggregate count. It is not a forecast of where burning
will start, of unique fires, of burned area, of emissions, of danger, or of any need for action.

## 2. Target, fixed before fitting

- **Area:** Punjab (geoBoundaries gbOpen PAK ADM1, 2019), the only area tested. No other area gets an outlook.
- **Satellite:** NOAA-20 VIIRS 375 m alone (the platform that continues after S-NPP's end on 2 Nov 2026).
  No conversion to another scale; no other satellite is added.
- **Data:** FIRMS country archive, standard processing, 1 April 2018 to 31 December 2025, as held in
  `data/processed/pak_detections.parquet` (SHA-256 in `reports/c08/ingest_report.json`). Quality rule: nominal or high
  confidence. Type 0 only. Day and night passes.
- **Daily value** `y(d)`: retained detections on UTC day `d`. A day is **complete** when NOAA-20 is inside its record,
  the day is not on FIRMS's missing-days list for NOAA-20 (standard stream), and NOAA-20 has at least one row anywhere
  in Pakistan on its day pass and on its night pass that day (every row, before the quality rule). A day that is not
  complete has **no value**; it is never zero.
- **Origin** `t`: the last complete input day. Origins lie on a fixed weekly grid: 28 April 2018 and every 7th day
  after it, so target windows never overlap.
- **Target** `Y_next(t)`: the sum of `y` over days `t+1 … t+7`. All seven days must be complete.
- **Comparison** `Y_prev(t)`: the sum of `y` over days `t−6 … t`. All seven must be complete.
- **Lead time:** zero days between the last input day and the first target day; the horizon is seven days. No other
  horizon is tested.
- **Scale used for errors:** `z = ln(Y_next + 7)`. The offset 7 (one detection a day) keeps ratios defined when a week
  has no detections.
- **Observed change:** `R = (Y_next + 7) / (Y_prev + 7)`. **Increase** if `R ≥ 1.25`, **decrease** if `R ≤ 0.80`,
  otherwise **no clear change**. This ±25% band is the meaningful-change threshold.
- An origin is **eligible** when the target and the comparison are complete, at least 5 of the 7 days `t−13 … t−7` are
  complete, and at least 20 of the 28 days `t−27 … t` are complete. Ineligible origins are counted and left out.

## 3. Inputs a model may use (all known on day `t`)

1. `ln(Y_prev + 7)`.
2. `ln(W2 + 7)`, where `W2` is 7 × the mean of the complete days in `t−13 … t−7`.
3. `ln(M28 + 7)`, where `M28` is 7 × the mean of the complete days in `t−27 … t`.
4. `ln(y(t) + 1)`.
5. `ln(C_next + 7)` and `ln(C_prev + 7)`: the seasonal normal for the target week and for the week just ended, from the
   **training years only**. The daily normal is the mean of `y` on each day of the year over the training years
   (29 February is read as 28 February), smoothed with a centred 15-day circular mean.
6. `sin` and `cos` of `2π·doy/365.25` and of twice that angle, for the first target day.

No weather, no land cover, no other satellite, no value dated after `t`.

## 4. Benchmarks and candidates

- **B0, persistence:** `Y_next = Y_prev`.
- **B1, seasonal normal:** `Y_next = C_next`.
- **B2, seasonal-scaled persistence (the declared baseline):** `Y_next = (Y_prev + 7) · (C_next + 7)/(C_prev + 7) − 7`.
- **M1, ridge regression** on `z` with the inputs of section 3, standardised with the training fold's own mean and
  spread. Penalty chosen from {0.1, 1, 10, 100}.
- **M2, boosted regression stumps** on `z` (squared loss, depth 1, learning rate 0.1, 16 candidate cuts per input at
  the training fold's own quantiles; written in NumPy, no new dependency). Rounds chosen from {50, 100, 200}.
  Justification for one tree-type challenger: the seasonal change may depend on the level in a way a straight line
  misses. No other model family, no deep learning, no wider search.

## 5. Splits (dates fixed here)

- **Validation, used for every choice:** the years 2021, 2022, 2023 and 2024, one at a time. For validation year `V`,
  a model is fitted on origins whose target week ends before 1 January `V`, with seasonal normals from the years before
  `V`, and scored on the eligible origins whose target week lies inside `V`. Penalty and rounds are the values with the
  lowest mean absolute error of `z` averaged over the four years. The **one** ML candidate carried forward is the one
  with the lower such error.
- **Held-out test, read once:** eligible origins whose target week lies inside 2025. Models are fitted on origins whose
  target week ends on or before 31 December 2024, with seasonal normals from 2018–2024. Nothing is chosen on 2025.
  The runner writes `holdout.json` once and refuses to overwrite it.
- Row order is never shuffled. No fold sees a later date than its own test origins.

## 6. Metrics

- **Primary:** mean absolute error of `z` on the held-out origins (`MAE_z`). `exp(MAE_z)` is reported as the typical
  factor by which a prediction misses.
- **Count error:** WAPE of `Y_next` (sum of absolute errors ÷ sum of observed), overall and for October–November,
  April–May and the other months. A percentage error is an error, not an accuracy.
- **Direction:** the three-way agreement with section 2's observed change; the share correct among the origins where
  a direction is issued; and how often no direction is issued.
- The number of eligible and ineligible origins is reported with every figure. Failures are kept.

## 7. Uncertainty

An 80% interval for `z` is the prediction ± `q`, where `q` is the 80th percentile of the absolute validation errors of
the carried-forward model (out-of-sample predictions of 2021–2024). `q` is fixed before the held-out year is read.
On the held-out year the interval's coverage and its width (`exp(2q)`, the ratio of its ends) are reported.

**Direction issued by a model:** "increase" if its predicted ratio is at least 1.25 **and** the interval's lower end
is above 1; "decrease" if the predicted ratio is at most 0.80 **and** the upper end is below 1; otherwise **no clear
direction**. No clear direction is an abstention. It is not a prediction that nothing will change.

## 8. Release rule (all must hold)

1. **Material improvement:** the carried-forward model's held-out `MAE_z` is at least 10% lower than B2's, is lower
   than B0's and B1's, and the 90% interval of (B2's error − the model's error), from a block bootstrap over the
   held-out origins (blocks of 4 consecutive origins, 2,000 resamples, seed 20261112), lies above zero.
2. **Uncertainty behaves:** held-out coverage of the 80% interval is between 70% and 90%.
3. **Direction:** a direction is issued on at least 10 held-out origins, and at least 70% of those are right
   (observed `R > 1` for "increase", `R < 1` for "decrease").
4. **Fresh inputs:** the last complete input day is at most 3 days before the day the outlook is shown, in the same
   processing stream the model was tested on.

If 1–3 fail, no ML outlook is shown. The benchmark table is shown as it came out, and the baseline is never renamed
as ML. If 4 fails, no current outlook of any kind is shown, whatever 1–3 say: the result is a **retrospective
experiment (hindcast)** on reprocessed archive data. This archive ends on 31 December 2025, so rule 4 cannot hold on
12 November 2026 unless a tested, current input stream is added under a new protocol entry.

## 9. Known limits, stated before the result

- Standard-archive data are reprocessed; no as-issued near-real-time vintages are kept for 2018–2025. This is not a
  real-time backtest.
- One area, one satellite, one horizon, seven and a half years. About 50 held-out weeks.
- The target is detections by one instrument. Cloud, smoke and overpass timing change what is detected without any
  change in burning; no clear-sky exposure is known for these days.
- A good score would show that detection counts follow their own recent past and season. It would say nothing about
  causes, and it would not make this a warning system.

## Change log

- 12 Nov 2026: first version, frozen before fitting.
