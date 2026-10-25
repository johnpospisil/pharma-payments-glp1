"""P20 disclosure audit of everything that goes public with the repo (CLAUDE.md ethics rule).

Checks, each pass/fail with details:
  1. no real NPI appears in any git-tracked text file (10-digit tokens matched against every NPI
     in Part D and Open Payments)
  2. no public CSV has an identifier column (npi, names, profile IDs)
  3. prescriber counts in public tables are 0 or >= 11 (CSV columns and JSON count keys)
  4. geography cells shown pass the dominance rule (recomputed from the parquet)
  5. the masked chart-6 states cannot be recovered as one person's dollars by subtraction
  6. the P23 explorer JSON (app/data): counts 0 or >= 11, no withheld cell is the only unknown in
     an additive line, and shown state dollars pass the dominance rule (recomputed)

    python -m ppg.qa.disclosure        -> report/qa/disclosure_audit.json
"""

from __future__ import annotations

import json
import re
import subprocess

import duckdb
import pandas as pd

from ppg import config

P = config.PARQUET_DIR
ROOT = config.REPORT_DIR.parent
TOKEN = re.compile(rb"(?<![\d.])[12]\d{9}(?![\d.])")
ID_COLUMNS = re.compile(
    r"^(npi|npi_linked|prscrbr_npi|covered_recipient_npi|physician_npi|.*first_name|.*last_name"
    r"|.*profile_id|record_id)$", re.I)  # fmt: skip
# (file, count columns): prescriber-derived public tables
COUNT_COLUMNS = {
    "payments_by_brand_year.csv": r"^npis_",
    "payments_cohorts.csv": r"^new_",
    "eda_state_payments_per_diabetic.csv": r"^npis_paid$",
    "eda_specialty_payments_vs_load.csv": r"^prescribers",
    "state_specialty_2024.csv": r"^prescribers$",
    "heterogeneity.csv": r"^treated$",
    "dose_response.csv": r"^treated$",
    "matched_estimates.csv": r"^treated$",
    "sensitivity.csv": r"^treated$",
    "panel_sample_flow.csv": r"^npis",
    "drug_map_glp1_by_brand_year.csv": r"^records$",
    "linkage_specialty_crosstab.csv": r".",
}
# JSON keys that count prescribers (or prescribers in a treated / control group)
JSON_COUNT_KEYS = {
    "treated", "treated_matched", "matched_treated", "controls_matched", "controls_never",
    "treated_physicians", "treated_eligible", "npis", "prescribers", "distinct_npis",
    "glp1_paid_npis", "n_units",
}  # fmt: skip
# Part D's own published national prescriber counts (CMS geography file), not our cells
CMS_PUBLISHED = {"partd_glp1_brands.csv"}


def tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    return out.stdout.split()


def npi_universe() -> set[int]:
    s = duckdb.sql(f"""
        SELECT DISTINCT prscrbr_npi AS npi FROM read_parquet('{P}/partd/by_provider/*/*.parquet')
        UNION SELECT DISTINCT npi FROM '{P}/payments/npi_class_year.parquet'
        UNION SELECT DISTINCT npi FROM '{P}/linkage/profile_npi.parquet'""").df()
    return set(s.npi.dropna().astype("int64"))


def check_npis(files: list[str]) -> dict:
    real = npi_universe()
    hits = []
    for f in files:
        if f.endswith((".png", ".jpg", ".pdf", ".parquet", ".zip")):
            continue
        b = (ROOT / f).read_bytes()
        found = {int(t) for t in TOKEN.findall(b)} & real
        hits += [{"file": f, "count": len(found)}] if found else []
    return {"pass": not hits, "npis_checked": len(real), "files_scanned": len(files),
            "files_with_real_npis": hits}  # fmt: skip


def check_columns(files: list[str]) -> dict:
    bad = []
    for f in files:
        if f.endswith(".csv") and not f.startswith("tests/fixtures/"):
            cols = pd.read_csv(ROOT / f, nrows=0).columns
            bad += [{"file": f, "column": c} for c in cols if ID_COLUMNS.match(str(c))]
    return {"pass": not bad, "identifier_columns": bad}


