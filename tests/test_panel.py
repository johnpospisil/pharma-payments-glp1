"""Prescriber x brand x year panel (P10): structure and suppression rules (real data)."""

import json

import duckdb
import pytest

from ppg import config
from ppg.build.panel import IN_SAMPLE, OUT

PB, DIMS, NY = (f"'{OUT}/{n}.parquet'" for n in ("panel_brand", "npi_dims", "npi_year"))
pytestmark = pytest.mark.data


@pytest.fixture(scope="module")
def db():
    if not (OUT / "panel_brand.parquet").exists():
        pytest.skip("run python -m ppg.build.panel first")
    return duckdb.connect()


def one(db, sql):
    return db.execute(sql).fetchone()[0]


def test_unique_keys(db):
    assert one(db, f"SELECT count(*) - count(DISTINCT (npi, brand, year)) FROM {PB}") == 0
    assert one(db, f"SELECT count(*) - count(DISTINCT (npi, year)) FROM {NY}") == 0
    assert one(db, f"SELECT count(*) - count(DISTINCT npi) FROM {DIMS}") == 0


def test_status_rules(db):
    bad = one(
        db,
        f"""SELECT count(*) FROM {PB} WHERE
        (status = 'observed' AND (claims IS NULL OR claims < 11))
        OR (status = 'suppressed' AND (claims IS NOT NULL OR supp_cap IS NULL
                                       OR supp_cap NOT BETWEEN 1 AND 10))
        OR (status = 'zero_known' AND claims <> 0)
        OR (status = 'absent' AND (claims IS NOT NULL OR supp_cap IS NOT NULL))
        OR (status = 'pre_launch' AND (claims <> 0 OR year >= first_partd_year))""",
    )
    assert bad == 0


def test_never_silently_zero(db):
    # a missing row is 0-10 claims: only zero_known / pre_launch cells may carry claims = 0
    assert one(db, f"SELECT count(*) FROM {PB} WHERE claims = 0 AND status NOT IN "
                   "('zero_known', 'pre_launch')") == 0  # fmt: skip


def test_panel_is_exactly_the_sample(db):
    n_sample = one(db, f"SELECT count(*) FROM {DIMS} WHERE {IN_SAMPLE}")
    assert one(db, f"SELECT count(DISTINCT npi) FROM {PB}") == n_sample


def test_sample_flow_monotone():
    stats = json.loads((config.QA_DIR / "panel.json").read_text())
    n = [s["npis"] for s in stats["flow"]]
    assert all(a >= b for a, b in zip(n, n[1:], strict=False))


def test_panel_dollars_match_payments(db):
    pay = one(
        db,
        f"""SELECT sum(p.usd_split)
        FROM '{config.PARQUET_DIR}/payments/npi_brand_year.parquet' p
        JOIN (SELECT npi FROM {DIMS} WHERE {IN_SAMPLE}) USING (npi)
        WHERE p.drug_class IN ('glp1', 'glp1_insulin_combo') AND p.year <= 2024
          AND p.brand <> 'Saxenda'""",
    )  # Saxenda has no Part D rows (obesity only)
    panel = one(db, f"SELECT sum(usd) FROM {PB}")
    assert abs(panel / pay - 1) < 1e-4


def test_glp1_claims_reconcile(db):
    a = one(db, f"SELECT sum(claims) FROM {PB} WHERE status = 'observed'")
    b = one(db, f"SELECT sum(clms_glp1) FROM {NY} JOIN (SELECT npi FROM {DIMS} WHERE "
                f"{IN_SAMPLE}) USING (npi)")  # fmt: skip
    assert abs(a - b) < 1
