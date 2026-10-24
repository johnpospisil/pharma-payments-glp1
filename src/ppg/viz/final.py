"""Final published figures (P21): hero, chart 1b and charts 2-8, light + dark, alt text, crops.

Everything is drawn from report/qa only (no parquet), so the site build can re-render it. Each
chart is a `draw(t, social)` function; `render` writes, for each one:
    report/figures/final/<name>.png / .svg            light, 2000 px wide
    report/figures/final/<name>_dark.png / _dark.svg  dark
    report/figures/social/<name>_1200x675.png         16:9 crop (light), larger type
plus report/figures/final/alt_text.json and contact_sheet.png. Captions follow docs/qa.md W1-W10
(D38): every headline chart carries its "what this doesn't mean" line.

    python -m ppg.viz.final
"""

from __future__ import annotations

import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import RegularPolygon

from ppg import config
from ppg.viz.theme import BRANDS, axes, dot, footnote, heading, use

QA = config.QA_DIR
OUT = config.FIGURE_DIR / "final"
SOCIAL = config.FIGURE_DIR / "social"
ARTICLE, CROP = (10, 5.6), (12, 6.75)
SRC_OP = "CMS Open Payments (general payments, promotional natures)"
SRC_PD = "CMS Medicare Part D Prescribers"
NOT_CAUSAL = "Associations, not proof that payments changed prescribing."
PRIMARY = ["Trulicity", "Victoza", "Ozempic"]


def _j(name: str):
    return json.loads((QA / name).read_text())


def _pp(v, _=None) -> str:
    return f"{v:+.0f} pp" if round(v) else "0"


def _events(rows, lo=-5, hi=3, scale=100.0) -> pd.DataFrame:
    d = pd.DataFrame(rows)
    d = d[(d.e >= lo) & (d.e <= hi)][["e", "att", "se"]]
    d = pd.concat([d, pd.DataFrame({"e": [-1], "att": [0.0], "se": [0.0]})]).sort_values("e")
    d[["att", "se"]] *= scale
    return d.reset_index(drop=True)


def _xlabel(fig, t, fh: float, text="Years since the physician's first payment for the brand"):
    fig.supxlabel(
        text, y=fh + 0.025, va="bottom", color=t.ink2, fontsize=plt.rcParams["axes.labelsize"]
    )


def _size(social: bool):
    return CROP if social else ARTICLE


def _note(social: bool, full: str, short: str) -> str:
    return short if social else full


# ------------------------------------------------------------------ hero: brand share


HERO = ["Trulicity", "Ozempic", "Mounjaro", "Victoza"]


