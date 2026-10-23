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
