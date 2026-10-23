# CLAUDE.md: Pharma Payments and the GLP-1 Boom

Project brief: [02-pharma-payments-glp1.md](02-pharma-payments-glp1.md) (the source of truth for scope, method and charts). Data provenance: `DATA.md` (created in P01).

**Working title:** *Lunch, Speaking Fees and Semaglutide: Industry Payments and GLP-1 Prescribing in Medicare*

**Core claim to test:** Medicare Part D prescribers who start receiving payments tied to a GLP-1 brand then prescribe more of *that brand* than similar prescribers who did not receive payments. The pre-trend must be flat, the effect must show up in brand share as well as volume, and the negative controls must come out null. The finding is **wrong**, or only shows targeting, if paid prescribers were already rising before their first payment, if the effect appears just as strongly for unrelated drugs (statins) or for payments about unrelated drugs, or if it disappears once prescribers are matched on their pre-period trajectory.

---

## How we work

1. The project runs as the numbered prompts below, **one at a time, in order**. The user starts each one by saying "Run P05" (or similar).
2. Act as a senior data scientist: think about identification, selection (companies target high prescribers), measurement error (free-text drug names, suppression) and other explanations, not just code.
3. Run only the prompt asked for. If a prompt turns up something that changes later prompts, say so in the findings and propose an edit to this file. Don't edit the prompt list unless asked.
4. **After each prompt, stop and report** in this format:
   - **Done:** what was built or run (files as links)
   - **Key results:** the numbers that matter, with units and years
   - **Deliverables for you:** the files, charts, tables or links worth opening, one line each on why (the prompt's "Deliverables" line is the minimum)
   - **Data issues / surprises:** anything odd, and how it was handled
   - **Questions before the next prompt:** decisions only the user can make (0–3), each with a recommended answer
   - **Next:** the next prompt ID and anything to check before running it (e.g. "mount Drive3")
5. When a prompt is finished and its findings are approved, tick its box and add a dated one-line result next to it. When every prompt in a phase is ticked, add "✅ DONE" to the phase heading. Record decisions in the Decisions table.
6. **Pre-registration (P12) is locked before any model compares exposed and unexposed prescribers after exposure.** Descriptive work before P12 must not compute post-payment prescribing contrasts. Later changes go in a dated "Deviations" section of `PREREGISTRATION.md`, never as silent edits.

## Working conventions

- **Environment:** `uv` project venv, Python 3.12, locked in `uv.lock`. Package `ppg`, src layout as in brief §7. R is used only to cross-check estimators: Homebrew R 4.6.1 (arm64) at `/opt/homebrew/bin/Rscript`, with `did` 2.5.1, `fixest` 0.14.2, `HonestDiD` 0.2.8, `arrow` 25.0.1 (`/usr/local/bin/R` is an old Intel build that won't run; `/opt/homebrew/bin` comes first on PATH). Quarto 1.10.19 at `/usr/local/bin/quarto`.
- **Dataframes:** DuckDB + Parquet for anything over 1M rows, with polars for transforms. Use pandas only where a library requires it. Never load a full Open Payments or Part D year into memory; push the work into DuckDB.
- **Storage (decided):** raw downloads (zips/CSVs, read once in order) go on **Drive3** at `PPG_RAW_DIR` (default `/Volumes/Drive3/ppg/raw`). Working Parquet and DuckDB files go on the **internal SSD** at `PPG_DATA_DIR` (default `./data`, git-ignored). Paths come from `.env`; never hard-code them. Ingest needs Drive3 mounted (`make check-env` checks this); everything after ingest must run without it.
- **Raw is immutable:** `raw/` is written only by `ppg.ingest.*`, with the retrieval date and SHA-256 logged in `data/reference/retrievals.csv`. Cleaning adds new columns and never overwrites source values.
- **Caching:** downloaders are idempotent (skip files already present, retry with backoff, log what was fetched). Re-running `make data` must be cheap.
- **Never commit data** except small reviewed reference files in `data/reference/` (drug map, taxonomy crosswalk, sources, CMS summary totals).
- **Tests:** `pytest`. Every cleaning rule, the drug map, the linkage and every published number get a test. Headline estimates are pinned in `tests/test_pinned_estimates.py`. Every number in the article is read from `report/qa/*.json`, never typed by hand.
- **Reproducibility:** fixed seeds; `make all` rebuilds everything from raw; figures come from code only.
- **Suppression:** Part D leaves out prescriber × drug rows with fewer than 11 claims. A missing row means "0–10 claims", **not zero**. Keep a `suppressed` flag in the panel and never fill with 0 silently.
- **Ethics (non-negotiable):** never name, map, rank or otherwise expose individual prescribers in the article, app, figures, social posts or released data. Aggregates shown publicly need **≥ 11 prescribers per cell**. Code may use NPIs internally; released panels use hashed IDs or are aggregated.
- **Language:** "associated with", "consistent with", "after accounting for…". Never "caused" or "bought". Every headline sentence gets a matching "what this doesn't mean" sentence.
- **Scope:** diabetes-indicated GLP-1s in Medicare Part D. This is **not** a study of obesity prescribing (Part D excludes weight-loss-only use).

## Decisions

**Audience and pace:** portfolio piece + social media (HN, Reddit, LinkedIn, Bluesky). No journalist outreach. Own pace: the brief's weekly milestones set the order only, not a schedule. Prefer the simplest approach that is methodologically sound.

| # | Decision | Status |
|---|---|---|
| D1 | Storage | **Decided 2026-10-22:** raw on Drive3, Parquet/DuckDB on internal SSD |
| D2 | Audience / distribution | **Decided 2026-10-22:** portfolio + socials; no journalist pitch |
| D3 | Expert review | **Decided 2026-10-22:** AI red-team (health economist, pharmacist, data journalist) in P24, plus a review checklist the user can send to a real reviewer later |
| D4 | Environment | **Decided 2026-10-22:** uv venv, Python 3.12; R only for cross-checks |
| D5 | Publication | Quarto article + static explorer on GitHub Pages. Repo stays **private** until launch; Pages turns on when it goes public (free plan), as in stackoverflow-decline |
| D6 | Year range | **Decided 2026-10-22:** outcomes 2013–2024; payments PY2013–2024 linked (PY2025 descriptive only); event cohorts first-paid 2015–2024 (see DATA.md §4) |
| D10 | NPs / PAs | **Decided 2026-10-22:** excluded from the primary event study (pre-2021 payments unobserved); kept in descriptive work; secondary analysis treats 2021 as washout and uses cohorts first-paid 2022+ |
| D7 | Brands in the primary analysis | Open: decided in P12. Mounjaro (launched 2022) and Ozempic (2018) have no pre-launch prescribing, so their pre-trends can't be tested the usual way (see P12) |
| D8 | Payments that name several drugs | Open: allocation rule proposed in P09 |
| D9 | Outcome scale | **Leaning (P02, 2026-10-22):** Poisson/PPML proportional ATT primary (Wooldridge 2023), log(1+fills) as robustness (Chen & Roth 2024). Locked in P12 |
| D12 | Non-positive payments | **Decided 2026-10-22:** the 871 records with amount ≤ $0 are dropped from dollar totals but kept as contacts (count of interactions) in P09 |
| D13 | Raw Part D / Part B CSVs | **Decided 2026-10-22:** kept on Drive3 as the immutable raw copy (no zip exists) |
| D11 | Positioning | **Decided 2026-10-22:** the article names Khunte et al. 2026 (*Mayo Clin Proc*, cross-sectional) as the baseline; our headline is the within-prescriber, brand-level change and switching, not the cross-sectional association |

## Prompt list

### Phase 0: Setup and scope

- [x] **P00: Repo scaffold.** _Done 2026-10-22: uv + Python 3.12, 24 tests pass, CI green; private repo johnpospisil/pharma-payments-glp1; Quarto 1.10.19 + Homebrew R 4.6.1 (did, fixest, HonestDiD) working; Drive3 1.2 TB / SSD 329 GB free._ `git init`; `pyproject.toml` with `uv` and pinned dependencies (duckdb, polars, pyarrow, pyfixest, differences, statsmodels, linearmodels, matplotlib, plotly, httpx, pytest, ruff); a `Makefile` with targets `check-env data build models figures report app test all`; the `src/ppg/` layout from brief §7; `src/ppg/config.py` reading `PPG_RAW_DIR` and `PPG_DATA_DIR` from `.env`; `.gitignore` excluding data and `.env`; `make check-env`, which reports whether Drive3 is mounted, free space on both disks, and Python/R/DuckDB versions. Install Quarto if it's missing (`brew install --cask quarto`). Create a **private** GitHub repo `johnpospisil/pharma-payments-glp1` with `gh` and push. Add CI (ruff + pytest on fixtures only).
  **Deliverables:** repo URL; `make check-env` output; the package/version list; anything that failed to install.

- [x] **P01: Data inventory and schema history.** _Done 2026-10-22: OP PY2013–2025 (June 2026 pub; 10.4 GB zips → 94.7 GB), Part D 2013–2024 (43.8 GB); 3 OP schema eras (no NPI before 2015); NP/PA covered from PY2021 (0 → 3.5M records); Part B diabetes % 2017+ only; NPPES download down._ Confirm for every source in brief §3 the latest available year, download URLs, file sizes and licence. Record them in `data/reference/sources.csv` and start `DATA.md`. Build a **schema-change table** for Open Payments across program years: the 2016 drug-field renames, the PY2021 restructure (`Covered_Recipient_*` columns), when the recipient NPI field appears, and the **PY2021 expansion to NPs, PAs and other non-physician recipients** (a change in who is covered, which affects exposure definitions). Do the same for Part D (column names, suppression rules, the GE65 fields). Download and save CMS's published summary totals (payments $ by year, Part D totals) to `data/reference/cms_summaries/` for later reconciliation. Propose the year range (D6) and estimate the disk footprint.
  **Deliverables:** `DATA.md` (sources table), `data/reference/sources.csv`, the schema-change table, the disk estimate, the proposed year range.

- [x] **P02: Literature and prior-art scan.** _Done 2026-10-22: 28 refs in docs/literature.md; only GLP-1 precedent is Khunte et al. 2026 (cross-sectional, Mayo Clin Proc); closest design Carey et al. 2021; spillovers (Agha & Zeltzer) → practice-level design; 6 design changes adopted._ Find and summarise 15–25 key papers: DeJong et al. 2016 (meals), Yeh et al. 2016, Fleischman et al. 2016, Hadland et al. 2018 (opioids), Sharma et al. 2018 (difference-in-differences on payments), Mitchell et al. 2021 (review), any 2022–2026 work on GLP-1 / diabetes-drug payments, and the methods papers (Callaway & Sant'Anna 2021, Sun & Abraham 2021, Goodman-Bacon 2021, Roth et al. 2023 on pre-trends, Chen & Roth 2024 on log(1+y)). Say exactly what is new here (brand-level, GLP-1 era, staggered event study, public pipeline), and what we borrow or must not claim.
  **Deliverables:** `docs/literature.md` (table: citation, design, finding, relevance) and a 3-sentence "what's new" statement for the article.

### Phase 1: Ingest (CSV → Parquet)

- [x] **P03: Open Payments ingest.** _Done 2026-10-22: 148.8M general records / $39.2B (PY2013–25) → 3.3 GB Parquet; PY2019–25 match CMS dashboard exactly, PY2013–18 within 0.74% of Reports to Congress; `N/A` product placeholders fixed; `make progress` meter added._ Download the per-year **zip bundles** listed in `data/reference/sources.csv` (8× smaller than the CSVs; they include General, Research, Ownership, Deleted records and a README), plus the Covered Recipient Profile Supplement and profile-ID mapping table, into `PPG_RAW_DIR`. Keep the zips as the immutable raw copy; extract one year at a time, convert, then delete the extracted CSVs. Stream each into Parquet with DuckDB (`PPG_DATA_DIR/open_payments/general/year=…/`), mapping each era's columns to one **harmonised schema**: record ID, program year, payment date, amount, nature of payment, form of payment, manufacturer (name + ID), recipient type, NPI, profile ID, specialty, state, ZIP, product indicators, all five drug/product name + category + NDC fields, dispute and delay flags, and the publication date. Keep the latest publication of each record (CMS republishes corrections). Apply the deleted-records files. Reconcile record counts and $ totals per year against `cms_summaries` for PY2019–2025 (tolerance ±0.5%) and against each archive zip's README / CMS published figures for PY2013–2018.
  **Deliverables:** rows and $ per year (table + chart), Parquet sizes, run times, reconciliation table with pass/fail, harmonised-schema doc in `DATA.md`.

- [ ] **P04: Part D ingest.** Download Medicare Part D Prescribers by Provider and Drug (all years), by Provider (all years), by Geography and Drug (all years), and Part D Spending by Drug. Convert to Parquet, harmonising column names across years. Reconcile total claims and cost per year against CMS's published totals. Measure how much suppression hides: compare by-Provider totals with the sum of that provider's by-Drug rows, and national by-Geography-and-Drug totals with the sum of prescriber rows per drug (first confirm the geography totals include suppressed claims), overall and for each GLP-1 brand.
  **Deliverables:** rows/claims/cost per year, reconciliation table, the **suppression gap** (% of claims hidden, by year, overall vs antidiabetics), GLP-1 brand rows per year.

- [ ] **P05: NPPES and reference data.** Primary specialty = Part D `Prscrbr_Type` per year (CMS-derived). NPPES full file only if the download is back (it was down 2026-10-22): keep NPI, entity type, primary taxonomy, practice state/ZIP, enumeration and deactivation dates, never names; the public **Doctors and Clinicians national downloadable file** (all available vintages): NPI → group practice PAC ID, number of group members, specialty, used for practice-level clustering and practice-clean controls (D-3, from Agha & Zeltzer 2022 / Hyman 2025), and as a specialty cross-check; the NUCC taxonomy → specialty-group crosswalk (`data/reference/specialty_groups.csv`: endocrinology, primary care MD/DO, NP, PA, cardiology, nephrology, other); state diabetes prevalence among Medicare beneficiaries (CMS Chronic Conditions or Geographic Variation file) and CDC PLACES county diabetes/obesity prevalence; Medicare Part D enrollment by state for denominators.
  **Deliverables:** reference tables with row counts, the specialty crosswalk for review (**you may want to check the groupings**), and which diabetes denominator is used for the state map.

- [ ] **P06: Data quality profile.** `tests/test_data_quality.py` covering duplicate record IDs, negative or zero amounts, payment dates outside the program year, NPIs failing the Luhn check, negative claims, Part D rows with claims < 11 (there should be none), disputed and delayed records, and year-to-year jumps in rows per manufacturer. Chart monthly payment counts and $ for the GLP-1 makers (Novo Nordisk, Eli Lilly, AstraZeneca, Sanofi) to spot launches and gaps.
  **Deliverables:** pass/fail checklist, anomaly list with dates, the monthly-payments chart.

### Phase 2: Linkage and measures

- [ ] **P07: Drug-name mapping.** Build `ppg.build.drug_map`: a normaliser (case, punctuation, ® / ™, dosage strings, "(semaglutide)" suffixes, misspellings) plus `data/reference/drug_name_map.csv` (raw string → brand, molecule, class, manufacturer, `is_glp1`, reviewer note). Map Wegovy and Ozempic to the same molecule so a molecule-level exposure (Wegovy payments counted for Ozempic) can be run as a sensitivity in P12/P18. Cover all GLP-1 brands (Ozempic, Rybelsus, Wegovy, Mounjaro, Zepbound, Trulicity, Victoza, Saxenda, Byetta, Bydureon/BCise, Adlyxin, and the combos Soliqua and Xultophy) and the negative-control drugs chosen for P17 (statins, and an unrelated heavily promoted class such as anticoagulants or inhalers). Use NDCs where present. Unit-test 50+ known variants. **Review by hand every unmapped name above $10k total.** Map Part D brand/generic names to the same keys.
  **Deliverables:** `drug_name_map.csv` (**worth reviewing**: it gets released publicly), % of GLP-1-maker $ mapped by year, the top unmapped strings, test count.

- [ ] **P08: NPI linkage.** Attach NPIs to Open Payments recipients: use the direct NPI field where present, and for earlier years match profile ID → NPI through the profile supplement. Report **match rates by year and recipient type** (MD/DO vs NP/PA from PY2021). Measure overlap with Part D: what share of GLP-1 Part D fills come from prescribers who ever appear in Open Payments, and what share of GLP-1 payment $ goes to NPIs who are in Part D. Flag NPIs whose NPPES specialty disagrees with the Open Payments specialty.
  **Deliverables:** match-rate table (written into `DATA.md`), overlap figures, a list of linkage failure modes.

- [ ] **P09: Payment measures.** Build the NPI × year × brand payment table: count, $, and $ by nature group (food & beverage; speaker/faculty fees; consulting; travel & lodging; education; other), first-payment date per brand, and whether the prescriber was ever on a speaker bureau. Decide **D8 (payments naming several drugs)**: propose full credit to each brand vs equal split vs first-listed, and show how many $ each rule moves. Also build the matching **unrelated-drug payments** table (for the P17 negative-control exposure).
  **Deliverables:** payment-measures Parquet, D8 comparison table with a recommendation, per-brand counts of newly exposed prescribers by year (the cohort sizes the event study will have).

- [ ] **P10: Prescriber × brand × year panel.** Build `panel_brand.parquet`: every in-sample NPI × GLP-1 brand × year with 30-day fills, claims, beneficiaries, cost and a **suppression status** (observed / missing-row (0–10 claims) / prescriber absent from Part D that year); the prescriber's diabetes load (claims for metformin, SGLT2, DPP-4, sulfonylureas and insulin); total Part D volume; statin claims and other negative-control outcomes; specialty group, state, the brand launch year, the first-payment year for each brand, and payment measures. Define the analysis sample (e.g. active in Part D ≥ 3 years and a diabetes-load threshold) and report what each filter removes.
  **Deliverables:** panel size and coverage, the sample-flow diagram (counts at each filter), suppression share by brand × year, data dictionary in `DATA.md`.

- [ ] **P11: Descriptive charts and EDA.** In `notebooks/01_eda.ipynb` and `ppg.viz.figures`: chart 3 (Part D GLP-1 spending by brand), chart 4 (GLP-1 payment $ by brand and payment type over time), chart 6 (hex-tile state map of GLP-1 payment $ per diabetic Medicare beneficiary), chart 7 (Lorenz curve of payment $ concentration, with top-1% and top-10% shares), plus payments relative to diabetes load by specialty (secondary question 3). **Stay descriptive:** no post-payment comparisons of paid vs unpaid prescribers (they wait until after P12).
  **Deliverables:** the four charts (PNG + SVG), concentration statistics, top specialties and states by $ per diabetic beneficiary, the EDA notebook.

### Phase 3: Pre-registration

- [ ] **P12: Pre-registration.** Carry in the P02 design implications (docs/literature.md §5): PPML primary scale (D9); brand-specific exposure primary and manufacturer-level secondary (D-2); directional secondaries speaker/consulting > meals and specialists > primary care (D-5); SEs clustered by practice (D-3). Write and lock `PREREGISTRATION.md` (git tag `prereg-v1`) before any outcome model is fitted. Commit to: the primary estimand (ATT on paid-brand 30-day fills, event years 0–3); **the primary brands (D7)**: established brands with a pre-period (Trulicity, Victoza, and Ozempic from 2019 on) for the volume event study, with Mounjaro and new launches analysed through brand share relative to launch; the exposure (first year with a brand-B payment, treated as absorbing) and the control group (not-yet-treated plus never-treated, within specialty × state); the primary estimator (Callaway & Sant'Anna, doubly robust, with pre-period covariates; Sun & Abraham and the R `did` package as cross-checks); **the outcome scale (D9)**; the smallest effect of interest; how secondary tests are adjusted for multiple comparisons (Holm); every falsification and sensitivity test from brief §5; and which results would count as a null or as evidence of targeting only.
  **Deliverables:** `PREREGISTRATION.md` with a one-paragraph summary, the git tag, and the open judgement calls **for you to approve before it's locked**.

### Phase 4: Main models

- [ ] **P13: Event study (primary).** Fit the pre-registered event study per brand and pooled. Report event-time coefficients with 95% CIs, the pre-trend joint test and HonestDiD-style sensitivity (Rambachan & Roth), and the aggregated ATT as a % change. Cross-check with Sun & Abraham, the Borusyak–Jaravel–Spiess imputation estimator, and R `did`. Report event year 0 separately: it is partly treated because payments arrive during the year (D-1). Split by payment type (meals-only vs speaking/consulting). Produce **hero chart v1**. Pin the headline estimates.
  **Deliverables:** hero chart v1, estimates table (estimator × brand), pre-trend test, how far the estimators agree, the pinned-estimate test.

- [ ] **P14: Matched design.** Match exposed prescribers to controls on pre-period level and growth of brand-B and GLP-1-class fills, diabetes load, specialty × state, and total volume (coarsened exact or propensity score; balance table with standardised differences < 0.1). Re-estimate on the matched sample. This is the main defence against "companies target rising prescribers".
  **Deliverables:** balance table and Love plot, matched vs unmatched estimates side by side, what share of exposed prescribers found matches.

- [ ] **P15: Brand switching.** Within-prescriber analysis of the paid brand's share of GLP-1 fills before and after the first payment, vs competing brands (fractional-response or share DiD), including Ozempic ↔ Mounjaro after 2022. Split total growth into class growth vs switching between brands. Produce **chart 5** (paired dumbbells, paid vs unpaid).
  **Deliverables:** chart 5, share-effect estimates, the class-growth vs switching split.

- [ ] **P16: Dose-response and payment type.** Effects by payment bin ($0, < $100, $100–1k, $1k–10k, > $10k) and by nature (meals, speaking, consulting, travel), with intervals. Add a continuous spline on cumulative $. State plainly that higher bins are more selected (the doctors in them differ). Produce **chart 2**.
  **Deliverables:** chart 2, the gradient table, the interpretation caveats.

### Phase 5: Robustness and falsification

- [ ] **P17: Falsification tests.** Negative-control outcome (statin fills should not respond to GLP-1 payments); negative-control exposure (payments for unrelated drugs should not predict GLP-1 growth); placebo timing (fake first-payment years 1–2 years early); a placebo brand (does a Trulicity payment move Ozempic volume upward? It should not, or it should move it down).
  **Deliverables:** falsification table with pass/fail, the placebo event-study charts, and what any failures mean for the headline.

- [ ] **P18: Sensitivity.** Suppression bounds (missing rows set to 0, 5 and 10 claims, and a sample restricted to prescribers who are never suppressed); event year moved to t+1 when the first payment is in July–December (D-1); controls restricted to practices with no paid member, to gauge spillover bias (D-3); manufacturer-level exposure (D-2); drop the top 1% of payees; the D8 allocation variants; excluding NPs/PAs; physicians only before 2021; alternative outcomes (claims, beneficiaries, cost); PPML vs log(1+y); different sample filters. All in one **forest plot**.
  **Deliverables:** forest plot, robustness table, a list of conclusions that hold up and any that don't.

- [ ] **P19: Heterogeneity and geography.** Effects by specialty group (endocrinology, primary care MD/DO, NP/PA), region and urban/rural; payments relative to diabetes load by state × specialty. Holm-adjust the comparisons. Enforce ≥ 11 prescribers in every cell shown.
  **Deliverables:** heterogeneity chart and table, the adjusted p-values, any subgroup results that are fragile.

- [ ] **P20: QA and validation pass.** Rebuild with `make all` from raw on a clean checkout; check every number destined for the article against `report/qa/*.json`; review the methodology for overstated claims (data:validate-data style); confirm that no output exposes an individual prescriber.
  **Deliverables:** QA checklist with pass/fail, the rebuild time, the list of claims that are still weak.

### Phase 6: Write, build, review

- [ ] **P21: Final figures.** `ppg.viz.theme` (one palette, light and dark, colour-blind safe), with final versions of the hero chart and charts 2–7, alt text for each, and social-media crops.
  **Deliverables:** `report/figures/` (all charts), a contact sheet of every figure.

- [ ] **P22: Quarto article.** `report/index.qmd`: "What we found / what it doesn't mean" box first, then the question, data, method in plain English, results, falsification, limitations, an ethics note (why no individual doctors are shown), and a reproducibility section. Cite the literature from P02. Every number comes from `report/qa`. Render locally.
  **Deliverables:** the rendered article (local link), word count, claims flagged as weak.

- [ ] **P23: Specialty × state explorer.** A static app in `app/` (no server, so it runs on GitHub Pages): brand selector, specialty and state filters, payments vs prescribing trends over time, cells with fewer than 11 prescribers hidden. Data is pre-aggregated JSON from the pipeline. Check it on desktop and at phone width with Playwright screenshots.
  **Deliverables:** local app link, screenshots (desktop + mobile), JSON size.

- [ ] **P24: Red-team review.** Fresh agents review the article and app separately as (a) a skeptical health economist (identification, targeting, staggered-DiD pitfalls), (b) a clinical pharmacist (GLP-1 indications, formulary and coverage changes, shortages in 2022–2024, Wegovy CV coverage from 2024, compounding), and (c) a data journalist (claims vs evidence, ethics, fairness to physicians). Triage every point into fix / disclose / reject (with reason) and apply the fixes. Also write `docs/review-checklist.md` that the user could send to a real clinician.
  **Deliverables:** review triage table, the changes made, the review checklist.

### Phase 7: Publish (portfolio + socials)

- [ ] **P25: Released datasets.** Release (1) `drug_name_map.csv` with a data card, and (2) the aggregated specialty × state × brand × year panel (no NPIs), each with a column dictionary, licence (CMS data is public domain; code MIT), checksums and known limitations. Ask the user before uploading anywhere.
  **Deliverables:** `release/` files and sizes, the data cards.

- [ ] **P26: README and GitHub Pages.** README leading with the hero chart, three findings, one "what this doesn't show" line, how to reproduce, and links. A Pages workflow (`.github/workflows/pages.yml`, modelled on stackoverflow-decline) builds the article + app from the committed `report/qa` and figures, so raw data isn't needed in CI. **The user confirms before the repo goes public.** Then enable Pages and confirm the live site with Playwright screenshots.
  **Deliverables:** live URLs (`https://johnpospisil.github.io/pharma-payments-glp1/` and `/app/`), screenshots, a green CI run.

- [ ] **P27: Launch kit.** Drafts for a Show HN title + first comment, r/medicine and r/pharmacy (check each subreddit's rules first), r/dataisbeautiful, LinkedIn (framed around the method), a Bluesky thread (5–7 posts, one chart each), 15 likely reviewer questions with answers, and a short project-page blurb for johnpospisil.com/data-science/. Nothing is posted without the user.
  **Deliverables:** `docs/launch/` drafts, the Q&A, the launch checklist.

### Stretch (after publishing)

- [ ] Replicate the pipeline on SGLT2 inhibitors or anticoagulants.
- [ ] Commercial-market context from company 10-K figures (scale only, no microdata).
- [ ] Telehealth / compounding prescribers, if public data supports it.
