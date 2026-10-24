"""Brand switching (P15, H5): the paid brand's share of the physician's GLP-1 claims.

    python -m ppg.models.switching all       # estimates for Trulicity, Victoza, Ozempic, Mounjaro
    python -m ppg.models.switching report    # tables, chart 5 (dumbbells), share-sources chart

Outcome (prereg §5): B's share of the physician's observed GLP-1 claims, defined in years with any
observed GLP-1 claims. Each ATT(g, t) uses physicians with a defined share in both the base year
and t, so it measures switching among physicians already prescribing GLP-1s (intensive margin).

Estimators (D28): panel-form CS-DR (`cs_panel`), its CEM-matched counterpart (`matched`), and a
fractional-response check that assumes parallel trends in the log-odds of the share. Mounjaro has
no pre-launch share, so it is analysed relative to launch (D7): cohorts from the launch year 2022,
base year 2021. Shares of all six brand groups are estimated for each exposure; because the DR
estimator is linear in the outcome and the shares sum to one, the six effects sum to zero, which
shows where the paid brand's share comes from.

Decomposition: ATT on B's claims = s * ATT on GLP-1 class claims (class growth at the treated
physicians' pre-payment share s) + ATT on (B claims - s * class claims) (switching).
"""

from __future__ import annotations

import json
import sys

import duckdb
import numpy as np
import pandas as pd

from ppg import config
from ppg.models.cs_panel import fit
from ppg.models.event_study import QA, _p
from ppg.models.matched import Wide, _se, estimate, load, strata

GROUPS = ("Ozempic", "Trulicity", "Victoza", "Mounjaro", "Rybelsus", "Other GLP-1")
EXPOSURES = {"Trulicity": {}, "Victoza": {}, "Ozempic": {}, "Mounjaro": {"first_cohort": 2022}}
FIT_START = {"Mounjaro": 2021}  # base year before launch (the panel's Mounjaro rows start 2022)
DUMBBELL_E = 2  # post year for chart 5 (g + 2)


def claims(w: Wide) -> dict[str, np.ndarray]:
    """Observed claims per brand group (physician x year); 0 when present without an observed
    row (0-10 claims or none), NaN when the physician is not in Part D that year."""
    npis = pd.DataFrame({"npi": w.npi})
    con = duckdb.connect()
    con.register("npis", npis)
    named = ", ".join(f"'{g}'" for g in GROUPS[:-1])
    d = con.execute(
        f"""SELECT b.npi, b.year,
                   CASE WHEN b.brand IN ({named}) THEN b.brand ELSE 'Other GLP-1' END AS grp,
                   sum(b.claims) AS claims
            FROM '{config.PARQUET_DIR}/panel/panel_brand.parquet' b JOIN npis USING (npi)
            WHERE b.status = 'observed' AND b.year >= {w.y0}
            GROUP BY ALL"""
    ).df()
    present = ~np.isnan(w.tot)
    out = {}
    for g in GROUPS:
        a = np.where(present, 0.0, np.nan)
        x = d[d.grp == g]
        a[np.searchsorted(w.npi, x.npi.to_numpy()), x.year.to_numpy() - w.y0] = x.claims
        out[g] = a
    total = sum(out.values())
    assert np.allclose(total[present], w.cls[present]), "brand groups must add up to class claims"
    return out


def shares(c: dict[str, np.ndarray], cls: np.ndarray) -> dict[str, np.ndarray]:
    with np.errstate(invalid="ignore", divide="ignore"):
        return {g: np.where(cls > 0, a / cls, np.nan) for g, a in c.items()}


# ------------------------------------------------------------- fractional-response check


