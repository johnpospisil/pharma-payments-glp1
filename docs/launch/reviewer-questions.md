# Likely questions, with short answers

For replies on HN, Reddit and LinkedIn. Each answer links back to the article section that says it properly. Keep the tone: what the data can and can't show.

1. **So drug companies are buying prescriptions?**
   The study does not show that. Paid physicians' brand share rises a few points after the first payment (+4.1 / +3.0 / +5.3 for Trulicity, Ozempic, Mounjaro), but companies choose whom to pay, and the result is consistent with influence *or* with paid doctors adopting new brands sooner.

2. **Isn't this just targeting? Reps visit doctors who prescribe a lot.**
   Partly, yes, and the article says so. The volume outcome (11+ claims) rises, but statins rise almost as much (+6.4 / +7.9 / +7.1), so paid practices were already growing. That's why the article leads with brand share, which targeting of growing practices shouldn't move toward one brand.

3. **Why lead with brand share if it wasn't the pre-registered primary?**
   Fair challenge. The primary failed its falsification test; share was a pre-registered secondary, and I chose to lead with it afterwards. That choice is disclosed in the article and logged as a deviation. Treat the share result as less confirmatory than a primary would be.

4. **How big is the effect, really?**
   Between 1.7–1.8 and 3.0–5.3 percentage points of share, depending on how Medicare's hidden small counts are treated. The low end is below the 2-point smallest effect of interest I set in advance, so it is not a precise effect size.

5. **What about Medicare's suppression of small counts?**
   Rows with fewer than 11 claims are hidden, and a brand crossing that line looks like a share gain. The bounded re-estimate shrinks the gains to 1.7–1.8 points; 30-day fills (+4.1 / +3.1 / +4.8) and high-volume physicians, where suppression is rare, give the larger numbers.

6. **Victoza's share falls after payment. Doesn't that contradict the story?**
   It's in the headline chart on purpose. Victoza was already losing share to weekly drugs before payment, and Novo Nordisk moved promotion to Ozempic. One possible reason, not tested.

7. **Why only Medicare?**
   Part D is the only public, prescriber-level prescribing data in the US. It covers older patients, and it excludes weight-loss-only use, so this is about diabetes prescribing, not the obesity boom.

8. **Isn't the comparison group biased? Almost everyone gets paid eventually.**
   Yes: 78% of GLP-1 fills in 2024 came from prescribers paid at some point. So the comparison is mostly doctors *not paid yet*, matched on diabetes workload, volume, specialty and region, which is a fairer comparison than never-paid doctors.

9. **Did you check the pre-trends?**
   All of them are reported. Trulicity's share pre-trend passes (p = 0.32) but fails when matched (p = 0.007); Ozempic's and Victoza's fail unmatched (Victoza's passes matched, p = 0.271); Mounjaro's rests on about one year. That mixed picture is one reason the article says "consistent with", not "caused".

10. **What's the difference between a meal and a speaker fee here?**
    The event study mostly describes physicians first reached through meals. Speakers were mostly first paid before 2015 and can't be followed this way; there are only 71–109 newly paid fee recipients per brand, too few to compare.

11. **Couldn't shortages or new indications explain the shifts?**
    They could explain some. Ozempic and Trulicity gained cardiovascular indications in early 2020, and the 2022–2024 shortages forced switches. Both are named in the article as alternative explanations; plan formulary data, which would help, isn't used.

12. **Can I find my own doctor?**
    No, by design. Public tables show only groups of 11 or more prescribers, dollars are withheld where one person dominates a state cell, and the explorer was tested with an attack that tries to work out hidden cells from published totals.

13. **Open Payments is public anyway. Why so careful?**
    Open Payments shows payments, not prescribing. Linking the two at the individual level, then publishing it, would imply a judgement about specific doctors that this design can't support.

14. **How do I know the numbers are right?**
    `make all` rebuilds everything from the raw CMS files, two independent rebuilds give identical results, and every number in the article is read from the pipeline's outputs (a test fails if one is typed by hand). Totals reconcile with CMS's own published figures.

15. **How is this different from earlier studies?**
    Earlier work, including the one GLP-1 study (Khunte et al. 2026), is mostly cross-sectional. This follows the same physicians over twelve years with an estimator built for staggered timing, tests brand switching directly, and reports the negative controls that cut against its own headline.
