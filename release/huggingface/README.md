---
license: cc0-1.0
pretty_name: GLP-1 drug-maker payments and prescribing in Medicare Part D, 2013-2024
language:
  - en
tags:
  - medicare
  - open-payments
  - part-d
  - glp-1
  - pharmaceutical-industry
  - health-policy
size_categories:
  - 10K<n<100K
configs:
  - config_name: specialty_state_panel
    data_files: specialty_state_panel/panel.csv
    default: true
  - config_name: brand_visibility
    data_files: specialty_state_panel/brand_visibility.csv
  - config_name: drug_name_map
    data_files: drug_name_map/drug_name_map.csv
  - config_name: partd_drug_map
    data_files: drug_name_map/partd_drug_map.csv
---

# GLP-1 drug-maker payments and prescribing in Medicare Part D, 2013–2024

Two datasets from *After the Free Lunch: Drug-Maker Payments and GLP-1 Brand Choice in Medicare* (John Pospisil, 2026). Article: https://johnpospisil.github.io/pharma-payments-glp1/. Code, method and pre-registration: https://github.com/johnpospisil/pharma-payments-glp1. Built from CMS Open Payments and Medicare Part D; **aggregates only**, no NPIs, names or prescriber-level rows. Not affiliated with or endorsed by CMS.

| Folder | What it is | Data card |
|---|---|---|
| `drug_name_map/` | Open Payments product names and Part D drug names mapped to GLP-1 and comparator brands | [DATACARD.md](drug_name_map/DATACARD.md) |
| `specialty_state_panel/` | Prescribers, promotional payments and GLP-1 prescribing by specialty x state x brand x year, privacy-protected | [DATACARD.md](specialty_state_panel/DATACARD.md) |

Checksums: `SHA256SUMS` (this page itself is the only file not listed in it).

## GLP-1 payments and prescribing by specialty and state

Medicare Part D diabetes prescribers grouped by specialty, state, GLP-1 brand and year
(2013–2024), with the drug makers' promotional payments to them (CMS Open Payments) and their
prescribing of the brand (Medicare Part D). It is the data behind the explorer that accompanies
*After the Free Lunch* (https://github.com/johnpospisil/pharma-payments-glp1), in one table. There are no NPIs, names or prescriber-level rows.

**This is descriptive data.** A group with more payments and more prescribing does not show
that payments changed prescribing: companies pay the doctors who already prescribe, or are
about to prescribe, the most. The article's event study is the attempt to separate the two, and
even it finds that paid doctors' practices were already growing.

### Files

- `panel.csv`: 35,616 rows, one per brand x year x specialty x state.
- `brand_visibility.csv`: the share of each brand's national Part D claims that is visible in
  prescriber rows (the rest sits in hidden rows of 1–10 claims).

### Who is counted

Each year, the prescribers in the study's analysis panel (Part D prescribers who treat diabetes
regularly: at least two years with 11 or more claims of other diabetes drugs), placed in the
state and specialty group of their Part D record that year.

- Specialties: Primary care (MD/DO), Endocrinology, Cardiology, Nephrology, Other physician, Nurse practitioner, Physician assistant, All physicians. "All physicians" is the
  total of the five physician groups. **Nurse practitioners and physician assistants are
  outside every total**, because Open Payments did not cover them before 2021.
- States: 50 states and DC, "Territories and other", and "US" (the national total).
- Brands: Ozempic, Trulicity, Mounjaro, Victoza, Rybelsus, Bydureon, Other GLP-1s. "Other GLP-1s" is
  Soliqua, Byetta, Xultophy, Tanzeum, Adlyxin, liraglutide (generic). The obesity brands (Wegovy, Saxenda, Zepbound)
  are not included. **There is no all-brands total**, on purpose (see below); `prescribers` and
  `partd_claims_all_drugs` describe the group and are the same on every brand's row.

### Columns

