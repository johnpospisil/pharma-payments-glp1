"""Sensitivity analyses (P18; PREREGISTRATION.md §9 sensitivity list, DEV-8, H6).

    python -m ppg.models.sensitivity all      # every spec x brand (progress bar)
    python -m ppg.models.sensitivity report   # robustness table and forest plot

Binary-outcome specs (pp, ATT over e = 0..3) re-estimate the primary (panel-form CS-DR, D27) with
one change each, plus the matched (CEM) counterpart where it is defined (D28). Scale-free outcomes
(claims, beneficiaries, cost, fills, volume-normalised claims) are reported relative to the paid
physicians' mean in the year before payment, or on the ratio (PPML) scale with suppression
bounds (H6, D14).
"""

from __future__ import annotations

import json
import sys

import duckdb
import numpy as np
import pandas as pd

from ppg import config
from ppg.models.cs_panel import fit
from ppg.models.data import PRIMARY_BRANDS, frame
from ppg.models.event_study import QA, _p
from ppg.models.falsification import array, ppml_fit
from ppg.models.matched import Wide, estimate, run_brand, with_early

P = config.PARQUET_DIR
MAKER = {"Trulicity": "Eli Lilly", "Victoza": "Novo Nordisk", "Ozempic": "Novo Nordisk"}


# ------------------------------------------------------------------ sample / exposure variants


def _paid_practices(brand: str) -> set:
    """Group practices with any member ever promotionally paid for the brand (2013-2025)."""
    return set(duckdb.sql(
        f"""SELECT DISTINCT d.org_pac_id FROM '{P}/payments/npi_brand_first.parquet' f
            JOIN '{P}/panel/npi_dims.parquet' d USING (npi)
            WHERE f.brand = '{brand}' AND f.first_promo_year IS NOT NULL
              AND d.org_pac_id IS NOT NULL""").df().org_pac_id)  # fmt: skip


def _maker_first_year(maker: str) -> pd.Series:
    return (
        duckdb.sql(
            f"""SELECT npi, min(year) AS g FROM '{P}/payments/npi_maker_year.parquet'
            WHERE maker = '{maker}' AND first_promo_date IS NOT NULL GROUP BY 1"""
        )
        .df()
        .set_index("npi")
        .g
    )


def _top_payees(share: float = 0.01) -> set:
    d = duckdb.sql(
        f"""SELECT npi, sum(glp1_usd) AS usd FROM '{P}/panel/npi_year.parquet'
            GROUP BY 1 HAVING sum(glp1_usd) > 0"""
    ).df()
    return set(d[d.usd >= d.usd.quantile(1 - share)].npi)


def variants(brand: str, df: pd.DataFrame) -> dict[str, dict]:
    """name -> {df, fit kwargs, matched: bool}. df None = the primary frame."""
    v: dict[str, dict] = {"Primary (reference)": {}}
    v["Never-treated controls"] = {"fit": {"control": "nevertreated"}, "matched": False}
    dirty = _paid_practices(brand)
    clean = df[(df.g > 0) | ~df.org_pac_id.isin(dirty)]
    v["Never-treated controls in practices with no paid member (D-3)"] = {
        "df": clean, "fit": {"control": "nevertreated"}, "matched": False}  # fmt: skip
    late = (df.g > 0) & (pd.to_datetime(df.first_promo_date).dt.month >= 7)
    d1 = df.copy()
    d1.loc[late, "g"] = np.where(d1.loc[late, "g"] + 1 <= 2024, d1.loc[late, "g"] + 1, 0)
    v["g + 1 when the first payment is in Jul–Dec (D-1)"] = {"df": d1}
    v["Manufacturer-level exposure (D-2)"] = {
        "df": frame(brand, first_year=_maker_first_year(MAKER[brand]))}  # fmt: skip
    v["Molecule-level exposure (any semaglutide / liraglutide / dulaglutide brand)"] = {
        "df": frame(brand, exposure="first_promo_year_molecule")}  # fmt: skip
    v["D8 first-listed product rule"] = {"df": frame(brand, exposure="first_year_first_listed")}
    v["Drop top 1% of GLP-1 payees"] = {"df": df[~df.npi.isin(_top_payees())]}
    pre = df[(df.g > 0) & (df.year < df.g)].assign(ok=lambda x: x.dm_load >= 11)
    weak = pre.groupby("npi").ok.sum().pipe(lambda s: set(s[s < 2].index))
    weak |= set(df[(df.g > 0)].npi) - set(pre.npi)
    v["Diabetes-prescriber filter met before payment (D24)"] = {"df": df[~df.npi.isin(weak)]}
    v["2020 not used as a base year"] = {"fit": {"skip_base": (2020,)}, "matched": False}
    v["State instead of region in covariates"] = {"fit": {"geo": "state"}, "matched": False}
    full = df.groupby("npi").year.transform("size") == df.year.nunique()
    v["Balanced panel (in Part D every year)"] = {"df": df[full]}
    v["High-volume diabetes prescribers"] = {"df": frame(brand, sample="high_volume")}
    return v


