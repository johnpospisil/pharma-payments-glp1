"""Drug-name map (P07): normaliser, matcher, Part D families, NDC keys, committed CSVs."""

import pandas as pd
import pytest

from ppg import config
from ppg.build.drug_map import BRANDS, match, ndc9, ndc_key, normalise, partd_match

# raw string -> expected brand (None = must not map to any brand)
OP_VARIANTS = [
    ("Ozempic", "Ozempic"),
    ("OZEMPIC", "Ozempic"),
    ("Ozempic®", "Ozempic"),
    ("OZEMPIC® (semaglutide) injection 0.25 mg", "Ozempic"),
    ("Ozempic (semaglutide)", "Ozempic"),
    ("Ozempic 2 mg/3 mL pen", "Ozempic"),
    ("ozempic pen", "Ozempic"),
    ("Ozempik", "Ozempic"),  # misspelling -> fuzzy
    ("Rybelsus", "Rybelsus"),
    ("RYBELSUS tablets", "Rybelsus"),
    ("Wegovy", "Wegovy"),
    ("WEGOVY™ 2.4 mg", "Wegovy"),
    ("Victoza", "Victoza"),
    ("VICTOZA", "Victoza"),
    ("Victoza 3-Pak", "Victoza"),
    ("Victoza 2-Pak", "Victoza"),
    ("Saxenda", "Saxenda"),
    ("TRULICITY", "Trulicity"),
    ("TRULICITY 1.5MG/0.5ML", "Trulicity"),
    ("Trulicty", "Trulicity"),
    ("MOUNJARO", "Mounjaro"),
    ("Mounjaro 2.5 mg/0.5 mL", "Mounjaro"),
    ("MOUNJARO KwikPen", "Mounjaro"),
    ("ZEPBOUND", "Zepbound"),
    ("Zepbound™ (tirzepatide) injection", "Zepbound"),
    ("BYETTA", "Byetta"),
    ("BYDUREON", "Bydureon"),
    ("BYDUREON WEEKLY", "Bydureon"),
    ("BYDUREON PEN", "Bydureon"),
    ("BYDUREON BCISE", "Bydureon"),
    ("Bydureon BCise", "Bydureon"),
    ("BYDUREON DCP", "Bydureon"),
    ("ADLYXIN", "Adlyxin"),
    ("LIXISENATIDE", "Adlyxin"),  # reviewed: pre-approval Adlyxin
    ("TANZEUM", "Tanzeum"),
    ("SOLIQUA", "Soliqua"),
    ("SOLIQUA 100/33", "Soliqua"),
    ("Soliqua 100-33", "Soliqua"),
    ("Xultophy", "Xultophy"),
    ("Xultophy 100/3.6", "Xultophy"),
    ("JARDIANCE", "Jardiance"),
    ("FARXIGA", "Farxiga"),
    ("JANUVIA Diabetes", "Januvia"),
    ("Trajenta", "Tradjenta"),  # reviewed misspelling
    ("Tresiba", "Tresiba"),
    ("Humalog Mix 75-25", "Humalog"),
    ("Lantus SoloStar", "Lantus"),
    ("TOUJEO", "Toujeo"),
    ("Toujeo 300 Units/mL", "Toujeo"),
    ("Basaglar KwikPen", "Basaglar"),
    ("CRESTOR", "Crestor"),
    ("Lipitor", "Lipitor"),
    ("VYTORIN Cardiovascular", "Vytorin"),
    ("Eliquis", "Eliquis"),
    ("XARELTO", "Xarelto"),
    ("Xarelto DVT PE", "Xarelto"),
    ("SYMBICORT", "Symbicort"),
    ("BREZTRI AEROSPHERE", "Breztri"),
    ("Breo Ellipta", "Breo"),
    ("Trelegy Ellipta", "Trelegy"),
    # false positives seen in the data: must not map
    ("PLUVICTO", None),
    ("APC II Victory Series", None),
    ("APC Flash-Free Victory Series Low Profile", None),
    ("Victory Guidewires", None),
    ("STELARA", None),
    ("EXPAREL", None),
    ("CAPLYTA", None),
    ("Leqembi", None),
    ("RELISTOR", None),
    ("Tactoset", None),
    ("GLYCATE", None),
    ("Hylenex with Insulin", None),
    ("DUPIXENT", None),
    ("", None),
    (None, None),
]


