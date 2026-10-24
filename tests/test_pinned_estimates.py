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

PINNED = {  # brand: (ATT 0-3, SE), panel-form primary (DEV-5, D27)
    "Trulicity": (0.120332, 0.00180),
    "Victoza": (0.054624, 0.00221),
    "Ozempic": (0.137097, 0.00257),
}
PINNED_P13_AS_REPORTED = {  # R did cross-section mode, kept as "first reported"
    "Trulicity": (0.083824, 0.00190),
    "Victoza": (0.012122, 0.00249),
    "Ozempic": (0.073596, 0.00226),
}

pytestmark = pytest.mark.data


@pytest.fixture(scope="module")
def results():
    f = config.QA_DIR / "es"
    if not (f / "panel_Ozempic.json").exists():
        pytest.skip("run python -m ppg.models.event_study all and ppg.models.cs_panel all first")
    return {(t, b): json.loads((f / f"{t}_{b}.json").read_text())
            for t in ("panel", "primary") for b in PINNED}  # fmt: skip


@pytest.mark.parametrize("brand", list(PINNED))
def test_primary_att(results, brand):
    att, se = PINNED[brand]
    o = results["panel", brand]["overall_0_3"]
    assert o["att"] == pytest.approx(att, abs=5e-6)
    assert o["se"] == pytest.approx(se, rel=0.01)


@pytest.mark.parametrize("brand", list(PINNED))
def test_p13_as_reported(results, brand):
    att, se = PINNED_P13_AS_REPORTED[brand]
    o = results["primary", brand]["overall_0_3"]
    assert o["att"] == pytest.approx(att, abs=5e-6)
    assert o["se"] == pytest.approx(se, rel=0.10)


def test_holm_adjusted_primary_family_significant():
    m = json.loads((config.QA_DIR / "matched.json").read_text())
    assert all(p < 0.05 for p in m["holm_primary"].values())


PINNED_P14 = {  # (tag, brand): (ATT 0-3, SE)
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


PINNED_P15 = {  # (estimate, brand): own-share ATT 0-3 (H5, DEV-6); deterministic
    ("shares", "Trulicity"): 0.041405,
    ("shares", "Victoza"): -0.047594,
    ("shares", "Ozempic"): 0.030399,
    ("shares", "Mounjaro"): 0.053237,
    ("matched", "Trulicity"): 0.047955,
    ("matched", "Victoza"): -0.040924,
    ("matched", "Ozempic"): 0.034609,
    ("matched", "Mounjaro"): 0.045039,
}


@pytest.mark.parametrize("key", list(PINNED_P15), ids=lambda k: "-".join(k))
def test_p15_own_share(key):
    f = config.QA_DIR / "es" / f"switching_{key[1]}.json"
    if not f.exists():
        pytest.skip("run python -m ppg.models.switching all first")
    r = json.loads(f.read_text())
    assert r[key[0]][key[1]]["att"] == pytest.approx(PINNED_P15[key], abs=5e-6)


PINNED_P16 = {  # (brand, family, group): ATT 0-3 (H4 / DEV-7); deterministic
    ("Trulicity", "dose_g", "< $100"): 0.118727,
    ("Trulicity", "dose_g", "≥ $100"): 0.168103,
    ("Victoza", "dose_g", "< $100"): 0.052162,
    ("Victoza", "dose_g", "$100–1k"): 0.095699,
    ("Ozempic", "dose_g", "< $100"): 0.131607,
    ("Ozempic", "dose_g", "≥ $100"): 0.191447,
    ("Trulicity", "contacts_g", "≥ 4 contacts"): 0.182790,
    ("Ozempic", "contacts_g", "≥ 4 contacts"): 0.212875,
}


@pytest.mark.parametrize("key", list(PINNED_P16), ids=lambda k: "-".join(k))
def test_p16_dose(key):
    f = config.QA_DIR / "es" / f"dose_{key[0]}.json"
    if not f.exists():
        pytest.skip("run python -m ppg.models.dose_response all first")
    rows = json.loads(f.read_text())["families"][key[1]]
    att = next(r["att"] for r in rows if r["group"] == key[2])
    assert att == pytest.approx(PINNED_P16[key], abs=5e-6)


PINNED_P17 = {  # falsification estimates (deterministic): (file stem, key path) -> value
    ("falsification_Trulicity", ("statin_binary", "att")): 0.064021,
    ("falsification_Victoza", ("statin_binary", "att")): 0.079306,
    ("falsification_Ozempic", ("statin_binary", "att")): 0.070682,
    ("falsification_Ozempic", ("placebo_brand", "att")): 0.082591,
    ("falsification_nc_exposure", ("anticoagulant", "att")): 0.050246,
    ("falsification_nc_exposure", ("glp1", "att")): 0.133791,
}


@pytest.mark.parametrize("key", list(PINNED_P17), ids=lambda k: k[0] + "-" + "-".join(k[1]))
def test_p17_falsification(key):
    f = config.QA_DIR / "es" / f"{key[0]}.json"
    if not f.exists():
        pytest.skip("run python -m ppg.models.falsification all first")
    x = json.loads(f.read_text())
    for k in key[1]:
        x = x[k]
    assert x == pytest.approx(PINNED_P17[key], abs=5e-6)
