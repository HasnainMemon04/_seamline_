# Protocol P04: Terra's step outside Punjab, season dates, the record past 2 Nov 2026, the headline check and a positive control

Written 5 Nov 2026 by Claude (build session), for the package chosen that day (DECISIONS.md, "Strategy package"; research/08_C08_What_To_Build_Different_2026-11-05.md). It is committed **on its own, before any data used by these tests is opened**. Runs start only after the research session's CHECK REPORT on this file, or when Hasnain says to go ahead without it.

P01 and P02 and their results stay unchanged. Any later change to this file is logged at the bottom, with its reason and date, before the result it affects. Each test runs once.

## 0. What had already been seen (so nothing below is called blind where it is not)

- **All results of P01 and P02**, and the P02 post-hoc file (reports/c08/p02_posthoc.json). For Punjab only, these include:
  - yearly Terra and Aqua Q (October, November, other months, 2012–2025);
  - median detection times;
  - S-NPP's October–November counts for 2018–2025;
  - burned area;
  - Terra's November-only step: −61% from 2021 to 2022.
  - Monthly median detection times for Terra and Aqua over all of Pakistan, 2021–2025, were also printed in a scratch check.
- **The research study's probes, all Punjab only** (research/strategy_2026-11-05/probe_scripts):
  - Rice-season dates (15 Sep–31 Dec; onset, middle, end, peak) per satellite, 2003–2025. Aqua − S-NPP middle dates ranged from −3 to +3 days, and end dates from −3 to +4 days; onsets were about 3 days later on Aqua.
  - 1–29 October counts per satellite, 2018–2025 (all rows, and quality-filtered rows).
  - Season totals, Aqua against S-NPP, 2012–2025, with z-scores.
- **Sindh and Khyber Pakhtunkhwa (KP), in aggregate only:**
  - monthly counts in the app's calendars and charts (viewed during checks on 2–5 Nov);
  - P01's Sindh test (2012–13);
  - P01's provincial drift diagnostic (Aqua to S-NPP, 2018–2025);
  - P02 D1's T2 and T3 tests (Aqua and S-NPP monthly day counts, 2012–2021, as WAPE and yearly bias).
- **2026:**
  - the near-real-time (NRT) download of 26 Oct–2 Nov 2026. Its Punjab latest-days counts for 27 Oct–1 Nov were S-NPP 2,560 and NOAA-20 2,647;
  - press figures for Pakistani Punjab, 1–29 Oct 2026: 13,241 detections summed over three VIIRS satellites, and 4,562 for S-NPP alone (Daily Pakistan, 2 Nov; Minute Mirror, 31 Oct);
  - PAQI's "about a third fewer than October 2025" (ProPakistani, 2 Nov);
  - NASA catalogue (CMR) granule counts, which contain no fire counts.
- **India:** published findings only, which are the effect G05 is meant to detect: iFOREST 2025, Jethva 2026, NASA Earth Observatory (Dec 2025), and stubble-fire-watch's night-pass share. No Indian FIRMS data has been opened by this project; only file sizes were checked.

**Never computed before this protocol:**
- Terra/S-NPP ratios for Sindh or KP;
- any season date for Sindh or KP;
- any spring-season date for any province;
- any 2026 monthly count for any satellite, apart from the late-October NRT days and the press figures above;
- any count from Indian FIRMS files.

**Tolerances set from Punjab.** The date tolerances in section 2 (3 days for middle dates, 4 for end dates) and the count floors were set from Punjab's probe, which is disclosed above. Sindh and KP are the test.

## 1. G01: is Terra's autumn fall also in Sindh and KP? (check for the "same fields, different clocks" strip)

**Quantity.** For each province (Sindh, KP) and year 2018–2025:

    R(y) = Terra day-pass detections / S-NPP day-pass detections

Both counts use the standard stream, the quality rule and the type-0 screen, and only months that are complete for both satellites (P01 change log, item 2). October 2022 is not complete for Terra: FIRMS lists 11–22 Oct as missing during its orbit change. R is computed for November alone, and for October–November.

**Eligibility.** A province-year counts only if:
- S-NPP has at least 300 day-pass detections in the months used; and
- the expected Terra count is at least 20, where the expected count is S-NPP's count × the mean R over the eligible years of 2018–2021.

A fall to near zero therefore stays visible.

**Tests, per province:**
1. **Period fall (October–November).**
   - Δ = mean R(2023–25) / mean R(2018–21) − 1.
   - An exact one-sided permutation test with whole years as the unit (every split of the eligible years into the two groups sizes). This is the rule from CHECK REPORT P02, fix 6.
   - "Fall present" if Δ ≤ −0.40 and p ≤ 0.10.
   - "Not testable" with fewer than 3 eligible years in 2018–21 or fewer than 2 in 2023–25.
2. **2022 step (November only).** "Step present" if R(Nov 2022) is below every eligible R(Nov 2018–21) and at most 0.6 × their mean.

**Reading, declared now:**
- **Fall (and step) in Sindh or KP too:** a satellite-side cause becomes more likely (the pass time, the October 2022 orbit change, or both). It remains untested.
- **No fall where testable:** this does not rule out the clock, because burning hours may differ between provinces. It is reported as "Terra's fall not seen there".
- Either way: no "proves", and no cause claimed.

