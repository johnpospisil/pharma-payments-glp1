"""Callaway & Sant'Anna, doubly robust, panel form, for an unbalanced panel (DEV-5).

R `did` with allow_unbalanced_panel = TRUE falls back to its repeated-cross-section estimator,
which takes covariates from each row's own year (post-payment years included) and does not
difference within physician. The registered specification (§6) is the panel estimator with
covariates from the base period. This module applies it cell by cell: for each ATT(g, t), the
physicians observed in both the base year and t, treated cohort g against not-yet-treated
controls, covariates from min(base, t) (as R `did` does with a balanced panel), and
Sant'Anna & Zhao's (2020) locally efficient DR estimator (DRDID::drdid_panel) with its
influence function. Aggregation follows did::aggte(type = "dynamic"): cohort-size weights,
then the average of e = 0..3. Standard errors: influence functions summed by practice.

    python -m ppg.models.cs_panel all           # three brands, varying + universal base
    python -m ppg.models.cs_panel validate      # vs R did on the balanced Ozempic sample
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from ppg import config
from ppg.models.data import LAST_YEAR, PRIMARY_BRANDS, frame
from ppg.models.event_study import QA, _p
from ppg.models.matched import Wide, _se, _vcov

EVENTS = tuple(range(-9, 6))


def _logit(X: np.ndarray, D: np.ndarray, iters: int = 25) -> tuple[np.ndarray, np.ndarray]:
    """Logistic regression by Newton-Raphson; returns fitted p and (X'WX)^-1."""
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(X @ b)))
        W = p * (1 - p)
        H = X.T @ (X * W[:, None])
        step = np.linalg.lstsq(H, X.T @ (D - p), rcond=None)[0]
        b += step
        if np.max(np.abs(step)) < 1e-10:
            break
    p = 1 / (1 + np.exp(-(X @ b)))
    H = X.T @ (X * (p * (1 - p))[:, None])
    return np.minimum(p, 1 - 1e-6), np.linalg.pinv(H)


def drdid_panel(dy: np.ndarray, D: np.ndarray, X: np.ndarray) -> tuple[float, np.ndarray]:
    """DRDID::drdid_panel (unit weights). Returns ATT and the influence function (mean scale)."""
    n = len(dy)
    ps, Hinv = _logit(X, D)
    c = D == 0
    beta = np.linalg.lstsq(X[c], dy[c], rcond=None)[0]
    out = X @ beta
    w_t = D.astype(float)
    w_c = ps * (1 - D) / (1 - ps)
    att_t, att_c = w_t * (dy - out), w_c * (dy - out)
    eta_t, eta_c = att_t.mean() / w_t.mean(), att_c.mean() / w_c.mean()
    # influence function (Sant'Anna & Zhao 2020; DRDID::drdid_panel)
    wols = (1 - D)[:, None] * X
    xpx_inv = np.linalg.pinv(wols.T @ X / n)
    lin_ols = (wols * (dy - out)[:, None]) @ xpx_inv
    lin_ps = ((D - ps)[:, None] * X) @ (Hinv * n)
    inf_t = (att_t - w_t * eta_t - lin_ols @ (w_t[:, None] * X).mean(0)) / w_t.mean()
    m2 = (w_c * (dy - out - eta_c))[:, None] * X
    inf_c = att_c - w_c * eta_c + lin_ps @ m2.mean(0) - lin_ols @ (w_c[:, None] * X).mean(0)
    inf_c /= w_c.mean()
    return float(eta_t - eta_c), inf_t - inf_c


def design(
    w: Wide,
    i: np.ndarray,
    year: int,
    covariates: bool,
    extra: tuple[np.ndarray, ...] = (),
    geo: str = "region",
) -> np.ndarray:
    """Registered covariates (§6) measured in `year`: specialty, region, log diabetes claims,
    log total claims, any other GLP-1, urban; plus any `extra` physician x year arrays (P15:
    the outcome's own base-year share); geo='state' swaps region for state (P18); constant
    columns dropped."""
    if not covariates:
        return np.ones((len(i), 1))
    c = w.col(year)
    cols = [np.ones(len(i))]
    for codes in (w.spec[i], (w.state if geo == "state" else w.reg)[i, c]):
        for k in np.unique(codes)[1:]:
            cols.append((codes == k).astype(float))
    cols += [np.log1p(w.dm[i, c]), np.log1p(w.tot[i, c]), w.other[i, c], w.urban[i, c]]
    cols += [x[i, c] for x in extra]
    X = np.column_stack(cols)
    keep = np.r_[True, X[:, 1:].std(0) > 0]
    return X[:, keep]


