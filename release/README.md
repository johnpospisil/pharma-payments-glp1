# Released datasets

Two datasets from *After the Free Lunch: Drug-Maker Payments and GLP-1 Brand Choice in
Medicare* (https://github.com/johnpospisil/pharma-payments-glp1). Both are built by `make release` from the project's pipeline; neither
contains NPIs, names or prescriber-level rows.

| Folder | What it is | Data card |
|---|---|---|
| `drug_name_map/` | Open Payments product names and Part D drug names mapped to GLP-1 and comparator brands | [DATACARD.md](drug_name_map/DATACARD.md) |
| `specialty_state_panel/` | Prescribers, promotional payments and GLP-1 prescribing by specialty x state x brand x year, privacy-protected | [DATACARD.md](specialty_state_panel/DATACARD.md) |

File sizes, row counts and SHA-256 checksums: `manifest.json` and `SHA256SUMS`
(check with `shasum -a 256 -c SHA256SUMS`). Licence: [LICENSE.md](LICENSE.md).