## 2. G02: season dates that survive the change of satellite (critical periods)

**Windows:**
- **Rice season:** 15 Sep–31 Dec (primary).
- **Spring season:** 15 Mar–30 Jun (secondary). This is mostly wheat residue in Punjab and Sindh; in KP it includes forest fires.

**Dates.** For each province, year, satellite and window, using day-pass detections (standard stream, quality rule, type-0 screen):
- **middle date:** the first calendar day on which the cumulative share of the window's detections reaches 50%;
- **end date:** the first day on which it reaches 90%.
- Onset (10%) is not used: in Punjab it differed by about 3 days between Aqua and S-NPP.
- One difference from the probe: the type-0 screen is added, so Punjab's dates are recomputed under this rule for display.

**Pairs:**
- **Primary:** Aqua against S-NPP, 2012–2025 (the MODIS-to-VIIRS change).
- **Secondary:** NOAA-20 against S-NPP, 2018–2025 (the 2026 handover). Spring 2018 is not used, because NOAA-20's archive starts on 1 Apr 2018.
- Terra is not used ("morning, different").

**Eligibility of a province-year (per pair and window):**
- each satellite of the pair has at least 100 day-pass detections in the window; and
- neither satellite's standard record has FIRMS-listed missing days inside the window.

**Tests:**
- **Rice season:** held out on Sindh and KP. Punjab's rice dates were seen.
- **Spring season:** on all three provinces. None of their spring dates has been seen.
- **Per province, window and pair:** Δ = date(first satellite) − date(S-NPP), in days.
  - "Middle date holds" if |Δ_middle| ≤ 3 days in all but at most 2 eligible years.
  - "End date holds" if |Δ_end| ≤ 4 days in all but at most 2 eligible years.
  - "Not testable" with fewer than 6 eligible years.

**Reading, declared now:**
- **Holds in both Sindh and KP (rice, Aqua–S-NPP):** that date is shown as one "critical period" band labelled "the same on the old and new satellites". Punjab's band is labelled as the development area.
- **Holds in one province only:** the claim is limited to it.
- **Fails:** the dates are shown per satellite, side by side, with no "survives the change" claim.
- **NOAA-20–S-NPP holds:** the band continues on NOAA-20 after S-NPP's end.
- Historical dates only; never a forecast.

## 3. G03: the record past 2 Nov 2026 (NOAA-20 bridge test)

**Data.**
- FIRMS API with Hasnain's MAP_KEY, Pakistan, 1 Jan–31 Oct 2026, for S-NPP and NOAA-20.
- **Stream, month by month:** both satellites use the standard stream (SP) if FIRMS's data-availability list shows SP for the whole month for both; otherwise both use NRT. The two satellites are never mixed across streams within a month.
- Files are hashed and recorded in the manifest, like other raw files. The FIRMS missing-days list is refreshed at the same time and hashed, and it defines complete months for 2026.

**Filters.**
- The quality rule and the same provincial polygons.
- The type-0 screen where the files carry a type field. Where a month has no type field (NRT), the screen is skipped for both satellites. The bridge for that month is then fitted without the screen too: same model, same training months.

**Bridge.**
- Model M1, selected in E01 (`hz.fit(..., "M1", src="NOAA20")`), predicting S-NPP's monthly total (day + night) from NOAA-20.
- **Primary:** fitted on all Punjab months from 2018-04 to 2025-12 that are complete for both satellites (`p01.DEPLOY_BRIDGE`). This is the version that would continue the record.
- **Secondary, reported:** E02's tested fit on 2019–2023.
- Nothing is refitted on 2026.

**Scored months.** January–October 2026 months that are complete for both satellites in Punjab. "Not testable" with fewer than 6 scored months.

**Pass mark, set from the 2024–25 test (WAPE 4.4%; worst month about 12%):**
- WAPE ≤ 0.10 over the scored months; and
- every scored month with at least 300 S-NPP detections has |predicted − observed| / observed ≤ 0.20.
- Months with fewer than 300 S-NPP detections, where counting noise alone is about ±8–10%, are reported but not held to the month rule.

**Reported, not held to the pass mark:** Pakistan, Sindh and KP.

**Reading, declared now:**
- **Pass:** from November 2026 the harmonised record continues on NOAA-20, converted by the primary bridge, in whole months only (no month mixes satellites). The seam is drawn and labelled "S-NPP ended 2 Nov 2026, 15:40 UTC (NOAA NESDIS Update #4)". NOAA-21 appears only as its own labelled series, never summed.
- **Fail:** the harmonised record stops at October 2026, the last full S-NPP month, and the app says that the bridge failed its frozen test. NOAA-20 is shown in its own units.
- The result is reported either way.

## 4. G04: reproducing this week's headline (check for the headline card)

**Check.**
- Pakistani Punjab (geoBoundaries polygon), 1–29 Oct 2026, all rows: no quality or type filter, as a press count may use. The stream is as in G03; NOAA-21 is NRT.
- **Sum test:** S-NPP + NOAA-20 + NOAA-21 must be within ±20% of 13,241.
- **Single-satellite test:** S-NPP alone must be within ±20% of 4,562.
- **Reading:** both within → "reproduced". Otherwise: "not reproduced; the published method may differ (area, filters or stream)". The card shows our counts either way.

