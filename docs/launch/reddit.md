# Reddit

**Status:** drafts. Nothing is posted without John. Read each subreddit's rules and sidebar on the day (I could not load reddit.com from here; the notes below come from mirrors of the rules pages and may be out of date). Post from an account with other activity, one subreddit per day, never cross-posted.

## r/dataisbeautiful (recommended first)

**Rules to check:** `[OC]` in the title (you did the data, the analysis and the chart); the **first top-level comment** must give the data source and tools; link to the full article in that comment. US-politics posts are limited to Thursdays; this is health data, not politics, but avoid framing it as a policy argument.
**Post type:** image: `report/figures/social/hero_brand_share_1200x675.png` (or the dark crop).
**When:** a weekday morning, US time, a day or two after Hacker News.

**Title:**
> [OC] After a drug maker's first payment, physicians' GLP-1 prescribing shifts a few points toward its brand (Medicare, 2013–2024)

**Required first comment:**
> **Source:** CMS Open Payments (promotional payments naming a GLP-1, 2013–2025) linked by NPI to Medicare Part D Prescribers by Provider and Drug (2013–2024). Both public.
> **Tools:** Python (DuckDB, pandas, statsmodels), R (`did`, `HonestDiD`) for cross-checks, matplotlib.
>
> Each panel is one brand. The line is the change in the paid brand's share of a physician's GLP-1 claims, year by year around their first payment from the brand's maker, compared with similar physicians not yet paid. Bands are 95% intervals. Averaged over years 0–3: +4.1 (Trulicity), +3.0 (Ozempic), +5.3 (Mounjaro) percentage points; Victoza −4.8.
>
> Caveats: this is not proof that payments cause prescribing. Companies choose whom to pay, Medicare hides small counts (bounding them shrinks the gains to 1.7–1.8 points), and paid doctors' practices were already growing.
>
> Full write-up, method and code: https://johnpospisil.github.io/pharma-payments-glp1/

## r/pharmacy

**Rules to check:** the sub is kept for pharmacy professionals; self-promotion and surveys are restricted. Read the sidebar; if in doubt, message the moderators first with the draft below. Frame it as asking for a professional check of the clinical assumptions, which is genuine: the red-team review flagged formulary and shortage effects the data can't see.
**Post type:** text post with the article link.

**Title:**
> Drug-maker payments and GLP-1 brand choice in Medicare Part D: looking for a pharmacist's read on the formulary and shortage caveats

**Body:**
> I'm a data scientist, not a pharmacist. I linked every promotional payment naming a GLP-1 in CMS Open Payments to the same prescribers' Part D claims (2013–2024) and looked at what happens to a brand's share of a physician's GLP-1 claims after their first payment from its maker. The paid brand gains a few points of share (+4.1 Trulicity, +3.0 Ozempic, +5.3 Mounjaro), mostly from direct competitors; bounding Medicare's hidden small counts shrinks that to 1.7–1.8.
>
> Things I can't see in the data and would value a pharmacist's view on: plan formulary tiers and prior authorisation by year, how much the 2022–2024 semaglutide and tirzepatide shortages forced switches, and how much weekly dosing and the cardiovascular labels (Trulicity and Ozempic, early 2020) explain the move away from Victoza.
>
> Write-up (with a "what this doesn't mean" section and the limitations): https://johnpospisil.github.io/pharma-payments-glp1/. No individual prescriber is identifiable anywhere.

## r/medicine (dropped, D54)

Not posted: the sub requires a healthcare-role flair. If a physician who has read the article wants to share it, the draft below is a starting point for them.

### Draft (for reference)

**Rules to check:** r/medicine is for medical professionals, mainly physicians. Posting requires a **user flair stating your role in healthcare**, an account more than 7 days old with more than 10 comment karma, and a substantive first comment on any link post. As a non-clinician, John may not be able to post here at all. Only post if the flair options include a fitting non-clinical role, or if a moderator agrees; otherwise skip it, or ask a physician who has read the article whether they would share it.

**Title (if allowed):**
> Industry payments and GLP-1 brand choice in Medicare Part D: a pre-registered event study (2013–2024)

**First comment:**
> Not a clinician: I'm a data scientist and wrote this up. The design compares each physician's GLP-1 prescribing before and after their first promotional payment for a brand (mostly sponsored meals) with physicians not yet paid. The paid brand's share of their GLP-1 claims rises a few points (+4.1 / +3.0 / +5.3 for Trulicity, Ozempic, Mounjaro), 1.7–1.8 under the most conservative treatment of Medicare's hidden small counts. Paid physicians' practices were already growing: statin prescribing rises after a GLP-1 payment too (+6.4 / +7.9 / +7.1). It doesn't show that payments changed any individual's prescribing, and no physician is identifiable. Clinical pushback very welcome, especially on formularies, shortages and the CV labels.
