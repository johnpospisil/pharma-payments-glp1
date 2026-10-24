"""Payment measures (P09): NPI x year x brand exposure tables.

One row per (record, brand) is built first (`record_brand`), from every linked,
non-teaching-hospital General Payments record that names an in-scope product
(drug_name_map.csv; name-less slots recovered through drug_ndc_map.csv). Everything else
aggregates it. Conventions (CLAUDE.md decisions):

    contacts   every record naming the brand, any nature and any amount (D12, D16)
    dollars    promotional natures only (D16), amount > 0 (D12)
    D8         payments naming several products, three rules side by side:
                 full   each named brand gets the whole amount
                 split  amount x (brand's slots / all product slots)   [sums to the total]
                 first  only the first-listed product gets the amount
               contacts count for every named brand under 'full' and 'split', and only for
               the first-listed product under 'first'
    D21        payments naming no product go to no brand; they count only in npi_maker_year

Outputs (PARQUET_DIR/payments/): record_brand, npi_brand_year, npi_brand_first,
npi_class_year, npi_maker_year, npi_flags. QA (report/qa/): payments.json,
payments_d8_comparison.csv, payments_cohorts.csv, payments_by_brand_year.csv.

    python -m ppg.build.payments
"""

from __future__ import annotations

import json

import pandas as pd

from ppg import config
from ppg.build.drug_map import GLP1_CLASSES, ndc_key
from ppg.build.linkage import RECORDS
from ppg.disclosure import mask_small
from ppg.ingest.quality import MAKERS, NON_PROMOTIONAL, OP, connect

OUT = config.PARQUET_DIR / "payments"
_TABLES = ("record_brand", "npi_brand_year", "npi_brand_first", "npi_class_year",
           "npi_maker_year", "npi_flags")  # fmt: skip
T = {n: f"'{OUT}/{n}.parquet'" for n in _TABLES}
PARTD_PROVIDER = (
    f"read_parquet('{config.PARQUET_DIR}/partd/by_provider/*/*.parquet', hive_partitioning = true)"
)

SPEAKER = (
    "Compensation for services other than consulting, including serving as faculty or as a "
    "speaker at a venue other than a continuing education program",
    "Compensation for serving as faculty or as a speaker for a non-accredited and noncertified "
    "continuing education program",
    "Compensation for serving as faculty or as a speaker for a medical education program",
    "Compensation for serving as faculty or as a speaker for an accredited or certified "
    "continuing education program",
)
NATURE_GROUP = f"""CASE
    WHEN nature_of_payment IN {NON_PROMOTIONAL} THEN 'non_promotional'
    WHEN nature_of_payment = 'Food and Beverage' THEN 'food_beverage'
    WHEN nature_of_payment IN {SPEAKER} THEN 'speaker'
    WHEN nature_of_payment = 'Consulting Fee' THEN 'consulting'
    WHEN nature_of_payment = 'Travel and Lodging' THEN 'travel'
    WHEN nature_of_payment = 'Education' THEN 'education'
    ELSE 'other_promotional' END"""  # other: gifts, honoraria, entertainment
PROMO_GROUPS = ("food_beverage", "speaker", "consulting", "travel", "education",
                "other_promotional")  # fmt: skip
MAKER_CASE = "CASE " + " ".join(
    f"WHEN manufacturer_name ILIKE '%{pat}%' THEN '{label}'" for label, pat in MAKERS.items()
) + " WHEN manufacturer_name ILIKE '%genzyme%' THEN 'Sanofi' END"  # fmt: skip


def _promo(col: str, rule: str = "") -> str:
    w = {"": "", "first": " AND first_listed"}[rule]
    return f"sum({col}) FILTER (WHERE promotional AND amount_usd > 0{w})"


