"""Part D reconciliation and suppression measurement (P04).

1. Integrity: no prescriber x drug row with < 11 claims, no negative values, one row per
   NPI x brand x generic x year.
2. Do the national rows of "by Geography and Drug" include claims hidden at prescriber
   level? If so, national claims >= the sum of prescriber rows for (almost) every drug.
3. Suppression gap, two ways:
   a. per drug: national claims - sum of prescriber x drug rows  (overall and per GLP-1 brand)
   b. per prescriber: by-Provider total claims - sum of that NPI's by-Drug rows
4. Cross-source: national GLP-1 claims (Geography) vs Part D Spending by Drug (2020-2024).

Writes report/qa/partd_*.csv|json and report/figures/p04_suppression_gap.png.
"""

from __future__ import annotations

import json

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from ppg import config  # noqa: E402

PD = config.PARQUET_DIR / "partd"
DRUG = f"read_parquet('{PD}/by_provider_drug/*/*.parquet', hive_partitioning = true)"
PROV = f"read_parquet('{PD}/by_provider/*/*.parquet', hive_partitioning = true)"
GEO = f"read_parquet('{PD}/by_geography_drug/*/*.parquet', hive_partitioning = true)"
SPEND = f"read_parquet('{PD}/spending_by_drug/all.parquet')"

GLP1_GENERICS = (
    "semaglutide",
    "tirzepatide",
    "dulaglutide",
    "liraglutide",
    "exenatide",
    "lixisenatide",
    "albiglutide",
)
GLP1 = " OR ".join(f"lower(gnrc_name) LIKE '%{g}%'" for g in GLP1_GENERICS)

SURFACE, INK, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SERIES = ["#2a78d6", "#eb6834"]


def q(con, sql):
    return con.execute(sql).df()


def integrity(con) -> dict:
    r = (
        con.execute(
            f"""SELECT count(*) FILTER (WHERE tot_clms < 11)           AS rows_lt11,
                   count(*) FILTER (WHERE tot_clms IS NULL)          AS rows_null_clms,
                   count(*) FILTER (WHERE tot_clms < 0 OR tot_drug_cst < 0
                                    OR tot_30day_fills < 0)          AS rows_negative,
                   count(*) FILTER (WHERE prscrbr_npi IS NULL)       AS rows_null_npi,
                   count(*) - count(DISTINCT (year, prscrbr_npi, brnd_name, gnrc_name))
                                                                     AS duplicate_keys
            FROM {DRUG}"""
        )
        .df()
        .iloc[0]
    )
    return {k: int(v) for k, v in r.items()}


def by_year(con):
    return q(
        con,
        f"""
        WITH d AS (SELECT year, count(*) AS drug_rows, count(DISTINCT prscrbr_npi) AS prescribers,
                          sum(tot_clms) AS prescriber_row_claims,
                          sum(tot_clms) FILTER (WHERE {GLP1}) AS glp1_prescriber_row_claims,
                          count(DISTINCT prscrbr_npi) FILTER (WHERE {GLP1}) AS glp1_prescribers
                   FROM {DRUG} GROUP BY 1),
             g AS (SELECT year, sum(tot_clms) AS national_claims,
                          sum(tot_clms) FILTER (WHERE {GLP1}) AS glp1_national_claims,
                          sum(tot_prscrbrs) FILTER (WHERE {GLP1}) AS glp1_national_prescriber_drug
                   FROM {GEO} WHERE prscrbr_geo_lvl = 'National' GROUP BY 1),
             p AS (SELECT year, count(*) AS provider_rows, sum(tot_clms) AS provider_total_claims
                   FROM {PROV} GROUP BY 1)
        SELECT d.*, g.*, p.provider_rows, p.provider_total_claims,
               1 - prescriber_row_claims / national_claims           AS gap_vs_national,
               1 - glp1_prescriber_row_claims / glp1_national_claims AS glp1_gap_vs_national,
               1 - prescriber_row_claims / provider_total_claims     AS gap_vs_provider_totals
        FROM d JOIN g USING (year) JOIN p USING (year) ORDER BY year""",
    ).drop(columns=["year_1", "year_2"], errors="ignore")


def national_includes_suppressed(con):
    """Share of drug-years where national claims >= sum of prescriber rows."""
    return q(
        con,
        f"""
        WITH d AS (SELECT year, brnd_name, gnrc_name, sum(tot_clms) AS rows_claims,
                          count(*) AS n_rows
                   FROM {DRUG} GROUP BY ALL),
             g AS (SELECT year, brnd_name, gnrc_name, tot_clms AS national_claims, tot_prscrbrs
                   FROM {GEO} WHERE prscrbr_geo_lvl = 'National')
        SELECT year, count(*) AS drugs,
               avg((national_claims >= rows_claims)::INT)  AS share_national_ge_rows,
               avg((tot_prscrbrs >= n_rows)::INT)          AS share_prescribers_ge_rows,
               median(1 - rows_claims / national_claims)   AS median_gap
        FROM d JOIN g USING (year, brnd_name, gnrc_name) GROUP BY 1 ORDER BY 1""",
    )


