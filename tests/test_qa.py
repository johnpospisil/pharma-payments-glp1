"""P20 QA gates: every article claim matches report/qa, and nothing public exposes a prescriber."""

import pytest

from ppg import config

pytestmark = pytest.mark.data


@pytest.fixture(scope="module", autouse=True)
def _need_data():
    if not (config.PARQUET_DIR / "payments" / "record_brand.parquet").exists():
        pytest.skip("needs the built parquet")


def test_article_claims_match_qa():
    from ppg.qa.claims import check

    res = check()
    assert res["pass"], res["failures"]


def test_disclosure_audit():
    from ppg.qa.disclosure import audit

    res = audit()
    assert res["npis_in_tracked_files"]["pass"], res["npis_in_tracked_files"]
    assert res["identifier_columns"]["pass"], res["identifier_columns"]
    assert res["small_cells"]["pass"], res["small_cells"]
    assert all(v["pass"] for v in res["geography"].values()), res["geography"]
