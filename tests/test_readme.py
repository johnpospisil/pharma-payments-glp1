"""P26: the README's findings use only numbers the article reads from report/qa."""

import re

import yaml

from ppg import config

README = config.REPORT_DIR.parent / "README.md"
VARS = config.REPORT_DIR / "_variables.yml"
ALLOWED = {"11", "1%"}  # definitions: the suppression threshold, the top-1% group


def _findings() -> str:
    s = README.read_text()
    return s[s.index("<!-- findings") : s.index("<!-- /findings -->")].split("-->", 1)[1]


NUMBER = re.compile(r"(?<![\w.])[+−-]?\$?\d[\d,]*(?:\.\d+)?(?:–\d+(?:\.\d+)?)?%?")


def _exempt(tok: str) -> bool:
    """Definitions, years, year ranges and small counts ("twelve years", "top 1%")."""
    plain = tok.lstrip("+−-$").rstrip("%").replace(",", "")
    if tok in ALLOWED or re.fullmatch(r"20[12]\d–20[12]\d", plain):
        return True
    return plain.isdigit() and (int(plain) <= 12 or 2013 <= int(plain) <= 2025)


def test_findings_numbers_come_from_the_article_variables():
    values = {str(v).lstrip("+−-") for v in yaml.safe_load(VARS.read_text()).values()}
    values |= {p.lstrip("+−-") for v in values for p in re.split(r"\s*/\s*", v)}
    found = [m.group() for m in NUMBER.finditer(_findings())]
    bad = [t for t in found if not _exempt(t) and t.lstrip("+−-$").rstrip("%") not in values]
    assert not bad, f"not in report/_variables.yml: {bad}"


def test_findings_carry_the_doesnt_show_line():
    f = _findings()
    assert "doesn't show" in f and "consistent with" in f
