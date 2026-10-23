"""Reference data (P05): practices, taxonomy, diabetes prevalence, enrollment.

    python -m ppg.ingest.reference           # download + convert all
    python -m ppg.ingest.reference nppes     # retry NPPES only (it was down 2026-10-22/23)

Outputs (PARQUET_DIR/reference/):
  dac.parquet                 NPI -> group practice (org_pac_id, size), specialty, grad year
  nucc_taxonomy.parquet       taxonomy code -> grouping / classification / specialization
  places_county.parquet       CDC PLACES county diabetes / obesity prevalence (2025 release)
  brfss_diabetes_65plus.parquet  state x year % of adults 65+ ever told they have diabetes
  enrollment_state_year.parquet  state x year Medicare / Part D enrollment (annual rows)
  gv_state_county.parquet     Medicare Geographic Variation, state and county rows
"""

from __future__ import annotations

import logging
import re
import sys

from ppg import config
from ppg.ingest import download, sources
from ppg.ingest.op_convert import _connect, _csv_columns, _read_csv
from ppg.progress import Progress

log = logging.getLogger(__name__)

RAW = config.RAW_DIR / "reference"
OUT = config.PARQUET_DIR / "reference"

FILES = {  # short name -> dataset title in sources.csv
    "dac": "Doctors and Clinicians National Downloadable File",
    "nucc_taxonomy": "NUCC Health Care Provider Taxonomy v26.1",
    "places_county": "PLACES: County Data (GIS Friendly Format), 2025 release",
    "brfss_diabetes_65plus": "BRFSS Prevalence Data: diabetes, age 65+, by state",
    "enrollment": "Medicare Monthly Enrollment",
    "gv": "Medicare Geographic Variation - by National, State & County",
}

# DAC: names, addresses, phone and the group's name never leave the raw file.
DAC_DROP = re.compile(
    r"(last name|first name|middle name|^suff$|facility name|adr_ln|ln_2_sprs|city|"
    r"telephone|adrs_id)",
    re.I,
)


def download_all() -> dict[str, object]:
    by_title = {s.dataset: s for s in sources.load()}
    paths = {}
    with Progress("reference_download") as p:
        for name, title in FILES.items():
            p.add(name, total=download.remote_size(by_title[title].url) or 50_000_000, unit="B")
        for name, title in FILES.items():
            s = by_title[title]
            dest = RAW / f"{name}.csv"
            p.start(name)
            download.fetch(s.url, dest, s.source, progress=p, task=name)
            p.state["tasks"][name]["total"] = dest.stat().st_size
            p.finish(name)
            paths[name] = dest
    return paths


def _snake(c: str) -> str:
    return re.sub(r"[^0-9a-z]+", "_", c.lower()).strip("_")


def convert_all(paths: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    con = _connect()

    def copy(select: str, src, name: str, where: str = "") -> None:
        con.execute(
            f"COPY (SELECT {select} FROM {_read_csv(src)} {where}) TO '{OUT / name}.parquet' "
            "(FORMAT parquet, COMPRESSION zstd)"
        )
        n = con.execute(f"SELECT count(*) FROM '{OUT / name}.parquet'").fetchone()[0]
        log.info("%s: %s rows", name, f"{n:,}")

    cols = [c for c in _csv_columns(con, paths["dac"]) if not DAC_DROP.search(c)]
    sel = ", ".join(
        f'try_cast("{c}" AS BIGINT) AS npi'
        if c == "NPI"
        else f'try_cast("{c}" AS INTEGER) AS {_snake(c)}'
        if c in ("Grd_yr", "num_org_mem")
        else f'left("{c}", 5) AS zip5'
        if c == "ZIP Code"
        else f"nullif(trim(\"{c}\"), '') AS {_snake(c)}"
        for c in cols
    )
    copy(sel, paths["dac"], "dac")

    copy("*", paths["nucc_taxonomy"], "nucc_taxonomy")

    places = _csv_columns(con, paths["places_county"])
    keep = [
        c
        for c in places
        if c.upper()
        in {
            "STATEABBR",
            "STATEDESC",
            "COUNTYNAME",
            "COUNTYFIPS",
            "TOTALPOPULATION",
            "TOTALPOP18PLUS",
        }
        or re.match(r"(?i)^(diabetes|obesity)_(crude|adj)", c)
    ]
    copy(", ".join(f'"{c}" AS {_snake(c)}' for c in keep), paths["places_county"], "places_county")

    copy(
        "try_cast(year AS INTEGER) AS year, locationabbr AS state, locationdesc AS state_name, "
        "question, response, break_out, try_cast(data_value AS DOUBLE) AS pct, "
        "try_cast(confidence_limit_low AS DOUBLE) AS pct_low, "
        "try_cast(confidence_limit_high AS DOUBLE) AS pct_high, "
        "try_cast(sample_size AS INTEGER) AS sample_size",
        paths["brfss_diabetes_65plus"],
        "brfss_diabetes_65plus",
        "WHERE response = 'Yes'",
    )

    enr = _csv_columns(con, paths["enrollment"])
    num = [c for c in enr if c.endswith("_BENES") or c == "PART_D" or c.startswith("PRSCRPTN")]
    copy(
        "try_cast(YEAR AS INTEGER) AS year, BENE_GEO_LVL AS geo_lvl, "
        "BENE_STATE_ABRVTN AS state, BENE_STATE_DESC AS state_name, "
        + ", ".join(f'try_cast("{c}" AS DOUBLE) AS {_snake(c)}' for c in num),
        paths["enrollment"],
        "enrollment_state_year",
        "WHERE MONTH = 'Year' AND BENE_GEO_LVL IN ('National', 'State')",
    )

    gv = _csv_columns(con, paths["gv"])
    copy(
        ", ".join(f'"{c}" AS {_snake(c)}' for c in gv),
        paths["gv"],
        "gv_state_county",
        "WHERE BENE_AGE_LVL = 'All'",
    )
    con.close()


def try_nppes() -> bool:
    """NPPES download page was down for maintenance; report whether it is back."""
    import httpx

    r = httpx.get(
        "https://download.cms.gov/nppes/NPI_Files.html", headers=download.HEADERS, timeout=30
    )
    zips = re.findall(r"NPPES_Data_Dissemination_[A-Za-z]+_\d{4}(?:_V2)?\.zip", r.text)
    log.info("NPPES page: %s", f"{len(zips)} zip links" if zips else "no zip links (still down?)")
    return bool(zips)


def main(argv: list[str]) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S"
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try_nppes()
    if argv[:1] == ["nppes"]:
        return 0
    convert_all(download_all())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