def hero(t, social=False):
    sw = _j("switching.json")
    fig, axs = plt.subplots(1, 4, figsize=_size(social), sharey=True)
    for ax, b in zip(axs, HERO, strict=True):
        d = _events(_j(f"es/switching_{b}.json")["own_event"], lo=-4)
        c = t.brand(b)
        ax.fill_between(d.e, d.att - 1.96 * d.se, d.att + 1.96 * d.se, color=c, alpha=0.14, lw=0)
        ax.plot(d.e, d.att, color=c, zorder=3)
        dot(ax, d.e, d.att, c, t)
        ax.axhline(0, color=t.axis, lw=0.9, zorder=1)
        ax.axvline(-0.5, color=t.muted, lw=0.8, zorder=1)
        last = d.iloc[-1]
        ax.annotate(
            f"{last.att:+.1f}",
            (last.e, last.att),
            xytext=(8, 0),
            va="center",
            textcoords="offset points",
            ha="left",
            color=t.ink,
            fontweight="bold",
        )
        axes(ax, t)
        p = sw[b]["pretrend_wald"]["p"]
        ax.set_title(b, loc="left", fontweight="bold", pad=16)
        ax.text(
            0,
            1.02,
            f"pre-payment trend test p = {p:.2f}"
            if p >= 0.01
            else "pre-payment trend test p < 0.01",
            transform=ax.transAxes,
            color=t.ink2,
            fontsize=plt.rcParams["font.size"] * 0.82,
        )
        ax.set_xlim(-4.5, 4.6)
        ax.set_xticks(range(-4, 4))
        ax.text(
            -0.3,
            10.4,
            "first payment",
            color=t.muted,
            ha="left",
            fontsize=plt.rcParams["font.size"] * 0.8,
        )
    axs[0].yaxis.set_major_locator(plt.MultipleLocator(4))
    axs[0].yaxis.set_major_formatter(_pp)
    axs[0].set_ylim(-9, 11)
    heading(
        fig,
        t,
        "After a company's first payment, its brand gains share of the doctor's GLP-1 prescribing",
        "Change in the paid brand's share of the physician's GLP-1 "
        "claims, percentage points, vs the year before the first payment",
    )
    fr = {b: sw[b]["own_share_fractional_matched"] for b in ("Trulicity", "Ozempic", "Mounjaro")}
    clear = [b for b, r in fr.items() if r["att"] - 1.96 * r["se"] > 0]
    full = (
        "Physicians already prescribing GLP-1s. Callaway–Sant'Anna doubly robust estimator, "
        "not-yet-paid comparison physicians with similar diabetes workload, volume, specialty and "
        "region; bands: 95% CIs clustered by practice. Mounjaro measured from its 2022 launch. "
        "Victoza's payments came as its maker moved patients to Ozempic. In the pre-registered "
        "log-odds form (matched), the gains are similar ("
        + ", ".join(f"{fr[b]['att'] * 100:+.1f}" for b in fr)
        + f" pp) but only {' and '.join(clear) or 'none'} clears zero. "
        "Companies also call on doctors when a brand gains formulary position. Shown from 4 "
        f"years before payment; every year is in report/qa. {NOT_CAUSAL}\n"
        f"Source: {SRC_OP}; {SRC_PD}, 2013–2024."
    )
    fh = footnote(
        fig, t, _note(social, full, f"Bands: 95% CIs. {NOT_CAUSAL} Source: {SRC_OP}; {SRC_PD}.")
    )
    _xlabel(fig, t, fh)
    fig.subplots_adjust(left=0.07, right=0.975, top=0.77, bottom=fh + 0.13, wspace=0.12)
    alt = (
        "Four small line charts, one per brand, of the change in the paid brand's share of a "
        "physician's GLP-1 prescriptions from four years before to three years after the first "
        "payment. Before payment the lines stay near zero. After it, the share rises by "
        + ", ".join(
            f"{b} {_events(_j(f'es/switching_{b}.json')['own_event'], lo=-4).att.iloc[-1]:+.1f}"
            for b in HERO[:3]
        )
        + " percentage points by the last year shown, while Victoza's share falls "
        f"({_events(_j('es/switching_Victoza.json')['own_event']).att.iloc[-1]:+.1f})."
    )
    return fig, alt


# ------------------------------------------------- chart 1b: the paid brand vs statins


def targeting(t, social=False):
    fig, axs = plt.subplots(1, 3, figsize=_size(social), sharey=True)
    for ax, b in zip(axs, PRIMARY, strict=True):
        br = _events(_j(f"es/panel_universal_{b}.json")["event"])
        st = _events(_j(f"es/falsification_{b}.json")["statin_binary"]["event"])
        c = t.brand(b)
        for d, col, hollow in ((st, t.ink2, True), (br, c, False)):
            ax.fill_between(
                d.e, d.att - 1.96 * d.se, d.att + 1.96 * d.se, color=col, alpha=0.12, lw=0
            )
            ax.plot(d.e, d.att, color=col, zorder=3)
            dot(ax, d.e, d.att, col, t, hollow=hollow)
        ax.axhline(0, color=t.axis, lw=0.9, zorder=1)
        ax.axvline(-0.5, color=t.muted, lw=0.8, zorder=1)
        for d, lab in ((br, b), (st, "Statins")):
            ax.annotate(
                f"{lab} {d.att.iloc[-1]:+.0f}",
                (3, d.att.iloc[-1]),
                xytext=(7, 0),
                textcoords="offset points",
                va="center",
                color=t.ink,
                fontsize=plt.rcParams["font.size"] * 0.9,
            )
        axes(ax, t)
        ax.set_title(f"Paid for {b}", loc="left", fontweight="bold")
        ax.set_xlim(-5.5, 5.2)
        ax.set_xticks(range(-5, 4))
    axs[0].yaxis.set_major_formatter(_pp)
    heading(
        fig,
        t,
        "Paid physicians' statin prescribing rose too, before and after the first "
        "payment: a sign of growing practices",
        "Change in the probability of ≥ 11 Part D "
        "claims in a year, percentage points, vs the year before the first payment",
    )
    full = (
        "Statins (hollow markers) are a negative control: GLP-1 payments should not move them. "
        "That they rise before and after the first payment means the paid physicians' practices "
        "were growing, so this contrast reflects, at least partly, which physicians companies "
        "reach rather than the payment. Brand share (hero chart) cancels practice size out. "
        "Callaway–Sant'Anna "
        "doubly robust, not-yet-paid controls, base year = year before payment; bands: 95% CIs "
        f"clustered by practice. Physicians first paid 2015–2024.\nSource: {SRC_OP}; {SRC_PD}."
    )
    fh = footnote(
        fig,
        t,
        _note(
            social,
            full,
            f"Statins are a negative control. Bands: 95% CIs. Source: {SRC_OP}; {SRC_PD}.",
        ),
    )
    _xlabel(fig, t, fh)
    fig.subplots_adjust(left=0.07, right=0.93, top=0.8, bottom=fh + 0.13, wspace=0.32)
    f = {b: _j(f"es/falsification_{b}.json")["statin_binary"]["att"] * 100 for b in PRIMARY}
    alt = (
        "Three line charts, one per brand (Trulicity, Victoza, Ozempic), each with two lines: "
        "the change in the probability that a paid physician writes at least 11 claims of the "
        "paid brand, and the same for statins, a drug class unrelated to the payments. Both "
        "lines climb steadily before the first payment and keep rising after it. Averaged over "
        "years 0 to 3, statins rise "
        + ", ".join(f"{v:+.1f}" for v in f.values())
        + " percentage points, so the brand increase reflects growing practices at least in part."
    )
    return fig, alt