| Column | Meaning |
|---|---|
| `brand` | GLP-1 brand, or Other GLP-1s |
| `year` | Calendar year (Part D data year; Open Payments program year) |
| `specialty` | Specialty group key |
| `specialty_label` | Specialty group name |
| `state` | Two-letter state code, `Territories and other`, or `US` |
| `prescribers` | Prescribers in the group that year |
| `partd_claims_all_drugs` | Their total Part D claims, all drugs |
| `paid_prescribers` | Prescribers with at least one promotional payment naming the brand that year |
| `promo_usd` | Promotional dollars naming the brand that year (meals, speaker and consulting fees, travel, education, gifts), whole dollars; a payment naming several drugs is split equally between them |
| `prescribers_11plus_claims` | Prescribers with 11 or more claims of the brand that year |
| `brand_claims_visible` | Claims of the brand in prescriber rows Medicare publishes (rows of 1–10 claims are hidden, so this is a lower bound) |
| `*_status` | For each value column: `shown`; `withheld` (privacy, see below); `not_reported_before_2021` (NP and PA payments, PY2013–2020); `brand_not_in_partd` (the brand was not yet in Part D). The value is blank unless the status is `shown` |

### Privacy protection

The same rules as the explorer, applied before anything is written:

1. Counts of 1 to 10 prescribers are withheld, with the values that depend
   on them. So is a count equal to its group's size when the group has fewer than 20.
2. Dollars are withheld when one prescriber holds more than
   50% of them, in every state cell and in national cells with
   fewer than 50 paid prescribers.
3. Totals are published (All physicians; US), so more cells are withheld until no hidden value
   can be worked out by subtraction, or by solving all the published sums at once: an attacker
   must not be able to narrow a withheld count to a range under 10, or prove more than half of a
   withheld dollar amount. This is checked by a linear-programming attack in the project's
   tests and audit.
4. Every withheld value carries the same status, whatever the reason, because the reason
   itself can point at a person.

Withheld values, all rows: `prescribers` 1,218, `partd_claims_all_drugs` 1,218, `paid_prescribers` 10,237, `promo_usd` 11,666, `prescribers_11plus_claims` 12,389, `brand_claims_visible` 12,412. In
state rows for 2024, 29% of paid-prescriber counts and
32% of dollar values are withheld. Please do not try to recover withheld values,
and do not combine this table with other sources to identify individual prescribers.

### Known limitations

- **Hidden small counts.** Part D hides prescriber-drug rows with fewer than 11 claims, so
  `brand_claims_visible` undercounts, most for shrinking brands (see `brand_visibility.csv`;
  Victoza in 2024 shows 21% of its national claims).
  `prescribers_11plus_claims` is always fully observed.
- **Partial first year.** Open Payments began in August 2013, so 2013 payments cover five
  months.
- **Group membership changes.** Prescribers enter and leave Part D and move between states and
  specialties; groups are not a fixed cohort.
- **Claims are not patients.** A claim is one fill; starting doses are filled more often.
- **Gross promotion, not influence.** `promo_usd` is dominated by speaker fees to a few
  prescribers; the mean per prescriber is not what a typical doctor receives.
- **Ecological data.** State and specialty differences do not describe individual doctors.
- Diabetes-indicated GLP-1s only; Part D excludes weight-loss-only use.

### Licence and citation

Source data: CMS Open Payments and Medicare Part D, US government works in the public domain.
This table is released under CC0 1.0; the code that builds it is MIT-licensed. Please cite the
repository: John Pospisil (2026), *After the Free Lunch*, https://github.com/johnpospisil/pharma-payments-glp1.

## GLP-1 drug-name map