def _cell(w: Wide, s: np.ndarray, g: int, t: int, m: pd.DataFrame | None):
    """Units in ATT(g, t) with a share in g - 1 and t: (index, treated, weight). With CEM
    strata m, controls get CEM weights recomputed among those present (as in matched.cell)."""
    y1, y0 = s[:, w.col(t)], s[:, w.col(g - 1)]
    ok = ~np.isnan(y1) & ~np.isnan(y0) & ((w.g == g) | (w.g == 0) | (w.g > t))
    if m is None:
        i = np.flatnonzero(ok)
        return i, w.g[i] == g, np.ones(len(i))
    c = m[ok[m.i]]
    n = c.groupby("s").treated.agg(nt="sum", n="size")
    n["nc"] = n.n - n.nt
    c = c.join(n[["nt", "nc"]], on="s")
    c = c[(c.nt > 0) & (c.nc > 0)]
    wt = np.where(c.treated, 1.0, c.nt / c.nc)
    return c.i.to_numpy(), c.treated.to_numpy(), wt


def frac_fit(w: Wide, s: np.ndarray, matched: bool = False) -> dict:
    """Fractional-response DiD (H5): parallel trends in the log-odds of the mean share,
    ATT(g,t) = m_T1 - expit(logit m_T0 + logit m_C1 - logit m_C0), no covariates; with
    matched=True the controls are CEM-weighted (registered strata). Delta-method influence
    functions, cohort-size aggregation, average of e = 0..3. Cells where a mean share is 0 or 1
    (a brand before launch) have no log-odds and are skipped and counted."""
    nunit = len(w.npi)
    sizes = pd.Series(w.g[w.g > 0]).value_counts()
    by_e: dict[int, list] = {}
    skipped = 0
    for g in w.cohorts():
        m = strata(w, g, "registered") if matched else None
        for e in range(0, 4):
            t = g + e
            if t > w.years[-1]:
                continue
            i, tr, wt = _cell(w, s, g, t, m)
            if tr.sum() < 1 or (~tr).sum() < 1:
                continue
            y1, y0 = s[i, w.col(t)], s[i, w.col(g - 1)]
            grp = {"T": tr, "C": ~tr}
            mean = {f"{k}{p}": np.average(y[ix], weights=wt[ix])
                    for k, ix in grp.items() for p, y in (("1", y1), ("0", y0))}  # fmt: skip
            if min(mean.values()) <= 0 or max(mean.values()) >= 1:
                skipped += 1  # log-odds undefined (e.g. a brand before launch)
                continue
            z = _logit(mean["T0"]) + _logit(mean["C1"]) - _logit(mean["C0"])
            cf = 1 / (1 + np.exp(-z))
            d = cf * (1 - cf)
            vt = {k: x * (1 - x) for k, x in mean.items()}
            wT, wC = wt[tr].sum(), wt[~tr].sum()
            inf = np.where(
                tr,
                ((y1 - mean["T1"]) - d * (y0 - mean["T0"]) / vt["T0"]) / wT,
                -d * ((y1 - mean["C1"]) / vt["C1"] - (y0 - mean["C0"]) / vt["C0"]) * wt / wC,
            )
            v = np.zeros(nunit)
            np.add.at(v, i, inf)
            by_e.setdefault(e, []).append((g, mean["T1"] - cf, v))
    atts, ifs = [], []
    for e in sorted(by_e):
        tot = sum(sizes[g] for g, *_ in by_e[e])
        atts.append(sum(sizes[g] / tot * a for g, a, _ in by_e[e]))
        ifs.append(sum(sizes[g] / tot * x for g, _, x in by_e[e]))
    if not atts:
        return {"att": None, "se": None, "skipped_cells": skipped,
                "note": "undefined: every cell has a mean share of 0 or 1"}  # fmt: skip
    return {"att": float(np.mean(atts)), "se": _se(w, sum(ifs) / len(ifs)),
            "skipped_cells": skipped}  # fmt: skip


def _logit(p: float) -> float:
    return float(np.log(p / (1 - p)))


# ------------------------------------------------------------- dumbbells (chart 5 data)