# ------------------------------------------------------------ chart 2: dose and contacts


def dose(t, social=False):
    d = pd.read_csv(QA / "dose_response.csv")
    fig, axs = plt.subplots(1, 3, figsize=_size(social), sharey=True)
    for ax, b in zip(axs, PRIMARY, strict=True):
        c = t.brand(b)
        x0, ticks, labels = 0, [], []
        for fam, name in (("dose_g", "First-year $"), ("contacts_g", "First-year contacts")):
            g = d[(d.brand == b) & (d.family == fam)].reset_index(drop=True)
            xs = x0 + np.arange(len(g))
            for x, r in zip(xs, g.itertuples(), strict=True):
                ax.plot([x, x], [r.lo * 100, r.hi * 100], color=c, lw=1.4, zorder=2)
                dot(ax, x, r.att * 100, c, t, size=34)
                dot(ax, x + 0.28, r.matched_att * 100, c, t, size=30, hollow=True)
                ticks.append(x + 0.14)
                n = f"{r.treated / 1000:.1f}K" if r.treated >= 1000 else f"{r.treated}"
                labels.append(f"{r.group.replace(' contacts', '').replace(' contact', '')}\nn {n}")
            ax.text(
                xs.mean() + 0.14,
                -0.24,
                name,
                transform=ax.get_xaxis_transform(),
                ha="center",
                color=t.ink2,
                fontsize=plt.rcParams["font.size"] * 0.88,
            )
            x0 = xs[-1] + 1.8
        axes(ax, t)
        ax.axhline(0, color=t.axis, lw=0.9, zorder=1)
        ax.set_xticks(ticks, labels, fontsize=plt.rcParams["xtick.labelsize"] * 0.85)
        ax.set_title(b, loc="left", fontweight="bold")
        ax.set_xlim(-0.7, x0 - 1.1)
    axs[0].yaxis.set_major_formatter(_pp)
    axs[0].set_ylim(0, 30)
    h = [
        axs[0].scatter([], [], s=34, color=t.ink2, ec=t.surface, lw=1.6),
        axs[0].scatter([], [], s=30, color=t.surface, ec=t.ink2, lw=1.8),
    ]
    fig.legend(
        h,
        ["All not-yet-paid comparison physicians", "Matched comparison physicians"],
        loc="upper left",
        bbox_to_anchor=(0.06, 0.84),
        ncol=2,
        handletextpad=0.3,
    )
    heading(
        fig,
        t,
        "Physicians who got more in their first year rose more, but they were different physicians",
        "Change in the probability of ≥ 11 claims of the paid "
        "brand, percentage points, average of years 0–3 after the first payment",
    )
    full = (
        "Groups by promotional dollars and contacts for the brand in the year of the first "
        "payment; bars: 95% CIs clustered by practice. 91–97% of newly paid physicians got under "
        "$100 that year (mostly sponsored meals). Bigger first-year payments go to physicians who "
        "differ in ways matching cannot fully capture, so this gradient is descriptive, not a "
        f"dose-response. {NOT_CAUSAL}\nSource: {SRC_OP}; {SRC_PD}."
    )
    fh = footnote(
        fig,
        t,
        _note(
            social, full, f"Descriptive gradient, not a dose-response. Source: {SRC_OP}; {SRC_PD}."
        ),
    )
    fig.subplots_adjust(left=0.07, right=0.985, top=0.72, bottom=fh + 0.2, wspace=0.1)
    g = d[d.family == "dose_g"]
    alt = (
        "Three dot charts, one per brand, comparing groups of newly paid physicians by first-year "
        "dollars and by number of contacts. The increase in the probability of at least 11 claims "
        "is larger for physicians who got $100 or more ("
        + "; ".join(
            f"{b}: {g[(g.brand == b)].att.iloc[0] * 100:.1f} vs "
            f"{g[(g.brand == b)].att.iloc[1] * 100:.1f} points"
            for b in PRIMARY
        )
        + ") and for those with more contacts. The note says this reflects who gets paid more."
    )
    return fig, alt


