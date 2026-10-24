"""Open Payments recipient -> NPI linkage (P08).

Each non-teaching-hospital General Payments record gets one `npi_linked`, by the first
route that works:

    direct      the record's own NPI field (PY2015+), if it passes the Luhn check (D17)
    supplement  profile ID -> NPI in the Covered Recipient Profile Supplement, after
                resolving merged profiles (profile-ID mapping table: secondary -> primary)
    learned     profile ID -> NPI learned from the same profile's PY2015+ records, used for
                PY2013-14 profiles that have dropped out of the current supplement
    none        no route (teaching hospitals are out of scope and never linked)

Outputs (PARQUET_DIR/linkage/):
    profile_npi.parquet                     profile_id -> npi, source
    npi_specialty.parquet                   npi -> OP and Part D specialty group, agree flag
    op_record_npi/program_year=Y/*.parquet  record_id, recipient_class, npi_linked, link_method
QA (report/qa/): linkage.json, linkage_match_rates.csv, linkage_overlap_by_year.csv,
    linkage_specialty_crosstab.csv

    python -m ppg.build.linkage
"""

from __future__ import annotations

import json

import pandas as pd

from ppg import config
from ppg.build.specialty import assign
from ppg.disclosure import mask_crosstab
from ppg.ingest.quality import NON_PROMOTIONAL, OP, PD, connect

OUT = config.PARQUET_DIR / "linkage"
_OPD = config.PARQUET_DIR / "open_payments"
SUPPLEMENT = f"'{_OPD}/profile_supplement.parquet'"
MAPPING = f"'{_OPD}/profile_id_mapping.parquet'"
RECORDS = f"read_parquet('{OUT}/op_record_npi/*/*.parquet', hive_partitioning = true)"

RECIPIENT_CLASS = """CASE
    WHEN recipient_type ILIKE '%teaching hospital%' THEN 'teaching_hospital'
    WHEN primary_types[1] IN ('Medical Doctor', 'Doctor of Osteopathy') THEN 'md_do'
    WHEN primary_types[1] = 'Nurse Practitioner' THEN 'np'
    WHEN primary_types[1] = 'Physician Assistant' THEN 'pa'
    WHEN primary_types[1] IS NULL THEN 'unknown'
    ELSE 'other' END"""  # other: dentists, optometrists, podiatrists, chiropractors, CRNAs...


def op_specialty_group(path: str | None) -> str:
    """Open Payments taxonomy path ("Grouping|Classification|Specialization") -> group.

    Uses the same groups as the Part D crosswalk (ppg.build.specialty). Physicians with a
    specialization are grouped by it (Internal Medicine|Gastroenterology -> other_physician),
    otherwise by their classification (Family Medicine -> primary care)."""
    if not isinstance(path, str) or not path.strip():
        return "missing"
    parts = [p.strip() for p in path.split("|")]
    grouping, cls = parts[0], parts[1] if len(parts) > 1 else ""
    spec = parts[2] if len(parts) > 2 else ""
    if grouping.startswith("Physician Assistants & Advanced Practice Nursing"):
        if cls.startswith("Nurse Practitioner"):
            return "nurse_practitioner"
        if cls.startswith("Physician Assistant"):
            return "physician_assistant"
        return "other_nonphysician"
    if grouping.startswith("Allopathic & Osteopathic Physicians"):
        return assign(spec or cls)[0]
    group, rule = assign(cls or grouping)
    return "other_nonphysician" if rule == "default" else group