def dumbbell(w: Wide, s: np.ndarray, e: int = DUMBBELL_E) -> dict:
    """Mean share at g - 1 and g + e: paid physicians vs CEM-matched not-yet-paid physicians
    (registered strata; CEM weights recomputed among those with a share in both years)."""
    acc = {k: 0.0 for k in ("tp", "tq", "cp", "cq", "n")}
    for g in w.cohorts():
        t = g + e
        if t > w.years[-1]:
            continue
        m = strata(w, g, "registered")
        if m.empty:
            continue
        pre, post = s[m.i, w.col(g - 1)], s[m.i, w.col(t)]
        gi = w.g[m.i]
        ok = ~np.isnan(pre) & ~np.isnan(post) & (m.treated.to_numpy() | (gi == 0) | (gi > t))
        c = m.assign(pre=pre, post=post)[ok]
        n = c.groupby("s").treated.agg(nt="sum", n="size")
        n["nc"] = n.n - n.nt
        c = c.join(n[["nt", "nc"]], on="s")
        c = c[(c.nt > 0) & (c.nc > 0)]
        tr = c[c.treated]
        co = c[~c.treated]
        wc = co.nt / co.nc
        k = len(tr)
        acc["tp"] += tr.pre.sum()
        acc["tq"] += tr.post.sum()
        acc["cp"] += (wc * co.pre).sum()
        acc["cq"] += (wc * co.post).sum()
        acc["n"] += k
    n = acc.pop("n")
    return {
        "paid_pre": acc["tp"] / n,
        "paid_post": acc["tq"] / n,
        "control_pre": acc["cp"] / n,
        "control_post": acc["cq"] / n,
        "paid_physicians": int(n),
        "post_event": e,
    }


# ------------------------------------------------------------- run


def run_brand(brand: str, p=None) -> dict:
    w = load(brand, **EXPOSURES[brand])
    c = claims(w)
    sh = shares(c, w.cls)
    own = sh[brand]
    kw = {"start": FIT_START.get(brand)}
    res: dict = {"brand": brand, "first_cohort": int(min(w.cohorts())), "shares": {}, "matched": {}}
    for g in GROUPS:
        r = fit(w, outcome=sh[g], **kw)
        res["shares"][g] = r["overall_0_3"] | {"p": _p(**r["overall_0_3"])}
        a = fit(w, outcome=sh[g], extra=(sh[g],), **kw)["overall_0_3"]
        res.setdefault("base_adjusted", {})[g] = a | {"p": _p(**a)}
        if g == brand:
            res["own_event"] = fit(w, base="universal", outcome=own, **kw)["event"]
            res["own_pretrend_wald"] = r["pretrend_wald"]
            res["own_cells_treated"] = int(sum(x["treated"] for x in r["att_gt"] if x["e"] == 0))
        m = estimate(w, "registered", outcome=sh[g])
        res["matched"][g] = m["overall_0_3"] | {"p": _p(**m["overall_0_3"])}
        if g == brand:
            res["matched_own_event"] = m["event"]
            res["matched_own_pretrend_wald"] = m["pretrend_wald"]
        if p:
            p.advance(brand, 1)
    res["fractional"] = frac_fit(w, own)
    res["fractional_matched"] = frac_fit(w, own, matched=True)
    res["dumbbell"] = dumbbell(w, own)
    # decomposition on all physicians present in both years (class claims may be 0)
    base_rows = [(i, g - 1) for g in w.cohorts() for i in np.flatnonzero(w.g == g)]
    bi = np.array([r[0] for r in base_rows])
    bt = np.array([w.col(r[1]) for r in base_rows])
    sb = float(np.nansum(c[brand][bi, bt]) / np.nansum(w.cls[bi, bt]))
    dec = {}
    for name, y in [
        ("brand_claims", c[brand]),
        ("class_claims", w.cls),
        ("switching", c[brand] - sb * w.cls),
    ]:
        dec[name] = fit(w, outcome=y, **kw)["overall_0_3"]
    dec["class_component"] = {
        "att": sb * dec["class_claims"]["att"],
        "se": sb * dec["class_claims"]["se"],
    }
    dec["pre_share_treated"] = sb
    tot = dec["brand_claims"]["att"]
    dec["switching_fraction"] = dec["switching"]["att"] / tot if tot else None
    res["decomposition"] = dec
    QA.mkdir(parents=True, exist_ok=True)
    (QA / f"switching_{brand}.json").write_text(json.dumps(res, indent=1, default=float))
    o = res["shares"][brand]
    print(
        f"{brand}: own share ATT {o['att']:.4f} (se {o['se']:.4f}); matched "
        f"{res['matched'][brand]['att']:.4f}; switching fraction "
        f"{dec['switching_fraction']:.2f}",
        flush=True,
    )
    return res


