# Project 2: Pharma Payments and the GLP-1 Boom

**Working title:** *Lunch, Speaking Fees and Semaglutide: Industry Payments and GLP-1 Prescribing in Medicare*

**One-sentence pitch:** Link every payment drug makers report to doctors (CMS Open Payments) with what those doctors prescribe in Medicare Part D, and measure whether GLP-1 prescribing (Ozempic, Mounjaro, Rybelsus, Trulicity) rises after a doctor starts receiving GLP-1-related payments, beyond what similar doctors do.

---

## 1. The question

**Primary:** Among Medicare Part D prescribers, does receiving payments tied to a specific GLP-1 brand predict a larger increase in prescribing *that brand* afterwards, compared with similar prescribers who received nothing?

**Secondary:**
- Does it matter what the payment is for (meals vs speaking fees vs consulting)? Is there a dose-response relationship with dollar amount?
- Do payments shift prescribing *between brands* (Ozempic ↔ Mounjaro) more than they grow the class?
- Which specialties and regions get the most GLP-1 payment dollars relative to their diabetes patient load?

**Framing to be careful with:** this is about **association with careful controls**, not proof of corruption. Companies target doctors who already prescribe heavily (reverse causality). The design has to deal with that, and the write-up has to say so plainly.

## 2. Why now

- GLP-1s are the most-discussed drug class of the decade. Medicare Part D spending on semaglutide is now among the largest of any drug, and coverage and pricing fights (Medicare price negotiation, obesity coverage) are in the news constantly.
- Open Payments has been public since 2013, and ProPublica's "Dollars for Docs" made it famous, but **a brand-level, event-study analysis of the GLP-1 era with a public pipeline** is still uncommon.
- Prior research to build on: DeJong et al., *JAMA Internal Medicine* (2016), found that even single industry-sponsored meals were associated with more prescribing of the promoted brand. You'd be testing whether that still holds for the biggest drug class of the 2020s.

## 3. Data sources

| Source | What it gives you | Grain | Where |
|---|---|---|---|
| **Open Payments: General Payments** | Every payment/transfer of value ≥ ~$10–$13 (threshold adjusts yearly): recipient, amount, date, nature (food, speaking, consulting, travel), **associated drug names** | payment, 2013–present (annual program years, published each June) | openpaymentsdata.cms.gov (bulk CSV downloads) |
| **Open Payments: Research & Ownership** | Research payments, physician ownership interests | payment | same |
| **Medicare Part D Prescribers by Provider and Drug** | Claims, 30-day fills, cost and beneficiary counts per prescriber × drug | NPI × drug × year (~2-year lag) | data.cms.gov |
| **Medicare Part D Prescribers by Provider** | Total volume, specialty, patient demographics and risk score | NPI × year | data.cms.gov |
| **NPPES NPI Registry** | Specialty taxonomy, practice address, entity type | NPI | download.cms.gov/nppes |
| **Medicare Physician & Other Practitioners** | Part B volume (proxy for patient panel and diabetes visits) | NPI × year | data.cms.gov |
| **CDC PLACES / BRFSS** | Diabetes and obesity prevalence | county / census tract | cdc.gov/places |
| **Medicare Part D Spending by Drug** | National spending trends (context charts) | drug × year | data.cms.gov |

**Join key:** NPI. Recent Open Payments years include the recipient NPI. Earlier years use a CMS profile ID that you match to NPI using the physician profile supplement file. Document the match rate.

**Important coverage caveat:** Medicare Part D is barred by statute from covering drugs used *only* for weight loss. Wegovy and Zepbound show up only for covered indications (e.g. Wegovy for cardiovascular risk reduction since 2024). So **focus on the diabetes-indicated brands** (Ozempic, Rybelsus, Mounjaro, Trulicity, Victoza) and say clearly that this is *not* a study of obesity prescribing overall.

**Expected size:** Open Payments general file ≈ 10–15M rows/year; Part D by provider and drug ≈ 25M rows/year. Use **DuckDB + Parquet**.

## 4. Building the dataset

1. **Ingest** every Open Payments program year and every Part D year. Store raw files with retrieval dates.
2. **Drug normalisation:** Open Payments lists drugs as free text in up to five name fields ("OZEMPIC", "Ozempic (semaglutide)", "SEMAGLUTIDE"). Build a mapping table to `brand` and `molecule`; unit-test it with known variants. Part D gives brand and generic names directly.
3. **Prescriber panel:** NPI × year × brand, with claims, 30-day fills and beneficiaries; NPI × year × brand payments (count, $, by payment nature); specialty, state and total Part D volume.
4. **Exposure definition:** first year an NPI receives a payment associated with brand B. Control pool: same specialty and state with no GLP-1 payments that year.
5. **Checks:** NPI match rate by year, totals reconciled against CMS's published summary figures, no negative claims, and CMS's privacy suppression (counts < 11 are suppressed in Part D) handled explicitly rather than treated as zeros.

## 5. Method

