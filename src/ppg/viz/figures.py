"""Descriptive charts (P11): charts 3, 4, 6, 7 and payments vs diabetes load by specialty.

Descriptive only (CLAUDE.md rule 6): nothing here compares paid and unpaid prescribers'
prescribing after payment. Every chart is an aggregate with >= 11 prescribers per cell.
Each figure is written as PNG + SVG to report/figures/ and its data to report/qa/eda_*.csv;
headline numbers go to report/qa/eda.json.

    python -m ppg.viz.figures

Palette: the dataviz reference categorical order (validated with
scripts/validate_palette.js: adjacent CVD dE >= 9.1, normal-vision >= 19.6; three slots are
under 3:1 contrast, so series are direct-labelled and every chart has a CSV table). P21
replaces this with the final light/dark theme.
"""

from __future__ import annotations

import json
import textwrap

import duckdb
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from ppg import config  # noqa: E402

SURFACE, INK, INK2, MUTED, GRID, AXIS = (
    "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7",
)  # fmt: skip
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"]
OTHER = "#c3c2b7"
SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
# colour follows the brand everywhere (never its rank)
BRAND_COLOR = dict(zip(["Ozempic", "Trulicity", "Mounjaro", "Victoza", "Rybelsus", "Bydureon"],
                       CATEGORICAL, strict=False))  # fmt: skip
NATURES = [("usd_speaker", "Speaker / faculty fees"), ("usd_food_beverage", "Meals"),
           ("usd_travel", "Travel and lodging"), ("usd_consulting", "Consulting"),
           ("usd_other", "Education and other")]  # fmt: skip
SOURCE_PD = "Source: CMS Medicare Part D Prescribers by Geography and Drug."
SOURCE_OP = "Source: CMS Open Payments (General Payments), linked to NPIs."
P = config.PARQUET_DIR
GLP1 = "('glp1', 'glp1_insulin_combo')"
MIN_CELL = config.MIN_CELL

plt.rcParams.update({
    "font.family": "sans-serif", "font.size": 9, "axes.edgecolor": AXIS,
    "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.titlecolor": INK, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "svg.fonttype": "none", "text.parse_math": False,  # "$" is currency, not mathtext
    "svg.hashsalt": "ppg",  # stable element ids, so rebuilt SVGs are byte-identical
})  # fmt: skip


def _style(ax, grid: str = "y") -> None:
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    if grid:
        ax.grid(axis=grid, color=GRID, lw=0.8, zorder=0)
    ax.tick_params(length=0)
    ax.set_axisbelow(True)


def _save(fig, name: str, note: str) -> None:
    width = int(fig.get_figwidth() * 17)  # characters per line at 7.5 pt
    lines = [textwrap.fill(p, width) for p in note.split("\n")]
    fig.text(0.01, 0.01, "\n".join(lines), fontsize=7.5, color=MUTED, va="bottom")
    config.FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(config.FIGURE_DIR / f"{name}.{ext}", dpi=160, facecolor=SURFACE,
                    metadata={"Date": None} if ext == "svg" else None)  # fmt: skip
    plt.close(fig)


def _csv(df: pd.DataFrame, name: str) -> None:
    config.QA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.QA_DIR / f"eda_{name}.csv", index=False, float_format="%.4f")


def _fold(brand: str) -> str:
    return brand if brand in BRAND_COLOR else "Other GLP-1"


# ---------------------------------------------------------------- chart 3: Part D spending


def spending_by_brand(con) -> pd.DataFrame:
    m = pd.read_csv(config.REFERENCE_DIR / "partd_drug_map.csv")
    con.register("glp1_names", m[m.is_glp1][["brnd_name", "gnrc_name", "brand_family"]])
    return con.execute(f"""
        SELECT g.year, n.brand_family AS brand, sum(g.tot_drug_cst) AS cost,
               sum(g.tot_clms) AS claims, sum(g.tot_30day_fills) AS fills
        FROM read_parquet('{P}/partd/by_geography_drug/*/*.parquet', hive_partitioning = true) g
        JOIN glp1_names n USING (brnd_name, gnrc_name)
        WHERE g.prscrbr_geo_lvl = 'National' GROUP BY 1, 2 ORDER BY 1, 2""").df()


