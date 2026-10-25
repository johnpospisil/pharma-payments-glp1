"""P23 explorer data: specialty x state x brand x year aggregates for the static app in app/.

The universe is the analysis panel (diabetes prescribers, P10), placed each year in the state and
specialty group of their Part D record. For each cell:

    n        prescribers in Part D that year
    dm       their non-GLP-1 diabetes claims (the denominator for brand claims)
    paid     prescribers with a promotional payment naming the brand that year (D16, D22)
    usd      promotional $ naming the brand (multi-drug payments split equally, D8)
    regular  prescribers with >= 11 claims of the brand (always observed, D14)
    claims   the brand's claims in those observed rows (a lower bound: rows of 0-10 are hidden)

"All GLP-1s" is every diabetes-indicated GLP-1 brand (Wegovy and Zepbound excluded, as in the
article); "Other GLP-1s" is the ones without their own option, so the brand list adds up.

Disclosure (CLAUDE.md ethics rule, D37), applied before anything is written:
  1. primary: a count of 1-10 is withheld with the values that depend on it (n -> the whole cell,
     paid -> usd, regular -> claims); a state cell's usd is withheld when one prescriber holds
     > 50% of it (D37 covers geography; national cells are not geographic, D40)
  2. secondary: totals are published (All specialties, United States, All GLP-1s), so in every
     line of an additive table (components + total) a lone withheld cell could be recovered by
     subtraction; another cell is withheld until each line has none or at least two, and for
     dollars until the withheld cells' combined $ is not > 50% one prescriber
Withheld values are written as negative codes (see CODES); nothing at prescriber level is written.

    python -m ppg.app.build        -> app/data/meta.json, app/data/<brand>.json
"""

from __future__ import annotations

import json

import duckdb
import numpy as np
import pandas as pd

from ppg import config
from ppg.report.vars import claim_vars
from ppg.viz.final import HEX

P = config.PARQUET_DIR / "panel"
OUT = config.REPORT_DIR.parent / "app" / "data"
YEARS = list(range(2013, 2025))
BRANDS = ["Ozempic", "Trulicity", "Mounjaro", "Victoza", "Rybelsus", "Bydureon"]
OTHER = ["Soliqua", "Byetta", "Xultophy", "Tanzeum", "Adlyxin", "liraglutide (generic)"]
NOT_DIABETES = ["Wegovy", "Zepbound"]
BRAND_KEYS = [*BRANDS, "Other GLP-1s", "All GLP-1s"]  # last = the total
SPECS = {
    "primary_care_physician": "Primary care (MD/DO)", "endocrinology": "Endocrinology",
    "cardiology": "Cardiology", "nephrology": "Nephrology", "other_physician": "Other physician",
    "nurse_practitioner": "Nurse practitioner", "physician_assistant": "Physician assistant",
    "other_nonphysician": "Other non-physician",
}  # fmt: skip
NONPHYSICIAN = {"nurse_practitioner", "physician_assistant", "other_nonphysician"}
OP_NONPHYSICIAN_FROM = 2021  # Open Payments covers NPs, PAs and others from PY2021
STATES = sorted(
    """AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT
    NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY""".split()
)
OTHER_STATE = "Territories and other"
CODES = {-1: "fewer than 11 prescribers", -2: "one prescriber holds more than half the dollars",
         -3: "withheld so another hidden cell cannot be worked out by subtraction",
         -4: "payments to this group were not reported before 2021",
         -5: "brand not yet on the market"}  # fmt: skip
METRICS = ("n", "dm", "paid", "usd", "regular", "claims")
# values that must be withheld together (a withheld key forces its dependants)
CASCADE = {"n": METRICS, "dm": METRICS, "paid": ("usd",), "regular": ("claims",)}
# additive axes of each metric: 0 brand, 1 specialty, 2 state (distinct counts don't add by brand)
AXES = {"n": (1, 2), "dm": (1, 2), "paid": (1, 2), "regular": (1, 2),
        "usd": (0, 1, 2), "claims": (0, 1, 2)}  # fmt: skip


