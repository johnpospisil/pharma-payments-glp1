"""P22: the article types no statistic by hand, uses only defined variables, and never claims
causation (CLAUDE.md: every article number is read from report/qa)."""

import re

import yaml

from ppg import config

QMD = config.REPORT_DIR / "index.qmd"
VARS = config.REPORT_DIR / "_variables.yml"
# definitions, not results: suppression threshold, bin edge, rate denominator, group names
# ("top 1%"), the 30-day fill unit and the Python version
ALLOWED = {"11", "$100", "1,000", "1%", "10%", "30", "3.12"}


def _prose() -> str:
    s = QMD.read_text()
    s = s.split("---", 2)[2]  # drop YAML front matter
    s = re.sub(r"\{\{<.*?>\}\}", " ", s)  # shortcodes
    s = re.sub(r"\[@[^\]]*\]|@\w+", " ", s)  # citations
    s = re.sub(r"\]\([^)]*\)", "]", s)  # link targets
    s = re.sub(r"\{[^}]*\}", " ", s)  # attributes
    return re.sub(r"`[^`]*`", " ", s)


def test_no_hand_typed_numbers():
    bad = []
    for m in re.finditer(r"(?<![\w.\-–])\$?\d[\d,]*(?:\.\d+)?%?", _prose()):
        tok = m.group().rstrip(",")
        plain = tok.replace(",", "")
        if tok in ALLOWED or (plain.isdigit() and (int(plain) <= 12 or 1979 <= int(plain) <= 2030)):
            continue
        bad.append(tok)
    assert not bad, f"type these through {{{{< var >}}}}: {bad}"


def test_every_variable_is_defined():
    used = set(re.findall(r"\{\{< var (\w+) >\}\}", QMD.read_text()))
    defined = set(yaml.safe_load(VARS.read_text()))
    assert used <= defined, used - defined


def test_no_causal_language():
    text = QMD.read_text().lower()
    for m in re.finditer(r"\bcaus\w*|\bbought\b|\bbuy(s|ing)?\b", text):
        ctx = text[max(0, m.start() - 60) : m.end()]
        assert "not show" in ctx or "does not" in ctx or "cannot" in ctx, ctx
