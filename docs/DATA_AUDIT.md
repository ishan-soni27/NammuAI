# Data audit: every trap in the BlueTide exports, and the rule we apply

This is the plain-English version of BUILD_PROMPT §5. Each trap has an ID (**T01–T31**). The same ID appears in
`data_issues.trap_id`, in code comments, and in test names, so any rule can be traced from the screen to the code to the test
to the line in the export that needed it. The **golden facts (G01–G17)** at the bottom are numbers computed directly from the
raw files. The test suite asserts them.

**Source files.** The loader reads byte-identical copies in `data/raw/` (ADR-017). Mapping to BlueTide's export names:

| Working copy (`data/raw/`) | BlueTide export (`kestrel-bay/data/`) | Rows | What it is |
|---|---|---|---|
| `bluetide_items.csv` | `items.csv` | 48 | Item master |
| `bluetide_inventory_on_hand.csv` | `inventory_on_hand.csv` | 228 | Lot-level on hand, two nights |
| `bluetide_sales_lines.csv` | `sales_lines.csv` | 15,750 | Order lines Oct 2025 – Nov 2026 (ship dates to Dec 15) |
| `bluetide_purchase_orders.csv` | `purchase_orders.csv` | 377 | PO lines in every status |
| `bluetide_vendors.csv` | `vendors.csv` | 8 | Vendors |
| `bluetide_customers.csv` | `customers.csv` | 52 | Customers (RESTAURANT 46, GROCERY 4, INTERNAL 1, CRUISE 1) |
| `bluetide_price_list.csv` | `price_list.csv` | 79 | Price tiers + fuel surcharge (Marco, phase 2) |

All files are CRLF. They are read as strings (`dtype=str, keep_default_na=False`), so trailing spaces, leading zeros and blanks survive into
the raw layer. Types are parsed only in the cleaning step.

**Test phase:** "P2" = loader tests (Phase 2), "P3" = planning engine tests (Phase 3). Tests live in `backend/tests/unit/`
(tiny synthetic fixtures) and `backend/tests/golden/test_real_data.py` (the real files).

---

## On-hand file (`inventory_on_hand`)

### T01 Two nights in one file
- **Found:** snapshot_date 2026-11-14 (115 rows) and 2026-11-15 (113 rows); 113 lot keys repeat.
- **Why it matters:** summing both nights roughly doubles the stock. Dana: "sometimes the file has two nights in it" (00:05:50).
- **Rule:** use only `max(snapshot_date)` = 2026-11-15. Each older row is logged `excluded`.
- **Test:** `test_T01_latest_snapshot_only` (P2) · golden G01.

### T02 Malformed item codes
- **Found:** `"shr-1620 "` (lowercase + trailing space), `"Sal-Por6"`, `"COD-LOIN "`. In on-hand: 1 row on Nov 15
  (`shr-1620 `, **80 cs at PVD**). In sales: 72 rows. In POs: 5 rows (including the cancelled 500 cs `Sal-Por6`).
- **Why it matters:** without fixing, 80 cs of 16/20 shrimp would vanish from the count.
- **Rule:** canonical code = `strip().upper()`. Each raw variant is stored in `item_aliases`, and every corrected row is logged `corrected`.
- **Test:** `test_T02_item_codes_canonicalized` (P2) · golden G04.

### T10 Mixed units in lots
- **Found:** case items with lots in pounds: CAL-RING NB L261005-02 = 132 lb; LOB-T56 NB L261027-01 = 220 lb and PVD
  L261103-01 = 160 lb. The unit cost on those lots is **per lb** (2.71, 23.66, 24.66).
- **Why it matters:** Dana: "Sometimes a vendor ships a case item in pounds" (00:05:50). Adding 220 "lb" as 220 cases
  would massively overstate lobster tails.
- **Rule:** convert every lot to the item's `sell_uom` using `lb_per_case` from `data/reference/pack_sizes.csv`.
  LB lot of a CS item: qty ÷ lb_per_case and cost × lb_per_case. Keep the source qty/uom/cost alongside. A missing factor
  excludes the lot and logs an `error`.
