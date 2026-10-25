# Data card: GLP-1 payments and prescribing by specialty and state

Medicare Part D diabetes prescribers grouped by specialty, state, GLP-1 brand and year
(2013–2024), with the drug makers' promotional payments to them (CMS Open Payments) and their
prescribing of the brand (Medicare Part D). It is the data behind the explorer that accompanies
*After the Free Lunch* (https://github.com/johnpospisil/pharma-payments-glp1), in one table. There are no NPIs, names or prescriber-level rows.

**This is descriptive data.** A group with more payments and more prescribing does not show
that payments changed prescribing: companies pay the doctors who already prescribe, or are
about to prescribe, the most. The article's event study is the attempt to separate the two, and
even it finds that paid doctors' practices were already growing.

## Files

- `panel.csv`: 35,616 rows, one per brand x year x specialty x state.
- `brand_visibility.csv`: the share of each brand's national Part D claims that is visible in
  prescriber rows (the rest sits in hidden rows of 1–10 claims).

## Who is counted

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

## Columns

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

## Privacy protection

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

## Known limitations

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

## Licence and citation

Source data: CMS Open Payments and Medicare Part D, US government works in the public domain.
This table is released under CC0 1.0; the code that builds it is MIT-licensed. Please cite the
repository: John Pospisil (2026), *After the Free Lunch*, https://github.com/johnpospisil/pharma-payments-glp1.
