"""Data-quality checks on the converted real data (P06). Skipped when the data is absent.

Thresholds encode what P03/P04/P06 found; a change in the source data that breaks them
should fail loudly and be investigated, not silently absorbed.
"""

import pytest

from ppg.ingest import quality as q

pytestmark = pytest.mark.data


def test_luhn_reference_values():
    assert q.luhn_ok(1234567893) is True  # CMS example NPI
    assert q.luhn_ok(1234567890) is False
    assert q.luhn_ok(123) is False
    assert q.luhn_ok(None) is None


@pytest.fixture(scope="module")
def op(con):
    return q.op_checks(con)


@pytest.fixture(scope="module")
def pd_(con):
    return q.partd_checks(con)


def test_op_record_ids_unique(op):
    assert op["duplicate_record_ids"] == 0


def test_op_amounts_and_dates_present(op):
    assert op["null_amount"] == 0 and op["null_payment_date"] == 0


def test_op_known_anomalies_stay_small(op):
    # flagged, not dropped: 871 amounts <= 0 (D12), 467 dates outside the program year
    assert op["nonpositive_amount"] <= 1_000
    assert op["date_outside_program_year"] <= 600
    assert op["bad_n_payments"] <= 20


def test_op_missing_npi_is_rare(op):
    # all such records carry a profile ID (linked in P08)
    assert op["missing_npi_2015plus"] / op["records"] < 0.001


def test_op_npis_pass_check_digit(con):
    r = q.op_npi_luhn(con)
    assert r["failing_luhn"] / r["distinct_npis"] < 1e-4


def test_partd_suppression_rule_holds(pd_):
    assert pd_["rows_lt11_claims"] == 0


def test_partd_no_negative_or_duplicate(pd_):
    assert pd_["rows_negative"] == 0 and pd_["duplicate_keys"] == 0


def test_partd_internal_consistency(pd_):
    assert pd_["fills_below_claims"] == 0  # 30-day fills >= claims
    assert pd_["benes_above_claims"] == 0  # a beneficiary has >= 1 claim
    assert pd_["missing_drug_name"] == 0


def test_partd_npis_pass_check_digit(con):
    assert q.partd_npi_luhn(con)["failing_luhn"] == 0
