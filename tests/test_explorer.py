"""P23/P24: disclosure control of the explorer cube (ppg.app.build, ppg.app.protect), on synthetic
data: the primary rules, no lone withheld cell, and the LP attack (D47)."""

import numpy as np
import pytest

from ppg import config
from ppg.app import build as ex
from ppg.app import protect


def test_lp_pins_down_the_reviewers_example():
    # one state's column: three withheld 1-10 cells, the shown ones and the total leave 3 for them
    v = np.array([[26.0], [27.0], [14.0], [1.0], [1.0], [1.0], [70.0]])
    hid = np.zeros(v.shape, bool)
    hid[3:6] = True
    lines = {0: list(range(7))}
    lo, hi = np.minimum(1.0, v), np.full(v.shape, np.inf)
    mn, mx = protect.ranges(v, hid, lo, hi, lines, hid, want_max=True)
    assert np.allclose(mn[3:6, 0], 1) and np.allclose(mx[3:6, 0], 1)  # recovered exactly
    cube = {"paid": v, "n": np.full(v.shape, 100.0)}
    bad = protect.violations("paid", cube, {"paid": hid, "n": np.zeros(v.shape, bool)}, hid, lines)
    assert bad[3:6].all()


def test_withholding_one_more_cell_protects_it():
    v = np.array([[26.0], [27.0], [14.0], [1.0], [1.0], [1.0], [70.0]])
    hid = np.zeros(v.shape, bool)
    hid[3:6] = True
    hid[2] = True  # the complement: 14 more units of slack
    lines = {0: list(range(7))}
    cube = {"paid": v, "n": np.full(v.shape, 100.0)}
    bad = protect.violations("paid", cube, {"paid": hid, "n": np.zeros(v.shape, bool)}, hid, lines)
    assert not bad[3:6].any()


@pytest.fixture(scope="module")
def cube():
    """A synthetic year: components drawn at random, totals added along the published lines."""
    rng = np.random.default_rng(7)
    nb, ns, nt = len(ex.BRAND_KEYS), len(ex.SPECS) + 1, len(ex.STATE_KEYS)
    comp = np.zeros((nb, ns, nt), bool)
    comp[:, : len(ex.SPECS), : nt - 1] = True
    n = np.where(comp, rng.choice([0, 3, 8, 15, 40, 200, 2000], size=(1, ns, nt)), 0.0)
    n = np.repeat(n[:1], nb, 0)
    frac = lambda opts: rng.choice(opts, size=n.shape)  # noqa: E731
    c = {"n": n, "tot": n * 400, "paid": np.floor(n * frac([0, 0.05, 0.3, 0.6])),
         "regular": np.floor(n * frac([0, 0.04, 0.2, 0.5]))}  # fmt: skip
    c["usd"] = c["paid"] * rng.lognormal(5, 1.5, size=n.shape)
    c["claims"] = c["regular"] * 30
    top = c["usd"] * np.where(c["paid"] > 0, rng.uniform(0.1, 1, size=n.shape), 0)
    phys = list(range(len(ex.PHYSICIANS)))
    for m in ex.METRICS:  # totals: physicians -> All physicians; states -> US
        a = c[m]
        a[:, ex.S_TOTAL, :] = a[:, phys, :].sum(1)
        a[:, :, ex.US] = a[:, :, :-1].sum(2)
    top[:, ex.S_TOTAL, :] = top[:, phys, :].max(1)
    top[:, :, ex.US] = top[:, :, :-1].max(2)
    for m in ex.CELL_LEVEL:
        c[m][:] = c[m][-1]
    code = ex.secondary(c, ex.primary(c, top, 2024), top)
    code = ex.lp_protect(c, code, top)
    return c, top, code


def test_no_small_counts_shown(cube):
    c, _, code = cube
    for m in ("n", "paid", "regular"):
        small = (c[m] > 0) & (c[m] < config.MIN_CELL)
        assert (code[m][small] < 0).all(), m


def test_no_lone_withheld_cell_in_any_line(cube):
    c, _, code = cube
    for m in ex.METRICS:
        for _, _, cells in protect.all_lines(c[m].shape, ex.LINES):
            hid = [code[m][x] < 0 and code[m][x] != -4 for x in cells]
            assert not (sum(hid) == 1 and c[m][cells[-1]] > 0), (m, cells[0])


def test_lp_attack_finds_nothing(cube):
    c, _, code = cube
    k = len(ex.PUBLISHED)
    sub = {m: a[:k] for m, a in c.items()}
    hid = {m: (code[m][:k] < 0) & (code[m][:k] != -4) for m in ex.METRICS}
    for m in ex.METRICS:
        sens = (code[m][:k] == -1) | (code[m][:k] == -2)
        assert not protect.violations(m, sub, hid, sens, ex.LINES).any(), m


def test_state_dollars_pass_dominance(cube):
    c, top, code = cube
    shown = (code["usd"] == 0) & (c["usd"] > 0) & ex._geo(c["usd"].shape)
    assert not (shown & (top > config.DOMINANCE * c["usd"])).any()


def test_withheld_counts_take_their_values(cube):
    _, _, code = cube
    assert (code["usd"][code["paid"] < 0] < 0).all()
    assert (code["claims"][code["regular"] < 0] < 0).all()
    for m in ex.METRICS:
        assert (code[m][code["n"] < 0] < 0).all(), m


def test_cell_withholding_is_the_same_for_every_brand(cube):
    _, _, code = cube
    assert ((code["n"] < 0) == (code["n"][-1:] < 0)).all()
