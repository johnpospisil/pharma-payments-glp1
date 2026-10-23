"""Read download URLs from data/reference/sources.csv (built in P01)."""

from __future__ import annotations

import csv
from dataclasses import dataclass

from ppg import config

SOURCES_CSV = config.REFERENCE_DIR / "sources.csv"


@dataclass(frozen=True)
class Source:
    source: str
    dataset: str
    year: str
    url: str

    @property
    def filename(self) -> str:
        return self.url.rsplit("/", 1)[1].replace("%20", "_")


def load(source: str | None = None, dataset_prefix: str | None = None) -> list[Source]:
    with SOURCES_CSV.open() as f:
        rows = [Source(r["source"], r["dataset"], r["year"], r["url"]) for r in csv.DictReader(f)]
    if source:
        rows = [r for r in rows if r.source == source]
    if dataset_prefix:
        rows = [r for r in rows if r.dataset.startswith(dataset_prefix)]
    return rows
