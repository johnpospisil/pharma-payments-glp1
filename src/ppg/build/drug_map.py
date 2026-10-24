"""Drug-name map (P07): Open Payments product strings and Part D drug names -> brand keys.

Open Payments names come from each manufacturer's own product list, so they are mostly
clean ("Ozempic", "TRULICITY", "SOLIQUA 100/33"); the risk is false positives from
substring matching ("PLUVICTO", 3M "Victory Series" brackets), so matching is on
normalised whole names and whole words only. Order of rules for one string:

    1. exact      normalised string equals a brand alias
    2. contains   one brand alias appears as whole words (two or more -> 'multi', no brand)
    3. molecule   a molecule rule matches (generic name; brand left blank)
    4. non_product  "No product discussed", "Diabetes - disease state", ...
    5. fuzzy      close spelling of an alias (difflib ratio >= FUZZY_CUTOFF); flagged for review

Edits belong in BRANDS / MOLECULES / ACCEPT / REJECT here, never in the generated CSVs:

    data/reference/drug_name_map.csv   Open Payments raw string -> brand (in-scope + reviewed)
    data/reference/partd_drug_map.csv  Part D (brnd_name, gnrc_name) -> brand family
    data/reference/drug_ndc_map.csv    NDC labeler-product (9 digits) -> brand, learned from names

    python -m ppg.build.drug_map       # needs data/work/op_product_strings.parquet (built here)
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass

import duckdb
import pandas as pd

from ppg import config
from ppg.disclosure import mask_small
from ppg.ingest.quality import MAKERS, NON_PROMOTIONAL

GLP1_CLASSES = ("glp1", "glp1_insulin_combo")
FUZZY_CUTOFF = 0.85


@dataclass(frozen=True)
class Brand:
    brand: str
    molecule: str
    drug_class: str
    manufacturer: str  # US marketer (latest); payer names are checked against `maker_re`
    aliases: tuple[str, ...] = ()
    indication: str = ""  # GLP-1s: 't2d' or 'obesity' (Part D excludes weight-loss-only use)
    maker_re: str = ""

    @property
    def keys(self) -> set[str]:
        return {normalise(a) for a in (self.brand, *self.aliases)}


_NOVO, _LILLY, _SANOFI = "novo nordisk", "lilly", "sanofi|genzyme"
_AZ = "astrazeneca|amylin|squibb|bristol|medimmune|acerta"  # exenatide: Amylin -> BMS -> AZ

# fmt: off
BRANDS: list[Brand] = [
    # GLP-1 receptor agonists (tirzepatide is a dual GIP/GLP-1 agonist; grouped here)
    Brand("Ozempic", "semaglutide", "glp1", "Novo Nordisk", indication="t2d", maker_re=_NOVO),
    Brand("Rybelsus", "semaglutide", "glp1", "Novo Nordisk", indication="t2d", maker_re=_NOVO),
    Brand("Wegovy", "semaglutide", "glp1", "Novo Nordisk", indication="obesity", maker_re=_NOVO),
    Brand("Victoza", "liraglutide", "glp1", "Novo Nordisk", ("Victoza 2-Pak", "Victoza 3-Pak"),
          indication="t2d", maker_re=_NOVO),
    Brand("Saxenda", "liraglutide", "glp1", "Novo Nordisk", indication="obesity", maker_re=_NOVO),
    Brand("Trulicity", "dulaglutide", "glp1", "Eli Lilly", indication="t2d", maker_re=_LILLY),
    Brand("Mounjaro", "tirzepatide", "glp1", "Eli Lilly", indication="t2d", maker_re=_LILLY),
    Brand("Zepbound", "tirzepatide", "glp1", "Eli Lilly", indication="obesity", maker_re=_LILLY),
    Brand("Byetta", "exenatide", "glp1", "AstraZeneca", indication="t2d", maker_re=_AZ),
    Brand("Bydureon", "exenatide extended-release", "glp1", "AstraZeneca",
          ("Bydureon BCise", "Bydureon DCP", "Bydureon Pen", "Bydureon Weekly"),
          indication="t2d", maker_re=_AZ),
    Brand("Adlyxin", "lixisenatide", "glp1", "Sanofi", indication="t2d", maker_re=_SANOFI),
    Brand("Tanzeum", "albiglutide", "glp1", "GlaxoSmithKline", indication="t2d",
          maker_re="glaxo|gsk"),
    Brand("Soliqua", "insulin glargine/lixisenatide", "glp1_insulin_combo", "Sanofi",
          ("Soliqua 100/33",), indication="t2d", maker_re=_SANOFI),
    Brand("Xultophy", "insulin degludec/liraglutide", "glp1_insulin_combo", "Novo Nordisk",
          ("Xultophy 100/3.6",), indication="t2d", maker_re=_NOVO),
    # SGLT2 inhibitors (and combinations containing one)
    Brand("Jardiance", "empagliflozin", "sglt2", "Boehringer Ingelheim / Eli Lilly"),
    Brand("Farxiga", "dapagliflozin", "sglt2", "AstraZeneca"),
    Brand("Invokana", "canagliflozin", "sglt2", "Janssen"),
    Brand("Steglatro", "ertugliflozin", "sglt2", "Merck"),
    Brand("Inpefa", "sotagliflozin", "sglt2", "Lexicon"),
    Brand("Brenzavvy", "bexagliflozin", "sglt2", "TheracosBio"),
    Brand("Glyxambi", "empagliflozin/linagliptin", "sglt2", "Boehringer Ingelheim / Eli Lilly"),
    Brand("Synjardy", "empagliflozin/metformin", "sglt2", "Boehringer Ingelheim / Eli Lilly"),
    Brand("Trijardy", "empagliflozin/linagliptin/metformin", "sglt2",
          "Boehringer Ingelheim / Eli Lilly"),
    Brand("Xigduo", "dapagliflozin/metformin", "sglt2", "AstraZeneca"),
    Brand("Qtern", "dapagliflozin/saxagliptin", "sglt2", "AstraZeneca"),
    Brand("Invokamet", "canagliflozin/metformin", "sglt2", "Janssen"),
    Brand("Steglujan", "ertugliflozin/sitagliptin", "sglt2", "Merck"),
    Brand("Segluromet", "ertugliflozin/metformin", "sglt2", "Merck"),
    # DPP-4 inhibitors (and combinations)
    Brand("Januvia", "sitagliptin", "dpp4", "Merck"),
    Brand("Zituvio", "sitagliptin", "dpp4", "Zydus"),
    Brand("Tradjenta", "linagliptin", "dpp4", "Boehringer Ingelheim / Eli Lilly"),
    Brand("Onglyza", "saxagliptin", "dpp4", "AstraZeneca"),
    Brand("Nesina", "alogliptin", "dpp4", "Takeda"),
    Brand("Janumet", "sitagliptin/metformin", "dpp4", "Merck"),
    Brand("Jentadueto", "linagliptin/metformin", "dpp4", "Boehringer Ingelheim / Eli Lilly"),
    Brand("Kombiglyze", "saxagliptin/metformin", "dpp4", "AstraZeneca"),
    Brand("Kazano", "alogliptin/metformin", "dpp4", "Takeda"),
    Brand("Oseni", "alogliptin/pioglitazone", "dpp4", "Takeda"),
    Brand("Juvisync", "sitagliptin/simvastatin", "dpp4", "Merck"),
    # Insulins
    Brand("Tresiba", "insulin degludec", "insulin", "Novo Nordisk"),
    Brand("Ryzodeg", "insulin degludec/insulin aspart", "insulin", "Novo Nordisk"),
    Brand("Levemir", "insulin detemir", "insulin", "Novo Nordisk"),
    Brand("NovoLog", "insulin aspart", "insulin", "Novo Nordisk", ("NovoLog Mix",)),
    Brand("Fiasp", "insulin aspart", "insulin", "Novo Nordisk"),
    Brand("Novolin", "human insulin", "insulin", "Novo Nordisk"),
    Brand("Lantus", "insulin glargine", "insulin", "Sanofi"),
    Brand("Toujeo", "insulin glargine", "insulin", "Sanofi"),
    Brand("Admelog", "insulin lispro", "insulin", "Sanofi"),
    Brand("Apidra", "insulin glulisine", "insulin", "Sanofi"),
    Brand("Basaglar", "insulin glargine", "insulin", "Eli Lilly"),
    Brand("Rezvoglar", "insulin glargine-aglr", "insulin", "Eli Lilly"),
    Brand("Humalog", "insulin lispro", "insulin", "Eli Lilly", ("Humalog Mix",)),
    Brand("Lyumjev", "insulin lispro-aabc", "insulin", "Eli Lilly"),
    Brand("Humulin", "human insulin", "insulin", "Eli Lilly"),
    Brand("Semglee", "insulin glargine-yfgn", "insulin", "Biocon / Viatris"),
    Brand("Afrezza", "inhaled insulin", "insulin", "MannKind"),
    # Other diabetes drugs
    Brand("Actos", "pioglitazone", "tzd", "Takeda"),
    Brand("Actoplus Met", "pioglitazone/metformin", "tzd", "Takeda"),
    Brand("Duetact", "pioglitazone/glimepiride", "tzd", "Takeda"),
    Brand("Avandia", "rosiglitazone", "tzd", "GlaxoSmithKline"),
    Brand("Glucophage", "metformin", "metformin", "Bristol Myers Squibb"),
    Brand("Glumetza", "metformin", "metformin", "Salix"),
    Brand("Riomet", "metformin", "metformin", "Sun"),
    Brand("Amaryl", "glimepiride", "sulfonylurea", "Sanofi"),
    Brand("Glucotrol", "glipizide", "sulfonylurea", "Pfizer"),
    Brand("Symlin", "pramlintide", "antidiabetic_other", "AstraZeneca", ("SymlinPen",)),
    Brand("Cycloset", "bromocriptine", "antidiabetic_other", "VeroScience"),
    Brand("Baqsimi", "glucagon (nasal)", "antidiabetic_other", "Amphastar"),
    Brand("Gvoke", "glucagon", "antidiabetic_other", "Xeris"),
    Brand("Zegalogue", "dasiglucagon", "antidiabetic_other", "Zealand"),
    Brand("Tzield", "teplizumab", "antidiabetic_other", "Sanofi"),
    # Negative-control outcome: statins (incl. statin combinations)
    Brand("Lipitor", "atorvastatin", "statin", "Pfizer / Viatris"),
    Brand("Crestor", "rosuvastatin", "statin", "AstraZeneca"),
    Brand("Zocor", "simvastatin", "statin", "Merck / Organon"),
    Brand("Pravachol", "pravastatin", "statin", "Bristol Myers Squibb"),
    Brand("Livalo", "pitavastatin", "statin", "Kowa"),
    Brand("Zypitamag", "pitavastatin", "statin", "Medicure"),
    Brand("Lescol", "fluvastatin", "statin", "Novartis"),
    Brand("Altoprev", "lovastatin", "statin", "Covis"),
    Brand("Mevacor", "lovastatin", "statin", "Merck"),
    Brand("Ezallor", "rosuvastatin", "statin", "Sun", ("Ezallor Sprinkle",)),
    Brand("Atorvaliq", "atorvastatin", "statin", "CMP Pharma"),
    Brand("Flolipid", "simvastatin", "statin", "Salerno"),
    Brand("Vytorin", "ezetimibe/simvastatin", "statin", "Merck / Organon"),
    Brand("Roszet", "ezetimibe/rosuvastatin", "statin", "Althera"),
    Brand("Liptruzet", "ezetimibe/atorvastatin", "statin", "Merck"),
    Brand("Caduet", "amlodipine/atorvastatin", "statin", "Pfizer / Viatris"),
    Brand("Advicor", "niacin/lovastatin", "statin", "AbbVie"),
    Brand("Simcor", "niacin/simvastatin", "statin", "AbbVie"),
    # Negative-control exposure candidates: oral anticoagulants
    Brand("Eliquis", "apixaban", "anticoagulant", "Bristol Myers Squibb / Pfizer"),
    Brand("Xarelto", "rivaroxaban", "anticoagulant", "Janssen"),
    Brand("Pradaxa", "dabigatran", "anticoagulant", "Boehringer Ingelheim"),
    Brand("Savaysa", "edoxaban", "anticoagulant", "Daiichi Sankyo"),
    Brand("Bevyxxa", "betrixaban", "anticoagulant", "Portola"),
    Brand("Coumadin", "warfarin", "anticoagulant", "Bristol Myers Squibb"),
    Brand("Jantoven", "warfarin", "anticoagulant", "Upsher-Smith"),
    # ... and inhaled respiratory drugs (asthma / COPD)
    Brand("Symbicort", "budesonide/formoterol", "inhaled_respiratory", "AstraZeneca"),
    Brand("Breztri", "budesonide/glycopyrrolate/formoterol", "inhaled_respiratory",
          "AstraZeneca"),
    Brand("Bevespi", "glycopyrrolate/formoterol", "inhaled_respiratory", "AstraZeneca"),
    Brand("Airsupra", "albuterol/budesonide", "inhaled_respiratory", "AstraZeneca"),
    Brand("Pulmicort", "budesonide", "inhaled_respiratory", "AstraZeneca"),
    Brand("Tudorza", "aclidinium", "inhaled_respiratory", "AstraZeneca / Covis"),
    Brand("Duaklir", "aclidinium/formoterol", "inhaled_respiratory", "AstraZeneca / Covis"),
    Brand("Advair", "fluticasone/salmeterol", "inhaled_respiratory", "GlaxoSmithKline"),
    Brand("Breo", "fluticasone furoate/vilanterol", "inhaled_respiratory", "GlaxoSmithKline"),
    Brand("Trelegy", "fluticasone furoate/umeclidinium/vilanterol", "inhaled_respiratory",
          "GlaxoSmithKline"),
    Brand("Anoro", "umeclidinium/vilanterol", "inhaled_respiratory", "GlaxoSmithKline"),
    Brand("Incruse", "umeclidinium", "inhaled_respiratory", "GlaxoSmithKline"),
    Brand("Arnuity", "fluticasone furoate", "inhaled_respiratory", "GlaxoSmithKline"),
    Brand("Flovent", "fluticasone propionate", "inhaled_respiratory", "GlaxoSmithKline"),
    Brand("Ventolin", "albuterol", "inhaled_respiratory", "GlaxoSmithKline"),
    Brand("Spiriva", "tiotropium", "inhaled_respiratory", "Boehringer Ingelheim"),
    Brand("Stiolto", "tiotropium/olodaterol", "inhaled_respiratory", "Boehringer Ingelheim"),
    Brand("Striverdi", "olodaterol", "inhaled_respiratory", "Boehringer Ingelheim"),
    Brand("Combivent", "ipratropium/albuterol", "inhaled_respiratory", "Boehringer Ingelheim"),
    Brand("Dulera", "mometasone/formoterol", "inhaled_respiratory", "Merck / Organon"),
    Brand("Asmanex", "mometasone", "inhaled_respiratory", "Merck / Organon"),
    Brand("Utibron", "indacaterol/glycopyrrolate", "inhaled_respiratory", "Novartis / Sunovion"),
    Brand("Seebri", "glycopyrrolate", "inhaled_respiratory", "Novartis / Sunovion"),
    Brand("Arcapta", "indacaterol", "inhaled_respiratory", "Novartis / Sunovion"),
    Brand("Lonhala", "glycopyrrolate", "inhaled_respiratory", "Sunovion"),
    Brand("Yupelri", "revefenacin", "inhaled_respiratory", "Viatris / Theravance"),
    Brand("Wixela", "fluticasone/salmeterol", "inhaled_respiratory", "Viatris"),
    Brand("AirDuo", "fluticasone/salmeterol", "inhaled_respiratory", "Teva"),
    Brand("ArmonAir", "fluticasone propionate", "inhaled_respiratory", "Teva"),
    Brand("Qvar", "beclomethasone", "inhaled_respiratory", "Teva"),
    Brand("ProAir", "albuterol", "inhaled_respiratory", "Teva"),
    Brand("Alvesco", "ciclesonide", "inhaled_respiratory", "Covis"),
    Brand("Ohtuvayre", "ensifentrine", "inhaled_respiratory", "Verona / Merck"),
]
# fmt: on

# Generic-name rules (first match wins), used for Part D generic rows and for any
# Open Payments string naming a molecule rather than a brand. Order matters: supplies
# before insulin ("Syringe-Needle,insulin"), GLP-1 before insulin (Soliqua), SGLT2 before
# DPP-4 before metformin (combinations). Part D truncates generic names to 30 characters
# ("Dapaglifloz Propaned/Metformin"), hence the short stems.
MOLECULES: list[tuple[str, str, str]] = [  # (regex on lower-case name, molecule, class)
    (  # insulin / diabetic context AND a supply word ("Medical Device" alone is not one)
        r"^(?=.*(insul|insln|\bins\b|diabet))"
        r"(?=.*(syring|syrge|syr\b|needle|ndl|pump|\bpmp\b|device|supplies|pen,reusable"
        r"|sharps|container))",
        "diabetes supply",
        "diabetes_supply",
    ),
    (r"semaglutide", "semaglutide", "glp1"),
    (r"tirzepatide", "tirzepatide", "glp1"),
    (r"dulaglutide", "dulaglutide", "glp1"),
    (r"liraglutide", "liraglutide", "glp1"),
    (r"exenatide", "exenatide", "glp1"),
    (r"lixisenatide", "lixisenatide", "glp1"),
    (r"albiglutide", "albiglutide", "glp1"),
    (r"\binsulin\b|\b(glargine|lispro|aspart|detemir|degludec|glulisine)\b", "insulin", "insulin"),
    (r"(empa|dapa|cana|ertu|sota|bexa)glifloz", "sglt2 inhibitor", "sglt2"),
    (r"(sita|lina|saxa|alo)glip", "dpp-4 inhibitor", "dpp4"),
    (r"(pio|rosi)glit", "thiazolidinedione", "tzd"),
    (
        r"glipizide|glyburide|glimepiride|chlorpropamide|tolbutamide|tolazamide",
        "sulfonylurea",
        "sulfonylurea",
    ),
    (r"metformin", "metformin", "metformin"),
    (
        r"repaglinide|nateglinide|acarbose|miglitol|pramlintide",
        "other antidiabetic",
        "antidiabetic_other",
    ),
    (r"\b(atorva|rosuva|simva|prava|lova|fluva|pitava)statin\b", "statin", "statin"),
    (
        r"apixaban|rivaroxaban|dabigatran|edoxaban|betrixaban|warfarin",
        "oral anticoagulant",
        "anticoagulant",
    ),
]

# Strings that name no product: "No product discussed", "Diabetes - disease state", ...
NON_PRODUCT = re.compile(
    r"^(NO|NON)[ _-]?PRODUCT|^NONE\b|^NOT APPLICABLE|DISEASE STATE|(?<!INFECTIOUS)[ -]DISEASE$|"
    r"\bUNBRANDED\b|^(DIABETES|OBESITY|CARDIOMETABOLIC|WEIGHT MANAGEMENT)$"
)  # not Merck's "<BRAND> Infectious Disease" strings, which name a product
AREA = [("diabetes", r"DIABET"), ("obesity", r"OBES|WEIGHT"), ("cardiometabolic", r"CARDIOMET")]

# Reviewed fuzzy / contains decisions (raw string -> brand, or None to reject).
ACCEPT: dict[str, str] = {
    "LIXISENATIDE": "Adlyxin",  # Sanofi, PY2013-15, before Adlyxin's 2016 approval
    "Trajenta": "Tradjenta",  # misspelling (fuzzy match, confirmed)
    "Stioloto": "Stiolto",  # misspelling (fuzzy match, confirmed)
    "Actosmet": "Actoplus Met",
}
# Reviewed strings with a class but no brand (raw string -> (molecule, class)).
CLASS_ONLY: dict[str, tuple[str, str]] = {
    "DUAL GLP-1/GLUCAGON AGONIST": ("GLP-1/glucagon dual agonist (pipeline)", "glp1"),
    "SAR425899": ("GLP-1/glucagon dual agonist (pipeline)", "glp1"),  # Sanofi, stopped 2019
}
REJECT: set[str] = {
    "GLYCATE",  # Intra-Sana nutritional supplement
    "Hylenex with Insulin",  # hyaluronidase (Halozyme), an insulin adjunct, not insulin
    "Hylenex with insulin",
}

_MARKS = re.compile(r"[®™©®™©]|\((R|TM|C)\)", re.I)
_PAREN = re.compile(r"\(([^)]*)\)")
_UNIT = r"(MG|MCG|ML|G|UNITS?|IU|U|%)"
_STRENGTH = re.compile(rf"^(\d[\d.]*{_UNIT}?|{_UNIT})(/(\d[\d.]*)?({_UNIT}|DOSE)?)*$")
FORM_WORDS = {
    "INJECTION", "INJ", "INJECTABLE", "TABLET", "TABLETS", "TAB", "TABS", "CAPSULE",
    "CAPSULES", "PEN", "PENS", "AUTOINJECTOR", "SOLUTION", "SUSPENSION", "ORAL",
    "SUBCUTANEOUS", "SC", "SUBQ", "PREFILLED", "SINGLE", "DOSE", "KWIKPEN", "FLEXTOUCH",
    "FLEXPEN", "SOLOSTAR", "TEMPO", "KIT", "PAK", "PACK", "XR", "ER", "XL", "SR", "CR",
    "ONCE", "WEEKLY", "DAILY", "HFA", "DISKUS", "ELLIPTA", "RESPIMAT", "HANDIHALER",
    "AEROSPHERE", "INHALER", "INHALATION", "AEROSOL", "POWDER", "SPRINKLE", "VIAL",
}  # fmt: skip


def _words(s: str) -> str:
    s = re.sub(r"[\u2010-\u2015_,;:+*\"'!?/&-]", " ", s)
    words = [w.strip(".") for w in s.split()]
    return " ".join(w for w in words if w and w not in FORM_WORDS and not _STRENGTH.match(w))


def normalise(s: str | None) -> str:
    """Upper case, no ®/™, no parentheses, strengths or dosage-form words.

    Text in parentheses is dropped ("Ozempic (semaglutide)" -> "OZEMPIC") unless nothing
    else is left ("(semaglutide) injection" -> "SEMAGLUTIDE")."""
    if not isinstance(s, str):
        return ""
    s = _MARKS.sub(" ", s.upper())
    return _words(_PAREN.sub(" ", s)) or _words(" ".join(_PAREN.findall(s)))


KEY_TO_BRAND: dict[str, Brand] = {}
for _b in BRANDS:
    for _k in _b.keys:
        assert _k not in KEY_TO_BRAND, f"duplicate alias {_k}"
        KEY_TO_BRAND[_k] = _b
BY_NAME = {b.brand: b for b in BRANDS}
_KEYS = sorted(KEY_TO_BRAND, key=len, reverse=True)


@dataclass(frozen=True)
class Match:
    brand: str | None
    molecule: str | None
    drug_class: str | None
    method: str  # exact | contains | multi | molecule | non_product | fuzzy | none
    area: str | None = None  # therapeutic area of non-product strings
    candidates: tuple[str, ...] = ()

    @property
    def is_glp1(self) -> bool:
        return self.drug_class in GLP1_CLASSES


def _brand_match(b: Brand, method: str) -> Match:
    return Match(b.brand, b.molecule, b.drug_class, method)


def _molecule(text: str) -> Match | None:
    low = text.lower()
    for pattern, _group, cls in MOLECULES:
        if m := re.search(pattern, low):
            return Match(None, m.group(0), cls, "molecule")
    return None


def match(raw: str | None, drug: bool = True, fuzzy: bool = True) -> Match:
    """Map one Open Payments product string (or Part D brand name) to a brand.

    Molecule, non-product and fuzzy rules apply only when `drug` (device strings such as
    "insulin pump" must not be read as insulin); fuzzy matches are flagged for review."""
    if not isinstance(raw, str) or not raw.strip():
        return Match(None, None, None, "none")
    if raw in ACCEPT:
        return _brand_match(BY_NAME[ACCEPT[raw]], "reviewed")
    if raw in CLASS_ONLY:
        return Match(None, *CLASS_ONLY[raw], "reviewed")
    if raw in REJECT:
        return Match(None, None, None, "none")
    k = normalise(raw)
    if k in KEY_TO_BRAND:
        return _brand_match(KEY_TO_BRAND[k], "exact")
    found: list[Brand] = []
    rest = f" {k} "
    for key in _KEYS:  # longest first, so "BYDUREON BCISE" is consumed before "BYDUREON"
        if len(key) >= 4 and f" {key} " in rest:
            b = KEY_TO_BRAND[key]
            if b not in found:
                found.append(b)
            rest = rest.replace(f" {key} ", " ")
    if len(found) == 1:
        return _brand_match(found[0], "contains")
    if len(found) > 1:
        classes = {b.drug_class for b in found}
        return Match(None, None, classes.pop() if len(classes) == 1 else None, "multi",
                     candidates=tuple(b.brand for b in found))  # fmt: skip
    if not drug:
        return Match(None, None, None, "none")
    if m := _molecule(raw):
        return m
    up = raw.upper().strip()
    if NON_PRODUCT.search(up) or NON_PRODUCT.search(k):
        area = next((a for a, p in AREA if re.search(p, up)), None)
        return Match(None, None, "non_product", "non_product", area=area)
    if fuzzy and len(k) >= 5:
        close = difflib.get_close_matches(k, _KEYS, n=1, cutoff=FUZZY_CUTOFF)
        if close:
            b = KEY_TO_BRAND[close[0]]
            return Match(b.brand, b.molecule, b.drug_class, "fuzzy", candidates=(close[0],))
    return Match(None, None, None, "none")


def partd_match(brnd_name: str | None, gnrc_name: str | None) -> tuple[str | None, Match]:
    """Part D row -> (brand family, match).

    Rows whose brand name is itself a generic name get '<generic name> (generic)'; minor
    brands not in BRANDS (Precose, Glucovance) keep their own name as the family."""
    m = match(brnd_name, fuzzy=False)
    if m.brand:
        return m.brand, m
    g = _molecule(gnrc_name or "") or _molecule(brnd_name or "")
    if g is None:
        return None, Match(None, None, None, "none")
    molecule = (gnrc_name or brnd_name or "").lower()
    generic = _molecule(brnd_name or "") is not None
    family = f"{molecule} (generic)" if generic else brnd_name
    return family, Match(None, molecule, g.drug_class, "molecule" if generic else "minor_brand")


def ndc9(s: str | None) -> str | None:
    """NDC -> 9-digit labeler-product key (5-4). Ambiguous 10-digit undashed codes -> None."""
    if not isinstance(s, str):
        return None
    s = s.strip()
    parts = s.split("-")
    if len(parts) >= 2 and all(p.isdigit() for p in parts[:2]):
        lab, prod = parts[0], parts[1]
        if len(lab) == 4 and len(prod) == 4:
            lab = "0" + lab
        elif len(lab) == 5 and len(prod) == 3:
            prod = "0" + prod
        return lab + prod if len(lab) == 5 and len(prod) == 4 else None
    digits = re.sub(r"\D", "", s)
    return digits[:9] if len(digits) == 11 else None


def ndc_key(s: str | None) -> str | None:
    """9-digit labeler-product key, else the raw digits (ambiguous 10-digit codes)."""
    if (k := ndc9(s)) is not None:
        return k
    digits = re.sub(r"\D", "", s) if isinstance(s, str) else ""
    return f"d{digits}" if len(digits) >= 10 else None


# ---------------------------------------------------------------------------- build

STRINGS = config.DATA_DIR / "work" / "op_product_strings.parquet"
PD_NAMES = config.DATA_DIR / "work" / "partd_drug_names.parquet"
OP = f"read_parquet('{config.PARQUET_DIR}/open_payments/general/*/*.parquet', hive_partitioning = true)"  # noqa: E501
PD = f"read_parquet('{config.PARQUET_DIR}/partd/by_provider_drug/*/*.parquet', hive_partitioning = true)"  # noqa: E501
_MAKER_RE = "|".join(MAKERS.values()) + "|genzyme"
IN_SCOPE_ALL = {b.drug_class for b in BRANDS} | {c for _, _, c in MOLECULES}
REVIEW_MIN_USD = 10_000


def _connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("SET enable_progress_bar_print = false")
    con.execute("SET threads = 6")
    con.execute("SET memory_limit = '8GB'")
    return con


def extract(con) -> None:
    """Distinct product strings (with $) and Part D names, cached in DATA_DIR/work."""
    STRINGS.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"""COPY (
        WITH u AS (SELECT program_year, manufacturer_name, amount_usd, nature_of_payment,
                          len(products) AS nprod, unnest(products) AS p FROM {OP})
        SELECT p.name AS raw_name, p.kind, p.ndc, manufacturer_name, program_year,
               count(*) AS records, sum(amount_usd) AS usd,
               sum(amount_usd / nprod) AS usd_split,
               coalesce(sum(amount_usd / nprod) FILTER (
                   WHERE nature_of_payment NOT IN {NON_PROMOTIONAL}), 0) AS promo_usd_split
        FROM u GROUP BY ALL) TO '{STRINGS}' (FORMAT parquet)""")
    con.execute(f"""COPY (SELECT brnd_name, gnrc_name, min(year) AS first_year,
                                 max(year) AS last_year, sum(tot_clms) AS claims
                          FROM {PD} GROUP BY 1, 2) TO '{PD_NAMES}' (FORMAT parquet)""")


def _row(m: Match) -> dict:
    b = BY_NAME.get(m.brand) if m.brand else None
    return {
        "brand": m.brand,
        "molecule": m.molecule,
        "drug_class": m.drug_class,
        "is_glp1": m.is_glp1,
        "indication": b.indication if b else None,
        "manufacturer": b.manufacturer if b else None,
        "method": m.method,
        "area": m.area,
        "candidates": "; ".join(m.candidates) or None,
    }


def build_op_map(con) -> tuple[pd.DataFrame, pd.DataFrame]:
    s = con.execute(f"""
        SELECT raw_name, string_agg(DISTINCT kind, '/' ORDER BY kind) AS kinds,
               sum(records) AS records, sum(usd_split) AS usd, sum(promo_usd_split) AS promo_usd,
               min(program_year) AS first_year, max(program_year) AS last_year,
               string_agg(DISTINCT manufacturer_name, ' | ' ORDER BY manufacturer_name) AS payers,
               bool_or(regexp_matches(lower(manufacturer_name), '{_MAKER_RE}')) AS glp1_maker
        FROM '{STRINGS}' WHERE raw_name IS NOT NULL GROUP BY 1""").df()
    drugish = s.kinds.fillna("").str.contains("Drug|Biological") | (s.kinds.fillna("") == "")
    rows = [_row(match(r, drug=bool(d))) for r, d in zip(s.raw_name, drugish, strict=True)]
    s = pd.concat([s, pd.DataFrame(rows)], axis=1)
    s["drugish"] = drugish
    s.insert(1, "key", s.raw_name.map(normalise))
    s["maker_consistent"] = [_maker_ok(b, p) for b, p in zip(s.brand, s.payers, strict=True)]
    in_scope = s.drug_class.notna()
    review = s[~in_scope & (s.usd >= REVIEW_MIN_USD) & (s.glp1_maker & drugish)].copy()
    near = s[~in_scope & (s.usd >= REVIEW_MIN_USD) & drugish].raw_name.map(_near_miss)
    review = pd.concat([review, s.loc[near[near.notna()].index]]).drop_duplicates("raw_name")
    review["nearest_alias"] = review.raw_name.map(_near_miss)
    review["reviewer_note"] = review.raw_name.map(lambda r: REVIEW_NOTES.get(r, REVIEWED_DEFAULT))
    s["reviewer_note"] = s.raw_name.map(REVIEW_NOTES)
    s.loc[s.method == "fuzzy", "reviewer_note"] = "fuzzy match: check"
    out = pd.concat([s[in_scope], review]).drop_duplicates("raw_name")
    out["reviewed"] = ~out.raw_name.isin(s[in_scope].raw_name) | out.reviewer_note.notna()
    return out.sort_values(["is_glp1", "drug_class", "brand", "usd"],
                           ascending=[False, True, True, False]), s  # fmt: skip


def _maker_ok(brand, payers: str) -> bool | None:
    """Do the paying companies include the brand's maker? (None when not checked.)"""
    if not isinstance(brand, str) or not BY_NAME[brand].maker_re:
        return None
    return bool(re.search(BY_NAME[brand].maker_re, payers.lower()))


