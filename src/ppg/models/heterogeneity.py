"""Heterogeneity, geography, H7 and the secondary Holm family (P19; DEV-10).

    python -m ppg.models.heterogeneity all      # subgroups, H7, pooled secondary tests (progress)
    python -m ppg.models.heterogeneity report   # tables, Holm, heterogeneity chart, state map data

Subgroup ATTs are estimated within each subgroup's own sample (treated and controls) with the
panel-form CS-DR (D27). Differences and brand-pooled tests combine influence functions summed by
practice across fits, so shared practices, physicians and controls are accounted for.
Every reported cell has >= 11 treated physicians (CLAUDE.md ethics rule).
"""

from __future__ import annotations

import json
import sys

import duckdb
import numpy as np
import pandas as pd

from ppg import config
from ppg.models.cs_panel import fit
from ppg.models.data import PRIMARY_BRANDS, SAMPLE, STATE_REGION, frame
from ppg.models.dose_response import unit_measures
from ppg.models.event_study import QA, _p, holm
from ppg.models.falsification import array, ppml_fit
from ppg.models.matched import Wide, load
from ppg.models.switching import EXPOSURES, claims, frac_fit, shares
from ppg.viz.figures import LABELS

SPECIALTY_REF = "primary_care_physician"
SPECIALTIES = (SPECIALTY_REF, "endocrinology", "cardiology", "nephrology", "other_physician")
REGIONS = ("South", "Northeast", "Midwest", "West")  # reference first
URBAN = ("Urban", "Rural")
DOMINANCE = config.DOMINANCE  # mask a geography cell if one prescriber holds > 50% of its $


def combine(parts: list[tuple[float, dict]]) -> dict:
    """Linear combination sum_k w_k * est_k with practice-clustered influence functions."""
    att = float(sum(w * p["att"] for w, p in parts))
    s = pd.concat([w * p["if"] for w, p in parts], axis=1).fillna(0).sum(axis=1)
    se = float(np.sqrt((s**2).sum()))
    return {"att": att, "se": se, "p": _p(att, se) if se > 0 else float(att == 0) or 0.0}


def _fit(df: pd.DataFrame, **kw) -> dict:
    r = fit(Wide(df), return_if=True, **kw)
    o = r["overall_0_3"]
    return {"att": o["att"], "se": o["se"], "if": r["if_overall"],
            "treated": int((df.groupby("npi").g.first() > 0).sum())}  # fmt: skip


def _modal(df: pd.DataFrame, col: str) -> pd.Series:
    m = df.groupby("npi")[col].agg(lambda s: s.mode().iloc[-1] if s.notna().any() else np.nan)
    return df.npi.map(m)


# ------------------------------------------------------------------ subgroups


def subgroups(brand: str) -> dict:
    df = frame(brand)
    df["region_m"] = _modal(df, "region")
    df["urban_m"] = np.where(_modal(df, "urban") == 1, "Urban", "Rural")
    dims = {"Specialty": ("specialty_group", SPECIALTIES), "Region": ("region_m", REGIONS),
            "Urbanicity": ("urban_m", URBAN)}  # fmt: skip
    out: dict = {}
    for dim, (col, levels) in dims.items():
        out[dim] = {}
        for lev in levels:
            d = df[df[col] == lev]
            if (d.groupby("npi").g.first() > 0).sum() < config.MIN_CELL:
                continue
            out[dim][lev] = _fit(d)
            print(brand, dim, lev, round(out[dim][lev]["att"] * 100, 2), flush=True)
    spec = df[df.specialty_group.isin(["endocrinology", "cardiology"])]
    out["H3 specialists"] = _fit(spec)
    return out


def comparisons(sub: dict[str, dict]) -> pd.DataFrame:
    """DEV-10 family: per brand, subgroup minus reference (24 tests)."""
    rows = []
    for b, s in sub.items():
        for dim, ref in (
            ("Specialty", SPECIALTY_REF),
            ("Region", "South"),
            ("Urbanicity", "Urban"),
        ):
            for lev, est in s[dim].items():
                if lev == ref:
                    continue
                c = combine([(1.0, est), (-1.0, s[dim][ref])])
                rows.append({"brand": b, "dimension": dim, "group": lev, "reference": ref, **c})
    t = pd.DataFrame(rows)
    t["key"] = t.brand + "|" + t.dimension + "|" + t.group
    t["p_holm"] = t.key.map(holm(dict(zip(t.key, t.p, strict=True))))
    return t.drop(columns="key")