**Demonstration, not a test** (the effect is true by construction):
- the card shows each satellite's count for 1–29 Oct, 2019 and 2026, side by side and never stacked, under the project's quality rule;
- the number of VIIRS satellites flying (2 and 3);
- the S-NPP-only change beside the summed change.

Neutral wording, Pakistan only, no country comparison.

## 5. G05: positive control on Indian Punjab and Haryana (stretch: run only if the core is on track by 10 Nov)

**Data.**
- FIRMS public yearly country files for India, MODIS and S-NPP, 2018–2025 (no key).
- Each file is downloaded one at a time, after a disk check (2 GB must stay free), hashed and recorded. It is cropped to the bounding box of the two states, the crop is kept, and the original is deleted.
- State polygons: geoBoundaries IND ADM1 ("Punjab", "Haryana"), hashed.
- Needs Hasnain's download go-ahead.

**Quantity.** For each year 2018–2025:

    R_A(y) = Aqua day-pass detections / S-NPP day-pass detections

Using October–November months complete for both, and separately all other months. Quality rule and type-0 screen.

**Prediction: the control sees the published late-burning shift if all three hold:**
1. Δ_A(Oct–Nov) = mean R_A(2023–25) / mean R_A(2018–21) − 1 ≥ +0.20.
2. Every year in 2023–25 is above every year in 2018–21 (exact one-sided p = 1/35).
3. Δ_A(Oct–Nov) > Δ_A(other months).

**Reading, declared now:**
- **Pass:** the clock test can see a known late-burning shift. Pakistani Punjab's Aqua result (+4%, whole-year p = 0.77) then argues against an India-sized shift in 2023–25, but only as far as Pakistan's range excludes India's effect; both ranges are shown.
- **Fail:** the test cannot see the published shift with these satellites, so the Pakistani Aqua result is no longer cited as evidence about burning time, and P02's wording is updated.

**Secondary, reported:** Terra's October–November ratio in India, 2023–25 against 2018–21, and its November 2022 step. If India shows the same 2022 step, a Terra-side cause is more likely.

**Place.** Only on the methods page and one line on a slide. No country ranking, no side-by-side maps, no country totals.

## 6. Order, records and general rules

1. This file is committed alone. The research session checks it.
2. G01 and G02 use data in hand. G03 and G04 run after the 2026 download, which needs Hasnain's go-ahead. G05 runs only if the core is on track by 10 Nov.
3. Code: `c08/p04.py`, written after this commit and implementing exactly these rules. Results go to experiments/P04_G01_terra_step, P04_G02_season_dates, P04_G03_bridge_2026, P04_G04_headline and P04_G05_india_control. Each is run once, and the code refuses to overwrite a result.
4. Every result file records `code_state` (commit, uncommitted-changes flag, c08 source hash) and `ingest.protocol_state("experiments/PROTOCOL_P04.md")` (path and SHA-256 of this file).
5. Whole years are the unit wherever periods are compared (CHECK REPORT P02, fix 6). Exact permutation tests are used; there is no day-level bootstrap.
6. **Not tested here (display only):**
   - the day-by-day calendar. Daily values in the MODIS years use the monthly conversion, and their daily accuracy is untested; the screen says so;
   - the clock strip's P02 numbers, already checked in REVIEW_P02;
   - the verification log.

## Change log

### Entry 1: 5 Nov 2026, evening, before any G01–G05 test data is opened

Written by the build session after CHECK REPORT P04 (docs/REVIEW_P04_2026-11-05.md), then corrected the same evening after three Opus agents checked a draft against that report. **Where this entry and the text above differ, this entry governs**; the main replaced lines are named where they are replaced.

**Runs.** G01–G04 start only after the research session's CHECK REPORT P04-CL on this entry, or when Hasnain says to go ahead without it. This replaces line 3's condition, which CHECK REPORT P04 already met.

**Rounding.** Every comparison in G01–G04 uses unrounded values; rounding is for display only.

**Where the numbers come from.** The new Punjab numbers (items 3.3 and 4.6) and the availability counts come from `python -m c08.p04_devcheck` (output reports/c08/p04_devcheck.json); every other number names its source where it appears.
- That module counts Punjab only, P04's development area, which is already seen.
- For every other place, every spring window and 2026, it reads only the FIRMS missing-days lists and each platform's archive span (the first and last day of its record in the whole Pakistan table): dates, never counts.
- It ran in two versions, both counting Punjab only. The first (5 Nov evening, never committed) counted G02's gaps in calendar days only. The second (run 8 Nov, committed with its output as 705d2ee, whose c08 sources hash matches the one recorded) adds matched-day gaps, whole-number dates and a hash check of the detections file it reads.
- No Sindh or KP count, spring date, 2026 count or Indian count was computed for this entry.

#### 1. Section 0, corrected and completed (report §4)