- **Also found in Phase 2 (not in the original audit):** two LOB-T56 purchase orders were entered in LB
  (PO-260258 900 lb, PO-260271 800 lb). Both were received long ago, so nothing is incoming. The same conversion rule
  applies to any open PO line in pounds, and these two are flagged for information.
- **Test:** `test_T10_lb_lots_converted_to_cases` (P2) · golden G05, G06.

### T11 Hold and damaged pseudo-locations
- **Found (Nov 15):** QA-HOLD: HAD-FIL 300 cs, SHR-1620 80 cs, CRAB-SNW8 40 cs (420 total). DAMAGED: CRAB-SNW5 2,
  POL-FIL 3, SAL-POR4 4, SCL-U10 6, SHR-2630 5 (20 total).
- **Why it matters:** Walt: "If I can't sell it, it isn't inventory" (00:04:40).
- **Rule:** not sellable (`data/reference/locations.csv`). QA-HOLD is shown separately as "on hold, may come back"; DAMAGED as "not counted".
- **Test:** `test_T11_hold_and_damaged_not_sellable` (P2) · golden G04, G08.

### T12 Zero-quantity split lots
- **Found:** 8 rows on Nov 15 with qty 0, mostly lots with a `B` suffix (e.g. `L260911-01B`).
- **Rule:** skip and log as `info`.
- **Test:** `test_T12_zero_qty_lots_skipped` (P2).

### T13 Negative adjustment lines
- **Found:** `ADJ-2211` COD-FIL −2 cs, `ADJ-7360` SHR-2630 −6 cs, `ADJ-1069` POL-BLK −40.5 lb. They have no pack, expiry or received dates, all at NB.
- **Rule:** net them against the item's sellable total (conservative) and log as `warning`. Assumption A07 (not asked of Dana).
- **Test:** `test_T13_adj_lines_netted` (P2) · golden G07.

### T14 Expired lots
- **Found:** SAL-POR8 L250303-01 60 cs at HCS (expired 2026-10-20). SHR-4150 L241202-01 18 cs at PVD (expired
  2026-08-30). All ZZ lots expired 2023–2024.
- **Rule:** not sellable. Shown in "stuck with" as a write-off.
- **Test:** `test_T14_expired_lots_not_sellable` (P2) · golden G09.

### T15 The six-month line
- **Found:** AS_OF + 6 months = **2027-05-16**. Inside the line: SAL-POR6 all 3 lots (300 NB + 600 HCS + 450 HCS =
  **1,350 cs, 1,050 at Harbor, ≈ $81,233 at cost**), SAL-POR8 L260720-02 380 cs (HCS), TIL-FIL 140 cs (HCS). SAL-POR8
  L260817-02 (320 cs, expiry 2027-05-30) is just outside.
- **Why it matters:** Dana: "nobody will take it with less than six months left" (00:03:30).
- **Rule:** these lots still count as sellable for run-out (Dana discounts them) but are flagged "inside six-month line" in "stuck with".
- **Test:** `test_T15_six_month_line_flagged` (P3) · golden G10.

### T30 Received date is not age
- **Found:** SAL-POR6 lots were **packed Feb–Apr 2025 but received Jul–Aug 2026**, so Dana bought already-old stock.
  `shelf_life_months` is blank on several items.
- **Rule:** always use the lot's `expiry_date` for age and the six-month line. Never `received_date` or `shelf_life_months`. (A12)
- **Test:** `test_T30_age_uses_expiry_not_received` (P3).

### T31 Lots disappear between nights
- **Found:** POL-FIL and SCL-U10 lot L260601-09 (3 cs each) exist Nov 14 and are gone Nov 15.
- **Rule:** absence in the latest snapshot means sold out, not missing data. Informational only.
- **Test:** `test_T31_missing_lot_means_sold_out` (P2, documents the behavior).

## Item master (`items`)

### T03 Duplicate item master rows
- **Found:** the three alias rows from T02 exist alongside the canonical rows, all with created_date 2021-04-12 (looks like a
  botched migration) and mostly missing UPC/bin.
- **Rule:** collapse to one item per canonical code, keeping the row whose raw code already equals the canonical code. Dropped rows are logged.
- **Test:** `test_T03_duplicate_item_rows_collapsed` (P2) · golden G02 (45 items).

