# After the Free Lunch: Drug-Maker Payments and GLP-1 Brand Choice in Medicare

**[Read the article](https://johnpospisil.github.io/pharma-payments-glp1/)** · **[Explore by specialty and state](https://johnpospisil.github.io/pharma-payments-glp1/app/)** · **[Datasets on Hugging Face](https://huggingface.co/datasets/audiofreak7/glp1-payments-prescribing-medicare)**

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="report/figures/final/hero_brand_share_dark.png">
  <img src="report/figures/final/hero_brand_share.png" alt="Event-study chart: the paid brand's share of a physician's GLP-1 claims, before and after the first payment, for Trulicity, Ozempic, Mounjaro and Victoza. Shares are flat or noisy before payment and rise a few points afterwards for every brand except Victoza, whose share falls.">
</picture>

<!-- findings: every number below is a value in report/_variables.yml (tests/test_readme.py) -->
Does a doctor's first payment from a GLP-1 maker (a sponsored lunch, most often) come before a shift toward that company's brand? This project links every promotional payment in CMS Open Payments to the same prescribers' Medicare Part D claims, 2013–2024, and follows 280,610 physicians brand by brand with a pre-registered staggered event study.

## What we found

1. **Paid physicians' GLP-1 prescribing tilts a few points toward the paying brand.** The paid brand's share of their GLP-1 claims rises by +4.1 (Trulicity), +3.0 (Ozempic) and +5.3 (Mounjaro) percentage points against not-yet-paid physicians, mostly at the expense of direct competitors; Victoza's falls (−4.8). Bounding Medicare's hidden small counts against the result shrinks the gains to 1.7–1.8 points.
2. **Paid physicians' practices were already growing.** They become more likely to have 11 or more claims of the brand (+12.0 / +5.5 / +13.7 points for Trulicity, Victoza and Ozempic), but their statin prescribing rises too (+6.4 / +7.9 / +7.1), so much of the volume increase reflects whom companies pay.
3. **The money is concentrated.** Drug makers paid $424.5 million in promotional payments naming a GLP-1 (2013–2025). Through 2024 the top 1% of paid prescribers received 76% of the dollars, mostly as speaker fees; the median paid prescriber received $109 over twelve years.

**What this doesn't show:** that payments caused prescribing. Companies choose whom to pay, and the share shift is *consistent with* influence but could also reflect paid doctors adopting new brands sooner.
<!-- /findings -->

No individual prescriber is named, mapped or ranked anywhere in this project: public tables show only groups of 11 or more prescribers, with further protection against recovering hidden cells ([article, Ethics](https://johnpospisil.github.io/pharma-payments-glp1/#ethics-why-no-individual-doctors-appear)).

## Reproduce

Everything comes from public federal data (CMS Open Payments, Medicare Part D; sources and checksums in [DATA.md](DATA.md)).

```bash
uv sync                  # Python 3.12, locked dependencies
cp .env.example .env     # PPG_RAW_DIR: raw downloads (~70 GB); PPG_DATA_DIR: Parquet (~15 GB)
make check-env
make all                 # download, build, models, figures, article, explorer, release, QA (~2 h)
make test                # unit tests; tests marked `data` need the built data
```

Without the raw data, `make report` renders the article from the committed results in `report/qa`, and `make serve-app` serves the explorer at http://localhost:8766/app/. Every number in the article is read from `report/qa`; `make qa` checks each against its source and runs the disclosure audit.

## Where things are

| | |
|---|---|
| [PREREGISTRATION.md](PREREGISTRATION.md) | The locked analysis plan (tag `prereg-v1`) and every dated deviation |
| [docs/results.md](docs/results.md) | Full results log, prompt by prompt, including subgroups |
| [docs/qa.md](docs/qa.md) | QA checklist, rebuild checks and the claims that are still weak |
| [docs/review-triage.md](docs/review-triage.md) | Red-team review: every point and what was done about it |
| [docs/literature.md](docs/literature.md) | Prior work and what is new here |
| [release/](release/README.md) | Drug-name map and the specialty × state panel, with data cards; also on [Hugging Face](https://huggingface.co/datasets/audiofreak7/glp1-payments-prescribing-medicare) |
| `src/ppg/` | The pipeline: `ingest`, `build`, `models`, `viz`, `report`, `app`, `release`, `qa` |

## Licence

Code: [MIT](LICENSE). Released datasets: CC0 1.0. Source data: US public domain (CMS).
