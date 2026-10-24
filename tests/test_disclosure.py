"""Disclosure helpers: cells describing 1-10 prescribers are blanked."""

import numpy as np
import pandas as pd

from ppg.disclosure import mask_crosstab, mask_small


def test_mask_small_blanks_count_and_values():
    d = pd.DataFrame({"n": [0, 3, 10, 11, 500], "usd": [0.0, 5.0, 6.0, 7.0, 8.0]})
    m = mask_small(d, "n", ["usd"])
    assert m.n.isna().tolist() == [False, True, True, False, False]
    assert m.usd.isna().tolist() == [False, True, True, False, False]
    assert d.n.tolist() == [0, 3, 10, 11, 500]  # input untouched


def test_mask_crosstab():
    xt = pd.DataFrame({"a": [1, 11], "b": [0, 10]})
    m = mask_crosstab(xt)
    assert np.isnan(m.loc[0, "a"]) and m.loc[1, "a"] == 11
    assert m.loc[0, "b"] == 0 and np.isnan(m.loc[1, "b"])