1. **India (line 30).** No Indian yearly FIRMS file has been opened. Indian rows exist in two kinds of file in hand, and nothing counted them by state or satellite:
   - the 2026 South Asia NRT files (data/raw/firms_nrt/20261102T1200Z), from which the C08 ingest dropped them together with every other non-Pakistan row (9,630 rows in all; reports/c08/ingest_report.json);
   - two global 24-hour files from 27 Oct, downloaded by the Portugal baseline as an access smoke test and never ingested (src/build_source_register.py).

   Also seen: HamariHawa's published 1–29 Oct 2026 count for Indian Punjab, 918 for S-NPP alone (research/08, line 303).
2. **The checker's earlier scripts printed related numbers.** They are not G01 or G02 quantities (wrong passes or quantities), but they bear on G01's S-NPP floor and on G02's spring and NOAA-20 eligibility:
   - docs/review_2026-11-03_p02/scripts/clock_g_time.py: Terra and Aqua day-pass median times and yearly counts for "non-Punjab, all months" from 2016. It was run (verdicts.json, line 9).
   - docs/review_2026-11-02/scripts/science_reviewer/q7.py: Sindh's yearly October–November S-NPP-equivalent and Aqua totals.
   - docs/review_2026-11-02/scripts/skeptics/F2_judge/f2_indep.py, as its code reads, for Sindh, for October–November and for April–May:
     - yearly S-NPP and NOAA-20 totals, 2012–21 (day and night, standard stream, quality rule, type-0 screen);
     - Terra's share of early MODIS, 2003–11;
     - the NOAA-20/S-NPP season ratio, 2018–21.

     A 2012–17 Terra/S-NPP ratio for Sindh follows from these outputs.
   - The outputs of q7.py and f2_indep.py were not saved.
