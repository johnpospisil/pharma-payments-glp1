"""P20 article-claims check: every number destined for the article, read from report/qa.

Each claim names its source (a JSON path or a CSV row), the scale and rounding it is quoted at,
and the value stated in the approved prompt results (CLAUDE.md, docs/results.md). The check
recomputes the quoted value from report/qa and compares; P22 renders article numbers from
report/qa/claims.json, so nothing in the article is typed by hand.

    python -m ppg.qa.claims        -> report/qa/claims.json (+ exit 1 on any mismatch)
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass

import pandas as pd

from ppg import config

QA = config.QA_DIR


@dataclass(frozen=True)
class Claim:
    id: str
    text: str  # how the article quotes it ({} = the value)
    source: str  # file in report/qa
    path: tuple  # JSON keys, or (pandas query, column) for a CSV
    stated: float  # value as stated in the approved results, at `scale` and `digits`
    scale: float = 1.0
    digits: int = 1

    def value(self) -> float:
        if self.source.endswith(".csv"):
            q, col = self.path
            rows = pd.read_csv(QA / self.source).query(q, engine="python")
            assert len(rows) == 1, f"{self.id}: {len(rows)} rows match {q!r}"
            return float(rows[col].iloc[0])
        x = json.loads((QA / self.source).read_text())
        for k in self.path:
            x = x[k]
        return float(x)

    def quoted(self) -> float:
        return round(self.value() * self.scale, self.digits)


def _pp(id, text, source, path, stated, digits=1):
    return Claim(id, text, source, path, stated, 100.0, digits)


def _m(brand, spec):  # matched.json binary estimate
    return ("brands", brand, spec, "att")


def _f(test, brand, col="att"):  # falsification.csv row
    return (f"test.str.startswith({test!r}) and brand == {brand!r}", col)


def _sens(brand, spec):
    return (f"brand == {brand!r} and spec == {spec!r}", "att")


H = "secondary_family.json"
CLAIMS: list[Claim] = [
    # --- descriptive (P11)
    Claim("spend_2013", "Part D GLP-1 spending ${}B in 2013", "eda.json",
          ("chart3", "partd_glp1_cost_by_year", "2013"), 0.55, digits=2),
    Claim("spend_2024", "${}B in 2024", "eda.json",
          ("chart3", "partd_glp1_cost_by_year", "2024"), 27.9),
    Claim("ozempic_share_2024", "Ozempic {}% of 2024 GLP-1 spending", "eda.json",
          ("chart3", "share_ozempic_2024"), 46, 100, 0),
    Claim("promo_usd_m", "${}M GLP-1 promotional payments 2013-2025", "payments.json",
          ("glp1_promo_usd", "split"), 424.5, 1e-6),
    Claim("paid_npis_k", "{}K prescribers paid for a GLP-1", "payments.json",
          ("glp1_paid_npis",), 320, 1e-3, 0),
    Claim("speaker_share", "speaker fees {}% of GLP-1 promotional $", "eda.json",
          ("chart4", "glp1_promo_usd_by_type_share", "usd_speaker"), 59, 100, 0),
    Claim("meal_share", "meals {}%", "eda.json",
          ("chart4", "glp1_promo_usd_by_type_share", "usd_food_beverage"), 28, 100, 0),
    Claim("glp1_speakers", "{} prescribers ever paid as GLP-1 speakers", "payments.json",
          ("npis_ever_glp1_speaker",), 3288, digits=0),
    Claim("top1_share", "top 1% of paid prescribers got {}% of GLP-1 promotional $", "eda.json",
          ("chart7", "top1_share"), 76, 100, 0),
    Claim("gini", "Gini {}", "eda.json", ("chart7", "gini"), 0.92, digits=2),
    Claim("state_us", "US ${} per Part D enrollee with diabetes (2024)", "eda.json",
          ("chart6", "usd_per_diabetic_us"), 2.59, digits=2),
    Claim("state_max", "highest state ${}", "eda.json",
          ("chart6", "top5_states", "CO"), 4.25, digits=2),
    Claim("state_min", "lowest state ${}", "eda.json",
          ("chart6", "bottom5_states", "MT"), 0.41, digits=2),
    Claim("endo_per_1000", "endocrinology ${} per 1,000 other diabetes claims", "eda.json",
          ("specialty_2024", "endocrinology", "usd_per_1000_dm_claims"), 1421, digits=0),
    Claim("pc_per_1000", "primary care ${}", "eda.json",
          ("specialty_2024", "primary_care_physician", "usd_per_1000_dm_claims"), 234, digits=0),
    # --- primary binary estimates (P14, DEV-5 panel form) and matched (registered CEM)
    _pp("att_trulicity", "Trulicity +{} pp", "matched.json", _m("Trulicity", "primary"), 12.0),
    _pp("att_victoza", "Victoza +{} pp", "matched.json", _m("Victoza", "primary"), 5.5),
    _pp("att_ozempic", "Ozempic +{} pp", "matched.json", _m("Ozempic", "primary"), 13.7),
    _pp("matched_trulicity", "matched +{} pp", "matched.json", _m("Trulicity", "registered"),
        12.5),
    _pp("matched_victoza", "matched +{} pp", "matched.json", _m("Victoza", "registered"), 6.6),
    _pp("matched_ozempic", "matched +{} pp", "matched.json", _m("Ozempic", "registered"), 14.6),
    Claim("treated_trulicity", "{} newly paid Trulicity physicians", "matched.json",
          ("brands", "Trulicity", "primary", "treated"), 67741, digits=0),
    Claim("honest_trulicity", "HonestDiD breakdown M̄ {}", "matched.json",
          ("brands", "Trulicity", "primary", "honest_breakdown_mbar"), 1.75, digits=2),
    # --- brand share (P15; D29, D34)
    _pp("share_trulicity", "Trulicity share +{} pp", "switching.json",
        ("Trulicity", "own_share", "att"), 4.1),
    _pp("share_ozempic", "Ozempic share +{} pp", "switching.json",
        ("Ozempic", "own_share", "att"), 3.0),
    _pp("share_mounjaro", "Mounjaro share +{} pp", "switching.json",
        ("Mounjaro", "own_share", "att"), 5.3),
    _pp("share_victoza", "Victoza share {} pp", "switching.json",
        ("Victoza", "own_share", "att"), -4.8),
    Claim("switch_frac_trulicity", "{}% of extra Trulicity claims are switching",
          "switching.json", ("Trulicity", "decomposition", "switching_fraction"), 56, 100, 0),
    Claim("switch_frac_ozempic", "{}% for Ozempic", "switching.json",
          ("Ozempic", "decomposition", "switching_fraction"), 58, 100, 0),
    # --- dose / payment type (P16)
    _pp("dose_lt100_trulicity", "Trulicity < $100 +{}", "dose_response.csv",
        ("brand == 'Trulicity' and family == 'dose_g' and group == '< $100'", "att"), 11.9),
    _pp("dose_ge100_trulicity", "Trulicity ≥ $100 +{}", "dose_response.csv",
        ("brand == 'Trulicity' and family == 'dose_g' and group != '< $100'", "att"), 16.8),
    _pp("dose_lt100_ozempic", "Ozempic < $100 +{}", "dose_response.csv",
        ("brand == 'Ozempic' and family == 'dose_g' and group == '< $100'", "att"), 13.2),
    _pp("dose_ge100_ozempic", "Ozempic ≥ $100 +{}", "dose_response.csv",
        ("brand == 'Ozempic' and family == 'dose_g' and group != '< $100'", "att"), 19.1),
    # --- falsification (P17)
    _pp("statin_trulicity", "statins +{} pp (Trulicity-paid)", "falsification.csv",
        _f("Negative-control outcome: statins", "Trulicity"), 6.4),
    _pp("statin_victoza", "statins +{} pp (Victoza)", "falsification.csv",
        _f("Negative-control outcome: statins", "Victoza"), 7.9),
    _pp("statin_ozempic", "statins +{} pp (Ozempic)", "falsification.csv",
        _f("Negative-control outcome: statins", "Ozempic"), 7.1),
    _pp("nc_anticoag", "anticoagulant payments +{} pp on any GLP-1", "falsification.csv",
        _f("Negative-control exposure: Anticoagulant", "any GLP-1"), 5.0),
    _pp("nc_inhaled", "inhaled-respiratory payments +{} pp", "falsification.csv",
        _f("Negative-control exposure: Inhaled", "any GLP-1"), 9.0),
    # --- sensitivity (P18)
    Claim("dev8_trulicity", "volume-growth matched +{} pp", "sensitivity.csv",  # already in pp
          _sens("Trulicity", "Matched also on total-claims growth (DEV-8)"), 12.7),
    Claim("h6_max", "matched PPML fills up to +{}%", "sensitivity.csv",
          _sens("Trulicity", "Fills, PPML, suppressed = 0 (H6) [matched]"), 111, digits=0),
    Claim("h6_min", "matched PPML fills from +{}%", "sensitivity.csv",
          _sens("Victoza", "Fills, PPML, suppressed = cap (H6) [matched]"), 17, digits=0),
    # --- secondary family (P19, DEV-10)
    _pp("h2", "H2 +{} pp", H, ("family", "H2 speaker/consulting − meals only", "att"), 5.6),
    Claim("h2_holm", "Holm p {}", H, ("family", "H2 speaker/consulting − meals only",
                                      "p_holm"), 0.12, digits=2),
    _pp("h3", "H3 {} pp", H, ("family", "H3 endocrinology + cardiology − primary care", "att"),
        -0.4),
    _pp("h4", "H4 +{} pp", H, ("family", "H4 ≥ $100 − < $100 in the first year", "att"), 5.1),
    _pp("h5", "H5 +{} pp share", H, ("family", "H5 own-brand share (log-odds, matched)", "att"),
        3.2),
    Claim("h5_holm", "Holm p {}", H, ("family", "H5 own-brand share (log-odds, matched)",
                                      "p_holm"), 0.021, digits=3),
    Claim("h6", "H6 +{}% fills", H, ("family", "H6 fills, PPML matched, suppressed = cap (log "
                                     "ratio)", "ratio"), 28.7, 100),
    _pp("h7", "H7 NPs/PAs +{} pp", H, ("family", "H7 NPs/PAs, Pr(≥ 11 claims)", "att"), 15.0),
    _pp("south_min", "South larger by {} pp (smallest contrast)", "heterogeneity_comparisons.csv",
        ("brand == 'Trulicity' and group == 'Northeast'", "att"), -2.3),
    _pp("victoza_endo", "Victoza endocrinology +{} pp vs primary care",
        "heterogeneity_comparisons.csv",
        ("brand == 'Victoza' and group == 'endocrinology'", "att"), 8.3),
]  # fmt: skip


def check() -> dict:
    rows = []
    for c in CLAIMS:
        try:
            q = c.quoted()
            ok = abs(q - c.stated) < 10**-c.digits / 2 + 1e-9
            rows.append({"id": c.id, "text": c.text.format(q), "source": c.source,
                         "path": list(c.path), "value": c.value(), "quoted": q,
                         "stated": c.stated, "pass": ok})  # fmt: skip
        except (KeyError, AssertionError, FileNotFoundError) as e:
            rows.append({"id": c.id, "source": c.source, "error": repr(e), "pass": False})
    out = {"claims": len(rows), "pass": all(r["pass"] for r in rows),
           "failures": [r for r in rows if not r["pass"]], "values": rows}  # fmt: skip
    (QA / "claims.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return out


if __name__ == "__main__":
    res = check()
    print(f"{res['claims']} claims, {len(res['failures'])} failing")
    for r in res["failures"]:
        print(" ", r)
    sys.exit(0 if res["pass"] else 1)