### T04 Status is free text
- **Found:** `Active`, `A`, `active`, blank, `Discontinued`, `DISC`.
- **Rule:** normalize. **Blank does NOT mean discontinued** (LOB-MEAT and PAN-PORT4 are blank and actively selling).
  Only `DISC`/`Discontinued` mean discontinued.
- **Test:** `test_T04_blank_status_is_not_discontinued` (P2).

### T05 Legacy ZZ items
- **Found:** 6 items start with `ZZ-`. `ZZ-SCL-0002` is marked `Active`. 4 of them hold **59 cs at Harbor**
  (ZZ-SHR-0001 35, ZZ-SAL-0007 12, ZZ-SCL-0002 8, ZZ-LOB-0004 4), all long expired.
- **Why it matters:** Dana: "Anything starting with ZZ is from the old system, and we never deleted those" (00:04:40).
- **Rule:** lifecycle `legacy` regardless of status. Never in the order list. Their stock appears in "stuck with" as a write-off.
- **Test:** `test_T05_zz_items_are_legacy` (P2) · golden G03, G17.

### T06 Quietly dead items
- **Found:** TIL-FIL last real sale 2026-04-16 (140 cs at Harbor, vendor OCN "old"). SHR-6170 last sale 2026-03-05 (60 cs
  at Harbor, status blank). PAN-1012 last sale 2026-02-10 (no stock, status `A`).
