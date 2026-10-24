"""P20 rebuild comparison: report/ from a clean `make all` vs the committed report/.

Files are byte-identical, numerically equal (every number within a relative 1e-6; JSON leaves
and CSV cells), or different (with the largest relative difference and where it is).

    python -m ppg.qa.compare <rebuilt report dir> [<reference report dir>]
        -> report/qa/rebuild_compare.json
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from ppg import config

RTOL = 1e-6
IGNORE_KEYS = {"fit_seconds"}  # run-time metadata
SKIP = {"rebuild_compare.json", "claims.json", "disclosure_audit.json"}


def _leaves(x, path=""):
    if isinstance(x, dict):
        for k, v in x.items():
            yield from _leaves(v, f"{path}/{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from _leaves(v, f"{path}[{i}]")
    else:
        yield path, x


def _rel(a: float, b: float) -> float:
    if a == b or (np.isnan(a) and np.isnan(b)):
        return 0.0
    return abs(a - b) / max(abs(a), abs(b), 1e-12)


def _cmp_json(a: Path, b: Path) -> tuple[float, str]:
    la, lb = dict(_leaves(json.loads(a.read_text()))), dict(_leaves(json.loads(b.read_text())))
    if la.keys() != lb.keys():
        return np.inf, f"keys differ: {sorted(la.keys() ^ lb.keys())[:5]}"
    worst, where = 0.0, ""
    for k, va in la.items():
        if k.rsplit("/", 1)[-1] in IGNORE_KEYS:
            continue
        vb = lb[k]
        num = isinstance(va, (int, float)) and isinstance(vb, (int, float))
        r = _rel(float(va), float(vb)) if num and va is not None else float(va != vb)
        if r > worst:
            worst, where = r, f"{k}: {va} vs {vb}"
    return worst, where


def _cmp_csv(a: Path, b: Path) -> tuple[float, str]:
    da, db = pd.read_csv(a), pd.read_csv(b)
    if da.shape != db.shape or list(da.columns) != list(db.columns):
        return np.inf, f"shape {da.shape} vs {db.shape}"
    worst, where = 0.0, ""
    for c in da.columns:
        xa = pd.to_numeric(da[c], errors="coerce").astype(float)
        xb = pd.to_numeric(db[c], errors="coerce").astype(float)
        if xa.notna().any():
            den = np.maximum(np.maximum(xa.abs(), xb.abs()), 1e-12)
            r = ((xa - xb).abs() / den).where(~(xa.isna() & xb.isna()), 0).fillna(1.0)
        else:
            both_na = da[c].isna() & db[c].isna()
            r = ((da[c].astype(str) != db[c].astype(str)) & ~both_na).astype(float)
        if r.max() > worst:
            i = int(r.values.argmax())
            worst, where = float(r.max()), f"row {i}, {c}: {da[c].iloc[i]} vs {db[c].iloc[i]}"
    return worst, where


def compare(new: Path, ref: Path) -> dict:
    files = sorted({p.relative_to(ref) for p in ref.rglob("*") if p.is_file()} |
                   {p.relative_to(new) for p in new.rglob("*") if p.is_file()})  # fmt: skip
    rows = []
    for f in files:
        if f.name in SKIP:
            continue
        a, b = ref / f, new / f
        if not (a.exists() and b.exists()):
            rows.append({"file": str(f), "status": "only in " + ("rebuild" if b.exists() else
                                                                  "reference")})  # fmt: skip
            continue
        if hashlib.sha256(a.read_bytes()).digest() == hashlib.sha256(b.read_bytes()).digest():
            rows.append({"file": str(f), "status": "identical"})
            continue
        if f.suffix in (".json", ".csv"):
            worst, where = (_cmp_json if f.suffix == ".json" else _cmp_csv)(a, b)
            status = "numerically equal" if worst <= RTOL else "different"
            rows.append({"file": str(f), "status": status, "max_rel_diff": worst, "where": where})
        else:
            rows.append({"file": str(f), "status": "different (binary)"})
    d = pd.DataFrame(rows)
    ok = d.status.isin(["identical", "numerically equal"])
    out = {"rtol": RTOL, "counts": d.status.value_counts().to_dict(),
           "not_equal": d[~ok].to_dict("records")}  # fmt: skip
    (config.QA_DIR / "rebuild_compare.json").write_text(json.dumps(out, indent=1, default=str))
    return out


if __name__ == "__main__":
    new = Path(sys.argv[1])
    ref = Path(sys.argv[2]) if len(sys.argv) > 2 else config.REPORT_DIR
    print(json.dumps(compare(new, ref), indent=1, default=str))