def run_all() -> None:
    from ppg.progress import Progress

    with Progress("switching") as p:
        for b in EXPOSURES:
            p.add(b, total=len(GROUPS), unit="outcomes")
        for b in EXPOSURES:
            p.start(b)
            run_brand(b, p)
            p.finish(b)


# ------------------------------------------------------------- report


def report() -> dict:
    res = {b: json.loads((QA / f"switching_{b}.json").read_text()) for b in EXPOSURES}
    rows = []
    for b, r in res.items():
        for g in GROUPS:
            for est, o in [
                ("primary", r["shares"][g]),
                ("base_adjusted", r["base_adjusted"][g]),
                ("matched", r["matched"][g]),
            ]:
                rows.append(
                    {
                        "exposure": b,
                        "share_of": g,
                        "estimate": est,
                        "att": o["att"],
                        "se": o["se"],
                        "lo": o["att"] - 1.96 * o["se"],
                        "hi": o["att"] + 1.96 * o["se"],
                        "p": o["p"],
                    }
                )
    est = pd.DataFrame(rows)
    est.to_csv(config.QA_DIR / "switching_estimates.csv", index=False)
    summary = {
        b: {
            "own_share": r["shares"][b],
            "own_share_matched": r["matched"][b],
            "own_share_base_adjusted": r["base_adjusted"][b],
            "own_share_fractional": r["fractional"],
            "own_share_fractional_matched": r["fractional_matched"],
            "pretrend_wald": r["own_pretrend_wald"],
            "matched_pretrend_wald": r["matched_own_pretrend_wald"],
            "decomposition": r["decomposition"],
            "dumbbell": r["dumbbell"],
            "first_cohort": r["first_cohort"],
        }
        for b, r in res.items()
    }
    (config.QA_DIR / "switching.json").write_text(json.dumps(summary, indent=1, default=float))
    chart5(summary)
    sources_chart(est)
    print(est[est.exposure == est.share_of].to_string(index=False))
    return summary