def build_record_brand(con) -> None:
    m = pd.read_csv(config.REFERENCE_DIR / "drug_name_map.csv")
    m = m[m.brand.notna()][["raw_name", "brand", "molecule", "drug_class"]]
    n = pd.read_csv(config.REFERENCE_DIR / "drug_ndc_map.csv", dtype={"ndc9": str})
    n = n.merge(m.drop_duplicates("brand")[["brand", "molecule", "drug_class"]], on="brand")
    con.register("name_map", m)
    nameless = con.execute(f"""SELECT DISTINCT p.ndc FROM (SELECT unnest(products) AS p FROM {OP})
                               WHERE p.name IS NULL AND p.ndc IS NOT NULL""").df()
    nameless["ndc9"] = nameless.ndc.map(ndc_key)
    n = nameless.merge(n[["ndc9", "brand", "molecule", "drug_class"]], on="ndc9")
    con.register("ndc_map", n[["ndc", "brand", "molecule", "drug_class"]])
    OUT.mkdir(parents=True, exist_ok=True)
    con.execute(f"""
        COPY (
            WITH u AS (
                SELECT o.record_id, o.program_year, o.payment_date, o.amount_usd,
                       o.nature_of_payment, o.manufacturer_name, len(o.products) AS nprod,
                       list_min(list_transform(o.products, lambda p: p.slot)) AS min_slot,
                       unnest(o.products) AS p
                FROM {OP} o WHERE len(o.products) > 0),
            s AS (
                SELECT u.*, coalesce(nm.brand, nd.brand) AS brand,
                       coalesce(nm.molecule, nd.molecule) AS molecule,
                       coalesce(nm.drug_class, nd.drug_class) AS drug_class,
                       nm.brand IS NULL AS via_ndc
                FROM u LEFT JOIN name_map nm ON nm.raw_name = u.p.name
                LEFT JOIN ndc_map nd ON u.p.name IS NULL AND nd.ndc = u.p.ndc)
            SELECT s.record_id, s.program_year, r.npi_linked AS npi, r.recipient_class,
                   s.payment_date, s.manufacturer_name, {MAKER_CASE} AS maker,
                   s.nature_of_payment, {NATURE_GROUP} AS nature_group,
                   s.nature_of_payment NOT IN {NON_PROMOTIONAL} AS promotional,
                   s.amount_usd, s.nprod, s.brand, any_value(s.molecule) AS molecule,
                   any_value(s.drug_class) AS drug_class,
                   count(*) AS brand_slots, bool_or(s.p.slot = s.min_slot) AS first_listed,
                   bool_or(s.via_ndc) AS via_ndc
            FROM s JOIN {RECORDS} r USING (program_year, record_id)
            WHERE s.brand IS NOT NULL AND r.npi_linked IS NOT NULL
            GROUP BY ALL
        ) TO {T["record_brand"]} (FORMAT parquet)""")