def chart3(df: pd.DataFrame) -> dict:
    d = (
        df.assign(group=df.brand.map(_fold)).pivot_table(
            index="year", columns="group", values="cost", aggfunc="sum", fill_value=0
        )
        / 1e9
    )
    order = [b for b in BRAND_COLOR if b in d] + ["Other GLP-1"]
    d = d[order]
    fig, ax = plt.subplots(figsize=(9, 5.2))
    colors = [BRAND_COLOR.get(b, OTHER) for b in order]
    ax.stackplot(d.index, d.T.values, colors=colors, edgecolor=SURFACE, lw=1.2, zorder=2)
    _style(ax)
    ax.set_xlim(d.index.min(), d.index.max() + 2.2)
    ax.set_xticks(range(d.index.min(), d.index.max() + 1, 2))
    ax.yaxis.set_major_formatter(lambda v, _: f"${v:.0f}B")
    cum = d.cumsum(axis=1).iloc[-1]
    last = d.iloc[-1]
    for b in order:  # direct labels at the right edge for segments big enough to label
        if last[b] > 0.9:
            ax.text(d.index.max() + 0.15, cum[b] - last[b] / 2, f"{b}  ${last[b]:.1f}B",
                    va="center", fontsize=8.5, color=INK)  # fmt: skip
    ax.legend([plt.Rectangle((0, 0), 1, 1, fc=c) for c in colors], order, frameon=False,
              loc="upper left", fontsize=8, ncol=2)  # fmt: skip
    total = d.sum(axis=1)
    ax.set_title(f"Medicare Part D spending on GLP-1 drugs rose from ${total.iloc[0]:.1f}B "
                 f"({d.index.min()}) to ${total.iloc[-1]:.1f}B ({d.index.max()})",
                 loc="left", fontsize=11)  # fmt: skip
    fig.tight_layout(rect=(0, 0.09, 1, 1))
    _save(fig, "chart3_partd_glp1_spending",
          "Gross drug cost before rebates, all prescribers (national totals include suppressed "
          "claims). Other: Byetta, Tanzeum, Adlyxin, Soliqua, Xultophy, Wegovy, Zepbound, "
          f"generic liraglutide.\n{SOURCE_PD}")  # fmt: skip
    return {
        "partd_glp1_cost_by_year": total.round(3).to_dict(),
        "share_ozempic_2024": float(d.loc[d.index.max(), "Ozempic"] / total.iloc[-1]),
    }


# ------------------------------------------------- chart 4: payments by brand and type


def payments_by_brand_type() -> pd.DataFrame:
    b = pd.read_csv(config.QA_DIR / "payments_by_brand_year.csv")
    b["usd_other"] = b.usd_education + b.usd_other_promotional
    return b