def chart5(summary: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from ppg.viz.figures import BRAND_COLOR, GRID, INK, INK2, MUTED, SURFACE, _save, _style

    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    labels, y = [], 0
    for b, r in summary.items():
        d = r["dumbbell"]
        for who, pre, post, col in [
            ("paid", d["paid_pre"], d["paid_post"], BRAND_COLOR[b]),
            ("matched, not yet paid", d["control_pre"], d["control_post"], MUTED),
        ]:
            ax.plot([pre * 100, post * 100], [y, y], color=col, lw=2, zorder=2)
            ax.scatter(pre * 100, y, s=56, facecolors=SURFACE, edgecolors=col, lw=2, zorder=3)
            ax.scatter(post * 100, y, s=56, color=col, ec=SURFACE, lw=1.5, zorder=4)
            ax.annotate(
                f"{post * 100:.0f}%",
                (post * 100, y),
                xytext=(8 if post >= pre else -8, 0),
                textcoords="offset points",
                ha="left" if post >= pre else "right",
                va="center",
                fontsize=8.5,
                color=INK2,
            )
            labels.append((y, f"{b}: {who}"))
            y -= 1
        y -= 0.6
    ax.set_yticks([p for p, _ in labels], [t for _, t in labels], fontsize=9)
    _style(ax, grid="x")
    ax.axhline(0.5, color=GRID, lw=0)
    ax.set_xlim(0, None)
    ax.set_xlabel("Brand's share of the physician's GLP-1 claims (%)", color=INK2)
    ax.scatter(
        [], [], s=56, facecolors=SURFACE, edgecolors=MUTED, lw=2, label="Year before first payment"
    )
    ax.scatter([], [], s=56, color=MUTED, label="Two years after")
    ax.legend(loc="lower right", frameon=False, fontsize=8.5)
    fig.suptitle(
        "The paid brand's share of GLP-1 prescribing, before and after the first payment",
        x=0.01,
        ha="left",
        fontsize=11,
        color=INK,
    )
    fig.tight_layout(rect=(0, 0.1, 1, 0.95))
    _save(
        fig,
        "chart5_brand_share_dumbbells",
        "Physicians already prescribing GLP-1s (any brand ≥ 11 claims) in both years, pooled over "
        "first-payment cohorts with two follow-up years; controls: not yet paid by then, matched "
        "(CEM) on pre-payment brand status, GLP-1 level and growth, diabetes load, volume, "
        "specialty × state. Mounjaro: share relative to launch (2021 = 0).\nSource: CMS Open "
        "Payments, Medicare Part D Prescribers. Associations, not proof of causation.",
    )


def sources_chart(est: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from ppg.viz.figures import AXIS, BRAND_COLOR, INK, INK2, OTHER, _save, _style

    exps = list(EXPOSURES)
    fig, axes = plt.subplots(1, len(exps), figsize=(12, 3.8), sharey=True)
    for ax, b in zip(axes, exps, strict=True):
        ypos = np.arange(len(GROUPS))[::-1]
        cols = [BRAND_COLOR.get(g, OTHER) for g in GROUPS]
        for kind, dy, alpha, label in [
            ("primary", 0.19, 1.0, "Covariates at g − 1"),
            ("base_adjusted", -0.19, 0.45, "… plus that brand's share at g − 1"),
        ]:
            d = est[(est.exposure == b) & (est.estimate == kind)].set_index("share_of")
            d = d.loc[list(GROUPS)]
            ax.barh(ypos + dy, d.att * 100, color=cols, alpha=alpha, height=0.36, zorder=2,
                    label=label)  # fmt: skip
            ax.errorbar(d.att * 100, ypos + dy, xerr=1.96 * d.se * 100, fmt="none",
                        ecolor=INK2, lw=1, zorder=3)  # fmt: skip
        ax.axvline(0, color=AXIS, lw=1, zorder=1)
        _style(ax, grid="x")
        ax.set_title(f"Paid for {b}", loc="left", fontsize=10, color=INK)
        ax.set_xlabel("Change in share (pp)", color=INK2)
    axes[0].set_yticks(np.arange(len(GROUPS))[::-1], [f"{g} share" for g in GROUPS], fontsize=9)
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h[:2], lab[:2], loc="lower left", bbox_to_anchor=(0.12, 0.09),
               ncol=2, frameon=False, fontsize=8.5)  # fmt: skip
    fig.suptitle(
        "Where the paid brand's share comes from: change in each brand's share of GLP-1 "
        "claims, event years 0–3",
        x=0.01,
        ha="left",
        fontsize=11,
        color=INK,
    )
    fig.tight_layout(rect=(0, 0.17, 1, 0.93))
    _save(
        fig,
        "p15_share_sources",
        "Callaway & Sant'Anna (panel, doubly robust, not-yet-paid controls); physicians with GLP-1 "
        "claims in the base year and the outcome year. Dark bars sum to zero across brands; pale "
        "bars also adjust for the outcome brand's own base-year share (removes mean reversion "
        "when paid and unpaid physicians start from different portfolios). 95% CIs clustered by "
        "practice.\nSource: CMS Open Payments, Medicare Part D Prescribers. Associations, not "
        "proof of causation.",
    )


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "all"
    if cmd == "all":
        run_all()
    elif cmd == "brand":
        for b in argv[1:]:
            run_brand(b)
    elif cmd == "report":
        report()
    else:
        raise SystemExit(f"unknown command {cmd}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
