"""Falsification tests (P17; PREREGISTRATION.md §9), each with its matched counterpart (D28).

    python -m ppg.models.falsification all      # every test (progress bar)
    python -m ppg.models.falsification report   # table with pass/fail, forest plot, event studies

Tests:
    other_glp1_pretrend  pre-trend test on a second outcome, 1{any other GLP-1 observed} (§9.1)
    statin               negative-control outcome: 1{statin claims >= 11}, and statin claims on
                         the ratio (PPML) scale, on GLP-1 brand exposure (§9.2)
    nc_exposure          first anticoagulant (primary, D20) or inhaled-respiratory (secondary)
                         promotional payment on 1{any GLP-1 claims >= 11}, against the same
                         contrast for the first GLP-1 payment (§9.3)
    placebo_timing       first payment moved 1 and 2 years earlier, pre-payment data only (§9.4)
    placebo_brand        Trulicity exposure on the Ozempic outcome and the reverse (§9.5)

Fail rule (§9): the 95% CI excludes 0 *and* the estimate is at least half the comparator in the
comparator's direction. Ratio-scale (PPML) estimates also get the equivalence check against the
10% SESOI (90% CI within +-10%, §8).
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from ppg import config
from ppg.models.cs_panel import fit
from ppg.models.data import LAST_YEAR, PRIMARY_BRANDS, first_promo_year, frame, physician_frame
from ppg.models.event_study import QA, _p
from ppg.models.matched import Wide, _se, estimate, load, strata
from ppg.models.switching import _cell, claims

PLACEBO_BRAND = {"Trulicity": "Ozempic", "Ozempic": "Trulicity"}
NC_CLASSES = {
    "anticoagulant": "Anticoagulant (primary)",
    "inhaled_respiratory": "Inhaled respiratory (secondary)",
    "glp1": "GLP-1 (comparator)",
}
SESOI_RATIO = 0.10


def array(w: Wide, df: pd.DataFrame, values: pd.Series) -> np.ndarray:
    """Physician x year array aligned to w (NaN where the physician-year is not in df)."""
    a = np.full((len(w.npi), len(w.years)), np.nan)
    a[np.searchsorted(w.npi, df.npi.to_numpy()), df.year.to_numpy() - w.y0] = values.to_numpy()
    return a


# ------------------------------------------------------------------ ratio (PPML) scale


def ppml_fit(w: Wide, y: np.ndarray, matched: bool = False) -> dict:
    """Multiplicative parallel trends in means, the PPML two-period estimand:
    log ratio(g,t) = log m_T1 - log m_T0 - log m_C1 + log m_C0 (CEM-weighted controls when
    matched). Cohort-size aggregation over e = 0..3 of the log ratios; returns the proportional
    effect exp(tau) - 1 with a delta-method CI."""
    nunit = len(w.npi)
    sizes = pd.Series(w.g[w.g > 0]).value_counts()
    by_e: dict[int, list] = {}
    for g in w.cohorts():
        m = strata(w, g, "registered") if matched else None
        if matched and m.empty:
            continue
        for e in range(4):
            t = g + e
            if t > LAST_YEAR or g - 1 < w.start:
                continue
            i, tr, wt = _cell(w, y, g, t, m)
            if tr.sum() < 1 or (~tr).sum() < 1:
                continue
            y1, y0 = y[i, w.col(t)], y[i, w.col(g - 1)]
            mean = {
                f"{k}{p}": np.average(v[ix], weights=wt[ix])
                for k, ix in (("T", tr), ("C", ~tr))
                for p, v in (("1", y1), ("0", y0))
            }
            if min(mean.values()) <= 0:
                continue
            tau = np.log(mean["T1"]) - np.log(mean["T0"]) - np.log(mean["C1"]) + np.log(mean["C0"])
            wT, wC = wt[tr].sum(), wt[~tr].sum()
            inf = np.where(
                tr,
                ((y1 - mean["T1"]) / mean["T1"] - (y0 - mean["T0"]) / mean["T0"]) / wT,
                -((y1 - mean["C1"]) / mean["C1"] - (y0 - mean["C0"]) / mean["C0"]) * wt / wC,
            )
            v = np.zeros(nunit)
            np.add.at(v, i, inf)
            by_e.setdefault(e, []).append((g, tau, v))
    taus, ifs = [], []
    for e in sorted(by_e):
        tot = sum(sizes[g] for g, *_ in by_e[e])
        taus.append(sum(sizes[g] / tot * a for g, a, _ in by_e[e]))
        ifs.append(sum(sizes[g] / tot * x for g, _, x in by_e[e]))
    tau, se = float(np.mean(taus)), _se(w, sum(ifs) / len(ifs))
    return {
        "tau_log": tau,
        "se_log": se,
        "att": float(np.expm1(tau)),
        "lo": float(np.expm1(tau - 1.96 * se)),
        "hi": float(np.expm1(tau + 1.96 * se)),
        "lo90": float(np.expm1(tau - 1.645 * se)),
        "hi90": float(np.expm1(tau + 1.645 * se)),
    }


# ------------------------------------------------------------------ helpers


def _pair(w: Wide, outcome: np.ndarray | None = None, **kw) -> dict:
    """Panel-form CS-DR and its matched counterpart, overall over e = 0..3, with events."""
    r = fit(w, outcome=outcome, **kw)
    u = fit(w, outcome=outcome, base="universal", **kw)
    m = estimate(w, "registered", outcome=outcome)
    o, mo = r["overall_0_3"], m["overall_0_3"]
    return {
        "att": o["att"],
        "se": o["se"],
        "p": _p(**o),
        "matched_att": mo["att"],
        "matched_se": mo["se"],
        "matched_p": _p(**mo),
        "pretrend_wald": r["pretrend_wald"],
        "matched_pretrend_wald": m["pretrend_wald"],
        "event": u["event"],
        "matched_event": m["event"],
    }


def _verdict(att: float, se: float, comp: float) -> str:
    lo, hi = att - 1.96 * se, att + 1.96 * se
    excl = lo > 0 or hi < 0
    big = np.sign(att) == np.sign(comp) and abs(att) >= 0.5 * abs(comp)
    return "FAIL" if excl and big else "pass"


def _ratio_verdict(r: dict, comp: float) -> dict:
    excl = r["lo"] > 0 or r["hi"] < 0
    big = np.sign(r["att"]) == np.sign(comp) and abs(r["att"]) >= 0.5 * abs(comp)
    equiv = -SESOI_RATIO < r["lo90"] and r["hi90"] < SESOI_RATIO
    return {"verdict": "FAIL" if excl and big else "pass", "equivalent_to_null": bool(equiv)}


# ------------------------------------------------------------------ tests by brand


def brand_tests(brand: str, prim: dict, p=None) -> dict:
    w = load(brand)
    df = frame(brand)
    out: dict = {"brand": brand, "primary_att": prim[brand]}
    statin = df.clms_statin.fillna(0)
    sb = array(w, df, (statin >= 11).astype(float))
    sc = array(w, df, statin)
    out["statin_binary"] = _pair(w, sb)
    out["statin_binary"]["verdict"] = _verdict(
        out["statin_binary"]["att"], out["statin_binary"]["se"], prim[brand]
    )
    out["statin_binary"]["matched_verdict"] = _verdict(
        out["statin_binary"]["matched_att"], out["statin_binary"]["matched_se"], prim[brand]
    )
    if p:
        p.advance(brand, 1)
    bc = claims(w)[brand]
    comp = {"unmatched": ppml_fit(w, bc), "matched": ppml_fit(w, bc, matched=True)}
    out["brand_claims_ratio"] = comp
    out["statin_ratio"] = {
        k: (r := ppml_fit(w, sc, matched=k == "matched")) | _ratio_verdict(r, comp[k]["att"])
        for k in comp
    }
    if p:
        p.advance(brand, 1)
    out["other_glp1_pretrend"] = _pair(w, w.other)
    # diagnostic: does the physician's whole Part D volume grow after a GLP-1 payment?
    out["total_claims_ratio"] = {
        k: ppml_fit(w, w.tot, matched=k == "matched") for k in ("unmatched", "matched")
    }
    tr = np.flatnonzero(w.g > 0)
    out["statin_binary_base_rate"] = float(np.nanmean(sb[tr, (w.g[tr] - 1 - w.y0).astype(int)]))
    if p:
        p.advance(brand, 1)
    out["placebo_timing"] = {}
    for k in (1, 2):
        d = df[(df.g == 0) | (df.year < df.g)].copy()
        d["g"] = np.where(d.g > 0, d.g - k, 0)
        wk = Wide(d)
        r = _pair(wk)
        r["verdict"] = _verdict(r["att"], r["se"], prim[brand])
        r["matched_verdict"] = _verdict(r["matched_att"], r["matched_se"], prim[brand])
        out["placebo_timing"][f"shift_{k}"] = r
        if p:
            p.advance(brand, 1)
    if brand in PLACEBO_BRAND:
        other = PLACEBO_BRAND[brand]
        c = claims(w)[other]
        yo = np.where(np.isnan(c), np.nan, (c > 0).astype(float))
        r = _pair(w, yo)
        r["outcome"] = other
        r["verdict"] = _verdict(r["att"], r["se"], prim[brand])
        r["matched_verdict"] = _verdict(r["matched_att"], r["matched_se"], prim[brand])
        out["placebo_brand"] = r
    if p:
        p.advance(brand, 1)
    return out


# ------------------------------------------------------------------ negative-control exposure


def nc_exposure(p=None) -> dict:
    """First promotional payment for a drug class (2015-2024 cohorts; 2013-14 already treated)
    on 1{any GLP-1 claims >= 11}. Registered covariates except 'any other GLP-1', which is the
    outcome's own base value here."""
    base = physician_frame()
    out = {}
    for cls, label in NC_CLASSES.items():
        g = base.npi.map(first_promo_year(cls)).fillna(0).astype(int)
        d = base[~((g > 0) & (g < 2015))].copy()
        g = g[d.index]
        d["g"] = np.where(g <= LAST_YEAR, g, 0)
        d["y"] = (d.glp1_claims_all > 0).astype(float)
        d["other_glp1"] = 0.0
        w = Wide(d)
        r = _pair(w)
        r |= {
            "label": label,
            "treated": int((w.g > 0).sum()),
            "controls_never": int((w.g == 0).sum()),
        }
        out[cls] = r
        print(
            f"nc_exposure {cls}: ATT {r['att']:.4f} (se {r['se']:.4f}); matched "
            f"{r['matched_att']:.4f}",
            flush=True,
        )
        if p:
            p.advance("negative-control exposure", 1)
    comp = out["glp1"]
    for cls in ("anticoagulant", "inhaled_respiratory"):
        out[cls]["verdict"] = _verdict(out[cls]["att"], out[cls]["se"], comp["att"])
        out[cls]["matched_verdict"] = _verdict(
            out[cls]["matched_att"], out[cls]["matched_se"], comp["matched_att"]
        )
        out[cls]["ratio_to_glp1"] = out[cls]["att"] / comp["att"]
    return out


