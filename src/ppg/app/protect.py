"""Linear-programming protection audit for the explorer cube (P24 red-team, D47).

Withholding a cell is not enough when totals are published: an attacker can solve the system of
line sums (components + total along every additive axis) for each withheld value, using what
they know about it (a count is at least 1 and at most the cell's shown prescriber count; amounts
are not negative). `ranges` computes each withheld cell's feasible minimum and maximum with
HiGHS; `violations` flags primarily withheld cells that are not protected:

    counts (n, paid, regular)       feasible range at least COUNT_WIDTH wide
    amounts (usd, claims, tot)      feasible minimum at most AMOUNT_SHARE of the true value
                                    (nobody can prove more than half of a withheld amount)

Only positive values need protecting: a withheld zero is implied by a published zero total, and
zeros are published anyway (as CMS does). A line is given by `lines[ax]`: the indices along axis
`ax` of its components, then its total (last).
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

COUNT_WIDTH = 10
AMOUNT_SHARE = 0.5
COUNTS = ("n", "paid", "regular")


def line_cells(ax: int, idx: tuple, members) -> list[tuple]:
    """Full index tuples of the line through `idx` (the other axes) along `ax`: components,
    then the total."""
    out = []
    for j in members:
        full = list(idx)
        full.insert(ax, j)
        out.append(tuple(full))
    return out


def all_lines(shape, lines: dict):
    """Every line as (axis, other-axis index tuple, cells)."""
    for ax, members in lines.items():
        other = [k for i, k in enumerate(shape) if i != ax]
        for idx in np.ndindex(*other):
            yield ax, idx, line_cells(ax, idx, members)


def ranges(v: np.ndarray, hid: np.ndarray, lo: np.ndarray, hi: np.ndarray, lines: dict,
           need: np.ndarray, want_max: bool) -> tuple[np.ndarray, np.ndarray]:  # fmt: skip
    """Feasible [min, max] of each `need` cell (withheld), given the shown values, the line sums
    and per-cell bounds lo/hi (hi = inf for none). NaN where not computed."""
    mn, mx = np.full(v.shape, np.nan), np.full(v.shape, np.nan)
    hv = [tuple(i) for i in np.argwhere(hid)]
    if not hv or not need.any():
        return mn, mx
    vid = {c: i for i, c in enumerate(hv)}
    parent = list(range(len(hv)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    eqs = []  # (var ids, coefficients, rhs): sum(components) - total = 0
    for _, _, cells in all_lines(v.shape, lines):
        if not any(hid[c] for c in cells):
            continue
        ids, coef, rhs = [], [], 0.0
        for j, c in enumerate(cells):
            s = -1.0 if j == len(cells) - 1 else 1.0
            if hid[c]:
                ids.append(vid[c])
                coef.append(s)
            else:
                rhs -= s * v[c]
        eqs.append((ids, coef, rhs))
        for a in ids[1:]:
            ra, rb = find(ids[0]), find(a)
            if ra != rb:
                parent[ra] = rb
    comp: dict[int, list[int]] = {}
    for i in range(len(hv)):
        comp.setdefault(find(i), []).append(i)
    eq_by: dict[int, list[int]] = {}
    for e, (ids, _, _) in enumerate(eqs):
        eq_by.setdefault(find(ids[0]), []).append(e)
    for root, members in comp.items():
        targets = [i for i in members if need[hv[i]]]
        if not targets:
            continue
        local = {g: n for n, g in enumerate(members)}
        rows, cols, vals, b = [], [], [], []
        for r, e in enumerate(eq_by.get(root, [])):
            ids, coef, rhs = eqs[e]
            for g, cf in zip(ids, coef, strict=True):
                rows.append(r)
                cols.append(local[g])
                vals.append(cf)
            b.append(rhs)
        nv = len(members)
        bounds = [(lo[hv[g]], None if np.isinf(hi[hv[g]]) else hi[hv[g]]) for g in members]
        a_eq = coo_matrix((vals, (rows, cols)), shape=(len(b), nv)).tocsr() if b else None
        for g in targets:
            c = np.zeros(nv)
            c[local[g]] = 1.0
            r = linprog(c, A_eq=a_eq, b_eq=b or None, bounds=bounds, method="highs")
            mn[hv[g]] = r.fun if r.status == 0 else -np.inf
            if want_max:
                r = linprog(-c, A_eq=a_eq, b_eq=b or None, bounds=bounds, method="highs")
                mx[hv[g]] = -r.fun if r.status == 0 else np.inf
    return mn, mx


def attacker_bounds(m: str, cube: dict, hid: dict) -> tuple[np.ndarray, np.ndarray]:
    """What an attacker knows about each withheld value of metric m."""
    v = cube[m]
    lo = np.zeros(v.shape)
    hi = np.full(v.shape, np.inf)
    if m in COUNTS:
        lo = np.minimum(1.0, v)  # withheld counts are positive (zeros are shown)
        if m != "n":
            hi = np.where(~hid["n"], cube["n"], np.inf)  # paid, regular <= prescribers
    return lo, hi


def violations(m: str, cube: dict, hid: dict, sensitive: np.ndarray, lines: dict) -> np.ndarray:
    """Sensitive, positive withheld cells of metric m that the line system pins down too far."""
    v = cube[m]
    need = hid[m] & sensitive & (v > 0)
    if not need.any():
        return np.zeros(v.shape, bool)
    lo, hi = attacker_bounds(m, cube, hid)
    mn, mx = ranges(v, hid[m], lo, hi, lines, need, want_max=m in COUNTS)
    if m in COUNTS:
        return need & ((mx - mn) < COUNT_WIDTH)
    return need & (mn > AMOUNT_SHARE * v + 1e-6)


def complement_for(cell, v: np.ndarray, hid: np.ndarray, lines: dict, weight: dict):
    """The cheapest shown, positive component in a line through `cell` (else a shown total)."""
    best, best_cost, total = None, np.inf, None
    for ax, members in lines.items():
        if cell[ax] not in members:
            continue
        idx = tuple(c for i, c in enumerate(cell) if i != ax)
        cells = line_cells(ax, idx, members)
        for j, c in enumerate(cells[:-1]):
            if not hid[c] and v[c] > 0:
                cost = v[c] * weight[ax][j]
                if cost < best_cost:
                    best, best_cost = c, cost
        if total is None and not hid[cells[-1]] and v[cells[-1]] > 0:
            total = cells[-1]
    return best if best is not None else total


def fallback_complement(cell, v: np.ndarray, hid: np.ndarray, lines: dict, weight: dict):
    """When every line through `cell` is already withheld: the cheapest shown, positive cell in
    any line that touches a withheld cell of the same slice (cell[0]), which widens the whole
    connected system the attacker solves."""
    best, best_cost = None, np.inf
    for ax, _, cells in all_lines(v.shape, lines):
        if cells[0][0] != cell[0] or not any(hid[c] for c in cells):
            continue
        for j, c in enumerate(cells):
            if not hid[c] and v[c] > 0:
                cost = v[c] * (weight[ax][j] if j < len(cells) - 1 else 2.0)
                if cost < best_cost:
                    best, best_cost = c, cost
    return best
