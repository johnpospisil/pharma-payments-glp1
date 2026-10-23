"""Prescriber x GLP-1 brand x year panel (P10).

Three tables in PARQUET_DIR/panel/ (git-ignored; contain NPIs):

    npi_year.parquet     every individual Part D prescriber x year, 2013-2024: state, RUCA,
                         specialty, total volume, claims by drug class (observed rows only),
                         the suppressed-claims gap, payments at class and maker level
    npi_dims.parquet     one row per NPI: modal specialty, years active, diabetes load,
                         practice (DAC), recipient class, sample filters and flags
    panel_brand.parquet  in-sample NPI x GLP-1 brand family x year (from the brand's first
                         Part D year), with the brand outcome, its suppression status, brand
                         payments and the main NPI-year covariates

Suppression status of a brand cell (CLAUDE.md: a missing row is 0-10 claims, never 0):

    observed    the prescriber has a row for the brand (>= 11 claims)
    zero_known  no row, but the prescriber's by-Provider total equals the sum of their drug
                rows, so nothing at all is suppressed: the brand count is exactly 0
    suppressed  no row and some claims are suppressed: 1-10 claims, or 0; `supp_cap` is
                min(10, suppressed total)
    absent      no by-Provider row that year (not in Part D, or under 11 claims in total)
    pre_launch  before the brand's first Part D year, kept because promotion can start
                earlier (Ozempic 2017, Wegovy 2021-22); claims are 0

    python -m ppg.build.panel
"""

from __future__ import annotations

import json

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from ppg import config  # noqa: E402
from ppg.ingest.quality import INK, MUTED, PD, SERIES, SURFACE, connect  # noqa: E402

OUT = config.PARQUET_DIR / "panel"
_P = config.PARQUET_DIR
PROVIDER = f"read_parquet('{_P}/partd/by_provider/*/*.parquet', hive_partitioning = true)"
GEO = f"read_parquet('{_P}/partd/by_geography_drug/*/*.parquet', hive_partitioning = true)"
PAY = {n: f"'{_P}/payments/{n}.parquet'" for n in ("npi_brand_year", "npi_brand_first",
                                                  "npi_class_year", "npi_maker_year",
                                                  "npi_flags")}  # fmt: skip
LINK = f"'{_P}/linkage/npi_specialty.parquet'"
RECORDS = f"read_parquet('{_P}/linkage/op_record_npi/*/*.parquet', hive_partitioning = true)"
YEARS = (2013, 2024)

DM_CLASSES = ("metformin", "sglt2", "dpp4", "sulfonylurea", "tzd", "insulin",
              "antidiabetic_other")  # fmt: skip  # diabetes load excludes GLP-1s (the outcome)
CLASSES = ("glp1", *DM_CLASSES, "statin", "anticoagulant", "inhaled_respiratory",
           "diabetes_supply")  # fmt: skip
PHYSICIAN = ("endocrinology", "primary_care_physician", "cardiology", "nephrology",
             "other_physician")  # fmt: skip
MIN_YEARS = 3  # active in Part D at least this many years
DM_YEAR = 11  # a "diabetes year": >= 11 observed non-GLP-1 antidiabetic claims
MIN_DM_YEARS = 2
HIGH_VOLUME = 250  # median non-GLP-1 antidiabetic claims per active year (D14 subsample)
MAKER_OF = {"Ozempic": "Novo Nordisk", "Rybelsus": "Novo Nordisk", "Wegovy": "Novo Nordisk",
            "Victoza": "Novo Nordisk", "Xultophy": "Novo Nordisk",
            "liraglutide (generic)": None, "Trulicity": "Eli Lilly", "Mounjaro": "Eli Lilly",
            "Zepbound": "Eli Lilly", "Byetta": "AstraZeneca", "Bydureon": "AstraZeneca",
            "Adlyxin": "Sanofi", "Soliqua": "Sanofi", "Tanzeum": None}  # fmt: skip


