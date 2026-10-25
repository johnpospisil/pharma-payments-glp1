# Project page blurb (johnpospisil.com/data-science/)

**Status:** draft. Nothing is published without John.
**Image:** `report/figures/social/hero_brand_share_1200x675.png` (dark variant: `hero_brand_share_1200x675_dark.png`).

## Card (short)

**After the Free Lunch: Drug-Maker Payments and GLP-1 Brand Choice in Medicare**
Does a drug maker's first payment to a doctor come before a shift toward its brand? A pre-registered event study of 280,610 Medicare physicians, 2013–2024: the paid brand gains a few points of share, but paid practices were already growing.
*Python, DuckDB, R, Quarto, causal inference · [Article](https://johnpospisil.github.io/pharma-payments-glp1/) · [Explorer](https://johnpospisil.github.io/pharma-payments-glp1/app/) · [Code](https://github.com/johnpospisil/pharma-payments-glp1)*

## Longer description

I linked every promotional payment naming a GLP-1 in CMS Open Payments ($424.5 million, 2013–2025) to the same prescribers' Medicare Part D claims and followed physicians brand by brand around their first payment, against similar physicians not yet paid. After the first payment, the paid brand's share of their GLP-1 claims rises by +4.1 (Trulicity), +3.0 (Ozempic) and +5.3 (Mounjaro) points, or 1.7–1.8 when Medicare's hidden small counts are bounded against the result. Statin prescribing rises too, so much of the volume increase reflects whom companies pay.

What the project shows about how I work:

- **Pre-registration:** the analysis plan was locked before any post-payment comparison, and every later change is a public, dated deviation, including the ones that weakened the headline.
- **Falsification first:** negative-control drugs and payments, placebo timing, matching on pre-payment trajectories, and suppression bounds, reported whether they help or not.
- **Privacy by design:** no prescriber is identifiable. The interactive explorer was red-teamed with a linear-programming attack and rebuilt until no hidden cell could be recovered.
- **Reproducible:** one command rebuilds every number and chart from the raw federal files; every number in the article comes from the pipeline, never typed by hand.
