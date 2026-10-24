# Pre-registration: Industry payments and GLP-1 prescribing in Medicare Part D

**Status: LOCKED v1.0 (2026-10-23), git tag `prereg-v1`.** Approved by the author on 2026-10-23, including the judgement calls in §12 (all as drafted). Registered before any model compared exposed and unexposed prescribers after exposure (CLAUDE.md rule 6). Changes after this point go in §13 "Deviations", dated, never as silent edits.

## Summary

We test whether Medicare Part D physicians who start receiving industry payments that name a specific GLP-1 brand become more likely to prescribe that brand at volume afterwards, compared with similar physicians not yet (or never) paid for it.

**Design:**
- **Estimator:** a staggered-adoption difference-in-differences (Callaway & Sant'Anna 2021, doubly robust, not-yet-treated controls, pre-period covariates).
- **Data:** a 2013–2024 prescriber × brand × year panel.
- **Brands:** Trulicity, Victoza and Ozempic (first-payment cohorts 2015–2024).
- **Primary outcome:** whether the physician has ≥ 11 Part D claims of the brand in the year. This is the only fully observed outcome, because Part D suppresses smaller counts.
- **Exposure:** the first promotional payment naming the brand, which is absorbing. Event years 0–3 are averaged; year 0 is partly treated and is reported separately.
- **Standard errors:** clustered by group practice.

**Secondary analyses:**
- volume (30-day fills, Poisson, with suppressed cells bounded);
- brand share and switching;
- payment type;
- dose;
- specialty.

**Falsification tests:** pre-trends with HonestDiD sensitivity, statin prescribing (negative-control outcome), anticoagulant payments (negative-control exposure), placebo timing and a placebo brand.

**Interpretation is fixed in advance (§10).** Because manufacturers target high and rising prescribers, a positive estimate counts as "consistent with influence" only if pre-trends, negative controls and the matched design all hold. Otherwise it is reported as targeting.

---

## 1. Questions and hypotheses

**H1 (primary).** For brand B ∈ {Trulicity, Victoza, Ozempic}, the first promotional payment naming B is followed by a higher probability that the physician prescribes B at ≥ 11 claims a year. The estimand is the average ATT over event years 0–3, versus not-yet-treated physicians with similar pre-period characteristics. Direction: positive.

Secondary hypotheses (directional, from P02 design implications D-5 and the brief):
- **H2. Payment type.** First exposure through speaker/faculty or consulting payments has a larger ATT than first exposure through meals only. This is underpowered: about 600–1,300 GLP-1 speakers a year (D23).
- **H3. Specialty.** The ATT is larger for endocrinology and cardiology than for primary care.
- **H4. Dose.** The ATT increases across cumulative-dollar bins ($0 < $100, $100–1k, $1k–10k, > $10k). Higher bins are more selected, so this is descriptive of a gradient, not a causal dose-response.
- **H5. Switching.** Exposure to brand B raises B's share of the physician's GLP-1 claims. This includes Ozempic ↔ Mounjaro after 2022 (brand share relative to launch, P15).
- **H6. Volume.** The proportional ATT on 30-day fills of B (Poisson) is positive.
- **H7. Non-physicians.** In nurse practitioners and physician assistants (cohorts 2022+, with 2021 as a washout year, D10), the ATT is positive.

## 2. Data

- **Sources:**
  - CMS Open Payments General Payments, PY2013–2024 (PY2025 descriptive only, D6).
  - CMS Medicare Part D Prescribers by Provider and Drug, and by Provider, 2013–2024.
  - Doctors and Clinicians national file (practice IDs, October 2026 snapshot).
  - Reference files as built in P03–P10 (DATA.md §6–13).
- **Drug-name and NPI maps:** drug names are mapped with `data/reference/drug_name_map.csv` (P07). Recipients are linked to NPIs as in P08: 98.5% of 2013 records, 99.3% of 2014 and ≥ 99.8% from 2015 for MD/DO.
- **Panel:** `PARQUET_DIR/panel/panel_brand.parquet` (P10). The data dictionary is in DATA.md §13.

## 3. Sample

1. **Diabetes-prescriber panel (P10):**
   - individual prescribers with a prescribing specialty;
   - active in Part D ≥ 3 years;
   - ≥ 2 years with ≥ 11 non-GLP-1 antidiabetic claims.

   That is 427,286 NPIs, holding 97.5% of GLP-1 claims.
2. **Primary sample:** physicians (endocrinology, primary care MD/DO, cardiology, nephrology, other MD/DO), 280,610 NPIs. NPs and PAs are excluded, because their payments are unobserved before PY2021 (D10); they form the H7 sample.
3. **Prescriber-years outside a physician's Part D span are dropped (D25).** That means years before the first or after the last by-Provider row, plus internal gap years. They are not coded as 0 or as suppressed.
4. **Brand-specific exclusions:**
   - Physicians whose first promotional contact for B falls in PY2013–2014 are already treated and are excluded from B's analysis. PY2013 covers August–December only, so a 2015 cohort member has at least 17 months without a recorded B payment. Payments before August 2013 are unobservable, a stated limitation.
   - **Cohort eligibility:** a cohort g must have at least one full Part D year of the brand before g (g ≥ first Part D year + 1). That gives:
     - Victoza: g ≥ 2015 (launched 2010);
     - Trulicity: g ≥ 2015 (Part D from 2014);
     - Ozempic: g ≥ 2019 (Part D from 2018, D7).

     Ozempic contacts in 2017–2018 are launch-period contacts and are excluded as already treated.
5. **Sensitivity (D24):** the diabetes-prescriber filter is re-applied using only years before g.

## 4. Exposure and timing

- **Exposure (D22):** B is treated from the program year g of the physician's first promotional contact naming B: any amount, any promotional nature (D16), with full credit when several products are named (D8). Non-promotional natures (royalties, grants, acquisitions…) do not start exposure. Exposure is absorbing.
- **Not yet treated by 2024:** physicians first contacted in 2025 are coded never-treated within the 2013–2024 outcome window.
- **Year 0 (D-1)** is partly treated, because payments arrive during the year. It is reported separately. A sensitivity check moves g to g + 1 when the first payment is in July–December.
- **Co-promotion:** Ozempic and Rybelsus are named together on 1.5M records (P09), so the Ozempic exposure partly measures semaglutide promotion. The molecule-level exposure (any semaglutide brand) is a pre-specified sensitivity check.

## 5. Outcomes

| Role | Outcome | Notes |
|---|---|---|
| **Primary** | Y = 1{claims of B ≥ 11 in year t} (`status = observed`) | Fully observed (D14). 0 for suppressed (0–10), zero_known and pre_launch cells |
| Secondary (H6) | 30-day fills of B, Poisson / PPML | Suppressed cells set to 0, to min(5, cap) and to cap (`supp_cap` ≤ 10), reported as bounds (D14, D9) |
| Secondary | Same as primary in the high-volume subsample (median ≥ 250 non-GLP-1 diabetes claims a year; 79,355 physicians) | Suppression is lower there but not rare (20–43% of 2024 cells) |
| Secondary (H5) | B's share of the physician's observed GLP-1 claims | Physician-years with ≥ 1 observed GLP-1 row; fractional-response DiD (P15) |
| Negative control | Statin claims (PPML) and 1{statin claims ≥ 11} | Should not respond (P17) |

## 6. Estimation

- **Primary estimator:** Callaway & Sant'Anna ATT(g, t), doubly robust (`est_method = "dr"`), not-yet-treated control group, varying base period, no anticipation. It is estimated separately for each primary brand with the Python `differences` package (0.3.0), then aggregated to event time e = −5…+3 and to the overall ATT over e = 0…3.
- **Covariates** (base period g − 1):
  - specialty group;
  - Census region;
  - log(1 + non-GLP-1 diabetes claims);
  - log(1 + total Part D claims);
  - 1{any observed claims of another GLP-1 brand};
  - urban/rural (RUCA < 4).

  Comparing within specialty × state is a sensitivity check (state dummies replace region).
- **Inference:** multiplier bootstrap (999 iterations, seed 20261023), clustered by group practice (`org_pac_id`; physicians with no practice in the DAC are their own cluster, D-3), plus simultaneous confidence bands for the event-time estimates.
- **Cross-checks** (reported side by side; agreement is judged in §10):
  1. R `did` 2.5.1 (same specification);
  2. Sun & Abraham interaction-weighted event study (pyfixest), with NPI and specialty × region × year fixed effects;
  3. the Borusyak–Jaravel–Spiess imputation estimator (pyfixest `did2s`), also used for a stacked pooled estimate across the three brands with brand × year effects;
  4. two-way fixed effects, as a Goodman-Bacon diagnostic only.
- **Control pool (P08):** never-paid physicians are a small, selected group, so not-yet-treated controls are primary and never-treated controls secondary. The number of control units per cohort and event time is reported.
- **Matched design (P14):** treated physicians are matched to controls on pre-period (g − 2, g − 1) brand-B status, GLP-1 class claims and their growth, diabetes load, total volume and specialty × state (coarsened exact matching; balance target |standardised difference| < 0.1). CS is re-estimated on the matched sample.

## 7. Multiple comparisons

- **Primary family:** the three brand-specific overall ATTs (H1), with Holm adjustment at α = 0.05. The stacked pooled estimate is a summary, not a separate test.
- **Secondary family:** H2–H7, with Holm adjustment across the six. P19's subgroup comparisons get their own Holm family.
- **Falsification and sensitivity tests are not adjusted for multiplicity**, which is the conservative choice when looking for failures.

## 8. Smallest effect size of interest and equivalence

- **Thresholds:** SESOI = 2 percentage points on the primary outcome (overall ATT over e = 0–3), and 10% for the proportional fills ATT (H6).
- **"Null" means equivalence,** not merely failing to reject. It requires the 90% CI to lie within ±SESOI (two one-sided tests).
- **Effects below the SESOI that are statistically significant** are reported as "statistically detectable but small".

## 9. Robustness, falsification and sensitivity (pre-specified)

**Falsification (P17)**, reported pass/fail. "Fail" means the 95% CI excludes 0 *and* the point estimate is at least half the corresponding primary estimate in the effect's direction.
1. **Pre-trends:**
   - a joint Wald test on event times e ≤ −2;
   - HonestDiD relative-magnitudes bounds, with the breakdown value M̄* reported;
   - a pre-trend test on a second outcome, 1{any observed claims of other GLP-1 brands}. For recently launched brands, B's own pre-period is mechanically near zero.
2. **Negative-control outcome:** statin prescribing on GLP-1 brand exposure.
3. **Negative-control exposure (D20):** first oral-anticoagulant promotional payment on the primary GLP-1 outcome (any GLP-1 brand ≥ 11 claims). Inhaled-respiratory payments are a secondary version.
4. **Placebo timing:** g shifted 1 and 2 years earlier, using pre-treatment years only.
5. **Placebo brand:** Trulicity exposure on the Ozempic outcome, and the reverse. The expected effect is ≤ 0.

**Sensitivity (P18)**, all shown in one forest plot:
- suppression bounds (0 / 5 / cap);
- physicians never suppressed for B;
- g + 1 for second-half first payments (D-1);
- controls only from practices with no B-paid member (D-3);
- manufacturer-level exposure (D-2, D21);
- molecule-level exposure;
- dropping the top 1% of payees by cumulative GLP-1 dollars;
- the D8 first-listed rule;
- never-treated controls;
- the pre-period diabetes-load filter (D24);
- excluding the 2020 COVID year from base periods;
- state instead of region in the covariates;
- outcomes claims, beneficiaries and cost;
- PPML vs log(1 + fills) (D9).

**Heterogeneity (P19):** specialty group, Census region and urban/rural, Holm-adjusted, with ≥ 11 physicians in every reported cell.

## 10. Interpretation rules (fixed in advance)

| Pattern | Reported as |
|---|---|
| Holm-significant positive ATT ≥ SESOI for ≥ 2 of 3 brands; pre-trend test not rejected **and** HonestDiD M̄* ≥ 0.5; negative controls and placebos pass; matched-design estimate ≥ half the primary and still significant | **"Consistent with payments influencing brand choice, after accounting for targeting and pre-trends"** (never "caused") |
| Positive ATT but pre-trends rising before g, or M̄* < 0.5, or the matched estimate falls below half / loses significance | **"Explained at least partly by targeting of already-rising prescribers"** |
| The negative-control exposure gives an effect of similar size | **"A general 'paid-physician' difference, not brand-specific influence"** |
| 90% CI within ±SESOI for all brands | **"No meaningful association"** (equivalence) |
| Anything else (e.g. 1 of 3 brands, mixed tests) | **"Mixed / inconclusive"**, with the specific failures listed |

Estimators "agree" when the cross-check point estimates lie within the primary 95% CI and have the same sign. Disagreement is reported, not resolved by choosing an estimator.

Every headline sentence gets a matching "what this doesn't mean" sentence. Prescribing more GLP-1s is not evidence of inappropriate prescribing, and nothing here concerns obesity prescribing or the commercial market (CLAUDE.md, docs/literature.md).

## 11. What has been seen before registration

Descriptive outputs only (P03–P11; DATA.md §6–14):
- payment totals, brand and payment-type distributions, concentration, state and specialty payment rates;
- Part D spending and suppression shares by brand × year, not split by exposure;
- cohort sizes by first-payment year;
- linkage overlap: 78–88% of GLP-1 fills come from physicians paid for a GLP-1 in *some* year.

**No outcome has been compared between exposed and unexposed prescribers around the time of exposure.**

## 12. Judgement calls (approved 2026-10-23, all as the draft choice)

| # | Call | Registered choice | Alternative not taken |
|---|---|---|---|
| J1 | Primary outcome | Binary ≥ 11 claims (D14); fills via PPML secondary | PPML fills primary (D9 "leaning"), binary secondary |
| J2 | Primary test structure | Three brand-specific ATTs, Holm; pooled stacked estimate as summary | One pooled estimate as the single primary test |
| J3 | Cohort eligibility | g ≥ first Part D year + 1 (keeps Ozempic 2019, D7) | g ≥ + 2 (two post-launch pre-years; drops Ozempic 2019 and Trulicity 2015) |
| J4 | Aggregation window | e = 0–3, year 0 also reported separately | e = 1–3 (excluding the partly treated year 0) |
| J5 | SESOI | 2 percentage points (binary); 10% (fills) | 1 pp / 5% (stricter), or relative to the base rate |
| J6 | Implementation | Python `differences` primary, R `did` cross-check (D4) | R `did` primary |

## 13. Deviations

Each deviation after locking gets a dated entry: what changed, why, and whether results had been seen.

**DEV-1 (2026-10-23, before any estimate was seen): primary implementation moved from Python `differences` to R `did` 2.5.1 (J6 alternative).**
- **What happened:** on the first test fits (a 20% Ozempic sample, inspected only for errors), `differences` 0.3.0 failed three ways under pandas 3 / numpy 2:
  1. clustered inference crashes because the cluster column is passed as a Series;
  2. the parallel multiplier bootstrap builds a mis-shaped mask;
  3. a repeat fit on identical data failed with an empty influence-function stack.
- **Change:** the estimator is now R `did::att_gt`, the reference implementation by the method's authors. Everything else stays as registered: doubly robust, not-yet-treated controls, varying base period, the same covariates, multiplier bootstrap clustered by practice.
- **Why it is an improvement:** R `did` also provides the influence functions that HonestDiD and the joint pre-trend test need.
- **Cross-checks:** the Python ones are now the Sun & Abraham and imputation (did2s) estimators in pyfixest. R `did` with never-treated controls stays as a sensitivity.
- **Unbalanced panel:** prescriber-years dropped under D25 make the panel unbalanced. It is estimated with `allow_unbalanced_panel = TRUE`; a balanced-panel subsample (physicians observed in every year of the brand's window) is added as a sensitivity.

**DEV-2 (2026-10-23, before any estimate was seen): covariate coding for estimability.**
- **What happened:** test fits gave singular design matrices in many group-time cells. In the unbalanced-panel (repeated cross-section) DR estimator, outcome regressions are also fitted within each treated cohort, and small cohorts lacked some covariate levels.
- **Change 1, specialty:** specialty is the physician's modal specialty group (the one that defines the sample, P10). It is time-invariant, not the year-specific label, which occasionally reads NP or other for a physician.
- **Change 2, territories:** physicians practising in US territories (PR, VI, GU, other non-state codes) in any year are excluded, because they have no Census region. That is 5,233 physicians in the Ozempic frame.
- **No other change.**

**DEV-3 (2026-10-23, after the primary estimates were seen): HonestDiD computed from a universal-base-period event study.**
- **The problem:** the registered specification uses a varying base period. Its pre-treatment estimates are then year-on-year changes, not deviations from a common reference year. HonestDiD's relative-magnitudes bounds assume the latter, as the `did` and HonestDiD authors recommend (`base_period = "universal"`).
- **What was seen:** the first HonestDiD numbers, computed from the varying-base estimates, were seen. They are discarded as invalid, not reported.
- **Change:** CS is re-estimated with `base_period = "universal"` (everything else unchanged), and HonestDiD and the event-study chart use those estimates.
- **What stays registered:** post-treatment ATT(g, t), and hence every primary ATT, are identical under both base periods. The joint pre-trend Wald test is reported for both.

**Exploratory (not registered), added 2026-10-23:** CS without covariates. The fixed-effects cross-checks (imputation, Sun & Abraham, TWFE) gave estimates about twice the primary ones, and this run shows how much of the gap the covariate adjustment explains. It does not replace the primary estimate (§10: disagreement is reported, not resolved by choosing an estimator).

**DEV-3 addendum (2026-10-23): HonestDiD window and supplementary bound.**
- **The problem:** with all available pre-periods (up to e = −7), the relative-magnitudes C-LF solver returned no interval (NA) for most M̄ values for Trulicity and Ozempic. A breakdown value computed from those rows would have been spurious.
- **Window:** HonestDiD now uses pre-periods e = −4…−2 (e = −1 is the reference), the common practice for short, well-estimated pre-windows.
- **Breakdown rule:** the breakdown is reported only when every row solves.
- **Supplementary:** the smoothness restriction (ΔSD), whose M = 0 case lets the estimated pre-trend continue linearly after treatment, is reported alongside. Rising pre-trends were seen for all three brands, and the natural question is whether the post-payment change exceeds a continuation of that trend.

**DEV-4 (2026-10-23, after the P13 estimates were seen, before any matched-design estimate): P14 implementation and a trajectory-matching sensitivity.** Approved by the user before P14 ran (CLAUDE.md D26).
- **Why:** P13 found rising pre-trends for all three brands, so the matched design (§6) is now the decisive targeting test. §6 names the matching variables but not the bins or the estimator details, so these are fixed here before any post-payment outcome on the matched sample is computed.
- **Matching (registered spec, CEM):** within each cohort g, every physician first paid in g is matched to physicians not yet paid by g (first paid after g, or never by 2024). Exact strata on:
  - modal specialty group × state in g − 1;
  - brand-B status (≥ 11 claims) in g − 2 and in g − 1;
  - GLP-1 class claims in g − 1 (0, 11–49, 50–199, ≥ 200);
  - growth of class claims from g − 2 to g − 1 (≤ −11, −10 to +10, +11 to +49, ≥ +50);
  - non-GLP-1 diabetes claims and total Part D claims in g − 1, each in quartiles of that cohort's candidate pool.

  Physicians must be in Part D in g − 2 and g − 1. Strata without both a treated and a control physician are dropped. Controls get the usual CEM weights (treated count / control count within stratum).
- **Trajectory sensitivity (new):** adds brand-B status in g − 3 and class-claims growth from g − 3 to g − 2 to the strata, so matched physicians share a three-year trajectory (requires Part D presence in g − 3).
- **Estimator:** CS logic on the matched sample: ATT(g, t) is the CEM-weighted difference in the change of the outcome from g − 1 to t, treated minus matched controls still unpaid in t (not-yet-treated; CEM weights recomputed among the controls present in each cell), universal base g − 1. Aggregation as in P13 (cohort-size weights, average of e = 0…3). No covariates are added, because matching replaces the covariate adjustment. Standard errors are clustered by practice from the influence functions, with CEM weights treated as fixed.
- **Pre-trend test on the matched sample:** event times that are matched on are zero by construction (e = −2; also e = −3 in the trajectory spec), so the joint test uses the earlier pre-periods (e ≤ −3, or e ≤ −4).
- **Design-stage rule:** if balance misses the |SMD| < 0.1 target, the bins may be coarsened or refined using pre-period data only, before any post-period estimate is computed, and the change is recorded here.
- **§10 test unchanged:** the matched estimate must be ≥ half the primary and still significant.
