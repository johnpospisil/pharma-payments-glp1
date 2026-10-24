"""Matched design (P14): coarsened exact matching, then CS on the matched sample (prereg §6, DEV-4).

    python -m ppg.models.matched balance   # design stage: strata and balance (pre-period data)
    python -m ppg.models.matched all       # balance + estimates, three brands x specs
    python -m ppg.models.matched report    # tables, Love plot, matched event-study chart, qa json

Specs: 'registered' matches on g-2 and g-1 (§6); 'trajectory' adds g-3 (DEV-4); 'unmatched' is
the same estimator on the same eligible physicians with one stratum (the no-matching reference).
Writes report/qa/es/matched_<spec>_<brand>.json (aggregates only; cohort cells < 11 masked).
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from ppg import config
from ppg.models.data import LAST_YEAR, PRIMARY_BRANDS, STATE_REGION, frame
from ppg.models.event_study import QA, _p, holm

SPECS = {"unmatched": 2, "registered": 2, "trajectory": 3, "volume_growth": 3}  # years required
EVENTS = tuple(range(-5, 4))
CLASS_CUTS = [0.5, 49.5, 199.5]  # GLP-1 class claims: 0, 11-49, 50-199, >= 200
GROWTH_CUTS = [-10.5, 10.5, 49.5]  # change in class claims: <= -11, +-10, 11-49, >= 50
BALANCE_TARGET = 0.1


class Wide:
    """Physician x year arrays for one brand (NaN where the physician is not in Part D)."""

    def __init__(self, df: pd.DataFrame, early: pd.DataFrame | None = None):
        self.start = int(df.year.min())  # P13 outcome window
        if early is not None:  # pre-window years: matching features only
            df = pd.concat([df, early], ignore_index=True)
        self.npi = np.sort(df.npi.unique())
        self.y0 = int(df.year.min())
        self.years = np.arange(self.y0, LAST_YEAR + 1)
        i = np.searchsorted(self.npi, df.npi.to_numpy())
        j = df.year.to_numpy() - self.y0
        shape = (len(self.npi), len(self.years))
        state = df.state.astype("category")
        self.state_codes = state.cat.categories
        region = df.region.astype("category")
        self.region_codes = region.cat.categories
        for name, col in [("y", df.y), ("cls", df.glp1_claims_all.fillna(0)),
                          ("dm", df.dm_load.fillna(0)), ("tot", df.tot_clms),
                          ("state", state.cat.codes), ("reg", region.cat.codes),
                          ("other", df.get("other_glp1")), ("urban", df.get("urban"))]:  # fmt: skip
            if col is None:
                continue
            a = np.full(shape, np.nan)
            a[i, j] = col.to_numpy(dtype=float)
            setattr(self, name, a)
        u = df.drop_duplicates("npi").set_index("npi").loc[self.npi]
        self.g = u.g.to_numpy()
        self.spec = u.specialty_group.astype("category").cat.codes.to_numpy()
        self.specialty = u.specialty_group.to_numpy()
        self.region = u.region.to_numpy()
        cl = u.cluster.astype("category")
        self.cluster = cl.cat.codes.to_numpy()
        self.cluster_labels = cl.cat.categories

    def col(self, year: int) -> int:
        return int(year - self.y0)

    def cohorts(self) -> list[int]:
        return sorted(int(c) for c in np.unique(self.g) if c > 0)


def strata(w: Wide, g: int, spec: str, keep: np.ndarray | None = None) -> pd.DataFrame:
    """CEM strata for cohort g: candidate rows (unit index, treated, stratum, CEM weight)."""
    k = SPECS[spec]
    treated = (w.g == g) if keep is None else ((w.g == g) & keep)  # keep: treated subgroup
    cand = treated | (w.g == 0) | (w.g > g)
    pre = [g - j for j in range(1, k + 1)]  # g-1, g-2 (, g-3)
    if pre[-1] < w.y0:
        return pd.DataFrame(columns=["i", "treated", "s", "w"])
    present = cand.copy()
    for t in pre:
        present &= ~np.isnan(w.y[:, w.col(t)])
    i = np.flatnonzero(present)
    c1, c2 = w.col(g - 1), w.col(g - 2)
    f = pd.DataFrame({"i": i, "treated": w.g[i] == g})
    if spec != "unmatched":
        f["spec"] = w.spec[i]
        f["state"] = w.state[i, c1]
        f["y1"], f["y2"] = w.y[i, c1], w.y[i, c2]
        f["cls"] = np.digitize(w.cls[i, c1], CLASS_CUTS)
        f["gr"] = np.digitize(w.cls[i, c1] - w.cls[i, c2], GROWTH_CUTS)
        for v in ("dm", "tot"):
            x = getattr(w, v)[i, c1]
            f[v] = np.digitize(x, np.quantile(x, [0.25, 0.5, 0.75]))
        if spec == "volume_growth":  # DEV-8: + quartile of total-claims growth g-3 -> g-1
            vg = np.log1p(w.tot[i, c1]) - np.log1p(w.tot[i, w.col(g - 3)])
            f["vg"] = np.digitize(vg, np.quantile(vg, [0.25, 0.5, 0.75]))
        if spec == "trajectory":
            c3 = w.col(g - 3)
            f["y3"] = w.y[i, c3]
            f["gr3"] = np.digitize(w.cls[i, c2] - w.cls[i, c3], GROWTH_CUTS)
    keys = [c for c in f.columns if c not in ("i", "treated")]
    f["s"] = f.groupby(keys, sort=False, dropna=False).ngroup() if keys else 0
    n = f.groupby("s").treated.agg(nt="sum", n="size")
    n["nc"] = n.n - n.nt
    f = f.join(n[["nt", "nc"]], on="s")
    f = f[(f.nt > 0) & (f.nc > 0)].copy()
    f["w"] = np.where(f.treated, 1.0, f.nt / f.nc)
    return f[["i", "treated", "s", "w"]].reset_index(drop=True)


# ------------------------------------------------------------------ balance (design stage)


GROWTH_DIAGNOSTIC = "Total claims growth"


def features(w: Wide, i: np.ndarray, g: int) -> pd.DataFrame:
    """Pre-period covariates for the balance table, measured at g-1 (and g-2, g-3)."""
    c1, c2 = w.col(g - 1), w.col(g - 2)
    c3 = w.col(g - 3) if g - 3 >= w.y0 else None
    lc = np.log1p(w.cls[i])
    out = {
        "Brand ≥ 11 claims, g − 1": w.y[i, c1],
        "Brand ≥ 11 claims, g − 2": w.y[i, c2],
        "Brand ≥ 11 claims, g − 3": w.y[i, c3] if c3 is not None else np.nan,
        "log(1 + GLP-1 class claims), g − 1": lc[:, c1],
        "Class growth g − 2 → g − 1 (log)": lc[:, c1] - lc[:, c2],
        "Class growth g − 3 → g − 1 (log)": lc[:, c1] - lc[:, c3] if c3 is not None else np.nan,
        "log(1 + diabetes claims), g − 1": np.log1p(w.dm[i, c1]),
        "log(1 + total claims), g − 1": np.log1p(w.tot[i, c1]),
        "Total claims growth g − 3 → g − 1 (log)": (
            np.log1p(w.tot[i, c1]) - np.log1p(w.tot[i, c3]) if c3 is not None else np.nan
        ),
    }
    for s in ("endocrinology", "primary_care_physician"):
        out[f"Specialty: {s.replace('_', ' ')}"] = (w.specialty[i] == s).astype(float)
    for r in ("Northeast", "Midwest", "South", "West"):
        out[f"Region: {r}"] = (w.region[i] == r).astype(float)
    return pd.DataFrame(out)


def balance(w: Wide, spec: str) -> tuple[pd.DataFrame, list[dict]]:
    """Standardised differences before matching (all eligible) and after (CEM weights)."""
    rows, stats = [], []
    for g in w.cohorts():
        k = SPECS[spec]
        cand = (w.g == g) | (w.g == 0) | (w.g > g)
        pre_ok = cand.copy()
        for t in range(g - k, g):
            pre_ok &= ~np.isnan(w.y[:, w.col(t)]) if t >= w.y0 else False
        m = strata(w, g, spec)
        n_treated = int((w.g == g).sum())
        stats.append({"g": g, "treated": n_treated,
                      "treated_eligible": int((pre_ok & (w.g == g)).sum()),
                      "treated_matched": int(m.treated.sum()),
                      "controls_matched": int((~m.treated).sum()),
                      "strata": int(m.s.nunique())})  # fmt: skip
        if m.empty:
            continue
        allx = np.flatnonzero(pre_ok)
        before = features(w, allx, g).assign(treated=w.g[allx] == g, w=1.0, stage="before")
        after = features(w, m.i.to_numpy(), g).assign(
            treated=m.treated.to_numpy(), w=m.w.to_numpy(), stage="after"
        )
        rows += [before, after]
    if not rows:
        return pd.DataFrame(), stats
    x = pd.concat(rows, ignore_index=True)
    out = []
    for v in [c for c in x.columns if c not in ("treated", "w", "stage")]:
        b = x[x.stage == "before"]
        sd = np.sqrt((b.loc[b.treated, v].var() + b.loc[~b.treated, v].var()) / 2)
        for stage, d in x.groupby("stage"):
            t, c = d[d.treated], d[~d.treated]
            if t[v].isna().all():
                continue
            mt = np.average(t[v].dropna(), weights=t.loc[t[v].notna(), "w"])
            mc = np.average(c[v].dropna(), weights=c.loc[c[v].notna(), "w"])
            out.append(
                {
                    "variable": v,
                    "stage": stage,
                    "mean_treated": mt,
                    "mean_control": mc,
                    "smd": (mt - mc) / sd if sd > 0 else 0.0,
                }
            )
    return pd.DataFrame(out), stats


# ------------------------------------------------------------------ estimation


def cell(
    w: Wide, m: pd.DataFrame, g: int, e: int, outcome: np.ndarray | None = None
) -> tuple[float, int, np.ndarray, np.ndarray]:
    """ATT(g, g+e) on the matched set m, universal base g-1, not-yet-treated controls.

    Returns (att, treated in cell, unit indices, influence function on the sum scale)."""
    t = g + e
    yy = w.y if outcome is None else outcome
    d = yy[m.i, w.col(t)] - yy[m.i, w.col(g - 1)]
    gi = w.g[m.i]
    ok = ~np.isnan(d) & (m.treated.to_numpy() | (gi == 0) | (gi > max(t, g - 1)))
    c = m.assign(d=d)[ok]
    n = c.groupby("s").treated.agg(nt="sum", n="size")
    n["nc"] = n.n - n.nt
    c = c.join(n[["nt", "nc"]], on="s")
    c = c[(c.nt > 0) & (c.nc > 0)]
    mc = c[~c.treated].groupby("s").d.mean()
    c = c.join(mc.rename("mc"), on="s")
    tr = c.treated.to_numpy()
    nt = int(tr.sum())
    if nt == 0:
        return np.nan, 0, np.array([], int), np.array([])
    att = float((c.d[tr] - c.mc[tr]).mean())
    inf = np.where(tr, (c.d - c.mc - att) / nt, -(c.nt / nt) * (c.d - c.mc) / c.nc)
    return att, nt, c.i.to_numpy(), inf


def estimate(
    w: Wide, spec: str, outcome: np.ndarray | None = None, keep: np.ndarray | None = None
) -> dict:
    """Event-time and overall (e = 0..3) ATTs with practice-clustered influence-function SEs."""
    nunit = len(w.npi)
    cells, ife, ng = [], {}, {}
    for g in w.cohorts():
        m = strata(w, g, spec, keep)
        if m.empty:
            continue
        ng[g] = int(m.treated.sum())
        for e in EVENTS:
            t = g + e
            if e == -1 or t < w.start or t > LAST_YEAR:
                continue
            att, nt, idx, inf = cell(w, m, g, e, outcome)
            if nt == 0:
                continue
            v = np.zeros(nunit)
            np.add.at(v, idx, inf)
            cells.append({"g": g, "e": e, "t": t, "att": att, "treated": nt,
                          "se": _se(w, v)})  # fmt: skip
            ife.setdefault(e, []).append((g, att, v))
    events, cols = [], []
    for e in sorted(ife):
        tot = sum(ng[g] for g, *_ in ife[e])
        att = sum(ng[g] / tot * a for g, a, _ in ife[e])
        v = sum(ng[g] / tot * x for g, _, x in ife[e])
        events.append({"e": e, "att": att, "se": _se(w, v), "cohorts": len(ife[e])})
        cols.append(v)
    ev = pd.DataFrame(events)
    V = _vcov(w, np.column_stack(cols))
    es = ev.e.to_numpy()

    def lin(sel: np.ndarray) -> dict:
        lv = sel / sel.sum()
        return {"att": float(lv @ ev.att), "se": float(np.sqrt(lv @ V @ lv))}

    # matched event times are zero by construction, so the pre-test starts below them
    pre = (es < -SPECS[spec]) if spec != "unmatched" else (es <= -2)
    pre &= np.diag(V) > 1e-14  # drop mechanically zero cells (e.g. pre-launch shares)
    wald = None
    if pre.any():
        b, Vp = ev.att[pre].to_numpy(), V[np.ix_(pre, pre)]
        stat = float(b @ np.linalg.solve(Vp, b))
        from scipy.stats import chi2

        wald = {"stat": stat, "df": int(pre.sum()), "p": float(chi2.sf(stat, pre.sum())),
                "events": [int(x) for x in es[pre]]}  # fmt: skip
    return {
        "spec": spec,
        "cohort_matched_treated": {
            str(g): (n if n >= config.MIN_CELL else "<11") for g, n in ng.items()
        },  # fmt: skip
        "att_gt": [c for c in cells if c["treated"] >= config.MIN_CELL],
        "event": ev.to_dict("records"),
        "overall_0_3": lin(((es >= 0) & (es <= 3)).astype(float)),
        "overall_1_3": lin(((es >= 1) & (es <= 3)).astype(float)),
        "pretrend_wald": wald,
    }


def cluster_if(w: Wide, v: np.ndarray) -> pd.Series:
    """Influence function summed by practice label, for combining estimates across fits (P19)."""
    s = np.bincount(w.cluster, weights=v, minlength=len(w.cluster_labels))
    return pd.Series(s, index=w.cluster_labels)


def _se(w: Wide, v: np.ndarray) -> float:
    s = np.bincount(w.cluster, weights=v)
    return float(np.sqrt(s @ s))


def _vcov(w: Wide, m: np.ndarray) -> np.ndarray:
    s = np.zeros((w.cluster.max() + 1, m.shape[1]))
    np.add.at(s, w.cluster, m)
    return s.T @ s


# ------------------------------------------------------------------ run


def load(brand: str, **frame_kw) -> Wide:
    """The P13 frame plus physician-level rows for 2013 .. window start - 1 (npi_year), where the
    brand is pre-launch (y = 0), so cohorts near launch can be matched on g - 2 and g - 3 (and,
    in P15, Mounjaro's launch cohort gets base-year covariates for 2021)."""
    return with_early(frame(brand, **frame_kw))


def with_early(df: pd.DataFrame) -> Wide:
    """Wide arrays for a frame plus npi_year rows for 2013 .. its first year (see `load`)."""
    import duckdb

    early = duckdb.sql(
        f"""SELECT npi, year, 0 AS y, clms_glp1 AS glp1_claims_all, dm_load, tot_clms, state,
                   (coalesce(clms_glp1, 0) > 0)::INT AS other_glp1,
                   (coalesce(ruca, 99) < 4)::INT AS urban
            FROM '{config.PARQUET_DIR}/panel/npi_year.parquet'
            WHERE year >= 2013 AND year < {int(df.year.min())}"""
    ).df()
    early = early[early.npi.isin(df.npi.unique())]
    early["region"] = early.state.map(STATE_REGION)
    return Wide(df, early)


def run_brand(brand: str, w: Wide | None = None, specs=tuple(SPECS)) -> None:
    w = w or load(brand)
    QA.mkdir(parents=True, exist_ok=True)
    for spec in specs:
        bal, stats = balance(w, spec) if spec != "unmatched" else (pd.DataFrame(), [])
        res = estimate(w, spec) | {"brand": brand, "match": _mask(stats),
                                   "balance": bal.to_dict("records")}  # fmt: skip
        (QA / f"matched_{spec}_{brand}.json").write_text(json.dumps(res, indent=1, default=float))
        o = res["overall_0_3"]
        print(f"{brand} {spec}: ATT(0-3) = {o['att']:.4f} (se {o['se']:.4f})", flush=True)


def _mask(stats: list[dict]) -> list[dict]:
    return [{k: (v if k == "g" or v >= config.MIN_CELL or v == 0 else "<11")
             for k, v in s.items()} for s in stats]  # fmt: skip


def balance_only() -> None:
    """Design stage: print match rates and the worst |SMD| per spec, no outcomes after g - 1."""
    for b in PRIMARY_BRANDS:
        w = load(b)
        for spec in ("registered", "trajectory"):
            bal, stats = balance(w, spec)
            s = pd.DataFrame(stats)
            a = bal[bal.stage == "after"]
            worst = a.loc[a.smd.abs().idxmax(), "variable"]
            n, m = s.treated.sum(), s.treated_matched.sum()
            print(
                f"{b} {spec}: matched {m:,} of {n:,} treated ({m / n:.1%}); "
                f"max |SMD| after {a.smd.abs().max():.3f} ({worst})"
            )


def run_all() -> None:
    from ppg.progress import Progress

    with Progress("matched") as p:
        for b in PRIMARY_BRANDS:
            p.add(b, total=len(SPECS) + 1, unit="steps")
        for b in PRIMARY_BRANDS:
            p.start(b)
            w = load(b)
            p.advance(b, 1)
            for spec in SPECS:
                run_brand(b, w, specs=(spec,))
                p.advance(b, 1)
            p.finish(b)


# ------------------------------------------------------------------ report


def report() -> dict:
    load_ = lambda tag: {b: json.loads((QA / f"{tag}_{b}.json").read_text())  # noqa: E731
                         for b in PRIMARY_BRANDS}  # fmt: skip
    prim, rc, nocov, honest = (
        load_("panel"),
        load_("primary"),
        load_("panel_nocov"),
        load_("honest_panel"),
    )
    res = {s: load_(f"matched_{s}") for s in SPECS}
    rows, out = [], {"brands": {}}
    for b in PRIMARY_BRANDS:
        po = prim[b]["overall_0_3"]
        sd0 = next(r for r in honest[b]["smoothness"] if r["M"] == 0)
        entry = {
            "primary": po | {"treated": prim[b]["frame"]["treated_physicians"],
                             "pretrend_wald": prim[b]["pretrend_wald"],
                             "honest_breakdown_mbar": honest[b]["breakdown_mbar"],
                             "smoothness_m0": {"lb": sd0["lb"], "ub": sd0["ub"]}},
            "p13_as_reported": rc[b]["overall_0_3"],
            "no_covariates": nocov[b]["overall_0_3"],
        }  # fmt: skip
        for label, o, n in [
            ("CS primary, panel form (DEV-5)", po, prim[b]["frame"]["treated_physicians"]),
            (
                "CS as reported in P13 (cross-section form)",
                rc[b]["overall_0_3"],
                rc[b]["frame"]["treated_physicians"],
            ),
            ("CS no covariates (panel form)", nocov[b]["overall_0_3"], None),
        ]:
            rows.append({"brand": b, "estimate": label, **_ci(o), "treated": n})
        for s in SPECS:
            r = res[s][b]
            o = r["overall_0_3"]
            st = pd.DataFrame(r["match"])
            treated = int(pd.to_numeric(st.treated, errors="coerce").sum()) if len(st) else None
            matched = sum(n for n in r["cohort_matched_treated"].values() if n != "<11")
            e = {**o, "p": _p(o["att"], o["se"]), "matched_treated": matched,
                 "pretrend_wald": r["pretrend_wald"]}  # fmt: skip
            if treated:
                e |= {"treated": treated, "share_matched": matched / treated}
            if s != "unmatched":
                a = pd.DataFrame(r["balance"])
                a = a[a.stage == "after"]
                # total-claims growth is a diagnostic (DEV-8), matched on only by volume_growth
                diag = a.variable.str.startswith(GROWTH_DIAGNOSTIC)
                own = a if s == "volume_growth" else a[~diag]
                e["max_abs_smd_after"] = float(own.smd.abs().max())
                e["growth_smd_after"] = float(a.loc[diag, "smd"].abs().max())
                e["ratio_to_primary"] = o["att"] / po["att"]
                e["ratio_to_p13"] = o["att"] / rc[b]["overall_0_3"]["att"]
                e["half_primary_and_significant"] = bool(
                    o["att"] >= 0.5 * po["att"] and o["att"] - 1.96 * o["se"] > 0
                )
            entry[s] = e
            rows.append({"brand": b, "estimate": f"matched: {s}", **_ci(o), "treated": matched})
        out["brands"][b] = entry
    out["holm_primary"] = holm({b: out["brands"][b]["primary"]["p"] for b in PRIMARY_BRANDS})
    out["holm_registered"] = holm({b: out["brands"][b]["registered"]["p"] for b in PRIMARY_BRANDS})
    est = pd.DataFrame(rows)
    est.to_csv(config.QA_DIR / "matched_estimates.csv", index=False)
    bal = pd.concat([pd.DataFrame(res[s][b]["balance"]).assign(brand=b, spec=s)
                     for s in ("registered", "trajectory") for b in PRIMARY_BRANDS])  # fmt: skip
    bal.to_csv(config.QA_DIR / "matched_balance.csv", index=False)
    ev = pd.concat([pd.DataFrame(res[s][b]["event"]).assign(brand=b, spec=s)
                    for s in SPECS for b in PRIMARY_BRANDS])  # fmt: skip
    uni = pd.concat([pd.DataFrame(load_("panel_universal")[b]["event"]).assign(brand=b,
                     spec="primary") for b in PRIMARY_BRANDS])  # fmt: skip
    ev = pd.concat([ev, uni[["e", "att", "se", "brand", "spec", "cohorts"]]])
    ev.to_csv(config.QA_DIR / "matched_event_time.csv", index=False)
    (config.QA_DIR / "matched.json").write_text(json.dumps(out, indent=1, default=float))
    love_plot(bal)
    event_chart(ev)
    event_chart(
        ev,
        ("primary", "registered"),
        "hero_v2_event_study",
        "Prescribing the paid brand before and after the first payment (event study, v2)",
    )
    print(est.to_string(index=False))
    return out


def _ci(o: dict) -> dict:
    return {"att": o["att"], "se": o["se"], "lo": o["att"] - 1.96 * o["se"],
            "hi": o["att"] + 1.96 * o["se"]}  # fmt: skip


def love_plot(bal: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from ppg.viz.figures import AXIS, CATEGORICAL, GRID, INK, INK2, MUTED, SURFACE, _save, _style

    vars_ = list(dict.fromkeys(bal.variable))
    fig, axes = plt.subplots(1, 3, figsize=(12, 5.6), sharey=True)
    ypos = {v: i for i, v in enumerate(reversed(vars_))}
    marks = [("registered", "before", "Before matching", MUTED, "o", "none", 0.0),
             ("registered", "after", "Matched (registered: g − 2, g − 1)", CATEGORICAL[0], "o",
              None, 0.18),
             ("trajectory", "after", "Matched (trajectory: g − 3 … g − 1)", CATEGORICAL[1], "D",
              None, -0.18)]  # fmt: skip
    for ax, b in zip(axes, PRIMARY_BRANDS, strict=True):
        ax.axvspan(-BALANCE_TARGET, BALANCE_TARGET, color=GRID, alpha=0.6, lw=0, zorder=0)
        ax.axvline(0, color=AXIS, lw=1, zorder=1)
        for spec, stage, label, col, mk, face, dy in marks:
            d = bal[(bal.brand == b) & (bal.spec == spec) & (bal.stage == stage)]
            ax.scatter(d.smd, d.variable.map(ypos) + dy, s=36, marker=mk, label=label, zorder=3,
                       facecolors=face or col, edgecolors=col if face else SURFACE,
                       linewidths=1.5)  # fmt: skip
        _style(ax, grid="x")
        ax.set_xlim(-0.3, 1.0)
        ax.set_xticks([-0.25, 0, 0.25, 0.5, 0.75, 1.0])
        ax.set_title(b, loc="left", fontsize=10, color=INK)
        ax.set_xlabel("Standardised difference (paid − not yet paid)", color=INK2, fontsize=9)
    axes[0].set_yticks(list(ypos.values()), list(ypos.keys()), fontsize=8.5)
    axes[0].legend(loc="upper left", bbox_to_anchor=(0, -0.13), ncol=3, frameon=False,
                   fontsize=8.5)  # fmt: skip
    fig.suptitle("Covariate balance before and after coarsened exact matching", x=0.01, ha="left",
                 fontsize=11, color=INK)  # fmt: skip
    fig.subplots_adjust(left=0.2, right=0.98, top=0.88, bottom=0.25, wspace=0.08)
    _save(fig, "p14_love_plot",
          "Physicians first paid for the brand vs physicians not yet paid, pooled over cohorts; "
          "shaded band: |SMD| < 0.1. Measured in the years before the first payment (g − 1 etc.)."
          "\nSource: CMS Open Payments, Medicare Part D Prescribers.")  # fmt: skip


NOTE_EVENT = (
    "Relative to the year before the first payment (g − 1); bars: 95% CIs clustered by "
    "practice. Matched estimates: CEM on pre-period brand status, GLP-1 class level and "
    "growth,\ndiabetes load, volume, specialty × state; not-yet-paid controls. Physicians. "
    "Source: CMS Open Payments, Medicare Part D Prescribers. Associations, not proof of "
    "causation."
)


def event_chart(
    ev: pd.DataFrame,
    specs: tuple[str, ...] = ("primary", "registered", "trajectory"),
    name: str = "p14_matched_event_study",
    title: str = "Primary and matched event studies",
) -> None:
    import matplotlib
    import matplotlib.ticker

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from ppg.viz.figures import AXIS, CATEGORICAL, GRID, INK, INK2, MUTED, SURFACE, _save, _style

    lines = [("primary", "All paid vs not-yet-paid (CS, covariates at g − 1)", MUTED, "o"),
             ("registered", "Matched on pre-payment trajectory (CEM)", CATEGORICAL[0], "o"),
             ("trajectory", "Matched on three pre-payment years", CATEGORICAL[1], "D")]  # fmt: skip
    lines = [x for x in lines if x[0] in specs]
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 4.4), sharey=True)
    for ax, b in zip(axes, PRIMARY_BRANDS, strict=True):
        ax.axhline(0, color=AXIS, lw=1, zorder=1)
        ax.axvline(-0.5, color=GRID, lw=1, ls="--", zorder=1)
        for k, (spec, label, col, mk) in enumerate(lines):
            d = ev[(ev.brand == b) & (ev.spec == spec) & ev.e.between(-5, 3)].sort_values("e")
            ref = pd.DataFrame({"e": [-1], "att": [0.0], "se": [0.0]})
            d = pd.concat([d, ref]).sort_values("e")
            x = d.e + (k - (len(lines) - 1) / 2) * 0.12
            ax.errorbar(x, d.att, yerr=1.96 * d.se, fmt="none", ecolor=col, lw=1.2, zorder=2)
            ax.plot(x, d.att, color=col, lw=2, zorder=3, label=label)
            ax.scatter(x, d.att, s=30, marker=mk, color=col, ec=SURFACE, lw=1.5, zorder=4)
        _style(ax)
        ax.set_title(b, loc="left", fontsize=10, color=INK)
        ax.set_xticks(range(-5, 4))
        ax.set_xlabel("Years since first promotional payment for the brand", color=INK2)
        ax.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(0.02))
        ax.yaxis.set_major_formatter(lambda v, _: f"{v * 100:+.0f} pp")
    axes[0].set_ylabel("Change in probability of ≥ 11 claims of the brand")
    axes[1].legend(loc="lower right", frameon=False, fontsize=8)
    fig.suptitle(title, x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout(rect=(0, 0.09, 1, 0.93))
    _save(fig, name, NOTE_EVENT)


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "all"
    if cmd == "balance":
        balance_only()
    elif cmd == "all":
        run_all()
    elif cmd == "brand":
        for b in argv[1:] or PRIMARY_BRANDS:
            run_brand(b)
    elif cmd == "report":
        report()
    else:
        raise SystemExit(f"unknown command {cmd}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