def fit(
    w: Wide,
    base: str = "varying",
    covariates: bool = True,
    outcome: np.ndarray | None = None,
    start: int | None = None,
    extra: tuple[np.ndarray, ...] = (),
    keep: np.ndarray | None = None,
    control: str = "notyettreated",
    skip_base: tuple[int, ...] = (),
    geo: str = "region",
) -> dict:
    """outcome: physician x year array replacing w.y (NaN = not defined that year).
    start: first year usable as a base year (default: the P13 window start).
    control: 'notyettreated' (primary) or 'nevertreated'; skip_base: base years not used
    (P18: 2020); geo: 'region' (registered) or 'state' (P18)."""
    start = w.start if start is None else start
    yy = w.y if outcome is None else outcome
    nunit = len(w.npi)
    keep = np.ones(len(w.npi), bool) if keep is None else keep  # treated subgroup (P16)
    sizes = pd.Series(w.g[(w.g > 0) & keep]).value_counts()
    cells, ife = [], {}
    for g in w.cohorts():
        for t in range(start + 1, LAST_YEAR + 1):
            e = t - g
            if e == -1 and base == "universal":
                continue
            b = g - 1 if (t >= g or base == "universal") else t - 1
            if b < start or b in skip_base:
                continue
            y1, y0 = yy[:, w.col(t)], yy[:, w.col(b)]
            ok = ~np.isnan(y1) & ~np.isnan(y0)
            # cohort g is never its own control, even members outside the `keep` subgroup
            nyt = (w.g > max(t, b)) & (w.g != g) if control == "notyettreated" else False
            ok &= ((w.g == g) & keep) | (w.g == 0) | nyt
            i = np.flatnonzero(ok)
            D = (w.g[i] == g).astype(float)
            if D.sum() < 1 or (1 - D).sum() < 1:
                continue
            X = design(w, i, min(b, t), covariates, extra, geo)
            att, inf = drdid_panel(y1[i] - y0[i], D, X)
            v = np.zeros(nunit)
            np.add.at(v, i, inf / len(i))
            cells.append({"g": g, "t": t, "e": e, "att": att, "se": _se(w, v),
                          "treated": int(D.sum()), "n": len(i)})  # fmt: skip
            ife.setdefault(e, []).append((g, att, v))
    events, cols = [], []
    for e in sorted(ife):
        tot = sum(sizes[g] for g, *_ in ife[e])
        att = sum(sizes[g] / tot * a for g, a, _ in ife[e])
        v = sum(sizes[g] / tot * x for g, _, x in ife[e])
        events.append({"e": e, "att": att, "se": _se(w, v), "cohorts": len(ife[e])})
        cols.append(v)
    ev = pd.DataFrame(events)
    V = _vcov(w, np.column_stack(cols))
    es = ev.e.to_numpy()

    def lin(sel: np.ndarray) -> dict:
        lv = sel / sel.sum()
        return {"att": float(lv @ ev.att), "se": float(np.sqrt(lv @ V @ lv))}

    pre = (es <= -2) & (np.diag(V) > 1e-14)  # drop mechanically zero cells (pre-launch)
    wald = None
    if pre.any():
        from scipy.stats import chi2

        bvec, Vp = ev.att[pre].to_numpy(), V[np.ix_(pre, pre)]
        stat = float(bvec @ np.linalg.solve(Vp, bvec))
        wald = {"stat": stat, "df": int(pre.sum()), "p": float(chi2.sf(stat, pre.sum()))}

    return {
        "base": base,
        "covariates": covariates,
        "cohort_sizes": {
            str(k): (int(v) if v >= config.MIN_CELL else "<11")
            for k, v in sizes.sort_index().items()
        },  # fmt: skip
        "att_gt": [c for c in cells if c["treated"] >= config.MIN_CELL],
        "event": ev.to_dict("records"),
        "overall_0_3": lin(((es >= 0) & (es <= 3)).astype(float)),
        "overall_1_3": lin(((es >= 1) & (es <= 3)).astype(float)),
        "pretrend_wald": wald,
        "event_vcov": {"e": es.tolist(), "beta": ev.att.tolist(), "V": V.tolist()},
    }


def run(brand: str, df: pd.DataFrame | None = None, tag: str = "panel", **kw) -> dict:
    df = frame(brand) if df is None else df
    res = fit(Wide(df), **kw) | {"brand": brand, "frame": {
        "physicians": int(df.npi.nunique()),
        "treated_physicians": int((df.groupby("npi").g.first() > 0).sum())}}  # fmt: skip
    o = res["overall_0_3"]
    res["overall_0_3"] |= {"p": _p(o["att"], o["se"])}
    QA.mkdir(parents=True, exist_ok=True)
    (QA / f"{tag}_{brand}.json").write_text(json.dumps(res, indent=1, default=float))
    print(f"{brand} {tag}: ATT(0-3) = {o['att']:.6f} (se {o['se']:.5f}); pre-trend p = "
          f"{res['pretrend_wald']['p']:.3g}", flush=True)  # fmt: skip
    return res


def validate() -> None:
    """Balanced Ozempic sample: must reproduce R did (panel mode) = 0.12582940704."""
    df = frame("Ozempic")
    b = df[df.groupby("npi").year.transform("size") == df.year.nunique()].copy()
    run("Ozempic", b, tag="validate_balanced")


def run_all() -> None:
    from ppg.progress import Progress

    with Progress("cs_panel") as p:
        for b in PRIMARY_BRANDS:
            p.add(b, total=3, unit="fits")
        for b in PRIMARY_BRANDS:
            p.start(b)
            df = frame(b)
            for tag, kw in [("panel", {}), ("panel_universal", {"base": "universal"}),
                            ("panel_nocov", {"covariates": False})]:  # fmt: skip
                run(b, df, tag=tag, **kw)
                p.advance(b, 1)
            p.finish(b)


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "all"
    {"all": run_all, "validate": validate}[cmd]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
