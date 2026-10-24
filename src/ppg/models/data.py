"""Analysis frames for the event study, exactly as PREREGISTRATION.md §3-5 (prereg-v1).

One frame per brand: physician x year rows with
    y        1{claims of the brand >= 11} (primary outcome, D14)
    g        first promotional-contact year for the brand (D22); 0 = not treated by 2024
    covariates measured each year (the estimator takes them from the base period g - 1)
Rows outside a physician's Part D span, and internal gap years, are dropped (D25).
"""

from __future__ import annotations

import duckdb
import pandas as pd

from ppg import config

P = config.PARQUET_DIR
PRIMARY_BRANDS = ("Trulicity", "Victoza", "Ozempic")
LAST_YEAR = 2024
REGION = {  # Census regions
    "Northeast": "CT ME MA NH RI VT NJ NY PA",
    "Midwest": "IL IN MI OH WI IA KS MN MO NE ND SD",
    "South": "DE DC FL GA MD NC SC VA WV AL KY MS TN AR LA OK TX",
    "West": "AZ CO ID MT NV NM UT WY AK CA HI OR WA",
}
STATE_REGION = {s: r for r, states in REGION.items() for s in states.split()}
SAMPLE = """d.f1_individual AND d.f2_prescriber_specialty AND d.f3_active_years
            AND d.f4_diabetes_prescriber"""


def frame(
    brand: str,
    con: duckdb.DuckDBPyConnection | None = None,
    sample: str = "physician",
    exposure: str = "first_promo_year",
    first_cohort: int | None = None,
) -> pd.DataFrame:
    """Physician x year analysis frame for one brand (prereg §3-5).

    sample: 'physician' (primary), 'np_pa' (H7), 'high_volume' (physicians, D14 subsample).
    exposure: the cohort column (first_promo_year; first_year_first_listed;
              first_promo_year_molecule) for pre-registered sensitivities.
    first_cohort: earliest cohort kept (default max(2015, launch + 1)); P15 sets the launch year
              for brand share relative to launch (H5, Mounjaro).
    """
    con = con or duckdb.connect()
    who = {
        "physician": "d.physician",
        "np_pa": "d.specialty_group IN ('nurse_practitioner', 'physician_assistant')",
        "high_volume": "d.physician AND d.high_volume",
    }[sample]
    df = con.execute(
        f"""
        SELECT b.npi, b.year, b.first_partd_year,
               (b.status = 'observed')::INT AS y,
               coalesce(b.fills, 0) AS fills_obs, b.status, b.supp_cap, b.fills,
               b.{exposure} AS first_year, b.first_promo_date,
               b.specialty_group, b.state, b.ruca, b.tot_clms, b.dm_load,
               (b.glp1_claims_all - coalesce(CASE WHEN b.status = 'observed'
                                                  THEN b.claims END, 0)) > 0 AS other_glp1,
               b.glp1_claims_all, b.clms_statin, b.contacts, b.usd, b.usd_speaker, b.usd_consulting,
               b.usd_food_beverage, d.org_pac_id, d.specialty_group AS specialty_modal
        FROM '{P}/panel/panel_brand.parquet' b
        JOIN '{P}/panel/npi_dims.parquet' d USING (npi)
        WHERE b.brand = ? AND {SAMPLE} AND {who}
          AND b.status <> 'absent' AND b.tot_clms IS NOT NULL      -- D25: in Part D that year
          AND b.year >= greatest(2013, b.first_partd_year - 1)
          AND b.year <= {LAST_YEAR}""",
        [brand],
    ).df()
    launch = int(df.first_partd_year.iloc[0])
    # cohorts (prereg §3.4): first contact in 2013-14 or before launch + 1 -> already treated
    g = df.first_year.fillna(0).astype(int)
    first_eligible = first_cohort or max(2015, launch + 1)
    already = (g > 0) & (g < first_eligible)
    n_already = int(df.loc[already, "npi"].nunique())
    df = df[~already].copy()
    g = g[~already]
    df["g"] = g.where((g >= first_eligible) & (g <= LAST_YEAR), 0)  # 2025 -> not treated
    df["region"] = df.state.map(STATE_REGION)
    territory = df.groupby("npi").region.transform(lambda r: r.isna().any())
    n_territory = int(df.loc[territory, "npi"].nunique())
    df = df[~territory].copy()  # DEV-2: territories have no Census region
    df["specialty_group"] = df.specialty_modal  # time-invariant (the sample-defining group)
    df["urban"] = (df.ruca < 4).astype(int)
    df["log_dm"] = (1 + df.dm_load).map(_log)
    df["log_tot"] = (1 + df.tot_clms).map(_log)
    df["other_glp1"] = df.other_glp1.astype(int)
    df["cluster"] = df.org_pac_id.fillna("npi" + df.npi.astype(str))
    df.attrs |= {"brand": brand, "launch": launch, "first_eligible_cohort": first_eligible,
                 "excluded_already_treated_npis": n_already,
                 "excluded_territory_npis": n_territory}  # fmt: skip
    return df.reset_index(drop=True)


def _log(x: float) -> float:
    import math

    return math.log(x)


def cohort_table(df: pd.DataFrame) -> pd.DataFrame:
    u = df.groupby("npi").g.first()
    return u.value_counts().sort_index().rename("npis").to_frame()