def _near_miss(raw: str) -> str | None:
    """Closest alias at a loose cutoff, to surface misspellings for hand review."""
    k = normalise(raw)
    close = difflib.get_close_matches(k, _KEYS, n=1, cutoff=0.7) if len(k) >= 5 else []
    return close[0] if close else None


REVIEWED_DEFAULT = "reviewed 2026-10-23: not a GLP-1, comparator or control drug"
REVIEW_NOTES: dict[str, str] = {
    "DUAL GLP-1/GLUCAGON AGONIST": "Sanofi pipeline compound (2017-18); GLP-1 class, no brand",
    "SAR425899": "Sanofi GLP-1/glucagon dual agonist, discontinued 2019; GLP-1 class, no brand",
    "GLARGINE": "insulin glargine, brand not stated (Sanofi: Lantus or Toujeo)",
    "LOVENOX": "reviewed: injectable anticoagulant (enoxaparin); not in the oral class",
    "PRALUENT": "reviewed: PCSK9 inhibitor; lipid-lowering but not a statin",
    "MYALEPT": "reviewed: metreleptin (lipodystrophy); not a diabetes-class drug",
    "Hylenex with Insulin": "reviewed: hyaluronidase, not insulin",
    "Tactoset": "reviewed: device (contains 'ACTOS' as a substring)",
}