def build_profile_npi(con) -> dict:
    """profile_id -> NPI from the supplement (with merges) and from PY2015+ records."""
    con.execute(f"""
        CREATE OR REPLACE TABLE sup AS
        SELECT try_cast(covered_recipient_profile_id AS BIGINT) AS profile_id,
               try_cast(covered_recipient_npi AS BIGINT) AS npi
        FROM {SUPPLEMENT}
        WHERE npi_luhn_ok(try_cast(covered_recipient_npi AS BIGINT))""")
    # merged profiles: the secondary ID inherits the primary profile's NPI
    con.execute(f"""
        CREATE OR REPLACE TABLE merged AS
        SELECT try_cast(m.secondary_provider_profile_id AS BIGINT) AS profile_id, s.npi
        FROM {MAPPING} m JOIN sup s
          ON s.profile_id = try_cast(m.primary_provider_profile_id AS BIGINT)""")
    con.execute(f"""
        CREATE OR REPLACE TABLE learned AS
        SELECT profile_id, any_value(npi) AS npi, count(DISTINCT npi) AS n_npi
        FROM {OP}
        WHERE program_year >= 2015 AND profile_id IS NOT NULL AND npi_luhn_ok(npi)
        GROUP BY 1""")
    con.execute("""
        CREATE OR REPLACE TABLE profile_npi AS
        WITH c AS (
            SELECT profile_id, npi, 'supplement' AS source, 1 AS rank FROM sup
            UNION ALL SELECT profile_id, npi, 'supplement', 2 FROM merged
            UNION ALL SELECT profile_id, npi, 'learned', 3 FROM learned WHERE n_npi = 1)
        SELECT profile_id, first(npi ORDER BY rank, npi) AS npi,
               first(source ORDER BY rank, npi) AS source
        FROM c GROUP BY 1""")
    OUT.mkdir(parents=True, exist_ok=True)
    con.execute(f"COPY profile_npi TO '{OUT}/profile_npi.parquet' (FORMAT parquet)")
    q = con.execute
    return {
        "supplement_profiles_with_valid_npi": q("SELECT count(*) FROM sup").fetchone()[0],
        "merged_secondary_profiles": q("SELECT count(*) FROM merged").fetchone()[0],
        "learned_profiles": q("SELECT count(*) FROM learned WHERE n_npi = 1").fetchone()[0],
        "learned_profiles_ambiguous": q("SELECT count(*) FROM learned WHERE n_npi > 1").fetchone()[
            0
        ],
        "learned_vs_supplement_disagree": q(
            "SELECT count(*) FROM learned l JOIN sup s USING (profile_id) "
            "WHERE l.n_npi = 1 AND l.npi <> s.npi"
        ).fetchone()[0],
        "profile_npi_rows": q("SELECT count(*) FROM profile_npi").fetchone()[0],
        "npis_with_several_profiles": q(
            "SELECT count(*) FROM (SELECT npi FROM profile_npi GROUP BY 1 HAVING count(*) > 1)"
        ).fetchone()[0],
    }


def build_records(con) -> None:
    con.execute(f"""
        COPY (
            SELECT o.program_year, o.record_id, {RECIPIENT_CLASS} AS recipient_class,
                   CASE WHEN o.recipient_type ILIKE '%teaching hospital%' THEN NULL
                        WHEN npi_luhn_ok(o.npi) THEN o.npi ELSE p.npi END AS npi_linked,
                   CASE WHEN o.recipient_type ILIKE '%teaching hospital%' THEN 'out_of_scope'
                        WHEN npi_luhn_ok(o.npi) THEN 'direct'
                        WHEN p.npi IS NOT NULL THEN p.source
                        WHEN o.npi IS NOT NULL THEN 'invalid_npi'
                        ELSE 'none' END AS link_method,
                   o.npi IS NOT NULL AND p.npi IS NOT NULL AND o.npi <> p.npi
                       AS profile_disagrees
            FROM {OP} o LEFT JOIN profile_npi p USING (profile_id)
        ) TO '{OUT}/op_record_npi' (FORMAT parquet, PARTITION_BY (program_year),
                                    OVERWRITE_OR_IGNORE)""")


def match_rates(con) -> pd.DataFrame:
    df = con.execute(f"""
        SELECT program_year, recipient_class, link_method, count(*) AS records
        FROM {RECORDS} GROUP BY ALL""").df()
    w = df.pivot_table(
        index=["program_year", "recipient_class"], columns="link_method", values="records",
        aggfunc="sum", fill_value=0,
    )  # fmt: skip
    w["records"] = w.sum(axis=1)
    linked = w[[c for c in ("direct", "supplement", "learned") if c in w]].sum(axis=1)
    w["match_rate"] = linked / w.records
    return w.reset_index()


GLP1_OP = "glp1_op"  # registered: raw product strings that are GLP-1 (drug_name_map.csv)
GLP1_PD = "glp1_pd"  # registered: Part D (brnd_name, gnrc_name) that are GLP-1


def register_maps(con) -> None:
    op = pd.read_csv(config.REFERENCE_DIR / "drug_name_map.csv")
    pdm = pd.read_csv(config.REFERENCE_DIR / "partd_drug_map.csv")
    con.register(GLP1_OP, op[op.is_glp1 == True][["raw_name"]])  # noqa: E712
    con.register(GLP1_PD, pdm[pdm.is_glp1][["brnd_name", "gnrc_name"]])