def _small(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and 0 < v < config.MIN_CELL


def _walk(x, path=""):
    if isinstance(x, dict):
        for k, v in x.items():
            yield from _walk(v, f"{path}/{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from _walk(v, f"{path}[{i}]")
    else:
        yield path, x


def check_counts() -> dict:
    qa = config.QA_DIR
    bad = []
    for name, pat in COUNT_COLUMNS.items():
        d = pd.read_csv(qa / name)
        for c in [c for c in d.columns if re.search(pat, str(c))]:
            v = pd.to_numeric(d[c], errors="coerce")
            n = int(((v > 0) & (v < config.MIN_CELL)).sum())
            bad += [{"file": name, "column": c, "cells": n}] if n else []
    for f in sorted(qa.rglob("*.json")):
        if f.name == "disclosure_audit.json":
            continue
        for path, v in _walk(json.loads(f.read_text())):
            key = path.rsplit("/", 1)[-1].split("[")[0]
            if (key in JSON_COUNT_KEYS or "/cohort_sizes/" in path) and _small(v):
                bad.append({"file": str(f.relative_to(qa)), "key": path, "value": v})
    return {"pass": not bad, "small_cells": bad, "not_checked_cms_published": sorted(CMS_PUBLISHED)}


def _state_npi_usd(year: int = 2024) -> pd.DataFrame:
    """GLP-1 promotional $ per state x NPI as chart 6 counts it (recipient's OP state)."""
    return duckdb.sql(f"""
        WITH r AS (SELECT DISTINCT b.record_id, b.program_year, b.npi,
                          b.amount_usd * b.brand_slots / b.nprod AS usd, b.brand
                   FROM '{P}/payments/record_brand.parquet' b
                   WHERE b.drug_class IN ('glp1', 'glp1_insulin_combo')
                     AND b.program_year = {year} AND b.promotional AND b.amount_usd > 0)
        SELECT o.recipient_state AS state, r.npi, sum(r.usd) AS usd
        FROM r JOIN read_parquet('{P}/open_payments/general/*/*.parquet',
                                 hive_partitioning = true) o
          ON o.record_id = r.record_id AND o.program_year = r.program_year
        GROUP BY ALL""").df()


def check_geography() -> dict:
    qa = config.QA_DIR
    out: dict = {}
    # chart 6: shown states recomputed from the parquet
    st = pd.read_csv(qa / "eda_state_payments_per_diabetic.csv")
    n = _state_npi_usd()
    g = n.groupby("state").usd.agg(["sum", "max", "size"])
    g["top_share"] = g["max"] / g["sum"]
    shown = st[st.shown].state
    viol = g.loc[g.index.isin(shown) & ((g.top_share > config.DOMINANCE) |
                                         (g["size"] < config.MIN_CELL))]  # fmt: skip
    masked = st[~st.shown].state
    # complementary: the US total is published, so the masked states' combined $ is derivable
    res = n[n.state.isin(masked)]
    res_top = float(res.usd.max() / res.usd.sum()) if len(res) else 0.0
    out["chart6"] = {
        "pass": viol.empty and res_top <= config.DOMINANCE,
        "shown_states_violating": viol.index.tolist(),
        "max_top_share_shown": round(float(g.loc[g.index.isin(shown), "top_share"].max()), 3),
        "masked_states": masked.tolist(),
        "masked_residual_top_share": round(res_top, 3),
        "masked_residual_prescribers": int(res.npi.nunique()),
    }
    # P19 heatmap: shown cells have values; masked ones are blank
    ss = pd.read_csv(qa / "state_specialty_2024.csv")
    vis = ss.masked.isna()
    out["state_specialty"] = {
        "pass": bool(ss.loc[~vis, "usd"].isna().all() and (ss.loc[vis, "prescribers"] >= 11).all()),
        "cells": len(ss), "masked": int((~vis).sum()),
        "masked_by_reason": ss.masked.value_counts().to_dict(),
    }  # fmt: skip
    return out


def check_explorer() -> dict:
    import numpy as np

    from ppg.app import build as ex

    data = ROOT / "app" / "data"
    meta = json.loads((data / "meta.json").read_text())
    cube = {b["key"]: json.loads((data / b["file"]).read_text()) for b in meta["brands"]}
    arr = {m: np.array([cube[k][m] for k in ex.BRAND_KEYS]) for m in ex.METRICS}  # b, y, s, t
    known = {m: np.where(a <= -4, 0, a) for m, a in arr.items()}  # -4 / -5 are known zeros
    small = {m: int(((arr[m] > 0) & (arr[m] < config.MIN_CELL)).sum())
             for m in ("n", "paid", "regular")}  # fmt: skip
    lone = {}
    for m in ex.METRICS:
        for ax in ex.AXES[m]:
            v = np.moveaxis(known[m], ax if ax == 0 else ax + 1, -1)
            k = (v < 0).sum(-1)
            lone[f"{m}/axis{ax}"] = int(((k == 1) & (v[..., -1] != 0)).sum())
    # dominance: recompute each shown state cell's top-prescriber share from the parquet
    con, dom = duckdb.connect(), 0
    for i, y in enumerate(meta["years"]):
        c, top, usd = ex.cells(ex.prescriber_rows(con, y))
        shown = (arr["usd"][:, i] > 0) & ex._geo(usd.shape)
        dom += int((shown & (top > config.DOMINANCE * usd)).sum())
    return {"pass": not any(small.values()) and not any(lone.values()) and dom == 0,
            "small_counts": small, "lone_withheld_in_line": lone,
            "shown_state_usd_over_dominance": dom,
            "bytes": sum(f.stat().st_size for f in data.glob("*.json"))}  # fmt: skip


def audit() -> dict:
    files = tracked()
    res = {
        "npis_in_tracked_files": check_npis(files),
        "identifier_columns": check_columns(files),
        "small_cells": check_counts(),
        "geography": check_geography(),
        "explorer": check_explorer(),
    }
    res["pass"] = all(
        v["pass"] if "pass" in v else all(x["pass"] for x in v.values()) for v in res.values()
    )
    (config.QA_DIR / "disclosure_audit.json").write_text(json.dumps(res, indent=1, default=str))
    return res


if __name__ == "__main__":
    print(json.dumps(audit(), indent=1, default=str))
