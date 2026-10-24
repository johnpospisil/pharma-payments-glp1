"""Project paths and constants.

Paths come from environment variables (or `.env` in the repo root) so nothing
machine-specific is hard-coded in the pipeline. Raw downloads live on the
external drive; working Parquet/DuckDB files live on the internal SSD (see DATA.md).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")


def _path(var: str, default: str | Path) -> Path:
    """Env-var path; relative values are taken from the repo root, not the working directory."""
    p = Path(os.environ.get(var, default)).expanduser()
    return p if p.is_absolute() else REPO_ROOT / p


RAW_DIR = _path("PPG_RAW_DIR", "/Volumes/Drive3/ppg/raw")
DATA_DIR = _path("PPG_DATA_DIR", "data")

PARQUET_DIR = DATA_DIR / "parquet"
PANEL_DIR = DATA_DIR / "panels"
MODEL_DIR = DATA_DIR / "models"
DUCKDB_PATH = DATA_DIR / "ppg.duckdb"

REFERENCE_DIR = _path("PPG_REFERENCE_DIR", "data/reference")
REPORT_DIR = _path("PPG_REPORT_DIR", "report")
FIGURE_DIR = REPORT_DIR / "figures"
QA_DIR = REPORT_DIR / "qa"

# Smallest number of prescribers in any cell shown publicly (matches CMS's < 11 suppression).
MIN_CELL = 11
# Geography cells are also masked if one prescriber holds more than this share of the dollars (D37)
DOMINANCE = 0.5
