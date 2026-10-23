"""Open Payments zips -> Parquet (P03).

General Payments are mapped to one harmonised schema across the three CSV eras
(see DATA.md §2). Research, Ownership and Removed/Deleted files are kept close to
source (lower-cased column names, all text) minus names and street addresses.
Recipient names and street addresses are never written: the analysis does not need
them, and leaving them out supports the no-individuals rule.

Each year is extracted to DATA_DIR/tmp (SSD), converted with DuckDB, then the
extracted CSV is deleted. The zips on RAW_DIR stay the immutable raw copy.
"""

from __future__ import annotations

import logging
import re
import shutil
import threading
import zipfile
from pathlib import Path

import duckdb

from ppg import config
from ppg.ingest.open_payments import RAW, zip_sources
from ppg.progress import Progress

log = logging.getLogger(__name__)

OUT = config.PARQUET_DIR / "open_payments"
TMP = config.DATA_DIR / "tmp" / "open_payments"
README_DIR = config.REFERENCE_DIR / "op_readme"

# Column-name fragments that identify people or street addresses (dropped everywhere).
PII = re.compile(
    r"(first_name|middle_name|last_name|name_suffix|_suffix$|street_address|address_line"
    r"|alternate_.*name|teaching_hospital_name|name_of_third_party_entity)",
    re.I,
)

PRODUCT_STRUCT = (
    "STRUCT(slot INTEGER, covered VARCHAR, kind VARCHAR, category VARCHAR, "
    "name VARCHAR, ndc VARCHAR, pdi VARCHAR)"
)


def _yes(col: str) -> str:
    return f"CASE upper(trim({col})) WHEN 'YES' THEN TRUE WHEN 'NO' THEN FALSE END"


def _date(col: str) -> str:
    return f"try_strptime(nullif(trim({col}), ''), '%m/%d/%Y')::DATE"


def _nz(col: str) -> str:
    return f"nullif(trim({col}), '')"


# Placeholder text CMS uses in empty product slots (e.g. PDI = 'N/A' throughout PY2016-2020).
PLACEHOLDERS = ("N/A", "NA", "NONE", "NULL", "-")


def _nzp(col: str) -> str:
    """Product-field value, with blanks and placeholder text treated as missing."""
    quoted = ", ".join(f"'{p}'" for p in PLACEHOLDERS)
    return f"CASE WHEN upper(trim({col})) IN ({quoted}, '') THEN NULL ELSE trim({col}) END"


