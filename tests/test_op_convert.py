"""Harmonised General Payments schema across the three CSV eras (fixtures, no real data)."""

from pathlib import Path

import pandas as pd
import pytest

from ppg.ingest import op_convert as oc

FIX = Path(__file__).parent / "fixtures" / "open_payments"


def _convert(year: str):
    con = oc._connect()
    path = FIX / f"general_{year}.csv"
    cols = oc._csv_columns(con, path)
    return con.execute(f"SELECT {oc.general_select(set(cols))} FROM {oc._read_csv(path)}").df()


@pytest.mark.parametrize("year", ["2013", "2015", "2024"])
def test_common_fields(year):
    df = _convert(year)
    assert len(df) == 2
    r = df.iloc[0]
    assert r.program_year == int(year)
    assert r.record_id == int(f"{year}0001")
    assert r.amount_usd == pytest.approx(1500.50)
    assert str(r.payment_date.date()) == f"{year}-03-15"
    assert r.recipient_zip5 == "62701"
    assert bool(r.disputed) is True and bool(r.delayed_publication) is False
    assert r.nature_of_payment == "Consulting Fee"
    assert '"quoted"' in r.contextual_information and "\n" in r.contextual_information


@pytest.mark.parametrize("year,npi", [("2013", None), ("2015", 1234567893), ("2024", 1234567893)])
def test_npi_by_era(year, npi):
    got = _convert(year).iloc[0].npi
    assert pd.isna(got) if npi is None else got == npi


def test_era_a_products_drugs_then_devices():
    prods = list(_convert("2013").iloc[0].products)
    assert [(p["slot"], p["kind"], p["name"]) for p in prods] == [
        (1, "Drug", "VICTOZA"),
        (6, "Device", "NovoFine Needle"),
    ]
    assert prods[0]["ndc"] == "0169406012"


def test_era_b_products_keep_category_and_ndc():
    prods = list(_convert("2024").iloc[0].products)
    assert [p["name"] for p in prods] == ["Ozempic", "RYBELSUS"]
    assert prods[0]["category"] == "Diabetes" and prods[0]["ndc"] == "0169-4132-12"


def test_lists_drop_blanks():
    r = _convert("2024").iloc[0]
    assert list(r.primary_types) == ["Medical Doctor"]
    assert len(r.specialties) == 1


@pytest.mark.parametrize("year", ["2013", "2015", "2024"])
def test_no_names_or_street_addresses(year):
    df = _convert(year)
    text = df.astype(str).to_string()
    assert "SECRET" not in text


def test_placeholder_product_slots_are_dropped():
    # PY2016-2020 fill empty device PDI slots with 'N/A'; those must not count as products.
    prods = list(_convert("2024").iloc[0].products)
    assert [p["slot"] for p in prods] == [1, 2]
    assert all(p["pdi"] is None for p in prods)
