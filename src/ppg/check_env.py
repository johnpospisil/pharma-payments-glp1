"""`make check-env`: confirm the raw drive is mounted, there is room to work, and tools exist."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import duckdb

from ppg import config

# Raw downloads (~150 GB) go on the external drive; Parquet (~25 GB) on the SSD.
MIN_FREE_GB = {"Raw disk": 200, "Data disk": 50}


def _tool_version(cmd: list[str]) -> str | None:
    """First line of `cmd`'s output, or None if the tool is missing or won't run."""
    if shutil.which(cmd[0]) is None:
        return None
    out = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if out.returncode != 0:
        return None
    return out.stdout.strip().splitlines()[0]


def _raw_volume_mounted(path: Path) -> bool:
    """True if `path` is not on an external volume, or that volume is mounted."""
    parts = path.parts
    if len(parts) >= 3 and parts[1] == "Volumes":
        return os.path.ismount(Path(*parts[:3]))
    return True


def main(require_raw: bool = True) -> int:
    problems: list[str] = []
    warnings: list[str] = []  # tools needed later (R for P13 cross-checks, Quarto for P22)

    print(f"Python      {sys.version.split()[0]}")
    print(f"DuckDB      {duckdb.__version__}")
    for label, cmd in (("R", ["R", "--version"]), ("Quarto", ["quarto", "--version"])):
        version = _tool_version(cmd)
        print(f"{label:<11} {version or 'NOT FOUND / NOT RUNNABLE'}")
        if version is None:
            warnings.append(f"{label} not found or won't run")
    print(f"Raw dir     {config.RAW_DIR}")
    print(f"Data dir    {config.DATA_DIR}")

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    disks = [("Data disk", config.DATA_DIR)]
    if _raw_volume_mounted(config.RAW_DIR):
        config.RAW_DIR.mkdir(parents=True, exist_ok=True)
        disks.insert(0, ("Raw disk", config.RAW_DIR))
    else:
        msg = f"raw dir {config.RAW_DIR} not reachable (is Drive3 mounted?)"
        print(f"\n{msg}")
        if require_raw:
            problems.append(msg)

    for label, path in disks:
        free_gb = shutil.disk_usage(path).free / 1e9
        print(f"{label:<11} {free_gb:,.0f} GB free")
        if free_gb < MIN_FREE_GB[label]:
            problems.append(f"{label.lower()} has under {MIN_FREE_GB[label]} GB free")

    if warnings:
        print("\nWARNINGS:\n  - " + "\n  - ".join(warnings))
    if problems:
        print("\nPROBLEMS:\n  - " + "\n  - ".join(problems))
        return 1
    print("\nOK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(require_raw="--no-raw" not in sys.argv))
