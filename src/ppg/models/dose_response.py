"""Dose-response and payment type (P16, H4 and H2 as far as estimable; DEV-7).

    python -m ppg.models.dose_response all      # three brands (progress bar)
    python -m ppg.models.dose_response report   # tables, chart 2, payment-type chart, spline chart

Each group of paid physicians (a dollar bin, a contact count, a payment type) is estimated as its
own treated group with the panel-form CS-DR (D27) against the same not-yet-paid controls, plus
its matched (CEM) counterpart (D28). Higher bins are more selected (prereg §1 H4): the gradient
is described, not read as a causal dose-response.

Groups (DEV-7):
    dose_g      brand-B promotional $ in the first exposure year g (primary H4 bins)
    dose_03     cumulative brand-B promotional $ over event years 0-3, cohorts <= 2021 (partly an
                outcome: later payments respond to prescribing)
    contacts_g  number of promotional contacts for B in year g (exploratory)
    type_01     natures received over event years 0-1 (speaker/consulting fee > other > meals)
Bins with fewer than 100 treated physicians are merged into the bin below.
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from ppg import config
from ppg.models.cs_panel import design, fit
from ppg.models.data import LAST_YEAR, PRIMARY_BRANDS, frame
from ppg.models.event_study import QA, _p
from ppg.models.matched import Wide, estimate, load

DOLLAR_CUTS = [0, 100, 1_000, 10_000, np.inf]
CONTACT_CUTS = [1, 2, 4, np.inf]  # 1, 2-3, >= 4
TYPES = ("Meals only", "Travel, education or other (no fee)", "Speaker or consulting fee")
MIN_BIN = 100
LAST_FULL_COHORT = LAST_YEAR - 3  # cohorts with event years 0-3 all observed


def _money(x: float) -> str:
    return f"${x / 1000:g}k" if x >= 1000 else f"${x:g}"


def _label(lo: float, hi: float, unit: str) -> str:
    if unit == "$":
        if lo == 0:
            return f"< {_money(hi)}"
        return f"≥ {_money(lo)}" if np.isinf(hi) else f"{_money(lo)}–{_money(hi)[1:]}"
    if np.isinf(hi):
        return f"≥ {lo:g} contacts"
    return f"{lo:g} contact" if hi - lo == 1 else f"{lo:g}–{hi - 1:g} contacts"


def bins(x: pd.Series, cuts: list[float], unit: str) -> dict[str, pd.Series]:
    """Bins [cut_k, cut_k+1); from the top down, a bin with < MIN_BIN members merges into the
    bin below. Returns {label: membership mask}."""
    edges = list(zip(cuts[:-1], cuts[1:], strict=True))
    k = len(edges) - 1
    while k > 0:
        lo, hi = edges[k]
        if ((x >= lo) & (x < hi)).sum() < MIN_BIN:
            edges[k - 1] = (edges[k - 1][0], hi)
            del edges[k]
        k -= 1
    return {_label(lo, hi, unit): (x >= lo) & (x < hi) for lo, hi in edges}


def unit_measures(df: pd.DataFrame, w: Wide) -> pd.DataFrame:
    """Per treated physician (w.npi order): $ and contacts in year g, cumulative $ over event
    years 0-3, and payment type over event years 0-1."""
    t = df[(df.g > 0) & (df.year >= df.g) & (df.year <= df.g + 3)].copy()
    t["e"] = t.year - t.g
    fee = t.usd_speaker.fillna(0) + t.usd_consulting.fillna(0)
    named = (t.usd_food_beverage.fillna(0) + fee + t.usd_travel.fillna(0)
             + t.usd_education.fillna(0))  # fmt: skip
    t["fee"] = fee
    t["other"] = t.usd_travel.fillna(0) + t.usd_education.fillna(0) + (t.usd - named).clip(0)
    g0 = t[t.e == 0].set_index("npi")
    e01 = t[t.e <= 1].groupby("npi")[["fee", "other"]].sum()
    m = pd.DataFrame(index=pd.Index(w.npi, name="npi"))
    m["g"] = w.g
    m["usd_g"] = g0.usd
    m["contacts_g"] = g0.promo_contacts
    m["usd_03"] = t.groupby("npi").usd.sum().where(lambda s: s.index.isin(m.index[m.g > 0]))
    m.loc[m.g > LAST_FULL_COHORT, "usd_03"] = np.nan
    m["type_01"] = np.select(
        [e01.fee.reindex(m.index) > 0, e01.other.reindex(m.index) > 0], TYPES[:0:-1], TYPES[0]
    )
    m.loc[m.g == 0, ["usd_g", "contacts_g", "type_01"]] = np.nan
    return m


def groups(m: pd.DataFrame) -> dict[str, dict[str, np.ndarray]]:
    tr = m.g > 0
    out = {
        "dose_g": bins(m.usd_g.where(tr).fillna(-1), DOLLAR_CUTS, "$"),
        "dose_03": bins(m.usd_03.fillna(-1), DOLLAR_CUTS, "$"),
        "contacts_g": bins(m.contacts_g.where(tr).fillna(-1), CONTACT_CUTS, "n"),
        "type_01": {t: (m.type_01 == t) & tr for t in TYPES},
    }
    return {f: {k: v.to_numpy() for k, v in d.items()} for f, d in out.items()}


def ra_effects(w: Wide) -> pd.Series:
    """Unit-level regression-adjusted effects: change from g - 1 minus the change predicted by
    an outcome model (registered covariates at g - 1) fitted on not-yet-paid controls, averaged
    over each treated physician's event years 0-3."""
    tot, cnt = np.zeros(len(w.npi)), np.zeros(len(w.npi))
    for g in w.cohorts():
        for e in range(4):
            t = g + e
            if t > LAST_YEAR:
                continue
            y1, y0 = w.y[:, w.col(t)], w.y[:, w.col(g - 1)]
            ok = ~np.isnan(y1) & ~np.isnan(y0) & ((w.g == g) | (w.g == 0) | (w.g > t))
            i = np.flatnonzero(ok)
            D = w.g[i] == g
            X = design(w, i, g - 1, True)
            beta = np.linalg.lstsq(X[~D], (y1 - y0)[i][~D], rcond=None)[0]
            r = (y1 - y0)[i][D] - X[D] @ beta
            np.add.at(tot, i[D], r)
            np.add.at(cnt, i[D], 1)
    keep = cnt > 0
    return pd.Series(tot[keep] / cnt[keep], index=np.flatnonzero(keep))