def build_partd_map(con) -> pd.DataFrame:
    n = con.execute(f"SELECT * FROM '{PD_NAMES}'").df()
    out = []
    for r in n.itertuples():
        fam, m = partd_match(r.brnd_name, r.gnrc_name)
        if fam is None:
            continue
        out.append({"brnd_name": r.brnd_name, "gnrc_name": r.gnrc_name, "brand_family": fam,
                    **_row(m), "first_year": r.first_year, "last_year": r.last_year,
                    "claims": r.claims})  # fmt: skip
    return pd.DataFrame(out).sort_values(["drug_class", "brand_family", "claims"],
                                         ascending=[True, True, False])  # fmt: skip


def build_ndc_map(con, op_map: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    names = op_map[op_map.brand.notna() & op_map.method.isin(["exact", "contains"])]
    con.register("names", names[["raw_name", "brand"]])
    df = con.execute(f"""SELECT n.brand, s.ndc, sum(s.records) AS records
                         FROM '{STRINGS}' s JOIN names n USING (raw_name)
                         WHERE s.ndc IS NOT NULL GROUP BY 1, 2""").df()
    df["ndc9"] = df.ndc.map(ndc_key)
    g = df.dropna(subset=["ndc9"]).groupby(["ndc9", "brand"]).records.sum().reset_index()
    g["share"] = g.records / g.groupby("ndc9").records.transform("sum")
    best = g.sort_values("share").groupby("ndc9").tail(1)
    ndc_map = best[best.share >= 0.95].sort_values(["brand", "ndc9"])
    conflicts = g[~g.set_index(["ndc9", "brand"]).index.isin(
        ndc_map.set_index(["ndc9", "brand"]).index)]  # fmt: skip
    # name-less product slots recovered through the NDC
    nameless = con.execute(f"""SELECT ndc, program_year, sum(records) AS records,
                                      sum(usd_split) AS usd
                               FROM '{STRINGS}' WHERE raw_name IS NULL AND ndc IS NOT NULL
                               GROUP BY 1, 2""").df()
    nameless["brand"] = nameless.ndc.map(ndc_key).map(dict(zip(ndc_map.ndc9, ndc_map.brand,
                                                             strict=True)))  # fmt: skip
    stats = {
        "ndc_keys_mapped": int(len(ndc_map)),
        "records_with_ndc_conflicting_brand": int(conflicts.records.sum()),
        "nameless_records": int(nameless.records.sum()),
        "nameless_records_recovered": int(nameless[nameless.brand.notna()].records.sum()),
        "nameless_glp1_records_recovered": int(
            nameless[nameless.brand.map(lambda b: b in BY_NAME
                                        and BY_NAME[b].drug_class in GLP1_CLASSES)]
            .records.sum()),
    }  # fmt: skip
    return ndc_map[["ndc9", "brand", "records", "share"]], stats


def coverage(con, all_strings: pd.DataFrame) -> pd.DataFrame:
    """Per year: GLP-1-maker promotional $, how much names a product, how much is resolved."""
    resolved = all_strings[all_strings.drug_class.notna() | all_strings.reviewed_flag]
    con.register("resolved", resolved[["raw_name", "drug_class"]])
    totals = con.execute(f"""
        SELECT program_year,
               sum(amount_usd) FILTER (WHERE nature_of_payment NOT IN {NON_PROMOTIONAL})
                   AS maker_promo_usd,
               sum(amount_usd) FILTER (WHERE nature_of_payment NOT IN {NON_PROMOTIONAL}
                                         AND len(products) > 0) AS with_product_usd
        FROM {OP} WHERE regexp_matches(lower(manufacturer_name), '{_MAKER_RE}')
        GROUP BY 1""").df()
    by = con.execute(f"""
        SELECT s.program_year,
               sum(s.promo_usd_split) FILTER (WHERE r.raw_name IS NOT NULL) AS resolved_usd,
               sum(s.promo_usd_split) FILTER (WHERE r.drug_class IN {GLP1_CLASSES})
                   AS glp1_usd,
               sum(s.promo_usd_split) FILTER (WHERE r.drug_class IS NOT NULL
                                               AND r.drug_class <> 'non_product') AS in_scope_usd
        FROM '{STRINGS}' s LEFT JOIN resolved r USING (raw_name)
        WHERE regexp_matches(lower(s.manufacturer_name), '{_MAKER_RE}')
        GROUP BY 1""").df()
    c = totals.merge(by, on="program_year").sort_values("program_year")
    c["share_with_product"] = c.with_product_usd / c.maker_promo_usd
    c["share_resolved_of_named"] = c.resolved_usd / c.with_product_usd
    c["share_glp1_of_named"] = c.glp1_usd / c.with_product_usd
    return c


def glp1_by_brand_year(con, op_map: pd.DataFrame) -> pd.DataFrame:
    """Records and promotional $ (split across a record's products) per GLP-1 brand-year.
    Public file: brand-years with fewer than 11 records (so < 11 recipients) are blanked."""
    g = op_map[op_map.is_glp1 == True][["raw_name", "brand", "molecule"]]  # noqa: E712
    con.register("glp1_names", g)
    return mask_small(
        con.execute(f"""
        SELECT coalesce(n.brand, n.molecule) AS brand, s.program_year, sum(s.records) AS records,
               sum(s.promo_usd_split) AS promo_usd
        FROM '{STRINGS}' s JOIN glp1_names n USING (raw_name)
        GROUP BY ALL ORDER BY 1, 2""").df(),
        "records",
        ["promo_usd"],
    )


def _counts(s: pd.Series) -> dict[str, int]:
    return {str(k): int(v) for k, v in s.value_counts().items()}


def build() -> dict:
    con = _connect()
    if not STRINGS.exists() or not PD_NAMES.exists():
        extract(con)
    op_map, all_strings = build_op_map(con)
    all_strings["reviewed_flag"] = all_strings.raw_name.isin(op_map[op_map.reviewed].raw_name)
    pd_map = build_partd_map(con)
    ndc_map, ndc_stats = build_ndc_map(con, op_map)
    cov = coverage(con, all_strings)

    cols = ["raw_name", "key", "brand", "molecule", "drug_class", "is_glp1", "indication",
            "manufacturer", "method", "area", "candidates", "maker_consistent", "kinds",
            "first_year", "last_year", "records", "usd", "promo_usd", "payers",
            "nearest_alias", "reviewer_note"]  # fmt: skip
    op_map = op_map.reindex(columns=cols)
    ref = config.REFERENCE_DIR
    op_map.to_csv(ref / "drug_name_map.csv", index=False, float_format="%.2f")
    pd_map.to_csv(ref / "partd_drug_map.csv", index=False)
    ndc_map.to_csv(ref / "drug_ndc_map.csv", index=False, float_format="%.4f")

    unmapped = (
        all_strings[
            all_strings.drug_class.isna() & ~all_strings.reviewed_flag & all_strings.drugish
        ]
        .sort_values("usd", ascending=False)
        .head(100)[["raw_name", "kinds", "records", "usd", "promo_usd", "payers"]]
    )
    config.QA_DIR.mkdir(parents=True, exist_ok=True)
    unmapped.to_csv(config.QA_DIR / "drug_map_unmapped_top.csv", index=False,
                    float_format="%.0f")  # fmt: skip
    cov.to_csv(config.QA_DIR / "drug_map_coverage_by_year.csv", index=False, float_format="%.4f")
    glp1_by_brand_year(con, op_map).to_csv(
        config.QA_DIR / "drug_map_glp1_by_brand_year.csv", index=False, float_format="%.0f"
    )

    glp = op_map[op_map.is_glp1 == True]  # noqa: E712
    pdg = pd_map[pd_map.is_glp1]
    stats = {
        "op_strings_total": int(len(all_strings)),
        "op_strings_in_map": int(len(op_map)),
        "op_strings_by_method": _counts(op_map.method),
        "op_strings_by_class": _counts(op_map.drug_class.fillna("reviewed_out_of_scope")),
        "glp1_strings": int(len(glp)),
        "glp1_records": int(glp.records.sum()),
        "glp1_usd": round(float(glp.usd.sum()), 2),
        "glp1_promo_usd": round(float(glp.promo_usd.sum()), 2),
        "glp1_strings_maker_inconsistent": glp[glp.maker_consistent == False]  # noqa: E712
        .raw_name.tolist(),
        "glp1_brands_in_op": sorted(glp.brand.dropna().unique().tolist()),
        "partd_rows_in_map": int(len(pd_map)),
        "partd_glp1_families": sorted(pdg.brand_family.unique().tolist()),
        "partd_by_class": _counts(pd_map.drug_class),
        "reviewed_out_of_scope": int((op_map.drug_class.isna()).sum()),
        "unreviewed_drug_strings_over_10k": int(
            (all_strings.drug_class.isna() & ~all_strings.reviewed_flag & all_strings.drugish
             & (all_strings.usd >= REVIEW_MIN_USD)).sum()),
        "ndc": ndc_stats,
        "coverage_glp1_makers": {
            int(r.program_year): {
                "share_with_product": round(float(r.share_with_product), 4),
                "share_resolved_of_named": round(float(r.share_resolved_of_named), 4),
                "share_glp1_of_named": round(float(r.share_glp1_of_named), 4),
            }
            for r in cov.itertuples()
        },
    }  # fmt: skip
    (config.QA_DIR / "drug_map.json").write_text(json.dumps(stats, indent=1, default=str))
    return stats


if __name__ == "__main__":
    print(json.dumps(build(), indent=1, default=str))
