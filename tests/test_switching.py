"""Brand switching (P15): share effects add up across brands; fractional-response check."""

import numpy as np
import pandas as pd
import pytest

from ppg.models.cs_panel import fit
from ppg.models.matched import Wide
from ppg.models.switching import frac_fit, shares


def _panel(n: int = 8_000, effect: float = 0.0, seed: int = 0) -> tuple[Wide, np.ndarray]:
    rng = np.random.default_rng(seed)
    g = np.where(rng.random(n) < 0.4, rng.choice([2016, 2018], n), 0)
    base = rng.uniform(0.1, 0.5, n)
    rows = []
    for t in range(2013, 2021):
        share = np.clip(base + 0.01 * (t - 2013) + effect * ((g > 0) & (t >= g))
                        + rng.normal(0, 0.05, n), 0, 1)  # fmt: skip
        rows.append(pd.DataFrame({
            "npi": np.arange(n), "year": t, "y": share, "g": g, "glp1_claims_all": 100.0,
            "dm_load": rng.uniform(100, 900, n), "tot_clms": 3000.0, "state": "OH",
            "specialty_group": rng.choice(["primary_care_physician", "endocrinology"], n),
            "region": "Midwest", "other_glp1": 1.0, "urban": rng.integers(0, 2, n),
            "cluster": "c" + (np.arange(n) // 4).astype(str),
        }))  # fmt: skip
    df = pd.concat(rows, ignore_index=True)
    w = Wide(df)
    return w, w.y.copy()


def test_shares_and_effects_sum_to_zero():
    w, s = _panel(effect=0.05)
    sh = shares({"B": s * 100, "rest": (1 - s) * 100}, np.full_like(s, 100.0))
    tot = sh["B"] + sh["rest"]
    assert np.allclose(tot[~np.isnan(tot)], 1)
    a = fit(w, outcome=sh["B"])["overall_0_3"]["att"]
    b = fit(w, outcome=sh["rest"])["overall_0_3"]["att"]
    assert a == pytest.approx(0.05, abs=0.01)
    assert a + b == pytest.approx(0.0, abs=1e-9)  # DR is linear in the outcome


def test_fractional_check_null_and_positive():
    w0, s0 = _panel(effect=0.0, seed=1)
    r0 = frac_fit(w0, s0)
    assert abs(r0["att"]) < 3 * r0["se"] + 0.005
    w1, s1 = _panel(effect=0.08, seed=2)
    assert frac_fit(w1, s1)["att"] > 0.05