3. **The late-October latest-days counts were also seen for Sindh, KP and all of Pakistan**, not only Punjab (docs/review_2026-11-03_b05fix/verdicts.json; the app's card works for any area).
4. **Line 14.** The −61% (November step) and the −79% (October–November fall) are P02 **Q** values: actual detections ÷ a camera model's prediction. They are not raw Terra/S-NPP ratios. Punjab's raw values under G01's rules are in item 3.3 below.
5. **Line 15.** The all-Pakistan scratch check of monthly median detection times was not saved, so it cannot be reproduced.
6. **New exposure from this entry:** Punjab's raw G01 ratios and Punjab's rice-season G02 dates under the rules below. Both are in p04_devcheck.json, and Punjab is the development area.
7. **Punjab's monthly Aqua and S-NPP counts were seen** in the app's charts and calendars, for all months, including 15 Mar–30 Jun, 2003–2025. No spring date was computed from them.
8. **What the app could serve since 2 Nov.**
   - Its analysis reply has carried per-satellite monthly columns, Terra included, for every area. The page never draws Terra.
   - The monthly CSV carries the same columns, and the detections export carries every row.
   - The build session's notes record no printed Terra or per-satellite Sindh/KP months, and no Sindh, KP or Pakistan detections export. Older session transcripts were not searched, so as not to open them.
   - Item 10.4 now closes all of these until the tests have run.

#### 2. One day rule for G01, G02 and G03: matched days (B2, B3, report §5.4)

A **matched day** is a UTC day on which both satellites being compared:
- are inside their archive record (from the first to the last day of the satellite's record in the Pakistan table); and
- are not on the FIRMS missing-days list.

Both satellites' counts are summed over the same matched days, so a gap removes the same days from both sides.
- This replaces "only months that are complete for both satellites" (line 47) and G02's "no FIRMS-listed missing days inside the window" (line 87). For G03 it also replaces lines 109 and 121 (item 6.4).
- Reason: comparing two satellites over the same days is fair whichever days are missing, and it keeps years that one listed day would otherwise remove. Examples: S-NPP is missing 3–5 Nov 2024; NOAA-20 is missing 30 Sep 2023.
- **G01 and G02 use the committed list**, research/metadata/provider_missing_dates.json (27 Oct snapshot; its SHA-256 is in p04_devcheck.json).
- **G03** uses the refreshed lists saved at download time (section 6).

#### 3. G01: Terra's fall outside Punjab (B3, B4, B5; report §5.1, §5.2, §5.11)

1. **Days.** R(y) = Terra day-pass detections ÷ S-NPP day-pass detections, summed over the matched days of the window (standard stream, quality rule, type-0 screen).
   - A window-year counts only with **at least 90% of its days matched**: 55 of 61 for October–November, 27 of 30 for November.
   - From the list: October–November 2022 has 49 matched days (Terra is missing 11–22 Oct), so it is out. That window is not in either period group anyway.
   - 2024 has 58 (S-NPP is missing 3–5 Nov), so it stays: the period groups are 2018–21 (4 years) and 2023–25 (3 years). This settles B3.
2. **Floors.** The eligibility floors are judged on the counts of the days used.
   - **Fall test:** the mean R behind the expected-Terra floor is the mean October–November R over the 2018–21 years that pass the S-NPP floor (open choice 1).
   - **Step test:** floors are judged on November counts alone. Expected Terra = November S-NPP × the mean November R over the 2018–21 Novembers that pass the S-NPP floor on November counts.
   - If the mean R of the eligible 2018–21 years is 0, the test is not testable.
3. **Punjab, under these exact rules (B5; development area).**

   | Window | R by year (Terra ÷ S-NPP, day passes) | Result |
   |---|---|---|
   | October–November | 2018–21: 0.0279, 0.0158, 0.0234, 0.0210<br>2023–25: 0.0067, 0.0039, 0.0018 | Δ = **−0.81**, one-sided p = 1/35 |
   | November | R(2022) = 0.0073; mean of 2018–21 = 0.0192 | **0.38× the mean**, below every year of 2018–21 |

   Under the month rule as written, the fall is Δ = −0.78 (p = 1/35), with 2024 on October alone. The checker's 0.72 used the probe's window and no type screen. That window, 15 Sep–31 Dec, covers late September, October, November and December, including Terra's missing 11–22 Oct 2022; G01's step is November only. Under G01's rules, Punjab passes both marks with margin, so **−0.40, p ≤ 0.10 and 0.6 are kept** (section 9).
4. **Step test (B4).** It is not testable unless November 2022 and **at least 3 Novembers of 2018–21** pass both floors, judged on November counts alone.
5. **Permutation (report §5.11).**
   - The statistic is the difference of means of R between the two groups, over every split of the eligible years into the two group sizes. The one-sided p is the share of splits with a difference at or below the observed one, within 10⁻¹². This is `permutation()` in c08/p02_posthoc.py, field `p_as_low`.
   - Smallest p: 1/35 at 4 and 3 years; 1/15 at 4 and 2; 1/20 at 3 and 3; exactly 0.10 at 3 and 2. That is why the comparison is inclusive.
6. **Readings, per province, replacing lines 63–66 (report §5.1, §5.2).** Each province gets two clauses, one per test, so every combination has exactly one reading:

   | Fall test | Fall clause |
   |---|---|
   | Δ ≤ −0.40 and p ≤ 0.10 | "Terra's fall is also seen" |
   | Δ ≤ −0.40 and p > 0.10 | "a large fall, not significant with these years" (not "not seen") |
   | Δ > −0.40 | "Terra's fall is not seen; this does not rule out the clock, because burning hours may differ between provinces" |
   | Not testable | "the fall is not testable", with the reason |

   | Step test | Step clause |
   |---|---|
   | Present | "a 2022 step is seen" |
   | Absent | "no 2022 step is seen" |
   | Not testable | "the 2022 step is not testable", with the reason |

   - The reading is "<province>: <fall clause>; <step clause>."
   - **Only when both are present** does it add: "This is consistent with a satellite-side cause (the pass time, the October 2022 orbit change, or both); a Pakistan-wide change in burning hours would give the same result; untested." No reading ranks causes.
   - **"Seen outside Punjab"** means "Terra's fall is also seen" in at least one province, named. A step without that fall is reported as such, not as "seen".
   - **The strip** shows Punjab (development area) and both clauses for each province. Its title is neutral: "Morning and afternoon passes see different shares" (research/08, dated correction at lines 41 and 266). It replaces the strip title "same fields, different clocks" (line 41).

#### 4. G02: season dates (B6; report §5.3, §5.4, §5.12)

1. **Days.** Dates are computed over the window's matched days for the pair, in calendar order.
   - A province-year needs **at least 100 of the window's 108 matched days**.
   - From the list: spring 2022 for Aqua–S-NPP (92 days; Aqua is missing 1–16 Apr) and spring 2018 for NOAA-20–S-NPP (91; the archive starts on 1 Apr 2018) are out. Every other year stays.
   - **Dates, in whole numbers** (replaces lines 75–76): the middle date is the first matched day on which 2 × the cumulative count ≥ the window's total; the end date is the first on which 10 × the cumulative count ≥ 9 × the total.
   - **The gap Δ is counted in matched days** (replaces line 92's calendar days): the difference between the two satellites' positions in the pair's matched-day sequence. Removed days never count as disagreement. Example: in Punjab in 2024, Aqua's middle date (6 Nov) is 6 calendar days after S-NPP's (31 Oct), but only 3 matched days, because 3–5 Nov are removed.
2. **Floor raised from 100 to 200** day-pass detections per satellite, counted on the pair's matched days (report §5.3).
   - In the checker's simulation with equal true timing (lead/g02_power_lead.py), both dates held over 13 years in 86% of runs at 200, against 33% at 100. 200 is the lowest floor in that table with power above 80%.
   - The floor was fixed from the simulation alone. How many Sindh, KP or Punjab-spring years pass 100, 200 or 300 was not looked up, although the app's monthly totals (section 0 and item 1.7) would show it roughly.
3. **"Holds".**
   - A date holds if |Δ| is within its tolerance (3 days for the middle date, 4 for the end date) in all eligible years except at most ⌊0.2 × n⌋, where n is the number of eligible years. That allows 2 misses at 10–14 years and 1 at 6–9 years. This replaces "all but at most 2", which allowed 2 of 6.
   - **The pair holds for a province and window only if both dates hold.**
   - Not testable with fewer than 6 eligible years.
4. **The band.** For each satellite, the span from its middle date (50% of the window's detections) to its end date (90%), per year. Onset (10%) is still not used. The words "critical period" are dropped: the screen says "the season's middle and end dates (detected burning activity)".
5. **Readings, replacing lines 97–102.**

   | Outcome | Reading |
   |---|---|
   | Rice, Aqua–S-NPP holds in Sindh and in KP | Each province's band is labelled "the same on the older and newer satellites (Aqua and S-NPP)" |
   | Holds in one province only | That label for that province only. The other shows each satellite's band side by side |
   | Fails (either date) | Each satellite's band side by side, with no "same on both" label, plus "k of n eligible years outside the tolerance" |
   | Not testable | Each satellite's band for its eligible years, labelled "not tested: too few years with enough detections" |
   | Spring | Read the same way, province by province (Punjab included), and independently of rice. Rice may hold while spring fails, and only the pair that holds gets the label |
   | NOAA-20–S-NPP holds (province, window) | NOAA-20's dates are labelled "matched S-NPP's dates within the tolerance in <the eligible years, listed>" |
   | NOAA-20–S-NPP fails | NOAA-20's dates are labelled "did not match S-NPP's dates within the tolerance (k of n eligible years outside)" |
   | NOAA-20–S-NPP not testable | NOAA-20's dates are labelled "not tested" |
   | Punjab, rice, both pairs, any outcome elsewhere | Each satellite's band side by side, labelled "development area (dates seen before the test)". Punjab's rice dates are not tested |

   - **After S-NPP's end,** NOAA-20's own dates are shown only for complete windows, each labelled with its pair's outcome above (Punjab's rice: "development area, not tested"). The first such window is rice 2026, complete on 31 Dec 2026, after the event. Its stream (standard with the type-0 screen, or NRT without it) is named beside it.
   - Historical dates only, never a forecast.
6. **Punjab under these rules (development area; rice only; no spring date computed; p04_devcheck.json, commit 705d2ee).**
   - **Aqua–S-NPP:** 14 eligible years, with no miss. The largest gaps are 3 matched days (middle; 2024, which is 6 calendar days) and 4 (end). It holds.
   - **NOAA-20–S-NPP:** 8 eligible years; largest gaps 1 matched day (middle) and 3 (end). It holds.
   - Under the rule as written (13 and 6 years), Punjab's largest gaps are exactly 3 and 4 days: the tolerances have no headroom (B8). Counting 2024's gap in calendar days would have made one middle-date miss.
7. **Not used:** the source "mostly wheat residue" (line 72). The spring window is simply 15 Mar–30 Jun.

#### 5. G01 and G02 run together

G01 and G02 share data: Sindh and KP October–November day passes. Every rule above is fixed before either runs, they run in one invocation, and nothing from G01 changes G02.

#### 6. G03: the NOAA-20 bridge on 2026 (B1, B2; report §5.5, §5.6, §5.7)

1. **The key (B1).**
   - Every stored or printed URL shows `<MAP_KEY>` in place of the key.
   - The manifest records the source, area, start date, day range and data_id, never the key.
   - A test fails if data/manifest.json contains the key from .env. That test reads the key but never prints it.
   - Before each commit, the manifest is checked.
   - If the key in .env is the one pasted into chat on 5 Nov, Hasnain replaces it before the first API call.
2. **Streams.** As line 108: a month uses the standard stream (SP) only if FIRMS's data-availability answer shows SP for the whole month for both satellites; otherwise both use NRT. A month that the SP/NRT boundary falls inside uses NRT. "SP for the whole month" means the availability range covers the month; listed missing days are handled only by the matched-day rule.
3. **Matched days in 2026.**
   - A day is matched if neither satellite is on either refreshed list, standard or NRT. NRT lists do not cover days before the last standard date.
   - Each satellite must also have at least one row anywhere in Pakistan on both its day and its night pass that day.
     - A row is any row of the downloaded Pakistan file, before the quality rule.
     - A pass is the daynight flag; the day is the UTC acq_date.
     - The check applies to every 2026 month, SP or NRT, so an empty or failed download chunk is never counted as zero.
     - Its cost: a pass with no detection anywhere in Pakistan, such as a quiet night, is treated as missing, on both sides. The latest-days panel uses the same rule (DECISIONS.md, 3 Nov).
4. **Scored months** (replaces lines 109 and 121).
   - A month is scored if it has **at least 20 matched days**, using totals over those days.
   - The 300 floor for the month rule is S-NPP's day-plus-night total on the matched days (open choice 2).
   - From the 27 Oct list, matched days per month are: January 31, February 28, March 28, April 27, **May 0**, June 28, July 26, August 31, September 30 and October 31. That gives 9 scored months, unless the refreshed list or the NRT pass check removes more.
   - November and December are never scored.
5. **Not testable (B2).** Fewer than 6 scored months means "not testable". The harmonised record then stops at October 2026; the app says "the NOAA-20 bridge was not tested (too few months with matched data)"; and NOAA-20 is shown in its own units. "Fail" is used only for a bridge that was tested.
6. **Pass mark (report §5.5).**
   - Pass or fail is decided by the primary bridge alone.
   - WAPE = Σ|predicted − observed| ÷ Σ observed over the scored months (`metrics()` in c08/harmonize.py).
   - M0 (no conversion) is reported beside it. In E02, M0 scored 0.0447 against M1's 0.0438, so a pass shows that converted NOAA-20 tracks S-NPP within the marks, not that M1 beats no conversion.
   - **After October 2026** NOAA-20's files are NRT, with no type field. The record then uses the primary bridge's months fitted without the type screen, as for NRT months in the test (line 113).
7. **Regions (report §5.6).** This narrows line 131's Pass reading.
   - Only Punjab is scored, and only Punjab's harmonised record continues past October 2026, on its own bridge.
   - Other areas show NOAA-20 in its own units after S-NPP's end, labelled "bridge tested in Punjab only".
   - Pakistan, Sindh and KP scores are reported, not held to the mark. Each uses its own M1 fit on its own complete months of 2018-04 to 2025-12 (refitted without the type screen for NRT months), with the same day rules and floors, and is labelled "reported, not tested". Punjab's factor is never applied to another area.
8. **Records (report §5.7).** Saved as new files, each with the download date and hashed:
   - the refreshed missing-days lists;
   - FIRMS's data-availability answer.

   P01, P02, G01 and G02 keep using the committed 27 Oct list, so their reproduction is unchanged. Also recorded: the download time, the stream used for each month, and the raw file hashes.

#### 7. G04: the headline check (report §5.10)

1. The ±20% is measured from the press numbers (13,241 and 4,562). The dates are UTC days.
   - **Data:** S-NPP and NOAA-20 as in G03, plus NOAA-21's NRT file for 1–29 Oct 2026, hashed and recorded with its list version.
   - G04 counts every UTC day of 1–29 Oct. Listed gap days are reported beside the counts, not removed.
2. **Readings** (replaces line 141's two-way reading):

   | Sum (S-NPP + NOAA-20 + NOAA-21) | S-NPP alone | Reading |
   |---|---|---|
   | Within | Within | "Reproduced" |
   | Within | Not within | "The three-satellite sum matches the press figure, S-NPP alone does not: the published single-satellite count may use another method" |
   | Not within | Within | "S-NPP alone matches; the sum does not: the press may have summed other satellites or streams" |
   | Not within | Not within | "Not reproduced; the published method may differ (area, filters or stream)" |

3. **The summed change** is labelled as the press method: "a naive sum of satellites, not comparable across years" (docs/DATA_CONTRACT.md).
4. **The demonstration's numbers** (display only, lines 143–146): each satellite's 1–29 Oct count in Punjab, for 2019 and 2026, under the quality rule and with no type screen in either year, because NRT files have no type field. The summed change uses the same rows and carries the naive label.
5. **2019 is the press's comparison year.** It was also S-NPP's lowest Punjab rice season of 2018–25 (15 Sep–31 Dec: 11,317; report §5.10), so the card shows the 2018–25 range of the same 1–29 Oct count beside it.

#### 8. G05 is withdrawn (B7)

G05 is withdrawn before any Indian data is opened:
- As written, it compared P02's Q result for Pakistan (+4%) with a raw ratio for India.
- Aqua's own pass moved later, which raises the raw Aqua/S-NPP ratio wherever afternoon burning exists. On the raw ratio, Pakistani Punjab rose about 18% with full separation (report B7, from the probe table).
- A fair test would compare India with Pakistan year by year. That is a new design, and G05 was a stretch item due by 10 Nov.

If the core is on track, it may return as a separate protocol. P02's Aqua result stays stated in Q units only. Open choice 3 is closed with it.

For G05, section 6 items 2–3 (lines 180–181) no longer apply: it is not run and has no result folder, and c08/p04.py implements G01–G04 only. The title's "positive control" is withdrawn with it.

#### 9. Where each threshold comes from (B8; corrects line 39)

Line 39 is corrected:
- The date tolerances equal the extremes of Punjab's probe, so they have no headroom.
- **The count floors were not set from the probe.** The probe skipped seasons below 200 detections, and Punjab's smallest season was 1,179.

| Number | Test | Source |
|---|---|---|
| Δ ≤ −0.40 | G01 fall | Judgment, set in the frozen text beside P02's Q values (−79%, −61%); checked on 5 Nov against Punjab's raw R (−81%; item 3.3) and kept |
| p ≤ 0.10 | G01 fall | Judgment: the largest p that the smallest allowed groups (3 and 2 years) can reach |
| 0.6 × the mean, below every year | G01 step | Judgment, set in the frozen text beside P02's Q values; checked on 5 Nov against Punjab's raw R (0.38×) and kept |
| 300 S-NPP; 20 expected Terra | G01 floors | Counting statistics: at 300 a count's Poisson noise is about ±6%; at 20 expected, a fall to zero stays visible |
| 3 and 2 years minimum | G01 | Judgment, frozen at d0e75b5 (line 60): 3 and 2 is one of the smallest designs in which p can reach 0.10 (2 and 3 is another) |
| 90% of days matched | G01 | Judgment |
| 3 and 4 days | G02 tolerances | Data: the extremes of Punjab's probe (no headroom) |
| 200 detections | G02 floor | Counting statistics: the checker's power simulation (item 4.2) |
| 100 of 108 days | G02 | Judgment |
| ⌊0.2 × n⌋ misses; 6 years | G02 | Judgment (keeps the original 2 of 14) |
| WAPE ≤ 0.10; month error ≤ 20% | G03 | Data: E02's 2024–25 test (WAPE 0.044, worst month 12.4%), with margins of about 2.3× and 1.6× |
| 300 S-NPP in a month | G03 | Counting statistics: below it, noise alone is about ±8–10% |
| 20 matched days; 6 months | G03 | Judgment |
| ±20% | G04 | Judgment: press methods may differ in area, filters and stream |

#### 10. Records, provenance and later changes (report §5.8, §5.9, §5.12)

1. **Every result file records:**
   - the platforms, streams and filters;
   - the days and months used;
   - the eligible years, with each exclusion's reason;
   - the input hashes: processed detections, missing-days list, boundaries, and any raw 2026 file;
   - `code_state` and `protocol_state`.

   c08/p04.py hashes the processed detections file it reads and refuses to run if that hash differs from the ingest report, as p01.load_inputs does.
2. **Later changes.** All known open choices are closed by this entry. If a later change is ever needed, it is logged before the result it affects, with a list of the P04 results already seen.
3. **Facts used:**
   - NOAA-20's archive in hand starts on 1 Apr 2018; FIRMS pages disagree on the date.
   - S-NPP's end follows NOAA NESDIS Update #4: 15:40 UTC on 2 Nov 2026. FIRMS's blog still says 13:00 UTC.
4. **The app's lock** (an app rule recorded in DECISIONS.md, "P04 lock", not part of any test). Until the named test has a result file, the app serves none of the following, for any area that overlaps the provinces named (Pakistan and drawn boxes included):
   - **daily values and Worldview links** in G01's and G02's windows: Sindh and KP, 15 Sep–31 Dec; Punjab, Sindh and KP, 15 Mar–30 Jun; 2012–2025 (lifts after G01 and G02, or G02 alone for spring);
   - **Terra's monthly columns** in the analysis reply and the monthly CSV, October and November 2018–2025, for areas overlapping Sindh or KP (lifts after G01);
   - **detection rows** in the export, inside those windows, for rows in those provinces (lifts as for daily values);
   - **past years in the latest-days panel** whose compared days fall in those windows.

### Entry 2: 8 Nov 2026, before any G01–G04 run

Written by the build session after an Opus check of c08/p04.py against this protocol, which found no deviation in G01–G04's logic, and after the 2026 download. **Nothing here changes a threshold, a window or a reading.** It records facts and choices before the runs, as item 10.2 asks.

1. **Go-ahead.** On 8 Nov Hasnain answered "Run without it" to "Run P04's tests before the checker's P04-CL report arrives?". Under entry 1's "Runs" paragraph, the runs may start without CHECK REPORT P04-CL. That report is applied when it arrives. Anything it finds is reported beside the results, not used to re-run.
2. **The 2026 download** (commit 9a83b63).
   - **Streams.** FIRMS's availability answer (8 Nov) has the standard stream (SP) for S-NPP and NOAA-20 up to 31 Jul 2026. So January–July use SP and August–October use NRT, for both satellites. If either satellite's SP range were missing from the answer, the runner would refuse rather than use NRT everywhere.
   - **Missing days.** The refreshed list (8 Nov, 178 entries) comes from FIRMS's missing-data page. Its answer is an HTML table of "Standard Data" and "Near Real Time Data" pairs. The runner refuses on any stream label or VIIRS satellite name it cannot map.
   - **Files.** The area API takes 1–5 days per request, so the files are 5-day chunks: 138 files, each hashed. The key is in no stored file.
   - **Exposure, logged under item 10.2.** In commit 9a83b63, data/manifest.json held each 2026 file's row count and byte size. Nobody printed, compared or summed them. They are removed in the next commit, and no P04 result had been seen.
3. **Definitions the runner uses,** closing what the text left implicit:
   - **"Anywhere in Pakistan"** (item 6.3): rows of the month's chosen stream that pass the ingest data contract and fall inside a province polygon, counted before the quality rule.
   - **G04's "all rows":** rows that pass the ingest data contract, with exact duplicates removed.
     - The 2026 rows are the download box intersected with the province polygons.
     - The 2019 and 2018–25 demonstration counts, and the bridge's training rows, come from FIRMS's Pakistan country file intersected with the polygons.
     - "Pakistan" means all seven polygons, Azad Kashmir, Gilgit-Baltistan and Islamabad included.
   - **"Listed missing" in 2026:** the union of the refreshed standard and NRT lists, for either satellite (entry 1, item 6.3).
   - **G03's month "error"** is signed, (predicted − observed) ÷ observed. The 20% rule uses its absolute value.
4. **Run safety.**
   - Each pair of results is written together, both or neither.
   - A run refuses if c08 has uncommitted changes, so every result's `code_state` matches a commit.
   - Before the runs, `python -m c08.p04 punjab-check` must reproduce Punjab's development numbers (items 3.3 and 4.6) on real data, with the same functions the runs use.
5. **The app's lock (entry 1, item 10.4), as built.** On held days, Worldview links are also withheld for any area whose map would show a held province. So until the tests have run, Punjab has no links from 15 Sep to 31 Dec, and no area has links from 15 Mar to 30 Jun (2012–2025).
