"""Dose-response bins (P16, DEV-7): labels and the merge-small-bins rule."""

import numpy as np
import pandas as pd

from ppg.models.dose_response import CONTACT_CUTS, DOLLAR_CUTS, MIN_BIN, bins


def test_small_top_bins_merge_downward():
    x = pd.Series([50.0] * 500 + [500.0] * 300 + [5_000.0] * 80 + [50_000.0] * 40)
    b = bins(x, DOLLAR_CUTS, "$")
    assert list(b) == ["< $100", "$100–1k", "≥ $1k"]  # 40 < MIN_BIN merged into $1k-10k
    assert int(b["≥ $1k"].sum()) == 120
    assert sum(int(m.sum()) for m in b.values()) == len(x)


def test_all_bins_kept_when_large():
    x = pd.Series(np.repeat([10.0, 200.0, 2_000.0, 20_000.0], MIN_BIN))
    assert list(bins(x, DOLLAR_CUTS, "$")) == ["< $100", "$100–1k", "$1k–10k", "≥ $10k"]


def test_contact_labels_and_untreated_excluded():
    x = pd.Series([1.0] * 200 + [2.0] * 150 + [3.0] * 50 + [6.0] * 120 + [-1.0] * 30)
    b = bins(x, CONTACT_CUTS, "n")
    assert list(b) == ["1 contact", "2–3 contacts", "≥ 4 contacts"]
    assert sum(int(m.sum()) for m in b.values()) == 520  # -1 (not treated) in no bin


def test_merging_continues_while_too_small():
    x = pd.Series([50.0] * 500 + [500.0] * 300 + [5_000.0] * 40 + [50_000.0] * 20)
    assert list(bins(x, DOLLAR_CUTS, "$")) == ["< $100", "≥ $100"]  # 60 still < MIN_BIN
