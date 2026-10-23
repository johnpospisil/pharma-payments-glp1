"""Primary event study (P13): Callaway & Sant'Anna via R `did` (PREREGISTRATION.md §6, DEV-1).

    python -m ppg.models.event_study all           # everything below, with a progress bar
    python -m ppg.models.event_study cs            # primary CS for the three brands
    python -m ppg.models.event_study crosscheck    # Sun & Abraham, imputation (did2s), TWFE
    python -m ppg.models.event_study types         # H2: speaker/consulting vs meals-only
    python -m ppg.models.event_study report        # tables, Holm, hero chart v1, qa json

Each CS run writes report/qa/es/<tag>_<brand>.json (aggregates only; cohort cells with
< 11 physicians are removed before saving, CLAUDE.md ethics rule).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from ppg import config
from ppg.models.data import PRIMARY_BRANDS, frame

R = Path(__file__).parent / "r" / "cs_did.R"
RSCRIPT = "/opt/homebrew/bin/Rscript"
WORK = config.DATA_DIR / "work" / "es"
QA = config.QA_DIR / "es"
COLS = [
    "npi",
    "year",
    "y",
    "g",
    "cluster_id",
    "specialty_group",
    "region",
    "log_dm",
    "log_tot",
    "other_glp1",
    "urban",
]
BITERS = 999


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["cluster_id"] = df.cluster.astype("category").cat.codes.astype(int)
    return df


def run_cs(
    brand: str,
    tag: str = "primary",
    df: pd.DataFrame | None = None,
    control: str = "notyettreated",
    biters: int = BITERS,
    balanced: bool = False,
    base: str = "varying",
    covariates: bool = True,
) -> dict:
    """Fit CS for one brand with R did; save and return the aggregated results."""
    df = _prepare(df if df is not None else frame(brand))
    WORK.mkdir(parents=True, exist_ok=True)
    QA.mkdir(parents=True, exist_ok=True)
    inp, raw = WORK / f"{tag}_{brand}.parquet", WORK / f"{tag}_{brand}.raw.json"
    df[COLS].to_parquet(inp, index=False)
    env = {
        "PPG_BALANCED": "TRUE" if balanced else "FALSE",
        "PPG_BASE": base,
        "PPG_NOCOV": "FALSE" if covariates else "TRUE",
        "PATH": "/opt/homebrew/bin:/usr/bin:/bin",
    }
    p = subprocess.run(
        [RSCRIPT, str(R), str(inp), str(raw), control, str(biters)],
        capture_output=True,
        text=True,
        env=env,
    )
    if p.returncode != 0:
        raise RuntimeError(f"R did failed for {brand}/{tag}:\n{p.stderr[-3000:]}")
    res = json.loads(raw.read_text())
    sizes = df.groupby("npi").g.first().value_counts()
    res["att_gt"] = [r for r in res["att_gt"] if sizes.get(r["group"], 0) >= config.MIN_CELL]
    res["cohort_sizes"] = {int(k): int(v) for k, v in sizes.sort_index().items()}
    res["frame"] = {
        k: (int(v) if isinstance(v, (int, np.integer)) else v) for k, v in df.attrs.items()
    } | {
        "physicians": int(df.npi.nunique()),
        "rows": int(len(df)),
        "treated_physicians": int((df.groupby("npi").g.first() > 0).sum()),
        "y_mean_pre_treated": float(df[(df.g > 0) & (df.year == df.g - 1)].y.mean()),
    }
    res["stderr_tail"] = p.stderr[-1500:]
    (QA / f"{tag}_{brand}.json").write_text(json.dumps(res, indent=1, default=float))
    return res


def cs_all(tag: str = "primary", **kw) -> None:
    for b in PRIMARY_BRANDS:
        r = run_cs(b, tag=tag, **kw)
        o = r["overall_0_3"]
        print(
            f"{tag} {b}: ATT(0-3) {o['att']:.4f} (se {o['se']:.4f}); "
            f"{r['n_units']:,} physicians; {r['fit_seconds']:.0f}s",
            flush=True,
        )


# ------------------------------------------------------------------ cross-checks (§6)

E_MIN, E_MAX = -6, 4  # event-time bins for the regression estimators (ends are grouped)


def _regression_frame(brand: str) -> pd.DataFrame:
    """Slim numeric frame for the pyfixest estimators (memory: ~2.7M rows each)."""
    df = _prepare(frame(brand))
    srt = df.specialty_group + "_" + df.region + "_" + df.year.astype(str)
    out = pd.DataFrame(
        {
            "npi": df.npi.astype("int64"),
            "y": df.y.astype("float64"),
            "g": df.g.astype("int32"),
            "cluster_id": df.cluster_id.astype("int32"),
            "rel": np.where(df.g > 0, df.year - df.g, -1).clip(E_MIN, E_MAX).astype("int32"),
            "treat": ((df.g > 0) & (df.year >= df.g)).astype("int64"),
            "srt": srt.astype("category").cat.codes.astype("int32"),
        }
    )
    del df, srt
    return out


def _lincomb(coef: pd.Series, vcov: pd.DataFrame, weights: dict[str, float]) -> tuple:
    names = list(weights)
    w = np.array([weights[n] for n in names])
    est = float(w @ coef[names].values)
    se = float(np.sqrt(w @ vcov.loc[names, names].values @ w))
    return est, se


def _event_names(coef: pd.Series, prefix: str) -> dict[int, str]:
    out = {}
    for name in coef.index:
        if name.startswith((f"{prefix}::", f"C({prefix}")):  # pyfixest: "rel::0"
            tail = name.split("[T.")[-1].rstrip("]") if "[T." in name else name.split("::")[-1]
            try:
                out[int(float(tail))] = name
            except ValueError:
                continue
    return out


def _two_way_fe(y, i, j, tol: float = 1e-9, max_iter: int = 500):
    """y = a[i] + b[j] by alternating projections (memory-light two-way fixed effects)."""
    ni, nj = i.max() + 1, j.max() + 1
    ci, cj = np.bincount(i, minlength=ni), np.bincount(j, minlength=nj)
    a, b = np.zeros(ni), np.zeros(nj)
    for _ in range(max_iter):
        a_new = np.bincount(i, y - b[j], minlength=ni) / np.maximum(ci, 1)
        b_new = np.bincount(j, y - a_new[i], minlength=nj) / np.maximum(cj, 1)
        done = max(np.abs(a_new - a).max(), np.abs(b_new - b).max()) < tol
        a, b = a_new, b_new
        if done:
            break
    return a, b, ci > 0, cj > 0


def crosscheck(brand: str) -> dict:
    """Cross-checks (prereg §6, DEV-1); written to fit in memory on 2-3M rows."""
    import pyfixest as pf

    df = _regression_frame(brand)
    out = {"brand": brand}
    # 1. imputation (Borusyak-Jaravel-Spiess): two-way FE on untreated rows, impute Y(0) for
    #    treated rows, average y - y0 by event time. Point estimates only (the did2s variance
    #    correction does not fit in memory); the agreement rule (§10) compares points.
    npi_code = df.npi.astype("category").cat.codes.to_numpy()
    srt = df.srt.to_numpy()
    u = df.treat.to_numpy() == 0
    a, b, has_a, has_b = _two_way_fe(df.y.to_numpy()[u], npi_code[u], srt[u])
    t = ~u
    ok = t & has_a[npi_code] & has_b[srt]
    y0 = a[npi_code[ok]] + b[srt[ok]]
    tau = pd.DataFrame({"rel": df.rel.to_numpy()[ok], "tau": df.y.to_numpy()[ok] - y0})
    ev = tau.groupby("rel").tau.agg(["mean", "size"])
    out["imputation_event"] = {
        int(e): {"att": float(r["mean"]), "n": int(r["size"])} for e, r in ev.iterrows()
    }
    post = [out["imputation_event"][e]["att"] for e in range(4) if e in out["imputation_event"]]
    out["imputation_0_3"] = {
        "att": float(np.mean(post)),
        "se": None,
        "treated_rows_without_untreated_baseline": int((t & ~ok).sum()),
    }
    # 2. Sun & Abraham interaction-weighted: one regression per cohort (cohort + never-treated),
    #    then cohort-size weights. SEs combined as independent (approximate: shared controls).
    never = df.g == 0
    catt = []
    for g in sorted(df.loc[df.g > 0, "g"].unique()):
        sub = df[never | (df.g == g)]
        if (sub.g == g).sum() < 50:
            continue
        fit = pf.feols("y ~ i(rel, ref=-1) | npi + srt", data=sub, vcov={"CRV1": "cluster_id"})
        n_e = sub[sub.g == g].groupby("rel").size()
        for e, name in _event_names(fit.coef(), "rel").items():
            catt.append(
                {
                    "g": int(g),
                    "e": e,
                    "att": float(fit.coef()[name]),
                    "se": float(fit.se()[name]),
                    "n": int(n_e.get(e, 0)),
                }
            )
        del sub, fit
    c = pd.DataFrame(catt)
    sa_event = {}
    for e, d in c.groupby("e"):
        w = d.n / d.n.sum()
        sa_event[int(e)] = {
            "att": float((w * d.att).sum()),
            "se": float(np.sqrt((w**2 * d.se**2).sum())),
        }
    post = [sa_event[e] for e in range(4) if e in sa_event]
    out["sunab_event"] = sa_event
    out["sunab_0_3"] = {
        "att": float(np.mean([p["att"] for p in post])),
        "se": float(np.sqrt(sum(p["se"] ** 2 for p in post)) / len(post)),
    }
    # 3. static TWFE (diagnostic only: biased under staggered timing)
    tw = pf.feols("y ~ treat | npi + srt", data=df, vcov={"CRV1": "cluster_id"})
    out["twfe_static"] = {"att": float(tw.coef()["treat"]), "se": float(tw.se()["treat"])}
    QA.mkdir(parents=True, exist_ok=True)
    (QA / f"crosscheck_{brand}.json").write_text(json.dumps(out, indent=1, default=float))
    return out


# ------------------------------------------------- H2: first-payment type (secondary)


def payment_type(df: pd.DataFrame) -> pd.Series:
    """Per treated physician: type of the payments naming the brand in the first year."""
    first = df[(df.g > 0) & (df.year == df.g)].set_index("npi")
    other = first.usd - first.usd_food_beverage - first.usd_speaker - first.usd_consulting
    t = np.select(
        [
            first.usd_speaker + first.usd_consulting > 0,
            (first.usd_food_beverage > 0) & (other <= 0.005),
        ],
        ["speaker_consulting", "meals_only"],
        default="other",
    )
    return pd.Series(t, index=first.index, name="ptype")


def types() -> None:
    for b in PRIMARY_BRANDS:
        df = frame(b)
        t = payment_type(df)
        for kind in ("meals_only", "speaker_consulting"):
            keep = (df.g == 0) | df.npi.map(t).eq(kind)
            r = run_cs(b, tag=f"type_{kind}", df=df[keep])
            o = r["overall_0_3"]
            print(
                f"{b} {kind}: ATT {o['att']:.4f} ({o['se']:.4f}), treated "
                f"{r['frame']['treated_physicians']:,}",
                flush=True,
            )


# ----------------------------------------------------------------------- report


def _p(att: float, se: float) -> float:
    from scipy.stats import norm

    return float(2 * norm.sf(abs(att / se)))


def holm(p: dict[str, float]) -> dict[str, float]:
    order = sorted(p, key=p.get)
    out, running = {}, 0.0
    for i, k in enumerate(order):
        running = max(running, min(1.0, (len(p) - i) * p[k]))
        out[k] = running
    return out


def report() -> dict:
    prim = {b: json.loads((QA / f"primary_{b}.json").read_text()) for b in PRIMARY_BRANDS}
    xc = {
        b: json.loads((QA / f"crosscheck_{b}.json").read_text())
        for b in PRIMARY_BRANDS
        if (QA / f"crosscheck_{b}.json").exists()
    }
    rows, pvals = [], {}
    for b, r in prim.items():
        o = r["overall_0_3"]
        pvals[b] = _p(o["att"], o["se"])
        ev = {int(e["e"]): e for e in r["event"]}
        base = r["frame"]["y_mean_pre_treated"]
        rows.append(
            {
                "brand": b,
                "estimator": "CS (R did, primary)",
                "att_0_3": o["att"],
                "se": o["se"],
                "ci_low": o["att"] - 1.96 * o["se"],
                "ci_high": o["att"] + 1.96 * o["se"],
                "att_e0": ev[0]["att"],
                "se_e0": ev[0]["se"],
                "att_1_3": r["overall_1_3"]["att"],
                "se_1_3": r["overall_1_3"]["se"],
                "relative_to_pre_mean": o["att"] / base if base else None,
                "pre_mean": base,
                "pretrend_p": (r.get("pretrend_wald") or {}).get("p"),
                "honest_breakdown_mbar": (r.get("honestdid") or {}).get("breakdown_mbar"),
                "physicians": r["frame"]["physicians"],
                "treated": r["frame"]["treated_physicians"],
            }
        )
        for key, label in (
            ("imputation_0_3", "Imputation (BJS / did2s)"),
            ("sunab_0_3", "Sun & Abraham"),
            ("twfe_static", "TWFE (diagnostic)"),
        ):
            if b in xc:
                x = xc[b][key]
                rows.append(
                    {
                        "brand": b,
                        "estimator": label,
                        "att_0_3": x["att"],
                        "se": x["se"],
                        "ci_low": None if x["se"] is None else x["att"] - 1.96 * x["se"],
                        "ci_high": None if x["se"] is None else x["att"] + 1.96 * x["se"],
                    }
                )
    tab = pd.DataFrame(rows)
    adj = holm(pvals)
    tab["p"] = [
        pvals[b] if e.startswith("CS") else None
        for b, e in zip(tab.brand, tab.estimator, strict=True)
    ]
    tab["p_holm"] = [
        adj[b] if e.startswith("CS") else None
        for b, e in zip(tab.brand, tab.estimator, strict=True)
    ]
    prim_ci = tab[tab.estimator.str.startswith("CS")].set_index("brand")
    tab["agrees_with_primary"] = [
        None
        if e.startswith("CS") or e.startswith("TWFE")
        else bool(
            prim_ci.loc[b, "ci_low"] <= a <= prim_ci.loc[b, "ci_high"]
            and np.sign(a) == np.sign(prim_ci.loc[b, "att_0_3"])
        )
        for b, e, a in zip(tab.brand, tab.estimator, tab.att_0_3, strict=True)
    ]
    tab.to_csv(config.QA_DIR / "event_study_estimates.csv", index=False, float_format="%.6f")
    events = pd.DataFrame(
        [
            {
                "brand": b,
                "e": int(e["e"]),
                "att": e["att"],
                "se": e["se"],
                "se_cluster_if": e["se_cluster_if"],
                "crit_val": r["crit_val_event"],
            }
            for b, r in prim.items()
            for e in r["event"]
        ]
    )
    events.to_csv(config.QA_DIR / "event_study_event_time.csv", index=False, float_format="%.6f")
    hero_chart(events, prim)
    out = {
        "estimates": tab.to_dict(orient="records"),
        "holm": adj,
        "sesoi_pp": 0.02,
        "types": _types_summary(),
    }
    (config.QA_DIR / "event_study.json").write_text(json.dumps(out, indent=1, default=float))
    return out


def _types_summary() -> dict:
    """H2. As registered (type of the first-year payments) it is not estimable: physicians are
    almost never first reached by a speaker or consulting fee, so those cohorts hold 52-91
    physicians per brand and every group-time cell is singular. Counts are reported instead."""
    out = {}
    for b in PRIMARY_BRANDS:
        df = frame(b)
        t = payment_type(df)
        g = df.groupby("npi").g.first()
        counts = t[t.index.isin(g[g > 0].index)].value_counts().to_dict()
        r = {"first_year_type_counts": {k: int(v) for k, v in counts.items()},
             "estimable": False}  # fmt: skip
        for kind in ("meals_only", "speaker_consulting"):
            f = QA / f"type_{kind}_{b}.json"
            if f.exists():
                j = json.loads(f.read_text())
                r[kind] = j["overall_0_3"] | {"treated": j["frame"]["treated_physicians"]}
        if "speaker_consulting" in r and "meals_only" in r:
            d = r["speaker_consulting"]["att"] - r["meals_only"]["att"]
            se = float(np.hypot(r["speaker_consulting"]["se"], r["meals_only"]["se"]))
            r["difference"] = {"att": d, "se": se, "p": _p(d, se)}  # shared controls: approximate
        out[b] = r
    return out


def hero_chart(events: pd.DataFrame, prim: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from ppg.viz.figures import AXIS, CATEGORICAL, GRID, INK, INK2, SURFACE, _save, _style

    fig, axes = plt.subplots(1, 3, figsize=(11.5, 4.4), sharey=True)
    color = dict(
        zip(
            ("Ozempic", "Trulicity", "Victoza"),
            (CATEGORICAL[0], CATEGORICAL[1], CATEGORICAL[3]),
            strict=True,
        )
    )
    for ax, b in zip(axes, PRIMARY_BRANDS, strict=True):
        d = events[(events.brand == b) & events.e.between(-5, 3)].sort_values("e")
        band = d.crit_val * d.se
        ax.axhline(0, color=AXIS, lw=1, zorder=1)
        ax.axvline(-0.5, color=GRID, lw=1, ls="--", zorder=1)
        ax.fill_between(d.e, d.att - band, d.att + band, color=color[b], alpha=0.18, lw=0, zorder=2)
        ax.plot(d.e, d.att, color=color[b], lw=2, zorder=3)
        ax.scatter(d.e, d.att, s=36, color=color[b], ec=SURFACE, lw=2, zorder=4)
        o = prim[b]["overall_0_3"]
        ax.set_title(
            f"{b}: {o['att'] * 100:+.1f} pp (95% CI {(o['att'] - 1.96 * o['se']) * 100:+.1f}"
            f" to {(o['att'] + 1.96 * o['se']) * 100:+.1f})",
            loc="left",
            fontsize=9.5,
            color=INK,
        )
        _style(ax)
        ax.set_xticks(range(-5, 4))
        ax.set_xlabel("Years since first promotional payment for the brand", color=INK2)
        ax.yaxis.set_major_formatter(lambda v, _: f"{v * 100:+.0f} pp")
    axes[0].set_ylabel("Change in probability of ≥ 11 claims of the brand")
    fig.suptitle(
        "Prescribing the paid brand before and after the first payment (event study, v1)",
        x=0.01,
        ha="left",
        fontsize=11,
        color=INK,
    )
    fig.tight_layout(rect=(0, 0.09, 1, 0.93))
    _save(
        fig,
        "hero_v1_event_study",
        "Callaway & Sant'Anna (doubly robust, not-yet-treated controls); bands: 95% simultaneous, "
        "clustered by practice. Year 0 is partly treated. Physicians, P10 diabetes-prescriber "
        "sample.\nSource: CMS Open Payments, Medicare Part D Prescribers. Associations, not proof "
        "of causation.",
    )


# ------------------------------------------------------------- run everything


ROWS_PER_SEC = {"cs": 15_000, "crosscheck": 8_000}  # calibrated on the first Trulicity fit


def _timed(p, task: str, fn):
    """Run fn() while a heartbeat advances the task's bar by elapsed seconds (capped at 97%)."""
    import threading
    import time

    stop = threading.Event()
    t = p.state["tasks"][task]

    def beat() -> None:
        t0 = time.time()
        while not stop.wait(1.0):
            t["done"] = min(time.time() - t0, 0.97 * t["total"])
            p._write()

    p.start(task)
    th = threading.Thread(target=beat, daemon=True)
    th.start()
    try:
        return fn()
    finally:
        stop.set()
        th.join()
        p.finish(task)


