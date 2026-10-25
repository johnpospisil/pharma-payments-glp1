"""P25 released datasets: the drug-name map and the specialty x state x brand x year panel.

    release/
      README.md, LICENSE.md, SHA256SUMS, manifest.json
      drug_name_map/       drug_name_map.csv, partd_drug_map.csv, DATACARD.md
      specialty_state_panel/  panel.csv, brand_visibility.csv, DATACARD.md

The panel is the P23 explorer's cube (app/data), flattened to one row per brand x year x
specialty x state. It is read from the published JSON, never rebuilt, so the release shows
exactly the values the explorer shows, under the same disclosure control (ppg.app.build, D47):
nothing here can be learned that the explorer does not already show, and the disclosure audit's
LP attack on the explorer covers the release too (ppg.qa.disclosure checks they are identical).
No NPI, name or prescriber-level row is written.

The drug-name map is data/reference/drug_name_map.csv (P07) with the record and dollar totals
blanked for strings with fewer than 11 records, as in the QA tables (ppg.build.drug_map).

    python -m ppg.release.build        -> release/, report/qa/release.json
"""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd

from ppg import config
from ppg.disclosure import mask_small

ROOT = config.REPORT_DIR.parent
APP = ROOT / "app" / "data"
OUT = ROOT / "release"
REPO = "https://github.com/johnpospisil/pharma-payments-glp1"
# explorer metric -> released column (and what it counts)
COLUMNS = {
    "n": "prescribers",
    "tot": "partd_claims_all_drugs",
    "paid": "paid_prescribers",
    "usd": "promo_usd",
    "regular": "prescribers_11plus_claims",
    "claims": "brand_claims_visible",
}
KEYS = ("brand", "year", "specialty", "specialty_label", "state")
STATUS = {0: "shown", -1: "withheld", -4: "not_reported_before_2021", -5: "brand_not_in_partd"}


def panel() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """The explorer cube as a long table: values blank unless shown, a status per value."""
    meta = json.loads((APP / "meta.json").read_text())
    specs = meta["specialties"]
    rows = []
    for b in meta["brands"]:
        cube = json.loads((APP / b["file"]).read_text())
        arr = {m: np.array(cube[m]) for m in COLUMNS}  # [year][specialty][state]
        yi, si, ti = np.indices(arr["n"].shape)
        d = pd.DataFrame({
            "brand": b["key"],
            "year": np.array(meta["years"])[yi.ravel()],
            "specialty": [specs[i]["key"] for i in si.ravel()],
            "specialty_label": [specs[i]["label"] for i in si.ravel()],
            "state": np.array(meta["states"])[ti.ravel()],
        })  # fmt: skip
        for m, col in COLUMNS.items():
            v = arr[m].ravel()
            d[col] = pd.Series(np.where(v >= 0, v, 0), dtype="Int64").where(v >= 0)
            d[f"{col}_status"] = pd.Series(np.where(v >= 0, 0, v)).map(STATUS)
        rows.append(d)
    p = pd.concat(rows, ignore_index=True)
    assert p.filter(like="_status").notna().all().all(), "unknown public code"
    vis = pd.DataFrame(
        [(b["key"], y, v) for b in meta["brands"]
         for y, v in zip(meta["years"], b["visible_pct"], strict=True)],
        columns=["brand", "year", "visible_claims_pct"],
    )  # fmt: skip
    vis["visible_claims_pct"] = vis.visible_claims_pct.astype("Int64")
    return p, vis, meta


def drug_maps() -> tuple[pd.DataFrame, pd.DataFrame]:
    ref = config.REFERENCE_DIR
    op = mask_small(pd.read_csv(ref / "drug_name_map.csv"), "records", ["usd", "promo_usd"])
    return op, pd.read_csv(ref / "partd_drug_map.csv")


def sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _no_product() -> str:
    cov = json.loads((config.QA_DIR / "drug_map.json").read_text())["coverage_glp1_makers"]
    gaps = [100 * (1 - v["share_with_product"]) for v in cov.values()]
    return f"{min(gaps):.0f}–{max(gaps):.0f}%"


def _victoza(meta: dict) -> int:
    return next(b for b in meta["brands"] if b["key"] == "Victoza")["visible_pct"][-1]


def _table(rows: list[tuple[str, str]]) -> str:
    return "\n".join(["| Column | Meaning |", "|---|---|", *(f"| `{c}` | {m} |" for c, m in rows)])


