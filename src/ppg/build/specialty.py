"""Part D prescriber type -> specialty group (P05).

Rules are ordered; the first match wins. The output CSV
(data/reference/specialty_groups.csv) lists every `prscrbr_type` seen in 2013-2024 with
its group, the rule that assigned it, and volumes, so it can be reviewed by hand.
Edits belong in RULES or OVERRIDES here, never in the CSV.
"""

from __future__ import annotations

import re

import duckdb

from ppg import config

GROUPS = (
    "endocrinology",
    "primary_care_physician",
    "nurse_practitioner",
    "physician_assistant",
    "cardiology",
    "nephrology",
    "other_physician",
    "other_nonphysician",
)

# (group, regex on lower-cased prscrbr_type)
RULES: list[tuple[str, str]] = [
    ("endocrinology", r"endocrin"),
    ("nurse_practitioner", r"nurse practitioner"),
    ("physician_assistant", r"physician assistant"),
    ("nephrology", r"nephrolog"),
    ("cardiology", r"cardiol|cardiovascular|heart failure|congenital heart|electrophysiolog"),
    (
        "primary_care_physician",
        r"^(family practice|family medicine|internal medicine|general practice|"
        r"geriatric medicine|preventive medicine|osteopathic manipulative medicine)$",
    ),
    (
        "other_nonphysician",
        r"pharmac|student|nurse|midwife|anesthetist|crna|dentist|dental|oral|optomet|podiat|"
        r"chiropract|psycholog|psychoanalyst|social work|therap|audiolog|dietit|dietary|nutrition|"
        r"counsel|technician|technologist|optician|supplier|supplies|equipment|clinic|center|"
        r"agency|agencies|hospital|laboratory|facility|organization|home health|homemaker|"
        r"assistant|aide|doula|naturopath|naprapath|acupunct|homeopath|massage|unknown|undefined|"
        r"case manag|health educator|emergency medical|prosthetist|orthotist|orthotic|denturist|"
        r"analyst|speech|attendant|companion|respite|chore|meals|lodging|driver|veterinarian|"
        r"contractor|roster|biller|worker|peer specialist|hearing instrument|consultant|"
        r"administrator|nursing care|centralized flu|point of service|ph\.?d|practitioner|"
        r"program|military health care provider|personnel|in home|day training|"
        r"habilitation specialist|prevention professional|slide preparation|snf|spec/tech|"
        r"supply company|residential|odontics|orofacial",
    ),
]
# Exact-label overrides after review (label -> group).
OVERRIDES: dict[str, str] = {
    "Specialist": "other_physician",  # CMS label for MD/DO without a more specific taxonomy
    "Hospitalist": "other_physician",
    "Hematopoietic Cell Transplantation and Cellular Therapy": "other_physician",
    "Clinical Pharmacology": "other_physician",
    "Oral & Maxillofacial Surgery": "other_nonphysician",  # dentist-surgeons
    "Maxillofacial Surgery": "other_nonphysician",
    "Medicare Diabetes Preventive Program": "other_nonphysician",
}


def assign(label: str | None) -> tuple[str, str]:
    if not isinstance(label, str) or not label.strip():
        return "other_nonphysician", "missing"
    if label in OVERRIDES:
        return OVERRIDES[label], "override"
    low = label.lower()
    for group, pattern in RULES:
        if m := re.search(pattern, low):
            return group, f"{group}:{m.group(0)}"
    return "other_physician", "default"


def build() -> None:
    con = duckdb.connect()
    con.execute("SET enable_progress_bar_print = false")
    glp1 = (
        "regexp_matches(lower(gnrc_name), "
        "'semaglutide|tirzepatide|dulaglutide|liraglutide|exenatide|lixisenatide|albiglutide')"
    )
    df = con.execute(f"""
        SELECT prscrbr_type,
               count(DISTINCT prscrbr_npi)                                AS prescribers_all_years,
               count(DISTINCT prscrbr_npi) FILTER (WHERE year = 2024)    AS prescribers_2024,
               coalesce(sum(tot_clms) FILTER (WHERE {glp1}), 0)          AS glp1_claims_all_years,
               min(year) AS first_year, max(year) AS last_year
        FROM read_parquet('{config.PARQUET_DIR}/partd/by_provider_drug/*/*.parquet',
                          hive_partitioning = true)
        GROUP BY 1 ORDER BY glp1_claims_all_years DESC, prescribers_all_years DESC
    """).df()
    assigned = df.prscrbr_type.map(assign)
    df.insert(1, "specialty_group", [a[0] for a in assigned])
    df.insert(2, "rule", [a[1] for a in assigned])
    df.to_csv(config.REFERENCE_DIR / "specialty_groups.csv", index=False)
    summary = (
        df.groupby("specialty_group")[["prescribers_2024", "glp1_claims_all_years"]]
        .sum()
        .sort_values("glp1_claims_all_years", ascending=False)
    )
    summary["glp1_share"] = summary.glp1_claims_all_years / summary.glp1_claims_all_years.sum()
    print(summary.to_string())


if __name__ == "__main__":
    build()