# ------------------------------------------------------------------ secondary family (H2-H7)


def _pool(per_brand: dict[str, list[tuple[float, dict]]], n: dict[str, int]) -> dict:
    tot = sum(n.values())
    return combine([(n[b] / tot * w, est) for b, parts in per_brand.items() for w, est in parts])


def secondary(sub: dict[str, dict], p=None) -> dict:
    out = {}
    h2, h4, n2, n4 = {}, {}, {}, {}
    h5, n5, h6, n6, h7, n7 = {}, {}, {}, {}, {}, {}
    for b in PRIMARY_BRANDS:
        w = load(b)
        m = unit_measures(frame(b), w)
        tr = (m.g > 0).to_numpy()
        fee = (m.type_01 == "Speaker or consulting fee").to_numpy() & tr
        meal = (m.type_01 == "Meals only").to_numpy() & tr
        hi = (m.usd_g >= 100).to_numpy() & tr
        lo = (m.usd_g < 100).to_numpy() & tr

        def est(keep: np.ndarray, w: Wide = w) -> dict:
            r = fit(w, keep=keep, return_if=True)
            return r["overall_0_3"] | {"if": r["if_overall"]}

        h2[b] = [(1.0, est(fee)), (-1.0, est(meal))]
        n2[b] = int(fee.sum() + meal.sum())
        h4[b] = [(1.0, est(hi)), (-1.0, est(lo))]
        n4[b] = int(hi.sum() + lo.sum())
        # H6: matched PPML fills, suppressed at cap (DEV-9, DEV-10)
        df = frame(b)
        sup = df.status == "suppressed"
        fills = df.fills.where(df.status == "observed", 0).fillna(0)
        y = array(w, df, fills.where(~sup, df.supp_cap.fillna(10)))
        r6 = ppml_fit(w, y, matched=True, return_if=True)
        h6[b] = [(1.0, {"att": r6["tau_log"], "if": r6["if"]})]
        n6[b] = int(tr.sum())
        # H7: NPs / PAs, cohorts 2022+ (2021 washout)
        d7 = frame(b, sample="np_pa", first_cohort=2022)
        r7 = _fit(d7)
        h7[b] = [(1.0, r7)]
        n7[b] = r7["treated"]
        out.setdefault("H7 by brand", {})[b] = {k: v for k, v in r7.items() if k != "if"}
        if p:
            p.advance("secondary family", 1)
    for b in EXPOSURES:  # H5: registered log-odds share effect, matched, incl. Mounjaro
        w = load(b, **EXPOSURES[b])
        r5 = frac_fit(w, shares(claims(w), w.cls)[b], matched=True, return_if=True)
        h5[b] = [(1.0, r5)]
        n5[b] = int((w.g > 0).sum())
    h3 = {b: [(1.0, sub[b]["H3 specialists"]), (-1.0, sub[b]["Specialty"][SPECIALTY_REF])]
          for b in PRIMARY_BRANDS}  # fmt: skip
    n3 = {b: sub[b]["H3 specialists"]["treated"] + sub[b]["Specialty"][SPECIALTY_REF]["treated"]
          for b in PRIMARY_BRANDS}  # fmt: skip
    tests = {
        "H2 speaker/consulting − meals only": _pool(h2, n2),
        "H3 endocrinology + cardiology − primary care": _pool(h3, n3),
        "H4 ≥ $100 − < $100 in the first year": _pool(h4, n4),
        "H5 own-brand share (log-odds, matched)": _pool(h5, n5),
        "H6 fills, PPML matched, suppressed = cap (log ratio)": _pool(h6, n6),
        "H7 NPs/PAs, Pr(≥ 11 claims)": _pool(h7, n7),
    }
    adj = holm({k: v["p"] for k, v in tests.items()})
    for k in tests:
        tests[k]["p_holm"] = adj[k]
    tests["H6 fills, PPML matched, suppressed = cap (log ratio)"]["ratio"] = float(
        np.expm1(tests["H6 fills, PPML matched, suppressed = cap (log ratio)"]["att"])
    )
    out["family"] = tests
    out["weights_n"] = {"H2": n2, "H3": n3, "H4": n4, "H5": n5, "H6": n6, "H7": n7}
    return out


# ------------------------------------------------------------------ geography (descriptive)


