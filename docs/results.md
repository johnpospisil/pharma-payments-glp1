# Results log (P13–P19)

Internal running record of model results against [PREREGISTRATION.md](../PREREGISTRATION.md) (`prereg-v1`, deviations DEV-1 to DEV-5). Every number comes from `report/qa/` (event study: [event_study.json](../report/qa/event_study.json), [event_study_estimates.csv](../report/qa/event_study_estimates.csv), [event_study_event_time.csv](../report/qa/event_study_event_time.csv)). The article (P22) words these cautiously. This file states them plainly.

## P13: Primary event study (2026-10-23)

> **Correction (P14, DEV-5):** the P13 primary below was fitted by R `did` in its repeated-cross-section mode. That mode uses each year's own covariates, post-payment years included, and does not difference within physician. The registered panel-form estimator (covariates at g − 1) gives **+12.0 / +5.5 / +13.7 pp** (Trulicity / Victoza / Ozempic). See the P14 section. The P13 numbers are kept here as first reported.

**Specification (prereg §6):**
- **Estimator:** Callaway & Sant'Anna, doubly robust, not-yet-treated controls, varying base period, via R `did` 2.5.1 (DEV-1).
- **Covariates** (base period g − 1): specialty, Census region, log non-GLP-1 diabetes claims, log total claims, any other GLP-1 observed, urban.
- **Inference:** multiplier bootstrap clustered by practice.
- **Outcome:** 1{≥ 11 claims of the brand in the year}.
- **Sample:** physicians, P10 diabetes-prescriber sample. Territories excluded (DEV-2).

### H1 (primary family; Holm across three brands)

| Brand | Physicians (treated) | Pre-period rate, treated (g − 1) | ATT, years 0–3 | 95% CI | Year 0 | Years 1–3 | Holm p |
|---|---|---|---|---|---|---|---|
| Trulicity | 272,735 (67,741) | 5.6% | **+8.4 pp** | +8.0 to +8.8 | +2.1 | +10.5 | < 0.001 |
| Victoza | 218,481 (22,105) | 8.9% | **+1.2 pp** | +0.7 to +1.7 | +0.4 | +1.5 | < 0.001 |
| Ozempic | 239,805 (48,378) | 10.7% | **+7.4 pp** | +6.9 to +7.8 | +3.2 | +8.7 | < 0.001 |

- **Size:** Trulicity and Ozempic exceed the SESOI of 2 pp. Victoza is statistically detectable but below the SESOI ("small").
- **Shape:** effects build over time. Year 0 is partly treated (D-1). Trulicity reaches +12.4 pp and Ozempic +9.7 pp by year 3.

### Pre-trends and sensitivity

| Brand | Joint pre-trend test (varying / universal base) | HonestDiD relative magnitudes: robust up to M̄ | Smoothness bound, linear pre-trend continued (ΔSD, M = 0) |
|---|---|---|---|
| Trulicity | p < 0.001 / p < 0.001 | ≥ 2 (grid maximum) | +6.6 to +8.0 pp |
| Victoza | p = 0.16 / p = 0.046 | 0.25 | −0.2 to +2.0 pp (includes 0) |
| Ozempic | p < 0.001 / p < 0.001 | ≥ 2 (grid maximum) | +4.8 to +6.4 pp |

- **Treated physicians were already rising before their first payment.** In the universal-base event study, Ozempic goes from −4.8 pp at e = −7 to 0 at e = −1, about 0.7 pp a year. Trulicity rises about 0.4 pp a year. These pre-trends are small next to the post-payment change, but with these sample sizes they are clearly non-zero.
- **The post-payment change is far larger than continuing that trend would give.** Allowing the pre-trend to continue linearly (ΔSD, M = 0) still leaves +6.6 to +8.0 pp for Trulicity and +4.8 to +6.4 pp for Ozempic. Ozempic's bound includes 0 only when the trend is allowed to bend by 1 pp a year² (M = 0.01).
- **HonestDiD:** for Trulicity and Ozempic, the average post effect stays significant even if post-period departures from parallel trends are twice the largest pre-period departure. Victoza loses significance at M̄ = 0.5.

### Estimator agreement (prereg §10: disagreement is reported, not resolved)

| Brand | CS primary | CS without covariates (exploratory) | Imputation (BJS) | Sun & Abraham | TWFE (diagnostic) |
|---|---|---|---|---|---|
| Trulicity | +8.4 | +16.8 | +17.0 | +15.6 | +17.7 |
| Victoza | +1.2 | +6.6 | +7.2 | +5.8 | +4.0 |
| Ozempic | +7.4 | +20.0 | +20.3 | +18.7 | +19.7 |

