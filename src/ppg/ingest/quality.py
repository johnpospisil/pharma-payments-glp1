"""Data-quality profile of the converted Open Payments and Part D data (P06).

Each check returns a dict of counts; `tests/test_data_quality.py` asserts on them and
`python -m ppg.ingest.quality` writes report/qa/data_quality.json, the anomaly tables and
the monthly-payments chart (report/figures/p06_monthly_payments_glp1_makers.png).
Nothing here edits the data: anomalies are flagged for the build step (P09/P10).
"""

from __future__ import annotations

import json

import duckdb
import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from ppg import config  # noqa: E402

_P = config.PARQUET_DIR
OP = f"read_parquet('{_P}/open_payments/general/*/*.parquet', hive_partitioning = true)"
PD = f"read_parquet('{_P}/partd/by_provider_drug/*/*.parquet', hive_partitioning = true)"

# GLP-1 makers in Open Payments (manufacturer_name patterns, case-insensitive)
MAKERS = {
    "Novo Nordisk": "novo nordisk",
    "Eli Lilly": "lilly",
    "AstraZeneca": "astrazeneca",
    "Sanofi": "sanofi",
}
# Natures that are not promotion of a product to a prescriber (royalties, buyouts, grants...).
# They hold about half of all dollars but few records; excluded from "promotional" totals.
# Provisional here; the definitive grouping is decided in P09.
NON_PROMOTIONAL = (
    "Royalty or License",
    "Acquisitions",
    "Grant",
    "Current or prospective ownership or investment interest",
    "Space rental or facility fees (teaching hospital only)",
    "Charitable Contribution",
    "Debt forgiveness",
    "Long term medical supply or device loan",
)
SURFACE, INK, MUTED, GRID, SERIES = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#2a78d6"


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("SET enable_progress_bar_print = false")
    con.execute("SET threads = 6")
    con.create_function("npi_luhn_ok", luhn_ok, ["BIGINT"], "BOOLEAN")
    return con


def luhn_ok(npi: int | None) -> bool | None:
    """NPI check digit: Luhn over '80840' + the first 9 digits (CMS NPI standard)."""
    if npi is None:
        return None
    s = str(npi)
    if len(s) != 10 or s[0] not in "12":
        return False
    digits = [int(c) for c in "80840" + s[:9]]
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 0:  # positions doubled, counting from the rightmost payload digit
            d *= 2
            d = d - 9 if d > 9 else d
        total += d
    return (10 - total % 10) % 10 == int(s[9])


def _one(con, sql: str) -> dict:
    r = con.execute(sql).df().iloc[0]
    return {
        k: (None if pd.isna(v) else (int(v) if float(v).is_integer() else float(v)))
        for k, v in r.items()
    }


def op_checks(con) -> dict:
    return _one(
        con,
        f"""
        SELECT count(*)                                                AS records,
               count(*) - count(DISTINCT record_id)                    AS duplicate_record_ids,
               count(*) FILTER (WHERE amount_usd IS NULL)              AS null_amount,
               count(*) FILTER (WHERE amount_usd <= 0)                 AS nonpositive_amount,
               count(*) FILTER (WHERE amount_usd > 1e6)                AS amount_over_1m,
               count(*) FILTER (WHERE payment_date IS NULL)            AS null_payment_date,
               count(*) FILTER (WHERE year(payment_date) <> program_year)
                                                                       AS date_outside_program_year,
               count(*) FILTER (WHERE abs(year(payment_date) - program_year) > 1)
                                                                       AS date_off_by_more_than_1y,
               count(*) FILTER (WHERE disputed)                        AS disputed,
               count(*) FILTER (WHERE delayed_publication)             AS delayed_publication,
               count(*) FILTER (WHERE n_payments IS NULL OR n_payments < 1) AS bad_n_payments,
               count(*) FILTER (WHERE recipient_type NOT ILIKE '%teaching%'
                                AND npi IS NULL AND program_year >= 2015)  AS missing_npi_2015plus,
               count(*) FILTER (WHERE manufacturer_id IS NULL)         AS null_manufacturer_id
        FROM {OP}""",
    )


def op_npi_luhn(con) -> dict:
    return _one(
        con,
        f"""
        WITH n AS (SELECT DISTINCT npi FROM {OP} WHERE npi IS NOT NULL)
        SELECT count(*) AS distinct_npis,
               count(*) FILTER (WHERE NOT npi_luhn_ok(npi)) AS failing_luhn
        FROM n""",
    )


def partd_checks(con) -> dict:
    return _one(
        con,
        f"""
        SELECT count(*)                                                  AS rows,
               count(*) FILTER (WHERE tot_clms < 11)                     AS rows_lt11_claims,
               count(*) FILTER (WHERE tot_clms < 0 OR tot_30day_fills < 0
                                OR tot_day_suply < 0 OR tot_drug_cst < 0) AS rows_negative,
               count(*) FILTER (WHERE tot_30day_fills < tot_clms * 0.99) AS fills_below_claims,
               count(*) FILTER (WHERE tot_benes > tot_clms)              AS benes_above_claims,
               count(*) FILTER (WHERE tot_benes IS NULL)                 AS benes_suppressed,
               count(*) FILTER (WHERE brnd_name IS NULL OR gnrc_name IS NULL)
                                                                         AS missing_drug_name,
               count(*) - count(DISTINCT (year, prscrbr_npi, brnd_name, gnrc_name))
                                                                         AS duplicate_keys
        FROM {PD}""",
    )


def partd_npi_luhn(con) -> dict:
    return _one(
        con,
        f"""
        WITH n AS (SELECT DISTINCT prscrbr_npi AS npi FROM {PD})
        SELECT count(*) AS distinct_npis,
               count(*) FILTER (WHERE NOT npi_luhn_ok(npi)) AS failing_luhn
        FROM n""",
    )


