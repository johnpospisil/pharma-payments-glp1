# Data card: GLP-1 drug-name map

Maps the free-text product names that drug makers report to CMS Open Payments, and the drug
names in Medicare Part D, to one set of brand keys. Built for *After the Free Lunch* (https://github.com/johnpospisil/pharma-payments-glp1),
released so others can reuse the mapping.

## Files

- `drug_name_map.csv`: 585 Open Payments product strings (program years
  2013–2025). 308
  are mapped to a drug class (GLP-1s, other diabetes drugs, statins, oral anticoagulants,
  inhaled respiratory drugs, or "no product"); 277 were
  reviewed by hand and left out of scope. 25 strings name a GLP-1, covering
  14 brands.
- `partd_drug_map.csv`: 691 Part D brand/generic name pairs mapped to a brand family.

## How strings were matched

First rule that applies: the exact normalised name (case, ®/™, text in parentheses,
strengths and dosage-form words removed); a whole-word brand name inside a longer string; a
generic-molecule rule; "no product discussed / disease state"; a close spelling, which was then
checked by hand. Matching is never by substring ("Victo" is also inside PLUVICTO). Every
unmapped string worth $10,000 or more from a GLP-1 maker, and every near-spelling of a mapped
brand, was reviewed by hand (`reviewer_note`). Methods: none 277, exact 186, non_product 51, contains 45, molecule 20, reviewed 6.

Rules live in code (`src/ppg/build/drug_map.py`, tested in `tests/test_drug_map.py`); this file
is generated from them.

## `drug_name_map.csv`

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

## `partd_drug_map.csv`

| Column | Meaning |
|---|---|
| `brnd_name, gnrc_name` | Part D brand and generic name as published by CMS |
| `brand_family` | Presentations merged into one family (Victoza 2-Pak and 3-Pak -> Victoza; Bydureon, Bydureon Pen and BCise -> Bydureon). Generic liraglutide is kept separate from Victoza |
| `brand, molecule, drug_class, is_glp1, indication, manufacturer` | As above; Part D adds `diabetes_supply` (needles, test strips) to `drug_class` |
| `method` | `exact`, `contains` or `molecule` as above; `minor_brand` = a brand without its own key, kept under its own name |
| `area, candidates` | As above |
| `first_year, last_year` | First and last Part D data year with the name |
| `claims` | Part D claims for the name, all years (prescriber rows with 11+ claims) |

## Known limitations

- 14–30% of GLP-1 makers' promotional dollars (by program year) name no product at
  all and cannot be mapped to a brand.
- A payment naming several products is split equally across them for `usd` and `promo_usd`.
- Covers the June 2026 Open Payments publication; later republications can add or change
  strings.
- Other out-of-scope strings (not from a GLP-1 maker and not a near-spelling, or under
  $10,000) were not reviewed one by one and are not in this file.

## Licence and citation

Source data: CMS Open Payments and Medicare Part D, US government works in the public domain.
This mapping is released under CC0 1.0; the code that builds it is MIT-licensed. Please cite
the repository: John Pospisil (2026), *After the Free Lunch*, https://github.com/johnpospisil/pharma-payments-glp1.
