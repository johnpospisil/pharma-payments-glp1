# LinkedIn, X and Bluesky

**Status:** drafts. Nothing is posted without John. Same day as Hacker News, after it.

## LinkedIn (framed around the method)

**Image:** `report/figures/social/hero_brand_share_1200x675.png`. Put the link in the first comment if reach matters more than tidiness (LinkedIn shows posts with links to fewer people).

> Do drug-maker payments change what doctors prescribe, or do companies just pay the doctors who were going to prescribe more anyway?
>
> That's the hard part of almost every study of industry payments, and it's what I tried to take seriously in my latest project. I linked every promotional payment naming a GLP-1 (CMS Open Payments, $424.5 million) to the same prescribers' Medicare Part D claims, 2013–2024, and followed 280,610 physicians brand by brand around their first payment.
>
> What I found:
> • The paid brand's share of a physician's GLP-1 claims rises a few points (+4.1 Trulicity, +3.0 Ozempic, +5.3 Mounjaro), mostly at competitors' expense.
> • But paid doctors' practices were already growing: their statin prescribing rises too. My pre-registered main outcome failed that falsification test, and I say so up front.
> • Medicare hides small counts. Bounding them against the result shrinks the share gain to 1.7–1.8 points.
>
> What I'd point other analysts to is the process, not the headline:
> 1. The analysis plan was locked (git tag) before any post-payment comparison was run, and every later change is a dated, public deviation.
> 2. A staggered event study (Callaway–Sant'Anna), with matching on pre-payment trajectories, negative-control drugs and payments, placebo timing and suppression bounds.
> 3. A red-team review by three AI reviewers (health economist, clinical pharmacist, data journalist). It cut my headline down and found a privacy hole in the interactive explorer, which I rebuilt with linear-programming checks so no hidden cell can be worked out from published totals.
> 4. Every number in the article is read from the pipeline's outputs, never typed, and a test fails if one is.
>
> No individual physician is named or identifiable anywhere. Article, explorer, code and data in the comments.
>
> #DataScience #HealthPolicy #CausalInference #OpenData

**First comment:**
> Article: https://johnpospisil.github.io/pharma-payments-glp1/
> Explorer by specialty and state: https://johnpospisil.github.io/pharma-payments-glp1/app/
> Code and pre-registration: https://github.com/johnpospisil/pharma-payments-glp1
> Data: https://huggingface.co/datasets/audiofreak7/glp1-payments-prescribing-medicare

## X and Bluesky thread (3 posts, one chart each; each post fits X's 280 characters, links counted as 23)

**1/3** · image: `hero_brand_share_1200x675.png`
> After a GLP-1 maker's first payment to a Medicare physician (usually a sponsored meal), the paid brand's share of their GLP-1 claims rises a few points: +4.1 Trulicity, +3.0 Ozempic, +5.3 Mounjaro. Victoza falls. 🧵
> https://johnpospisil.github.io/pharma-payments-glp1/

**2/3** · image: `chart1b_targeting_statins_1200x675.png`
> The catch: paid doctors' practices were already growing, and their statin prescribing rises too. Medicare also hides small counts; bounding them shrinks the share gain to 1.7–1.8 points. None of this shows that payments caused prescribing.

**3/3** · image: `chart7_lorenz_1200x675.png`
> The top 1% of paid prescribers got 76% of the money. Pre-registered, every deviation public, no doctor named. Explore by specialty and state: https://johnpospisil.github.io/pharma-payments-glp1/app/
> Code and data: https://github.com/johnpospisil/pharma-payments-glp1
