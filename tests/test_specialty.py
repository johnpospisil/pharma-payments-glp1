import pytest

from ppg.build.specialty import GROUPS, assign


@pytest.mark.parametrize(
    "label,group",
    [
        ("Endocrinology", "endocrinology"),
        ("Family Practice", "primary_care_physician"),
        ("Internal Medicine", "primary_care_physician"),
        ("General Practice", "primary_care_physician"),
        ("Geriatric Medicine", "primary_care_physician"),
        ("Nurse Practitioner", "nurse_practitioner"),
        ("Physician Assistant", "physician_assistant"),
        ("Cardiology", "cardiology"),
        ("Interventional Cardiology", "cardiology"),
        ("Cardiovascular Disease (Cardiology)", "cardiology"),
        ("Adult Congenital Heart Disease", "cardiology"),
        ("Nephrology", "nephrology"),
        ("Physical Medicine and Rehabilitation", "other_physician"),
        ("Physical Medicine & Rehabilitation", "other_physician"),
        ("Hematopoietic Cell Transplantation and Cellular Therapy", "other_physician"),
        ("Clinical Pharmacology", "other_physician"),
        ("Hospitalist", "other_physician"),
        ("Pharmacist", "other_nonphysician"),
        ("Certified Clinical Nurse Specialist", "other_nonphysician"),
        ("Student in an Organized Health Care Education/Training Program", "other_nonphysician"),
        ("Dentist", "other_nonphysician"),
        ("Skilled Nursing Facility", "other_nonphysician"),
        ("Rehabilitation Practitioner", "other_nonphysician"),
        (None, "other_nonphysician"),
        (float("nan"), "other_nonphysician"),
    ],
)
def test_assign(label, group):
    assert assign(label)[0] == group


def test_groups_closed_set():
    for label in ("Family Practice", "Nephrology", "Veterinarian", "Urology"):
        assert assign(label)[0] in GROUPS