def register_maps(con) -> None:
    pdm = pd.read_csv(config.REFERENCE_DIR / "partd_drug_map.csv")
    pdm["cls"] = pdm.drug_class.replace({"glp1_insulin_combo": "glp1"})
    con.register("dmap", pdm[["brnd_name", "gnrc_name", "brand_family", "molecule", "cls"]])
    sg = pd.read_csv(config.REFERENCE_DIR / "specialty_groups.csv")
    con.register("sgroups", sg[["prscrbr_type", "specialty_group"]])
    mk = pd.DataFrame([{"brand": b, "maker": m} for b, m in MAKER_OF.items()])
    con.register("brand_maker", mk)


def build_npi_year(con) -> None:
    cls_cols = ",\n".join(
        f"coalesce(sum(d.tot_clms) FILTER (WHERE m.cls = '{c}'), 0) AS clms_{c}" for c in CLASSES
    )
    con.execute(f"""
        CREATE OR REPLACE TABLE drug_rows AS
        SELECT d.year, d.prscrbr_npi AS npi, sum(d.tot_clms) AS clms_rows,
               {cls_cols},
               coalesce(sum(d.tot_30day_fills) FILTER (WHERE m.cls = 'glp1'), 0) AS fills_glp1
        FROM {PD} d LEFT JOIN dmap m USING (brnd_name, gnrc_name)
        GROUP BY 1, 2""")
    pay = f"""
        LEFT JOIN (SELECT npi, year,
                          sum(contacts) FILTER (WHERE class_group = 'glp1') AS glp1_contacts,
                          sum(usd_split) FILTER (WHERE class_group = 'glp1') AS glp1_usd,
                          sum(contacts) FILTER (WHERE class_group = 'anticoagulant')
                              AS anticoag_contacts,
                          sum(usd_split) FILTER (WHERE class_group = 'anticoagulant')
                              AS anticoag_usd,
                          sum(contacts) FILTER (WHERE class_group = 'inhaled_respiratory')
                              AS inhaled_contacts,
                          sum(usd_split) FILTER (WHERE class_group = 'inhaled_respiratory')
                              AS inhaled_usd
                   FROM {PAY["npi_class_year"]} GROUP BY 1, 2) c USING (npi, year)"""
    OUT.mkdir(parents=True, exist_ok=True)
    con.execute(f"""
        COPY (
            SELECT p.year, p.prscrbr_npi AS npi, p.prscrbr_ent_cd AS entity,
                   p.prscrbr_state_abrvtn AS state, p.prscrbr_zip5 AS zip5,
                   try_cast(p.prscrbr_ruca AS DOUBLE) AS ruca, p.prscrbr_type,
                   coalesce(g.specialty_group, 'other_nonphysician') AS specialty_group,
                   p.tot_clms, p.tot_30day_fills, p.tot_benes, p.tot_drug_cst,
                   p.bene_avg_risk_scre AS bene_risk, p.bene_avg_age,
                   coalesce(r.clms_rows, 0) AS clms_rows,
                   greatest(p.tot_clms - coalesce(r.clms_rows, 0), 0) AS clms_suppressed,
                   {", ".join(f"coalesce(r.clms_{c}, 0) AS clms_{c}" for c in CLASSES)},
                   coalesce(r.fills_glp1, 0) AS fills_glp1,
                   {" + ".join(f"coalesce(r.clms_{c}, 0)" for c in DM_CLASSES)} AS dm_load,
                   coalesce(c.glp1_contacts, 0) AS glp1_contacts,
                   coalesce(c.glp1_usd, 0) AS glp1_usd,
                   coalesce(c.anticoag_contacts, 0) AS anticoag_contacts,
                   coalesce(c.anticoag_usd, 0) AS anticoag_usd,
                   coalesce(c.inhaled_contacts, 0) AS inhaled_contacts,
                   coalesce(c.inhaled_usd, 0) AS inhaled_usd
            FROM {PROVIDER} p
            LEFT JOIN drug_rows r ON r.npi = p.prscrbr_npi AND r.year = p.year
            LEFT JOIN sgroups g ON g.prscrbr_type = p.prscrbr_type
            {pay.replace("USING (npi, year)", "ON c.npi = p.prscrbr_npi AND c.year = p.year")}
            WHERE p.year BETWEEN {YEARS[0]} AND {YEARS[1]}
        ) TO '{OUT}/npi_year.parquet' (FORMAT parquet)""")