Maps the free-text product names that drug makers report to CMS Open Payments, and the drug
names in Medicare Part D, to one set of brand keys. Built for *After the Free Lunch* (https://github.com/johnpospisil/pharma-payments-glp1),
released so others can reuse the mapping.

### Files

- `drug_name_map.csv`: 585 Open Payments product strings (program years
  2013–2025). 308
  are mapped to a drug class (GLP-1s, other diabetes drugs, statins, oral anticoagulants,
  inhaled respiratory drugs, or "no product"); 277 were
  reviewed by hand and left out of scope. 25 strings name a GLP-1, covering
  14 brands.
- `partd_drug_map.csv`: 691 Part D brand/generic name pairs mapped to a brand family.

### How strings were matched

First rule that applies: the exact normalised name (case, ®/™, text in parentheses,
strengths and dosage-form words removed); a whole-word brand name inside a longer string; a
generic-molecule rule; "no product discussed / disease state"; a close spelling, which was then
checked by hand. Matching is never by substring ("Victo" is also inside PLUVICTO). Every
unmapped string worth $10,000 or more from a GLP-1 maker, and every near-spelling of a mapped
brand, was reviewed by hand (`reviewer_note`). Methods: none 277, exact 186, non_product 51, contains 45, molecule 20, reviewed 6.

Rules live in code (`src/ppg/build/drug_map.py`, tested in `tests/test_drug_map.py`); this file
is generated from them.

### `drug_name_map.csv`

| Column | Meaning |
|---|---|
| `raw_name` | Product name exactly as reported to Open Payments |
| `key` | Normalised name used for matching |
| `brand` | Brand (blank for generic-molecule, class-only and out-of-scope strings) |
| `molecule` | Active ingredient |
| `drug_class` | `glp1`, `glp1_insulin_combo`, `insulin`, `sglt2`, `dpp4`, `metformin`, `sulfonylurea`, `tzd`, `antidiabetic_other`, `statin`, `anticoagulant`, `inhaled_respiratory`, `non_product`; blank = reviewed, out of scope |
| `is_glp1` | True for GLP-1 receptor agonists (tirzepatide included) and GLP-1/insulin combinations |
| `indication` | GLP-1s: `t2d` (diabetes) or `obesity` (Wegovy, Saxenda, Zepbound) |
| `manufacturer` | US marketer of the brand (latest) |
| `method` | `exact`, `contains`, `molecule`, `non_product`, `reviewed` (accepted by hand), `none` (reviewed, out of scope) |
| `area` | Therapeutic area of a `non_product` string (for example diabetes disease state) |
| `candidates` | Brands found when a string names several (then no brand is assigned) |
| `maker_consistent` | Whether the paying companies include the brand's maker |
| `kinds` | Product type reported (Drug, Biological, Device...) |
| `first_year, last_year` | First and last program year the string appears |
| `records` | Payment records naming the string, all years (blank when fewer than 11) |
| `usd` | Dollars, all natures of payment, split equally across a record's products (blank when fewer than 11 records) |
| `promo_usd` | The same for promotional natures only: meals, speaker and consulting fees, travel, education, honoraria, gifts, entertainment (blank when fewer than 11 records) |
| `payers` | Reporting companies, separated by a vertical bar |
| `nearest_alias` | Closest brand spelling, for reviewed strings |
| `reviewer_note` | Note from the hand review |

### `partd_drug_map.csv`

| Column | Meaning |
|---|---|
| `brnd_name, gnrc_name` | Part D brand and generic name as published by CMS |
| `brand_family` | Presentations merged into one family (Victoza 2-Pak and 3-Pak -> Victoza; Bydureon, Bydureon Pen and BCise -> Bydureon). Generic liraglutide is kept separate from Victoza |
| `brand, molecule, drug_class, is_glp1, indication, manufacturer` | As above; Part D adds `diabetes_supply` (needles, test strips) to `drug_class` |
| `method` | `exact`, `contains` or `molecule` as above; `minor_brand` = a brand without its own key, kept under its own name |
| `area, candidates` | As above |
| `first_year, last_year` | First and last Part D data year with the name |
| `claims` | Part D claims for the name, all years (prescriber rows with 11+ claims) |

### Known limitations

- 14–30% of GLP-1 makers' promotional dollars (by program year) name no product at
  all and cannot be mapped to a brand.
- A payment naming several products is split equally across them for `usd` and `promo_usd`.
- Covers the June 2026 Open Payments publication; later republications can add or change
  strings.
- Other out-of-scope strings (not from a GLP-1 maker and not a near-spelling, or under
  $10,000) were not reviewed one by one and are not in this file.

### Licence and citation

Source data: CMS Open Payments and Medicare Part D, US government works in the public domain.
This mapping is released under CC0 1.0; the code that builds it is MIT-licensed. Please cite
the repository: John Pospisil (2026), *After the Free Lunch*, https://github.com/johnpospisil/pharma-payments-glp1.