def state_specialty(year: int = 2024) -> pd.DataFrame:
    """GLP-1 promotional $ per 1,000 non-GLP-1 diabetes claims by state x specialty group (P10
    diabetes-prescriber sample, all individual prescribers); cells < 11 prescribers masked."""
    d = duckdb.sql(
        f"""SELECT y.state, d.specialty_group, count(*) AS prescribers,
                   sum(coalesce(y.glp1_usd, 0)) AS usd, sum(coalesce(y.dm_load, 0)) AS dm,
                   max(coalesce(y.glp1_usd, 0)) AS max_usd,
                   avg((coalesce(y.glp1_usd, 0) > 0)::INT) AS share_paid
            FROM '{config.PARQUET_DIR}/panel/npi_year.parquet' y
            JOIN '{config.PARQUET_DIR}/panel/npi_dims.parquet' d USING (npi)
            WHERE {SAMPLE} AND y.year = {year} AND y.state IS NOT NULL
            GROUP BY ALL"""
    ).df()
    d = d[d.state.isin(set(STATE_REGION))]
    d["usd_per_1000_dm"] = 1000 * d.usd / d.dm
    # disclosure control: >= 11 prescribers (CLAUDE.md) and no single prescriber holding more
    # than half the cell's dollars (dominance rule: payments are highly concentrated, P11)
    small = d.prescribers < config.MIN_CELL
    dominated = d.max_usd > DOMINANCE * d.usd
    d["masked"] = np.select([small, dominated], ["< 11 prescribers", "dominance"], "")
    d.loc[small | dominated, ["usd", "dm", "usd_per_1000_dm", "share_paid"]] = np.nan
    d["prescribers"] = d.prescribers.where(~small)
    return d.drop(columns="max_usd").sort_values(["state", "specialty_group"], ignore_index=True)


# ------------------------------------------------------------------ run / report


def _strip(x):
    if isinstance(x, dict):
        return {k: _strip(v) for k, v in x.items() if k != "if"}
    return x


def run_all() -> None:
    from ppg.progress import Progress

    with Progress("heterogeneity") as p:
        for b in PRIMARY_BRANDS:
            p.add(b, total=1, unit="brand")
        p.add("secondary family", total=3, unit="brands")
        sub = {}
        for b in PRIMARY_BRANDS:
            p.start(b)
            sub[b] = subgroups(b)
            p.finish(b)
        comp = comparisons(sub)
        p.start("secondary family")
        sec = secondary(sub, p)
        p.finish("secondary family")
    QA.mkdir(parents=True, exist_ok=True)
    (QA / "heterogeneity.json").write_text(json.dumps(
        {"subgroups": _strip(sub), "comparisons": comp.to_dict("records"),
         "secondary": _strip(sec)}, indent=1, default=float))  # fmt: skip


def report() -> dict:
    r = json.loads((QA / "heterogeneity.json").read_text())
    rows = [{"brand": b, "dimension": dim, "group": lev, **est}
            for b, s in r["subgroups"].items() for dim, levs in s.items() if dim != "H3 specialists"
            for lev, est in levs.items()]  # fmt: skip
    t = pd.DataFrame(rows)
    t["label"] = t.group.map(lambda g: LABELS.get(g, g))
    t["lo"], t["hi"] = t.att - 1.96 * t.se, t.att + 1.96 * t.se
    t["fragile"] = (t.treated < 500) | ((t.hi - t.lo) > 0.10)
    t.to_csv(config.QA_DIR / "heterogeneity.csv", index=False)
    comp = pd.DataFrame(r["comparisons"])
    comp.to_csv(config.QA_DIR / "heterogeneity_comparisons.csv", index=False)
    fam = pd.DataFrame(r["secondary"]["family"]).T
    fam.to_csv(config.QA_DIR / "secondary_family.csv")
    geo = state_specialty()
    geo.to_csv(config.QA_DIR / "state_specialty_2024.csv", index=False)
    (config.QA_DIR / "secondary_family.json").write_text(
        json.dumps(r["secondary"], indent=1, default=float))  # fmt: skip
    chart(t)
    heatmap(geo)
    with pd.option_context("display.width", 200):
        print(t[["brand", "dimension", "label", "treated", "att", "lo", "hi", "fragile"]]
              .round(4).to_string(index=False))  # fmt: skip
        print(comp[["brand", "dimension", "group", "att", "se", "p", "p_holm"]].round(4)
              .to_string(index=False))  # fmt: skip
        print(fam.to_string())
        print(json.dumps(r["secondary"]["H7 by brand"], indent=1, default=float))
    return r