def build_tables(con) -> None:
    rb = T["record_brand"]
    split = "amount_usd * brand_slots / nprod"
    by_nature = ",\n".join(
        f"sum({split}) FILTER (WHERE nature_group = '{g}' AND amount_usd > 0) AS usd_{g}"
        for g in PROMO_GROUPS
    )
    con.execute(f"""
        COPY (
            SELECT npi, program_year AS year, brand, any_value(molecule) AS molecule,
                   any_value(drug_class) AS drug_class,
                   count(*) AS contacts,
                   count(*) FILTER (WHERE promotional) AS promo_contacts,
                   count(*) FILTER (WHERE first_listed) AS contacts_first_listed,
                   coalesce({_promo("amount_usd")}, 0) AS usd_full,
                   coalesce({_promo(split)}, 0) AS usd_split,
                   coalesce({_promo("amount_usd", "first")}, 0) AS usd_first,
                   {by_nature},
                   sum({split}) FILTER (WHERE NOT promotional AND amount_usd > 0)
                       AS usd_non_promotional,
                   count(*) FILTER (WHERE nature_group = 'speaker') AS speaker_contacts,
                   min(payment_date) AS first_contact_date,
                   min(payment_date) FILTER (WHERE promotional) AS first_promo_date
            FROM {rb} GROUP BY npi, program_year, brand
        ) TO {T["npi_brand_year"]} (FORMAT parquet)""")
    con.execute(f"""
        COPY (
            SELECT npi, brand, any_value(drug_class) AS drug_class,
                   min(year) FILTER (WHERE promo_contacts > 0) AS first_promo_year,
                   min(first_promo_date) AS first_promo_date,
                   min(year) AS first_contact_year,
                   min(year) FILTER (WHERE contacts_first_listed > 0) AS first_year_first_listed,
                   sum(speaker_contacts) > 0 AS ever_speaker_brand
            FROM {T["npi_brand_year"]} GROUP BY 1, 2
        ) TO {T["npi_brand_first"]} (FORMAT parquet)""")
    class_group = (
        "CASE WHEN drug_class IN ('glp1', 'glp1_insulin_combo') THEN 'glp1' ELSE drug_class END"
    )
    con.execute(f"""
        COPY (
            WITH r AS (SELECT record_id, program_year, npi, {class_group} AS class_group,
                              any_value(promotional) AS promotional,
                              any_value(amount_usd) AS amount_usd,
                              any_value(nature_group) AS nature_group,
                              any_value(payment_date) AS payment_date,
                              sum(brand_slots) / any_value(nprod) AS share
                       FROM {rb} GROUP BY 1, 2, 3, 4)
            SELECT npi, program_year AS year, class_group, count(*) AS contacts,
                   count(*) FILTER (WHERE promotional) AS promo_contacts,
                   coalesce(sum(amount_usd * share) FILTER (WHERE promotional
                                                            AND amount_usd > 0), 0) AS usd_split,
                   count(*) FILTER (WHERE nature_group = 'speaker') AS speaker_contacts,
                   min(payment_date) FILTER (WHERE promotional) AS first_promo_date
            FROM r GROUP BY 1, 2, 3
        ) TO {T["npi_class_year"]} (FORMAT parquet)""")
    con.execute(f"""
        COPY (
            WITH g AS (SELECT DISTINCT record_id, program_year FROM {rb}
                       WHERE drug_class IN {GLP1_CLASSES})
            SELECT r.npi_linked AS npi, o.program_year AS year, {MAKER_CASE} AS maker,
                   count(*) AS contacts,
                   count(*) FILTER (WHERE g.record_id IS NOT NULL) AS glp1_contacts,
                   count(*) FILTER (WHERE len(o.products) = 0) AS no_product_contacts,
                   coalesce(sum(o.amount_usd) FILTER (WHERE o.amount_usd > 0
                       AND o.nature_of_payment NOT IN {NON_PROMOTIONAL}), 0) AS promo_usd,
                   coalesce(sum(o.amount_usd) FILTER (WHERE o.amount_usd > 0
                       AND o.nature_of_payment NOT IN {NON_PROMOTIONAL}
                       AND len(o.products) = 0), 0) AS promo_usd_no_product,
                   min(o.payment_date) FILTER (WHERE o.nature_of_payment NOT IN {NON_PROMOTIONAL})
                       AS first_promo_date
            FROM {OP} o JOIN {RECORDS} r USING (program_year, record_id)
            LEFT JOIN g USING (program_year, record_id)
            WHERE r.npi_linked IS NOT NULL AND ({MAKER_CASE}) IS NOT NULL
            GROUP BY ALL
        ) TO {T["npi_maker_year"]} (FORMAT parquet)""")
    con.execute(f"""
        COPY (
            WITH a AS (SELECT r.npi_linked AS npi, min(o.program_year) AS first_any_year,
                              bool_or(o.nature_of_payment IN {SPEAKER}) AS ever_speaker_any
                       FROM {OP} o JOIN {RECORDS} r USING (program_year, record_id)
                       WHERE r.npi_linked IS NOT NULL GROUP BY 1),
                 g AS (SELECT npi, sum(speaker_contacts) > 0 AS ever_speaker_glp1,
                              min(year) FILTER (WHERE promo_contacts > 0) AS first_glp1_promo_year
                       FROM {T["npi_class_year"]} WHERE class_group = 'glp1' GROUP BY 1)
            SELECT a.*, coalesce(g.ever_speaker_glp1, false) AS ever_speaker_glp1,
                   g.first_glp1_promo_year
            FROM a LEFT JOIN g USING (npi)
        ) TO {T["npi_flags"]} (FORMAT parquet)""")


