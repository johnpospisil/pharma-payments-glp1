# Results log (P13–P19)

Internal running record of model results against [PREREGISTRATION.md](../PREREGISTRATION.md) (`prereg-v1`, deviations DEV-1 to DEV-3). Every number comes from `report/qa/` (event study: [event_study.json](../report/qa/event_study.json), [event_study_estimates.csv](../report/qa/event_study_estimates.csv), [event_study_event_time.csv](../report/qa/event_study_event_time.csv)). The article (P22) words these cautiously. This file states them plainly.

## P13: Primary event study (2026-10-23)

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