def drug_card(op: pd.DataFrame, pdm: pd.DataFrame) -> str:
    glp = op[op.is_glp1 == True]  # noqa: E712
    methods = ", ".join(f"{k} {v}" for k, v in op.method.value_counts().items())
    return f"""# Data card: GLP-1 drug-name map

Maps the free-text product names that drug makers report to CMS Open Payments, and the drug
names in Medicare Part D, to one set of brand keys. Built for *After the Free Lunch* ({REPO}),
released so others can reuse the mapping.

## Files

- `drug_name_map.csv`: {len(op):,} Open Payments product strings (program years
  {int(op.first_year.min())}–{int(op.last_year.max())}). {int(op.drug_class.notna().sum()):,}
  are mapped to a drug class (GLP-1s, other diabetes drugs, statins, oral anticoagulants,
  inhaled respiratory drugs, or "no product"); {int(op.drug_class.isna().sum()):,} were
  reviewed by hand and left out of scope. {len(glp)} strings name a GLP-1, covering
  {glp.brand.nunique()} brands.
- `partd_drug_map.csv`: {len(pdm):,} Part D brand/generic name pairs mapped to a brand family.

## How strings were matched

First rule that applies: the exact normalised name (case, ®/™, text in parentheses,
strengths and dosage-form words removed); a whole-word brand name inside a longer string; a
generic-molecule rule; "no product discussed / disease state"; a close spelling, which was then
checked by hand. Matching is never by substring ("Victo" is also inside PLUVICTO). Every
unmapped string worth $10,000 or more from a GLP-1 maker, and every near-spelling of a mapped
brand, was reviewed by hand (`reviewer_note`). Methods: {methods}.

Rules live in code (`src/ppg/build/drug_map.py`, tested in `tests/test_drug_map.py`); this file
is generated from them.

## `drug_name_map.csv`

{
        _table(
            [
                ("raw_name", "Product name exactly as reported to Open Payments"),
                ("key", "Normalised name used for matching"),
                (
                    "brand",
                    "Brand (blank for generic-molecule, class-only and out-of-scope strings)",
                ),
                ("molecule", "Active ingredient"),
                (
                    "drug_class",
                    "`glp1`, `glp1_insulin_combo`, `insulin`, `sglt2`, `dpp4`, `metformin`, "
                    "`sulfonylurea`, `tzd`, `antidiabetic_other`, `statin`, `anticoagulant`, "
                    "`inhaled_respiratory`, `non_product`; blank = reviewed, out of scope",
                ),
                (
                    "is_glp1",
                    "True for GLP-1 receptor agonists (tirzepatide included) and GLP-1/insulin "
                    "combinations",
                ),
                ("indication", "GLP-1s: `t2d` (diabetes) or `obesity` (Wegovy, Saxenda, Zepbound)"),
                ("manufacturer", "US marketer of the brand (latest)"),
                (
                    "method",
                    "`exact`, `contains`, `molecule`, `non_product`, "
                    "`reviewed` (accepted by hand), `none` (reviewed, out of scope)",
                ),
                (
                    "area",
                    "Therapeutic area of a `non_product` string (for example diabetes disease "
                    "state)",
                ),
                (
                    "candidates",
                    "Brands found when a string names several (then no brand is assigned)",
                ),
                ("maker_consistent", "Whether the paying companies include the brand's maker"),
                ("kinds", "Product type reported (Drug, Biological, Device...)"),
                ("first_year, last_year", "First and last program year the string appears"),
                (
                    "records",
                    "Payment records naming the string, all years (blank when fewer than 11)",
                ),
                (
                    "usd",
                    "Dollars, all natures of payment, split equally across a record's products "
                    "(blank when fewer than 11 records)",
                ),
                (
                    "promo_usd",
                    "The same for promotional natures only: meals, speaker and consulting fees, "
                    "travel, education, honoraria, gifts, entertainment (blank when fewer than "
                    "11 records)",
                ),
                ("payers", "Reporting companies, separated by a vertical bar"),
                ("nearest_alias", "Closest brand spelling, for reviewed strings"),
                ("reviewer_note", "Note from the hand review"),
            ]
        )
    }

## `partd_drug_map.csv`

{
        _table(
            [
                ("brnd_name, gnrc_name", "Part D brand and generic name as published by CMS"),
                (
                    "brand_family",
                    "Presentations merged into one family (Victoza 2-Pak and 3-Pak -> Victoza; "
                    "Bydureon, Bydureon Pen and BCise -> Bydureon). Generic liraglutide is "
                    "kept separate from Victoza",
                ),
                (
                    "brand, molecule, drug_class, is_glp1, indication, manufacturer",
                    "As above; Part D adds "
                    "`diabetes_supply` (needles, test strips) to `drug_class`",
                ),
                (
                    "method",
                    "`exact`, `contains` or `molecule` as above; "
                    "`minor_brand` = a brand without its own key, kept under its own name",
                ),
                ("area, candidates", "As above"),
                ("first_year, last_year", "First and last Part D data year with the name"),
                (
                    "claims",
                    "Part D claims for the name, all years (prescriber rows with 11+ claims)",
                ),
            ]
        )
    }

## Known limitations

- {_no_product()} of GLP-1 makers' promotional dollars (by program year) name no product at
  all and cannot be mapped to a brand.
- A payment naming several products is split equally across them for `usd` and `promo_usd`.
- Covers the June 2026 Open Payments publication; later republications can add or change
  strings.
- Other out-of-scope strings (not from a GLP-1 maker and not a near-spelling, or under
  $10,000) were not reviewed one by one and are not in this file.

## Licence and citation

Source data: CMS Open Payments and Medicare Part D, US government works in the public domain.
This mapping is released under CC0 1.0; the code that builds it is MIT-licensed. Please cite
the repository: John Pospisil (2026), *After the Free Lunch*, {REPO}.
"""


