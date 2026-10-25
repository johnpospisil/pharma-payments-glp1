"""P23 explorer data: specialty x state x brand x year aggregates for the static app in app/.

The universe is the analysis panel (diabetes prescribers, P10), placed each year in the state and
specialty group of their Part D record. For each cell:

    n        prescribers in Part D that year
    tot      their total Part D claims, all drugs (the denominator for brand claims)
    paid     prescribers with a promotional payment naming the brand that year (D16, D22)
    usd      promotional $ naming the brand (multi-drug payments split equally, D8)
    regular  prescribers with >= 11 claims of the brand (always observed, D14)
    claims   the brand's claims in those visible rows (rows of 0-10 claims are hidden)

Groups: five physician specialties with an "All physicians" total, plus nurse practitioners and
physician assistants on their own (outside any total: their payments were not reported before
2021, so a total mixing them in would jump in 2021). "Other GLP-1s" is the diabetes-indicated
GLP-1 brands without their own option (Wegovy, Saxenda and Zepbound excluded, as in the
article). No cross-brand total is published.

Disclosure (CLAUDE.md ethics rule, D37, D45, D47), applied before anything is written:
  1. primary: a count of 1-10 is withheld with the values that depend on it (n -> the whole cell,
     paid -> usd, regular -> claims), as is a count equal to its group's size when the group has
     fewer than 20 prescribers; usd is withheld when one prescriber holds > 50% of it, in every
     state cell (D37) and in national cells with fewer than 50 paid prescribers (D47)
  2. secondary: totals are published (All physicians, United States), so no line of an additive
     table (components + total) may have a lone withheld cell
  3. LP protection (ppg.app.protect, D47): an attacker solving all the line sums at once, with
     counts known to be >= 1 and <= the shown prescriber count, must not pin a withheld count to
     a range narrower than 10, nor prove more than half of a withheld amount; more cells are
     withheld until that holds
Every withheld cell is published with one code (-1), whatever the reason: the reason itself can
point at a person. Nothing at prescriber level is written.

    python -m ppg.app.build        -> app/data/meta.json, app/data/<brand>.json
"""

from __future__ import annotations

import json

import duckdb
import numpy as np
import pandas as pd

from ppg import config
from ppg.app import protect
from ppg.report.vars import claim_vars
from ppg.viz.final import HEX

P = config.PARQUET_DIR / "panel"
OUT = config.REPORT_DIR.parent / "app" / "data"
YEARS = list(range(2013, 2025))
BRANDS = ["Ozempic", "Trulicity", "Mounjaro", "Victoza", "Rybelsus", "Bydureon"]
OTHER = ["Soliqua", "Byetta", "Xultophy", "Tanzeum", "Adlyxin", "liraglutide (generic)"]
NOT_DIABETES = ["Wegovy", "Saxenda", "Zepbound"]
PUBLISHED = [*BRANDS, "Other GLP-1s"]
BRAND_KEYS = [*PUBLISHED, "All GLP-1s"]  # last: every prescriber's cell (internal only)
PHYSICIANS = {
    "primary_care_physician": "Primary care (MD/DO)", "endocrinology": "Endocrinology",
    "cardiology": "Cardiology", "nephrology": "Nephrology", "other_physician": "Other physician",
}  # fmt: skip
NONPHYSICIAN = {
    "nurse_practitioner": "Nurse practitioner",
    "physician_assistant": "Physician assistant",
}
SPECS = {**PHYSICIANS, **NONPHYSICIAN}
SPEC_TOTAL = ("all_physicians", "All physicians")
OP_NONPHYSICIAN_FROM = 2021  # Open Payments covers NPs and PAs from PY2021
STATES = sorted(
    """AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT
    NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY""".split()
)
OTHER_STATE = "Territories and other"
STATE_KEYS = [*STATES, OTHER_STATE, "US"]
US = len(STATE_KEYS) - 1
S_TOTAL = len(SPECS)
# additive lines: along specialties the physicians and their total; along states all + the US
LINES = {1: [*range(len(PHYSICIANS)), S_TOTAL], 2: list(range(len(STATE_KEYS)))}
CODES = {-1: "fewer than 11 prescribers", -2: "one prescriber holds more than half the dollars",
         -3: "withheld so another hidden cell cannot be worked out by subtraction",
         -4: "payments to this group were not reported before 2021",
         -5: "brand not yet in Part D"}  # fmt: skip
