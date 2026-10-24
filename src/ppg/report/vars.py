"""Every number in report/index.qmd, as Quarto variables (`{{< var name >}}`).

Two sources, both read from report/qa: the pinned claims registry (ppg.qa.claims, checked by
`make qa`), and values derived here from the QA tables (ranges, ratios, state names), written to
report/qa/article_derived.json so each one traces to a file. tests/test_article.py fails if the
article types a statistic by hand or uses a variable that does not exist.

    python -m ppg.report.vars      -> report/_variables.yml, report/qa/article_derived.json
"""

from __future__ import annotations

import json

import pandas as pd
import yaml

from ppg import config
from ppg.qa.claims import CLAIMS

QA = config.QA_DIR
PRIMARY = ("Trulicity", "Victoza", "Ozempic")


def _j(name):
    return json.loads((QA / name).read_text())


def _minus(s: str) -> str:
    return s.replace("-", "−")  # typographic minus


def _pp(x: float, d: int = 1, sign: bool = True) -> str:
    return _minus(f"{x * 100:+.{d}f}" if sign else f"{x * 100:.{d}f}")


def _pct(x: float, d: int = 0) -> str:
    return f"{x * 100:.{d}f}"


def _range(vals, fmt) -> str:
    lo, hi = min(vals), max(vals)
    return fmt(lo) if fmt(lo) == fmt(hi) else f"{fmt(lo)}–{fmt(hi)}"