def prescriber_rows(con, year: int) -> pd.DataFrame:
    """One row per panel prescriber x brand key in `year` (internal only; never written)."""
    diabetes = [*BRANDS, *OTHER]
    case = " ".join(f"WHEN '{b}' THEN {i}" for i, b in enumerate(BRANDS))
    st = ", ".join(f"'{s}'" for s in STATES)
    sp = ", ".join(f"'{s}'" for s in SPECS)
    q = f"""
        WITH ny AS (
            SELECT npi, CASE WHEN state IN ({st}) THEN state ELSE '{OTHER_STATE}' END AS state,
                   specialty_group AS spec, coalesce(dm_load, 0) AS dm
            FROM '{P}/npi_year.parquet'
            WHERE year = {year} AND specialty_group IN ({sp})
              AND npi IN (SELECT npi FROM '{P}/npi_dims.parquet' WHERE f4_diabetes_prescriber)),
        b AS (
            SELECT npi, coalesce(CASE brand {case} END, {len(BRANDS)}) AS b,
                   sum(CASE WHEN status = 'observed' THEN claims ELSE 0 END) AS claims,
                   max(promo_contacts) > 0 AS paid, sum(usd) AS usd
            FROM '{P}/panel_brand.parquet'
            WHERE year = {year} AND brand IN ({", ".join(f"'{x}'" for x in diabetes)})
            GROUP BY ALL)
        SELECT ny.*, b.b, coalesce(b.claims, 0) AS claims, coalesce(b.paid, false) AS paid,
               coalesce(b.usd, 0) AS usd
        FROM ny LEFT JOIN b USING (npi)
        ORDER BY npi, b"""
    d = con.execute(q).df()
    # before 2021 Open Payments covered physicians only: the few nonphysician payments (recorded
    # under another recipient type) are left out, so "not reported" is a true zero in every total
    if year < OP_NONPHYSICIAN_FROM:
        early = d.spec.isin(NONPHYSICIAN)
        d.loc[early, "paid"], d.loc[early, "usd"] = False, 0.0
    # brand-level regular: >= 11 observed claims (observed rows are >= 11 by construction)
    d["regular"] = d.claims >= config.MIN_CELL
    tot = (d.groupby(["npi", "state", "spec", "dm"], as_index=False)
             .agg(claims=("claims", "sum"), paid=("paid", "any"), usd=("usd", "sum")))  # fmt: skip
    tot["b"], tot["regular"] = len(BRAND_KEYS) - 1, tot.claims >= config.MIN_CELL
    d = pd.concat([d.dropna(subset=["b"]), tot], ignore_index=True)
    d["b"] = d.b.astype(int)
    return d


def cells(d: pd.DataFrame) -> tuple[dict, np.ndarray, np.ndarray]:
    """Cube per metric [brand, specialty, state] with totals last on each axis; plus the top
    prescriber's $ and the $ sum per cell (for the dominance rule)."""
    specs, states = list(SPECS), [*STATES, OTHER_STATE]
    shape = (len(BRAND_KEYS), len(specs) + 1, len(states) + 1)
    d = d.assign(s=d.spec.map(specs.index), t=d.state.map(states.index), n=1,
                 paid=d.paid.astype(int), regular=d.regular.astype(int))  # fmt: skip
    cube = {m: np.zeros(shape) for m in METRICS}
    top = np.zeros(shape)
    for s_tot in (False, True):
        for t_tot in (False, True):
            x = d.assign(s=len(specs) if s_tot else d.s, t=len(states) if t_tot else d.t)
            g = x.groupby(["b", "s", "t"]).agg(
                n=("n", "sum"),
                dm=("dm", "sum"),
                paid=("paid", "sum"),
                usd=("usd", "sum"),
                regular=("regular", "sum"),
                claims=("claims", "sum"),
                top=("usd", "max"),
            )
            idx = tuple(g.index.to_frame().to_numpy().T)
            for m in METRICS:
                cube[m][idx] = g[m].to_numpy()
            top[idx] = g["top"].to_numpy()
    # n and dm do not depend on the brand: take them from the total so every brand agrees
    for m in ("n", "dm"):
        cube[m][:] = cube[m][-1]
    return cube, top, cube["usd"]


