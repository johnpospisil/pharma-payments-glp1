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