@pytest.mark.parametrize(("raw", "brand"), OP_VARIANTS)
def test_op_variants(raw, brand):
    assert match(raw).brand == brand


def test_variant_count():
    assert len(OP_VARIANTS) >= 50


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Ozempic®", "OZEMPIC"),
        ("OZEMPIC® (semaglutide) injection 0.25 mg", "OZEMPIC"),
        ("(semaglutide) injection", "SEMAGLUTIDE"),
        ("Victoza 3-Pak", "VICTOZA"),
        ("SOLIQUA 100/33", "SOLIQUA"),
        ("TRULICITY 1.5MG/0.5ML", "TRULICITY"),
        ("Breztri Aerosphere", "BREZTRI"),
        ("OZEMPIC/WEGOVY", "OZEMPIC WEGOVY"),
        ("  trulicity  ", "TRULICITY"),
        (None, ""),
    ],
)
def test_normalise(raw, expected):
    assert normalise(raw) == expected


def test_multi_brand_string_has_no_brand():
    m = match("OZEMPIC/WEGOVY")
    assert m.method == "multi" and m.brand is None
    assert m.drug_class == "glp1" and set(m.candidates) == {"Ozempic", "Wegovy"}
    assert match("JANUVIA JANUMET").drug_class == "dpp4"


def test_molecule_and_classes():
    assert match("(semaglutide) injection").molecule == "semaglutide"
    assert match("(semaglutide) injection").is_glp1
    assert match("Atorvastatin Calcium").drug_class == "statin"
    assert match("Nystatin").drug_class is None  # not a statin
    assert match("GLARGINE").drug_class == "insulin"
    assert match("SAR425899").drug_class == "glp1"
    assert match("Soliqua").is_glp1 and match("Xultophy").is_glp1
    assert not match("Tresiba").is_glp1


def test_device_strings_skip_molecule_rules():
    assert match("insulin pump", drug=False).drug_class is None
    assert match("Omnipod insulin management", drug=False).drug_class is None
    assert match("Medical Device").drug_class is None  # supply rule needs insulin context
    assert match("GABLOFEN 1 mL in 1 SYRINGE, GLASS").drug_class is None
    assert partd_match("Ulticare", "Syr-Nd,ins,0.3/Container,empty")[1].drug_class == (
        "diabetes_supply"
    )
    assert partd_match("Luer-Lok Syringe", "Syringe, Disposable, 1ml")[0] is None


@pytest.mark.parametrize(
    ("raw", "area"),
    [
        ("NO PRODUCT DISCUSSED", None),
        ("NO PRODUCT DISCUSSED - DIABETES", "diabetes"),
        ("DIABETES - DISEASE", "diabetes"),
        ("Non-Product", None),
        ("NO_PRODUCT", None),
        ("Disease State", None),
    ],
)
def test_non_product(raw, area):
    m = match(raw)
    assert m.drug_class == "non_product" and m.area == area


def test_named_product_with_area_is_not_non_product():
    assert match("CANCIDAS Infectious Disease").drug_class is None