def glp1_brands(con):
    return q(
        con,
        f"""
        WITH d AS (SELECT year, brnd_name, gnrc_name, sum(tot_clms) AS prescriber_row_claims,
                          sum(tot_30day_fills) AS prescriber_row_fills, count(*) AS prescriber_rows
                   FROM {DRUG} WHERE {GLP1} GROUP BY ALL),
             g AS (SELECT year, brnd_name, gnrc_name, tot_clms AS national_claims,
                          tot_30day_fills AS national_fills, tot_prscrbrs AS national_prescribers,
                          tot_drug_cst AS national_cost
                   FROM {GEO} WHERE prscrbr_geo_lvl = 'National' AND ({GLP1}))
        SELECT g.year, g.brnd_name, g.gnrc_name, national_prescribers, prescriber_rows,
               national_claims, prescriber_row_claims,
               1 - prescriber_row_claims / national_claims AS claims_hidden_share,
               1 - prescriber_rows / national_prescribers  AS prescribers_below_11_share,
               national_fills, national_cost
        FROM g LEFT JOIN d USING (year, brnd_name, gnrc_name)
        ORDER BY g.brnd_name, g.year""",
    )


def spending_crosscheck(con):
    parts = []
    for y in range(2020, 2025):
        parts.append(f"""SELECT {y} AS year, brnd_name, gnrc_name,
                                tot_clms_{y} AS spending_file_claims,
                                tot_spndng_{y} AS spending_file_cost
                         FROM {SPEND} WHERE mftr_name = 'Overall' AND ({GLP1})""")
    s = " UNION ALL ".join(parts)
    return q(
        con,
        f"""
        WITH s AS ({s}),
             g AS (SELECT year, brnd_name, gnrc_name, tot_clms AS geo_claims,
                          tot_drug_cst AS geo_cost
                   FROM {GEO} WHERE prscrbr_geo_lvl = 'National' AND ({GLP1}))
        SELECT s.*, geo_claims, geo_cost,
               geo_claims / spending_file_claims - 1 AS claims_diff,
               geo_cost / spending_file_cost - 1     AS cost_diff
        FROM s JOIN g USING (year, brnd_name, gnrc_name)
        WHERE spending_file_claims > 0 ORDER BY brnd_name, year""",
    )


def chart(df) -> None:
    fig, ax = plt.subplots(figsize=(8, 4), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    for (col, label), color in zip(
        [("gap_vs_national", "All drugs"), ("glp1_gap_vs_national", "GLP-1 drugs")],
        SERIES,
        strict=True,
    ):
        ax.plot(df.year, 100 * df[col], color=color, lw=2, marker="o", ms=5, label=label)
        ax.text(
            df.year.iloc[-1] + 0.2,
            100 * df[col].iloc[-1],
            label,
            color=INK,
            fontsize=9,
            va="center",
        )
    ax.set_title(
        "Share of Part D claims hidden by the < 11-claim rule (%)",
        loc="left",
        color=INK,
        fontsize=11,
    )
    ax.set_ylim(bottom=0)
    ax.set_xlim(df.year.min() - 0.5, df.year.max() + 2)
    ax.grid(axis="y", color=GRID, lw=0.8)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    ax.legend(frameon=False, fontsize=9, loc="upper left", labelcolor=INK)
    fig.text(
        0.01,
        0.01,
        "National claims (Part D by Geography and Drug) minus claims in "
        "prescriber x drug rows. Source: CMS Part D Prescribers, 2013–2024.",
        fontsize=7.5,
        color=MUTED,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    config.FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(config.FIGURE_DIR / "p04_suppression_gap.png", dpi=160, facecolor=SURFACE)


def main() -> int:
    con = duckdb.connect()
    con.execute("SET enable_progress_bar_print = false")
    config.QA_DIR.mkdir(parents=True, exist_ok=True)
    checks = integrity(con)
    year = by_year(con)
    incl = national_includes_suppressed(con)
    brands = glp1_brands(con)
    spend = spending_crosscheck(con)
    for name, df in (
        ("partd_by_year", year),
        ("partd_national_vs_rows", incl),
        ("partd_glp1_brands", brands),
        ("partd_spending_crosscheck", spend),
    ):
        df.to_csv(config.QA_DIR / f"{name}.csv", index=False, float_format="%.6g")
    checks["national_ge_rows_min_share"] = float(incl.share_national_ge_rows.min())
    (config.QA_DIR / "partd_checks.json").write_text(json.dumps(checks, indent=1))
    chart(year)
    print(json.dumps(checks, indent=1))
    print(year.to_string(index=False))
    print(incl.to_string(index=False))
    ok = (
        checks["rows_lt11"] == 0
        and checks["rows_negative"] == 0
        and checks["duplicate_keys"] == 0
        and checks["national_ge_rows_min_share"] > 0.99
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
