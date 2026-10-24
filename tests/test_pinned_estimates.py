"""Pinned headline estimates (CLAUDE.md: every published number is pinned).

Primary pre-registered estimates (PREREGISTRATION.md §6, P13): Callaway & Sant'Anna ATT over
event years 0-3 on Pr(>= 11 claims of the paid brand), physicians, not-yet-treated controls.
Point estimates are deterministic; standard errors come from a seeded multiplier bootstrap.
If a rebuild moves these, something upstream changed: find out what before re-pinning.

P14 adds the panel-form primary (DEV-5, base-period covariates) and the matched design
(DEV-4); both are deterministic, with analytic practice-clustered standard errors.
"""

import json

import pytest

from ppg import config

PINNED = {  # brand: (ATT 0-3, SE)
    "Trulicity": (0.083824, 0.00190),
    "Victoza": (0.012122, 0.00249),
    "Ozempic": (0.073596, 0.00226),
}

pytestmark = pytest.mark.data


@pytest.fixture(scope="module")
def results():
    f = config.QA_DIR / "es"
    if not (f / "primary_Ozempic.json").exists():
        pytest.skip("run python -m ppg.models.event_study all first")
    return {b: json.loads((f / f"primary_{b}.json").read_text()) for b in PINNED}


@pytest.mark.parametrize("brand", list(PINNED))
def test_primary_att(results, brand):
    att, se = PINNED[brand]
    o = results[brand]["overall_0_3"]
    assert o["att"] == pytest.approx(att, abs=5e-6)
    assert o["se"] == pytest.approx(se, rel=0.10)


def test_holm_adjusted_primary_family_significant():
    e = json.loads((config.QA_DIR / "event_study.json").read_text())
    assert all(p < 0.05 for p in e["holm"].values())


PINNED_P14 = {  # (tag, brand): (ATT 0-3, SE)
    ("panel", "Trulicity"): (0.120332, 0.00180),
    ("panel", "Victoza"): (0.054624, 0.00221),
    ("panel", "Ozempic"): (0.137097, 0.00257),
    ("matched_registered", "Trulicity"): (0.125040, 0.00176),
    ("matched_registered", "Victoza"): (0.066390, 0.00200),
    ("matched_registered", "Ozempic"): (0.145859, 0.00250),
    ("matched_trajectory", "Trulicity"): (0.131859, 0.00246),
    ("matched_trajectory", "Victoza"): (0.063989, 0.00241),
    ("matched_trajectory", "Ozempic"): (0.144967, 0.00251),
}


@pytest.mark.parametrize("key", list(PINNED_P14), ids=lambda k: "-".join(k))
def test_p14_att(key):
    f = config.QA_DIR / "es" / f"{key[0]}_{key[1]}.json"
    if not f.exists():
        pytest.skip("run python -m ppg.models.cs_panel all and ppg.models.matched all first")
    o = json.loads(f.read_text())["overall_0_3"]
    att, se = PINNED_P14[key]
    assert o["att"] == pytest.approx(att, abs=5e-6)
    assert o["se"] == pytest.approx(se, rel=0.01)


def test_matched_design_passes_registered_check():
    m = json.loads((config.QA_DIR / "matched.json").read_text())["brands"]
    assert all(m[b]["registered"]["half_primary_and_significant"] for b in PINNED)
    assert all(m[b]["registered"]["max_abs_smd_after"] < 0.1 for b in PINNED)