def primary(cube: dict, top: np.ndarray, year: int) -> dict:
    """Codes per metric: 0 shown, < 0 withheld (CODES)."""
    code = {m: np.zeros(cube[m].shape, dtype=int) for m in METRICS}
    small = lambda x: (x > 0) & (x < config.MIN_CELL)  # noqa: E731
    code["n"][small(cube["n"])] = -1
    code["paid"][small(cube["paid"])] = -1
    code["regular"][small(cube["regular"])] = -1
    usd = cube["usd"]
    dom = (usd > 0) & (top > config.DOMINANCE * usd) & _geo(usd.shape)
    code["usd"][dom] = -2
    code = cascade(code)
    # nonphysician payments before 2021: a published zero, known to everyone (not withheld)
    if year < OP_NONPHYSICIAN_FROM:
        for s, key in enumerate(SPECS):
            if key in NONPHYSICIAN:
                for m in ("paid", "usd"):
                    code[m][:, s] = -4
    return code


def _geo(shape) -> np.ndarray:
    """True for state cells (the last state index is the United States total)."""
    g = np.ones(shape, dtype=bool)
    g[..., -1] = False
    return g


def cascade(code: dict) -> dict:
    for k, deps in CASCADE.items():
        hid = code[k] < 0
        for m in deps:
            if m != k:
                code[m][hid & (code[m] == 0)] = code[k][hid & (code[m] == 0)]
    return code


def _lines(a: np.ndarray, axis: int) -> np.ndarray:
    """View with `axis` last: each [..., :] is one line, components then the total."""
    return np.moveaxis(a, axis, -1)


# complementary cells are chosen by smallest value x weight: residual categories ("other") are
# cheaper to withhold than named brands, specialties and states
RESIDUAL_WEIGHT = 0.2


def _weights() -> dict[int, np.ndarray]:
    w = {0: np.ones(len(BRAND_KEYS) - 1), 1: np.ones(len(SPECS)), 2: np.ones(len(STATES) + 1)}
    w[0][BRAND_KEYS.index("Other GLP-1s")] = RESIDUAL_WEIGHT
    for k in ("other_physician", "other_nonphysician"):
        w[1][list(SPECS).index(k)] = RESIDUAL_WEIGHT
    w[2][-1] = RESIDUAL_WEIGHT
    return w


def secondary(cube: dict, code: dict, top: np.ndarray, max_iter: int = 50) -> dict:
    """Withhold more cells until no withheld value is the only unknown in any additive line, and
    the withheld dollars in a line are not mostly one prescriber's. A line whose total is zero
    is skipped: every cell in it is already known to be zero."""
    weight = _weights()
    for _ in range(max_iter):
        changed = False
        for m in METRICS:
            for ax in AXES[m]:
                v, c = _lines(cube[m], ax), _lines(code[m], ax)
                hid = (c < 0) & (c != -4)
                k = hid.sum(-1)
                bad = (k == 1) & (v[..., -1] > 0)
                if m == "usd":
                    # several withheld components, total shown: their combined $ is known
                    t = _lines(top, ax)
                    geo = True if ax == 2 else _lines(_geo(top.shape), ax)[..., 0]
                    comp = hid[..., :-1]
                    s = np.where(comp, v[..., :-1], 0).sum(-1)
                    # a prescriber spans brands, so bound their share by the summed tops
                    tops = np.where(comp, t[..., :-1], 0)
                    bound = tops.sum(-1) if ax == 0 else tops.max(-1)
                    bad |= (geo & (k >= 2) & ~hid[..., -1] & (s > 0)
                            & (bound > config.DOMINANCE * s))  # fmt: skip
                for idx in zip(*np.nonzero(bad), strict=True):
                    line_v, line_c = v[idx], c[idx]
                    cand = np.flatnonzero((line_c[:-1] == 0) & (line_v[:-1] > 0))
                    if cand.size:
                        cost = line_v[:-1][cand] * weight[ax][cand]
                        line_c[cand[np.argmin(cost)]] = -3
                    elif line_c[-1] == 0:
                        line_c[-1] = -3
                    else:
                        continue
                    changed = True
        code = cascade(code)
        # n and dm are cell-level: a cell withheld for one brand is withheld for all
        for m in ("n", "dm"):
            worst = code[m].min(0, keepdims=True)
            code[m][:] = np.where(code[m] < 0, code[m], np.where(worst < 0, -3, 0))
        code = cascade(code)
        if not changed:
            return code
    raise RuntimeError("secondary suppression did not converge")


