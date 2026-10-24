"""Panel-form CS doubly robust estimator (DEV-5): DRDID::drdid_panel and the cell logic."""

import numpy as np
import pytest

from ppg.models.cs_panel import drdid_panel


def test_drdid_no_covariates_is_simple_did():
    rng = np.random.default_rng(0)
    D = (rng.random(5000) < 0.3).astype(float)
    dy = rng.normal(size=5000) + 0.2 * D
    att, inf = drdid_panel(dy, D, np.ones((5000, 1)))
    assert att == pytest.approx(dy[D == 1].mean() - dy[D == 0].mean(), abs=1e-10)
    assert abs(inf.mean()) < 1e-10  # influence function is mean zero


def test_drdid_removes_confounding_by_covariate():
    rng = np.random.default_rng(1)
    n = 40_000
    x = rng.normal(size=n)
    D = (rng.random(n) < 1 / (1 + np.exp(-x))).astype(float)  # treated have higher x
    dy = 0.5 * x + 0.1 * D + rng.normal(scale=0.5, size=n)  # x drives the trend
    X = np.column_stack([np.ones(n), x])
    att, inf = drdid_panel(dy, D, X)
    se = np.sqrt((inf**2).sum()) / n
    assert att == pytest.approx(0.1, abs=4 * se)
    assert dy[D == 1].mean() - dy[D == 0].mean() > 0.2  # the unadjusted contrast is biased
