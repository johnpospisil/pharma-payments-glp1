"""Part D / Part B CSVs -> Parquet (P04).

Column names are lower-cased; prescriber names, middle initials, street addresses and
city are dropped; counts, costs, percentages and rates become DOUBLE (blank = suppressed
-> NULL, never 0); the NPI becomes BIGINT; suppression flags and text stay as text.
Output: PARQUET_DIR/<partd|partb>/<table>/year=YYYY/part-0.parquet
(spending_by_drug is one wide file with year-suffixed columns).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from ppg import config
from ppg.ingest.op_convert import _connect, _csv_columns, _read_csv, _run_with_progress
from ppg.ingest.partd import planned, task_name
from ppg.progress import Progress

log = logging.getLogger(__name__)

PII = re.compile(r"(last_org_name|first_name|_mi$|_st1$|_st2$|_city$)", re.I)
NUMERIC = re.compile(
    r"(^tot_|_tot_|_cnt$|_pct$|_rate$|_avg_|^bene_avg|_cst|_shr$|_suply$|_clms$|_spndng|"
    r"_dsg_unts|_spnd_|_benes$|_ruca$|chg_avg|^cagr_)",
    re.I,
)
TEXT_EXCEPTIONS = re.compile(r"(sprsn|_flag$|_desc$|_src$)", re.I)


def select_list(cols: list[str]) -> str:
    out = []
    for c in cols:
        if PII.search(c):
            continue
        lc = c.lower()
        if lc.endswith("_npi"):
            expr = f"try_cast(nullif(trim(\"{c}\"), '') AS BIGINT)"
        elif NUMERIC.search(c) and not TEXT_EXCEPTIONS.search(c):
            expr = f"try_cast(replace(nullif(trim(\"{c}\"), ''), ',', '') AS DOUBLE)"
        else:
            expr = f"nullif(trim(\"{c}\"), '')"
        out.append(f'{expr} AS "{lc}"')
    return ", ".join(out)


def out_path(folder: str, table: str, year: str) -> Path:
    base = config.PARQUET_DIR / folder / table
    return base / "all.parquet" if year == "all" else base / f"year={year}" / "part-0.parquet"


def convert_all() -> None:
    files = planned()
    con = _connect()
    with Progress("partd_convert") as p:
        for s, _table, raw in files:
            p.add(task_name(s), total=raw.stat().st_size, unit="B")
        for s, table, raw in files:
            task = task_name(s)
            folder = raw.parent.parent.name
            final = out_path(folder, table, s.year)
            if final.exists():
                if not p.is_done(task):
                    p.finish(task)
                continue
            p.start(task)
            final.parent.mkdir(parents=True, exist_ok=True)
            tmp = final.with_suffix(".parquet.tmp")
            sql = (
                f"COPY (SELECT {select_list(_csv_columns(con, raw))} FROM {_read_csv(raw)}) "
                f"TO '{tmp}' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 500000)"
            )
            _run_with_progress(con, sql, p, task)
            tmp.replace(final)
            p.finish(task)
            n = con.execute(f"SELECT count(*) FROM '{final}'").fetchone()[0]
            log.info("%s: %s rows (%.1f MB)", task, f"{n:,}", final.stat().st_size / 1e6)
    con.close()
