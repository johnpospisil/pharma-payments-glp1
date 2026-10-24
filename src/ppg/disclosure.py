"""Disclosure control for public outputs (CLAUDE.md ethics rule; D37).

Everything committed under report/ becomes public with the repo, so tables written there follow
the same rules as the article: a cell describing 1-10 prescribers is blanked (count and values),
and geography cells are also blanked when one prescriber holds more than half the dollars.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ppg import config


def mask_small(df: pd.DataFrame, count: str, values=(), n: int = config.MIN_CELL) -> pd.DataFrame:
    """Blank `count` and `values` where 0 < count < n (zero cells stay: nobody is in them)."""
    df = df.copy()
    small = (df[count] > 0) & (df[count] < n)
    df[count] = df[count].astype(float)
    df.loc[small, [count, *values]] = np.nan
    return df


def mask_crosstab(xt: pd.DataFrame, n: int = config.MIN_CELL) -> pd.DataFrame:
    """Blank every count cell of 1 to n - 1."""
    return xt.astype(float).mask((xt > 0) & (xt < n))
