"""P03 summary: rows, dollars and recipient mix by program year, plus a QA chart.

Writes report/qa/op_by_year.csv and report/figures/p03_op_by_year.png.
"""

from __future__ import annotations

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from ppg import config  # noqa: E402

OP = config.PARQUET_DIR / "open_payments"
SURFACE, INK, MUTED, GRID, SERIES = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#2a78d6"


def by_year(con: duckdb.DuckDBPyConnection):
    return con.execute(
        f"""
        SELECT program_year,
               count(*)                                              AS general_records,
               sum(amount_usd) / 1e9                                 AS general_usd_bn,
               count(*) FILTER (WHERE recipient_type ILIKE '%physician%'
                                AND recipient_type NOT ILIKE '%non-physician%') AS to_physicians,
               count(*) FILTER (WHERE recipient_type ILIKE '%non-physician%') AS to_npp,
               count(*) FILTER (WHERE recipient_type ILIKE '%teaching%')     AS to_teaching_hosp,
               count(*) FILTER (WHERE npi IS NOT NULL)::DOUBLE / count(*)   AS share_with_npi,
               count(*) FILTER (WHERE len(products) > 0)::DOUBLE / count(*) AS share_with_product,
               count(DISTINCT coalesce(npi::VARCHAR, 'p' || profile_id::VARCHAR))
                                                                     AS distinct_recipients
        FROM read_parquet('{OP}/general/*/*.parquet', hive_partitioning = true)
        GROUP BY 1 ORDER BY 1
        """
    ).df()


def chart(df) -> None:
    config.FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8), facecolor=SURFACE)
    panels = [
        ("general_records", "General payment records (millions)", 1e6),
        ("general_usd_bn", "General payments ($ billions)", 1),
    ]
    for ax, (col, title, div) in zip(axes, panels, strict=True):
        ax.set_facecolor(SURFACE)
        ax.bar(df.program_year, df[col] / div, color=SERIES, width=0.7, zorder=2)
        ax.set_title(title, loc="left", color=INK, fontsize=11)
        ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.spines["bottom"].set_color(MUTED)
        ax.tick_params(colors=MUTED, labelsize=9, length=0)
        ax.set_xticks(df.program_year, [f"{y % 100:02d}" for y in df.program_year])
    notes = {2013: "partial\nyear", 2020: "COVID", 2021: "+NPs,\nPAs"}
    for y, label in notes.items():
        v = df.loc[df.program_year == y, "general_records"].iloc[0] / 1e6
        axes[0].text(y, v + 0.3, label, ha="center", va="bottom", fontsize=7.5, color=MUTED)
    fig.text(
        0.01,
        0.01,
        "Source: CMS Open Payments, June 2026 publication and archived "
        "final republications. Program year on x-axis.",
        fontsize=8,
        color=MUTED,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(config.FIGURE_DIR / "p03_op_by_year.png", dpi=160, facecolor=SURFACE)


def main() -> int:
    con = duckdb.connect()
    df = by_year(con)
    config.QA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.QA_DIR / "op_by_year.csv", index=False, float_format="%.4f")
    print(df.to_string(index=False))
    chart(df)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
