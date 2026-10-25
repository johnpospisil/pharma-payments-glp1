"""P23: disclosure control of the explorer cube (ppg.app.build), on a synthetic cube."""

import numpy as np
import pytest

from ppg import config
from ppg.app import build as ex


def _with_totals(c: np.ndarray, axes) -> np.ndarray:
    """Components [b, s, t] -> cube with a total appended on each axis in `axes`."""
    out = c
    for ax in axes:
        out = np.concatenate([out, out.sum(ax, keepdims=True)], axis=ax)
    return out


@pytest.fixture(scope="module")
def cube():
    rng = np.random.default_rng(7)
    nb, ns, nt = len(ex.BRAND_KEYS) - 1, len(ex.SPECS), len(ex.STATES) + 1
    n = rng.choice([0, 3, 8, 15, 40, 200, 2000], size=(1, ns, nt)).astype(float)
    n = np.repeat(n, nb, 0)
    paid = np.floor(n * rng.choice([0, 0.05, 0.3, 0.6], size=n.shape))
    regular = np.floor(n * rng.choice([0, 0.04, 0.2, 0.5], size=n.shape))
    usd = paid * rng.lognormal(5, 1.5, size=n.shape)
    share = np.where(paid > 0, rng.uniform(1 / np.maximum(paid, 1), 1), 0)
    top_c = usd * share
    c = {"n": n, "dm": n * 50, "paid": paid, "usd": usd, "regular": regular,
         "claims": regular * 30}  # fmt: skip
    full = {}
    for m, a in c.items():
        x = _with_totals(a, (1, 2))
        # the brand total: sums for additive metrics; distinct counts approximated by the max
        tot = x.sum(0, keepdims=True) if 0 in ex.AXES[m] else x.max(0, keepdims=True)
        full[m] = np.concatenate([x, tot], 0)
    full["n"][:], full["dm"][:] = full["n"][-1], full["dm"][-1]
    t = top_c
    for ax in (1, 2):
        t = np.concatenate([t, t.max(ax, keepdims=True)], axis=ax)
    top = np.concatenate([t, t.max(0, keepdims=True)], 0)
    code = ex.secondary(full, ex.primary(full, top, 2024), top)
    return full, top, code


def test_no_small_counts_shown(cube):
    full, _, code = cube
    for m in ("n", "paid", "regular"):
        small = (full[m] > 0) & (full[m] < config.MIN_CELL)
        assert (code[m][small] < 0).all(), m


def test_no_lone_withheld_cell_in_any_line(cube):
    full, _, code = cube
    for m in ex.METRICS:
        for ax in ex.AXES[m]:
            c, v = np.moveaxis(code[m], ax, -1), np.moveaxis(full[m], ax, -1)
            lone = ((c < 0).sum(-1) == 1) & (v[..., -1] > 0)
            assert not lone.any(), (m, ax)


def test_state_dollars_pass_dominance(cube):
    full, top, code = cube
    shown = (code["usd"] == 0) & (full["usd"] > 0) & ex._geo(full["usd"].shape)
    assert not (shown & (top > config.DOMINANCE * full["usd"])).any()


def test_withheld_counts_take_their_values(cube):
    _, _, code = cube
    assert (code["usd"][code["paid"] < 0] < 0).all()
    assert (code["claims"][code["regular"] < 0] < 0).all()
    for m in ex.METRICS:
        assert (code[m][code["n"] < 0] < 0).all(), m


def test_cell_withholding_is_the_same_for_every_brand(cube):
    _, _, code = cube
    assert ((code["n"] < 0) == (code["n"][-1:] < 0)).all()