@pytest.mark.parametrize(
    ("brnd", "gnrc", "family", "cls"),
    [
        ("Ozempic", "Semaglutide", "Ozempic", "glp1"),
        ("Victoza 3-Pak", "Liraglutide", "Victoza", "glp1"),
        ("Victoza 2-Pak", "Liraglutide", "Victoza", "glp1"),
        ("Liraglutide", "Liraglutide", "liraglutide (generic)", "glp1"),  # D15
        ("Bydureon Bcise", "Exenatide Microspheres", "Bydureon", "glp1"),
        ("Bydureon Pen", "Exenatide Microspheres", "Bydureon", "glp1"),
        ("Soliqua 100-33", "Insulin Glargine/Lixisenatide", "Soliqua", "glp1_insulin_combo"),
        ("Xultophy 100-3.6", "Insulin Degludec/Liraglutide", "Xultophy", "glp1_insulin_combo"),
        ("Atorvastatin Calcium", "Atorvastatin Calcium", "atorvastatin calcium (generic)",
         "statin"),
        ("Crestor", "Rosuvastatin Calcium", "Crestor", "statin"),
        ("Eliquis", "Apixaban", "Eliquis", "anticoagulant"),
        ("Warfarin Sodium", "Warfarin Sodium", "warfarin sodium (generic)", "anticoagulant"),
        ("Dapagliflozin-Metformin Er", "Dapaglifloz Propaned/Metformin",
         "dapaglifloz propaned/metformin (generic)", "sglt2"),
        ("Glucovance", "Glyburide/Metformin Hcl", "Glucovance", "sulfonylurea"),
        ("Unifine Pentips", "Pen Needle, Diabetic", "Unifine Pentips", "diabetes_supply"),
        ("Easy Touch", "Syringe-Needle,insulin,0.5 Ml", "Easy Touch", "diabetes_supply"),
        ("Symlinpen 120", "Pramlintide Acetate", "Symlin", "antidiabetic_other"),
    ],
)  # fmt: skip
def test_partd(brnd, gnrc, family, cls):
    fam, m = partd_match(brnd, gnrc)
    assert (fam, m.drug_class) == (family, cls)


@pytest.mark.parametrize(
    ("brnd", "gnrc"),
    [("Nystatin", "Nystatin"), ("Gattex", "Teduglutide"), ("Primaxin", "Imipenem/Cilastatin")],
)
def test_partd_lookalikes_unmapped(brnd, gnrc):
    assert partd_match(brnd, gnrc)[0] is None


@pytest.mark.parametrize(
    ("ndc", "key"),
    [
        ("0169-4132-12", "001694132"),  # 4-4-2
        ("06678-002-26", "066780002"),  # 5-3-2
        ("00002-1433-80", "000021433"),  # 5-4-2
        ("00002143380", "000021433"),  # 11 digits
        ("0002143380", None),  # 10 digits, ambiguous
        (None, None),
    ],
)
def test_ndc9(ndc, key):
    assert ndc9(ndc) == key


def test_ndc_key_falls_back_to_digits():
    assert ndc_key("0667800226") == "d0667800226"
    assert ndc_key("JDR") is None


def test_aliases_unique_and_brands_unique():
    names = [b.brand for b in BRANDS]
    assert len(names) == len(set(names))  # duplicate aliases fail at import


# ---- committed reference files (reviewed; drug_name_map.csv is released publicly)

GLP1_BRANDS = {b.brand for b in BRANDS if b.drug_class in ("glp1", "glp1_insulin_combo")}


@pytest.fixture(scope="module")
def op_map():
    return pd.read_csv(config.REFERENCE_DIR / "drug_name_map.csv")


@pytest.fixture(scope="module")
def pd_map():
    return pd.read_csv(config.REFERENCE_DIR / "partd_drug_map.csv")


def test_map_covers_every_glp1_brand(op_map, pd_map):
    assert GLP1_BRANDS <= set(op_map[op_map.is_glp1 == True].brand.dropna())  # noqa: E712
    assert (GLP1_BRANDS - {"Saxenda"}) <= set(pd_map.brand_family)  # Saxenda: obesity only


def test_map_rows_unique_and_consistent(op_map):
    assert op_map.raw_name.is_unique
    mapped = op_map[op_map.brand.notna()]
    for r in mapped.itertuples():  # the committed CSV agrees with the code
        assert match(r.raw_name, drug=True).brand == r.brand, r.raw_name


def test_glp1_payers_are_the_makers(op_map):
    glp = op_map[(op_map.is_glp1 == True) & op_map.brand.notna()]  # noqa: E712
    assert glp.maker_consistent.all()


def test_no_false_positive_rows(op_map):
    bad = op_map[op_map.raw_name.str.contains("Victory|PLUVICTO", case=False)]
    assert bad.brand.isna().all()


def test_partd_map_has_no_lookalikes(pd_map):
    assert not pd_map.gnrc_name.str.contains("Nystatin|Teduglutide|Cilastatin|Pentostatin").any()