def spline(w: Wide, m: pd.DataFrame) -> dict:
    """Natural cubic spline (4 df) of log10 cumulative $ (years 0-3) on unit-level effects."""
    import statsmodels.formula.api as smf

    r = ra_effects(w)
    d = pd.DataFrame({"r": r, "usd": m.usd_03.to_numpy()[r.index],
                      "cl": w.cluster[r.index]}).dropna()  # fmt: skip
    d = d[d.usd > 0]
    d["x"] = np.log10(d.usd)
    f = smf.ols("r ~ cr(x, df=4, constraints='center')", d).fit(
        cov_type="cluster", cov_kwds={"groups": d.cl}
    )
    lo, hi = np.quantile(d.x, [0.01, 0.99])
    grid = pd.DataFrame({"x": np.linspace(lo, hi, 60)})
    pr = f.get_prediction(grid).summary_frame(alpha=0.05)
    return {"n": int(len(d)), "x_log10_usd": grid.x.tolist(), "fit": pr["mean"].tolist(),
            "lo": pr.mean_ci_lower.tolist(), "hi": pr.mean_ci_upper.tolist(),
            "x_quantiles": {q: float(np.quantile(d.x, q)) for q in (0.1, 0.5, 0.9)}}  # fmt: skip


def run_brand(brand: str, p=None) -> dict:
    w = load(brand)
    m = unit_measures(frame(brand), w)
    res: dict = {"brand": brand, "families": {}}
    for fam, gs in groups(m).items():
        rows = []
        for label, keep in gs.items():
            n = int(keep.sum())
            if n < config.MIN_CELL:
                continue
            o = fit(w, keep=keep)["overall_0_3"]
            mt = estimate(w, "registered", keep=keep)["overall_0_3"]
            rows.append({"group": label, "treated": n, **o, "p": _p(**o),
                         "matched_att": mt["att"], "matched_se": mt["se"]})  # fmt: skip
            if p:
                p.advance(brand, 1)
        res["families"][fam] = rows
    res["spline"] = spline(w, m)
    QA.mkdir(parents=True, exist_ok=True)
    (QA / f"dose_{brand}.json").write_text(json.dumps(res, indent=1, default=float))
    for fam, rows in res["families"].items():
        print(brand, fam, [(r["group"], r["treated"], round(r["att"] * 100, 1)) for r in rows],
              flush=True)  # fmt: skip
    return res


