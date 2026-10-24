# Results log (P13–P19)

Internal running record of model results against [PREREGISTRATION.md](../PREREGISTRATION.md) (`prereg-v1`, deviations DEV-1 to DEV-7). Every number comes from `report/qa/` (event study: [event_study.json](../report/qa/event_study.json), [event_study_estimates.csv](../report/qa/event_study_estimates.csv), [event_study_event_time.csv](../report/qa/event_study_event_time.csv)). The article (P22) words these cautiously. This file states them plainly.

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

## P15: Brand switching (2026-10-23)

Specification: H5, [PREREGISTRATION.md](../PREREGISTRATION.md) §5 and DEV-6. Numbers: [switching.json](../report/qa/switching.json), [switching_estimates.csv](../report/qa/switching_estimates.csv).

**Outcome:** the brand's share of the physician's observed GLP-1 claims.

**Sample:** physicians with GLP-1 claims in both the base year and the outcome year. This is switching among physicians who already prescribe GLP-1s. Starting to prescribe GLP-1s at all is P13's outcome.

**Mounjaro** is measured relative to launch: cohorts from 2022, base year 2021, when its share was 0 for everyone.

### Own-brand share (ATT, event years 0–3, percentage points)

| Brand | **Linear DR (covariates at g − 1)** | + base-year share | Matched (CEM) | **Fractional, matched (registered form)** | Fractional, unadjusted |
|---|---|---|---|---|---|
| Trulicity | **+4.1** (3.5 to 4.8) | +4.3 | +4.8 (4.1 to 5.4) | **+3.9** (−0.2 to 8.0) | +0.6 (−1.8 to 3.0) |
| Victoza | **−4.8** (−6.1 to −3.4) | −4.5 | −4.1 (−5.7 to −2.5) | **−4.1** (−6.2 to −1.9) | −5.0 (−6.5 to −3.4) |
| Ozempic | **+3.0** (2.5 to 3.5) | +3.5 | +3.5 (3.0 to 4.0) | **+3.1** (−2.1 to 8.2) | −0.9 (−4.8 to 2.9) |
| Mounjaro | **+5.3** (5.0 to 5.6) | +5.3 | +4.5 (4.2 to 4.8) | **+5.7** (0.9 to 10.4)¹ | −0.4 (−4.3 to 3.5)¹ |

¹ The 2023–2024 cohorts only. The launch cohort's base share is 0, so its log-odds is undefined.

**Trulicity, Ozempic and Mounjaro:**
- **The paid brand's share rises by 3–5 pp** under the linear estimators, precisely, and robust to matching and to adjusting for the base-year share.
- **Under the registered log-odds form, the matched point estimates are about the same** (+3.9, +3.1, +5.7). But they are far less precise, because shares near zero in the base year amplify noise on the log-odds scale. Only Mounjaro's interval excludes 0.
- **The unadjusted fractional version is near 0.** It has neither matching nor covariates, and paid physicians start with different brand mixes.

**Victoza:** its share **falls** after a Victoza payment under every estimator, although P(≥ 11 Victoza claims) rises (P13/P14).

### Pre-trends (own share)

| Brand | Primary, joint pre-test p | Matched pre-test p | Pattern before payment |
|---|---|---|---|
| Trulicity | 0.32 | 0.007 | Matched paid physicians' Trulicity share was slightly *falling* (+2.6 → 0 pp from e = −5 to −1): opposite in sign to the effect |
| Victoza | < 0.001 | 0.27 | Share already falling faster among paid physicians |
| Ozempic | 0.009 | 0.19 | Mildly rising (about 0.5 pp a year) without matching; flat with matching |
| Mounjaro | 0.53 (one cell) | — | Pre-launch |

### Where the share comes from (each brand's share; linear DR + base-year share)

| Paid for | Ozempic | Trulicity | Victoza | Mounjaro | Rybelsus | Other |
|---|---|---|---|---|---|---|
| Trulicity | +0.7 | **+4.3** | **−5.6** | +0.4 | +0.2 | −0.2 |
| Victoza | +1.4 | +2.7 | **−4.5** | 0.0 | +0.1 | +0.3 |
| Ozempic | **+3.5** | **−5.0** | −2.7 | +1.5 | +1.8 | +0.6 |
| Mounjaro | −1.9 | **−4.8** | −0.6 | **+5.3** | +1.0 | +0.4 |

