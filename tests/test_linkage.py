"""NPI linkage (P08): specialty grouping (unit) and linkage results (real data)."""

import json

import pytest

from ppg import config
from ppg.build.linkage import op_specialty_group

P = "Allopathic & Osteopathic Physicians"
APN = "Physician Assistants & Advanced Practice Nursing Providers"


@pytest.mark.parametrize(
    ("path", "group"),
    [
        (f"{P}|Family Medicine", "primary_care_physician"),
        (f"{P}|Internal Medicine", "primary_care_physician"),
        (f"{P}|General Practice", "primary_care_physician"),
        (f"{P}|Internal Medicine|Endocrinology, Diabetes & Metabolism", "endocrinology"),
        (f"{P}|Internal Medicine|Cardiovascular Disease", "cardiology"),
        (f"{P}|Internal Medicine|Interventional Cardiology", "cardiology"),
        (f"{P}|Internal Medicine|Nephrology", "nephrology"),
        (f"{P}|Internal Medicine|Gastroenterology", "other_physician"),
        (f"{P}|Psychiatry & Neurology|Neurology", "other_physician"),
        (f"{P}|Dermatology", "other_physician"),
        (f"{APN}|Nurse Practitioner|Family", "nurse_practitioner"),
        (f"{APN}|Nurse Practitioner", "nurse_practitioner"),
        (f"{APN}|Physician Assistant|Medical", "physician_assistant"),
        (f"{APN}|Clinical Nurse Specialist", "other_nonphysician"),
        ("Eye and Vision Services Providers|Optometrist", "other_nonphysician"),
        ("Dental Providers|Dentist|General Practice", "other_nonphysician"),
        ("Podiatric Medicine & Surgery Service Providers|Podiatrist", "other_nonphysician"),
        (None, "missing"),
        ("", "missing"),
    ],
)
def test_op_specialty_group(path, group):
    assert op_specialty_group(path) == group


@pytest.fixture(scope="module")
def stats():
    f = config.QA_DIR / "linkage.json"
    if not f.exists():
        pytest.skip("run python -m ppg.build.linkage first")
    return json.loads(f.read_text())


@pytest.mark.data
def test_learned_route_agrees_with_supplement(stats):
    p = stats["profiles"]
    assert p["learned_vs_supplement_disagree"] <= 10  # of ~1.7M shared profiles


@pytest.mark.data
def test_no_unlinked_records_after_2015_beyond_tolerance(stats):
    import pandas as pd

    r = pd.read_csv(config.QA_DIR / "linkage_match_rates.csv")
    r = r[r.recipient_class.isin(["md_do", "np", "pa"])]
    late = r[r.program_year >= 2015]
    assert (late.match_rate > 0.998).all()
    early = r[r.program_year <= 2014]
    assert (early.match_rate > 0.97).all()


@pytest.mark.data
def test_teaching_hospitals_never_linked(stats):
    assert stats["records_by_method"].get("out_of_scope", 0) > 0
