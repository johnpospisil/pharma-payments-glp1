"""State x year denominator: estimated Part D enrollees with diabetes (P05; used in chart 6).

    est_diabetic_partd = Part D enrollees (Medicare Monthly Enrollment, annual row)
                         x % of adults 65+ ever told they have diabetes (CDC BRFSS)

BRFSS state samples of adults 65+ are small (~200-800 a year), so prevalence is pooled
over years t-2..t, weighting each year by its sample size. Applying 65+ prevalence to all
Part D enrollees (about 13% are under 65, mostly disabled) is an approximation, noted in
DATA.md. Writes PARQUET_DIR/reference/state_diabetic_partd.parquet and a QA CSV.
"""

from __future__ import annotations

import duckdb

from ppg import config

R = config.PARQUET_DIR / "reference"


def build() -> None:
    con = duckdb.connect()
    con.execute("SET enable_progress_bar_print = false")
    df = con.execute(f"""
        WITH b AS (SELECT year, state, pct, sample_size
                   FROM '{R}/brfss_diabetes_65plus.parquet'
                   WHERE break_out = '65+' AND pct IS NOT NULL),
             pooled AS (SELECT y.year, b.state,
                               sum(b.pct * b.sample_size) / sum(b.sample_size) AS pct_pooled,
                               sum(b.sample_size) AS n_pooled, count(*) AS years_pooled
                        FROM (SELECT DISTINCT year FROM b) y
                        JOIN b ON b.year BETWEEN y.year - 2 AND y.year
                        GROUP BY 1, 2),
             e AS (SELECT year, state, prscrptn_drug_tot_benes AS partd_enrollees,
                          tot_benes AS medicare_benes
                   FROM '{R}/enrollment_state_year.parquet' WHERE geo_lvl = 'State')
        SELECT e.year, e.state, e.partd_enrollees, e.medicare_benes,
               b.pct AS brfss_pct_65plus_single_year, p.pct_pooled AS brfss_pct_65plus_pooled,
               p.n_pooled, p.years_pooled,
               e.partd_enrollees * p.pct_pooled / 100 AS est_diabetic_partd
        FROM e
        LEFT JOIN pooled p USING (year, state)
        LEFT JOIN b USING (year, state)
        WHERE e.year BETWEEN 2013 AND 2025
        ORDER BY e.state, e.year
    """).df()
    df.to_parquet(R / "state_diabetic_partd.parquet", index=False)
    config.QA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.QA_DIR / "state_diabetic_partd.csv", index=False, float_format="%.4g")
    missing = df[df.est_diabetic_partd.isna()]
    print(
        f"{len(df)} state-years; {len(missing)} without an estimate:",
        sorted(set(zip(missing.state, missing.year, strict=True)))[:20],
    )
    y = df[df.year == 2024].sort_values("brfss_pct_65plus_pooled")
    print(
        y[["state", "partd_enrollees", "brfss_pct_65plus_pooled", "est_diabetic_partd"]]
        .iloc[[0, 1, 2, -3, -2, -1]]
        .to_string(index=False)
    )
    print("US total 2024:", round(y.est_diabetic_partd.sum() / 1e6, 2), "M est. diabetic Part D")


if __name__ == "__main__":
    build()
