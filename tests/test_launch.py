"""P27: launch drafts use only the article's numbers, and Bluesky posts fit the limit."""

import re

import yaml

from ppg import config

LAUNCH = config.REPORT_DIR.parent / "docs" / "launch"
VARS = config.REPORT_DIR / "_variables.yml"
ALLOWED = {"1%", "95%"}  # definitions: the top-1% group, the confidence level
# statistics: a decimal, a percentage, a dollar amount or a comma-grouped count
STAT = re.compile(r"(?<![\w.])[+−-]?\$?\d[\d,]*(?:\.\d+)?(?:–\d[\d,]*(?:\.\d+)?)?%?")


def _values() -> set[str]:
    v = {str(x).lstrip("+−-") for x in yaml.safe_load(VARS.read_text()).values()}
    return v | {p.lstrip("+−-") for x in v for p in re.split(r"\s*/\s*", x)}


def _is_stat(tok: str) -> bool:
    return any(c in tok for c in ".%$,") and not re.fullmatch(r"20\d\d[–-]20\d\d", tok)


def test_draft_numbers_come_from_the_article_variables():
    values, bad = _values(), []
    for f in sorted(LAUNCH.glob("*.md")):
        text = re.sub(r"https?://\S+|`[^`]*`", " ", f.read_text())
        for m in STAT.finditer(text):
            tok = m.group().rstrip(",.")
            core = tok.lstrip("+−-$").rstrip("%")
            if _is_stat(tok) and tok not in ALLOWED and core not in values:
                bad.append((f.name, tok))
    assert not bad, f"not in report/_variables.yml: {bad}"


def test_bluesky_posts_fit_300_characters():
    text = (LAUNCH / "linkedin-bluesky.md").read_text().split("## Bluesky", 1)[1]
    posts = re.split(r"\*\*\d/\d\*\*[^\n]*\n", text)[1:]
    assert len(posts) == 6
    for i, p in enumerate(posts, 1):
        body = " ".join(line.removeprefix("> ") for line in p.strip().splitlines())
        assert len(body) <= 300, (i, len(body))


def test_no_causal_or_accusatory_wording_without_negation():
    for f in sorted(LAUNCH.glob("*.md")):
        text = f.read_text().lower()
        for m in re.finditer(r"\bcaus(?!al ?inference)\w*|\bbought\b|\bbuy\w*|\bbrib\w*", text):
            start, end = text.rfind("\n", 0, m.start()) + 1, text.find("\n", m.end())
            ctx = text[start:end]  # the whole line
            ok = any(w in ctx for w in ("not", "none", "never", "avoid", "n't", "?"))
            assert ok, (f.name, ctx)