def chart4(b: pd.DataFrame) -> dict:
    brands = ["Victoza", "Bydureon", "Trulicity", "Ozempic", "Rybelsus", "Mounjaro", "Wegovy",
              "Zepbound"]  # fmt: skip
    fig, axes = plt.subplots(2, 4, figsize=(11, 5.6), sharex=True, sharey=True)
    colors = dict(zip([n for n, _ in NATURES], CATEGORICAL, strict=False))
    years = range(2013, 2026)
    for ax, brand in zip(axes.flat, brands, strict=True):
        g = (
            b[b.brand == brand]
            .set_index("year")
            .select_dtypes("number")
            .reindex(years, fill_value=0)
        )
        bottom = np.zeros(len(g))
        for col, _label in NATURES:
            v = g[col].values / 1e6
            ax.bar(g.index, v, bottom=bottom, width=0.8, color=colors[col], edgecolor=SURFACE,
                   lw=0.6, zorder=2)  # fmt: skip
            bottom += v
        _style(ax)
        ax.set_title(f"{brand}  (${g.usd_split.sum() / 1e6:.0f}M)", loc="left", fontsize=9.5)
        ax.set_xticks([2014, 2019, 2024])
    axes[0, 0].yaxis.set_major_formatter(lambda v, _: f"${v:.0f}M")
    axes[1, 0].yaxis.set_major_formatter(lambda v, _: f"${v:.0f}M")
    fig.legend([plt.Rectangle((0, 0), 1, 1, fc=colors[c]) for c, _ in NATURES],
               [label for _, label in NATURES], frameon=False, ncol=5, fontsize=8.5,
               loc="upper left", bbox_to_anchor=(0.01, 0.93))  # fmt: skip
    fig.suptitle("Industry payments naming each GLP-1 brand, by type, per year", x=0.01,
                 ha="left", fontsize=11, color=INK)  # fmt: skip
    fig.tight_layout(rect=(0, 0.07, 1, 0.9))
    _save(fig, "chart4_payments_by_brand_type",
          "Promotional payments only (no royalties, grants, acquisitions); payments naming "
          "several products split equally. 2025: Lilly meal payments drop sharply in Nov–Dec "
          f"(unexplained, D18).\n{SOURCE_OP}")  # fmt: skip
    tot = b[[c for c, _ in NATURES]].sum()
    return {"glp1_promo_usd_by_type_share": (tot / tot.sum()).round(4).to_dict()}


# --------------------------------------------- chart 6: hex-tile state map per diabetic


HEX = {  # (column, row) of the standard US tile grid; odd rows shifted half a tile
    "AK": (0, 0), "ME": (11, 0), "VT": (10, 1), "NH": (11, 1), "WA": (1, 2), "ID": (2, 2),
    "MT": (3, 2), "ND": (4, 2), "MN": (5, 2), "IL": (6, 2), "WI": (7, 2), "MI": (8, 2),
    "NY": (9, 2), "RI": (10, 2), "MA": (11, 2), "OR": (1, 3), "NV": (2, 3), "WY": (3, 3),
    "SD": (4, 3), "IA": (5, 3), "IN": (6, 3), "OH": (7, 3), "PA": (8, 3), "NJ": (9, 3),
    "CT": (10, 3), "CA": (1, 4), "UT": (2, 4), "CO": (3, 4), "NE": (4, 4), "MO": (5, 4),
    "KY": (6, 4), "WV": (7, 4), "VA": (8, 4), "MD": (9, 4), "DE": (10, 4), "AZ": (2, 5),
    "NM": (3, 5), "KS": (4, 5), "AR": (5, 5), "TN": (6, 5), "NC": (7, 5), "SC": (8, 5),
    "DC": (9, 5), "OK": (4, 6), "LA": (5, 6), "MS": (6, 6), "AL": (7, 6), "GA": (8, 6),
    "HI": (0, 7), "TX": (4, 7), "FL": (9, 7),
}  # fmt: skip


def state_rates(con, year: int = 2024) -> pd.DataFrame:
    df = con.execute(f"""
        WITH r AS (SELECT DISTINCT b.record_id, b.program_year, b.npi,
                          b.amount_usd * b.brand_slots / b.nprod AS usd, b.brand
                   FROM '{P}/payments/record_brand.parquet' b
                   WHERE b.drug_class IN {GLP1} AND b.program_year = {year}
                     AND b.promotional AND b.amount_usd > 0),
             s AS (SELECT r.*, o.recipient_state AS state
                   FROM r JOIN read_parquet('{P}/open_payments/general/*/*.parquet',
                                            hive_partitioning = true) o
                     ON o.record_id = r.record_id AND o.program_year = r.program_year),
             n AS (SELECT state, npi, sum(usd) AS usd FROM s GROUP BY ALL)
        SELECT state, sum(usd) AS usd, count(DISTINCT npi) AS npis_paid, max(usd) AS max_npi_usd
        FROM n GROUP BY 1""").df()
    den = pd.read_parquet(P / "reference" / "state_diabetic_partd.parquet")
    den = den[den.year == year][["state", "est_diabetic_partd", "partd_enrollees"]]
    df = df.merge(den, on="state", how="inner")
    df["usd_per_diabetic"] = df.usd / df.est_diabetic_partd
    # disclosure control (D37): >= 11 paid prescribers and no one prescriber > 50% of the state's $
    df["top_npi_share"] = df.max_npi_usd / df.usd
    df["masked"] = np.select([df.npis_paid < MIN_CELL, df.top_npi_share > config.DOMINANCE],
                             ["< 11 prescribers", "dominance"], "")  # fmt: skip
    df["shown"] = df.masked == ""
    return df.sort_values("usd_per_diabetic", ascending=False)