def manufacturer_jumps(con, min_records: int = 20_000, ratio: float = 2.0) -> pd.DataFrame:
    """Manufacturer-years whose record count changed by more than `ratio`x vs the year before."""
    return con.execute(f"""
        WITH m AS (SELECT manufacturer_id, min(manufacturer_name) AS name, program_year,
                          count(*) AS records, sum(amount_usd) AS usd
                   FROM {OP} GROUP BY 1, 3),
             l AS (SELECT *, lag(records) OVER (PARTITION BY manufacturer_id
                                                 ORDER BY program_year) AS prev
                   FROM m)
        SELECT name, manufacturer_id, program_year, prev AS records_prev_year, records,
               round(records / prev, 2) AS ratio, round(usd / 1e6, 2) AS usd_m
        FROM l
        WHERE prev IS NOT NULL AND greatest(records, prev) >= {min_records}
          AND (records / prev > {ratio} OR prev / records > {ratio})
        ORDER BY greatest(records, prev) DESC""").df()


def monthly_makers(con) -> pd.DataFrame:
    cases = " ".join(
        f"WHEN manufacturer_name ILIKE '%{pat}%' THEN '{label}'" for label, pat in MAKERS.items()
    )
    return con.execute(f"""
        SELECT CASE {cases} END AS maker, date_trunc('month', payment_date) AS month,
               count(*) AS records, sum(amount_usd) AS usd,
               sum(amount_usd) FILTER (WHERE nature_of_payment NOT IN {NON_PROMOTIONAL})
                                                                   AS promo_usd
        FROM {OP}
        WHERE ({" OR ".join(f"manufacturer_name ILIKE '%{p}%'" for p in MAKERS.values())})
          AND payment_date >= DATE '2013-08-01' AND payment_date < DATE '2026-01-01'
        GROUP BY ALL ORDER BY 1, 2""").df()


def monthly_gaps(m: pd.DataFrame, drop: float = 0.5) -> pd.DataFrame:
    """Months where a maker's records fall below `drop` x its trailing 6-month median."""
    out = []
    for maker, g in m.groupby("maker"):
        g = g.set_index("month").records.asfreq("MS", fill_value=0)
        base = g.rolling(6, min_periods=3).median().shift(1)
        flag = g[(base > 500) & (g < drop * base)]
        out += [
            {
                "maker": maker,
                "month": d.date().isoformat(),
                "records": int(v),
                "trailing_median": int(base[d]),
            }
            for d, v in flag.items()
        ]
    return pd.DataFrame(out)


def chart(m: pd.DataFrame) -> None:
    makers = list(MAKERS)
    fig, axes = plt.subplots(len(makers), 1, figsize=(10, 9), sharex=True, facecolor=SURFACE)
    events = {
        "2017-12": "Ozempic launch",
        "2019-09": "Rybelsus",
        "2020-03": "COVID",
        "2022-05": "Mounjaro launch",
    }
    for ax, maker in zip(axes, makers, strict=True):
        g = m[m.maker == maker]
        ax.set_facecolor(SURFACE)
        ax.bar(g.month, g.promo_usd / 1e6, width=25, color=SERIES, zorder=2)
        ax.set_title(
            f"{maker}: promotional payments per month ($M)", loc="left", fontsize=10, color=INK
        )
        ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.spines["bottom"].set_color(MUTED)
        ax.tick_params(colors=MUTED, labelsize=8, length=0)
        for d in events:
            ax.axvline(pd.Timestamp(d + "-01"), color=MUTED, lw=0.6, ls=":", zorder=1)
    top = axes[0]
    ymax = top.get_ylim()[1]
    for i, (d, label) in enumerate(events.items()):
        y = ymax * (0.98 if i % 2 == 0 else 0.84)  # alternate heights so labels don't collide
        top.text(pd.Timestamp(d + "-01"), y, f" {label}", fontsize=7.5, color=MUTED, va="top")
    fig.text(
        0.01,
        0.005,
        "All products (not only GLP-1s); excludes royalties, licences, acquisitions, grants, "
        "ownership, space rental, charity, debt forgiveness, device loans.\n"
        "Source: CMS Open Payments, Aug 2013 – Dec 2025.",
        fontsize=7.5,
        color=MUTED,
    )
    fig.tight_layout(rect=(0, 0.035, 1, 1))
    config.FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        config.FIGURE_DIR / "p06_monthly_payments_glp1_makers.png", dpi=160, facecolor=SURFACE
    )


def main() -> int:
    con = connect()
    results = {
        "open_payments": op_checks(con) | {"npi": op_npi_luhn(con)},
        "partd": partd_checks(con) | {"npi": partd_npi_luhn(con)},
    }
    jumps = manufacturer_jumps(con)
    m = monthly_makers(con)
    gaps = monthly_gaps(m)
    config.QA_DIR.mkdir(parents=True, exist_ok=True)
    (config.QA_DIR / "data_quality.json").write_text(json.dumps(results, indent=1))
    jumps.to_csv(config.QA_DIR / "op_manufacturer_jumps.csv", index=False)
    m.to_csv(config.QA_DIR / "op_monthly_glp1_makers.csv", index=False)
    gaps.to_csv(config.QA_DIR / "op_monthly_gaps.csv", index=False)
    chart(m)
    print(json.dumps(results, indent=1))
    print(f"\nmanufacturer-year jumps (>2x, >=20k records): {len(jumps)}")
    print(jumps.head(25).to_string(index=False))
    print("\nmonthly gaps:\n", gaps.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
