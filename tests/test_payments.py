"""Payment measures (P09): nature groups (unit) and table invariants (real data)."""

import duckdb
import pytest

from ppg import config
from ppg.build.payments import NATURE_GROUP, PROMO_GROUPS, T
from ppg.ingest.quality import NON_PROMOTIONAL


@pytest.mark.parametrize(
    ("nature", "group"),
    [
        ("Food and Beverage", "food_beverage"),
        ("Consulting Fee", "consulting"),
        ("Travel and Lodging", "travel"),
        ("Education", "education"),
        ("Gift", "other_promotional"),
        ("Honoraria", "other_promotional"),
        ("Entertainment", "other_promotional"),
        ("Royalty or License", "non_promotional"),
        ("Acquisitions", "non_promotional"),
        ("Grant", "non_promotional"),
        (
            "Compensation for services other than consulting, including serving as faculty or "
            "as a speaker at a venue other than a continuing education program",
            "speaker",
        ),
        ("Compensation for serving as faculty or as a speaker for a medical education program",
         "speaker"),
    ],
)  # fmt: skip
def test_nature_group(nature, group):
    con = duckdb.connect()
    got = con.execute(
        f"SELECT {NATURE_GROUP} FROM (SELECT ? AS nature_of_payment)", [nature]
    ).fetchone()[0]
    assert got == group


def test_every_non_promotional_nature_is_grouped():
    con = duckdb.connect()
    for n in NON_PROMOTIONAL:
        got = con.execute(f"SELECT {NATURE_GROUP} FROM (SELECT ? AS nature_of_payment)", [n])
        assert got.fetchone()[0] == "non_promotional"


@pytest.fixture(scope="module")
def db():
    if not (config.PARQUET_DIR / "payments" / "npi_brand_year.parquet").exists():
        pytest.skip("run python -m ppg.build.payments first")
    return duckdb.connect()


@pytest.mark.data
def test_split_never_exceeds_full_and_first(db):
    bad = db.execute(f"""SELECT count(*) FROM {T["npi_brand_year"]}
                         WHERE usd_split > usd_full + 0.01 OR usd_first > usd_full + 0.01
                            OR contacts_first_listed > contacts""").fetchone()[0]
    assert bad == 0


@pytest.mark.data
def test_split_dollars_never_exceed_record_amount(db):
    bad = db.execute(f"""SELECT count(*) FROM (
                           SELECT record_id, program_year, sum(brand_slots) AS s,
                                  any_value(nprod) AS n
                           FROM {T["record_brand"]} GROUP BY 1, 2) WHERE s > n""").fetchone()[0]
    assert bad == 0


@pytest.mark.data
def test_nature_groups_add_up_to_split_total(db):
    groups = " + ".join(f"coalesce(usd_{g}, 0)" for g in PROMO_GROUPS)
    diff = db.execute(f"""SELECT max(abs(({groups}) - usd_split))
                          FROM {T["npi_brand_year"]}""").fetchone()[0]
    assert diff < 0.01


@pytest.mark.data
def test_one_row_per_key(db):
    for t, key in [("npi_brand_year", "npi, year, brand"), ("npi_brand_first", "npi, brand"),
                   ("npi_class_year", "npi, year, class_group"), ("npi_flags", "npi")]:  # fmt: skip
        dup = db.execute(f"SELECT count(*) - count(DISTINCT ({key})) FROM {T[t]}").fetchone()[0]
        assert dup == 0, t


@pytest.mark.data
def test_glp1_dollars_reconcile_with_drug_map(db):
    import json

    pay = json.loads((config.QA_DIR / "payments.json").read_text())
    dm = json.loads((config.QA_DIR / "drug_map.json").read_text())
    # drug_map counts every record (incl. teaching hospitals, unlinked); payments only linked
    ratio = pay["glp1_promo_usd"]["split"] / dm["glp1_promo_usd"]
    assert 0.97 < ratio <= 1.0
