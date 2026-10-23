from pathlib import Path

import pandas as pd

from ppg.ingest import op_convert as oc
from ppg.ingest import partd_convert as pc

FIX = Path(__file__).parent / "fixtures" / "partd" / "by_provider_drug.csv"


def _df():
    con = oc._connect()
    return con.execute(
        f"SELECT {pc.select_list(oc._csv_columns(con, FIX))} FROM {oc._read_csv(FIX)}"
    ).df()


def test_types_and_names():
    df = _df()
    assert df.prscrbr_npi.iloc[0] == 1234567893
    assert df.tot_clms.tolist() == [40.0, 120.0]
    assert df.tot_drug_cst.iloc[0] == 48210.55  # thousands separator removed
    assert df.prscrbr_state_fips.iloc[0] == "17"  # code stays text (leading zeros)
    assert df.ge65_sprsn_flag.iloc[0] == "*"


def test_suppressed_values_are_null_not_zero():
    r = _df().iloc[0]
    assert pd.isna(r.tot_benes) and pd.isna(r.ge65_tot_clms)


def test_names_and_city_dropped():
    df = _df()
    assert not any(
        c in df.columns for c in ("prscrbr_last_org_name", "prscrbr_first_name", "prscrbr_city")
    )
    assert "SECRET" not in df.astype(str).to_string()


def test_partb_columns():
    cols = [
        "Rndrng_NPI",
        "Rndrng_Prvdr_Last_Org_Name",
        "Rndrng_Prvdr_MI",
        "Rndrng_Prvdr_St1",
        "Rndrng_Prvdr_Crdntls",
        "Tot_Benes",
        "Bene_CC_PH_Diabetes_V2_Pct",
        "Bene_Avg_Risk_Scre",
        "Rndrng_Prvdr_RUCA",
        "Rndrng_Prvdr_RUCA_Desc",
    ]
    sel = pc.select_list(cols)
    assert "Last_Org_Name" not in sel and '"Rndrng_Prvdr_MI"' not in sel and "St1" not in sel
    assert 'AS DOUBLE) AS "bene_cc_ph_diabetes_v2_pct"' in sel
    assert 'AS DOUBLE) AS "bene_avg_risk_scre"' in sel
    assert 'AS BIGINT) AS "rndrng_npi"' in sel
    assert 'nullif(trim("Rndrng_Prvdr_RUCA_Desc"), \'\') AS "rndrng_prvdr_ruca_desc"' in sel
