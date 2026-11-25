# Assumptions

Every assumption the app relies on, with where it came from and its status. When Dana answers a question, flip the
status to **Confirmed by Dana (date)**, update the seed or config named in "Lives in", re-run the loader if needed, and
log it in `docs/PROMPT_LOG.md`. Where there is no answer, we use the **conservative** option (the one that makes a
stockout less likely), because Dana said running out hurts more than overstock (call 00:01:10).

**Status values:** Pending Dana (asked in the email, waiting) · Confirmed by call (said on the kickoff call) ·
Confirmed by Dana (date) · Decided by Ishan (date) · Assumption (not asked; our judgment, open to challenge).

| ID | Assumption | Default used | Source | Lives in | Status |
|---|---|---|---|---|---|
| A01 | Lead times (order placed → in our building) | BXE 84, AFS 42, MNP 14, ASP 28, DLC 21 days | Call 00:02:25 + email Q1 | `data/reference/vendor_settings_seed.csv` | Pending Dana |
| A02 | Cushion (extra stock for when ships slip) | Imports (BXE, AFS) 14 days, others (MNP, ASP, DLC) 7 | Call 00:08:30 + email Q2 | `data/reference/vendor_settings_seed.csv` | Pending Dana |
| A03 | Late POs (BlueTide date passed, nothing received) | Assume arrival 7 days after AS_OF, flagged "late, confirm with vendor" | Email Q3 | `OVERDUE_PO_ASSUMED_DAYS` in `business_rules.py` | Pending Dana |
| A04 | QA-HOLD stock | Not counted as available, shown separately as "on hold, may come back" | Call 00:04:40 + email Q4 | `data/reference/locations.csv` | Pending Dana |
| A05 | Dormant items | TIL-FIL, SHR-6170 and PAN-1012 have stopped selling (no real demand in 60 days, no open PO) | Email Q5 | `DORMANT_NO_SALES_DAYS` in `business_rules.py`; reactivate via `item_settings` | Pending Dana |
| A06 | Stockouts | Only SHR-1620, Dec 11, 2025 to Jan 2, 2026 | Data + email Q6 | `data/reference/stockout_periods.csv` | Pending Dana |
| A07 | Negative ADJ lines | Netted into the item's sellable total (conservative) | Not asked | Loader rule T13 | Assumption |
| A08 | Credits (negative sales) | Ignored in demand; returned goods are already in the snapshot | Not asked | Loader classify T18 | Assumption |
| A09 | Samples ($0 orders) | Excluded from demand (about 2 cs/week in total, negligible) | Call 00:06:50 | Loader classify T17 | Confirmed by call |
| A10 | Cruise order | SO-245503 excluded as a one-off | Call 00:06:50 | `data/reference/excluded_orders.csv` | Confirmed by call |
| A11 | Demand date | Demand is dated by **order date**; open orders are deducted from stock on **ship date** | Not asked | Planning demand / projection (ADR-013) | Assumption |
| A12 | Six-month line | Measured from each lot's **expiry date** (AS_OF + 6 months = 2027-05-16), never received date or shelf life | Call 00:03:30 | `SIX_MONTH_LINE_MONTHS` in `business_rules.py` | Confirmed by call |
| A13 | Order cycle | Weekly (Dana orders every Monday) | Call 00:01:10 | `order_cycle_days` in `vendor_settings_seed.csv` | Confirmed by call |
| A14 | Stuck thresholds | Overstock > 26 weeks of cover; long at Harbor > 12 weeks of cover | Not asked | `OVERSTOCK_WEEKS`, `HARBOR_LONG_WEEKS` in `business_rules.py` | Assumption |
| A15 | Auth | None in v1; `X-Actor` header (default "Dana") for the audit trail | Not asked | ADR-011 | Assumption |
| A16 | Harbor $ per month | Hidden until the pallet rate is known | Email P.S. | P1 item | Pending Dana |
| A17 | Currency of lot cost | "$ at cost" uses each lot's `unit_cost` as exported, treated as USD. BlueTide has no currency on lots; MNP's vendor currency is CAD | Not asked | Planning stuck valuation | Assumption |
| A18 | When a PO counts as late | A PO is late when its re-derived arrival date is **on or before** AS_OF (`<=`). BUILD_PROMPT §6.6 had strict `<`. PO-260407 (calamari, BlueTide Oct 19) re-derives to exactly Nov 16, so it is flagged late with ETA Nov 23, which matches what email Q3 told Dana | Email Q3 + Ishan | Planning supply (§6.6) | Decided by Ishan (2026-11-25) |
| A19 | Unrecognized item status | A status value that isn't one of the known ones is treated as **active** and flagged, so an item is never silently dropped from planning | Not asked | `loader/classify.py` `status_kind` | Assumption (conservative) |
| A20 | Vendor missing from vendor_types.csv | Treated as a **stock supplier** (its items still get planned) and flagged | Not asked | `loader/rules.py` `build_vendors` | Assumption (conservative) |
| A21 | Lot at an unknown location | **Not counted** as sellable, and logged as an error (the lot is left out) until the location is added to `data/reference/locations.csv` | Not asked | `loader/rules.py`, `planning/supply.py` | Assumption (conservative) |
| A22 | Open PO line received in full | Counts **nothing** as still coming, flagged for Dana | Not asked | `loader/rules.py` `_build_po_line` | Assumption |

## Notes for explaining these in the review
- **Why conservative?** Every default above leans toward ordering a little early: the upper end of the lead-time range,
  late POs assumed late rather than "arriving today", on-hold stock not counted. Dana: "Running out." (00:01:10).
  Marco: "I'd rather argue about price than tell a chef we're out."
- **A11 in plain words:** a customer's order is demand on the day they place it (that's when the need exists). Stock
  leaves the building on the ship date, so the run-out projection takes it out then. For pre-booked holiday orders this
  counts demand a little early, which errs toward ordering sooner.
- **A18 in plain words:** if our best estimate says a PO should already be here and it hasn't been received, we can't
  count it as arriving today. We assume it shows up within a week and flag it, until Dana types in the real date.
