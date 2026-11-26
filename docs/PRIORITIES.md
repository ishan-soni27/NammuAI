# Priorities board

The working copy of BUILD_PROMPT §11 (P0 / P1 / P2), kept up to date as Ishan adds or reorders things. The README's
"What I'd do next" section is built from this file. **Rule: P0 is finished before any P1 starts** (Ishan, 2026-11-26:
"We need to get through the priorities first").

## P0: mandatory (the MVP)

| # | Item | Phase | Status |
|---|---|---|---|
| 1 | Correct numbers: all T01–T31 rules, golden facts, visible data notes | 2 | ✅ Loader done (load run #5) |
| 2 | Run-out projection: sellable stock − promised orders + incoming POs with corrected dates − seasonal demand; statuses, "order at least", shortfall | 3, 4 | Done (engine + /dashboard) |
| 2a | **Late / unknown inventory section** (Ishan, 2026-11-26; Dana's Q3 + Q4): stock that might still come but can't be counted on is shown in its own bucket, never mixed into current inventory. Late POs ("ordered, arrival date unknown") and QA-HOLD ("may come back") go here. The run-out status counts only confirmed supply. A second "if the late PO arrives" line shows whether the item would be covered, and flags items **only covered by a late PO**. | 3 (engine), 5 (UI) | Done: "Late or unknown" section on Monday, dashed line on the item chart, "Only covered by a late PO" on cards |
| 3 | Monday screen: both answers, urgency-sorted, one-sentence summary, trust strip | 5 | Done (runway bars, Handled / Late or unknown / Fine sections) |
| 4 | Item drill-down "why" | 3 (explain), 4 (API), 5 (UI) | Done (numbered why, chart, source tables) |
| 5 | Stuck list: expired, stopped selling, inside six-month line, long at Harbor, overstock, $ at cost. Stopped items' Harbor stock flagged so Dana can clear it (her Q5) | 3, 4, 5 | Done (grouped by tag, Harbor lots first and badged) |
| 6 | "I've handled this" with optional qty and arrival date | 3 (engine), 4, 5 | Done (dialog; note, age, "BlueTide now shows" hint, clear) |
| 7 | Tell it what it knows: editable lead times, cushion, PO arrival dates | 4, 5 | Done (Lead times page in weeks; "Set real date" on Monday and item page; item cushion) |
| 8 | Log everything (4 layers) + Data notes and Activity pages | 4, 5 | Done (browser errors reported too) |
| 9 | Ship it: live deploy, loader, tests, README, DECISIONS, ASSUMPTIONS, DEMO_SCRIPT | 1–7 | Deploy live; README, DEMO_SCRIPT and final docs in Phase 7 |
| 10 | **Log POs and track them to received** (Ishan, 2026-11-26): new PO, shipped, received (lot, expiry, building), cancelled; counts as on the way, then as stock. Plus her own items and suppliers (independent of BlueTide) | 6.1 | Done (ADR-027); live |
| 11 | **Log outgoing shipments** (Ishan, 2026-11-26): customer orders out; promised, then shipped (lots picked); move stock between buildings | 6.2 | Done (ADR-028); live |
| 12 | **Import from the website** (Ishan, 2026-11-26): BlueTide's files *or* Dana's own templates (items, suppliers, customers, stock count, POs, sales history); dry run, then load; never touches Dana's records | 6.3 | Done (ADR-029); live |
| 13 | **Download to Excel (CSV)** (Ishan, 2026-11-26): order list, stuck list, POs, shipments, data notes | 6.4 | Done (ADR-030); live |

## P1: after P0, in this order

| # | Item | Why it's not P0 |
|---|---|---|
| 1 | **Harbor storage cost calculator** (Ishan, 2026-11-26). A separate section: for each item at Harbor, Dana types how many cases fit on a pallet; the tool computes pallets and **$30 per pallet per month** (Dana's rate, 2026-11-26). She can save results to a table and export it as CSV. Replaces old P1 #5 ("Harbor $ per month") and includes part of old P1 #1 (CSV export). **Done (ADR-031); live** | Doesn't answer "what will run out" or "what am I stuck with"; needs Dana's cases-per-pallet input |
| 2 | ~~CSV export of the order and stuck lists~~ | Done as P0 #13 (ADR-030) |
| 3 | QA-HOLD "what if it clears" toggle | The P0 default (show separately, don't count) already follows Walt's rule and Dana's Q4 |
| 4 | Lot-level expiry-aware projection (FEFO) + "projected to expire unsold" | P0 already flags every lot inside the line with $ |
| 5 | Stockout detector (suggest zero-sales runs for Dana to confirm) | Can't be auto-applied; Dana confirmed only the one known stockout (Q6) |
| 6 | Order rounding to vendor minimums or containers | No MOQ/container data; "order at least" is honest for v1 |
| 7 | Easter-aligned Lent seasonality | Monthly indices already capture Lent |
| 8 | Editable business thresholds in the UI | The config file is enough for v1 |
| 9 | Simple passcode gate | Fictional data; adds demo friction |

## P2: out of scope for now (listed in the README with reasons)

- **Chat assistant** (Ishan, 2026-11-26: "a later thing to worry about"): Dana asks questions in plain English ("why
  is the 16/20 shrimp red?") and gets answers grounded in the same numbers and explanation steps the screens use.
  Natural home: an endpoint that hands the engine's explain-steps and drill-down data to a Claude model. Not started.
- Fresh and day-boat ordering. Dana: separate, daily, doesn't need help.
- Marco's features (availability and price, routes, emails). "Dana first."
- ~~Live BlueTide integration / nightly ETL~~: moved to P0 #12 as uploads from the website (Ishan, 2026-11-26).
  A direct BlueTide connection is still out of scope.
- ~~Creating POs~~: moved to P0 #10 (Ishan, 2026-11-26: the app becomes the main record). *Sending* POs to
  suppliers (email, EDI) is still out of scope.
- Transfer suggestions between buildings. No capacity or pallet data yet.
- Statistical / ML forecasting. One year of data; explainability matters more.
- User accounts and roles. Single user, fictional data.
- Native mobile app. Responsive web covers her phone use.
- Pricing, margin and customer analytics. Not requested.
- Multi-tenant support for other Nammu clients.
