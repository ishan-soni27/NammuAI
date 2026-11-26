# Assumptions

Every assumption the app relies on, with where it came from and its status. When Dana answers a question, flip the
status to **Confirmed by Dana (date)**, update the seed or config named in "Lives in", re-run the loader if needed, and
log it in `docs/PROMPT_LOG.md`. Where there is no answer, we use the **conservative** option (the one that makes a
stockout less likely), because Dana said running out hurts more than overstock (call 00:01:10).

**Status values:** Pending Dana (asked in the email, waiting) · Confirmed by call (said on the kickoff call) ·
Changed by Dana (date) (her answer replaced our default) ·
Confirmed by Dana (date) · Decided by Ishan (date) · Assumption (not asked; our judgment, open to challenge).

| ID | Assumption | Default used | Source | Lives in | Status |
|---|---|---|---|---|---|
| A01 | Lead times (order placed → in our building) | BXE 84, AFS 42, MNP 14, ASP 28, DLC 21 days | Call 00:02:25 + email Q1 | `data/reference/vendor_settings_seed.csv` | **Confirmed by Dana (2026-11-26)** for BXE ("use the full 12"), ASP and DLC. AFS and MNP: confirmed by call |
| A02 | Cushion (extra stock for when ships slip) | Imports (BXE, AFS) 14 days, others (MNP, ASP, DLC) 7 | Call 00:08:30 + email Q2 | `data/reference/vendor_settings_seed.csv` | **Confirmed by Dana (2026-11-26)**: "One week is right for all three" |
| A03 | Late POs (should already be here, nothing received) | **Not counted as coming until Dana types in a real date.** Flagged late; any item that only a late PO would cover is called out. (Was: assume arrival 7 days after AS_OF) | Email Q3 | `late_po_assumed_days = None` in `business_rules.py`; engine in Phase 3 | **Changed by Dana (2026-11-26)**: "please don't assume they'll arrive within a week. If an item is only covered by a late PO, I want to see that." |
| A04 | QA-HOLD stock | Not counted as available, shown separately as "on hold, may come back" | Call 00:04:40 + email Q4 | `data/reference/locations.csv` | **Confirmed by Dana (2026-11-26)**: "until it does I can't sell it ... leave it out and show it separately" |
| A05 | Dormant items | TIL-FIL, SHR-6170 and PAN-1012 have stopped selling (no real demand in 60 days, no open PO). Their leftover stock at Harbor is flagged in "stuck with" so Dana can clear it | Email Q5 | `dormant_no_sales_days` in `business_rules.py`; reactivate via `item_settings` | **Confirmed by Dana (2026-11-26)**: "we've stopped carrying all three. Flag what's left at Harbor so I can clear it." |
| A06 | Stockouts | Only SHR-1620, Dec 11, 2025 to Jan 2, 2026 | Data + email Q6 | `data/reference/stockout_periods.csv` | **Confirmed by Dana (2026-11-26)**: "No, just the 16/20" |
| A07 | Negative ADJ lines | Netted into the item's sellable total (conservative) | Not asked | Loader rule T13 | Assumption |
| A08 | Credits (negative sales) | Ignored in demand; returned goods are already in the snapshot | Not asked | Loader classify T18 | Assumption |
| A09 | Samples ($0 orders) | Excluded from demand (about 2 cs/week in total, negligible) | Call 00:06:50 | Loader classify T17 | Confirmed by call |
| A10 | Cruise order | SO-245503 excluded as a one-off | Call 00:06:50 | `data/reference/excluded_orders.csv` | Confirmed by call |
| A11 | Demand date | Demand is dated by **order date**; open orders are deducted from stock on **ship date** | Not asked | Planning demand / projection (ADR-013) | Assumption |
| A12 | Six-month line | Measured from each lot's **expiry date** (AS_OF + 6 months = 2027-05-16), never received date or shelf life | Call 00:03:30 | `SIX_MONTH_LINE_MONTHS` in `business_rules.py` | Confirmed by call |
| A13 | Order cycle | Weekly (Dana orders every Monday) | Call 00:01:10 | `order_cycle_days` in `vendor_settings_seed.csv` | Confirmed by call |
| A14 | Stuck thresholds | Overstock > 26 weeks of cover; long at Harbor > 12 weeks of cover | Not asked | `OVERSTOCK_WEEKS`, `HARBOR_LONG_WEEKS` in `business_rules.py` | Assumption |
| A15 | Auth | None in v1; `X-Actor` header (default "Dana") for the audit trail | Not asked | ADR-011 | Assumption |
| A16 | Harbor $ per month | Harbor charges **$30 per pallet per month**. Still hidden: turning cases into pallets needs cases per pallet (or pallets in use) per item, which we don't have | Email P.S. | P1 item (Harbor $ per month) | **Rate confirmed by Dana (2026-11-26)**; cases per pallet unknown (open question for Ishan) |
| A17 | Currency of lot cost | "$ at cost" uses each lot's `unit_cost` as exported, treated as USD. BlueTide has no currency on lots; MNP's vendor currency is CAD | Not asked | Planning stuck valuation | Assumption |
| A18 | When a PO counts as late | A PO is late when its re-derived arrival date is **on or before** AS_OF (`<=`). BUILD_PROMPT §6.6 had strict `<`. PO-260407 (calamari, BlueTide Oct 19) re-derives to exactly Nov 16, so it is flagged late with ETA Nov 23, which matches what email Q3 told Dana | Email Q3 + Ishan | Planning supply (§6.6) | Decided by Ishan (2026-11-25) |
| A19 | Unrecognized item status | A status value that isn't one of the known ones is treated as **active** and flagged, so an item is never silently dropped from planning | Not asked | `loader/classify.py` `status_kind` | Assumption (conservative) |
| A20 | Vendor missing from vendor_types.csv | Treated as a **stock supplier** (its items still get planned) and flagged | Not asked | `loader/rules.py` `build_vendors` | Assumption (conservative) |
| A21 | Lot at an unknown location | **Not counted** as sellable, and logged as an error (the lot is left out) until the location is added to `data/reference/locations.csv` | Not asked | `loader/rules.py`, `planning/supply.py` | Assumption (conservative) |
| A22 | Open PO line received in full | Counts **nothing** as still coming, flagged for Dana | Not asked | `loader/rules.py` `_build_po_line` | Assumption |
| A23 | Open orders in the selling rate | Open (not yet shipped) orders are counted **once**: deducted from stock on their ship date, **not** added to the recent selling rate. BUILD_PROMPT §6.2 counted them in both. Data: all 11,881 past orders shipped within 3 days of ordering, but this week's open orders are mostly holiday pre-bookings 1–4+ weeks ahead, so the spec counted December twice (SHR-1620 showed 78 cs/wk instead of 53, and the holiday bump landed in November). Holiday protection is unchanged: SHR-1620 still plans 542 cs for December, above last December's ~487 cs pace, and is still flagged too late | Ishan + data | `open_orders_in_selling_rate = False` in `business_rules.py` | **Decided by Ishan (2026-11-26)** |
| A24 | "Covered only by a late PO" | Tested against the best case: the late PO arrives today. If that turns an item from red/amber to fine, it's flagged | Dana Q3 + Ishan | `planning/engine.py` | Assumption |
| A25 | Handled note dated in the past | Counted as arriving today and flagged ("your date has passed"); Dana clears it when it lands | Not asked | `planning/supply.py` | Assumption |
| A26 | Category seasonality across units | Case items are converted to pounds (verified pack sizes) before a category's months are compared, so pound items don't swamp case items | BUILD_PROMPT §6.7 refinement | `planning/seasonality.py` | Assumption (Claude, flagged to Ishan) |

## Notes for explaining these in the review
- **Why conservative?** Every default above leans toward ordering a little early: the upper end of the lead-time range,
  late POs assumed late rather than "arriving today", on-hold stock not counted. Dana: "Running out." (00:01:10).
  Marco: "I'd rather argue about price than tell a chef we're out."
- **A11 in plain words:** a customer's order is demand on the day they place it (that's when the need exists). Stock
  leaves the building on the ship date, so the run-out projection takes it out then. For pre-booked holiday orders this
  counts demand a little early, which errs toward ordering sooner.
- **A18 in plain words:** if our best estimate says a PO should already be here and it hasn't been received, we can't
  count it as arriving today. We assume it shows up within a week and flag it, until Dana types in the real date.