def build_npi_dims(con) -> None:
    ny = f"'{OUT}/npi_year.parquet'"
    con.execute(f"""
        COPY (
            WITH a AS (
                SELECT npi, any_value(entity) AS entity, count(*) AS years_active,
                       min(year) AS first_year, max(year) AS last_year,
                       any_value(modal_specialty) AS specialty_group,
                       any_value(modal_state) AS state,
                       count(*) FILTER (WHERE dm_load >= {DM_YEAR}) AS dm_years,
                       median(dm_load) AS dm_load_median, sum(dm_load) AS dm_load_total,
                       sum(clms_glp1) AS glp1_claims_total
                FROM {ny} y
                JOIN (SELECT npi, arg_max(specialty_group, n * 10000 + last) AS modal_specialty
                      FROM (SELECT npi, specialty_group, count(*) AS n, max(year) AS last
                            FROM {ny} GROUP BY 1, 2) GROUP BY 1) USING (npi)
                JOIN (SELECT npi, arg_max(state, n * 10000 + last) AS modal_state
                      FROM (SELECT npi, state, count(*) AS n, max(year) AS last
                            FROM {ny} GROUP BY 1, 2) GROUP BY 1) USING (npi)
                GROUP BY 1),  -- modal value; ties go to the latest year (deterministic)
            dac AS (
                SELECT npi, arg_max(org_pac_id, n * 1e7 + coalesce(num_org_mem, 0)) AS org_pac_id,
                       arg_max(num_org_mem, n * 1e7 + coalesce(num_org_mem, 0)) AS org_size,
                       any_value(cred) AS dac_cred
                FROM (SELECT npi, org_pac_id, num_org_mem, any_value(cred) AS cred, count(*) AS n
                      FROM '{_P}/reference/dac.parquet' WHERE org_pac_id IS NOT NULL
                      GROUP BY 1, 2, 3)
                GROUP BY 1),
            rc AS (SELECT npi_linked AS npi, arg_max(recipient_class, program_year) AS op_class
                   FROM {RECORDS} WHERE npi_linked IS NOT NULL GROUP BY 1)
            SELECT a.*, dac.org_pac_id, dac.org_size, rc.op_class,
                   s.agree AS specialty_agrees_op,
                   f.first_any_year AS first_payment_year_any,
                   f.first_glp1_promo_year, coalesce(f.ever_speaker_glp1, false)
                       AS ever_speaker_glp1,
                   -- sample filters, in order (see sample_flow)
                   a.entity = 'I' AS f1_individual,
                   a.specialty_group <> 'other_nonphysician' AS f2_prescriber_specialty,
                   a.years_active >= {MIN_YEARS} AS f3_active_years,
                   a.dm_years >= {MIN_DM_YEARS} AS f4_diabetes_prescriber,
                   a.specialty_group IN {PHYSICIAN} AS physician,
                   a.dm_load_median >= {HIGH_VOLUME} AS high_volume
            FROM a LEFT JOIN dac USING (npi) LEFT JOIN rc USING (npi)
            LEFT JOIN {LINK} s USING (npi) LEFT JOIN {PAY["npi_flags"]} f USING (npi)
        ) TO '{OUT}/npi_dims.parquet' (FORMAT parquet)""")


IN_SAMPLE = (
    "f1_individual AND f2_prescriber_specialty AND f3_active_years AND f4_diabetes_prescriber"
)