def run_all() -> None:
    """All of P13 under one progress job: `make progress WATCH=1` (job event_study)."""
    import gc

    from ppg.progress import Progress

    rows = {}  # expected sizes only; each task rebuilds its frame to keep memory low
    for b in PRIMARY_BRANDS:
        df = frame(b)
        t = payment_type(df)
        rows[b] = {"all": len(df)} | {
            k: int(((df.g == 0) | df.npi.map(t).eq(k)).sum())
            for k in ("meals_only", "speaker_consulting")
        }
        del df, t
        gc.collect()
    plan = []  # (task, kind, brand, payment type, expected seconds)
    for b in PRIMARY_BRANDS:
        plan.append((f"CS primary {b}", "cs", b, None, rows[b]["all"] / ROWS_PER_SEC["cs"]))
    for b in PRIMARY_BRANDS:
        secs = rows[b]["all"] / ROWS_PER_SEC["crosscheck"]
        plan.append((f"cross-checks {b}", "crosscheck", b, None, secs))
    for b in PRIMARY_BRANDS:  # speaker/consulting-first cohorts are too small (52-91 physicians)
        plan.append(
            (
                f"CS meals_only {b}",
                "type",
                b,
                "meals_only",
                rows[b]["meals_only"] / ROWS_PER_SEC["cs"],
            )
        )
    plan.append(("report + hero chart", "report", None, None, 15))
    done_file = {
        "cs": "primary_{b}.json",
        "crosscheck": "crosscheck_{b}.json",
        "type": "type_{k}_{b}.json",
    }
    with Progress("event_study") as p:
        for task, *_rest, secs in plan:
            p.add(task, total=round(secs), unit="s")
        for task, kind, b, k, _secs in plan:
            f = done_file.get(kind)
            if p.is_done(task) or (f and (QA / f.format(b=b, k=k)).exists()):
                if not p.is_done(task):
                    p.start(task)
                    p.finish(task)  # finished in an earlier run
                continue
            if kind == "cs":
                _timed(p, task, lambda b=b: run_cs(b))
            elif kind == "crosscheck":
                _timed(p, task, lambda b=b: crosscheck(b))
            elif kind == "type":
                _timed(p, task, lambda b=b, k=k: _run_type(b, k))
            else:
                _timed(p, task, report)
            gc.collect()


