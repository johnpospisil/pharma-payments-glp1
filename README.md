# Lunch, Speaking Fees and Semaglutide

*Industry payments and GLP-1 prescribing in Medicare Part D.* Work in progress.

This project links CMS Open Payments (what drug makers pay doctors) to Medicare Part D prescribing, then tests whether GLP-1 prescribing of a brand (Trulicity, Victoza and Ozempic in the event study; Mounjaro through brand share) rises after a prescriber starts receiving payments for that brand, compared with similar prescribers who received none. It measures association under careful controls, not proof of influence, and it never identifies individual prescribers.

- Plan: [02-pharma-payments-glp1.md](02-pharma-payments-glp1.md)
- Data provenance: `DATA.md` (from P01)

## Setup

```bash
uv sync
cp .env.example .env   # set PPG_RAW_DIR / PPG_DATA_DIR
make check-env
make test
```