PUBLIC_CODES = {-1: "withheld to protect privacy", -4: CODES[-4], -5: CODES[-5]}
ALL_SAME_MAX_N = 20  # a count equal to its group's size is withheld below this size
NATIONAL_DOMINANCE_MAX_PAID = 50  # national cells with fewer paid prescribers get the 50% rule
METRICS = ("n", "tot", "paid", "usd", "regular", "claims")
CELL_LEVEL = ("n", "tot")  # the same for every brand
# values that must be withheld together (a withheld key forces its dependants)
CASCADE = {"n": METRICS, "tot": METRICS, "paid": ("usd",), "regular": ("claims",)}
RESIDUAL_WEIGHT = 0.2  # residual groups are cheaper to withhold as complements
# market events a reader will see in the lines (FDA labels, launches, shortages, generics)
APPROVED = {"Victoza": 2010, "Bydureon": 2012, "Trulicity": 2014, "Ozempic": 2017,
            "Rybelsus": 2019, "Mounjaro": 2022}  # fmt: skip
EVENTS = [
    {"brand": "Victoza", "year": 2017, "label": "Cardiovascular indication (Aug 2017)"},
    {"brand": "Ozempic", "year": 2020, "label": "Cardiovascular indication (Jan 2020)"},
    {"brand": "Trulicity", "year": 2020, "label": "Cardiovascular indication (Feb 2020)"},
    {"brand": "*", "year": 2020, "label": "COVID-19 curbs in-person sales visits"},
    {"brand": "Ozempic", "year": 2022, "label": "Semaglutide shortage (Aug 2022 – Feb 2025)"},
    {"brand": "Mounjaro", "year": 2022, "label": "Launch (May 2022); shortage Dec 2022 – Oct 2024"},
    {"brand": "Trulicity", "year": 2022,
     "label": "Lilly launches Mounjaro; Trulicity supply limited from Dec 2022"},
    {"brand": "Victoza", "year": 2024, "label": "Generic liraglutide (June 2024)"},
]  # fmt: skip


