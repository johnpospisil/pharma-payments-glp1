"""Pinned headline estimates (CLAUDE.md: every published number is pinned).

Primary pre-registered estimates (PREREGISTRATION.md §6, P13): Callaway & Sant'Anna ATT over
event years 0-3 on Pr(>= 11 claims of the paid brand), physicians, not-yet-treated controls.
Point estimates are deterministic; standard errors come from a seeded multiplier bootstrap.
If a rebuild moves these, something upstream changed: find out what before re-pinning.
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