# ------------------------------------------------------------- chart 3: Part D spending


def spending(t, social=False):
    s = pd.read_csv(QA / "eda_partd_glp1_spending.csv")
    s["b"] = s.brand.where(s.brand.isin(BRANDS), "Other")
    p = s.pivot_table(index="year", columns="b", values="cost", aggfunc="sum").fillna(0) / 1e9
    order = [b for b in BRANDS if b in p.columns] + ["Other"]
    fig, ax = plt.subplots(figsize=_size(social))
    bottom = np.zeros(len(p))
    for b in order:
        ax.bar(
            p.index,
            p[b],
            bottom=bottom,
            width=0.72,
            color=t.brand(b),
            ec=t.surface,
            lw=1.2,
            zorder=2,
            label=b,
        )
        bottom += p[b].values
    for y in (p.index.min(), p.index.max()):
        ax.text(
            y,
            bottom[list(p.index).index(y)] + 0.4,
            f"${bottom[list(p.index).index(y)]:.1f}B"
            if bottom[list(p.index).index(y)] >= 1
            else f"${bottom[list(p.index).index(y)]:.2f}B",
            ha="center",
            va="bottom",
            color=t.ink,
            fontweight="bold",
        )
    axes(ax, t)
    ax.yaxis.set_major_formatter(lambda v, _: f"${v:.0f}B")
    ax.set_xticks(p.index)
    ax.legend(
        *[x[::-1] for x in ax.get_legend_handles_labels()],
        loc="upper left",
        handlelength=0.9,
        handleheight=0.9,
    )
    e = _j("eda.json")["chart3"]
    cost = e["partd_glp1_cost_by_year"]
    heading(
        fig,
        t,
        f"Medicare Part D spending on GLP-1 drugs grew from ${cost['2013']:.2f}B "
        f"to ${cost['2024']:.1f}B in 11 years",
        "Part D gross drug cost of diabetes-indicated GLP-1 drugs, by brand, $ billions",
    )
    full = (
        "All Part D prescribers (national totals include claims hidden by CMS suppression). Other: "
        "Byetta, Tanzeum, Adlyxin, Soliqua, Xultophy and the Part D claims for Wegovy. Gross cost "
        "before manufacturer rebates. Part D excludes weight-loss-only use, so this is not obesity "
        f"prescribing.\nSource: {SRC_PD} by Geography and Drug, 2013–2024."
    )
    fh = footnote(fig, t, _note(social, full, f"Gross cost before rebates. Source: {SRC_PD}."))
    fig.subplots_adjust(left=0.07, right=0.985, top=0.82, bottom=fh + 0.07)
    alt = (
        "Stacked column chart of Medicare Part D spending on GLP-1 drugs by brand, 2013 to 2024. "
        f"Total spending rises from ${bottom[0]:.2f} billion to ${bottom[-1]:.1f} billion. "
        f"Ozempic is the largest brand in 2024 ({e['share_ozempic_2024']:.0%}), followed by "
        "Trulicity and Mounjaro."
    )
    return fig, alt


# ----------------------------------------------------- chart 4: payments by brand and type