def d8_comparison(con) -> pd.DataFrame:
    """Per GLP-1 brand: $ and exposure under the three allocation rules."""
    d = con.execute(f"""
        WITH y AS (SELECT brand, sum(usd_full) AS usd_full, sum(usd_split) AS usd_split,
                          sum(usd_first) AS usd_first, sum(contacts) AS contacts,
                          sum(contacts_first_listed) AS contacts_first_listed
                   FROM {T["npi_brand_year"]} WHERE drug_class IN {GLP1_CLASSES} GROUP BY 1),
             f AS (SELECT brand, count(*) FILTER (WHERE first_contact_year IS NOT NULL)
                              AS npis_exposed,
                          count(*) FILTER (WHERE first_year_first_listed IS NOT NULL)
                              AS npis_exposed_first_listed,
                          count(*) FILTER (WHERE first_year_first_listed > first_contact_year)
                              AS first_year_later_under_first_listed
                   FROM {T["npi_brand_first"]} WHERE drug_class IN {GLP1_CLASSES} GROUP BY 1)
        SELECT * FROM y JOIN f USING (brand) ORDER BY usd_split DESC""").df()
    d["split_vs_full"] = d.usd_split / d.usd_full - 1
    d["first_vs_full"] = d.usd_first / d.usd_full - 1
    return d


def cohorts(con) -> pd.DataFrame:
    """Newly exposed prescribers per GLP-1 brand and first promotional-contact year."""
    return con.execute(f"""
        WITH f AS (SELECT b.npi, b.brand, b.first_promo_year AS year
                   FROM {T["npi_brand_first"]} b
                   WHERE b.drug_class IN {GLP1_CLASSES} AND b.first_promo_year IS NOT NULL),
             cls AS (SELECT npi_linked AS npi, arg_max(recipient_class, program_year) AS rc
                     FROM {RECORDS} WHERE npi_linked IS NOT NULL GROUP BY 1),
             pd AS (SELECT DISTINCT prscrbr_npi AS npi, year FROM {PARTD_PROVIDER})
        SELECT f.brand, f.year AS first_promo_year, count(*) AS new_npis,
               count(*) FILTER (WHERE c.rc = 'md_do') AS new_md_do,
               count(*) FILTER (WHERE c.rc = 'md_do' AND p.npi IS NOT NULL)
                   AS new_md_do_in_partd_prior_year
        FROM f LEFT JOIN cls c USING (npi)
        LEFT JOIN pd p ON p.npi = f.npi AND p.year = f.year - 1
        GROUP BY 1, 2 ORDER BY 1, 2""").df()


def by_brand_year(con) -> pd.DataFrame:
    """GLP-1 payments per brand-year, by nature; cells with 1-10 recipients blanked (public)."""
    cols = ", ".join(f"sum(usd_{g}) AS usd_{g}, count(DISTINCT npi) FILTER (WHERE usd_{g} > 0) "
                     f"AS npis_usd_{g}" for g in PROMO_GROUPS)  # fmt: skip
    d = con.execute(f"""
        SELECT brand, year, count(DISTINCT npi) AS npis_paid, sum(contacts) AS contacts,
               sum(usd_split) AS usd_split, {cols},
               count(DISTINCT npi) FILTER (WHERE speaker_contacts > 0) AS npis_speaker
        FROM {T["npi_brand_year"]} WHERE drug_class IN {GLP1_CLASSES}
        GROUP BY 1, 2 ORDER BY 1, 2""").df()
    for g in PROMO_GROUPS:
        d = mask_small(d, f"npis_usd_{g}", [f"usd_{g}"])
    d = mask_small(d, "npis_speaker")
    usd = ["contacts", "usd_split", *(f"usd_{g}" for g in PROMO_GROUPS)]
    return mask_small(
        d, "npis_paid", usd + ["npis_speaker", *(f"npis_usd_{g}" for g in PROMO_GROUPS)]
    )