Under the §10 rule, **the cross-checks do not agree with the primary:** their point estimates lie outside its 95% CI. The exploratory CS run without covariates reproduces them almost exactly, so the gap comes from the covariate adjustment, not the estimator.

- **What the covariates do:** the doubly robust adjustment compares paid physicians with unpaid ones who had similar diabetes workload, total volume and **prior prescribing of other GLP-1s** in the year before payment.
- **Why the fixed-effects models come out larger:** they absorb only each physician's level, so growth in GLP-1 prescribing among physicians already inclined to GLP-1s loads onto the treatment.

That is the targeting concern in concrete form: manufacturers pay physicians who are already moving into GLP-1s. The covariate-adjusted primary estimate is the conservative one, and the matched design (P14) is now the key check.

### H2 (payment type), not estimable as registered

Physicians are almost never first reached by a speaker or consulting fee. Among treated physicians, first-year payments were:

| Brand | Meals only | Speaker or consulting | Other |
|---|---|---|---|
| Trulicity | 67,493 | 52 | 50 |
| Victoza | 21,315 | 91 | 605 |
| Ozempic | 47,409 | 62 | 656 |

The speaker/consulting cohorts are too small: every group-time cell is singular. The meals-only estimates are therefore essentially the primary ones (+8.4, +1.3, +7.4 pp). Payment type is analysed through payment bins and types after first exposure in P16 (D23).

### Provisional classification (prereg §10; final after P14 and P17)

For Trulicity and Ozempic, the effect is positive, large and Holm-significant, robust in HonestDiD to M̄ ≥ 2, and survives a linear continuation of the pre-trend. **But the registered rule requires an unrejected pre-trend test, and that test rejects.** The registered reading is therefore, for now: **"explained at least partly by targeting of already-rising prescribers"**.

The sensitivity results show it is not explained *entirely* by a continuing trend: there is a change in level after the first payment beyond the prior trajectory. Victoza's effect is small (below the SESOI) and not robust.

Still to check before any "consistent with influence" wording:
- the matched design (P14), which is the strongest test of targeting here;
- the negative-control exposure and outcome, placebo timing and placebo brand (P17);
- brand switching (P15).

**What this doesn't mean:**
- It does not show that payments cause prescribing.
- It does not show that the extra prescribing is inappropriate. GLP-1s are effective drugs.
- It does not describe any individual physician.

## P14: Matched design (2026-10-23)

Specification: [PREREGISTRATION.md](../PREREGISTRATION.md) §6, DEV-4 and DEV-5. Numbers: [matched.json](../report/qa/matched.json), [matched_estimates.csv](../report/qa/matched_estimates.csv), [matched_balance.csv](../report/qa/matched_balance.csv), [matched_event_time.csv](../report/qa/matched_event_time.csv).

**Design:**
- **Coarsened exact matching within each cohort g.** Physicians first paid in g are matched to physicians not yet paid by g on:
  - specialty × state;
  - brand-B status (≥ 11 claims) in g − 2 and g − 1;
  - GLP-1 class claims (4 bins) and their g − 2 → g − 1 growth (4 bins);
  - diabetes load and total volume (cohort quartiles).
- **Trajectory spec (DEV-4)** adds brand status in g − 3 and g − 3 → g − 2 growth.
- **Estimation:** CS on the matched sample: CEM-weighted, not-yet-treated controls, universal base g − 1, no covariates. SEs are clustered by practice.
- **Unmatched reference:** the same estimator on the same physicians with a single stratum.

### A correction to the primary found on the way (DEV-5)

The matched estimates came out *above* the P13 primary, although matching on lagged brand status is the stricter control for targeting. The cause is in R `did`: with `allow_unbalanced_panel = TRUE` it uses its repeated-cross-section estimator. That estimator takes covariates from each row's own year, so in post-payment years it conditions on post-payment other-GLP-1 prescribing, volume and diabetes load. It also does not difference within physician.

Diagnostic on the balanced Ozempic subsample (169,181 physicians):

| Same data, R `did` | ATT(0–3) |
|---|---|
| Panel mode (covariates at g − 1, as registered) | 0.1258 |
| Cross-section mode (one row removed to trigger it) | 0.0767 |
| No covariates | 0.1933 |

`ppg.models.cs_panel` implements the registered panel estimator cell by cell for the unbalanced panel (DRDID `drdid_panel`). It reproduces R `did` on the balanced sample exactly (0.125829).