- **Trulicity's gain comes out of Victoza**, its main competitor in 2015–2018.
- **Ozempic's gain comes out of Trulicity**, and out of Novo's own Victoza.
- **Mounjaro's gain comes mostly out of Lilly's own Trulicity**, and less from Ozempic.

**Why the base-year adjustment is needed:** without it, Mounjaro exposure appears to *raise* Victoza's share (+2.9). Mounjaro-paid physicians started with less Victoza (8.3% vs 12.2%). Victoza collapsed after 2021, so physicians with more of it lost more in level terms. That is mean reversion, not switching.

### Class growth vs switching (Part D claims of the paid brand per physician-year, all physicians in Part D in both years)

| Brand | ATT on brand claims | Class growth at pre-payment share | Switching (share shift) | Switching share of the total |
|---|---|---|---|---|
| Trulicity | +4.6 | +2.0 | +2.6 | 56% |
| Ozempic | +8.1 | +3.4 | +4.7 | 58% |
| Victoza | +1.9 | +4.3 | −2.4 | share lost |
| Mounjaro | +13.2 | +0.4 | +12.8 | (launch brand: by construction almost all share shift) |

**Decomposition:** brand claims = pre-payment share × class claims + (brand claims − pre-payment share × class claims). Both parts are estimated with the same panel-form DR.

**For the established brands, a bit over half of the extra claims after payment come from switching between brands**, and the rest from paid physicians prescribing more GLP-1s overall.

### Reading

The brief calls this the cleanest test, because the physician's overall diabetes caseload cancels out of a share.

**It supports a brand-specific association for Trulicity, Ozempic and Mounjaro:**
- after a first payment for B, B's share of the physician's GLP-1 prescribing rises by 3–5 pp more than among comparable not-yet-paid physicians;
- the share comes from B's direct competitors.

**Victoza is the exception.** Its payments came while Novo Nordisk was moving the market from Victoza to Ozempic. Paid physicians expanded GLP-1 use but kept less of it on Victoza.

**What this doesn't mean:**
- A share shift after a payment is not proof the payment caused it. Reps also call on physicians when a brand gains formulary or guideline position.
- Under the registered log-odds form, the evidence is weak (CIs include 0) for Trulicity and Ozempic.
- Nothing here concerns individual physicians or whether the switches were clinically appropriate.

**Holm adjustment:** H5 joins the secondary-family Holm adjustment (H2–H7) once P16 and P19 are in.

## P16: Dose-response and payment type (2026-10-23)

Specification: H4 and H2, [PREREGISTRATION.md](../PREREGISTRATION.md) §1 and DEV-7. Numbers: [dose_response.json](../report/qa/dose_response.json), [dose_response.csv](../report/qa/dose_response.csv).

Each group of paid physicians is estimated as its own treated group, against the same not-yet-paid controls. Each gets the panel-form CS-DR and a matched (CEM) version.

**Who is in the event study:**
- **Newly paid physicians are meal recipients.** In their first payment year, 91–97% received under $100 for the brand, and only 13–83 per brand received $1k or more.
- **Speakers are almost absent.** Most were first paid in 2013–2014, so they are excluded as already treated (prereg §3).

**These results describe physicians whose first contact was a sponsored meal**, not the speaker bureau.

### ATT over event years 0–3 (pp, Pr(≥ 11 claims of the brand)); matched in brackets