def run_variant(spec: dict, df0: pd.DataFrame, w0: Wide) -> dict:
    d = spec.get("df")
    w = w0 if d is None else with_early(d)
    o = fit(w, **spec.get("fit", {}))["overall_0_3"]
    r = {"att": o["att"], "se": o["se"], "p": _p(**o),
         "treated": int((w.g > 0).sum()), "physicians": len(w.npi)}  # fmt: skip
    if spec.get("matched", True):
        m = estimate(w, "registered")["overall_0_3"]
        r |= {"matched_att": m["att"], "matched_se": m["se"]}
    return r


# ------------------------------------------------------------------ scale-free outcomes


def relative_outcomes(brand: str, df: pd.DataFrame, w: Wide) -> dict:
    """Brand claims / beneficiaries / cost (suppressed = 0), fills on the PPML ratio scale with
    suppression bounds (H6), log(1 + fills) (D9), and claims per 1,000 Part D claims (DEV-8).
    Linear ATTs are divided by the paid physicians' mean at g - 1."""
    out = {}
    obs = df.status == "observed"
    cap = df.supp_cap.fillna(10)
    sup = df.status == "suppressed"
    base = df[(df.g > 0) & (df.year == df.g - 1)]

    def lin(name: str, values: pd.Series, base_mean: float, unit: str = "relative") -> None:
        y = array(w, df, values)
        o = fit(w, outcome=y)["overall_0_3"]
        m = estimate(w, "registered", outcome=y)["overall_0_3"]
        out[name] = {"att": o["att"], "se": o["se"], "matched_att": m["att"],
                     "matched_se": m["se"], "base_mean": base_mean, "unit": unit}  # fmt: skip

    for col, label in [("claims", "Claims"), ("benes", "Beneficiaries"), ("cost", "Cost")]:
        val = df[col].where(obs, 0).fillna(0)
        lin(f"{label} of the brand (suppressed = 0)", val, float(val[base.index].mean()))
    fills = df.fills.where(obs, 0).fillna(0)
    lin("log(1 + fills) (D9)", np.log1p(fills), 1.0, unit="log points")
    for label, v in [("0", 0), ("5", np.minimum(5, cap)), ("cap", cap)]:
        y = array(w, df, fills.where(~sup, v) if label != "0" else fills)
        out[f"Fills, PPML, suppressed = {label} (H6)"] = {
            "unmatched": ppml_fit(w, y),
            "matched": ppml_fit(w, y, matched=True),
            "unit": "ratio",
        }
    # "never suppressed" is not estimable: a missing row means 0-10 claims *including none*, so
    # it means >= 11 claims of the brand in every Part D year; recorded as counts only
    ns = df[~df.npi.isin(set(df[sup].npi))].groupby("npi").g.first()
    out["Never suppressed for the brand (not estimable)"] = {
        "physicians": int(len(ns)), "treated": int((ns > 0).sum()), "unit": "count"}  # fmt: skip
    claims = df.claims.where(obs, 0).fillna(0)
    for label, c in [("0", claims), ("cap", claims.where(~sup, cap))]:
        per = 1000 * c / df.tot_clms
        lin(f"Claims per 1,000 Part D claims, suppressed = {label} (DEV-8)", per,
            float(per[base.index].mean()))  # fmt: skip
    return out


# ------------------------------------------------------------------ run


def run_brand_all(brand: str, p=None) -> dict:
    df = frame(brand)
    w0 = with_early(df)
    res: dict = {"brand": brand, "binary": {}}
    for name, spec in variants(brand, df).items():
        res["binary"][name] = run_variant(spec, df, w0)
        print(brand, name, round(res["binary"][name]["att"] * 100, 2), flush=True)
        if p:
            p.advance(brand, 1)
    run_brand(brand, w0, specs=("volume_growth",))  # DEV-8 matched spec (writes P14 json)
    vg = json.loads((QA / f"matched_volume_growth_{brand}.json").read_text())
    res["binary"]["Matched also on total-claims growth (DEV-8)"] = {
        "att": vg["overall_0_3"]["att"], "se": vg["overall_0_3"]["se"], "matched_only": True,
        "pretrend_wald": vg["pretrend_wald"]}  # fmt: skip
    res["relative"] = relative_outcomes(brand, df, w0)
    # does the DEV-8 matching also remove the statin negative-control failure (P17)?
    sb = array(w0, df, (df.clms_statin.fillna(0) >= 11).astype(float))
    r = estimate(w0, "volume_growth", outcome=sb)
    res["statin_binary_volume_growth_matched"] = r["overall_0_3"] | {
        "pretrend_wald": r["pretrend_wald"]}  # fmt: skip
    if p:
        p.advance(brand, 2)
    (QA / f"sensitivity_{brand}.json").write_text(json.dumps(res, indent=1, default=float))
    return res


def run_all() -> None:
    from ppg.progress import RESUME, Progress

    with Progress("sensitivity", keep_done=RESUME) as p:
        for b in PRIMARY_BRANDS:
            p.add(b, total=16, unit="specs")
        for b in PRIMARY_BRANDS:
            p.start(b)
            run_brand_all(b, p)
            p.finish(b)