def payments(t, social=False):
    b = pd.read_csv(QA / "payments_by_brand_year.csv").fillna(0)
    b["fees"] = b.usd_speaker + b.usd_consulting
    b["rest"] = b.usd_food_beverage + b.usd_travel + b.usd_education + b.usd_other_promotional
    fig, axs = plt.subplots(2, 3, figsize=_size(social), sharex=True, sharey=True)
    years = range(2013, 2026)
    for ax, brand in zip(axs.flat, BRANDS, strict=True):
        g = b[b.brand == brand].set_index("year")[["fees", "rest"]].reindex(years, fill_value=0)
        c = t.brand(brand)
        ax.bar(g.index, g.fees / 1e6, width=0.72, color=c, ec=t.surface, lw=1, zorder=2)
        ax.bar(
            g.index,
            g.rest / 1e6,
            bottom=g.fees / 1e6,
            width=0.72,
            color=t.tint(c),
            ec=t.surface,
            lw=1,
            zorder=2,
        )
        axes(ax, t)
        tot = (g.fees + g.rest).sum() / 1e6
        ax.set_title(f"{brand}  ${tot:.0f}M", loc="left", fontweight="bold")
        ax.set_xticks([2013, 2019, 2025])
    for a in axs[:, 0]:
        a.yaxis.set_major_formatter(lambda v, _: f"${v:.0f}M" if v else "0")
    k = t.ink2
    h = [plt.Rectangle((0, 0), 1, 1, fc=k), plt.Rectangle((0, 0), 1, 1, fc=t.tint(k))]
    fig.legend(
        h,
        ["Speaker and consulting fees (darker)", "Meals, travel, education (lighter)"],
        loc="upper left",
        bbox_to_anchor=(0.055, 0.845),
        ncol=2,
        handlelength=0.9,
    )
    sh = _j("eda.json")["chart4"]["glp1_promo_usd_by_type_share"]
    fees = sh["usd_speaker"] + sh["usd_consulting"]
    heading(
        fig,
        t,
        f"Speaker and consulting fees are {fees:.0%} of GLP-1 promotional dollars",
        "Promotional payments naming each brand, $ millions per year",
    )
    full = (
        "Payments naming several products split equally across them; royalties, grants, "
        "acquisitions and other non-promotional payments excluded. Fees go to a few thousand "
        f"speakers; meals reach far more physicians ({sh['usd_food_beverage']:.0%} of dollars). "
        "2025 Lilly meal records drop sharply in November–December (unexplained). Cells with "
        f"fewer than 11 recipients withheld.\nSource: {SRC_OP}, 2013–2025."
    )
    fh = footnote(fig, t, _note(social, full, f"Source: {SRC_OP}, 2013–2025."))
    fig.subplots_adjust(
        left=0.07, right=0.985, top=0.75, bottom=fh + 0.07, hspace=0.42, wspace=0.08
    )
    alt = (
        "Six small stacked column charts of industry payments naming each GLP-1 brand per year, "
        "2013 to 2025, split into speaker and consulting fees and other payments such as meals. "
        f"Fees are {fees:.0%} of all GLP-1 promotional dollars and meals "
        f"{sh['usd_food_beverage']:.0%}. Victoza and Trulicity peak before 2019; Ozempic, "
        "Rybelsus and Mounjaro dominate after."
    )
    return fig, alt


# ---------------------------------------------------------- chart 5: share dumbbells


def dumbbells(t, social=False):
    sw = _j("switching.json")
    fig, ax = plt.subplots(figsize=_size(social))
    rows, y = [], 0
    for b in HERO:
        d = sw[b]["dumbbell"]
        rows += [
            (y, f"{b}: paid", d["paid_pre"], d["paid_post"], t.brand(b)),
            (y - 1, "comparison, not yet paid", d["control_pre"], d["control_post"], t.ink2),
        ]
        y -= 2.7
    for y, _lab, a, z, c in rows:
        ax.plot([a * 100, z * 100], [y, y], color=c, lw=2.2, zorder=2)
        dot(ax, a * 100, y, c, t, size=46, hollow=True)
        dot(ax, z * 100, y, c, t, size=46)
        ax.text(
            z * 100 + (1.6 if z >= a else -1.6),
            y,
            f"{z:.0%}",
            va="center",
            ha="left" if z >= a else "right",
            color=t.ink,
        )
    ax.set_yticks([r[0] for r in rows], [r[1] for r in rows])
    for lab in ax.get_yticklabels():
        if ":" in lab.get_text():
            lab.set_fontweight("bold")
            lab.set_color(t.ink)
    axes(ax, t, grid="x")
    ax.spines["left"].set_visible(False)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.set_xlim(-2, 68)
    h = [
        ax.scatter([], [], s=46, color=t.surface, ec=t.ink2, lw=1.8),
        ax.scatter([], [], s=46, color=t.ink2, ec=t.surface, lw=1.6),
    ]
    fig.legend(
        h,
        ["Year before the first payment", "Two years after"],
        loc="upper left",
        bbox_to_anchor=(0.235, 0.85),
        ncol=2,
    )
    heading(
        fig,
        t,
        "Paid physicians moved more of their GLP-1 prescribing to the paying brand",
        "Brand's share of the physician's GLP-1 claims before and after the first payment, "
        "paid vs matched comparison physicians",
    )
    full = (
        "Physicians prescribing GLP-1s in both years, first-payment cohorts with two follow-up "
        "years; comparison physicians not yet paid by then, matched on prior brand prescribing, "
        "GLP-1 volume and growth, diabetes workload, specialty and state. Mounjaro: share relative "
        "to its launch. Victoza is the exception: its maker was moving patients to Ozempic. "
        f"{NOT_CAUSAL}\nSource: {SRC_OP}; {SRC_PD}."
    )
    fh = footnote(fig, t, _note(social, full, f"{NOT_CAUSAL} Source: {SRC_OP}; {SRC_PD}."))
    fig.subplots_adjust(left=0.24, right=0.97, top=0.76, bottom=fh + 0.07)
    alt = (
        "Dumbbell chart, two rows per brand, of the brand's share of a physician's GLP-1 "
        "prescriptions the year before the first payment and two years after. For Trulicity, "
        "Ozempic and Mounjaro, paid physicians' share rises more than matched comparison "
        "physicians' ("
        + "; ".join(
            f"{b} {sw[b]['dumbbell']['paid_post']:.0%} vs {sw[b]['dumbbell']['control_post']:.0%}"
            for b in HERO[:3]
        )
        + "). Victoza's share falls in both groups, more among paid physicians."
    )
    return fig, alt