def panel_card(p: pd.DataFrame, meta: dict) -> str:
    st = {c: p[f"{c}_status"].value_counts() for c in COLUMNS.values()}
    state_rows = p[(p.state != "US") & (p.year == p.year.max())]
    pct = lambda c, d=state_rows: f"{100 * (d[f'{c}_status'] == 'withheld').mean():.0f}%"  # noqa: E731
    years = f"{min(meta['years'])}–{max(meta['years'])}"
    return f"""# Data card: GLP-1 payments and prescribing by specialty and state

Medicare Part D diabetes prescribers grouped by specialty, state, GLP-1 brand and year
({years}), with the drug makers' promotional payments to them (CMS Open Payments) and their
prescribing of the brand (Medicare Part D). It is the data behind the explorer that accompanies
*After the Free Lunch* ({REPO}), in one table. There are no NPIs, names or prescriber-level rows.

**This is descriptive data.** A group with more payments and more prescribing does not show
that payments changed prescribing: companies pay the doctors who already prescribe, or are
about to prescribe, the most. The article's event study is the attempt to separate the two, and
even it finds that paid doctors' practices were already growing.

## Files

- `panel.csv`: {len(p):,} rows, one per brand x year x specialty x state.
- `brand_visibility.csv`: the share of each brand's national Part D claims that is visible in
  prescriber rows (the rest sits in hidden rows of 1–10 claims).

## Who is counted

Each year, the prescribers in the study's analysis panel (Part D prescribers who treat diabetes
regularly: at least two years with 11 or more claims of other diabetes drugs), placed in the
state and specialty group of their Part D record that year.

- Specialties: {", ".join(s["label"] for s in meta["specialties"])}. "All physicians" is the
  total of the five physician groups. **Nurse practitioners and physician assistants are
  outside every total**, because Open Payments did not cover them before 2021.
- States: 50 states and DC, "Territories and other", and "US" (the national total).
- Brands: {", ".join(b["key"] for b in meta["brands"])}. "Other GLP-1s" is
  {", ".join(meta["other_brands"])}. The obesity brands ({", ".join(meta["excluded_brands"])})
  are not included. **There is no all-brands total**, on purpose (see below); `prescribers` and
  `partd_claims_all_drugs` describe the group and are the same on every brand's row.

## Columns

{
        _table(
            [
                ("brand", "GLP-1 brand, or Other GLP-1s"),
                ("year", "Calendar year (Part D data year; Open Payments program year)"),
                ("specialty", "Specialty group key"),
                ("specialty_label", "Specialty group name"),
                ("state", "Two-letter state code, `Territories and other`, or `US`"),
                ("prescribers", "Prescribers in the group that year"),
                ("partd_claims_all_drugs", "Their total Part D claims, all drugs"),
                (
                    "paid_prescribers",
                    "Prescribers with at least one promotional payment naming the brand that year",
                ),
                (
                    "promo_usd",
                    "Promotional dollars naming the brand that year (meals, speaker and "
                    "consulting fees, travel, education, gifts), whole dollars; a payment naming "
                    "several drugs is split equally between them",
                ),
                (
                    "prescribers_11plus_claims",
                    "Prescribers with 11 or more claims of the brand that year",
                ),
                (
                    "brand_claims_visible",
                    "Claims of the brand in prescriber rows Medicare publishes (rows "
                    "of 1–10 claims are hidden, so this is a lower bound)",
                ),
                (
                    "*_status",
                    "For each value column: `shown`; `withheld` (privacy, see below); "
                    "`not_reported_before_2021` (NP and PA payments, PY2013–2020); "
                    "`brand_not_in_partd` (the brand was not yet in Part D). The value is blank "
                    "unless the status is `shown`",
                ),
            ]
        )
    }

## Privacy protection

The same rules as the explorer, applied before anything is written:

1. Counts of 1 to {meta["min_cell"] - 1} prescribers are withheld, with the values that depend
   on them. So is a count equal to its group's size when the group has fewer than 20.
2. Dollars are withheld when one prescriber holds more than
   {round(100 * meta["dominance"])}% of them, in every state cell and in national cells with
   fewer than 50 paid prescribers.
3. Totals are published (All physicians; US), so more cells are withheld until no hidden value
   can be worked out by subtraction, or by solving all the published sums at once: an attacker
   must not be able to narrow a withheld count to a range under 10, or prove more than half of a
   withheld dollar amount. This is checked by a linear-programming attack in the project's
   tests and audit.
4. Every withheld value carries the same status, whatever the reason, because the reason
   itself can point at a person.

Withheld values, all rows: {", ".join(f"`{c}` {st[c].get('withheld', 0):,}" for c in st)}. In
state rows for {max(meta["years"])}, {pct("paid_prescribers")} of paid-prescriber counts and
{pct("promo_usd")} of dollar values are withheld. Please do not try to recover withheld values,
and do not combine this table with other sources to identify individual prescribers.

## Known limitations

- **Hidden small counts.** Part D hides prescriber-drug rows with fewer than 11 claims, so
  `brand_claims_visible` undercounts, most for shrinking brands (see `brand_visibility.csv`;
  Victoza in {max(meta["years"])} shows {_victoza(meta)}% of its national claims).
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
repository: John Pospisil (2026), *After the Free Lunch*, {REPO}.
"""


