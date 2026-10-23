"""Medicare Part D (and Part B by Provider) ingest (P04).

    python -m ppg.ingest.partd download   # CSVs -> RAW_DIR/partd, RAW_DIR/partb
    python -m ppg.ingest.partd convert    # CSVs -> PARQUET_DIR/partd, PARQUET_DIR/partb
    python -m ppg.ingest.partd all

The CSVs are the immutable raw copy (D13). Part B by Provider is fetched here too:
same CMS site, same mechanics; it supplies the 2017+ diabetes caseload (DATA.md §3).
Progress: `make progress` (jobs "partd_download", "partd_convert").
"""

from __future__ import annotations

import logging
import sys

from ppg import config
from ppg.ingest import download, sources
from ppg.progress import Progress

log = logging.getLogger(__name__)

# dataset title in sources.csv -> (raw subfolder, short table name)
DATASETS = {
    "Medicare Part D Prescribers - by Provider and Drug": ("partd", "by_provider_drug"),
    "Medicare Part D Prescribers - by Provider": ("partd", "by_provider"),
    "Medicare Part D Prescribers - by Geography and Drug": ("partd", "by_geography_drug"),
    "Medicare Part D Spending by Drug": ("partd", "spending_by_drug"),
    "Medicare Physician & Other Practitioners - by Provider": ("partb", "by_provider"),
}
UNKNOWN_SIZE_GUESS = 60_000_000  # bytes, for progress weighting of files without Content-Length


def planned() -> list[tuple[sources.Source, str, str]]:
    """(source, table, raw path) for every file, in download order (small tables first)."""
    out = []
    for s in sources.load():
        if s.dataset in DATASETS:
            folder, table = DATASETS[s.dataset]
            out.append((s, table, config.RAW_DIR / folder / table / f"{s.year}.csv"))
    small_first = ["spending_by_drug", "by_geography_drug", "by_provider", "by_provider_drug"]
    out.sort(key=lambda x: (small_first.index(x[1]), DATASETS[x[0].dataset][0], x[0].year))
    return out


def task_name(s: sources.Source) -> str:
    folder, table = DATASETS[s.dataset]
    return f"{folder}/{table} {s.year}"


def download_all() -> None:
    files = planned()
    with Progress("partd_download") as p:
        for s, _table, dest in files:
            size = dest.stat().st_size if dest.exists() else download.remote_size(s.url)
            p.add(task_name(s), total=size or UNKNOWN_SIZE_GUESS, unit="B")
        for s, _table, dest in files:
            task = task_name(s)
            if p.is_done(task):
                continue
            download.fetch(s.url, dest, s.source, progress=p, task=task)
            p.state["tasks"][task]["total"] = dest.stat().st_size
            p.finish(task)


def main(argv: list[str]) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S"
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    stage = argv[0] if argv else "all"
    if stage in ("download", "all"):
        download_all()
    if stage in ("convert", "all"):
        from ppg.ingest.partd_convert import convert_all

        convert_all()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
