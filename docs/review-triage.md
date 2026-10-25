# P24 red-team review: triage

Six independent reviews ran on 2026-10-24: a health economist, a clinical pharmacist and a data journalist each reviewed the article (`report/index.qmd`) and the explorer (`app/`) separately. Every point is triaged as **fix** (changed), **disclose** (stated in the article or app, not changed), or **reject** (with a reason). Numbers quoted here come from `report/qa`.

## What changed most

1. **The brand-share headline shrinks** (economist and pharmacist, article #1). The share is computed from visible rows, so a paid brand crossing Medicare's 11-claim line looks like a share gain. A new sensitivity (DEV-11, `report/qa/review_p24.json`) bounds the hidden rows against the result. The gain falls from +4.1 / +3.0 / +5.3 to +1.8 / +1.7 / +1.8 pp (Trulicity / Ozempic / Mounjaro), below the 2 pp smallest effect of interest. Fills and the high-volume subsample reproduce the original estimates. The article now gives the range everywhere the number appears.
2. **The explorer's disclosure control was breakable** (data journalist, app #1–3). An LP attack recovered 251 withheld paid counts and 176 regular counts exactly, and bounded some dominance-withheld dollars tightly. Rebuilt with four protections:
   - one public "withheld" code;
   - no cross-brand total;
   - NPs and PAs outside the specialty total;
   - an LP protection audit with complementary suppression (`ppg.app.protect`, D47), checked by `make qa` and `tests/test_explorer.py`.

   The reviewer's own script now recovers 0 cells.
3. **The pre-2021 jump in the explorer was an artefact** (economist, journalist). "All specialties" counted NPs and PAs in the denominator before their payments were reported. The specialty total is now "All physicians", with NPs and PAs shown separately.

## Article

| # | Reviewer | Point | Triage | What was done |
|---|---|---|---|---|
| A1 | Economist, pharmacist | Share outcome partly a suppression artefact | **Fix** | DEV-11 bounds; range in the lead box, Result 1, hero caption and footnote, table, limitations |
| A2 | Journalist, economist | Lead switched to brand share after the primary failed; estimator changed after first results; neither disclosed | **Fix** | Stated in "How we measured it", with the first-reported +8.4 / +1.2 / +7.4 |
| A3 | Journalist, economist | First lead bullet overstates the share result (W2, D29) | **Fix** | Rewritten with the bound, the log-odds caveat and Victoza; new "not a precise effect size" line |
| A4 | All three | Mounjaro's flat pre-trend is near-automatic; its window is only 2022–24, during shortages | **Fix** | Called "rests on about one year"; follow-up window stated; shortages named |
| A5 | Journalist, economist | Pre-trends quoted selectively (Victoza; matched Trulicity p = 0.007) | **Fix** | Result 1 and the table give all four, matched and unmatched |
| A6 | Journalist | Title oversells ("Speaking Fees", "Semaglutide") | **Your call** | Title unchanged pending your decision |
| A7 | Journalist | Hero title temporal-causal; endpoint labels differ from text; "keeps rising" wrong; band clipped | **Fix** | Title "tilted toward the paying brand, except Victoza"; labels show the 0–3 average; text "rises for one to two years, then levels off"; axis unclipped |
| A8 | Journalist | Hero and 1b alt text misdescribe | **Fix** | Hero alt rewritten (pre-trends per brand, averages, bound) |
| A9 | Journalist | Chart 5 uses e = 2, the peak year | **Disclose** | Caption: e = 2 is the latest year observed for Mounjaro's 2022 cohort. Re-estimating at e = 3 would drop Mounjaro |
| A10 | Journalist, pharmacist | Named confounders missing (CV labels 2017/2020, shortages, formularies) | **Fix** | In "What this doesn't mean", Limitations, explorer events |
| A11 | Journalist, pharmacist | Concentration totals mix periods; obesity brands included; no "doesn't mean" pair | **Fix** | Periods stated; obesity-brand $66.7M (16%) disclosed; "fees pay for services" added; median $109 in the lead box |
| A12 | Journalist | Overreaching phrases (fills vs prescribers, company intent, heading, spillover, "every prescriber") | **Fix** | All five reworded |
| A13 | Journalist, economist | Robustness rows read as support for causation; placebo and HonestDiD described generously | **Fix** | Table note; HonestDiD correctly described ("year-to-year change") with the linear-trend bound (about half remains); placebo up to +3.0 pp stated |
| A14 | Journalist | State-map note points at individuals; map mostly maps speakers | **Fix** | Generic "withheld to protect privacy"; "Highest" removed; speaker caveat in text and chart note |
| A15 | Journalist | Jargon | **Fix** | pp defined; "How solid is this?" rewritten in plain words; SMD numbers removed from the text |
| A16 | Journalist, pharmacist | Victoza story post hoc and mistimed | **Fix** | "One possible reason, not tested", with the weekly-drug and 61%-starting-share account |
| A17 | Journalist | Ethics note gaps (meal size, unverified records) | **Fix** | Both added |
| A18 | Pharmacist | Claims are not patients (titration fills) | **Fix** | Share of 30-day fills reported (same result); claim defined; "wrote" removed |
| A19 | Pharmacist, economist | Statin control weaker than stated (CV-focused promotion) | **Fix** | Softened in text and chart 1b; total-claims growth leads the argument |
| A20 | Pharmacist | Brand switching follows guidelines (weekly, potency, CV evidence) | **Fix** | In "doesn't mean" and Result 1 |
| A21 | Pharmacist | Formulary-tier control from CMS formulary files; drop label-change cohorts | **Disclose** | Named in Limitations; not run (new data source; out of P24 scope) |
| A22 | Pharmacist | Spending is gross, before rebates | **Fix** | Stated in the text (chart 3 already said so) |
| A23 | Pharmacist | Obesity exclusion too absolute; Wegovy CV coverage from 2024 | **Fix** | Reworded; explorer notes Wegovy and plan verification |
| A24 | Pharmacist | Ozempic/Rybelsus co-promotion | **Fix** | Stated with the molecule-level result (+13.6 pp) |
| A25 | Pharmacist | "Other GLP-1" denominator includes insulin combos and Wegovy | **Disclose** | Explorer note; the share robustness without them was not run |
| A26 | Pharmacist | Post-data policy (price negotiation, kidney indication) | **Fix** | One sentence in Limitations |
| A27 | Economist | Matching worsens the practice-growth gap (regression to the mean) | **Fix** | Matched total-claims growth (15–19%) reported; Limitations say so |
| A28 | Economist | H6 "Supported" though about half is practice growth | **Fix** | Reading reworded with matched growth; bound label corrected |
| A29 | Economist | Share could be early adoption of new brands; anticoagulant NC on share; growth × brand-age | **Disclose** | Stated as an alternative explanation; the extra models were not run |
| A30 | Economist | Treatment is "entering a paid relationship"; report e = 1…3 | **Disclose** | Definition stated; e = 0 stays in the average as pre-registered (Limitations: annual timing) |
| A31 | Economist | Spillover direction not established | **Fix** | Reworded |
| A32 | Economist | NC exposure comparator unnamed; 37% vs 38% | **Fix** | "association with any GLP-1 prescribing"; docs/qa.md now 38% |
| A33 | Journalist | Five cuts to reach about 2,000 words | **Your call** | Not applied (D44 kept length); the article grew to about 3,800 words with the new caveats |

## Explorer

| # | Reviewer | Point | Triage | What was done |
|---|---|---|---|---|
| B1 | Journalist | LP attack recovers withheld counts exactly | **Fix** | `ppg.app.protect` LP audit + complementary suppression (D47); 0 recoverable |
| B2 | Journalist | Dominance-withheld dollars bounded tightly across brand × specialty × state | **Fix** | Cross-brand total removed; amounts protected so nobody can prove more than half of a withheld value |
| B3 | Journalist | The withholding reason discloses ("one prescriber > 50%") | **Fix** | One public code; reasons only in the notes |
| B4 | All three | Pre-2021 all-specialty payment rates deflated (NPs/PAs) | **Fix** | Total is now "All physicians"; NPs, PAs separate with "not reported before 2021" bands |
| B5 | Economist, journalist | Layout invites a causal reading; caveat too late; lifecycle missing | **Fix** | Banner above the charts; lifecycle in the caveat and events list; W1 wording |
| B6 | Pharmacist, economist | Suppression makes shrinking brands' claims fall too fast | **Fix** | Caption gives the share of national claims visible (Victoza 2024: 21%); note explains |
| B7 | Pharmacist | Market events unannotated | **Fix** | Numbered event markers and "What else happened" list |
| B8 | Pharmacist | Per-1,000 denominator includes SGLT2s (heart failure, CKD) | **Fix** | Denominator is now total Part D claims |
| B9 | Pharmacist, economist, journalist | "Prescribing regularly" overstates the 11-claim threshold | **Fix** | Relabelled "% with 11+ claims"; claim defined; practice-size caveat |
| B10 | Economist, journalist | "$ per prescriber" mean dominated by speakers | **Fix** | Axis text and note say so |
| B11 | Economist, journalist | Quantile bins recomputed per year | **Fix** | Breaks fixed per brand × group × measure across years; "under / to under / and above" legend |
| B12 | Economist | 2013 partial year looks like a surge | **Fix** | Dotted 2013–14 step, hollow point, flagged in table and map |
| B13 | Economist | Panel composition changes over time | **Disclose** | Note added; no constant-cohort toggle |
| B14 | Economist | Ecological inference on the map | **Fix** | Caveat sentence on states |
| B15 | Economist | Comparison line includes the state | **Fix** | "Rest of the US" |
| B16 | Economist | Add an All-GLP-1 class line | **Reject** | A cross-brand total reopens the subtraction attack (B2) |
| B17 | Pharmacist | "All GLP-1s" label; Saxenda unlisted | **Fix** | All-brand option removed; Saxenda listed as excluded |
| B18 | Pharmacist | "Other non-physician" is pharmacists and residents | **Fix** | Group dropped |
| B19 | Pharmacist | Launch year vs first Part D year; pre-approval payments | **Fix** | Both years shown; 2017 Ozempic payments explained |
| B20 | Pharmacist | "Other GLP-1s" mostly insulin combinations | **Fix** | Stated in the note |
| B21 | Journalist | Empty states look like withholding | **Fix** | Cause-specific legend text; "No data" swatch |
| B22 | Journalist | Tile contrast below AA | **Fix** | Per-bin text colours; values 10px, full opacity |
| B23 | Journalist | Keyboard and screen readers | **Fix** | Tile grid is one tab stop with arrow keys; radio groups; charts labelled; skip link |
| B24 | Journalist | Phones can't read state values | **Fix** | Readout under the map. Tiles stay 27 px: 51 tiles can't reach 44 px at 390 px; the table is the alternative |
| B25 | Journalist | National specialty dollars exempt from dominance | **Fix** | 50% rule also applies to national cells with fewer than 50 paid prescribers (amends D45) |
| B26 | Journalist | "Everyone in a small group" disclosures | **Fix** | Withheld when a count equals the group size and the group has fewer than 20 |
| B27 | Journalist | Article link and GitHub link 404 | **Defer** | Live at launch (P26, D46) |
