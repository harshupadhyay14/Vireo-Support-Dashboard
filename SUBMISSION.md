# Submission form: Vireo Set B

**1. What did you build, and what business outcome does it move? State the number and the money.**
A local Python tool (`python run.py`) that cleans the exports, scores every agent on CSAT and handle time fairly (adjusted for the queue, compared within tier), flags the bottom ten as asked, and automatically detects faulty manufacturing lots from replacement rates. It found that Pulse 2 lots 2510-2512 explain the CSAT slide: Jan-Mar 2026 CSAT is 3.07 overall and 3.47 without the 2,563 tickets on those lots. Goal: bring replacements on those lots from 37% back to the ~10% baseline. Worth about Rs 12.7 lakh recovered to date (excess replacements x Rs 1,820), and about Rs 2.4 lakh a quarter still leaking (Apr-Jun 2026). Also moves CSAT back from 3.07 to ~3.47.

**2. Cost of one run and a month at 650 tickets/week?**
Rs 0. No paid calls: pandas/numpy on a laptop, about 10 seconds. 650/week is about 2,817 tickets/month (650 x 52 / 12); at 0 model calls that is Rs 0/month. For comparison, the per-ticket model call Arjun ruled out would be 2,817 x Rs 5 = about Rs 14,100/month.

**3. How do you know it works?**
- Seven automated tests (`tests/`): legacy UTC fix removes all 2,309 negative handle times; agents join on id (the two Kavya Pandeys stay separate); lot detector flags exactly Pulse 2 2510/2511/2512 and nothing else at z thresholds 3, 4 and 6 (about 200 SKU-lot cells checked).
- Free-text fault rule: checked on 60 random tickets I labelled by hand (well, by Claude, not an independent human). 8 of 9 true faults caught, 0 false alarms. Only 9 positives, so the uncertainty is wide; it misses phrasing like "right earbud silent" on non-Pulse products.
- Lot join: 99.2% of tickets matched to a lot (exact order_id, else most recent earlier order of that customer+SKU). The fallback is a guess for customers with several orders of the same SKU (about 10% of customer-SKU pairs).
- Agent scores: OLS with 44 agent effects, standard errors about 0.13-0.18 on a 1-5 scale. Not validated against any ground truth; there is none.

**4. Did you change, narrow, or push back on the client's ask?**
Yes. Asked for bottom ten to retrain; I still print it but say most of them are not distinguishable from peers once the faulty-lot queue is removed, and recommend not spending the Rs 4 lakh on them. Tier 2 is not compared with Tier 1 (policy s6). I also questioned the Diwali top-five (gaps inside noise) and Arjun's Rs 2,500 (policy gives Rs 1,820 for Pulse 2). Done from the first data pass, once the lot pattern showed.

**5. What is wrong with what you are handing us?**
- Adjusting for "faulty-lot earbud fault" could hide a real difference in how well agents handle that case; I cannot separate the two.
- The 90% flag across 44 agents will produce about 2 false alarms by chance; I got 1 (A3004). It is a "watch", not a finding.
- CSAT is only ~45% response; agents have 40-240 answers each.
- Baseline replacement rate (10.2%) comes from the same data; "excess" cost counts replacements only, not the extra contacts (about Rs 7 lakh at policy contact costs), not refunds.
- Replacement flag is agent-entered; I did not check it against shipments.
- Legacy fix is a constant +5h30; I checked the result (no negatives, same distribution as helpdesk) but not against the original event log. I found no re-imported duplicate tickets by ticket_id or customer+SKU+time, though policy s9 says they may exist. Refund units looked consistent (refund/order value identical across systems), so no conversion applied.
- Export holds about 150 tickets/week, not 650; I used it as is.
- Dashboard is a static HTML file, not sortable. The Kavya Pandey pair are shown by agent_id; Neha's "Kavya's four" I read as A3004-A3007, from the data, not confirmed.

**6. What did you deliberately leave out, and why that rather than something else?**
SLA breach credits (1,064 breaches x Rs 350 = Rs 3.7 lakh over 18 months) and transfer costs (1,215 x Rs 305 = Rs 3.7 lakh): real but small next to Rs 12.7 lakh. Repeat-contact (30-day) costing, per-agent trends over time, IVR-junk handling, customer segmentation (Care+), and the Finance "double remedy" check (only 6 tickets with both refund and replacement). Reason: one root cause explained the ask and the money; anything else would not fit in the cap.

**7. Anything you built or found that nobody asked for?**
The faulty-lot detector and the finding itself. Also: the bot's category tag catches only 28% of the faulty-lot tickets as "Charging & Battery"; the free-text rule finds more.

**8. What did you use AI for?**
[FILL IN: tools, models, cost in Rs, what you discarded.] Suggested: Claude did exploration, code, the memo and this form; I reviewed and ran everything. Wasted time: first-pass ranking by raw CSAT and a text "anger" score (it did not predict CSAT, discarded). Screen recording link: [ADD].

**9. Public Google Drive link:** [ADD]

**10. Someone picks this up on Monday and you are unreachable: the three things they need to know.**
1) `python run.py` rebuilds everything from five CSVs in `data/`; `tests/` must pass. 2) The message to Priya is "the bottom ten are a queue effect from Pulse 2 lots 2510-2512, don't retrain yet"; the supporting table is `out/lot_alerts.csv`. 3) Open items: a supplier claim needs Finance's real replacement counts, and the free-text rule needs a proper human-labelled sample.

**11. Honest hours spent:** [ADD]

**12. GitHub repo:** [ADD]