def overlap(con) -> tuple[pd.DataFrame, dict]:
    """Part D GLP-1 fills from NPIs found in Open Payments, and GLP-1 $ to Part D NPIs."""
    con.execute(f"""
        CREATE OR REPLACE TABLE op_npi_year AS
        SELECT DISTINCT r.npi_linked AS npi, r.program_year AS year
        FROM {RECORDS} r WHERE r.npi_linked IS NOT NULL""")
    con.execute(f"""
        CREATE OR REPLACE TABLE glp1_pay AS
        WITH u AS (SELECT o.record_id, o.program_year, o.amount_usd, o.nature_of_payment,
                          len(o.products) AS nprod, unnest(o.products) AS p
                   FROM {OP} o WHERE o.program_year <= 2025)
        SELECT r.npi_linked AS npi, u.program_year AS year, r.link_method, r.recipient_class,
               sum(u.amount_usd / u.nprod) FILTER (WHERE u.amount_usd > 0
                   AND u.nature_of_payment NOT IN {NON_PROMOTIONAL}) AS promo_usd,
               count(DISTINCT u.record_id) AS records
        FROM u JOIN {GLP1_OP} g ON g.raw_name = u.p.name
        JOIN {RECORDS} r ON r.record_id = u.record_id AND r.program_year = u.program_year
        GROUP BY ALL""")
    con.execute(f"""
        CREATE OR REPLACE TABLE pd_glp1 AS
        SELECT d.year, d.prscrbr_npi AS npi, sum(d.tot_30day_fills) AS fills,
               sum(d.tot_clms) AS claims
        FROM {PD} d JOIN {GLP1_PD} g USING (brnd_name, gnrc_name) GROUP BY 1, 2""")
    con.execute(f"CREATE OR REPLACE TABLE pd_npi AS SELECT DISTINCT prscrbr_npi AS npi FROM {PD}")
    con.execute(f"""CREATE OR REPLACE TABLE pd_npi_year AS
                    SELECT DISTINCT year, prscrbr_npi AS npi FROM {PD}""")
    by_year = con.execute("""
        WITH ever_op AS (SELECT DISTINCT npi FROM op_npi_year),
             ever_glp1 AS (SELECT DISTINCT npi FROM glp1_pay WHERE promo_usd > 0 OR records > 0),
             f AS (SELECT p.year, sum(p.fills) AS fills,
                          sum(p.fills) FILTER (WHERE e.npi IS NOT NULL) AS fills_ever_op,
                          sum(p.fills) FILTER (WHERE g.npi IS NOT NULL) AS fills_ever_glp1_paid,
                          count(*) AS prescribers,
                          count(*) FILTER (WHERE g.npi IS NOT NULL) AS prescribers_ever_glp1_paid
                   FROM pd_glp1 p LEFT JOIN ever_op e USING (npi)
                   LEFT JOIN ever_glp1 g USING (npi) GROUP BY 1),
             d AS (SELECT g.year, sum(g.promo_usd) AS glp1_promo_usd,
                          sum(g.promo_usd) FILTER (WHERE g.npi IS NOT NULL) AS usd_linked,
                          sum(g.promo_usd) FILTER (WHERE a.npi IS NOT NULL) AS usd_to_partd_ever,
                          sum(g.promo_usd) FILTER (WHERE y.npi IS NOT NULL)
                              AS usd_to_partd_same_year
                   FROM glp1_pay g LEFT JOIN pd_npi a USING (npi)
                   LEFT JOIN pd_npi_year y USING (year, npi) GROUP BY 1)
        SELECT * FROM d FULL JOIN f USING (year) ORDER BY year""").df()
    by_year["share_fills_ever_op"] = by_year.fills_ever_op / by_year.fills
    by_year["share_fills_ever_glp1_paid"] = by_year.fills_ever_glp1_paid / by_year.fills
    by_year["share_glp1_usd_linked"] = by_year.usd_linked / by_year.glp1_promo_usd
    by_year["share_glp1_usd_to_partd_ever"] = by_year.usd_to_partd_ever / by_year.glp1_promo_usd
    by_year["share_glp1_usd_to_partd_same_year"] = (
        by_year.usd_to_partd_same_year / by_year.glp1_promo_usd
    )
    q = con.execute
    npis = {
        "op_linked_npis": q("SELECT count(DISTINCT npi) FROM op_npi_year").fetchone()[0],
        "op_linked_npis_in_partd": q(
            "SELECT count(DISTINCT o.npi) FROM op_npi_year o JOIN pd_npi USING (npi)"
        ).fetchone()[0],
        "partd_npis": q("SELECT count(*) FROM pd_npi").fetchone()[0],
        "glp1_paid_npis": q(
            "SELECT count(DISTINCT npi) FROM glp1_pay WHERE npi IS NOT NULL"
        ).fetchone()[0],
        "glp1_paid_npis_in_partd": q(
            "SELECT count(DISTINCT g.npi) FROM glp1_pay g JOIN pd_npi USING (npi)"
        ).fetchone()[0],
        "glp1_paid_npis_glp1_prescribers": q(
            "SELECT count(DISTINCT g.npi) FROM glp1_pay g JOIN pd_glp1 USING (npi)"
        ).fetchone()[0],
        "glp1_unlinked_promo_usd": float(
            q("SELECT coalesce(sum(promo_usd), 0) FROM glp1_pay WHERE npi IS NULL").fetchone()[0]
        ),
    }
    return by_year, npis


