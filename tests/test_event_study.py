"""Event-study helpers (P13): Holm adjustment, HonestDiD robust-Mbar rule, 2-way FE solver."""

import numpy as np
import pandas as pd
import pytest

from ppg.models.event_study import _event_names, _two_way_fe, holm, robust_mbar


def test_holm():
    adj = holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adj == pytest.approx({"a": 0.03, "b": 0.06, "c": 0.06})


def test_robust_mbar_rule():
    rm = [
        {"Mbar": 0.0, "lb": 0.01, "ub": 0.02},
        {"Mbar": 0.25, "lb": 0.003, "ub": 0.02},
        {"Mbar": 0.5, "lb": -0.002, "ub": 0.03},
        {"Mbar": 0.75, "lb": 0.001, "ub": 0.04},
    ]
    assert robust_mbar(rm) == 0.25  # contiguous from 0; a later exclusion does not count
    assert robust_mbar([{"Mbar": 0.0, "lb": None, "ub": None}]) is None  # unsolved: no claim


def test_two_way_fe_recovers_effects():
    rng = np.random.default_rng(0)
    i, j = rng.integers(0, 300, 6000), rng.integers(0, 20, 6000)
    a0, b0 = rng.normal(size=300), rng.normal(size=20)
    a, b, *_ = _two_way_fe(a0[i] + b0[j], i, j)
    assert np.allclose(a[i] + b[j], a0[i] + b0[j], atol=1e-6)


def test_event_names():
    names = _event_names(pd.Series([1.0, 2.0, 3.0], index=["rel::-3", "rel::0", "treat"]), "rel")
    assert names == {-3: "rel::-3", 0: "rel::0"}