def build_panel_brand(con) -> None:
    dims, ny = f"'{OUT}/npi_dims.parquet'", f"'{OUT}/npi_year.parquet'"
    con.execute(f"""
        CREATE OR REPLACE TABLE launch AS
        SELECT m.brand_family AS brand, any_value(m.molecule) AS molecule,
               min(g.year) AS first_partd_year
        FROM {GEO} g JOIN dmap m USING (brnd_name, gnrc_name)
        WHERE g.prscrbr_geo_lvl = 'National' AND m.cls = 'glp1' GROUP BY 1""")
    # payments can start before a brand's first Part D year (Ozempic 2017, Wegovy 2021-22)
    con.execute(f"""
        ALTER TABLE launch ADD COLUMN first_payment_year INTEGER;
        UPDATE launch SET first_payment_year = p.y
        FROM (SELECT brand, min(year) AS y FROM {PAY["npi_brand_year"]} GROUP BY 1) p
        WHERE p.brand = launch.brand""")
    # normalise the molecule label (Part D generic names vary: "Exenatide Microspheres")
    con.execute("""
        UPDATE launch SET molecule = CASE
            WHEN brand IN ('Ozempic', 'Rybelsus', 'Wegovy') THEN 'semaglutide'
            WHEN brand IN ('Mounjaro', 'Zepbound') THEN 'tirzepatide'
            WHEN brand IN ('Victoza', 'liraglutide (generic)', 'Saxenda') THEN 'liraglutide'
            WHEN brand IN ('Byetta', 'Bydureon') THEN 'exenatide'
            WHEN brand = 'Trulicity' THEN 'dulaglutide'
            WHEN brand = 'Adlyxin' THEN 'lixisenatide'
            WHEN brand = 'Tanzeum' THEN 'albiglutide'
            WHEN brand = 'Soliqua' THEN 'insulin glargine/lixisenatide'
            WHEN brand = 'Xultophy' THEN 'insulin degludec/liraglutide' END""")
    con.execute(f"""
        CREATE OR REPLACE TABLE brand_rows AS
        SELECT d.year, d.prscrbr_npi AS npi, m.brand_family AS brand,
               sum(d.tot_clms) AS claims, sum(d.tot_30day_fills) AS fills,
               sum(d.tot_benes) AS benes, sum(d.tot_drug_cst) AS cost
        FROM {PD} d JOIN dmap m USING (brnd_name, gnrc_name)
        WHERE m.cls = 'glp1' GROUP BY 1, 2, 3""")
    groups = ("food_beverage", "speaker", "consulting", "travel", "education")
    con.execute(f"""
        COPY (
            WITH s AS (SELECT npi FROM {dims} WHERE {IN_SAMPLE}),
                 grid AS (SELECT s.npi, l.brand, l.molecule, l.first_partd_year, y.year
                          FROM s CROSS JOIN launch l
                          CROSS JOIN range({YEARS[0]}, {YEARS[1]} + 1) y(year)
                          WHERE y.year >= least(l.first_partd_year,
                                                coalesce(l.first_payment_year, 9999))),
                 mol AS (SELECT f.npi, l.molecule, min(f.first_promo_year) AS first_promo_year
                         FROM {PAY["npi_brand_first"]} f JOIN launch l USING (brand)
                         GROUP BY 1, 2)
            SELECT g.npi, g.year, g.brand, g.molecule, bm.maker, g.first_partd_year,
                   CASE WHEN g.year < g.first_partd_year THEN 'pre_launch'
                        WHEN y.npi IS NULL THEN 'absent'
                        WHEN b.npi IS NOT NULL THEN 'observed'
                        WHEN y.clms_suppressed = 0 THEN 'zero_known'
                        ELSE 'suppressed' END AS status,
                   CASE WHEN b.npi IS NOT NULL THEN b.claims
                        WHEN g.year < g.first_partd_year THEN 0
                        WHEN y.npi IS NOT NULL AND y.clms_suppressed = 0 THEN 0 END AS claims,
                   CASE WHEN b.npi IS NOT NULL THEN b.fills
                        WHEN g.year < g.first_partd_year THEN 0
                        WHEN y.npi IS NOT NULL AND y.clms_suppressed = 0 THEN 0 END AS fills,
                   b.benes, b.cost,
                   CASE WHEN b.npi IS NULL AND y.npi IS NOT NULL
                             AND g.year >= g.first_partd_year
                        THEN least(10, y.clms_suppressed) END AS supp_cap,
                   -- brand payments (D8: contacts full credit, $ equal split; D22)
                   coalesce(p.contacts, 0) AS contacts,
                   coalesce(p.promo_contacts, 0) AS promo_contacts,
                   coalesce(p.contacts_first_listed, 0) AS contacts_first_listed,
                   coalesce(p.usd_split, 0) AS usd,
                   coalesce(p.usd_first, 0) AS usd_first_listed,
                   {", ".join(f"coalesce(p.usd_{n}, 0) AS usd_{n}" for n in groups)},
                   coalesce(p.speaker_contacts, 0) AS speaker_contacts,
                   f.first_promo_year, f.first_year_first_listed,
                   f.first_promo_date, mol.first_promo_year AS first_promo_year_molecule,
                   -- maker-level exposure (D-2, D21)
                   coalesce(mk.contacts, 0) AS maker_contacts,
                   coalesce(mk.promo_usd, 0) AS maker_usd,
                   coalesce(mk.no_product_contacts, 0) AS maker_no_product_contacts,
                   -- NPI-year covariates
                   y.specialty_group, y.state, y.ruca, y.tot_clms, y.dm_load,
                   y.clms_glp1 AS glp1_claims_all, y.fills_glp1 AS glp1_fills_all,
                   y.clms_statin, y.clms_anticoagulant, y.glp1_contacts AS glp1_contacts_all,
                   y.anticoag_contacts, y.anticoag_usd
            FROM grid g
            LEFT JOIN {ny} y ON y.npi = g.npi AND y.year = g.year
            LEFT JOIN brand_rows b ON b.npi = g.npi AND b.year = g.year AND b.brand = g.brand
            LEFT JOIN brand_maker bm ON bm.brand = g.brand
            LEFT JOIN {PAY["npi_brand_year"]} p
                   ON p.npi = g.npi AND p.year = g.year AND p.brand = g.brand
            LEFT JOIN {PAY["npi_brand_first"]} f ON f.npi = g.npi AND f.brand = g.brand
            LEFT JOIN mol ON mol.npi = g.npi AND mol.molecule = g.molecule
            LEFT JOIN {PAY["npi_maker_year"]} mk
                   ON mk.npi = g.npi AND mk.year = g.year AND mk.maker = bm.maker
            ORDER BY g.brand, g.npi, g.year
        ) TO '{OUT}/panel_brand.parquet' (FORMAT parquet, ROW_GROUP_SIZE 1000000)""")