def _run_type(brand: str, kind: str) -> dict:
    df = frame(brand)
    t = payment_type(df)
    return run_cs(brand, tag=f"type_{kind}", df=df[(df.g == 0) | df.npi.map(t).eq(kind)])


def diagnostics() -> None:
    """Universal-base event study (for HonestDiD, DEV-3) and CS without covariates
    (exploratory: explains the gap to the fixed-effects cross-checks)."""
    from ppg.progress import Progress

    plan = [(f"CS universal base {b}", b, "universal", True, "universal") for b in PRIMARY_BRANDS]
    plan += [(f"CS no covariates {b}", b, "varying", False, "nocov") for b in PRIMARY_BRANDS]
    with Progress("event_study_diagnostics") as p:
        for task, *_ in plan:
            p.add(task, total=200, unit="s")
        for task, b, base, cov, tag in plan:
            if (QA / f"{tag}_{b}.json").exists():
                p.start(task)
                p.finish(task)
                continue
            _timed(
                p,
                task,
                lambda b=b, base=base, cov=cov, tag=tag: run_cs(
                    b, tag=tag, base=base, covariates=cov
                ),
            )


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "cs"
    if cmd == "diagnostics":
        diagnostics()
        return 0
    if cmd == "all":
        run_all()
    elif cmd == "cs":
        cs_all()
    elif cmd == "types":
        types()
    elif cmd == "report":
        print(json.dumps(report(), indent=1, default=float))
    elif cmd == "crosscheck":
        for b in argv[1:] or PRIMARY_BRANDS:
            r = crosscheck(b)
            print(b, {k: r[k] for k in ("imputation_0_3", "sunab_0_3", "twfe_static")}, flush=True)
    else:
        raise SystemExit(f"unknown command {cmd}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
