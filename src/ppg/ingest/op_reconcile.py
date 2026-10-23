"""Reconcile converted Open Payments Parquet against CMS's published totals (P03).

PY2019-2025: exact check against the June 2026 summary dashboard (tolerance ±0.5%) for
General records and dollars, Research records and dollars, and Ownership records.
PY2013-2018: soft check of all-category record counts against the latest CMS Report to
Congress that covers the year (tolerance ±3%; those reports predate the final archived
republications, and dollar totals were restated by large amounts between reports).

Writes report/qa/op_reconciliation.csv and .json; exits non-zero if any check fails.
"""

from __future__ import annotations

import csv
import json

import duckdb

from ppg import config

OP = config.PARQUET_DIR / "open_payments"
SUMMARY = config.REFERENCE_DIR / "cms_summaries"
DASHBOARD = next(SUMMARY.glob("PBLCTN_DSHBRD_*.csv"), None)
RTC = SUMMARY / "report_to_congress_totals.csv"

TOL_EXACT, TOL_SOFT = 0.005, 0.03
DASH_ROWS = {
    "general_records": "Total Number of all Payment Records - General Payments",
    "general_dollars": "Total Dollar Amount of all Payment Records - General Payments",
    "general_disputed_records": "Total Number of all Payment Records - General Payments - Disputed",
    "research_records": "Total Number of all Payment Records - Research Payments",
    "research_dollars": "Total Dollar Amount of all Payment Records - Research Payments",
    "ownership_records": "Total Number of all Payment Records - Ownership Payments",
}


def ours(con: duckdb.DuckDBPyConnection) -> dict[int, dict[str, float]]:
    out: dict[int, dict[str, float]] = {}
    for y, n, usd, nd in con.execute(
        f"""SELECT program_year, count(*), sum(amount_usd), count(*) FILTER (WHERE disputed)
            FROM read_parquet('{OP}/general/*/*.parquet', hive_partitioning = true)
            GROUP BY 1"""
    ).fetchall():
        out.setdefault(y, {}).update(
            general_records=n, general_dollars=float(usd), general_disputed_records=nd
        )
    for kind in ("research", "ownership"):
        q = f"""SELECT program_year, count(*) {{}}
                FROM read_parquet('{OP}/{kind}/*/*.parquet', hive_partitioning = true,
                                  union_by_name = true)
                GROUP BY 1"""
        extra = (
            ", sum(try_cast(total_amount_of_payment_usdollars AS DOUBLE))"
            if kind == "research"
            else ""
        )
        for row in con.execute(q.format(extra)).fetchall():
            d = out.setdefault(row[0], {})
            d[f"{kind}_records"] = row[1]
            if kind == "research":
                d["research_dollars"] = float(row[2] or 0)
    return out


def published() -> dict[int, dict[str, float]]:
    pub: dict[int, dict[str, float]] = {}
    with DASHBOARD.open() as f:
        rows = {r["Data_Metrics"].strip(): r for r in csv.DictReader(f)}
    for key, label in DASH_ROWS.items():
        for col, val in rows[label].items():
            if col.startswith("PY_"):
                pub.setdefault(int(col[3:]), {})[key] = float(val)
    with RTC.open() as f:
        for r in csv.DictReader(f):
            pub.setdefault(int(r["program_year"]), {})["all_records_rtc"] = float(
                r["total_records_all_categories"]
            )
    return pub


def main() -> int:
    con = duckdb.connect()
    mine, pub = ours(con), published()
    results = []
    for y in sorted(mine):
        m, p = mine[y], pub.get(y, {})
        if "general_records" in p:  # dashboard years
            checks = [(k, m.get(k, 0), p[k], TOL_EXACT) for k in DASH_ROWS if k in p]
        else:
            total = sum(m.get(f"{k}_records", 0) for k in ("general", "research", "ownership"))
            checks = [("all_records_rtc", total, p.get("all_records_rtc"), TOL_SOFT)]
        for metric, got, want, tol in checks:
            diff = None if not want else (got - want) / want
            results.append(
                {
                    "program_year": y,
                    "metric": metric,
                    "ours": round(got, 2),
                    "published": want,
                    "pct_diff": None if diff is None else round(100 * diff, 3),
                    "tolerance_pct": 100 * tol,
                    "pass": diff is not None and abs(diff) <= tol,
                }
            )
    config.QA_DIR.mkdir(parents=True, exist_ok=True)
    with (config.QA_DIR / "op_reconciliation.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0]))
        w.writeheader()
        w.writerows(results)
    (config.QA_DIR / "op_reconciliation.json").write_text(json.dumps(results, indent=1))
    for r in results:
        print(
            f"PY{r['program_year']} {r['metric']:<26} ours {r['ours']:>18,.2f}  "
            f"published {r['published'] or float('nan'):>18,.2f}  diff {r['pct_diff']}%  "
            f"{'PASS' if r['pass'] else 'FAIL'}"
        )
    return 0 if all(r["pass"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
