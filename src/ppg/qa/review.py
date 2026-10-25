"""P24 red-team review: the extra numbers the review asked for, written to report/qa so the article
can quote them (every article number comes from report/qa).

    share_sensitivity   DEV-11: the paid brand's share under suppression bounds, on 30-day fills
                        and in the high-volume subsample (from ppg.models.switching sensitivity)
    promo_usd           GLP-1 promotional dollars by period, and the part naming obesity-indicated
                        brands (Wegovy, Saxenda, Zepbound), which the article's totals include

    python -m ppg.qa.review        -> report/qa/review_p24.json
"""

from __future__ import annotations

import json

import duckdb

from ppg import config

BRANDS = ("Trulicity", "Ozempic", "Mounjaro", "Victoza")
OBESITY = ("Wegovy", "Saxenda", "Zepbound")


def promo_usd() -> dict:
    r = duckdb.sql(f"""
        SELECT program_year <= 2024 AS thru_2024, brand IN {OBESITY} AS obesity,
               sum(amount_usd * brand_slots / nprod) AS usd
        FROM '{config.PARQUET_DIR}/payments/record_brand.parquet'
        WHERE drug_class IN ('glp1', 'glp1_insulin_combo') AND promotional AND amount_usd > 0
        GROUP BY ALL""").df()
    tot = r.usd.sum()
    ob = r[r.obesity].usd.sum()
    return {
        "total_2013_2025": round(float(tot), 2),
        "obesity_brands_2013_2025": round(float(ob), 2),
        "obesity_share_2013_2025": round(float(ob / tot), 4),
        "total_2013_2024": round(float(r[r.thru_2024].usd.sum()), 2),
    }


def build() -> dict:
    sens = {b: json.loads((config.QA_DIR / "es" / f"switching_sensitivity_{b}.json").read_text())
            for b in BRANDS}  # fmt: skip
    out = {"share_sensitivity": sens, "promo_usd": promo_usd()}
    (config.QA_DIR / "review_p24.json").write_text(json.dumps(out, indent=1, default=float))
    return out


if __name__ == "__main__":
    print(json.dumps(build()["promo_usd"], indent=1))
