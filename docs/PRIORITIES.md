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
| 4 | Item drill-down "why" | 3 (explain), 4 (API), 5 (UI) | Done: a numbers-only breakdown linked to its source tables, one instruction for late-PO items, chart (ADR-033) |
| 5 | Stuck list: expired, stopped selling, inside six-month line, long at Harbor, overstock, $ at cost. Stopped items' Harbor stock flagged so Dana can clear it (her Q5) | 3, 4, 5 | Done (grouped by tag, Harbor lots first and badged) |
| 6 | "I've handled this" with optional qty and arrival date | 3 (engine), 4, 5 | Done (dialog; note, age, "BlueTide now shows" hint, clear) |
| 7 | Tell it what it knows: editable lead times, cushion, PO arrival dates | 4, 5 | Done (Lead times page in weeks; "Set real date" on Monday and item page; item cushion) |
| 8 | Log everything (4 layers) + Data notes and Activity pages | 4, 5 | Done (browser errors reported too) |
| 9 | Ship it: live deploy, loader, tests, README, DECISIONS, ASSUMPTIONS, DEMO_SCRIPT | 1–7 | Done; updated for ADR-032 |
| 10 | ~~Log POs and track them to received~~ (Phase 6.1) | 6.1 | **Cut, archived on `archive/system-of-record`** (ADR-032): BlueTide stays the record; POs come in with each upload, and the **On the way** page shows them (read only, plus "Set real date") |
| 11 | ~~Log outgoing shipments and stock moves~~ (Phase 6.2) | 6.2 | **Cut, archived on `archive/system-of-record`** (ADR-032) |
| 12 | **Weekly upload from the website**: BlueTide's files only (Dana's own templates cut, ADR-032); check, then load; "today" follows the data; sales history accumulates; raw rows kept for 8 loads | 6.3, cut step 3 | Done (ADR-029 narrowed by ADR-032); live |
| 13 | **Download to Excel (CSV)**: order list, stuck list, open PO lines, data notes, Harbor table | 6.4 | Done (ADR-030); live |

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
  is the 16/20 shrimp red?") and gets answers grounded in the same breakdown rows the screens use. It could only
  *explain*: the math stays deterministic, with no LLM in it (ADR-032, boundary 5). Not started.
- Fresh and day-boat ordering. Dana: separate, daily, doesn't need help.
- Marco's features (availability and price, routes, emails). "Dana first."
- A direct BlueTide connection or nightly feed. BlueTide has no known API; Dana uploads its exports each week (P0 #12),
  and the loader's rules are pure functions a feed could reuse.
- **Recording transactions in the app** (POs, receipts, shipments, picks, moves, her own items, suppliers and stock
  counts). Built in Phase 6, **cut by ADR-032** (Ishan's scope review): it made the app a second system of record
  with double data entry. Archived on `archive/system-of-record`. Moving work off BlueTide is the README's
  "Roadmap off BlueTide": one job at a time, each record owned by one system.
- Replacing BlueTide outright. It also runs Marco's order entry, credits, receiving, transfers and invoicing: an ERP
  migration, not this app.
- Transfer suggestions between buildings. No capacity or pallet data yet.
- Statistical / ML forecasting. One year of data; explainability matters more.
- User accounts and roles. Single user, fictional data.
- Native mobile app. Responsive web covers her phone use.
- Pricing, margin and customer analytics. Not requested.
- Multi-tenant support for other Nammu clients.