# ------------------------------------------------------------------ run


def run_all() -> None:
    from ppg.progress import Progress

    prim = {
        b: json.loads((QA / f"panel_{b}.json").read_text())["overall_0_3"]["att"]
        for b in PRIMARY_BRANDS
    }
    QA.mkdir(parents=True, exist_ok=True)
    with Progress("falsification") as p:
        for b in PRIMARY_BRANDS:
            p.add(b, total=6, unit="tests")
        p.add("negative-control exposure", total=3, unit="fits")
        for b in PRIMARY_BRANDS:
            p.start(b)
            r = brand_tests(b, prim, p)
            (QA / f"falsification_{b}.json").write_text(json.dumps(r, indent=1, default=float))
            p.finish(b)
        p.start("negative-control exposure")
        nc = nc_exposure(p)
        (QA / "falsification_nc_exposure.json").write_text(json.dumps(nc, indent=1, default=float))
        p.finish("negative-control exposure")


def _row(test: str, brand: str, x: dict, comparator, unit: str = "pp") -> dict:
    return {
        "test": test,
        "brand": brand,
        "unit": unit,
        "att": x["att"],
        "se": x["se"],
        "matched_att": x.get("matched_att"),
        "matched_se": x.get("matched_se"),
        "comparator": comparator,
        "verdict": x.get("verdict"),
        "matched_verdict": x.get("matched_verdict"),
        "pretrend_p": (x.get("pretrend_wald") or {}).get("p"),
        "matched_pretrend_p": (x.get("matched_pretrend_wald") or {}).get("p"),
    }