def run_all() -> None:
    from ppg.progress import RESUME, Progress

    with Progress("dose_response", keep_done=RESUME) as p:
        for b in PRIMARY_BRANDS:
            p.add(b, total=13, unit="groups")
        for b in PRIMARY_BRANDS:
            p.start(b)
            run_brand(b, p)
            p.finish(b)


# ------------------------------------------------------------------ report

SHORT = {
    "Travel, education or other (no fee)": "Travel, education,\nother (no fee)",
    "Speaker or consulting fee": "Speaker or\nconsulting fee",
}
FAMILY_TITLE = {
    "dose_g": "Promotional $ in the first payment year",
    "dose_03": "Cumulative promotional $, years 0–3 (cohorts ≤ 2021)",
    "contacts_g": "Promotional contacts in the first payment year",
    "type_01": "What was paid for, years 0–1",
}


def report() -> pd.DataFrame:
    res = {b: json.loads((QA / f"dose_{b}.json").read_text()) for b in PRIMARY_BRANDS}
    rows = [{"brand": b, "family": f, **r} for b, x in res.items()
            for f, rs in x["families"].items() for r in rs]  # fmt: skip
    t = pd.DataFrame(rows)
    t["lo"], t["hi"] = t.att - 1.96 * t.se, t.att + 1.96 * t.se
    t.to_csv(config.QA_DIR / "dose_response.csv", index=False)
    (config.QA_DIR / "dose_response.json").write_text(json.dumps(
        {b: {"families": x["families"], "spline": x["spline"]} for b, x in res.items()},
        indent=1, default=float))  # fmt: skip
    chart2(t)
    type_chart(t)
    spline_chart({b: x["spline"] for b, x in res.items()})
    print(t[["brand", "family", "group", "treated", "att", "lo", "hi", "matched_att"]]
          .to_string(index=False))  # fmt: skip
    return t


def _points(ax, d: pd.DataFrame, color: str) -> None:
    from ppg.viz.figures import AXIS, SURFACE

    x = np.arange(len(d))
    ax.axhline(0, color=AXIS, lw=1, zorder=1)
    ax.errorbar(x - 0.1, d.att * 100, yerr=1.96 * d.se * 100, fmt="none", ecolor=color, lw=1.4,
                zorder=2)  # fmt: skip
    ax.scatter(x - 0.1, d.att * 100, s=44, color=color, ec=SURFACE, lw=1.5, zorder=3,
               label="All not-yet-paid controls (CS-DR)")  # fmt: skip
    ax.scatter(x + 0.1, d.matched_att * 100, s=40, facecolors=SURFACE, edgecolors=color, lw=1.5,
               zorder=3, label="Matched controls (CEM)")  # fmt: skip
    names = [SHORT.get(g, g) for g in d.group]
    ax.set_xticks(x, [f"{g}\n(n = {n:,})" for g, n in zip(names, d.treated, strict=True)],
                  fontsize=8)  # fmt: skip
    ax.set_xlim(-0.6, len(d) - 0.4)


