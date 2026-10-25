# Hacker News

**Status:** draft. Nothing is posted without John.
**When:** a weekday, 8–10 am US Eastern. Post the link, then the first comment right away.
**Link:** https://johnpospisil.github.io/pharma-payments-glp1/

## Title (pick one; HN allows 80 characters)

1. **After a drug maker's free lunch, GLP-1 prescribing tilts toward its brand** (recommended: what the study measured, in plain words)
2. Do drug-maker payments shift GLP-1 prescribing? A pre-registered Medicare study
3. Show HN: Explore drug-maker payments and GLP-1 prescribing by specialty and state (only if the link is the explorer, /app/; "Show HN" needs something people can try)

Avoid "bought", "bribed", "paid to prescribe" or "Ozempic doctors": the study doesn't show that payments caused prescribing, it is about diabetes prescribing in Medicare (not weight loss), and HN readers will say so.

## First comment

> Author here. Lots of studies find that doctors who take money from drug makers prescribe more of their drugs, but most compare paid and unpaid doctors at one moment, so they can't tell influence from targeting: sales reps call on the doctors who already prescribe the most. I wanted to see what happens *around* a doctor's first payment for a specific GLP-1 brand.
>
> Data: every promotional payment in CMS Open Payments that names a GLP-1 (2013–2025, $424.5M), linked by NPI to the same prescribers' Medicare Part D claims (2013–2024). The event study follows 280,610 physicians brand by brand, comparing each newly paid physician with similar physicians not yet paid (Callaway–Sant'Anna, doubly robust). Most first payments are sponsored meals.
>
> What came out:
> - The paid brand's share of the physician's GLP-1 claims rises by +4.1 (Trulicity), +3.0 (Ozempic) and +5.3 (Mounjaro) percentage points, mostly at the expense of direct competitors. Victoza's falls (−4.8).
> - But Medicare hides prescriber-drug rows with fewer than 11 claims, and a brand crossing that line looks like a share gain. Bounding the hidden rows against the result shrinks the gains to 1.7–1.8 points, below the smallest effect I pre-registered as meaningful.
> - The pre-registered main outcome (11+ claims of the brand) rises +12.0 / +5.5 / +13.7 points, but statin prescribing, which a GLP-1 payment has no reason to change, rises too (+6.4 / +7.9 / +7.1). Paid doctors' practices were already growing. That outcome failed its own falsification test.
> - The money is concentrated: the top 1% of paid prescribers got 76% of the dollars, mostly speaker fees; the median paid prescriber got $109 over twelve years.
>
> I locked the analysis plan before fitting any model on post-payment data, and logged every later change as a dated deviation. Two of them matter: I chose to lead with brand share after the main outcome failed, and I changed the estimator's implementation after the first results. Both are in the article.
>
> No individual doctor is named or identifiable anywhere: public tables only show groups of 11 or more prescribers, and the explorer was red-teamed with a linear-programming attack on its published totals (it found holes, which are fixed).
>
> Code (rebuilds everything from the raw CMS files with `make all`), pre-registration and data: https://github.com/johnpospisil/pharma-payments-glp1. Explorer: https://johnpospisil.github.io/pharma-payments-glp1/app/. Happy to answer questions.
