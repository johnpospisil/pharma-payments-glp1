"""Open Payments ingest (P03): download program-year zips, convert to harmonised Parquet.

    python -m ppg.ingest.open_payments download   # zips + reference files -> RAW_DIR
    python -m ppg.ingest.open_payments convert    # zips -> PARQUET_DIR/open_payments
    python -m ppg.ingest.open_payments all

Progress: `make progress` (job "open_payments").
"""

from __future__ import annotations

import logging
import sys

from ppg import config
from ppg.ingest import download, sources
from ppg.progress import Progress

log = logging.getLogger(__name__)

RAW = config.RAW_DIR / "open_payments"
YEARS = range(2013, 2026)


def zip_sources() -> dict[int, sources.Source]:
    return {int(s.year): s for s in sources.load("open_payments", "Program year bundle")}


def download_all() -> None:
    zips = zip_sources()
    others = [s for s in sources.load("open_payments") if s.year == "all"]
    with Progress("op_download") as p:
        sizes = {}
        for y, s in zips.items():
            dest = RAW / s.filename
            sizes[y] = dest.stat().st_size if dest.exists() else download.remote_size(s.url)
            p.add(f"PY{y} zip", total=sizes[y], unit="B")
        for y, s in sorted(zips.items()):
            task = f"PY{y} zip"
            if not p.is_done(task):
                download.fetch(s.url, RAW / s.filename, "open_payments", progress=p, task=task)
                p.finish(task)
        for s in others:
            download.fetch(s.url, RAW / s.filename, "open_payments")


def main(argv: list[str]) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S"
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    stage = argv[0] if argv else "all"
    if stage in ("download", "all"):
        download_all()
    if stage in ("convert", "all"):
        from ppg.ingest.op_convert import convert_all

        convert_all()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
