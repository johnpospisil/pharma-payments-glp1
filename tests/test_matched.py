"""Matched design (P14): CEM strata, weights and the matched CS estimator on synthetic panels."""

import numpy as np
import pandas as pd
import pytest

from ppg.models.matched import Wide, estimate, strata


def _panel(n: int = 20_000, effect: float = 0.10, seed: int = 0) -> pd.DataFrame:
    """Two types; 'rising' physicians (high class claims) trend up and are targeted for payment."""
    rng = np.random.default_rng(seed)
    rising = rng.random(n) < 0.4
    p_treat = np.where(rising, 0.5, 0.15)
    g = np.where(rng.random(n) < p_treat, rng.choice([2016, 2018], n), 0)
    rows = []
    for t in range(2013, 2021):
        trend = np.where(rising, 0.03 * (t - 2013), 0.0)
        p = 0.10 + trend + effect * ((g > 0) & (t >= g))
        rows.append(pd.DataFrame({
            "npi": np.arange(n), "year": t, "y": (rng.random(n) < p).astype(int), "g": g,
            "glp1_claims_all": np.where(rising, 300.0, 0.0), "dm_load": 500.0,
            "tot_clms": 3000.0, "state": "OH", "specialty_group": "primary_care_physician",
            "region": "Midwest", "cluster": "c" + (np.arange(n) // 3).astype(str),
        }))  # fmt: skip
    return pd.concat(rows, ignore_index=True)


@pytest.fixture(scope="module")
def wide():
    return Wide(_panel())


def test_cem_weights_balance_strata(wide):
    m = strata(wide, 2016, "registered")
    assert m.treated.sum() > 0 and set(m.i) <= set(range(len(wide.npi)))
    s = m.groupby(["s", "treated"]).w.sum().unstack()
    assert np.allclose(s[True], s[False])  # weighted controls = treated count in each stratum
    cand = wide.g[m.i]
    assert ((cand == 0) | (cand >= 2016)).all()  # controls not yet paid at g


def test_matched_recovers_effect_unmatched_is_biased(wide):
    reg = estimate(wide, "registered")["overall_0_3"]
    raw = estimate(wide, "unmatched")["overall_0_3"]
    assert reg["att"] == pytest.approx(0.10, abs=3 * reg["se"] + 0.005)
    assert raw["att"] > reg["att"] + 0.01  # targeting of rising physicians inflates it
    assert 0 < reg["se"] < 0.02


def test_matched_event_zero_by_construction(wide):
    ev = pd.DataFrame(estimate(wide, "registered")["event"]).set_index("e")
    assert ev.loc[-2, "att"] == pytest.approx(0.0, abs=1e-12)  # matched on g-2 status
    assert abs(ev.loc[-3, "att"]) < 3 * ev.loc[-3, "se"] + 0.005  # no pre-trend after matching


def test_no_effect_gives_null():
    r = estimate(Wide(_panel(effect=0.0, seed=1)), "registered")["overall_0_3"]
    assert abs(r["att"]) < 3 * r["se"] + 0.005
