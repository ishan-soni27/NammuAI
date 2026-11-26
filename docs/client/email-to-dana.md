# Email to Dana (sent by Ishan)

> Sent through the recruiter, who answers as Dana would. The text below is exactly what was sent (BUILD_PROMPT §4.4).
> **The bracketed guesses are the defaults the app uses until Dana replies.** Each one maps to a row in
> `docs/ASSUMPTIONS.md` (A01 to A06, A16). **Dana replied on 2026-11-26**: see `docs/client/dana-replies.md`.
> She confirmed every default except Q3 (late POs), which changed.

---

```
Subject: A few quick questions before I build your ordering tool

Hi Dana,

Thanks for sending the BlueTide exports. I've gone through them and have six quick questions. My best guess is in brackets after each one, so a simple yes or a number is all I need. Answer whichever ones you can and I'll use my guess for the rest.

1. Lead times. How many weeks does it take from placing an order to having it in our building for Aleutian Shore in Alaska and Downeast Lobster in Maine? And should I plan on the full 12 weeks for Vietnam? (Alaska 4 weeks, Maine 3 weeks, Vietnam 12 weeks)

2. Extra stock. You keep about two weeks of extra stock on imports. How many weeks do you like to keep for Canada, Alaska and Maine? (1 week each)

3. Late orders. These open POs are past their arrival date and nothing has been received yet. Are they still coming, and roughly which week? (I'll assume they arrive within a week and flag them as late)
- 21/25 shrimp, 800 cases, PO-260394, due Oct 5
- Calamari, 300 cases, PO-260407, due Oct 19
- 7-9 oz pangasius, the last 400 of 1,000 cases, PO-260376, due Sep 14

4. Stock on hold. There are 300 cases of haddock fillet and 80 cases of 16/20 shrimp sitting on QA-HOLD. Do you expect either to be released in the next few weeks? (I won't count them as available, but I'll show them separately so you can see them)

5. Items you may have stopped buying. Tilapia fillet, 61/70 shrimp and 10-12 oz pangasius haven't sold since the spring. Have you stopped carrying them? (I'll assume yes and list their leftover stock at Harbor as stock you're stuck with)

6. Other stockouts. Apart from the 16/20 shrimp last December, did any item sell out for more than a week in the past year? Sales drop to zero while something is out, and I don't want the tool to mistake that for low demand. (I'll assume no)

P.S. No rush on this one. If you know what Harbor charges per pallet each month, I can show what the stock sitting there is costing you.

Thanks,
Ishan Soni
```

---

## Where each answer lands in the code

| Question | Default in use | Where it lives | Assumption |
|---|---|---|---|
| Q1 Lead times | BXE 84 d, ASP 28 d, DLC 21 d | `data/reference/vendor_settings_seed.csv` | A01 |
| Q2 Cushion | 7 d for MNP, ASP, DLC (imports 14 d) | `data/reference/vendor_settings_seed.csv` | A02 |
| Q3 Late POs | ~~Arrive within 7 days~~ → **not counted until Dana enters a date** (her answer), flagged late | `late_po_assumed_days` in `backend/app/config/business_rules.py` | A03, A18 |
| Q4 QA-HOLD | Not counted, shown separately | `data/reference/locations.csv` (`is_sellable = false`) | A04 |
| Q5 Dormant items | Treated as stopped selling | `DORMANT_NO_SALES_DAYS` in `business_rules.py` | A05 |
| Q6 Other stockouts | None beyond SHR-1620 | `data/reference/stockout_periods.csv` | A06 |
| P.S. Harbor rate | Not shown until known | P1 item, needs pallet rate | A16 |