def derived() -> dict[str, str]:
    """Article values computed from report/qa (each formatted as quoted)."""
    v: dict[str, str] = {}
    eda, pay, mt = _j("eda.json"), _j("payments.json"), _j("matched.json")["brands"]
    sw, fam = _j("switching.json"), _j("secondary_family.json")
    flow = {f["step"].strip()[:12]: f["npis"] for f in _j("panel.json")["flow"]}
    v["n_partd_prescribers"] = f"{flow['All Part D p']:,}"
    v["n_diabetes"] = f"{flow['Diabetes pre']:,}"
    v["n_physicians"] = f"{flow['of which phy']:,}"
    v["glp1_records_m"] = f"{pay['glp1_records'] / 1e6:.1f}"
    sh = eda["chart4"]["glp1_promo_usd_by_type_share"]
    v["fees_share"] = _pct(sh["usd_speaker"] + sh["usd_consulting"])
    c7 = eda["chart7"]
    v["top10_share"], v["median_usd"] = _pct(c7["top10_share"]), f"{c7['median_usd']:.0f}"
    v["top1_speaker_share"] = _pct(c7["top1_speaker_share"])
    v["n_paid_lorenz"] = f"{c7['npis']:,}"
    c6 = eda["chart6"]
    v["state_max_name"] = max(c6["top5_states"], key=c6["top5_states"].get)
    v["state_min_name"] = min(c6["bottom5_states"], key=c6["bottom5_states"].get)
    v["masked_states"] = ", ".join(sorted(s for s in c6["masked_states"] if s not in ("GU", "VI")))
    sp = eda["specialty_2024"]
    per = {k: x["usd_per_1000_dm_claims"] for k, x in sp.items()}
    v["endo_ratio"] = f"{per['endocrinology'] / per['primary_care_physician']:.0f}"
    lk = pd.read_csv(QA / "linkage_match_rates.csv")
    md = lk[lk.recipient_class == "md_do"].set_index("program_year").match_rate
    v["link_2013"], v["link_2015"] = _pct(md[2013], 1), _pct(md[md.index >= 2015].min(), 1)
    ov = pd.read_csv(QA / "linkage_overlap_by_year.csv").dropna(subset=["fills"])
    v["fills_paid_2013"] = _pct(ov.share_fills_ever_glp1_paid.iloc[0])
    v["fills_paid_2024"] = _pct(ov.share_fills_ever_glp1_paid.iloc[-1])
    # newly paid physicians
    dr = pd.read_csv(QA / "dose_response.csv")
    g = dr[dr.family == "dose_g"]
    low = [g[(g.brand == b) & (g.group == "< $100")].treated.iloc[0] / g[g.brand == b].treated.sum()
           for b in PRIMARY]  # fmt: skip
    v["share_under_100"] = _range(low, _pct)
    t1 = dr[(dr.family == "type_01") & dr.group.str.startswith("Speaker")]
    v["n_fee_first"] = _range(t1.treated.tolist(), lambda x: f"{x:,}")
    for b in PRIMARY:
        k = b.lower()
        v[f"treated_{k}"] = f"{mt[b]['primary']['treated']:,}"
        v[f"dev8_{k}"] = _pp(mt[b]["volume_growth"]["att"])
        v[f"honest_{k}"] = f"{mt[b]['primary']['honest_breakdown_mbar']:g}"
        c = dr[(dr.brand == b) & (dr.family == "contacts_g")].set_index("group").att
        v[f"contacts1_{k}"], v[f"contacts4_{k}"] = _pp(c["1 contact"]), _pp(c["≥ 4 contacts"])
    v["share_matched"] = _range([mt[b]["registered"]["share_matched"] for b in PRIMARY], _pct)
    v["growth_smd"] = _range([mt[b]["registered"]["growth_smd_after"] for b in PRIMARY],
                             lambda x: f"{x:.2f}")  # fmt: skip
    v["own_smd"] = f"{max(mt[b]['registered']['max_abs_smd_after'] for b in PRIMARY):.2f}"
    # brand share (P15)
    for b in ("Trulicity", "Ozempic", "Mounjaro", "Victoza"):
        k = b.lower()
        r = sw[b]
        v[f"frac_{k}"] = _pp(r["own_share_fractional_matched"]["att"])
        v[f"share_pre_{k}"] = f"{r['pretrend_wald']['p']:.2f}"
        d = r["dumbbell"]
        v[f"db_paid_{k}"], v[f"db_ctrl_{k}"] = _pct(d["paid_post"]), _pct(d["control_post"])
        v[f"db_pre_{k}"] = _pct(d["paid_pre"])
        ev = pd.DataFrame(_j(f"es/switching_{b}.json")["own_event"]).set_index("e").att
        v[f"share_last_{k}"] = _pp(ev[ev.index <= 3].iloc[-1])
    se = pd.read_csv(QA / "switching_estimates.csv")
    ba = se[se.estimate == "base_adjusted"].set_index(["exposure", "share_of"]).att
    pairs = {
        "tru_vic": ("Trulicity", "Victoza"),
        "oz_tru": ("Ozempic", "Trulicity"),
        "mj_tru": ("Mounjaro", "Trulicity"),
    }
    for k, (e, o) in pairs.items():
        v[f"src_{k}"] = _pp(abs(ba[e, o]), sign=False)  # quoted as "falls by"
    # falsification (P17)
    f = pd.read_csv(QA / "falsification.csv")
    tot = f[f.test.str.startswith("Diagnostic: total Part D claims, ratio (unmatched)")]
    v["total_claims_growth"] = _range(tot.att.tolist(), _pct)
    pt = f[f.test.str.startswith("Placebo timing")]
    v["placebo_max"] = _pp(pt.att.max())
    nc = f[f.test.str.startswith("Negative-control exposure")].set_index("brand")
    nce = f[f.test.str.startswith("Negative-control exposure")]
    v["nc_anticoag_ratio"] = _pct(nce.att.iloc[0] / nce.comparator.iloc[0])
    v["nc_inhaled_ratio"] = _pct(nce.att.iloc[1] / nce.comparator.iloc[1])
    del nc
    pb = f[f.test.str.startswith("Placebo brand: Ozempic")]
    v["placebo_brand_oz"] = _pp(pb.att.iloc[0])
    # sensitivity (P18)
    s = pd.read_csv(QA / "sensitivity.csv")
    s = s[s.group.str.startswith("Pr(")]
    for b in PRIMARY:
        a = s[s.brand == b].att
        v[f"sens_{b.lower()}"] = f"{a.min():.1f}–{a.max():.1f}"
    v["n_specs"] = str(s.spec.nunique() - 1)  # alternatives to the primary
    # heterogeneity (P19)
    hc = pd.read_csv(QA / "heterogeneity_comparisons.csv")
    reg = hc[hc.dimension == "Region"]
    v["south_gap"] = _range((-reg.att).tolist(), lambda x: _pp(x, sign=False))
    rur = hc[hc.dimension == "Urbanicity"].set_index("brand").att
    v["rural_trulicity"], v["rural_victoza"] = _pp(rur["Trulicity"]), _pp(rur["Victoza"])
    spc = hc[hc.dimension == "Specialty"].set_index(["brand", "group"]).att
    v["oz_endo"], v["oz_cardio"] = (
        _pp(spc["Ozempic", "endocrinology"]),
        _pp(spc["Ozempic", "cardiology"]),
    )
    h7 = fam["H7 by brand"]
    v["h7_trulicity"], v["h7_ozempic"] = _pp(h7["Trulicity"]["att"]), _pp(h7["Ozempic"]["att"])
    v["h7_victoza_n"] = f"{h7['Victoza']['treated']}"
    v["h3_holm"] = f"{fam['family']['H3 endocrinology + cardiology − primary care']['p_holm']:.2f}"
    for k, r in fam["family"].items():
        p = r["p_holm"]
        v[f"{k.split()[0].lower()}_holm_fmt"] = "< 0.001" if p < 0.001 else f"{p:.3f}"
    return v


def claim_vars() -> dict[str, str]:
    out = {}
    for c in CLAIMS:
        q = c.quoted()
        signed = c.scale == 100.0 and c.digits == 1 and not c.id.endswith("holm")
        out[c.id] = _minus(f"{q:+.{c.digits}f}" if signed else f"{q:,.{c.digits}f}")
    return out


def build() -> dict[str, str]:
    d = derived()
    (QA / "article_derived.json").write_text(json.dumps(d, indent=1, ensure_ascii=False))
    v = claim_vars() | d
    alt = json.loads((config.FIGURE_DIR / "final" / "alt_text.json").read_text())
    v |= {f"alt_{k}": a for k, a in alt.items()}
    (config.REPORT_DIR / "_variables.yml").write_text(
        "# generated by python -m ppg.report.vars: do not edit\n"
        + yaml.safe_dump(v, allow_unicode=True, sort_keys=True, width=1000)
    )
    return v


if __name__ == "__main__":
    for k, x in build().items():
        print(f"{k}: {x}")