| Brand | Group | Physicians | ATT (95% CI) | Matched | Pre-period gap at e = −3 |
|---|---|---|---|---|---|
| Trulicity | < $100 in first year | 65,407 | **+11.9** (11.5 to 12.2) | [+12.3] | −4.9 |
| Trulicity | ≥ $100 in first year | 2,188 | **+16.8** (15.3 to 18.3) | [+18.3] | −5.1 |
| Victoza | < $100 | 20,603 | **+5.2** (4.8 to 5.7) | [+6.4] | −1.8 |
| Victoza | $100–1k | 1,304 | **+9.6** (7.9 to 11.3) | [+11.1] | −1.8 |
| Victoza | ≥ $1k | 104 | +2.5 (−3.6 to 8.6) | [+4.7] | −0.5 |
| Ozempic | < $100 | 44,295 | **+13.2** (12.6 to 13.7) | [+14.1] | −5.3 |
| Ozempic | ≥ $100 | 3,832 | **+19.1** (17.9 to 20.4) | [+20.2] | −4.7 |

**Bin merging:** for Trulicity and Ozempic, the $1k–10k and > $10k bins had fewer than 100 physicians each, so they merged into "≥ $100" under the DEV-7 rule.

**Contacts in the first payment year:**

| Brand | 1 contact | 2–3 contacts | ≥ 4 contacts |
|---|---|---|---|
| Trulicity | **+9.1** | **+13.2** | **+18.3** |
| Victoza | **+3.7** | **+6.9** | **+11.1** |
| Ozempic | **+11.0** | **+14.6** | **+21.3** |

- **Matched estimates** are within 2 pp of these and show the same gradient.
- **Pre-period gap at e = −3** (unmatched, relative to e = −1):
  - Trulicity: −4.6 / −5.6 / −4.8;
  - Victoza: −1.5 / −1.8 / −2.8;
  - Ozempic: −4.5 / −6.0 / −7.0.

**Cumulative dollars over years 0–3** (cohorts ≤ 2021; partly an outcome):

| Brand | < $100 | $100–1k | ≥ $1k |
|---|---|---|---|
| Trulicity | +9.5 | +19.9 | +19.8 (n = 160) |
| Victoza | +4.3 | +12.9 | +6.7 (n = 164) |
| Ozempic | +8.8 | +20.7 | +35.6 (n = 111) |

**Spline on cumulative dollars** (regression-adjusted unit effects, natural cubic spline): the curve rises steadily with log dollars.

| Brand | 10th percentile | Median | 90th percentile |
|---|---|---|---|
| Trulicity | $7: +4.9 | $39: +11.4 | $174: +20.9 |
| Victoza | $6: +2.3 | $21: +3.5 | $122: +11.3 |
| Ozempic | $11: +5.0 | $52: +11.0 | $228: +23.5 |

**Payment type over years 0–1 (H2 as far as estimable):**

| Brand | Meals only | Travel, education or other (no fee) | Speaker or consulting fee |
|---|---|---|---|
| Trulicity | +12.0 | +12.9 (n = 72) | +17.2 (n = 71) |
| Victoza | +5.2 | +11.7 (n = 899) | +2.3 (n = 109) |
| Ozempic | +13.6 | +17.2 (n = 784) | +23.6 (n = 80) |

- **Speaker/consulting groups are 71–109 physicians**, with CIs about ±8–10 pp.
- **H2 ordering (fees > meals):** it holds in point estimates for Trulicity and Ozempic, but the CIs overlap meals-only. It does not hold for Victoza.

### Reading

**There is a consistent gradient in point estimates:**
- more first-year contacts and more dollars go with larger increases in prescribing the paid brand;
- with ≥ 4 contacts, about twice the increase seen with one contact.

The gradient survives matching on the pre-payment trajectory.

**It is not a dose-response:**
1. **Reps choose how often to visit, and they visit physicians they expect to adopt.** For Ozempic, higher-contact groups were rising faster before payment (−4.5 vs −7.0 pp at e = −3).
2. **Contacts and dollars within year g can follow the first prescriptions in the same year.**
3. **Cumulative dollars after year 0 respond to prescribing.** Speaker invitations go to adopters.

The first-year-dollar bins, the least contaminated measure, show the gradient from < $100 to ≥ $100 (+4.9, +4.4 and +5.9 pp for Trulicity, Victoza and Ozempic). Their pre-period gaps are near-identical across bins, which is the more informative result.

**What this doesn't mean:**
- It does not show that a larger meal causes more prescribing, or that speaker fees work better than meals. The speaker groups are too small, and too selected, to say.
- It does not describe any individual physician.