def sample_flow(con) -> pd.DataFrame:
    dims, ny = f"'{OUT}/npi_dims.parquet'", f"'{OUT}/npi_year.parquet'"
    steps = [
        ("All Part D prescribers, 2013-2024", "TRUE"),
        ("Individuals (not organisations)", "f1_individual"),
        ("Prescribing specialty (not dentist, optometrist, pharmacist...)",
         "f1_individual AND f2_prescriber_specialty"),
        (f"Active in Part D >= {MIN_YEARS} years",
         "f1_individual AND f2_prescriber_specialty AND f3_active_years"),
        (f"Diabetes prescriber (>= {MIN_DM_YEARS} years with >= {DM_YEAR} non-GLP-1 "
         "antidiabetic claims)", IN_SAMPLE),
        ("  of which physicians (primary sample, D10)", f"{IN_SAMPLE} AND physician"),
        ("  of which high-volume (median >= 250 diabetes claims/yr, D14)",
         f"{IN_SAMPLE} AND physician AND high_volume"),
    ]  # fmt: skip
    rows = []
    for label, cond in steps:
        r = con.execute(f"""
            SELECT count(*), sum(years_active), sum(glp1_claims_total),
                   count(*) FILTER (WHERE first_glp1_promo_year IS NOT NULL)
            FROM {dims} WHERE {cond}""").fetchone()
        rows.append({"step": label, "npis": r[0], "npi_years": r[1], "glp1_claims": r[2],
                     "npis_ever_glp1_paid": r[3]})  # fmt: skip
    df = pd.DataFrame(rows)
    df["share_glp1_claims"] = df.glp1_claims / df.glp1_claims.iloc[0]
    tot = con.execute(f"SELECT sum(clms_glp1) FROM {ny}").fetchone()[0]
    assert abs(df.glp1_claims.iloc[0] - tot) < 1
    return df