def prescriber_rows(con, year: int) -> pd.DataFrame:
    """One row per panel prescriber x brand key in `year` (internal only; never written)."""
    diabetes = [*BRANDS, *OTHER]
    case = " ".join(f"WHEN '{b}' THEN {i}" for i, b in enumerate(BRANDS))
    st = ", ".join(f"'{s}'" for s in STATES)
    sp = ", ".join(f"'{s}'" for s in SPECS)
    q = f"""
        WITH ny AS (
            SELECT npi, CASE WHEN state IN ({st}) THEN state ELSE '{OTHER_STATE}' END AS state,
                   specialty_group AS spec, coalesce(tot_clms, 0) AS tot
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
    # before 2021 Open Payments covered physicians only: the few NP/PA payments (recorded under
    # another recipient type) are left out, so "not reported" is a true zero
    if year < OP_NONPHYSICIAN_FROM:
        early = d.spec.isin(NONPHYSICIAN)
        d.loc[early, "paid"], d.loc[early, "usd"] = False, 0.0
    # brand-level regular: >= 11 visible claims (visible rows are >= 11 by construction)
    d["regular"] = d.claims >= config.MIN_CELL
    tot = (d.groupby(["npi", "state", "spec", "tot"], as_index=False)
             .agg(claims=("claims", "sum"), paid=("paid", "any"), usd=("usd", "sum")))  # fmt: skip
    tot["b"], tot["regular"] = len(BRAND_KEYS) - 1, tot.claims >= config.MIN_CELL
    d = pd.concat([d.dropna(subset=["b"]), tot], ignore_index=True)
    d["b"] = d.b.astype(int)
    return d


def cells(d: pd.DataFrame) -> tuple[dict, np.ndarray, np.ndarray]:
    """Cube per metric [brand, specialty, state] (specialty total = physicians; state total =
    US); plus the top prescriber's $ per cell (for the dominance rule)."""
    specs = list(SPECS)
    shape = (len(BRAND_KEYS), len(specs) + 1, len(STATE_KEYS))
    d = d.assign(s=d.spec.map(specs.index), t=d.state.map(STATE_KEYS.index), n=1,
                 paid=d.paid.astype(int), regular=d.regular.astype(int))  # fmt: skip
    phys = d.spec.isin(PHYSICIANS)
    cube = {m: np.zeros(shape) for m in METRICS}
    top = np.zeros(shape)
    for s_tot in (False, True):
        for t_tot in (False, True):
            x = d[phys] if s_tot else d
            x = x.assign(s=S_TOTAL if s_tot else x.s, t=US if t_tot else x.t)
            g = x.groupby(["b", "s", "t"]).agg(
                n=("n", "sum"),
                tot=("tot", "sum"),
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
    for m in CELL_LEVEL:  # every brand agrees on the cell's prescribers and volume
        cube[m][:] = cube[m][-1]
    return cube, top, cube["usd"]


def _geo(shape) -> np.ndarray:
    """True for state cells (the last state index is the United States total)."""
    g = np.ones(shape, dtype=bool)
    g[..., US] = False
    return g


def primary(cube: dict, top: np.ndarray, year: int) -> dict:
    """Codes per metric: 0 shown, < 0 withheld (CODES)."""
    code = {m: np.zeros(cube[m].shape, dtype=int) for m in METRICS}
    small = lambda x: (x > 0) & (x < config.MIN_CELL)  # noqa: E731
    code["n"][small(cube["n"])] = -1
    for m in ("paid", "regular"):
        code[m][small(cube[m])] = -1
        # everyone in a small group sharing the attribute discloses each of them (D47)
        every = (cube[m] > 0) & (cube[m] == cube["n"]) & (cube["n"] < ALL_SAME_MAX_N)
        code[m][every] = -1
    usd = cube["usd"]
    # dominance: state cells (D37), and national cells with few paid prescribers (D47)
    scope = _geo(usd.shape) | (cube["paid"] < NATIONAL_DOMINANCE_MAX_PAID)
    code["usd"][(usd > 0) & (top > config.DOMINANCE * usd) & scope] = -2
    code = cascade(code)
    # NP and PA payments before 2021: a published zero, known to everyone (not withheld)
    if year < OP_NONPHYSICIAN_FROM:
        for s, key in enumerate(SPECS):
            if key in NONPHYSICIAN:
                for m in ("paid", "usd"):
                    code[m][:, s] = -4
    return code


def cascade(code: dict) -> dict:
    for k, deps in CASCADE.items():
        hid = code[k] < 0
        for m in deps:
            if m != k:
                fill = hid & (code[m] == 0)
                code[m][fill] = code[k][fill]
    # cell-level values: a cell withheld for one brand is withheld for all
    for m in CELL_LEVEL:
        worst = code[m].min(0, keepdims=True)
        code[m][:] = np.where(code[m] < 0, code[m], np.where(worst < 0, -3, 0))
    for k in CELL_LEVEL:
        hid = code[k] < 0
        for m in CASCADE[k]:
            fill = hid & (code[m] == 0)
            code[m][fill] = code[k][fill]
    return code


def _weights() -> dict[int, np.ndarray]:
    w = {1: np.ones(len(LINES[1]) - 1), 2: np.ones(len(LINES[2]) - 1)}
    w[1][LINES[1].index(list(SPECS).index("other_physician"))] = RESIDUAL_WEIGHT
    w[2][STATE_KEYS.index(OTHER_STATE)] = RESIDUAL_WEIGHT
    return w


def secondary(cube: dict, code: dict, top: np.ndarray, max_iter: int = 50) -> dict:
    """Withhold more cells until no line has a lone withheld cell, and a state line's withheld
    dollars (total shown) are not mostly one prescriber's. Lines with a zero total are skipped:
    every cell in them is already known to be zero."""
    weight = _weights()
    shape = cube["n"].shape
    for _ in range(max_iter):
        changed = False
        for m in METRICS:
            v, c = cube[m], code[m]
            for ax, idx, cells in protect.all_lines(shape, LINES):
                if v[cells[-1]] <= 0:
                    continue
                hid = [c[x] < 0 and c[x] != -4 for x in cells]
                k = sum(hid)
                bad = k == 1
                if m == "usd" and k >= 2 and not hid[-1]:
                    geo = ax == 2 or idx[-1] != US
                    comp = [x for x, h in zip(cells[:-1], hid[:-1], strict=True) if h]
                    s = sum(v[x] for x in comp)
                    bad = geo and s > 0 and max(top[x] for x in comp) > config.DOMINANCE * s
                if not bad:
                    continue
                cand = [(v[x] * weight[ax][j], x) for j, x in enumerate(cells[:-1])
                        if not hid[j] and v[x] > 0]  # fmt: skip
                if cand:
                    c[min(cand)[1]] = -3
                elif not hid[-1]:
                    c[cells[-1]] = -3
                else:
                    continue
                changed = True
        code = cascade(code)
        if not changed:
            return code
    raise RuntimeError("secondary suppression did not converge")


def lp_protect(cube: dict, code: dict, top: np.ndarray, max_iter: int = 60) -> dict:
    """Withhold more cells until the LP audit (ppg.app.protect) cannot pin down any primarily
    withheld value (codes -1, -2) from the published totals (D47)."""
    weight = _weights()
    k = len(PUBLISHED)
    for _ in range(max_iter):
        changed = False
        hid = {m: (code[m] < 0) & (code[m] != -4) for m in METRICS}
        for m in METRICS:
            sensitive = (code[m] == -1) | (code[m] == -2)
            one = m in CELL_LEVEL  # audit one brand slice, withhold in all
            sl = slice(-1, None) if one else slice(0, k)
            sub = {x: a[sl] for x, a in cube.items()}
            subhid = {x: a[sl] for x, a in hid.items()}
            bad = protect.violations(m, sub, subhid, sensitive[sl], LINES)
            touched: set = set()
            for cell in map(tuple, np.argwhere(bad)):
                lines = {(ax, tuple(x for i, x in enumerate(cell) if i != ax)) for ax in LINES}
                if lines & touched:
                    continue
                comp = protect.complement_for(cell, sub[m], subhid[m], LINES, weight)
                if comp is None:
                    comp = protect.fallback_complement(cell, sub[m], subhid[m], LINES, weight)
                if comp is None:
                    continue
                if one:
                    code[m][(slice(None), *comp[1:])] = -3
                else:
                    code[m][comp] = -3
                subhid[m][comp] = True
                touched |= lines
                changed = True
        if not changed:
            return code
        code = secondary(cube, cascade(code), top)
    raise RuntimeError("LP protection did not converge")


def structural(cube: dict, code: dict, year: int, first_partd: dict) -> dict:
    """Display-only code for known zeros before a brand's first Part D year (Ozempic was paid
    for in 2017, before its first Part D year: those values stay)."""
    out = {m: c.copy() for m, c in code.items()}
    for b, key in enumerate(BRANDS):
        if year < first_partd[key]:
            for m in ("paid", "usd", "regular", "claims"):
                out[m][b][(out[m][b] == 0) & (cube[m][b] == 0)] = -5
    return out


def national_claims() -> dict[tuple[str, int], float]:
    """Each brand key's national Part D claims (CMS geography file: includes hidden rows)."""
    d = duckdb.sql(f"""
        SELECT m.brand_family AS fam, g.year, sum(g.tot_clms) AS claims
        FROM read_parquet('{config.PARQUET_DIR}/partd/by_geography_drug/*/*.parquet',
                          hive_partitioning = true) g
        JOIN read_csv('{config.REFERENCE_DIR}/partd_drug_map.csv') m
          ON m.brnd_name = g.brnd_name AND m.gnrc_name = g.gnrc_name
        WHERE g.prscrbr_geo_lvl = 'National' AND m.is_glp1
        GROUP BY ALL""").df()
    d["key"] = np.where(
        d.fam.isin(BRANDS), d.fam, np.where(d.fam.isin(OTHER), "Other GLP-1s", None)
    )
    d = d.dropna(subset=["key"]).groupby(["key", "year"]).claims.sum()
    return {(k, int(y)): float(v) for (k, y), v in d.items()}


def protected_year(y: int, first_partd: dict, national: dict) -> tuple[dict, dict, dict]:
    """One year, disclosure-controlled: published arrays per metric [brand][specialty][state],
    counts of internal codes (report/qa/explorer.json), and the share of each brand's national
    claims that the explorer's visible rows hold."""
    cube, top, _ = cells(prescriber_rows(duckdb.connect(), y))
    code = secondary(cube, primary(cube, top, y), top)
    code = lp_protect(cube, code, top)
    shown = structural(cube, code, y, first_partd)
    out, counts = {}, {}
    k = len(PUBLISHED)
    for m in METRICS:
        # one public code for every withheld cell: the reason itself can point at a person
        pub = np.where((shown[m] >= -3) & (shown[m] < 0), -1, shown[m])
        out[m] = np.where(pub < 0, pub, np.rint(cube[m])).astype(int)[:k]
        for c, n in zip(*np.unique(code[m][:k], return_counts=True), strict=True):
            counts[f"{m}:{CODES.get(int(c), 'shown')}"] = int(n)
    groups = [S_TOTAL, *(list(SPECS).index(s) for s in NONPHYSICIAN)]
    visible = {}
    for b, key in enumerate(PUBLISHED):
        nat = national.get((key, y), 0.0)
        if nat > 0:
            visible[key] = round(100 * sum(cube["claims"][b, s, US] for s in groups) / nat)
    return out, counts, visible


def build(workers: int = 6) -> dict:
    from concurrent.futures import ProcessPoolExecutor

    pdm = pd.read_csv(config.REFERENCE_DIR / "partd_drug_map.csv")
    first_partd = pdm[pdm.brand_family.isin(BRANDS)].groupby("brand_family").first_year.min()
    first_partd = {k: int(v) for k, v in first_partd.items()}
    national = national_claims()
    with ProcessPoolExecutor(workers) as pool:
        years = list(pool.map(protected_year, YEARS, [first_partd] * len(YEARS),
                              [national] * len(YEARS)))  # fmt: skip
    per_brand = {b: {m: [] for m in METRICS} for b in PUBLISHED}
    visible = {b: [] for b in PUBLISHED}
    summary = {"cells_by_code": {}, "years": YEARS}
    for out, counts, vis in years:
        for m in METRICS:
            for b, key in enumerate(PUBLISHED):
                per_brand[key][m].append(out[m][b].tolist())
        for key in PUBLISHED:
            visible[key].append(vis.get(key))
        for k, n in counts.items():
            summary["cells_by_code"][k] = summary["cells_by_code"].get(k, 0) + n
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.json"):
        f.unlink()
    files = {}
    for key in PUBLISHED:
        slug = key.lower().replace(" ", "-")
        (OUT / f"{slug}.json").write_text(json.dumps(
            {"brand": key, "layout": "[metric][year][specialty][state]",
             **per_brand[key]}, separators=(",", ":")))  # fmt: skip
        files[key] = f"{slug}.json"
    cv = claim_vars()
    meta = {
        "years": YEARS,
        "brands": [{"key": k, "file": files[k], "approved": APPROVED.get(k),
                    "first_partd": first_partd.get(k), "visible_pct": visible[k]}
                   for k in PUBLISHED],
        "specialties": [{"key": k, "label": v, "physician": k in PHYSICIANS}
                        for k, v in SPECS.items()]
                       + [{"key": SPEC_TOTAL[0], "label": SPEC_TOTAL[1], "physician": True}],
        "states": STATE_KEYS,
        "tiles": {k: list(v) for k, v in HEX.items() if k in STATES},  # chart 6's tile grid
        "codes": {str(k): v for k, v in PUBLIC_CODES.items()},
        "events": EVENTS,
        "other_brands": OTHER, "excluded_brands": NOT_DIABETES,
        "min_cell": config.MIN_CELL, "dominance": config.DOMINANCE,
        "op_nonphysician_from": OP_NONPHYSICIAN_FROM,
        # caveat numbers, from the same claims registry as the article (D38, W1)
        "caveat": {k: cv[k] for k in ("att_trulicity", "att_victoza", "att_ozempic",
                                      "statin_trulicity", "statin_victoza", "statin_ozempic")},
    }  # fmt: skip
    (OUT / "meta.json").write_text(json.dumps(meta, indent=1))
    summary["bytes"] = {f.name: f.stat().st_size for f in sorted(OUT.glob("*.json"))}
    (config.QA_DIR / "explorer.json").write_text(json.dumps(summary, indent=1))
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=1))