# ------------------------------------------------------------------ chart 6: state map


HEX = {
    "AK": (0, 0),
    "ME": (11, 0),
    "VT": (10, 1),
    "NH": (11, 1),
    "WA": (1, 2),
    "ID": (2, 2),
    "MT": (3, 2),
    "ND": (4, 2),
    "MN": (5, 2),
    "IL": (6, 2),
    "WI": (7, 2),
    "MI": (8, 2),
    "NY": (9, 2),
    "RI": (10, 2),
    "MA": (11, 2),
    "OR": (1, 3),
    "NV": (2, 3),
    "WY": (3, 3),
    "SD": (4, 3),
    "IA": (5, 3),
    "IN": (6, 3),
    "OH": (7, 3),
    "PA": (8, 3),
    "NJ": (9, 3),
    "CT": (10, 3),
    "CA": (1, 4),
    "UT": (2, 4),
    "CO": (3, 4),
    "NE": (4, 4),
    "MO": (5, 4),
    "KY": (6, 4),
    "WV": (7, 4),
    "VA": (8, 4),
    "MD": (9, 4),
    "DE": (10, 4),
    "AZ": (2, 5),
    "NM": (3, 5),
    "KS": (4, 5),
    "AR": (5, 5),
    "TN": (6, 5),
    "NC": (7, 5),
    "SC": (8, 5),
    "DC": (9, 5),
    "OK": (4, 6),
    "LA": (5, 6),
    "MS": (6, 6),
    "AL": (7, 6),
    "GA": (8, 6),
    "HI": (0, 7),
    "TX": (4, 7),
    "FL": (9, 7),
}


def _luminance(rgb) -> float:
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def state_map(t, social=False):
    st = pd.read_csv(QA / "eda_state_payments_per_diabetic.csv").set_index("state")
    e = _j("eda.json")["chart6"]
    shown = st[st.shown & st.index.isin(HEX)].usd_per_diabetic
    lo, hi = shown.min(), shown.max()
    cmap = t.cmap()  # low values recede toward the surface in both modes
    fig, ax = plt.subplots(figsize=_size(social))
    ax.set_aspect("equal")
    ax.axis("off")
    for s, (c, r) in HEX.items():
        x, y = c + (0.5 if r % 2 else 0), -r * 0.87
        v = shown.get(s)
        fc = t.masked if v is None else cmap((v - lo) / (hi - lo))
        ax.add_patch(RegularPolygon((x, y), 6, radius=0.56, fc=fc, ec=t.surface, lw=2))
        ink = (
            t.ink
            if v is None
            else ("#ffffff" if _luminance(plt.cm.colors.to_rgb(fc)) < 0.45 else "#0b0b0b")
        )
        ax.text(
            x,
            y + 0.12,
            s,
            ha="center",
            va="center",
            color=ink,
            fontweight="bold",
            fontsize=plt.rcParams["font.size"] * 0.88,
        )
        ax.text(
            x,
            y - 0.18,
            "–" if v is None else f"${v:.2f}",
            ha="center",
            va="center",
            color=ink,
            fontsize=plt.rcParams["font.size"] * 0.72,
        )
    ax.set_xlim(-0.8, 12.4)
    ax.set_ylim(-7 * 0.87 - 0.7, 0.75)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(lo, hi))
    cb = fig.colorbar(
        sm, ax=ax, orientation="horizontal", fraction=0.03, pad=0.01, aspect=45, shrink=0.45
    )
    cb.outline.set_visible(False)
    cb.set_ticks([v for v in (1, 2, 3, 4) if lo <= v <= hi])
    cb.ax.xaxis.set_major_formatter(lambda v, _: f"${v:.0f}")
    cb.ax.tick_params(length=0, colors=t.ink2)
    top = shown.idxmax()
    heading(
        fig,
        t,
        f"GLP-1 promotional payments per Part D enrollee with diabetes ranged from "
        f"${lo:.2f} to ${hi:.2f} across states",
        f"Promotional dollars to prescribers in "
        f"each state, 2024, per Medicare Part D enrollee with diabetes "
        f"(US ${e['usd_per_diabetic_us']:.2f})",
    )
    masked = ", ".join(sorted(set(e["masked_states"]) & set(HEX)))
    full = (
        f"Grey ({masked}): not shown because one prescriber received more than half of the "
        "state's dollars, so the value would describe one person. Payments by the recipient's "
        "Open Payments state. Denominator: Part D enrollees × BRFSS diabetes prevalence, adults "
        f"65+, pooled 3 years. Highest: {top}.\nSource: {SRC_OP}; CMS Medicare Enrollment; "
        "CDC BRFSS."
    )
    fh = footnote(
        fig,
        t,
        _note(
            social,
            full,
            f"Grey: withheld ({masked}), one prescriber > half the state's $. Source: {SRC_OP}.",
        ),
    )
    fig.subplots_adjust(left=0.02, right=0.98, top=0.84, bottom=fh + 0.06)
    alt = (
        "Hexagon tile map of US states shaded by GLP-1 promotional payments per Medicare Part D "
        f"enrollee with diabetes in 2024. Values range from ${lo:.2f} ({shown.idxmin()}) to "
        f"${hi:.2f} ({top}); the US figure is ${e['usd_per_diabetic_us']:.2f}. Higher values "
        f"cluster in the South and mid-Atlantic. {masked} are grey: withheld because one "
        "prescriber received most of the state's dollars."
    )
    return fig, alt