def _grid(t: pd.DataFrame, fams: list[str], name: str, title: str, note: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from ppg.viz.figures import BRAND_COLOR, INK, INK2, _save, _style

    fig, axes = plt.subplots(len(fams), 3, figsize=(12, 3.6 * len(fams)), sharey="row",
                             squeeze=False)  # fmt: skip
    for r, fam in enumerate(fams):
        for c, b in enumerate(PRIMARY_BRANDS):
            ax = axes[r, c]
            _points(ax, t[(t.brand == b) & (t.family == fam)], BRAND_COLOR[b])
            _style(ax)
            ax.set_title(b, loc="left", fontsize=9.5, color=INK2)
            if c == 0:
                ax.annotate(FAMILY_TITLE[fam], (0, 1.16), xycoords="axes fraction", fontsize=10.5,
                            color=INK, weight="bold")  # fmt: skip
            ax.yaxis.set_major_formatter(lambda v, _: f"{v:+.0f} pp")
        axes[r, 0].set_ylabel("Change in Pr(≥ 11 claims), pp", color=INK2)
    axes[0, 0].legend(loc="upper left", frameon=False, fontsize=8)
    fig.suptitle(title, x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout(rect=(0, 0.07, 1, 0.93), h_pad=3.5)
    _save(fig, name, note)


NOTE = (
    "ATT over event years 0–3 for each group of paid physicians vs not-yet-paid physicians; "
    "bars: 95% CIs clustered by practice. Higher-paid groups are more selected, so the gradient "
    "is descriptive, not a dose-response. Physicians first paid 2015–2024.\nSource: CMS Open "
    "Payments, Medicare Part D Prescribers. Associations, not proof of causation."
)


def chart2(t: pd.DataFrame) -> None:
    _grid(
        t,
        ["dose_g", "dose_03"],
        "chart2_dose_response",
        "Prescribing the paid brand after the first payment, by dollars received",
        NOTE,
    )


def type_chart(t: pd.DataFrame) -> None:
    _grid(
        t,
        ["contacts_g", "type_01"],
        "p16_contacts_and_type",
        "By number of contacts and by what was paid for",
        NOTE,
    )


def spline_chart(sp: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from ppg.viz.figures import AXIS, BRAND_COLOR, INK, INK2, _save, _style

    fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.9), sharey=True)
    for ax, b in zip(axes, PRIMARY_BRANDS, strict=True):
        s = sp[b]
        x = 10 ** np.array(s["x_log10_usd"])
        ax.axhline(0, color=AXIS, lw=1)
        ax.fill_between(x, np.array(s["lo"]) * 100, np.array(s["hi"]) * 100,
                        color=BRAND_COLOR[b], alpha=0.18, lw=0)  # fmt: skip
        ax.plot(x, np.array(s["fit"]) * 100, color=BRAND_COLOR[b], lw=2)
        ax.set_xscale("log")
        ax.xaxis.set_major_formatter(lambda v, _: _money(v))
        _style(ax)
        ax.set_title(f"{b} (n = {s['n']:,})", loc="left", fontsize=10, color=INK)
        ax.set_xlabel("Cumulative promotional $ for the brand, years 0–3", color=INK2)
        ax.yaxis.set_major_formatter(lambda v, _: f"{v:+.0f} pp")
    axes[0].set_ylabel("Regression-adjusted change, pp", color=INK2)
    fig.suptitle("Change in prescribing the paid brand by cumulative dollars (spline)", x=0.01,
                 ha="left", fontsize=11, color=INK)  # fmt: skip
    fig.tight_layout(rect=(0, 0.1, 1, 0.93))
    _save(
        fig,
        "p16_spline",
        "Unit-level change from the year before payment minus the change predicted from "
        "not-yet-paid controls (covariates at g − 1), averaged over years 0–3; natural cubic "
        "spline (4 df), 1st–99th percentile of dollars; band: 95% CI clustered by practice. "
        "Cumulative dollars partly respond to prescribing.\nSource: CMS Open Payments, Medicare "
        "Part D Prescribers. Associations, not proof of causation.",
    )


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "all"
    if cmd == "all":
        run_all()
    elif cmd == "brand":
        for b in argv[1:]:
            run_brand(b)
    elif cmd == "spline":  # recompute only the spline in saved results
        for b in PRIMARY_BRANDS:
            f = QA / f"dose_{b}.json"
            res = json.loads(f.read_text())
            w = load(b)
            res["spline"] = spline(w, unit_measures(frame(b), w))
            f.write_text(json.dumps(res, indent=1, default=float))
    elif cmd == "pretrends":  # selection by group: universal-base pre-period estimates
        for b in PRIMARY_BRANDS:
            f = QA / f"dose_{b}.json"
            res = json.loads(f.read_text())
            w = load(b)
            gs = groups(unit_measures(frame(b), w))
            for fam in ("dose_g", "contacts_g"):
                for row in res["families"][fam]:
                    r = fit(w, base="universal", keep=gs[fam][row["group"]])
                    ev = {int(x["e"]): x for x in r["event"]}
                    row["pre_e3"] = ev.get(-3, {}).get("att")
                    row["pre_e3_se"] = ev.get(-3, {}).get("se")
                    row["pretrend_p"] = (r["pretrend_wald"] or {}).get("p")
                    print(b, fam, row["group"], round(row["pre_e3"] * 100, 2), flush=True)
            f.write_text(json.dumps(res, indent=1, default=float))
    elif cmd == "report":
        report()
    else:
        raise SystemExit(f"unknown command {cmd}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