def flow_chart(flow: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8.6, 6.2), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    ax.axis("off")
    n = len(flow)
    for i, r in enumerate(flow.itertuples()):
        y = n - 1 - i
        sub = r.step.startswith("  ")
        x0 = 0.08 if sub else 0.0
        ax.add_patch(plt.Rectangle((x0, y - 0.38), 0.62 - x0, 0.76, fc=SURFACE,
                                   ec=SERIES if not sub else MUTED, lw=1.2))  # fmt: skip
        ax.text(x0 + 0.015, y + 0.12, r.step.strip(), fontsize=8.6, color=INK, va="center")
        ax.text(x0 + 0.015, y - 0.16,
                f"{r.npis:,.0f} prescribers · {r.npi_years:,.0f} prescriber-years",
                fontsize=8, color=MUTED, va="center")  # fmt: skip
        ax.text(0.65, y, f"{r.share_glp1_claims:.1%} of GLP-1 claims\n"
                f"{r.npis_ever_glp1_paid:,.0f} ever paid for a GLP-1",
                fontsize=8, color=MUTED, va="center")  # fmt: skip
        if i and not sub:
            ax.annotate("", (0.31, y + 0.38), (0.31, y + 0.62),
                        arrowprops={"arrowstyle": "->", "color": MUTED, "lw": 0.8})  # fmt: skip
    ax.set_xlim(0, 0.95)
    ax.set_ylim(-0.6, n - 0.4)
    ax.set_title("Analysis sample: prescribers kept at each filter", loc="left", fontsize=11,
                 color=INK)  # fmt: skip
    note = (
        "GLP-1 claims are observed rows (>= 11 claims), 2013–2024. "
        "Source: CMS Part D Prescribers; Open Payments."
    )
    fig.text(0.01, 0.01, note, fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    config.FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(config.FIGURE_DIR / "p10_sample_flow.png", dpi=160, facecolor=SURFACE)


def suppression_by_brand_year(con) -> pd.DataFrame:
    pb, dims = f"'{OUT}/panel_brand.parquet'", f"'{OUT}/npi_dims.parquet'"
    return con.execute(f"""
        SELECT b.brand, b.year, count(*) AS cells,
               avg((b.status = 'observed')::INT) AS observed,
               avg((b.status = 'zero_known')::INT) AS zero_known,
               avg((b.status = 'suppressed')::INT) AS suppressed,
               avg((b.status = 'absent')::INT) AS absent,
               avg((b.status = 'suppressed')::INT) FILTER (WHERE d.physician AND d.high_volume)
                   AS suppressed_high_volume,
               avg((b.status = 'observed')::INT) FILTER (WHERE d.physician AND d.high_volume)
                   AS observed_high_volume
        FROM {pb} b JOIN {dims} d USING (npi) GROUP BY 1, 2 ORDER BY 1, 2""").df()


def build() -> dict:
    con = connect()
    con.execute("SET memory_limit = '10GB'")
    con.execute(f"SET temp_directory = '{config.DATA_DIR / 'tmp' / 'duckdb'}'")
    register_maps(con)
    build_npi_year(con)
    build_npi_dims(con)
    build_panel_brand(con)
    flow = sample_flow(con)
    flow_chart(flow)
    supp = suppression_by_brand_year(con)
    config.QA_DIR.mkdir(parents=True, exist_ok=True)
    flow.to_csv(config.QA_DIR / "panel_sample_flow.csv", index=False, float_format="%.4f")
    supp.to_csv(config.QA_DIR / "panel_suppression_by_brand_year.csv", index=False,
                float_format="%.4f")  # fmt: skip
    pb = f"'{OUT}/panel_brand.parquet'"
    q = lambda s: con.execute(s).fetchone()  # noqa: E731
    size = q(f"SELECT count(*), count(DISTINCT npi), count(DISTINCT brand) FROM {pb}")
    status = dict(con.execute(f"SELECT status, count(*) FROM {pb} GROUP BY 1").fetchall())
    claims = q(f"""SELECT sum(claims) FILTER (WHERE status = 'observed'),
                          (SELECT sum(clms_glp1) FROM '{OUT}/npi_year.parquet')
                   FROM {pb}""")
    stats = {
        "panel_rows": size[0], "panel_npis": size[1], "panel_brands": size[2],
        "status_counts": status,
        "glp1_claims_in_panel_vs_all_observed": claims[0] / claims[1],
        "flow": flow.to_dict(orient="records"),
        "launch": {b: {"first_partd_year": a, "first_payment_year": c} for b, a, c in
                   con.execute("SELECT brand, first_partd_year, first_payment_year FROM launch "
                               "ORDER BY 2").fetchall()},
    }  # fmt: skip
    (config.QA_DIR / "panel.json").write_text(json.dumps(stats, indent=1, default=float))
    return stats


if __name__ == "__main__":
    print(json.dumps(build(), indent=1, default=float))