def chart6(df: pd.DataFrame, year: int = 2024) -> dict:
    d = df[df.state.isin(HEX) & df.shown].set_index("state")
    masked = set(df[df.state.isin(HEX) & ~df.shown].state)
    cmap = LinearSegmentedColormap.from_list("seq", SEQUENTIAL)
    lo, hi = d.usd_per_diabetic.min(), d.usd_per_diabetic.max()
    fig, ax = plt.subplots(figsize=(9.2, 6.2))
    ax.set_aspect("equal")
    ax.axis("off")
    for st, (c, r) in HEX.items():
        x, y = c + (0.5 if r % 2 else 0), -r * 0.87
        v = d.usd_per_diabetic.get(st)
        t = 0 if v is None else (v - lo) / (hi - lo)
        fc = "#f0efec" if v is None else cmap(t)
        ax.add_patch(matplotlib.patches.RegularPolygon((x, y), 6, radius=0.56, fc=fc,
                                                       ec=SURFACE, lw=1.5))  # fmt: skip
        ink = SURFACE if t > 0.55 else INK
        ax.text(x, y + 0.1, st, ha="center", va="center", fontsize=8.5, color=ink,
                fontweight="bold")  # fmt: skip
        ax.text(x, y - 0.17, "–" if v is None else f"${v:.2f}", ha="center", va="center",
                fontsize=7, color=ink)  # fmt: skip
    ax.set_xlim(-0.8, 12.4)
    ax.set_ylim(-7 * 0.87 - 0.8, 0.8)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(lo, hi))
    cb = fig.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.035, pad=0.02,
                      aspect=40, shrink=0.5)  # fmt: skip
    cb.outline.set_visible(False)
    cb.ax.xaxis.set_major_formatter(lambda v, _: f"${v:.2f}")
    cb.ax.tick_params(length=0, labelsize=8)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.93, bottom=0.12)
    us = df.usd.sum() / df.est_diabetic_partd.sum()
    ax.set_title(f"GLP-1 promotional payments per Medicare Part D enrollee with diabetes, "
                 f"{year} (US ${us:.2f})", loc="left", fontsize=11)  # fmt: skip
    _save(fig, "chart6_state_payments_per_diabetic",
          "Payments by recipient's state; denominator = Part D enrollees × BRFSS diabetes "
          "prevalence, adults 65+ (pooled 3 years).\nGrey: not shown because one prescriber "
          f"received more than half of the state's dollars ({', '.join(sorted(masked))}), so "
          f"the value would describe one person.\n{SOURCE_OP} CMS Medicare Enrollment; "
          "CDC BRFSS.")  # fmt: skip
    top = d.sort_values("usd_per_diabetic", ascending=False)
    return {"usd_per_diabetic_us": us, "masked_states": sorted(masked),
            "top5_states": top.usd_per_diabetic.head(5).round(3).to_dict(),
            "bottom5_states": top.usd_per_diabetic.tail(5).round(3).to_dict(),
            "max_to_min_ratio": float(hi / lo)}  # fmt: skip


# ---------------------------------------------------------- chart 7: Lorenz curve


def lorenz_data(con) -> pd.DataFrame:
    return con.execute(f"""
        SELECT npi, sum(usd_split) AS usd FROM '{P}/payments/npi_class_year.parquet'
        WHERE class_group = 'glp1' AND year <= 2024 GROUP BY 1 HAVING sum(usd_split) > 0""").df()