# ------------------------------------------------------------------- chart 7: Lorenz


def lorenz(t, social=False):
    lz = pd.read_csv(QA / "eda_lorenz_curve.csv")
    s = _j("eda.json")["chart7"]
    w = (_size(social)[1] * 1.05, _size(social)[1]) if not social else _size(social)
    fig, ax = plt.subplots(figsize=(max(w[0], 7.6), w[1]))
    ax.plot([0, 1], [0, 1], color=t.axis, lw=1, zorder=1)
    ax.fill_between(lz.share_prescribers, lz.share_usd, color=t.ink, alpha=0.06, lw=0)
    ax.plot(lz.share_prescribers, lz.share_usd, color=t.ink, zorder=3)
    axes(ax, t, grid="both")
    ax.spines["left"].set_visible(True)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.set_xlabel("Paid prescribers, from least to most paid")
    ax.set_ylabel("Share of GLP-1 promotional dollars")
    for q, lab, k in ((0.99, "Top 1%", "top1_share"), (0.9, "Top 10%", "top10_share")):
        y = float(np.interp(q, lz.share_prescribers, lz.share_usd))
        dot(ax, q, y, t.ink, t, size=40)
        ax.annotate(
            f"{lab} received {s[k]:.0%}",
            (q, y),
            xytext=(-14, 22 if q > 0.95 else 40),
            textcoords="offset points",
            ha="right",
            color=t.ink,
            arrowprops={"arrowstyle": "-", "color": t.muted, "lw": 0.8},
        )
    ax.text(
        0.52,
        0.58,
        "equal shares",
        rotation=40,
        color=t.muted,
        ha="center",
        fontsize=plt.rcParams["font.size"] * 0.85,
    )
    heading(
        fig,
        t,
        f"The top 1% of paid prescribers received {s['top1_share']:.0%} of GLP-1 "
        "promotional dollars",
        f"Cumulative share of dollars, {s['npis']:,} prescribers paid for a GLP-1, 2013–2024",
    )
    full = (
        f"Promotional dollars, payments naming several products split equally. Gini "
        f"{s['gini']:.2f}; median paid prescriber received ${s['median_usd']:.0f} over 12 years. "
        f"The top payees are mostly paid speakers.\nSource: {SRC_OP}."
    )
    fh = footnote(fig, t, _note(social, full, f"Source: {SRC_OP}, 2013–2024."))
    fig.subplots_adjust(left=0.12 if not social else 0.09, right=0.96, top=0.8, bottom=fh + 0.12)
    alt = (
        "Lorenz curve of GLP-1 promotional dollars across paid prescribers. The curve hugs the "
        f"bottom axis until the top few percent: the top 1% received {s['top1_share']:.0%} of "
        f"dollars, the top 10% {s['top10_share']:.0%}, and the bottom half "
        f"{s['bottom50_share']:.1%}. Gini coefficient {s['gini']:.2f}."
    )
    return fig, alt


# ------------------------------------------------------- chart 8: payments vs workload


