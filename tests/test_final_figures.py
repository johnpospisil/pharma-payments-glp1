"""P21: every final figure exists in light, dark and social form, with alt text."""

import json

import pytest

from ppg import config
from ppg.viz.final import CHARTS, OUT, SOCIAL
from ppg.viz.theme import BRANDS, DARK, LIGHT

pytestmark = pytest.mark.data


def test_brand_colours_follow_the_brand_in_both_modes():
    assert len(set(LIGHT.slots)) == len(set(DARK.slots)) == len(BRANDS)
    assert LIGHT.brand("Ozempic") == LIGHT.slots[0] and DARK.brand("Victoza") == DARK.slots[3]
    assert LIGHT.brand("Byetta") == LIGHT.other


@pytest.mark.parametrize("name", list(CHARTS))
def test_figure_set(name):
    if not (OUT / "alt_text.json").exists():
        pytest.skip("run python -m ppg.viz.final first")
    for f in (f"{name}.png", f"{name}.svg", f"{name}_dark.png", f"{name}_dark.svg"):
        assert (OUT / f).stat().st_size > 10_000, f
    assert (SOCIAL / f"{name}_1200x675.png").exists()
    alt = json.loads((OUT / "alt_text.json").read_text())[name]
    assert len(alt) > 150 and "pp" not in alt.split()[0]
    assert config.QA_DIR.exists()
