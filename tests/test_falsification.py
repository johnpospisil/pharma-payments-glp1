"""Falsification helpers (P17): ratio-scale (PPML) estimator and the §9 fail rule."""

import numpy as np
import pandas as pd
import pytest

from ppg.models.falsification import _ratio_verdict, _verdict, ppml_fit
from ppg.models.matched import Wide


def _panel(effect: float, seed: int, n: int = 10_000) -> Wide:
    rng = np.random.default_rng(seed)
    g = np.where(rng.random(n) < 0.4, rng.choice([2016, 2018], n), 0)
    scale = rng.gamma(2.0, 50.0, n)
    rows = []
    for t in range(2013, 2021):
        mu = scale * 1.05 ** (t - 2013) * np.where((g > 0) & (t >= g), 1 + effect, 1.0)
        rows.append(pd.DataFrame({"npi": np.arange(n), "year": t, "y": rng.poisson(mu) * 1.0,
                                  "g": g, "glp1_claims_all": 100.0, "dm_load": 1.0,
                                  "tot_clms": 1.0, "state": "OH", "specialty_group": "x",
                                  "region": "Midwest",
                                  "cluster": (np.arange(n) // 3).astype(str)}))  # fmt: skip
    return Wide(pd.concat(rows, ignore_index=True))


def test_ppml_recovers_proportional_effect_and_null():
    w = _panel(0.2, 0)
    r = ppml_fit(w, w.y.copy())
    assert r["att"] == pytest.approx(0.2, abs=0.02)
    assert r["lo"] < r["att"] < r["hi"]
    w0 = _panel(0.0, 1)
    r0 = ppml_fit(w0, w0.y.copy())
    assert r0["lo"] < 0 < r0["hi"] and abs(r0["att"]) < 0.02


def test_fail_rule():
    assert _verdict(0.07, 0.01, 0.12) == "FAIL"  # significant and >= half the comparator
    assert _verdict(0.03, 0.01, 0.12) == "pass"  # significant but small
    assert _verdict(0.08, 0.05, 0.12) == "pass"  # large but CI includes 0
    assert _verdict(-0.08, 0.01, 0.12) == "pass"  # opposite direction
    v = _ratio_verdict({"att": 0.01, "lo": -0.02, "hi": 0.04, "lo90": -0.015, "hi90": 0.035}, 2.0)
    assert v == {"verdict": "pass", "equivalent_to_null": True}