def specialty(t, social=False):
    sp = pd.read_csv(QA / "eda_specialty_payments_vs_load.csv").dropna(subset=["label"])
    sp = sp.sort_values("usd_per_1000_dm_claims")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=_size(social), sharey=True)
    y = np.arange(len(sp))
    for ax, col, fmt, title in (
        (a1, "share_paid", lambda v: f"{v:.0%}", "Share paid for a GLP-1 in 2024"),
        (
            a2,
            "usd_per_1000_dm_claims",
            lambda v: f"${v:,.0f}",
            "GLP-1 promotional $ per 1,000 other diabetes-drug claims",
        ),
    ):
        ax.barh(y, sp[col], height=0.56, color=t.ink2, zorder=2)
        for yi, v in zip(y, sp[col], strict=True):
            ax.text(v, yi, f"  {fmt(v)}", va="center", color=t.ink)
        axes(ax, t, grid=None)
        ax.spines["left"].set_visible(True)
        ax.spines["bottom"].set_visible(False)
        ax.set_title(title, loc="left", fontsize=plt.rcParams["font.size"])
        ax.set_xlim(0, sp[col].max() * 1.3)
        ax.set_xticks([])
    a1.set_yticks(y, sp.label)
    e = sp.set_index("specialty_group").usd_per_1000_dm_claims
    r = e["endocrinology"] / e["primary_care_physician"]
    heading(
        fig,
        t,
        f"Per diabetes claim, endocrinologists receive about {r:.0f} times what "
        "primary-care physicians do",
        "Diabetes prescribers in the analysis sample, 2024",
    )
    full = (
        "Other diabetes-drug claims: metformin, SGLT2, DPP-4, sulfonylurea, TZD and insulin "
        "(observed Part D rows). A specialty with more payments per claim is not evidence that "
        f"its prescribing differs.\nSource: {SRC_OP}; {SRC_PD}."
    )
    fh = footnote(fig, t, _note(social, full, f"Source: {SRC_OP}; {SRC_PD}."))
    fig.subplots_adjust(left=0.17, right=0.97, top=0.8, bottom=fh + 0.04, wspace=0.12)
    alt = (
        "Two horizontal bar charts by specialty for 2024: the share of diabetes prescribers paid "
        "for a GLP-1, and GLP-1 promotional dollars per 1,000 other diabetes-drug claims. "
        f"Endocrinology is highest on both (${e['endocrinology']:,.0f} per 1,000 claims) versus "
        f"${e['primary_care_physician']:,.0f} for primary care."
    )
    return fig, alt


CHARTS = {
    "hero_brand_share": hero,
    "chart1b_targeting_statins": targeting,
    "chart2_dose": dose,
    "chart3_partd_spending": spending,
    "chart4_payments_by_type": payments,
    "chart5_share_dumbbells": dumbbells,
    "chart6_state_map": state_map,
    "chart7_lorenz": lorenz,
    "chart8_specialty": specialty,
}


def render(name: str, draw) -> str:
    OUT.mkdir(parents=True, exist_ok=True)
    SOCIAL.mkdir(parents=True, exist_ok=True)
    alt = ""
    for mode in ("light", "dark"):
        with use(mode) as t:
            fig, alt = draw(t)
            stem = name if mode == "light" else f"{name}_dark"
            fig.savefig(OUT / f"{stem}.png", dpi=200)
            fig.savefig(OUT / f"{stem}.svg", metadata={"Date": None})
            plt.close(fig)
    with use("light", scale=1.25) as t:
        fig, _ = draw(t, social=True)
        fig.savefig(SOCIAL / f"{name}_1200x675.png", dpi=100)
        plt.close(fig)
    return alt


def contact_sheet(names: list[str]) -> None:
    fig, axs = plt.subplots(len(names), 2, figsize=(12, 3.5 * len(names)))
    for row, n in zip(axs, names, strict=True):
        for ax, stem in zip(row, (n, f"{n}_dark"), strict=True):
            ax.imshow(plt.imread(OUT / f"{stem}.png"))
            ax.set_title(stem, fontsize=9, loc="left")
            ax.axis("off")
    fig.tight_layout()
    fig.savefig(OUT / "contact_sheet.png", dpi=80)
    plt.close(fig)


def build() -> dict:
    alt = {name: render(name, draw) for name, draw in CHARTS.items()}
    (OUT / "alt_text.json").write_text(json.dumps(alt, indent=1, ensure_ascii=False))
    md = [
        "# Final figures: alt text",
        "",
        "Light: `<name>.png/.svg`; dark: `<name>_dark.png/.svg`; social crop: "
        "`../social/<name>_1200x675.png`. Generated by `python -m ppg.viz.final`.",
        "",
    ]
    md += [f"## {k}\n\n![{k}]({k}.png)\n\n{v}\n" for k, v in alt.items()]
    (OUT / "README.md").write_text("\n".join(md))
    contact_sheet(list(CHARTS))
    return alt


if __name__ == "__main__":
    for k, v in build().items():
        print(f"{k}: {v}\n")