- **Main design:** staggered **event study** at the prescriber × brand level. Outcome = log(1 + 30-day fills of brand B); event = first year with a brand-B payment.
- **Controls and fixed effects:** prescriber fixed effects, specialty × state × year fixed effects, and pre-period prescribing trajectory (match on prescribing levels and growth in the 2 years before exposure).
- **Estimator:** Callaway & Sant'Anna / Sun & Abraham for staggered timing (`pyfixest`, `differences`, or R `did`).
- **Brand-switching test:** within-prescriber share of GLP-1 fills going to the paid brand vs competing brands. This is the cleanest test, because a doctor's overall diabetes patient load cancels out.
- **Dose-response:** binned payment totals ($0, <$100, $100–$1k, $1k–$10k, >$10k) and payment type.

### Robustness and falsification
- **Pre-trends:** a flat line before the first payment is the main defence against "they targeted rising prescribers".
- **Negative control outcome:** prescribing of an unrelated drug class (e.g. statins) should *not* respond to GLP-1 payments.
- **Negative control exposure:** payments for unrelated drugs shouldn't predict GLP-1 prescribing growth.
- **Suppression sensitivity:** bound results under different assumptions for suppressed cells.
- **Drop the top 1% of payees** (speaker-bureau doctors) and re-run.

### Ethics
- **Do not single out individual doctors** in the article or app, even though the data is public. Aggregate to specialty, state or region. Explain this choice; it makes the work more credible, not less.

## 6. Charts

| # | Chart | Purpose |
|---|---|---|
| **Hero** | **Event study:** % change in paid-brand fills by year relative to first payment, separate lines for meals-only vs speaking/consulting, 95% CIs | The causal-ish centrepiece |
| 2 | Dose-response: fills growth by payment bin, point estimates with intervals | Shows the gradient |
| 3 | Stacked area: Medicare Part D GLP-1 spending by brand over time | Context; shows the scale |
| 4 | Stacked area or bump chart: GLP-1 industry payment dollars by brand and by payment type over time | Who is spending how much, on what |
| 5 | Brand share within prescriber before/after, paired dumbbells (paid vs unpaid doctors) | The switching result |
| 6 | Hex-tile map: GLP-1 payment dollars per diabetic Medicare beneficiary by state | Normalised geography |
| 7 | Lorenz curve: share of payment dollars going to the top X% of recipients | Shows how concentrated payments are |

**Interactive:** an explorer by specialty and state (not individual doctor) showing payments vs prescribing trends, with a brand selector.

## 7. Repo skeleton

```
pharma-payments-glp1/
  README.md
  DATA.md                  # sources, NPI match rates, suppression rules, drug-name mapping
  Makefile
  pyproject.toml, uv.lock
  src/ppg/
    ingest/open_payments.py, partd.py, nppes.py, places.py
    build/drug_map.py, panel.py, exposure.py
    models/event_study.py, switching.py, dose_response.py, falsification.py
    viz/theme.py, figures.py
  data/reference/drug_name_map.csv   # versioned, reviewed by hand
  tests/                   # drug-map variants, totals vs CMS summaries, pinned estimates
  notebooks/
  report/index.qmd
  app/
```

## 8. Milestones

| Week | Deliverable |
|---|---|
| 1 | Ingest Open Payments + Part D + NPPES to Parquet; reconcile totals with CMS summaries |
| 2 | Drug-name mapping + tests; NPI linkage with documented match rates |
| 3 | Prescriber × brand × year panel; descriptive charts 3, 4, 6, 7 |
| 4 | Event study + switching analysis; hero chart v1 |
| 5 | Falsification tests, dose-response, suppression sensitivity |
| 6 | Article + specialty/state explorer |
| 7 | Review by a clinician or pharmacist; publish |

## 9. Distribution
- Article with a plain-language summary at the top ("What we found / what it doesn't mean").
- Health-policy outlets and newsletters (STAT, KFF Health News, and similar) sometimes pick up independent analyses with clean methods. Send a short pitch with the hero chart.
- Release the cleaned drug-name mapping table separately; other researchers will reuse it, which is a good source of citations.
- Hacker News ("Show HN") and r/medicine / r/pharmacy (read the subreddit rules first).

## 10. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Reverse causality (companies target high prescribers) | Pre-trend matching, brand-switching design, negative controls; careful language |
| Part D data lags ~2 years | Analysis ends at the latest available year; payments data fills in the more recent context |
| Suppression of small counts | Explicit handling + sensitivity bounds |
| Free-text drug names in Open Payments | Mapping table with tests and manual review of unmapped names above a $ threshold |
| Obesity drugs largely absent from Part D | State the scope clearly; don't generalise to the obesity market |

## 11. Stretch goals
- Add commercial-market context using public IQVIA or company 10-K figures (no microdata, just scale).
- Look at telehealth and compounding-pharmacy prescribers (an emerging GLP-1 story) if any public data supports it.
- Extend the same pipeline to another class (SGLT2 inhibitors, anticoagulants) as a replication.