def specialty_agreement(con) -> tuple[pd.DataFrame, dict]:
    """Specialty group in Open Payments (latest year, modal) vs Part D (latest year)."""
    op = con.execute(f"""
        WITH s AS (SELECT r.npi_linked AS npi, o.program_year AS y, o.specialties[1] AS spec,
                          count(*) AS n
                   FROM {OP} o JOIN {RECORDS} r USING (program_year, record_id)
                   WHERE r.npi_linked IS NOT NULL GROUP BY ALL)
        SELECT npi, first(spec ORDER BY y DESC, n DESC, spec) AS op_spec FROM s GROUP BY 1""").df()
    pdt = con.execute(f"""
        SELECT prscrbr_npi AS npi, arg_max(prscrbr_type, year) AS pd_type
        FROM {PD} GROUP BY 1""").df()
    groups = pd.read_csv(config.REFERENCE_DIR / "specialty_groups.csv")
    pdt["pd_group"] = pdt.pd_type.map(dict(zip(groups.prscrbr_type, groups.specialty_group,
                                               strict=True)))  # fmt: skip
    cache = {s: op_specialty_group(s) for s in op.op_spec.dropna().unique()}
    op["op_group"] = op.op_spec.map(cache).fillna("missing")
    allnpi = op.merge(pdt, on="npi", how="outer")
    known = allnpi.op_group.notna() & allnpi.pd_group.notna()
    allnpi["agree"] = (allnpi.op_group == allnpi.pd_group).where(known).astype("boolean")
    allnpi.to_parquet(OUT / "npi_specialty.parquet", index=False)
    both = op.merge(pdt, on="npi")
    xt = pd.crosstab(both.op_group, both.pd_group)
    agree = both.op_group == both.pd_group
    glp1 = both[both.npi.isin(con.execute("SELECT DISTINCT npi FROM pd_glp1").df().npi)]
    stats = {
        "npis_compared": int(len(both)),
        "agree_share": round(float(agree.mean()), 4),
        "agree_share_glp1_prescribers": round(float((glp1.op_group == glp1.pd_group).mean()), 4),
        "endocrinology_agree": round(float(
            (both[both.pd_group == "endocrinology"].op_group == "endocrinology").mean()), 4),
        "top_disagreements": {
            f"{a} (OP) vs {b} (Part D)": int(n)
            for (a, b), n in both[~agree].groupby(["op_group", "pd_group"]).size()
            .sort_values(ascending=False).head(8).items()
        },
    }  # fmt: skip
    return xt, stats


def build() -> dict:
    con = connect()
    con.execute("SET memory_limit = '8GB'")
    con.execute(f"SET temp_directory = '{config.DATA_DIR / 'tmp' / 'duckdb'}'")
    stats = {"profiles": build_profile_npi(con)}
    build_records(con)
    rates = match_rates(con)
    register_maps(con)
    ov, npis = overlap(con)
    xt, spec = specialty_agreement(con)
    totals = con.execute(f"""
        SELECT link_method, count(*) AS n, count(*) FILTER (WHERE profile_disagrees) AS disagree
        FROM {RECORDS} GROUP BY 1""").df()
    stats |= {
        "records_by_method": dict(zip(totals.link_method, totals.n.astype(int), strict=True)),
        "records_where_profile_npi_differs_from_direct": int(totals.disagree.sum()),
        "overlap": npis,
        "specialty": spec,
    }
    config.QA_DIR.mkdir(parents=True, exist_ok=True)
    rates.to_csv(config.QA_DIR / "linkage_match_rates.csv", index=False, float_format="%.4f")
    ov.to_csv(config.QA_DIR / "linkage_overlap_by_year.csv", index=False, float_format="%.4f")
    mask_crosstab(xt).to_csv(config.QA_DIR / "linkage_specialty_crosstab.csv", float_format="%.0f")
    (config.QA_DIR / "linkage.json").write_text(json.dumps(stats, indent=1, default=int))
    return stats


if __name__ == "__main__":
    print(json.dumps(build(), indent=1, default=int))