def general_select(cols: set[str]) -> str:
    """SELECT list mapping one General Payments CSV (any era) to the harmonised schema."""
    era_b = "Covered_Recipient_Profile_ID" in cols
    if era_b:
        profile, npi = "Covered_Recipient_Profile_ID", "Covered_Recipient_NPI"
        types = [f"Covered_Recipient_Primary_Type_{i}" for i in range(1, 7)]
        specs = [f"Covered_Recipient_Specialty_{i}" for i in range(1, 7)]
        rel = "Related_Product_Indicator"
        products = [
            f"struct_pack(slot := {i}, covered := {_nzp(f'Covered_or_Noncovered_Indicator_{i}')}, "
            f"kind := {_nzp(f'Indicate_Drug_or_Biological_or_Device_or_Medical_Supply_{i}')}, "
            f"category := {_nzp(f'Product_Category_or_Therapeutic_Area_{i}')}, "
            f"name := {_nzp(f'Name_of_Drug_or_Biological_or_Device_or_Medical_Supply_{i}')}, "
            f"ndc := {_nzp(f'Associated_Drug_or_Biological_NDC_{i}')}, "
            f"pdi := {_nzp(f'Associated_Device_or_Medical_Supply_PDI_{i}')})"
            for i in range(1, 6)
        ]
    else:
        profile = "Physician_Profile_ID"
        npi = "Physician_NPI" if "Physician_NPI" in cols else "NULL"
        types, specs = ["Physician_Primary_Type"], ["Physician_Specialty"]
        rel = "Product_Indicator"
        products = [
            f"struct_pack(slot := {i}, covered := 'Covered', kind := 'Drug', category := NULL, "
            f"name := {_nzp(f'Name_of_Associated_Covered_Drug_or_Biological{i}')}, "
            f"ndc := {_nzp(f'NDC_of_Associated_Covered_Drug_or_Biological{i}')}, pdi := NULL)"
            for i in range(1, 6)
        ] + [
            f"struct_pack(slot := {5 + i}, covered := 'Covered', kind := 'Device', "
            f"category := NULL, "
            f"name := {_nzp(f'Name_of_Associated_Covered_Device_or_Medical_Supply{i}')}, "
            f"ndc := NULL, pdi := NULL)"
            for i in range(1, 6)
        ]

    def nonnull_list(exprs: list[str]) -> str:
        return f"list_filter([{', '.join(_nz(e) for e in exprs)}], lambda x: x IS NOT NULL)"

    product_list = (
        f"list_filter([{', '.join(products)}]::{PRODUCT_STRUCT}[], "
        "lambda p: p.name IS NOT NULL OR p.ndc IS NOT NULL OR p.pdi IS NOT NULL)"
    )
    npi_expr = "NULL::BIGINT" if npi == "NULL" else f"try_cast({_nz(npi)} AS BIGINT)"
    return f"""
        try_cast(Program_Year AS INTEGER)                         AS program_year,
        try_cast(Record_ID AS BIGINT)                             AS record_id,
        {_nz("Change_Type")}                                      AS change_type,
        {_nz("Covered_Recipient_Type")}                           AS recipient_type,
        try_cast({_nz(profile)} AS BIGINT)                        AS profile_id,
        {npi_expr}                                                AS npi,
        {_nz("Teaching_Hospital_CCN")}                            AS teaching_hospital_ccn,
        try_cast({_nz("Teaching_Hospital_ID")} AS BIGINT)         AS teaching_hospital_id,
        {nonnull_list(types)}                                     AS primary_types,
        {nonnull_list(specs)}                                     AS specialties,
        {_nz("Recipient_City")}                                   AS recipient_city,
        {_nz("Recipient_State")}                                  AS recipient_state,
        left({_nz("Recipient_Zip_Code")}, 5)                      AS recipient_zip5,
        {_nz("Recipient_Country")}                                AS recipient_country,
        {_nz("Submitting_Applicable_Manufacturer_or_Applicable_GPO_Name")} AS submitting_entity,
        try_cast({_nz("Applicable_Manufacturer_or_Applicable_GPO_Making_Payment_ID")} AS BIGINT)
                                                                  AS manufacturer_id,
        {_nz("Applicable_Manufacturer_or_Applicable_GPO_Making_Payment_Name")}
                                                                  AS manufacturer_name,
        {_nz("Applicable_Manufacturer_or_Applicable_GPO_Making_Payment_State")}
                                                                  AS manufacturer_state,
        {_nz("Applicable_Manufacturer_or_Applicable_GPO_Making_Payment_Country")}
                                                                  AS manufacturer_country,
        try_cast({_nz("Total_Amount_of_Payment_USDollars")} AS DECIMAL(14, 2)) AS amount_usd,
        {_date("Date_of_Payment")}                                AS payment_date,
        try_cast({_nz("Number_of_Payments_Included_in_Total_Amount")} AS INTEGER) AS n_payments,
        {_nz("Form_of_Payment_or_Transfer_of_Value")}             AS form_of_payment,
        {_nz("Nature_of_Payment_or_Transfer_of_Value")}           AS nature_of_payment,
        {_nz("State_of_Travel")}                                  AS travel_state,
        {_nz("Country_of_Travel")}                                AS travel_country,
        {_yes("Physician_Ownership_Indicator")}                   AS physician_ownership,
        {_nz("Third_Party_Payment_Recipient_Indicator")}          AS third_party_recipient,
        {_yes("Charity_Indicator")}                               AS charity,
        {_yes("Third_Party_Equals_Covered_Recipient_Indicator")}  AS third_party_is_recipient,
        {_nz("Contextual_Information")}                           AS contextual_information,
        {_yes("Delay_in_Publication_Indicator")}                  AS delayed_publication,
        {_yes("Dispute_Status_for_Publication")}                  AS disputed,
        {_nz(rel)}                                                AS related_product_indicator,
        {product_list}                                            AS products,
        {_date("Payment_Publication_Date")}                       AS publication_date
    """


def _connect() -> duckdb.DuckDBPyConnection:
    (config.DATA_DIR / "tmp" / "duckdb").mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET memory_limit = '8GB'")
    con.execute("SET threads = 6")
    con.execute(f"SET temp_directory = '{config.DATA_DIR / 'tmp' / 'duckdb'}'")
    con.execute("SET preserve_insertion_order = false")
    # Keep DuckDB's progress tracking (read by _run_with_progress) but don't print its bar.
    con.execute("SET enable_progress_bar = true")
    con.execute("SET enable_progress_bar_print = false")
    return con


def _read_csv(path: Path) -> str:
    return (
        f"read_csv('{path}', header = true, all_varchar = true, quote = '\"', escape = '\"', "
        "max_line_size = 10000000, strict_mode = false)"
    )