def _shares(usd: np.ndarray) -> dict:
    v = np.sort(usd)[::-1]
    tot = v.sum()
    n = len(v)
    gini = 1 - 2 * np.sum(np.cumsum(np.sort(usd)) / tot) / n + 1 / n
    return {"npis": int(n), "top1_share": float(v[: max(1, n // 100)].sum() / tot),
            "top10_share": float(v[: max(1, n // 10)].sum() / tot),
            "bottom50_share": float(v[n - n // 2:].sum() / tot), "gini": float(gini),
            "median_usd": float(np.median(v)), "p99_usd": float(np.quantile(v, 0.99))}  # fmt: skip


def chart7(df: pd.DataFrame) -> dict:
    v = np.sort(df.usd.values)
    x = np.concatenate([[0], np.arange(1, len(v) + 1) / len(v)])
    y = np.concatenate([[0], np.cumsum(v) / v.sum()])
    s = _shares(df.usd.values)
    fig, ax = plt.subplots(figsize=(6.4, 6))
    ax.plot([0, 1], [0, 1], color=AXIS, lw=1, ls="--", zorder=1)
    ax.plot(x, y, color=CATEGORICAL[0], lw=2, zorder=3)
    _style(ax, grid="both")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.xaxis.set_major_formatter(lambda t, _: f"{t:.0%}")
    ax.yaxis.set_major_formatter(lambda t, _: f"{t:.0%}")
    ax.set_xlabel("Share of paid prescribers (from least to most paid)")
    ax.set_ylabel("Share of GLP-1 promotional dollars")
    for q, label in ((0.99, "top 1%"), (0.90, "top 10%")):
        yy = np.interp(q, x, y)
        ax.scatter([q], [yy], s=40, color=CATEGORICAL[0], ec=SURFACE, lw=2, zorder=4)
        ax.annotate(f"The {label} received {1 - yy:.0%} of the dollars", (q, yy),
                    xytext=(-12, 12 if q > 0.95 else 34), textcoords="offset points",
                    ha="right", fontsize=8.5, color=INK,
                    arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.7})  # fmt: skip
    ax.text(0.5, 0.56, "equal shares", rotation=42, color=MUTED, fontsize=8, ha="center")
    ax.set_title("GLP-1 payment dollars are highly concentrated", loc="left", fontsize=11)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    _save(fig, "chart7_lorenz_payments",
          f"{s['npis']:,} prescribers paid for a GLP-1, 2013–2024 total; promotional $ "
          f"(split). Gini {s['gini']:.2f}.\n{SOURCE_OP}")  # fmt: skip
    return s


# ------------------------------------- secondary Q3: payments vs diabetes load by specialty


LABELS = {"endocrinology": "Endocrinology", "primary_care_physician": "Primary care (MD/DO)",
          "nurse_practitioner": "Nurse practitioner", "physician_assistant": "Physician assistant",
          "cardiology": "Cardiology", "nephrology": "Nephrology",
          "other_physician": "Other physician"}  # fmt: skip


def specialty_load(con, year: int = 2024) -> pd.DataFrame:
    df = con.execute(f"""
        SELECT y.specialty_group, count(*) AS prescribers,
               count(*) FILTER (WHERE y.glp1_contacts > 0) AS prescribers_paid,
               sum(y.glp1_usd) AS glp1_usd, sum(y.dm_load) AS dm_claims,
               sum(y.clms_glp1) AS glp1_claims
        FROM '{P}/panel/npi_year.parquet' y
        JOIN '{P}/panel/npi_dims.parquet' d USING (npi)
        WHERE y.year = {year} AND d.f1_individual AND d.f2_prescriber_specialty
          AND d.f3_active_years AND d.f4_diabetes_prescriber
        GROUP BY 1""").df()
    df["share_paid"] = df.prescribers_paid / df.prescribers
    df["usd_per_1000_dm_claims"] = df.glp1_usd / df.dm_claims * 1000
    df["usd_per_prescriber"] = df.glp1_usd / df.prescribers
    df["label"] = df.specialty_group.map(LABELS)
    assert (df.prescribers >= MIN_CELL).all()
    return df.sort_values("usd_per_1000_dm_claims")


def chart_specialty(df: pd.DataFrame, year: int = 2024) -> dict:
    df = df[df.label.notna()]  # 'other_nonphysician' that year (a few hundred): CSV only
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4.4), sharey=True)
    y = np.arange(len(df))
    for ax, col, fmt, title in (
        (a1, "share_paid", lambda v: f"{v:.0%}", "Share paid for a GLP-1 that year"),
        (a2, "usd_per_1000_dm_claims", lambda v: f"${v:,.0f}",
         "GLP-1 promotional $ per 1,000 other diabetes-drug claims"),
    ):  # fmt: skip
        ax.barh(y, df[col], color=CATEGORICAL[0], height=0.62, zorder=2)
        for yi, v in zip(y, df[col], strict=True):
            ax.text(v, yi, f"  {fmt(v)}", va="center", fontsize=8.5, color=INK)
        _style(ax, grid="x")
        ax.set_title(title, loc="left", fontsize=9.5)
        ax.set_xlim(0, df[col].max() * 1.25)
        ax.set_xticks([])
    a1.set_yticks(y, df.label)
    fig.suptitle(f"Payments relative to diabetes workload, by specialty, {year}", x=0.01,
                 ha="left", fontsize=11, color=INK)  # fmt: skip
    fig.tight_layout(rect=(0, 0.06, 1, 0.94))
    _save(fig, "chart_specialty_payments_vs_load",
          f"Diabetes prescribers in the analysis sample (P10), {year}. Other diabetes-drug "
          "claims: metformin, SGLT2, DPP-4, sulfonylurea, TZD, insulin (observed rows).\n"
          f"{SOURCE_OP} CMS Part D Prescribers.")  # fmt: skip
    return {r.specialty_group: {"prescribers": int(r.prescribers),
                                "share_paid": round(float(r.share_paid), 4),
                                "usd_per_1000_dm_claims": round(float(r.usd_per_1000_dm_claims), 2),
                                "usd_per_prescriber": round(float(r.usd_per_prescriber), 2)}
            for r in df.itertuples()}  # fmt: skip


def build() -> dict:
    con = duckdb.connect()
    try:
        con.execute("SET enable_progress_bar_print = false")
    except duckdb.InvalidInputException:  # inside Jupyter without ipywidgets
        pass
    out = {}
    sp = spending_by_brand(con)
    _csv(sp, "partd_glp1_spending")
    out["chart3"] = chart3(sp)
    b = payments_by_brand_type()
    out["chart4"] = chart4(b)
    st = state_rates(con)
    pub = st.drop(columns=["max_npi_usd", "top_npi_share"])  # the CSV is public: no top-payee $
    pub.loc[~pub.shown, ["usd", "usd_per_diabetic"]] = np.nan
    pub["npis_paid"] = pub.npis_paid.where(pub.npis_paid >= MIN_CELL)
    _csv(pub, "state_payments_per_diabetic")
    out["chart6"] = chart6(st)
    lz = lorenz_data(con)
    out["chart7"] = chart7(lz)
    y24 = con.execute(f"""SELECT sum(usd_split) AS usd FROM '{P}/payments/npi_class_year.parquet'
                          WHERE class_group = 'glp1' AND year = 2024 GROUP BY npi
                          HAVING sum(usd_split) > 0""").df()  # fmt: skip
    out["concentration_2024"] = _shares(y24.usd.values)
    sl = specialty_load(con)
    _csv(sl, "specialty_payments_vs_load")
    out["specialty_2024"] = chart_specialty(sl)
    (config.QA_DIR / "eda.json").write_text(json.dumps(out, indent=1, default=float))
    return out


if __name__ == "__main__":
    print(json.dumps(build(), indent=1, default=float))