def table() -> pd.DataFrame:
    rows = []
    for b in PRIMARY_BRANDS:
        r = json.loads((QA / f"falsification_{b}.json").read_text())
        comp = r["primary_att"]
        rows.append(
            _row("Negative-control outcome: statins ≥ 11 claims", b, r["statin_binary"], comp)
        )
        for k in ("shift_1", "shift_2"):
            rows.append(
                _row(f"Placebo timing: {k[-1]} year(s) early", b, r["placebo_timing"][k], comp)
            )
        if "placebo_brand" in r:
            rows.append(
                _row(
                    f"Placebo brand: {b} payment → {r['placebo_brand']['outcome']}",
                    b,
                    r["placebo_brand"],
                    comp,
                )
            )
        o = r["other_glp1_pretrend"]
        x = _row("Pre-trend, second outcome (any other GLP-1)", b, o, None, unit="p")
        x["verdict"] = "pass" if o["pretrend_wald"]["p"] >= 0.05 else "FAIL"
        mp = (o.get("matched_pretrend_wald") or {}).get("p")
        x["matched_verdict"] = None if mp is None else ("pass" if mp >= 0.05 else "FAIL")
        rows.append(x)
        for k in ("unmatched", "matched"):
            s, c = r["statin_ratio"][k], r["brand_claims_ratio"][k]
            rows.append(
                {
                    "test": f"Negative-control outcome: statin claims, ratio ({k})",
                    "brand": b,
                    "unit": "ratio",
                    "att": s["att"],
                    "se": s["se_log"],
                    "comparator": c["att"],
                    "verdict": s["verdict"],
                    "lo": s["lo"],
                    "hi": s["hi"],
                    "equivalent_to_null": s["equivalent_to_null"],
                }
            )
        for k in ("unmatched", "matched"):
            v = r["total_claims_ratio"][k]
            rows.append(
                {
                    "test": f"Diagnostic: total Part D claims, ratio ({k})",
                    "brand": b,
                    "unit": "ratio",
                    "att": v["att"],
                    "se": v["se_log"],
                    "lo": v["lo"],
                    "hi": v["hi"],
                }
            )
    nc = json.loads((QA / "falsification_nc_exposure.json").read_text())
    for cls in ("anticoagulant", "inhaled_respiratory"):
        rows.append(
            _row(
                f"Negative-control exposure: {nc[cls]['label']}",
                "any GLP-1",
                nc[cls],
                nc["glp1"]["att"],
            )
        )
    t = pd.DataFrame(rows)
    pp = t.unit != "ratio"
    t.loc[pp, "lo"] = t.att - 1.96 * t.se
    t.loc[pp, "hi"] = t.att + 1.96 * t.se
    return t