def structural(cube: dict, code: dict, year: int, launch: dict) -> dict:
    """Display-only code for known zeros before a brand's first Part D year (Ozempic was paid
    for in 2017, before its first Part D year: those values stay)."""
    out = {m: c.copy() for m, c in code.items()}
    for b, key in enumerate(BRAND_KEYS[: len(BRANDS)]):
        if year < launch[key]:
            for m in ("paid", "usd", "regular", "claims"):
                out[m][b][(out[m][b] == 0) & (cube[m][b] == 0)] = -5
    return out


def build() -> dict:
    con = duckdb.connect()
    launch = dict(
        con.execute(f"""SELECT brand, min(year) FROM '{P}/panel_brand.parquet'
                                  WHERE status <> 'pre_launch' GROUP BY 1""").fetchall()
    )
    per_brand = {b: {m: [] for m in METRICS} for b in BRAND_KEYS}
    summary = {"cells_by_code": {}, "years": YEARS}
    for y in YEARS:
        cube, top, _ = cells(prescriber_rows(con, y))
        code = secondary(cube, primary(cube, top, y), top)
        shown = structural(cube, code, y, launch)
        for m in METRICS:
            v = np.where(shown[m] < 0, shown[m], np.rint(cube[m])).astype(int)
            for b, key in enumerate(BRAND_KEYS):
                per_brand[key][m].append(v[b].tolist())
        for m in METRICS:
            for c, n in zip(*np.unique(code[m], return_counts=True), strict=True):
                k = f"{m}:{CODES.get(int(c), 'shown')}"
                summary["cells_by_code"][k] = summary["cells_by_code"].get(k, 0) + int(n)
    OUT.mkdir(parents=True, exist_ok=True)
    files = {}
    for key in BRAND_KEYS:
        slug = key.lower().replace(" ", "-")
        (OUT / f"{slug}.json").write_text(json.dumps(
            {"brand": key, "layout": "[metric][year][specialty][state]",
             **per_brand[key]}, separators=(",", ":")))  # fmt: skip
        files[key] = f"{slug}.json"
    cv = claim_vars()
    meta = {
        "years": YEARS,
        "brands": [{"key": k, "file": files[k],
                    "launch": int(launch[k]) if k in launch else None} for k in BRAND_KEYS],
        "specialties": [{"key": k, "label": v, "physician": k not in NONPHYSICIAN}
                        for k, v in SPECS.items()] + [{"key": "all", "label": "All specialties"}],
        "states": [*STATES, OTHER_STATE, "US"],
        "tiles": {k: list(v) for k, v in HEX.items() if k in STATES},  # chart 6's tile grid
        "codes": {str(k): v for k, v in CODES.items()},
        "other_brands": OTHER, "excluded_brands": NOT_DIABETES,
        "min_cell": config.MIN_CELL, "dominance": config.DOMINANCE,
        "op_nonphysician_from": OP_NONPHYSICIAN_FROM,
        # caveat numbers, from the same claims registry as the article (D38, W1)
        "caveat": {k: cv[k] for k in ("att_trulicity", "att_victoza", "att_ozempic",
                                      "statin_trulicity", "statin_victoza", "statin_ozempic",
                                      "share_trulicity", "share_ozempic", "share_mounjaro")},
    }  # fmt: skip
    (OUT / "meta.json").write_text(json.dumps(meta, indent=1))
    summary["bytes"] = {f.name: f.stat().st_size for f in sorted(OUT.glob("*.json"))}
    (config.QA_DIR / "explorer.json").write_text(json.dumps(summary, indent=1))
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=1))