def _csv_columns(con: duckdb.DuckDBPyConnection, path: Path) -> list[str]:
    return [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {_read_csv(path)}").fetchall()]


def _run_with_progress(con, sql: str, p: Progress, task: str) -> None:
    """Run `sql`, feeding DuckDB's own % complete into the progress task (scaled to its total)."""
    stop = threading.Event()

    def poll() -> None:
        while not stop.wait(2):
            try:
                pct = con.query_progress()
            except Exception:  # noqa: BLE001 - progress is best-effort
                continue
            if pct and pct > 0:
                t = p.state["tasks"][task]
                p.advance(task, max(pct / 100 * t["total"] - t["done"], 0))

    th = threading.Thread(target=poll, daemon=True)
    th.start()
    try:
        con.execute(sql)
    finally:
        stop.set()
        th.join()


def _extract(zf: zipfile.ZipFile, member: str, dest: Path, p: Progress, task: str) -> Path:
    out = dest / Path(member).name
    with zf.open(member) as src, out.open("wb") as dst:
        while block := src.read(16 * 1024 * 1024):
            dst.write(block)
            p.advance(task, len(block))
    return out


def _kind(member: str) -> str | None:
    name = Path(member).name.upper()
    for key, kind in (
        ("_GNRL_", "general"),
        ("_RSRCH_", "research"),
        ("_OWNRSHP_", "ownership"),
        ("REMOVED_DELETED", "removed_deleted"),
    ):
        if key in name and name.endswith(".CSV"):
            return kind
    if "README" in name:
        return "readme"
    return None


def convert_year(year: int, zip_path: Path, p: Progress) -> None:
    TMP.mkdir(parents=True, exist_ok=True)
    README_DIR.mkdir(parents=True, exist_ok=True)
    con = _connect()
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            kind = _kind(info.filename)
            if kind is None:
                continue
            if kind == "readme":
                (README_DIR / f"PY{year}_{Path(info.filename).name}").write_bytes(
                    zf.read(info.filename)
                )
                continue
            final = OUT / kind / f"program_year={year}" / "part-0.parquet"
            task_x, task_c = f"PY{year} {kind} extract", f"PY{year} {kind} convert"
            if final.exists():
                for t in (task_x, task_c):
                    if not p.is_done(t):
                        p.finish(t)
                continue
            p.start(task_x)
            csv_path = _extract(zf, info.filename, TMP, p, task_x)
            p.finish(task_x)
            p.start(task_c)
            cols = _csv_columns(con, csv_path)
            if kind == "general":
                select = general_select(set(cols))
            else:
                keep = [c for c in cols if not PII.search(c)]
                select = ", ".join(f'"{c}" AS "{c.lower()}"' for c in keep)
            final.parent.mkdir(parents=True, exist_ok=True)
            tmp_out = final.with_suffix(".parquet.tmp")
            sql = (
                f"COPY (SELECT {select} FROM {_read_csv(csv_path)}) TO '{tmp_out}' "
                "(FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 500000)"
            )
            _run_with_progress(con, sql, p, task_c)
            tmp_out.replace(final)
            csv_path.unlink()
            p.finish(task_c)
            n = con.execute(f"SELECT count(*) FROM '{final}'").fetchone()[0]
            log.info(
                "PY%d %s: %s rows -> %s (%.1f MB)",
                year,
                kind,
                f"{n:,}",
                final.name,
                final.stat().st_size / 1e6,
            )
    con.close()


def convert_profiles() -> None:
    """Covered Recipient Profile Supplement and profile-ID mapping, without names/addresses."""
    con = _connect()
    for src, name in (
        ("OP_CVRD_RCPNT_PRFL_SPLMTL_", "profile_supplement"),
        ("PBLCTN_PRVDR_PRFL_MAPPING_", "profile_id_mapping"),
    ):
        path = next(RAW.glob(f"{src}*.csv"))
        final = OUT / f"{name}.parquet"
        if final.exists():
            continue
        keep = [c for c in _csv_columns(con, path) if not PII.search(c)]
        select = ", ".join(f'"{c}" AS "{c.lower()}"' for c in keep)
        con.execute(
            f"COPY (SELECT {select} FROM {_read_csv(path)}) TO '{final}' "
            "(FORMAT parquet, COMPRESSION zstd)"
        )
        log.info("%s: %s rows", name, con.execute(f"SELECT count(*) FROM '{final}'").fetchone()[0])
    con.close()


def convert_all() -> None:
    zips = zip_sources()
    with Progress("op_convert") as p:
        plan = {}
        for y, s in sorted(zips.items()):
            zp = RAW / s.filename
            with zipfile.ZipFile(zp) as zf:
                plan[y] = zp
                for info in zf.infolist():
                    kind = _kind(info.filename)
                    if kind and kind != "readme":
                        p.add(f"PY{y} {kind} extract", total=info.file_size, unit="B")
                        # convert work ~ CSV size, so both steps weigh the same bytes overall
                        p.add(f"PY{y} {kind} convert", total=info.file_size, unit="B")
        for y, zp in plan.items():
            convert_year(y, zp, p)
        convert_profiles()
    shutil.rmtree(TMP, ignore_errors=True)
