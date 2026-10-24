"""Combining estimates across fits by practice-summed influence functions (P19, DEV-10)."""

import numpy as np
import pandas as pd
import pytest

from ppg.models.heterogeneity import combine


def test_difference_of_identical_estimates_has_zero_variance():
    est = {"att": 0.1, "if": pd.Series([0.01, -0.02, 0.03], index=["a", "b", "c"])}
    c = combine([(1.0, est), (-1.0, est)])
    assert c["att"] == pytest.approx(0.0) and c["se"] == pytest.approx(0.0)


def test_disjoint_practices_add_variances_and_shared_ones_covary():
    a = {"att": 0.2, "if": pd.Series([0.03, 0.04], index=["p1", "p2"])}
    b = {"att": 0.1, "if": pd.Series([0.05], index=["p3"])}
    c = combine([(1.0, a), (-1.0, b)])
    assert c["att"] == pytest.approx(0.1)
    assert c["se"] == pytest.approx(np.sqrt(0.03**2 + 0.04**2 + 0.05**2))
    b2 = {"att": 0.1, "if": pd.Series([0.03], index=["p1"])}  # shares practice p1 with a
    assert combine([(1.0, a), (-1.0, b2)])["se"] == pytest.approx(0.04)