# ------------------------------------------------------------------ report


def table() -> pd.DataFrame:
    rows = []
    for b in PRIMARY_BRANDS:
        r = json.loads((QA / f"sensitivity_{b}.json").read_text())
        prim = r["binary"]["Primary (reference)"]["att"]
        for name, x in r["binary"].items():
            rows.append({"brand": b, "group": "Pr(≥ 11 claims), pp", "spec": name,
                         "att": x["att"] * 100, "lo": (x["att"] - 1.96 * x["se"]) * 100,
                         "hi": (x["att"] + 1.96 * x["se"]) * 100,
                         "matched_att": x.get("matched_att", np.nan) * 100
                         if x.get("matched_att") is not None else np.nan,
                         "ratio_to_primary": x["att"] / prim,
                         "treated": x.get("treated")})  # fmt: skip
        for name, x in r["relative"].items():
            if x["unit"] == "count":
                continue
            if x["unit"] == "ratio":
                for k in ("unmatched", "matched"):
                    y = x[k]
                    rows.append({"brand": b, "group": "Proportional change, %",
                                 "spec": f"{name} [{k}]", "att": y["att"] * 100,
                                 "lo": y["lo"] * 100, "hi": y["hi"] * 100})  # fmt: skip
                continue
            scale = 100 / x["base_mean"] if x["unit"] == "relative" else 100
            rows.append({"brand": b, "group": "Proportional change, %", "spec": name,
                         "att": x["att"] * scale, "lo": (x["att"] - 1.96 * x["se"]) * scale,
                         "hi": (x["att"] + 1.96 * x["se"]) * scale,
                         "matched_att": x["matched_att"] * scale})  # fmt: skip
    t = pd.DataFrame(rows)
    t["excludes_zero"] = (t.lo > 0) | (t.hi < 0)
    return t


def report() -> pd.DataFrame:
    t = table()
    t.to_csv(config.QA_DIR / "sensitivity.csv", index=False)
    (config.QA_DIR / "sensitivity.json").write_text(
        json.dumps(t.to_dict("records"), indent=1, default=float))  # fmt: skip
    forest(t)
    with pd.option_context("display.width", 250, "display.max_colwidth", 70):
        print(t[["brand", "group", "spec", "att", "lo", "hi", "matched_att"]].round(2)
              .to_string(index=False))  # fmt: skip
    return t


def forest(t: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from ppg.viz.figures import AXIS, BRAND_COLOR, GRID, INK, INK2, SURFACE, _save, _style

    groups = list(dict.fromkeys(t.group))
    specs = {g: list(dict.fromkeys(t[t.group == g].spec)) for g in groups}
    h = [len(specs[g]) for g in groups]
    fig, axes = plt.subplots(len(groups), 1, figsize=(11, 0.34 * sum(h) + 2.8),
                             gridspec_kw={"height_ratios": h})  # fmt: skip
    for ax, g in zip(axes, groups, strict=True):
        s = specs[g]
        ypos = {name: i for i, name in enumerate(reversed(s))}
        ax.axvline(0, color=AXIS, lw=1)
        prim = t[(t.group == g) & (t.spec == s[0])]
        for k, b in enumerate(PRIMARY_BRANDS):
            d = t[(t.group == g) & (t.brand == b)]
            y = d.spec.map(ypos) + (k - 1) * 0.24
            ax.errorbar(d.att, y, xerr=[d.att - d.lo, d.hi - d.att], fmt="none",
                        ecolor=BRAND_COLOR[b], lw=1.2)  # fmt: skip
            ax.scatter(d.att, y, s=22, color=BRAND_COLOR[b], ec=SURFACE, lw=1, zorder=3,
                       label=b)  # fmt: skip
            if g.startswith("Pr("):
                pa = prim[prim.brand == b].att.iloc[0]
                ax.axvline(pa, color=BRAND_COLOR[b], lw=0.8, ls=":", zorder=0)
        ax.set_yticks(list(ypos.values()), list(ypos.keys()), fontsize=8)
        for yv in ypos.values():
            ax.axhline(yv + 0.5, color=GRID, lw=0.5, zorder=0)
        _style(ax, grid="x")
        ax.set_title(g, loc="left", fontsize=10, color=INK)
        ax.set_xlabel(g.split(", ")[-1], color=INK2)
    axes[0].legend(loc="lower right", frameon=False, fontsize=8)
    fig.suptitle("Sensitivity analyses: ATT over event years 0–3", x=0.01, ha="left",
                 fontsize=11, color=INK)  # fmt: skip
    fig.tight_layout(rect=(0, 0.04, 1, 0.97))
    _save(
        fig,
        "p18_sensitivity_forest",
        "Top: probability of ≥ 11 claims of the brand, panel-form CS-DR with one change per row "
        "(dotted: primary). Bottom: proportional changes (linear ATT ÷ paid physicians' mean "
        "in g − 1, or PPML ratio). 95% CIs clustered by practice.\nSource: CMS Open Payments, "
        "Medicare Part D Prescribers. Associations, not proof of causation.",
    )


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "all"
    {"all": run_all, "report": report}[cmd]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