def report() -> pd.DataFrame:
    t = table()
    t.to_csv(config.QA_DIR / "falsification.csv", index=False)
    (config.QA_DIR / "falsification.json").write_text(
        json.dumps(t.to_dict("records"), indent=1, default=float)
    )
    forest(t)
    event_charts()
    print(
        t[
            [
                "test",
                "brand",
                "att",
                "lo",
                "hi",
                "matched_att",
                "comparator",
                "verdict",
                "matched_verdict",
                "pretrend_p",
                "matched_pretrend_p",
            ]
        ].to_string(index=False)
    )
    return t


def forest(t: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from ppg.viz.figures import AXIS, CATEGORICAL, GRID, INK, INK2, MUTED, SURFACE, _save, _style

    d = t[(t.unit == "pp")].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(10, 0.42 * len(d) + 1.6))
    y = np.arange(len(d))[::-1]
    ax.axvline(0, color=AXIS, lw=1)
    for yi, (_, r) in zip(y, d.iterrows(), strict=True):
        if r.comparator is not None and not np.isnan(r.comparator):
            ax.plot(
                [r.comparator * 50, r.comparator * 100],
                [yi, yi],
                color=GRID,
                lw=6,
                solid_capstyle="butt",
                zorder=1,
            )
        col = CATEGORICAL[1] if r.verdict == "FAIL" else CATEGORICAL[0]
        ax.errorbar(
            r.att * 100, yi, xerr=1.96 * r.se * 100, fmt="none", ecolor=col, lw=1.5, zorder=2
        )
        ax.scatter(r.att * 100, yi, s=40, color=col, ec=SURFACE, lw=1.5, zorder=3)
        if r.matched_att is not None and not np.isnan(r.matched_att):
            ax.scatter(
                r.matched_att * 100,
                yi,
                s=36,
                facecolors=SURFACE,
                edgecolors=MUTED,
                lw=1.5,
                zorder=3,
            )
    ax.set_yticks(y, [f"{r.test} — {r.brand}" for _, r in d.iterrows()], fontsize=8.5)
    _style(ax, grid="x")
    ax.set_xlabel("Estimate, percentage points (95% CI)", color=INK2)
    ax.scatter([], [], s=40, color=CATEGORICAL[0], label="Primary estimator: pass")
    ax.scatter([], [], s=40, color=CATEGORICAL[1], label="Primary estimator: fail")
    ax.scatter([], [], s=36, facecolors=SURFACE, edgecolors=MUTED, lw=1.5, label="Matched")
    ax.plot([], [], color=GRID, lw=6, label="Half to full comparator effect")
    ax.legend(loc="upper center", bbox_to_anchor=(0.3, -0.07), ncol=4, frameon=False, fontsize=8)
    fig.suptitle("Falsification tests", x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout(rect=(0, 0.09, 1, 0.96))
    _save(
        fig,
        "p17_falsification_forest",
        "Fail = 95% CI excludes 0 and the estimate is at least half the comparator (grey band: "
        "half to full comparator) in its direction (PREREGISTRATION.md §9). Panel-form CS-DR; "
        "hollow: matched (CEM).\nSource: CMS Open Payments, Medicare Part D Prescribers.",
    )


def event_charts() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from ppg.viz.figures import AXIS, BRAND_COLOR, CATEGORICAL, GRID, INK, INK2, _save, _style

    nc = json.loads((QA / "falsification_nc_exposure.json").read_text())
    br = {b: json.loads((QA / f"falsification_{b}.json").read_text()) for b in PRIMARY_BRANDS}
    cols = (CATEGORICAL[1], CATEGORICAL[4], CATEGORICAL[0])
    panels = [
        (
            "Any GLP-1 ≥ 11 claims, by first payment for…",
            [(NC_CLASSES[c], nc[c]["event"], col) for c, col in zip(NC_CLASSES, cols, strict=True)],
        )
    ]
    panels += [
        (
            f"Statins ≥ 11 claims, by first {b} payment",
            [(b, br[b]["statin_binary"]["event"], BRAND_COLOR[b])],
        )
        for b in PRIMARY_BRANDS
    ]
    panels += [
        (
            f"Any other GLP-1, by first {b} payment",
            [(b, br[b]["other_glp1_pretrend"]["event"], BRAND_COLOR[b])],
        )
        for b in PRIMARY_BRANDS
    ]
    panels += [
        (
            f"{br[b]['placebo_brand']['outcome']} ≥ 11 claims, by first {b} payment",
            [(b, br[b]["placebo_brand"]["event"], BRAND_COLOR[b])],
        )
        for b in PLACEBO_BRAND
    ]
    fig, axes = plt.subplots(3, 3, figsize=(12, 10.5))
    for ax, (title, lines) in zip(axes.flat, panels, strict=False):
        ax.axhline(0, color=AXIS, lw=1)
        ax.axvline(-0.5, color=GRID, lw=1, ls="--")
        for label, ev, col in lines:
            e = pd.DataFrame(ev)
            e = pd.concat([e, pd.DataFrame({"e": [-1], "att": [0.0], "se": [0.0]})])
            e = e[e.e.between(-5, 3)].sort_values("e")
            ax.fill_between(
                e.e,
                (e.att - 1.96 * e.se) * 100,
                (e.att + 1.96 * e.se) * 100,
                color=col,
                alpha=0.15,
                lw=0,
            )
            ax.plot(e.e, e.att * 100, color=col, lw=2, marker="o", ms=4, label=label)
        _style(ax)
        ax.set_title(title, loc="left", fontsize=9, color=INK)
        ax.set_xticks(range(-5, 4))
        ax.yaxis.set_major_formatter(lambda v, _: f"{v:+.0f}")
        if len(lines) > 1:
            ax.legend(loc="upper left", frameon=False, fontsize=7.5)
    for ax in axes.flat[len(panels) :]:
        ax.axis("off")
    for ax in axes[:, 0]:
        ax.set_ylabel("pp vs year before payment", color=INK2)
    for ax in axes[-1, :]:
        ax.set_xlabel("Years since first payment", color=INK2)
    fig.suptitle(
        "Placebo and negative-control event studies", x=0.01, ha="left", fontsize=11, color=INK
    )
    fig.tight_layout(rect=(0, 0.05, 1, 0.96))
    _save(
        fig,
        "p17_placebo_event_studies",
        "Panel-form CS-DR, universal base (year before first payment); bands: 95% CIs clustered "
        "by practice. Physicians.\nSource: CMS Open Payments, Medicare Part D Prescribers.",
    )


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "all"
    {"all": run_all, "report": report}[cmd]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
