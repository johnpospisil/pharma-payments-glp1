"""P25: the released panel is the explorer cube, flattened, with nothing beyond it (D47)."""

import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from ppg import config
from ppg.release import build as rel

APP = rel.APP


@pytest.fixture(scope="module")
def released():
    return rel.panel()


def test_one_row_per_brand_year_specialty_state(released):
    p, vis, meta = released
    n = len(meta["brands"]) * len(meta["years"]) * len(meta["specialties"]) * len(meta["states"])
    assert len(p) == n and not p.duplicated(list(rel.KEYS)).any()
    assert len(vis) == len(meta["brands"]) * len(meta["years"])


def test_values_blank_unless_shown(released):
    p, _, _ = released
    for c in rel.COLUMNS.values():
        assert (p[c].notna() == (p[f"{c}_status"] == "shown")).all(), c


def test_no_small_counts_and_no_identifiers(released):
    p, _, _ = released
    for c in ("prescribers", "paid_prescribers", "prescribers_11plus_claims"):
        v = p[c].astype(float)
        assert not ((v > 0) & (v < config.MIN_CELL)).any(), c
    assert not any("npi" in c.lower() or "name" in c.lower() for c in p.columns)


def test_values_equal_the_explorer(released):
    p, _, meta = released
    oz = json.loads((APP / "ozempic.json").read_text())
    y, s, t = len(meta["years"]) - 1, len(meta["specialties"]) - 1, len(meta["states"]) - 1
    row = p[(p.brand == "Ozempic") & (p.year == meta["years"][y])
            & (p.specialty == "all_physicians") & (p.state == "US")].iloc[0]  # fmt: skip
    for m, c in rel.COLUMNS.items():
        assert row[c] == oz[m][y][s][t], c


def test_withheld_status_is_the_only_privacy_code(released):
    p, _, _ = released
    statuses = set(np.unique(p.filter(like="_status").to_numpy()))
    assert statuses <= set(rel.STATUS.values())


def test_drug_map_totals_blank_below_11_records():
    op, _ = rel.drug_maps()
    src = pd.read_csv(config.REFERENCE_DIR / "drug_name_map.csv")
    small = (src.records > 0) & (src.records < config.MIN_CELL)
    assert op.loc[small, ["records", "usd", "promo_usd"]].isna().all().all()
    assert (op.raw_name == src.raw_name).all()


def test_committed_release_matches_its_checksums():
    sums = rel.OUT / "SHA256SUMS"
    if not sums.exists():
        pytest.skip("release/ not built")
    for line in sums.read_text().splitlines():
        h, f = line.split("  ", 1)
        assert hashlib.sha256((rel.OUT / f).read_bytes()).hexdigest() == h, f