- **Why it matters:** Dana: "Some items we just stopped buying" (00:04:40).
- **Rule:** lifecycle `dormant` when there is no real demand in the last `DORMANT_NO_SALES_DAYS` (60) days AND no open PO.
  Never suggest reordering. Stock appears in "stuck with". **Confirmed by Dana 2026-11-26** ("we've stopped carrying all
  three. Flag what's left at Harbor so I can clear it", A05). Dana can reactivate an item via `item_settings`.
- **Test:** `test_T06_dormant_items_detected` (P2) · golden G03, G17.

### T07 Fresh items
- **Found:** 6 `FR-` items, storage FRESH, vendor BBD, sold in LB. 2,856 fresh sales lines.
- **Why it matters:** Dana: "Fresh is local… that's a separate thing. It's daily and I don't need help with it" (00:00:00).
- **Rule:** lifecycle `fresh_out_of_scope`. Excluded everywhere in planning, including the golden counts for expired and
  six-month-line lots (see the note under G09).
- **Test:** `test_T07_fresh_items_out_of_scope` (P2) · golden G03, G11, G17.

### T08 Category casing
- **Found:** `groundfish`, `SALMON`, `SHRIMP`, `shrimp`.
- **Rule:** normalize with strip + title case (matters for category seasonality, T23/§6.7).
- **Test:** `test_T08_category_casing_normalized` (P2).

### T09 Pack size is free text
- **Found:** `6x2.2lb`, `5kg` (metric!), `10 lb cs`, `10#`, `10/2#`, `5x2#`, `5 x 2 lb`, `15 lb case`, `16.5 lb block`,
  `catch wt`, `per lb`, blank.
- **Why it matters:** Dana: "it's whatever someone typed… It's not a number" (00:05:50).
- **Rule:** the human-verified table `data/reference/pack_sizes.csv` is the source of truth (ADR-012). A regex parser
  exists only to validate the table and flag new items. Unparseable or missing → `data_issues` error.
- **Test:** `test_T09_pack_size_table_matches_parser` (P2).

## Sales (`sales_lines`)

Classification order (§6.2): cancelled → transfer → credit → sample → one_off → fresh_out_of_scope → real_demand.

### T16 Transfers recorded as sales
- **Found:** customer INT01 "TRANSFER - PVD" (type INTERNAL), 378 lines, about 5,444 units.
- **Why it matters:** Marco: "moving stock from New Bedford to Providence gets entered as a sale" (00:06:50).
- **Rule:** exclude from demand by **customer type INTERNAL**, not by name (ADR-014).
- **Test:** `test_T16_transfers_excluded_by_customer_type` (P2) · golden G11.

### T17 Samples recorded as $0 orders
- **Found:** 104 INVOICED lines with unit_price 0, all 1 cs.
- **Rule:** exclude from demand. Samples do physically consume stock (about 2 cs/week in total), which is negligible (A09).
- **Test:** `test_T17_zero_dollar_samples_excluded` (P2) · golden G11.

### T18 Credits recorded as negative sales
- **Found:** 76 lines, order_no starts with `CM-`, negative qty.
- **Rule:** exclude from demand (we count what customers ordered). Returned goods that go back on the shelf are already
  in the snapshot (A08).
- **Test:** `test_T18_credits_excluded` (P2) · golden G11.

### T19 Cancelled sales
- **Found:** 294 CANCELLED lines.
- **Rule:** exclude.
- **Test:** `test_T19_cancelled_sales_excluded` (P2) · golden G11.

### T20 Cruise line one-off
- **Found:** order SO-245503, 2026-03-30, CRU01: SHR-1620 330 cs + SHR-2125 240 cs.
- **Why it matters:** Marco: "about six weeks of shrimp in one go. They never came back" (00:06:50).
- **Rule:** exclude by **order number** listed in `data/reference/excluded_orders.csv`, not by customer (if the cruise line
  returns, its new orders count) (A10, ADR-014).
- **Test:** `test_T20_one_off_order_excluded_by_order_no` (P2) · golden G11.

### T21 Mixed date formats
- **Found:** 51 sales rows have order_date and ship_date as `MM/DD/YYYY` (e.g. `01/31/2026`); the rest are ISO.
- **Rule:** parse both. US format is unambiguous here (the second component reaches 31). Logged as `corrected`.
- **Test:** `test_T21_us_dates_parsed` (P2) · golden G12.

### T22 Open sales orders are committed stock
- **Found:** 180 OPEN lines (159 real-demand frozen lines), order dates Nov 9–15, ship dates Nov 16–Dec 15. These include grocery
  holiday pre-bookings, e.g. Seabright SO-251062 **120 cs SHR-1620 shipping Dec 14**, and CRAB-SNW5 80 + 70 cs shipping Dec 8 and Dec 10.
- **Why it matters:** Dana: "That stock is already spoken for, even though it's still in the building" (00:08:30).
- **Rule:** deduct each open line on its **ship date** in the projection (ship dates before AS_OF deduct on day 0). They also
  count as real demand in history, by order date (A11, ADR-013).
- **Test:** `test_T22_open_orders_deducted_on_ship_date` (P3) · golden G13.

### T23 Censored demand (a stockout hides true demand)
- **Found:** SHR-1620 has **zero sales from 2025-12-11 to 2026-01-02** while every other shrimp rose in December. Last sale
  before was 2025-12-10 and first after was 2026-01-03 (re-checked 2026-11-25, including MM/DD/YYYY rows). This is last year's stockout.
- **Why it matters:** Dana: "we ran out of 16/20 shrimp ten days before Christmas" (00:01:10). Treating those zero days as
  low demand would make December look slow for exactly the item that runs out in December.
- **Rule:** seeded in `data/reference/stockout_periods.csv`. Stockout days are excluded from all rate calculations, and
  category-level seasonality means one censored item can't flatten its own December (A06).
- **Test:** `test_T23_stockout_days_excluded_from_rate` (P3).

## Purchase orders (`purchase_orders`)

### T24 Duplicate PO lines
- **Found:** PO-260439 line 1 (BXE SHR-2630, 500 cs, open) and PO-260445 line 1 (MNP HAD-LOIN, 200 cs, open) each appear twice, identical.
- **Rule:** drop exact duplicate rows and log them. Incoming must be 500 and 200, not 1,000 and 400.
- **Test:** `test_T24_duplicate_po_lines_dropped` (P2) · golden G14.

### T25 PO statuses and partial receipts
- **Found:** Received (271), Closed (86), Open (16 rows, 14 unique), Cancelled (4, including PO-260423 `Sal-Por6` 500 cs).
  PO-260376 PAN-0709: 1,000 ordered, 600 received, still Open.
- **Why it matters:** Dana: "Some arrive in part, say 600 of 1,000 cases, and the PO stays open for the other 400" (00:08:30).
- **Rule:** Received and Closed = complete. Cancelled = ignore. Only Open lines are incoming, with **remaining = ordered − received**.
- **Test:** `test_T25_only_open_po_remaining_is_incoming` (P2) · golden G14.

### T26 Stale PO expected dates
- **Found:** BlueTide dates new Vietnam POs with the old 56-day lead time. PO-260443 SHR-1620 ordered 2026-11-02 "expected"
  2026-12-28, real ≈ **2027-01-25**. Overdue open POs: PO-260394 SHR-2125 800 cs expected 2026-10-05, nothing received;
  PO-260376 PAN-0709 remaining 400 expected 2026-09-14; PO-260407 CAL-RING 300 cs expected 2026-10-19.
- **Why it matters:** Dana: "The quantities are right, the dates aren't… I have open POs that say they arrived three weeks
  ago but are still on the water" (00:08:30).
- **Rule (§6.6, amended by A18 and by Dana's reply, A03):** `candidate = max(BlueTide date, order_date + effective lead
  time)`. A date set by Dana wins. Otherwise, if `candidate <= AS_OF`, the PO is **late**: flagged "late, confirm with
  vendor" and **not counted as coming** until Dana types in a real date (Dana 2026-11-26: "please don't assume they'll
  arrive within a week"). Any item that only a late PO would cover is called out ("If an item is only covered by a late
  PO, I want to see that"). Otherwise ETA = candidate. Flagged "BlueTide date has passed" whenever BlueTide's date < AS_OF.
- **Test:** `test_T26_overdue_open_po_flagged` (P2: the loader flags BlueTide dates that have passed) and
  `test_T26_po_eta_rederived` (P3: the engine re-derives the arrival date) · golden G15.

### T27 Vendor lead time problems
- **Found:** BXE `56` (stale; Dana says 10–12 weeks). AFS blank (Dana: about 6 weeks). DLC `"2-3 wks"` (text). MNP 14 (matches
  Dana). ASP 28 (not discussed).
- **Rule:** keep BlueTide's value (`lead_time_days_system`, parsed; "2-3 wks" → 21, the upper bound) and Dana's value
  (`vendor_settings`) separately. Effective = Dana's value if present. Seeds: `data/reference/vendor_settings_seed.csv` (A01).
- **Test:** `test_T27_effective_lead_time_prefers_dana` (P2) · golden G16.

## Vendors, customers, prices

### T28 Vendor table oddities
- **Found:** AFS payment_terms = `CAD` (currency in the wrong column). HCS = Harbor Cold Storage (a storage provider, not a
  seafood vendor). OCN "Oceanic Trading Corp (old)" (legacy vendor for TIL-FIL and the ZZ items). BBD = day boats (fresh).
- **Rule:** classify `vendor_type` from `data/reference/vendor_types.csv` (ADR-018): stock_supplier (BXE, AFS, MNP, ASP,
  DLC), fresh_supplier (BBD), service_provider (HCS), legacy (OCN). Log the AFS anomaly as `flagged`.
- **Test:** `test_T28_vendor_types_classified` (P2).

### T29 Price list quirks
- **Found:** FUEL-SURCH rows (uom EA, three open-ended effective ranges) and a GROCERY tier. **Also found in
  Phase 2:** a fourth surcharge row coded `FUEL SURCHARGE` (with a space, tier STD, $0.35 per LB, from 2026-03-01), a
  different spelling and a per-pound rate. Flagged for Marco's phase 2.
- **Rule:** out of scope (Marco, phase 2). Load into raw + a clean `prices` table and log only; no UI.
- **Test:** `test_T29_price_list_loaded_not_used` (P2).

---

## Golden facts (asserted in `backend/tests/golden/test_real_data.py`)

Computed from the raw files in the planning chat. **If the loader disagrees, the loader is probably wrong.** Investigate
before changing a test. The "Re-checked" column records an independent recomputation on 2026-11-25 (Phase 0) with the
Python stdlib `csv` module, before any app code existed.

**Phase 2 status (2026-11-25):** G01–G14 and G16 are asserted by `backend/tests/golden/test_real_data.py` and all pass.
`scripts/profile_data.py` re-derives the same facts with separate code (no app imports), and every one matches. The same
numbers were recomputed in SQL against the loaded Supabase database (load run #4), and they match too. G15 and G17 need
the planning engine (Phase 3).

| ID | Fact | Re-checked 2026-11-25 |
|---|---|---|
| G01 | Latest snapshot = 2026-11-15; the 115 rows dated 2026-11-14 are excluded | ✅ |
| G02 | 45 canonical items after collapsing 3 alias rows (`"COD-LOIN "`, `"Sal-Por6"`, `"shr-1620 "`) | ✅ 48 rows → 45 |
| G03 | Lifecycle counts: active 30, dormant 3 (TIL-FIL, SHR-6170, PAN-1012), legacy 6, fresh_out_of_scope 6, discontinued 0. Precedence fresh > legacy > discontinued > dormant > active | Partly (last-sale dates ✅; full count needs the loader) |
| G04 | Sellable SHR-1620 = **480 cs** (NB 260 + HCS 140 + PVD 80 from alias `shr-1620 `). On hold 80 | ✅ |
| G05 | Sellable LOB-T56 = **83 cs** (45 cs + 220 lb ÷ 10 + 160 lb ÷ 10) | ✅ |
| G06 | Sellable CAL-RING = **353 cs** (263 + 132 lb ÷ 13.2 + 80) | ✅ |
| G07 | ADJ netting: COD-FIL = 206 cs, SHR-2630 = 429 cs, POL-BLK = 8,478.5 lb | ✅ |
| G08 | HAD-FIL sellable 170 cs, on hold 300 cs | ✅ |
| G09 | Expired lots of in-scope items: exactly SAL-POR8 L250303-01 (60 cs) and SHR-4150 L241202-01 (18 cs). SAL-POR8 sellable = 700. SHR-4150 sellable = 381 | ✅ (see note) |
| G10 | Non-expired lots of in-scope items with expiry < 2027-05-16: exactly SAL-POR6 ×3 (1,350 cs), SAL-POR8 L260720-02 (380 cs), TIL-FIL L250602-01 (140 cs) | ✅ (see note) |
| G11 | Sales demand_class counts: real_demand 12,040; fresh_out_of_scope 2,856; transfer 378; cancelled 294; sample 104; credit 76; one_off 2 | ✅ |
| G12 | 51 sales rows parsed from MM/DD/YYYY | ✅ |
| G13 | Committed (OPEN, real demand): SHR-1620 = 201 cs, CRAB-SNW5 = 221 cs, SHR-2125 = 91 cs; 159 open real-demand lines | ✅ |
| G14 | POs: 2 exact duplicate rows removed; 14 open lines; incoming SHR-2630 = 500, HAD-LOIN = 200, PAN-0709 = 400, POL-BLK = 18,000 lb; PO-260423 (cancelled) contributes 0 | ✅ (2 dups, 14 open) |
| G15 | ETAs: PO-260443 SHR-1620 = 2027-01-25 (BlueTide 2026-12-28). PO-260394 SHR-2125, PO-260376 PAN-0709 and **PO-260407 CAL-RING (A18)** are late and **not counted as coming** (Dana 2026-11-26; the original fact assumed 2026-11-23). PO-260436 PAN-0507 = 2026-12-28 (BlueTide 2026-11-30). PO-260444 LOB-T810 = 2026-11-27 (BlueTide 2026-11-23) | ✅ (hand-simulated rule); amended by Dana's reply |
| G16 | Effective lead times BXE 84, AFS 42, MNP 14, ASP 28, DLC 21. System values BXE 56, AFS null, DLC 21 (parsed from "2-3 wks"), MNP 14, ASP 28 | Inputs ✅ |
| G17 | No legacy, dormant or fresh item ever appears in the order list | Needs the engine (P3) |

**Note on G09 and G10 (found while re-checking, 2026-11-25).** BUILD_PROMPT words these as "non-legacy" lots. Read
literally, that would also include fresh items: FR-FLK L261104-01 (18 lb) is expired, and all six FR- lots expire within days,
so they fall inside the six-month line. Fresh is out of scope everywhere (T07), so the golden tests scope G09 and G10 to
**in-scope items** (lifecycle not legacy and not fresh_out_of_scope; dormant items such as TIL-FIL are included). This clarifies the wording; it does not change any rule. The trust-strip total "78 cs expired"
(60 + 18) agrees with this reading.
