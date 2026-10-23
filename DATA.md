# DATA.md: sources, coverage and known issues

Inventory as of **2026-10-22** (P01). Machine-readable list with URLs and sizes: [data/reference/sources.csv](data/reference/sources.csv). Retrieval dates and checksums are logged in `data/reference/retrievals.csv` at download time (P03–P05).

## 1. Sources

| Source | Coverage | Latest release | Files | Size (download → uncompressed) | Role |
|---|---|---|---|---|---|
| **Open Payments**: General, Research, Ownership, Deleted records | PY2013 (Aug–Dec only) – PY2025 | June 2026 publication (`P06302026_06032026`), published 2026-06-30 | one zip per program year | 10.4 GB → 94.7 GB (General: 84.5 GB) | exposure (payments) |
| Open Payments: Covered Recipient Profile Supplement | all years | 2026-06-30 | 1 CSV | 0.40 GB | profile ID ↔ NPI for PY2013–2014 |
| Open Payments: Provider profile ID mapping | all years | 2026-06-30 | 1 CSV | small | merges duplicate profile IDs |
| Open Payments: summary dashboard + national totals | PY2019–2025 only | 2026-06-30 | 2 CSVs (in `data/reference/cms_summaries/`) | 18 KB | reconciliation |
| **Part D Prescribers by Provider and Drug** | 2013–2024 | 2024 data released 2026-05-21 | 12 CSVs | 43.8 GB | outcome (fills by brand) |
| Part D Prescribers by Provider | 2013–2024 | all years re-issued 2026-08-03 | 12 CSVs | 8.0 GB | total volume, specialty, patient mix, suppression gap |
| Part D Prescribers by Geography and Drug | 2013–2024 | 2026-05-21 | 12 CSVs | small | national/state totals per drug, **including suppressed rows** (used to measure suppression) |
| Part D Spending by Drug | 2020–2024 in latest file (earlier in archived editions) | 2026-06-25 | 1 CSV | small | context chart 3 |
| Physician & Other Practitioners by Provider (Part B) | 2013–2024 | 2026-05-21 | 12 CSVs | 5.1 GB | diabetes caseload (`Bene_CC_PH_Diabetes_V2_Pct`, **2017+ only**) |
| Medicare Geographic Variation (national/state/county), Original Medicare only | 2014–2024 | 2026-05-15 | 1 CSV | small | Medicare enrollment denominators |
| CDC PLACES, county, 2025 release | BRFSS 2023 model-based | 2025-12-04 | 1 CSV | small | diabetes/obesity prevalence (context) |
| NUCC provider taxonomy v26.1 | current | 2026 | 1 CSV | small | taxonomy → specialty group |
| **NPPES full file** | n/a | **unavailable 2026-10-22** ("down for maintenance until further notice") | — | ~1 GB zip / ~10 GB | taxonomy, deactivation dates (backup; retry in P05) |

All CMS and CDC data are US-government works in the public domain. NUCC taxonomy is free to use with attribution.

## 2. Open Payments schema history (General Payments)

Read from the header row of every program year's CSV (remote reads of the zips, 2026-10-22). CMS **re-released PY2016 onward in the current layout**, so the 2016–2025 files share one schema.

| Era | Program years | Columns | Recipient ID | Drug fields | Notes |
|---|---|---|---|---|---|
| A | 2013, 2014 | 65 | `Physician_Profile_ID` only (**no NPI**) | `Name_of_Associated_Covered_Drug_or_Biological1–5`, `NDC_of_…1–5`, separate device fields | PY2013 covers **Aug 1 – Dec 31, 2013 only** |
| A′ | 2015 | 66 | `Physician_Profile_ID` + **`Physician_NPI`** (added) | as era A | |
| B | 2016–2025 | 91 | `Covered_Recipient_Profile_ID` + `Covered_Recipient_NPI` | `Name_of_Drug_or_Biological_or_Device_or_Medical_Supply_1–5`, plus per slot: covered/non-covered flag, drug-vs-device flag, **`Product_Category_or_Therapeutic_Area`**, NDC, device PDI | physician fields renamed `Covered_Recipient_*`; up to 6 primary types/specialties |

Era A → B renames that the harmonised schema must map (P03): `Physician_*` → `Covered_Recipient_*`; `Product_Indicator` → `Related_Product_Indicator`; drug name/NDC slots as above. Columns that exist in every era: record ID, amounts, date, nature/form of payment, manufacturer IDs, recipient state/ZIP, dispute and delay flags, program year, publication date.

### Changes in who is covered (not visible in the header)

