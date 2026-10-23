"""Descriptive figures (P11): helpers (unit) and published-cell rules (real data)."""

import json

import numpy as np
import pandas as pd
import pytest

from ppg import config
from ppg.viz.figures import BRAND_COLOR, CATEGORICAL, HEX, _fold, _shares


def test_hex_grid_has_every_state_once():
    assert len(HEX) == 51 and len(set(HEX.values())) == 51


def test_brand_colours_are_fixed_and_distinct():
    assert list(BRAND_COLOR.values()) == CATEGORICAL[: len(BRAND_COLOR)]
    assert _fold("Ozempic") == "Ozempic" and _fold("Adlyxin") == "Other GLP-1"


def test_shares_equal_and_concentrated():
    eq = _shares(np.ones(1000))
    assert eq["top10_share"] == pytest.approx(0.10) and abs(eq["gini"]) < 1e-9
    v = np.r_[np.full(99, 1.0), 901.0]  # one recipient holds 90%
    s = _shares(v)
    assert s["top1_share"] == pytest.approx(0.901) and s["gini"] > 0.85


@pytest.mark.data
def test_published_cells_have_at_least_11_prescribers():
    f = config.QA_DIR / "eda_state_payments_per_diabetic.csv"
    if not f.exists():
        pytest.skip("run python -m ppg.viz.figures first")
    st = pd.read_csv(f)
    assert (st[st.shown].npis_paid >= config.MIN_CELL).all()
    sp = pd.read_csv(config.QA_DIR / "eda_specialty_payments_vs_load.csv")
    assert (sp.prescribers >= config.MIN_CELL).all()


@pytest.mark.data
def test_headline_numbers_recorded():
    e = json.loads((config.QA_DIR / "eda.json").read_text())
    assert 0.5 < e["chart7"]["top10_share"] <= 1
    assert e["chart3"]["partd_glp1_cost_by_year"]["2024"] > 20