### Matched vs unmatched (ATT, event years 0–3, pp)

| Brand | P13 as reported (cross-section form) | **Primary, panel form (DEV-5)** | No covariates | **Matched, registered** | Matched, trajectory |
|---|---|---|---|---|---|
| Trulicity | +8.4 | **+12.0** (11.7 to 12.4) | +16.6 | **+12.5** (12.2 to 12.8) | +13.2 (12.7 to 13.7) |
| Victoza | +1.2 | **+5.5** (5.0 to 5.9) | +6.3 | **+6.6** (6.2 to 7.0) | +6.4 (5.9 to 6.9) |
| Ozempic | +7.4 | **+13.7** (13.2 to 14.2) | +19.8 | **+14.6** (14.1 to 15.1) | +14.5 (14.0 to 15.0) |

| Brand | Treated matched (registered / trajectory) | Max \|SMD\| after | Matched pre-trend p (registered / trajectory) | Matched ÷ primary |
|---|---|---|---|---|
| Trulicity | 94.9% / 51.9% | 0.027 / 0.042 | 0.54 / 0.81 | 1.04 |
| Victoza | 92.5% / 60.3% | 0.029 / 0.034 | 0.18 / 0.92 | 1.22 |
| Ozempic | 93.4% / 88.5% | 0.036 / 0.039 | 0.81 / 0.86 | 1.06 |

- **Coverage of the trajectory spec:** it cannot use the 2015 cohorts of Trulicity and Victoza, because g − 3 = 2012 is before the data begin. Those cohorts are 42% of Trulicity's treated physicians, which explains its lower match share.
- **Pre-trend test on matched samples:** it uses only the pre-periods not matched on (e = −5…−3, or −5…−4), because matched event times are zero by construction. Brand status is persistent, so this test has less independent information than the unmatched one.

### What matching does to the pre-trend

**Unmatched pre-trends are steep.** Using the panel-form primary with a universal base, paid physicians were already rising relative to controls:

| Brand | e = −5 | e = −4 | e = −3 | e = −2 |
|---|---|---|---|---|
| Trulicity | −10.4 | −7.5 | −4.9 | −2.4 |
| Ozempic | −11.0 | −8.0 | −5.2 | −2.8 |
| Victoza | −2.7 | −2.4 | −1.8 | −1.2 |

The joint test rejects for all three (p < 10⁻⁴). This is targeting: manufacturers' first payments go to physicians already moving into the brand class.

**After matching, those pre-periods are flat** (within ±0.4 pp at e = −5…−3), yet the post-payment rise is almost unchanged:

| Brand | Year 0 | Year 3 |
|---|---|---|
| Ozempic | +6.8 pp | +18.9 pp |
| Trulicity | +3.8 pp | +18.1 pp |
| Victoza | +3.5 pp | +7.9 pp |

Matching pulls the no-covariate estimate down to about the covariate-adjusted primary. It does not go further.

**Robustness of the corrected primary:**
- **HonestDiD breakdown M̄:** 1.75 (Trulicity), 1.5 (Victoza), 2.0 (Ozempic).
- **Smoothness bound with the pre-trend continued linearly (M = 0):** +5.2 to +7.1 pp (Trulicity), +2.4 to +4.1 (Victoza), +5.8 to +7.7 (Ozempic).
- **Holm:** all three brands p < 0.001.

### §10 reading after P14 (provisional; final after P17)

**What passes:**
- the matched estimate is ≥ half the primary and significant, for all three brands;
- balance is within target;
- matched pre-trends are flat;
- HonestDiD M̄* ≥ 0.5;
- all three brands are now above the SESOI.

**What still fails:** the registered rule also requires an unrejected pre-trend test for the primary, and it rejects strongly. By the letter of §10 the reading therefore stays **"explained at least partly by targeting of already-rising prescribers"**. It is not changed after the fact.

**What the evidence supports describing:**
- Paid physicians were selected: they were already rising.
- Among physicians on the same pre-payment trajectory (same brand status in the prior two or three years, same class level and growth, same specialty, state, diabetes workload and volume), those who then received a first payment prescribed the brand much more over the next three years.

That gap is what P17's negative controls must test. Matching cannot exclude targeting on information reps have and the data lack, such as a physician about to adopt.

**What this doesn't mean:**
- Matching on observed history does not rule out targeting on unobserved intentions.
- Year 0 partly reflects payments that follow first prescriptions in the same year.
- None of this says the prescribing was inappropriate, or describes any individual physician.