- **PY2021: non-physician practitioners became covered recipients.** Payment records with primary type "Nurse Practitioner" / "Physician Assistant" (Open Payments API counts, 2026-10-22):

  | Program year | Medical Doctor | Nurse Practitioner | Physician Assistant |
  |---|---|---|---|
  | 2020 | 4,827,621 | **0** | **0** |
  | 2021 | 6,543,310 | 2,317,460 | 1,185,888 |
  | 2024 | 8,216,189 | 3,576,576 | 1,809,508 |

  Consequence: for NPs and PAs, payments **before 2021 are unobserved, not zero**. A "first payment in 2021" is mostly an artifact of the rule change. Other newly covered types (CNS, CRNA, CNM) are minor prescribers.
- **PY2013 is a partial year** (Aug–Dec), and nothing before Aug 2013 is observed. "First payment year" is left-censored for brands launched before then (Victoza 2010, Byetta 2005). Brands launched later (Trulicity 2014-09, Ozempic 2017-12, Rybelsus 2019-09, Mounjaro 2022-05) are not affected: their first brand payment can't predate the data.
- 2018 exists in two archived editions; we use the **final one (`P01232026_01102026`)**, not the Jan-2025 edition the archive page links to (per the openpayments-database project's `sources.yaml`; both URLs verified live on download.cms.gov 2026-10-22).
- Deleted-records files exist for PY2016+ only.
- CMS's published summary totals cover PY2019–2025 only. PY2013–2018 will be reconciled against the README in each archive zip and CMS's published annual figures (P03).

### Rough scale of GLP-1 promotion (product slot 1 only, from the API; **for orientation only**)

| PY | Ozempic | Mounjaro | Trulicity | Rybelsus | Victoza | Wegovy | Zepbound |
|---|---|---|---|---|---|---|---|
| 2019 | (timed out) | 0 | 94,542 | 0 | 2,732 | 0 | 0 |
| 2022 | 165,033 | 100,252 | 94,381 | 232,207 | 317 | 9,841 | 0 |
| 2024 | 200,760 | 231,854 | 3,313 | 94,556 | 197 | 128,112 | 31,104 |
| 2025 | 191,472 | 187,338 | 72 | 70,941 | 22 | 180,810 | 42,652 |

Payment records, not dollars. Full counts across all five product slots come in P03/P07.

## 3. Part D schema and suppression

- **Schema is stable 2013–2024:** by Provider and Drug has 22 columns (`Prscrbr_NPI`, `Prscrbr_Type`, `Prscrbr_Type_Src`, state, `Brnd_Name`, `Gnrc_Name`, `Tot_Clms`, `Tot_30day_Fills`, `Tot_Day_Suply`, `Tot_Drug_Cst`, `Tot_Benes`, GE65 fields and suppression flags); by Provider has 84 columns (totals, brand/generic/LIS/MAPD splits, opioid/antibiotic/antipsychotic measures, beneficiary age/sex/race/dual counts, average risk score). Neither has a diabetes measure.
- **Suppression:** prescriber × drug rows with **fewer than 11 claims are omitted entirely**. Within a row, `Tot_Benes` is blank when 1–10 (`GE65_*` likewise, with flags `*` = suppressed, `#` = counter-suppressed). A missing row means 0–10 claims, never "0". The by-Geography-and-Drug national totals should include the claims hidden at prescriber level (**to verify in P04**); if so, the gap between them and the sum of prescriber rows measures what is hidden.
- `Prscrbr_Type` is CMS's specialty per year (`Prscrbr_Type_Src` gives the source: claims-specialty or NPPES taxonomy). It is the primary specialty variable while NPPES is unavailable.
- Part B diabetes caseload (`Bene_CC_PH_Diabetes_V2_Pct` × beneficiaries) exists only from **2017** and only for fee-for-service patients. For 2013–2016, diabetes load is proxied by claims for other antidiabetic drugs in Part D.

## 4. Proposed year range (D6)

| Use | Years | Why |
|---|---|---|
| Outcomes (Part D) | **2013–2024** | all available; 2024 is the latest year |
| Exposure (Open Payments) | **PY2013–2024** linked to outcomes; **PY2025** descriptive only | outcomes for 2025 are not yet published |
| Event-study cohorts | first brand payment in **2015–2024** | 2013–2014 serve as the pre-period/washout (PY2013 partial; no NPI field before 2015) |
| NPs/PAs | in descriptive work; **excluded from the primary event study** (or kept with event years ≥ 2022 and a 2021 washout) | their payments before 2021 are unobserved |

## 5. Disk footprint

| Item | Where | Size |
|---|---|---|
| Open Payments zips (kept as raw) | Drive3 | 10.4 GB |
| One year's extracted CSVs during conversion (deleted afterwards) | Drive3 | ≤ 10 GB at a time |
| Part D by Drug + by Provider, Part B, other CSVs | Drive3 | ~58 GB |
| **Raw total on Drive3** | | **~70 GB** (1.2 TB free) |
| Parquet: Open Payments (all columns except names/addresses) | SSD | ~10–14 GB (est.) |
| Parquet: Part D + Part B | SSD | ~6–9 GB (est.) |
| Panels, models, figures | SSD | < 5 GB |
| **Working total on SSD** | | **~20–30 GB** (329 GB free) |

Prescriber names and street addresses are dropped at conversion: the analysis never needs them, and dropping them supports the no-individuals rule.

## 6. Converted Open Payments (P03)

Parquet under `PPG_DATA_DIR/parquet/open_payments/` (zstd, one file per program year):

| Table | Path | Content |
|---|---|---|
| `general` | `general/program_year=YYYY/part-0.parquet` | **harmonised schema below**, all eras |
| `research` | `research/program_year=YYYY/` | source columns (lower-cased, text), minus names/street addresses |
| `ownership` | `ownership/program_year=YYYY/` | as research |
| `removed_deleted` | `removed_deleted/program_year=YYYY/` | record IDs removed since the previous publication (PY2016+) |
| `profile_supplement.parquet` | | profile ID ↔ NPI, specialty, taxonomies, license states (no names/addresses) |
| `profile_id_mapping.parquet` | | secondary → primary profile IDs |

Each zip's README is copied to `data/reference/op_readme/`. Code: `src/ppg/ingest/open_payments.py` (download), `op_convert.py` (convert), `op_reconcile.py` (checks), `op_summary.py` (table + chart). Run with `make data-open-payments`; watch with `make progress`.

### Harmonised General Payments schema

| Column | Type | Era A (2013–14) / A′ (2015) source | Era B (2016–25) source |
|---|---|---|---|
| `program_year` | int | `Program_Year` | same |
| `record_id` | bigint | `Record_ID` | same |
| `change_type` | text | `Change_Type` (NEW / ADD / CHANGED / UNCHANGED) | same |
| `recipient_type` | text | `Covered_Recipient_Type` | same (NPP types from 2021) |
| `profile_id` | bigint | `Physician_Profile_ID` | `Covered_Recipient_Profile_ID` |
| `npi` | bigint | NULL (2013–14); `Physician_NPI` (2015) | `Covered_Recipient_NPI` |
| `teaching_hospital_ccn`, `teaching_hospital_id` | text, bigint | same names | same |
| `primary_types` | list<text> | `[Physician_Primary_Type]` | `Covered_Recipient_Primary_Type_1–6` (blanks dropped) |
| `specialties` | list<text> | `[Physician_Specialty]` (pipe-separated taxonomy path) | `Covered_Recipient_Specialty_1–6` |
| `recipient_city`, `recipient_state`, `recipient_zip5`, `recipient_country` | text | `Recipient_*` (ZIP cut to 5 digits) | same |
| `submitting_entity`, `manufacturer_id`, `manufacturer_name`, `manufacturer_state`, `manufacturer_country` | | `*Applicable_Manufacturer_or_Applicable_GPO*` | same |
| `amount_usd` | decimal(14,2) | `Total_Amount_of_Payment_USDollars` | same |
| `payment_date` | date | `Date_of_Payment` (MM/DD/YYYY) | same |
| `n_payments` | int | `Number_of_Payments_Included_in_Total_Amount` | same |
| `form_of_payment`, `nature_of_payment` | text | same names | same |
| `travel_state`, `travel_country` | text | `State_of_Travel`, `Country_of_Travel` | same |
| `physician_ownership`, `charity`, `third_party_is_recipient`, `delayed_publication`, `disputed` | bool | Yes/No fields | same |
| `third_party_recipient`, `related_product_indicator` | text | `Third_Party_Payment_Recipient_Indicator`, `Product_Indicator` | `…`, `Related_Product_Indicator` |
| `contextual_information` | text | free text (internal use only; never published) | same |
| `products` | list<struct{slot, covered, kind, category, name, ndc, pdi}> | drug slots 1–5 (kind = Drug), device slots 6–10 (kind = Device); no category | slots 1–5 with covered flag, kind, **therapeutic area**, name, NDC, device PDI |
| `publication_date` | date | `Payment_Publication_Date` | same |

**Dropped at conversion:** recipient first/middle/last names and suffixes, street addresses, license-state codes, teaching-hospital names and third-party entity names.

### P03 results (2026-10-22)

- **Converted:** 148.8M General Payments records (PY2013–2025, $39.2B), 11.0M Research, 53.9K Ownership, 162K removed/deleted IDs; 3.3 GB Parquet. Full run ≈ 5 min after download (download ≈ 15 min at 12 MB/s).
- **Reconciliation** ([report/qa/op_reconciliation.csv](report/qa/op_reconciliation.csv)): PY2019–2025 General/Research records and dollars, disputed records and Ownership records match the June 2026 dashboard **exactly** (0.000%); PY2013–2018 all-category record counts within +0.06%, −0.02%, +0.03%, +0.07%, +0.08%, +0.74% of CMS Reports to Congress (FY2019/FY2020/FY2022, which predate the final republications).
- **Integrity:** no duplicate `record_id` (within or across years); no removed/deleted record ID present in General; no null amounts or dates; **871 records with amount ≤ $0** and **467 with a payment date outside the program year** (left as published; handled in P06).
- **Product placeholders:** PY2016–2020 fill empty device-ID slots with the text `N/A`. Placeholder values (`N/A`, `NA`, `NONE`, `NULL`, `-`) are treated as missing in product fields. 91–93% of records name at least one product in every year.
- **NPI coverage:** 0% of PY2013–2014 records carry an NPI (field absent; linked via profile ID in P08); 99.4–99.7% from 2015 (the remainder are teaching hospitals).
- **PY2024 removed/deleted file has 160,183 rows** (vs ≤ 900 in other years) — a large deletion by reporting entities between publications; the deleted records are absent from General as expected.

## 7. Converted Part D and Part B (P04, 2026-10-23)

Parquet under `PPG_DATA_DIR/parquet/{partd,partb}/<table>/year=YYYY/part-0.parquet` (`spending_by_drug/all.parquet` is one wide file). Raw CSVs kept on Drive3 (D13): Part D 48 GB, Part B 4.8 GB → Parquet 6.7 GB + 1.2 GB. Columns lower-cased; prescriber names, middle initial, street address and city dropped; blanks (suppressed) are NULL, never 0. Code: `src/ppg/ingest/partd.py`, `partd_convert.py`, `partd_qa.py`; run with `make data-partd`.

| Table | Rows per year | Notes |
|---|---|---|
| Part D by Provider and Drug | 23.6M (2013) → 28.0M (2024) | 0.81M → 1.14M prescribers |
| Part D by Provider | 1.05M → 1.42M | prescriber totals incl. claims hidden in by-drug rows |
| Part D by Geography and Drug | ~107K–118K | national + state rows per drug |
| Part D Spending by Drug | 14.5K (one file, 2020–2024 wide) | |
| Part B by Provider | 0.96M → 1.30M | diabetes % from 2017 |

### Checks ([report/qa/partd_checks.json](report/qa/partd_checks.json))

- Prescriber × drug rows: **0** with < 11 claims, **0** negative, **0** missing NPI, **0** duplicate NPI × brand × generic × year keys.
- **National rows of "by Geography and Drug" include the claims hidden at prescriber level**: national claims ≥ the sum of prescriber rows (and national prescriber counts ≥ the number of prescriber rows) for **100% of drugs in every year** ([partd_national_vs_rows.csv](report/qa/partd_national_vs_rows.csv)).
- **Two CMS products agree:** national GLP-1 claims and cost (Geography) vs Part D Spending by Drug, 2020–2024, every brand: within **0.08%** ([partd_spending_crosscheck.csv](report/qa/partd_spending_crosscheck.csv)).
- Part D by Provider total claims = national claims within 0.1% each year (the gap = prescribers with < 11 claims in total).

### How much suppression hides ([partd_by_year.csv](report/qa/partd_by_year.csv), [partd_glp1_brands.csv](report/qa/partd_glp1_brands.csv))

- **All drugs:** 13.1%–14.0% of claims are in suppressed prescriber × drug cells, every year.
- **GLP-1 class:** **36.5% (2013) → 24.8% (2019) → 10.6% (2024)**: the hidden share falls as the drugs become common.
- **By brand, the share of prescribers below 11 claims (no row at all) is large:** Ozempic 74% (2019) → 40% (2024); Trulicity 65% (2017) → 53% (2024); Mounjaro 93% (2022) → 50% (2024); Rybelsus 77% (2022) → 72% (2024); Victoza 3-Pak 70–94%. Claims hidden: Ozempic 26% → 4.6%, Mounjaro 67% → 8.0%, Trulicity 20% → 11%, Rybelsus 33% → 28%.
- Consequence for the design: for most prescriber × brand × years the outcome is **interval-censored (0–10 claims)**, especially before and just after launch. See the P04 questions in CLAUDE.md / P12.

### Brand-name facts for the drug map (P07)

- Part D splits brands into presentations: `Victoza 2-Pak` / `Victoza 3-Pak`, `Bydureon` / `Bydureon Pen` / `Bydureon Bcise`, `Soliqua 100-33`, `Xultophy 100-3.6`.
- **Generic liraglutide** appears in 2024 (62K claims; generic Victoza) and must not be mapped to the Victoza brand.
- **Wegovy** appears in 2024 (211K claims, CV-risk indication); **Zepbound** has 353 claims in 2024. Tanzeum (albiglutide) was withdrawn by 2019; Adlyxin is negligible.
- Trulicity's first Part D year is 2014 (215 claims; launched Sept 2014); Ozempic 2018; Rybelsus 2019 (400 claims); Mounjaro 2022.

## 8. Reference data (P05, 2026-10-23)

Parquet under `PPG_DATA_DIR/parquet/reference/`; raw CSVs on Drive3 `raw/reference/`. Code: `src/ppg/ingest/reference.py`, `src/ppg/build/specialty.py`, `src/ppg/build/denominators.py`; run with `make data-reference`.

| Table | Rows | Use | Notes |
|---|---|---|---|
| `dac.parquet` (Doctors and Clinicians, **Oct 2026 snapshot**) | 3.63M rows; 1.64M NPIs; 83.7K group practices | practice ID (`org_pac_id`), group size, graduation year, specialty | names, addresses, phone and **group names dropped**. Covers 86.9% of 2024 GLP-1 prescribers (78.9% with a group) but only 71.3% / 61.2% of 2016 prescribers (attrition). Practice membership is **as of 2026, not as of each year**; archived snapshots are blocked for automated download (HTTP 403). Median 1 group per clinician (p90 = 2). |
| `nucc_taxonomy.parquet` | 883 | taxonomy code labels | v26.1 |
| `places_county.parquet` (CDC PLACES 2025) | 3,143 counties | diabetes / obesity prevalence (crude and age-adjusted, 18+) | context only |
| `brfss_diabetes_65plus.parquet` | 792 (54 jurisdictions × 2011–2025) | % of adults 65+ ever told they have diabetes | CDC BRFSS dataset dttw-5yxu |
| `enrollment_state_year.parquet` | 767 | Medicare and **Part D enrollees** (`prscrptn_drug_tot_benes`) by state and year, 2013–2025 | annual rows of Medicare Monthly Enrollment |
| `gv_state_county.parquet` | 35,762 | Original Medicare utilisation context, 2014–2024 | no diabetes measure |
| `state_diabetic_partd.parquet` | 754 state-years | **denominator for chart 6** | see below |

**NPPES:** still unavailable on 2026-10-23 ("down for maintenance until further notice"). Not needed: Part D `prscrbr_type` (CMS-derived, per year) is the primary specialty, DAC supplies practice IDs. `python -m ppg.ingest.reference nppes` re-checks.

### Specialty groups ([data/reference/specialty_groups.csv](data/reference/specialty_groups.csv))

All 290 `prscrbr_type` labels seen in Part D 2013–2024 → 8 groups by ordered keyword rules plus reviewed overrides (`src/ppg/build/specialty.py`; tests in `tests/test_specialty.py`). Share of all GLP-1 claims 2013–2024: **primary-care physicians 54.9%** (family practice, internal medicine, general practice, geriatrics, preventive, osteopathic manipulative), **nurse practitioners 18.0%**, **endocrinology 17.5%**, **physician assistants 6.3%**, other physicians 1.3%, other non-physicians 0.8% (pharmacists, CNS, students…), cardiology 0.7%, nephrology 0.4%. Labels change between years (e.g. "Cardiovascular Disease (Cardiology)" appears only in 2016), and an NPI's label can change across years; P10 assigns one group per NPI (modal label, ties → most recent).

### Diabetes denominator for the state map

`est_diabetic_partd = Part D enrollees (state, year) × BRFSS % of adults 65+ with diabetes`, prevalence pooled over years t−2..t weighted by sample size (single-year state samples are ~200–800). 2024: **12.96M** estimated diabetic Part D enrollees (≈24% of 54.4M); lowest prevalence MT 16.6%, VT 16.7%, CO 17.8%; highest PR 38.6%. Covers 50 states + DC + PR (+ GU, VI); no estimate for AS, MP and foreign/unknown rows. Approximation: 65+ prevalence applied to all Part D enrollees (≈13% are under 65).

## 9. Data-quality profile (P06, 2026-10-23)

Code: `src/ppg/ingest/quality.py` (`python -m ppg.ingest.quality`); tests: `tests/test_data_quality.py` (marked `data`, skipped when the Parquet is absent; `make test-fast` skips them). Results: [report/qa/data_quality.json](report/qa/data_quality.json).

| Check | Open Payments (148.8M records) | Part D by Provider and Drug (304.3M rows) |
|---|---|---|
| Duplicate keys | 0 record IDs | 0 NPI × brand × generic × year |
| Missing amount / date / drug name | 0 / 0 | 0 drug names |
| NPI check digit (Luhn) | **14** of 1,861,090 distinct NPIs fail | 0 of 1,721,486 |
| Negative values | 871 amounts ≤ $0 (D12: kept as contacts, not dollars) | 0 |
| Dates | 467 outside the program year (95 by > 1 year) | — |
| Other | 10 records with `n_payments` < 1; 1,999 single payments > $1M; 8,294 disputed | 0 rows < 11 claims; 0 with fills < claims; 0 with beneficiaries > claims |
| NPI missing (2015+, non-teaching-hospital) | 91,235, **all with a profile ID** → linked in P08 | — |

### Anomalies

- **Large non-promotional payments dominate dollars.** Royalties/licences are $13.9B (35% of all general-payment dollars); payments > $1M total ≈ $10.3B, mostly royalties, licences and acquisitions (e.g. a **$55.1M "Acquisitions" payment from Novo Nordisk to one physician on 2025-12-09**; **$16M AstraZeneca royalty to a teaching hospital, 2023-05-18**). Food and beverage is 132.8M of 148.8M records (89%) but $3.5B. → Dollar measures must use a **promotional subset** (P09).
- **Eli Lilly meals collapse in Nov–Dec 2025:** Food-and-beverage records 36,317 (Oct 2025) → 5,159 (Nov) → 6,993 (Dec); Lilly's speaker and consulting payments continue, and the other makers show only the usual December dip. No public explanation found (web search, 2026-10-23). PY2025 is descriptive only (D6), so it cannot affect the event study; flag it on any chart that includes 2025.
- **Usual seasonality:** December dips every year for all makers; spring 2020 COVID trough (e.g. Lilly 633 and 407 records in Apr–May 2020 vs ~23K median).
- **Manufacturer-year jumps (> 2× change, ≥ 20K records): 237** ([op_manufacturer_jumps.csv](report/qa/op_manufacturer_jumps.csv)): 75 in 2014 (vs partial 2013), 76 in 2020–2021 (COVID and rebound); most others are corporate events (Actavis/Allergan 2015–16, Shire→Takeda 2018, Valeant 2015, Biohaven→Pfizer 2023).
- Monthly series for the four GLP-1 makers: [op_monthly_glp1_makers.csv](report/qa/op_monthly_glp1_makers.csv); flagged months: [op_monthly_gaps.csv](report/qa/op_monthly_gaps.csv); chart: [p06_monthly_payments_glp1_makers.png](report/figures/p06_monthly_payments_glp1_makers.png).

## 10. Drug-name map (P07, 2026-10-23)

Code: `src/ppg/build/drug_map.py` (`python -m ppg.build.drug_map`, part of `make build`); tests: `tests/test_drug_map.py` (129, no data needed). Rules live in the code (`BRANDS`, `MOLECULES`, `ACCEPT`, `CLASS_ONLY`, `REJECT`); the CSVs are generated from them and committed after review:

| File | Rows | What it is |
|---|---|---|
| [data/reference/drug_name_map.csv](data/reference/drug_name_map.csv) | 585 | Open Payments product string → brand, molecule, class, `is_glp1`, indication, manufacturer, match method, payers, $ and records, reviewer note. 308 in-scope strings + 277 reviewed out-of-scope strings. **Released publicly in P25.** |
| [data/reference/partd_drug_map.csv](data/reference/partd_drug_map.csv) | 691 | Part D (`brnd_name`, `gnrc_name`) → brand family and class for GLP-1s, other diabetes drugs, diabetes supplies, statins, oral anticoagulants and inhalers |
| [data/reference/drug_ndc_map.csv](data/reference/drug_ndc_map.csv) | 1,114 | NDC key → brand, learned from named records (≥ 95% agreement) |

**How strings are matched** (first rule that applies): exact normalised name (case, ®/™, parentheses, strengths and dosage-form words removed) → whole-word brand inside a longer string → generic-molecule rule → "no product / disease state" → fuzzy spelling (flagged for review). Matching is never by substring: "Victo" also appears in PLUVICTO and in 3M's "Victory Series" orthodontic brackets.

**Open Payments names are clean.** Manufacturers report from their own product lists, so 25 strings cover every GLP-1 payment: 14 brands (Ozempic, Rybelsus, Wegovy, Victoza, Saxenda, Trulicity, Mounjaro, Zepbound, Byetta, Bydureon, Adlyxin, Tanzeum, and the insulin combinations Soliqua and Xultophy) plus a Sanofi GLP-1/glucagon pipeline compound. That is **9.49M records, $452.5M** in PY2013–2025 ($426.9M promotional, D16). Methods across the map: 186 exact, 45 contains, 20 molecule, 51 non-product, 6 reviewed by hand (two misspellings found by fuzzy matching, Trajenta and Stioloto, were confirmed). Every GLP-1 string is paid by its own brand's maker.

**Coverage, GLP-1 makers** (Novo Nordisk, Eli Lilly, AstraZeneca, Sanofi/Genzyme; promotional $, split equally across a record's products): [drug_map_coverage_by_year.csv](report/qa/drug_map_coverage_by_year.csv)

| Year | Promo $M | Names a product | Of which resolved | GLP-1 $M | GLP-1 share of named |
|---|---|---|---|---|---|
| 2013 | 58 | 75.8% | 98.8% | 9.3 | 21.2% |
| 2014 | 152 | 78.0% | 99.3% | 38.2 | 32.3% |
| 2015 | 150 | 81.2% | 99.1% | 35.7 | 29.3% |
| 2016 | 154 | 84.9% | 99.5% | 24.3 | 18.6% |
| 2017 | 166 | 86.4% | 99.7% | 38.3 | 26.7% |
| 2018 | 167 | 83.3% | 99.9% | 36.0 | 26.0% |
| 2019 | 165 | 81.1% | 99.9% | 29.3 | 21.8% |
| 2020 | 93 | 80.5% | 100.0% | 21.0 | 28.0% |
| 2021 | 124 | 80.2% | 100.0% | 32.8 | 33.1% |
| 2022 | 150 | 80.0% | 100.0% | 42.5 | 35.4% |
| 2023 | 160 | 70.0% | 100.0% | 27.6 | 24.6% |
| 2024 | 193 | 74.2% | 100.0% | 33.6 | 23.4% |
| 2025 | 210 | 74.3% | 100.0% | 48.3 | 30.9% |

"Resolved" = mapped to an in-scope class or reviewed by hand as out of scope. **14–30% of the makers' promotional $ names no product at all**; P09 has to decide how those payments count (manufacturer-level exposure only, D-2). GLP-1 $ by brand and year: [drug_map_glp1_by_brand_year.csv](report/qa/drug_map_glp1_by_brand_year.csv).

**Hand review.** Reviewed by hand:
- every unmapped drug/biologic string of ≥ $10K paid by a GLP-1 maker (277; oncology, immunology, rare disease, vaccines; none in scope);
- every string of ≥ $10K from any maker whose spelling is close to a mapped brand (STELARA ≈ Steglatro, EXPAREL ≈ Xarelto, CAPLYTA ≈ Arcapta: all different drugs);
- every string, at any $, containing a mapped brand name or a GLP-1, SGLT2, DPP-4, statin, anticoagulant or insulin stem.

The remaining 4,211 unmapped drug/biologic strings of ≥ $10K are other companies' products with no such signal. The top 100 by $ are in [drug_map_unmapped_top.csv](report/qa/drug_map_unmapped_top.csv) (COMIRNATY, Rituxan, BOTOX, Herceptin…).

**Traps found and handled**
- Part D generic names are truncated to 30 characters ("Dapaglifloz Propaned/Metformin"), so the molecule rules use short stems.
- Part D lists **insulin syringes, pen needles and pump cartridges under insulin-like generic names**: 411 rows, 54.9M claims in 2013–2024. They get their own `diabetes_supply` class, not `insulin`.
- Look-alikes are excluded and tested: nystatin, cilastatin and pentostatin are not statins; teduglutide (Gattex, a GLP-2 analogue) is not a GLP-1; "Hylenex with Insulin" is hyaluronidase.
- Strings that name a disease plus a product ("CANCIDAS Infectious Disease") are not "no product" strings.
- **NDCs are unreliable inside multi-product records.** In AstraZeneca's 2013–14 records one product's NDC appears against another (Farxiga and Crestor rows carry Bydureon's code): 2,523 records conflict. NDCs are therefore used only to recover name-less product slots: 2,705 of 9,532, including 1,575 GLP-1 (Bydureon, 2013–14), flagged as `ndc`-matched.
- Wegovy, Saxenda and Zepbound are obesity-indicated (`indication = obesity`). Part D excludes weight-loss-only use, so Saxenda has no Part D rows, while Wegovy (2023–24) and Zepbound (2024) have a few. The molecule column links Wegovy and Rybelsus to Ozempic (semaglutide) and Zepbound to Mounjaro (tirzepatide) for the molecule-level sensitivity analysis.
- Generic liraglutide (2024) is its own Part D family, `liraglutide (generic)` (D15).

## 11. NPI linkage (P08, 2026-10-23)

Code: `src/ppg/build/linkage.py` (`python -m ppg.build.linkage`, about 10 min, part of `make build`); tests: `tests/test_linkage.py`. Outputs are in `PARQUET_DIR/linkage/` (1.4 GB, git-ignored):

- `op_record_npi/`: one row per General Payments record, giving `npi_linked`, `link_method` and `recipient_class`.
- `profile_npi.parquet`: 1.86M profile IDs mapped to an NPI.
- `npi_specialty.parquet`: each NPI's specialty in Open Payments vs Part D, with an agree flag.

QA: [linkage.json](report/qa/linkage.json), [linkage_match_rates.csv](report/qa/linkage_match_rates.csv), [linkage_overlap_by_year.csv](report/qa/linkage_overlap_by_year.csv), [linkage_specialty_crosstab.csv](report/qa/linkage_specialty_crosstab.csv).

**Routes, in order:**
1. **direct:** the record's own NPI (PY2015+), Luhn-valid (D17). 132.8M records.
2. **supplement:** profile ID → Profile Supplement NPI, with 3,064 merged profiles resolved through the mapping table. 14.3M records.
3. **learned:** profile ID → the NPI that the same profile carries in its PY2015+ records. 1.02M records. This route agrees with the supplement for all but 2 of the ~1.68M profiles found in both; the 11 profiles with two or more NPIs are not used.

That leaves 233K records unlinked (0.16%). Teaching hospitals (530K records) are out of scope.

**Match rates** (share of records linked to an NPI):

| Program year | MD/DO | NP | PA | Other (dentists, optometrists, podiatrists…) |
|---|---|---|---|---|
| 2013 | 98.5% | — | — | 96.7% |
| 2014 | 99.3% | — | — | 97.9% |
| 2015–2020 | 99.94–99.97% | — | — | 99.8–99.9% |
| 2021–2025 | 99.96–99.97% | 99.83–99.99% | 99.97–99.99% | 99.75–99.93% |

NPs and PAs are covered recipients only from PY2021, so before that they have no records (D10).

**Overlap with Part D** (descriptive: "ever" means any program year 2013–2025, so these shares say nothing about timing):

| | 2013 | 2016 | 2019 | 2022 | 2024 |
|---|---|---|---|---|---|
| GLP-1 30-day fills from NPIs that ever appear in Open Payments | 95.6% | 96.5% | 95.7% | 94.5% | 93.3% |
| … from NPIs that ever get a GLP-1 payment | 87.8% | 87.8% | 84.4% | 80.6% | 77.6% |
| GLP-1 prescribers (≥ 11 claims) ever paid for a GLP-1 | 81% | 81% | 74% | 69% | 63% |
| GLP-1 promotional $ to NPIs ever in Part D | 95.6% | 96.0% | 97.9% | 98.4% | 97.7% |
| … to NPIs in Part D that same year | 93.4% | 91.8% | 95.2% | 95.4% | 93.4% |

1.86M NPIs are linked; 1.34M (72%) appear in Part D. 320K NPIs ever received a GLP-1 payment: 294K appear in Part D, and 159K have at least one GLP-1 row with ≥ 11 claims. Unlinked GLP-1 promotional $ total $2.4M (0.5%).

**Specialty agreement:** for the 1.34M NPIs in both sources, the Open Payments specialty group matches the Part D group for **91.5%**. That rises to 94.1% for GLP-1 prescribers; for Part D endocrinologists it is 90.5%. Open Payments specialties come from the recipient's taxonomy (grouping|classification|specialization); Part D uses CMS's per-year prescriber type. Most disagreements are primary care vs subspecialty: 30.1K are primary care in Open Payments but other physician in Part D, and 29.4K the reverse. Other notable ones: 2.3K are endocrinologists in Open Payments but primary care in Part D, and 5.6K the same for cardiologists. The analysis uses the Part D type (P05); P10 carries the disagreement flag.

### Linkage failure modes

1. **PY2013–14 profiles missing from the current Profile Supplement** (profiles never paid after 2014): 159K records unlinked. These physicians have no 2015+ records with an NPI, so they cannot be misassigned to a 2015–2024 first-payment cohort. The cost is small: missing 2013–14 pre-period payments for people who were not paid later anyway.
2. **Merged profiles:** 3,064 secondary profile IDs, and 3,096 NPIs with several profile IDs. Both are resolved to one NPI.
3. **Invalid NPIs** (14 NPIs fail the Luhn check, D17): linked through the profile ID, leaving 4 records unlinked.
4. **Direct and profile routes disagree:** 36 records. The direct NPI wins.
5. **Paid but not in Part D:** 28% of linked NPIs never have a Part D row (≥ 11 claims of any drug). They are surgeons, dentists, low-volume or non-Medicare prescribers, or prescribers whose every row is suppressed. In the panel they are "absent from Part D", not zero (P10).
6. **Specialty conflicts** (8.5%): different sources and dates; flagged, not resolved.
7. **No NPPES** (the download was still down): entity type, deactivation dates and practice location were not cross-checked. The DAC (P05) gives practice and specialty for 2026 only.