_FOLDERS = "\n".join([
    "| Folder | What it is | Data card |",
    "|---|---|---|",
    "| `drug_name_map/` | Open Payments product names and Part D drug names mapped to GLP-1 "
    "and comparator brands | [DATACARD.md](drug_name_map/DATACARD.md) |",
    "| `specialty_state_panel/` | Prescribers, promotional payments and GLP-1 prescribing by "
    "specialty x state x brand x year, privacy-protected "
    "| [DATACARD.md](specialty_state_panel/DATACARD.md) |",
])  # fmt: skip

README = f"""# Released datasets

Two datasets from *After the Free Lunch: Drug-Maker Payments and GLP-1 Brand Choice in
Medicare* ({REPO}). Both are built by `make release` from the project's pipeline; neither
contains NPIs, names or prescriber-level rows.

{_FOLDERS}

File sizes, row counts and SHA-256 checksums: `manifest.json` and `SHA256SUMS`
(check with `shasum -a 256 -c SHA256SUMS`). Licence: [LICENSE.md](LICENSE.md).
"""

LICENSE = """# Licence

- **Source data**: CMS Open Payments and Medicare Part D Prescribers files are works of the US
  government and in the public domain.
- **These datasets** (`drug_name_map/`, `specialty_state_panel/`): CC0 1.0 Universal
  (https://creativecommons.org/publicdomain/zero/1.0/). Attribution is appreciated, not
  required.
- **Code** that builds them (the repository): MIT License.

Use of the panel must respect its privacy protection: do not try to recover withheld values or
identify individual prescribers.
"""


def build() -> dict:
    p, vis, meta = panel()
    op, pdm = drug_maps()
    (OUT / "drug_name_map").mkdir(parents=True, exist_ok=True)
    (OUT / "specialty_state_panel").mkdir(parents=True, exist_ok=True)
    files = {
        "drug_name_map/drug_name_map.csv": op,
        "drug_name_map/partd_drug_map.csv": pdm,
        "specialty_state_panel/panel.csv": p,
        "specialty_state_panel/brand_visibility.csv": vis,
    }
    for name, df in files.items():
        df.to_csv(OUT / name, index=False, float_format="%.2f", lineterminator="\n")
    texts = {
        "README.md": README,
        "LICENSE.md": LICENSE,
        "drug_name_map/DATACARD.md": drug_card(op, pdm),
        "specialty_state_panel/DATACARD.md": panel_card(p, meta),
    }
    for name, t in texts.items():
        (OUT / name).write_text(t)
    every = sorted([*files, *texts])
    sums = {f: sha256(OUT / f) for f in every}
    (OUT / "SHA256SUMS").write_text("".join(f"{h}  {f}\n" for f, h in sums.items()))
    manifest = {
        f: {"bytes": (OUT / f).stat().st_size, "sha256": sums[f],
            **({"rows": len(files[f]), "columns": list(files[f].columns)} if f in files else {})}
        for f in every
    }  # fmt: skip
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    summary = {
        "files": {f: {k: v for k, v in m.items() if k != "columns"} for f, m in manifest.items()},
        "panel_status": {c: p[f"{c}_status"].value_counts().to_dict() for c in COLUMNS.values()},
        "drug_map_masked_strings": int(op.records.isna().sum()),
    }
    (config.QA_DIR / "release.json").write_text(json.dumps(summary, indent=1))
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=1))