def chart(t: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from ppg.viz.figures import AXIS, BRAND_COLOR, GRID, INK, INK2, SURFACE, _save, _style

    dims = ["Specialty", "Region", "Urbanicity"]
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.8), sharex=True,
                             gridspec_kw={"width_ratios": [1, 1, 1]})  # fmt: skip
    for ax, dim in zip(axes, dims, strict=True):
        d = t[t.dimension == dim]
        labels = list(dict.fromkeys(d.label))
        ypos = {lab: i for i, lab in enumerate(reversed(labels))}
        ax.axvline(0, color=AXIS, lw=1)
        for k, b in enumerate(PRIMARY_BRANDS):
            x = d[d.brand == b]
            y = x.label.map(ypos) + (k - 1) * 0.22
            ax.errorbar(x.att * 100, y, xerr=1.96 * x.se * 100, fmt="none",
                        ecolor=BRAND_COLOR[b], lw=1.3)  # fmt: skip
            ax.scatter(x.att * 100, y, s=30, color=BRAND_COLOR[b], ec=SURFACE, lw=1, zorder=3,
                       label=b)  # fmt: skip
        for yv in ypos.values():
            ax.axhline(yv + 0.5, color=GRID, lw=0.5)
        ax.set_yticks(list(ypos.values()), list(ypos.keys()), fontsize=9)
        _style(ax, grid="x")
        ax.set_title(dim, loc="left", fontsize=10, color=INK)
        ax.set_xlabel("Change in Pr(≥ 11 claims), pp", color=INK2)
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, loc="upper right", ncol=3, frameon=False, fontsize=8.5)
    fig.suptitle("Prescribing the paid brand after the first payment, by subgroup", x=0.01,
                 ha="left", fontsize=11, color=INK)  # fmt: skip
    fig.tight_layout(rect=(0, 0.08, 1, 0.94))
    _save(
        fig,
        "p19_heterogeneity",
        "ATT over event years 0–3, estimated within each subgroup (treated and not-yet-paid "
        "controls); 95% CIs clustered by practice; region and urbanicity are each physician's "
        "modal value. Physicians; every cell ≥ 11 treated physicians.\nSource: CMS Open "
        "Payments, Medicare Part D Prescribers. Associations, not proof of causation.",
    )


def heatmap(geo: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.colors
    import matplotlib.pyplot as plt

    from ppg.viz.figures import INK, INK2, SEQUENTIAL, SURFACE, _save

    order = ["endocrinology", "primary_care_physician", "nurse_practitioner",
             "physician_assistant", "cardiology", "nephrology", "other_physician"]  # fmt: skip
    m = geo.pivot(index="state", columns="specialty_group", values="usd_per_1000_dm")[order]
    tot = geo.groupby("state")[["usd", "dm"]].sum()
    m = m.loc[(tot.usd / tot.dm).sort_values(ascending=False).index]
    fig, ax = plt.subplots(figsize=(8, 13))
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("seq", SEQUENTIAL)
    cmap.set_bad(SURFACE)
    vmax = np.nanquantile(m.values, 0.97)
    im = ax.imshow(m.values, aspect="auto", cmap=cmap, vmin=0, vmax=vmax)
    ax.set_xticks(range(len(order)), [LABELS[o] for o in order], rotation=35, ha="right",
                  fontsize=8.5)  # fmt: skip
    ax.set_yticks(range(len(m)), m.index, fontsize=7.5)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0, colors=INK2)
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.set_label("GLP-1 promotional $ per 1,000 non-GLP-1 diabetes claims", color=INK2)
    cb.outline.set_visible(False)
    ax.set_title(
        "GLP-1 promotional dollars relative to diabetes workload, 2024\nby state and "
        "specialty (blank: < 11 prescribers or one prescriber > 50% of dollars)",
        loc="left",
        fontsize=10.5,
        color=INK,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    _save(
        fig,
        "p19_state_specialty_heatmap",
        "P10 diabetes-prescriber sample (individual prescribers with ≥ 2 years of ≥ 11 non-GLP-1 "
        "diabetes claims); states sorted by overall rate; colour capped at the 97th percentile."
        "\nSource: CMS Open Payments (PY2024), Medicare Part D Prescribers (2024).",
    )


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "all"
    {"all": run_all, "report": report}[cmd]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