def summary(con) -> dict:
    q = lambda s: con.execute(s).fetchone()  # noqa: E731
    rb = T["record_brand"]
    tot = q(f"""SELECT count(*), count(DISTINCT record_id), count(*) FILTER (WHERE via_ndc),
                       count(DISTINCT npi)
                FROM {rb} WHERE drug_class IN {GLP1_CLASSES}""")
    usd = q(f"""SELECT sum(usd_split), sum(usd_full), sum(usd_first)
                FROM {T["npi_brand_year"]} WHERE drug_class IN {GLP1_CLASSES}""")
    sums = ", ".join(f"sum(usd_{g})" for g in PROMO_GROUPS)
    nat = q(f"SELECT {sums} FROM {T['npi_brand_year']} WHERE drug_class IN {GLP1_CLASSES}")
    ctl = con.execute(f"""SELECT class_group, count(DISTINCT npi), sum(contacts), sum(usd_split)
                          FROM {T["npi_class_year"]} GROUP BY 1 ORDER BY 1""").fetchall()
    mk = con.execute(f"""SELECT maker, sum(contacts), sum(glp1_contacts), sum(no_product_contacts),
                                sum(promo_usd), sum(promo_usd_no_product)
                         FROM {T["npi_maker_year"]} GROUP BY 1 ORDER BY 1""").fetchall()
    fl = q(f"""SELECT count(*), count(*) FILTER (WHERE ever_speaker_glp1),
                      count(*) FILTER (WHERE ever_speaker_any),
                      count(*) FILTER (WHERE first_glp1_promo_year IS NOT NULL)
               FROM {T["npi_flags"]}""")
    return {
        "glp1_record_brand_rows": tot[0],
        "glp1_records": tot[1],
        "glp1_rows_via_ndc": tot[2],
        "glp1_paid_npis": tot[3],
        "glp1_promo_usd": {"split": usd[0], "full": usd[1], "first": usd[2]},
        "glp1_promo_usd_split_by_nature": dict(zip(PROMO_GROUPS, nat, strict=True)),
        "classes": {c: {"npis": n, "contacts": k, "usd_split": u} for c, n, k, u in ctl},
        "makers": {
            m: {
                "contacts": a,
                "glp1_contacts": b,
                "no_product_contacts": c,
                "promo_usd": d,
                "promo_usd_no_product": e,
            }
            for m, a, b, c, d, e in mk
        },  # fmt: skip
        "npis_with_any_payment": fl[0],
        "npis_ever_glp1_speaker": fl[1],
        "npis_ever_speaker_any": fl[2],
        "npis_ever_glp1_promo": fl[3],
    }


def build() -> dict:
    con = connect()
    con.execute("SET memory_limit = '8GB'")
    con.execute(f"SET temp_directory = '{config.DATA_DIR / 'tmp' / 'duckdb'}'")
    build_record_brand(con)
    build_tables(con)
    config.QA_DIR.mkdir(parents=True, exist_ok=True)
    d8_comparison(con).to_csv(config.QA_DIR / "payments_d8_comparison.csv", index=False,
                              float_format="%.4f")  # fmt: skip
    c = cohorts(con)
    for col in ("new_npis", "new_md_do", "new_md_do_in_partd_prior_year"):
        c = mask_small(c, col)
    c.to_csv(config.QA_DIR / "payments_cohorts.csv", index=False, float_format="%.0f")
    by_brand_year(con).to_csv(config.QA_DIR / "payments_by_brand_year.csv", index=False,
                              float_format="%.2f")  # fmt: skip
    stats = summary(con)
    (config.QA_DIR / "payments.json").write_text(json.dumps(stats, indent=1, default=float))
    return stats


if __name__ == "__main__":
    print(json.dumps(build(), indent=1, default=float))
