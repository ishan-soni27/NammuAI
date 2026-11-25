# Kestrel Bay Inventory App: Build Prompt for Claude Code

> **Owner:** Ishan Soni. Written with Claude (claude.ai) before any code existed.
> **How to use:** this file lives at the repo root as `BUILD_PROMPT.md`. Claude Code, read the entire file before doing anything. It is the single source of truth for context, requirements, business rules, architecture and working style. Everything Ishan and Claude discussed in the planning chat is synthesized in §4, because you cannot see that chat.

---

## 0. Your role and how we work together

You are a senior full-stack engineer pairing with **Ishan Soni** on a take-home assignment for **Nammu**. Ishan owns every decision. You implement, explain tradeoffs, and flag problems. Ishan is being assessed on *how he works with AI*, so the way we work matters as much as the code.

**Working agreement (follow all of these, every session):**

1. **Read first.** Before writing code, read this whole file, `docs/client/kickoff-call-transcript.md`, `docs/client/ASSIGNMENT.md`, and look at the headers and a few rows of every file in `data/raw/`.
2. **Phases with stop points.** Work through the phases in §14. At the end of each phase, STOP and post a summary: what you did, what Ishan should verify (exact commands, URLs, numbers), open questions, and what the next phase will do. Wait for "go".
3. **Plan before coding.** At the start of each phase, post a short plan (files to create or change, tests to add, risks) and wait for approval, unless Ishan explicitly says to continue without stopping.
4. **Never invent or silently change a business rule.** Rules live in §6 and in `backend/app/config/business_rules.py`. If the data contradicts a rule or a rule is ambiguous, stop and ask. If you must proceed without an answer, choose the **conservative option** (the one that makes a stockout less likely, because Dana says running out hurts more than overstock), record it in `docs/ASSUMPTIONS.md`, and tell Ishan.
5. **Never tune logic to match the answer key in §7.** It is a sanity check from a rough model. If results differ materially, investigate and explain why.
6. **Comment generously** (§12). The codebase must be maintainable by a future engineer, scalable to the client's needs, and defensible line by line in a live review.
7. **Update `docs/PROMPT_LOG.md` after EVERY prompt from Ishan**, before your final message in that turn (§13.2). No exceptions. This includes tiny prompts, prompts where nothing changed, and prompts where you made a mistake.
8. **Commit in small, logical units** with conventional messages (`feat(loader): …`, `fix(planning): …`, `test: …`, `docs: …`). Never commit secrets (`.env` stays local, `.env.example` is committed).
9. **Prove it works.** Run `pytest` and `npm run build` (plus lint) before saying something is done. Paste the key output.
10. **Prefer boring, well-known solutions.** The whole build is budgeted at roughly 4 to 6 hours of Ishan's time. P0 correctness beats breadth. Cut P1 before cutting P0 quality.
11. **Never read the system clock for business logic.** "Today" is `AS_OF_DATE = 2026-11-16`, configurable through the environment. Timestamps for logs and audit use real UTC time; business dates use `AS_OF_DATE`.
12. **Never modify `data/raw/`.** Those files are exactly as Kestrel Bay exported them from BlueTide. All cleaning happens in code, and every change is logged (§10).
13. **No hard-coded item codes, order numbers or customer codes in logic.** Business-specific facts (the cruise order, the known stockout, lead times, pack sizes) live in `data/reference/*.csv` seeds or in config, so they are visible, editable and testable.

---

## 1. The assignment (Nammu's email to Ishan, fully restated)

- **Kestrel Bay Seafood** is a fictional seafood distributor. Nammu had a kickoff call with them on Nov 10, 2026. Their VP of Purchasing, **Dana Okafor**, needs help with her Monday ordering.
- **Materials:** `kickoff-call-transcript.md` is the primary source of requirements. `data/` holds the exports Kestrel Bay sent afterwards, exactly as they came out of their system (BlueTide).
- **Task:** build Dana an inventory app. It should be a small, working web application with a **backend, database, and frontend**, deployed to a **live link** (free hosting is fine). No ETL pipeline is needed. **Loading the CSVs into the database once is fine.**
- **Time:** aim for 4 to 6 hours. Any tools or technologies, including AI. Nammu encourages AI and wants to see how Ishan works with it.
- **Questions:** email the recruiter, who answers as Dana would. Treat it like a real customer exchange.
- **Submit at least 24 hours before the live review:** (1) GitHub repo, (2) live app link, (3) README covering what was built and why, key assumptions, what was left out of scope, what to do next with more time, and how AI tools were used.
- **Live review, 45 minutes:**
  1. **Demo (10 min):** present the app to "Dana". She is sharp, non-technical, and skeptical of numbers she doesn't understand.
  2. **Decisions (15 min):** data model, API, UI choices, assumptions, technical tradeoffs.
  3. **Live change (15 min):** they introduce a small new requirement and Ishan implements it while screensharing. **The code must be easy to change quickly.**
  4. **Ishan's questions (5 min).**
- **From the assignment README in the zip:** treat **Monday, November 16, 2026** as today. The kickoff call was Nov 10, and the data runs to the Nov 15 snapshot. Use Nov 16 for anything date-based (expiry, run-out, lead times), not the computer's clock. Questions go by email, or make a reasonable assumption and write it down.

---

## 2. Repo inputs (Ishan adds these before the first prompt)

```
BUILD_PROMPT.md                         # this file
docs/client/ASSIGNMENT.md               # the zip's README.md, renamed
docs/client/kickoff-call-transcript.md  # unchanged
docs/client/email-to-dana.md            # the email Ishan sent (text in §4.4)
docs/client/dana-replies.md             # empty until Dana replies; Ishan pastes replies here
data/raw/customers.csv
data/raw/inventory_on_hand.csv
data/raw/items.csv
data/raw/price_list.csv
data/raw/purchase_orders.csv
data/raw/sales_lines.csv
data/raw/vendors.csv
```

**File handling notes:** the CSVs use CRLF line endings. Read every column as a string first (pandas: `dtype=str, keep_default_na=False`) so that trailing spaces in codes, leading zeros in UPCs, blanks and odd values are preserved exactly for the raw layer. Parse types only in the cleaning step.

---

## 3. Customer background (synthesized from the kickoff call, Nov 10, 2026)

**Attendees:** Ishan (Nammu); Walt Brennan (CEO), Dana Okafor (VP Purchasing) and Marco Ruiz (VP Sales), all of Kestrel Bay.

### 3.1 The business
- Distributor out of **New Bedford, MA**. About **forty active items, mostly frozen**. Sells to **restaurants and a couple of small grocery chains**. Dana does all the buying. Marco runs sales.
- **Suppliers.** Frozen is mostly imported. Shrimp and pangasius come from **Vietnam** (vendor Bien Xanh, BXE). Salmon portions come from **Chile** (Austral Frío, AFS). Cod, haddock and snow crab come from **Canada** (Maritime Northern Pack, MNP). Pollock blocks come from **Alaska** (Aleutian Shore, ASP). Lobster tails come from **Maine** (Downeast Lobster, DLC). **Fresh fish** comes from local day boats every morning (Buzzards Bay Day Boats, BBD). Fresh is a separate daily process, and **Dana does not need help with it**.
- **Three real locations:** New Bedford (NB, main), Providence (PVD, smaller), and **Harbor Cold Storage (HCS)**, a third-party overflow warehouse that **charges by the pallet every month**. For ordering, Dana does not care which building stock is in ("It's all mine, and we move it around"). Harbor matters only because of the cost. **"Long stock sitting at Harbor is the worst case"** (Walt).
- **Two pretend locations** in the warehouse system: **QA-HOLD** (waiting on paperwork or a temperature check; sometimes it passes and comes back) and **DAMAGED** (written off eventually). Both show up as on hand in BlueTide. Walt: **"If I can't sell it, it isn't inventory."**

### 3.2 Dana's Monday process today
- Every Monday she pulls the on-hand report and last month's sales from **BlueTide** ("ancient"), puts both in Excel, and goes line by line. **It takes half the day**, because the reports don't agree with each other. Some things are in cases and some in pounds, so she converts in her head.
- She is trying to find out **two things: what she is going to run out of, and what she is sitting on too much of.**
- **Running out hurts more.** Last December they ran out of **16/20 shrimp ten days before Christmas**. She saw it coming, but too late, because Vietnam shrimp takes **ten to twelve weeks door to door**. Marco had to call every account: "I'd rather argue about price than tell a chef we're out."
- The core insight: **the problem isn't knowing you're low, it's knowing early enough.** "Last month's sales tells me where I've been. It doesn't tell me that if I don't order this week, I'm out in March."

### 3.3 Lead times (Dana's real numbers vs BlueTide)
- **Vietnam: 10 to 12 weeks.** It used to be 8, and the vendor sheet in BlueTide still says 8 for Bien Xanh.
- **Chile: about 6 weeks.** Dana doesn't think it is even in the system.
- **Canada: about 2 weeks.**
- **Day boats: next day** (fresh, out of scope).
- Alaska and Maine were not stated on the call (asked in the email, §4.4).
- Walt: "Half of what we actually know lives in Dana's head, not the system. If she's out for two weeks, I'm blind."

### 3.4 Sitting on too much
- Right now it's the **Chilean salmon**. Dana bought heavy over the summer because the price was good, and those lots are getting old.
- Frozen is good for **18 to 24 months from the pack date**, but **nobody will take it with less than six months left**. Once a lot is inside six months, she is discounting it or dumping it. **The expiration date is on every lot.**
- It costs money while it sits, especially at Harbor (per pallet per month).

### 3.5 What success looks like
- Walt: **"One screen on Monday morning that tells us what we need to order and what we're stuck with. And it has to be right. Nobody trusts the current reports because they count things that aren't really there."**
- Things that aren't really there: stock on QA-HOLD and DAMAGED, and **dead items**. Anything starting with **ZZ** is from the old system and was never deleted. There is supposed to be a discontinued status, but people don't always set it. Some items they just stopped buying.

### 3.6 Units
- **Salmon sides** are tracked in pounds (catch weight, every side weighs something different). **Bulk pollock blocks** too. Everything else is mostly cases.
- Sometimes a vendor ships a case item in pounds and the warehouse receives it that way. **Each lot has a unit column, CS or LB.**
- The pack size on the item is free text ("10 lb cs", "4x2.5lb"). It is not a number.

### 3.7 Odd things in the exports (as described on the call)
- The on-hand export runs nightly, and **sometimes the file has two nights in it**. There is a date column.
- **Sales data (Marco):** samples are entered as **zero-dollar orders**. Returns are entered by accounting as a **credit, which shows up as a negative sale**. BlueTide can't do transfers between buildings, so moving stock from New Bedford to Providence is entered as a **sale to a customer called "TRANSFER - PVD"**. Dana: "Which all ends up in my sales numbers. I think I filter the transfers out. Mostly."
- **Last spring a cruise line ordered about six weeks of shrimp in one go and never came back. One-off.**

### 3.8 Seasonality
- **Lent** is huge, from late February to Easter: cod, haddock, pollock, anything white.
- **Holidays:** crab, shrimp and lobster tails.
- **Summer** is slower for frozen.
- "Right now last month's sales is October, which is slow, and December won't be. I know that, so I adjust in my head."
- Reference dates: Lent 2026 ran from Feb 18 (Ash Wednesday) to Apr 5 (Easter). **Lent 2027 runs from Feb 10 to Mar 28**, about a week earlier.

### 3.9 How much to order
- Mostly gut. **On imports she likes about two weeks of extra stock on top, because ships slip. Canada, less.**
- She has to **check open POs or she'll double order**.
- She also checks **Marco's open orders** (booked but not shipped). **That stock is already spoken for, even though it is still in the building.**

### 3.10 PO report reliability
- **Quantities are right, dates aren't.** The arrival date is whatever the vendor said when she ordered, and nobody updates it. She has **open POs that say they arrived three weeks ago but are still on the water**.
- If a PO had really arrived, it would have been received and closed.
- **Partial arrivals:** e.g. 600 of 1,000 cases arrive and the PO stays open for the other 400.
- The report also includes **received and cancelled POs**, which must be filtered out.

### 3.11 Things Dana knows that the system doesn't
- The **real lead times**.
- When she orders by phone, the PO doesn't go into BlueTide until the vendor confirms, which can take a week. She wants to be able to tell the tool **"I've handled this one."**

### 3.12 Marco (phase 2, not now)
- A customer calls wanting forty cases of 16/20s for Thursday. Marco needs to know if they have them and what to charge, so today he walks over to Dana. There is a price list, "sort of up to date, with the fuel surcharge mixed in". He'd also love route planning and something that writes his emails.
- **Walt: "Dana first." Marco: "Dana first. I know."**

### 3.13 Adoption constraints
- **"If it needs training, I won't use it. If I open it and it doesn't make sense within about a minute, I go back to Excel."** Mostly on her **laptop**, sometimes her **phone**.
- **"If it says I'm out in three weeks, I want to click in and see what I have, what I'm selling and what's coming. Otherwise I'll go check my spreadsheet, and then what's the point."**

### 3.14 The agreed playback (this is the spec; Dana and Walt both said "That's it")
> On Monday, Dana needs one screen that answers two questions. First, what will run out before a new order could get here? That counts what's already on order and uses the real lead times. Second, what are you stuck with, especially stock inside the six-month line or long stock sitting at Harbor? It counts only sellable stock and real demand: no hold, no damaged, no dead items, no transfers, no samples. You can click into any item and see why. And you can tell it things it doesn't know, like "I've already ordered this." Fresh is out for now, and Marco's questions come after Dana's.

---

## 4. What happened before Claude Code (synthesis of Ishan's planning chat)

You cannot see this chat, so here is everything relevant, in order.

### 4.1 Planning session 1: data audit and strategy (claude.ai)
- Ishan asked for a rundown of every file, the transcript, how to approach the assignment, how to prioritize, which questions to ask Dana, and how to use AI well.
- Claude unzipped the materials, read the transcript, and **profiled every CSV with pandas**. It found about 30 data traps, each mapped to something said on the call (full list in §5).
- Claude built a **rough Python model** of the correct answer (category seasonality × recent rate, corrected PO dates, open orders deducted on ship date). Its output is the answer key in §7. Headline finding: **SHR-1620 (16/20 shrimp) projects to run out around Dec 14, 2026, ten days before Christmas, exactly like last year.** The system hides it because the 600-case PO that BlueTide says lands Dec 28 was dated with the stale 8-week lead time. At 12 weeks it lands about Jan 25. This is the **demo opener**.
- Claude proposed the priority board (§11), a step-by-step plan, and AI-usage guidance (§4.3).

### 4.2 Planning session 2: Ishan's decisions
Ishan decided the following. Treat these as fixed requirements.
- **Database: Supabase** (managed Postgres).
- **Backend: Python. Frontend: React.** (Ishan is strongest in Python and React.)
- **Web-first.** Desktop browser is the primary target. It must still be readable on a phone, but desktop comes first.
- **Log everything.** Interpreted as four layers, and Ishan accepted this (§10):
  1. structured application logs for every request and calculation,
  2. a record of every row dropped or changed during the data load, with the reason,
  3. an audit trail of every change a user makes (lead times, PO dates, items marked handled), with timestamp and actor,
  4. an AI usage log (`docs/PROMPT_LOG.md`) for the README.
- **Comments everywhere.** The project must be maintainable later and scalable to the client's needs.
- **Every design decision must be defensible**, with the tradeoff stated (`docs/DECISIONS.md`, §13.3).
- **`docs/PROMPT_LOG.md`** must keep a simplified description of every prompt Ishan gives, what it changed, and what it impacted (§13.2).
- Ishan will later ask Claude (in claude.ai, not Claude Code) for two color-coded PDFs: one with all data traps, and one with the P0, P1 and P2 requirements and the reasoning for each. Not your job, but keep `docs/DATA_AUDIT.md` and the priorities in the README consistent with §5 and §11 so the PDFs and the repo agree.
- After the MVP works, Ishan will **iterate** with you, prompt by prompt, on things he wants tweaked (§14, iteration protocol).
- The UI in §9 is Claude's **v1 proposal**. Ishan said UI decisions would be made "later based on suggestions", so build v1 as specified and expect him to change it.

### 4.3 AI-usage guidance Ishan received (what you should help him demonstrate)
- **Ishan decides, AI implements.** Business decisions are logged in `docs/ASSUMPTIONS.md` and `docs/DECISIONS.md` with Ishan as the decider.
- **Plan first, small diffs, read every diff.** The commit history should show incremental work, not one giant dump.
- **Record every time the AI was wrong and how it was caught** (for example, a test catching double-counted snapshot nights). These stories are valuable in the review. Log them honestly in PROMPT_LOG, including your own mistakes.
- **One test per data trap**, so correctness is provable.
- **Ishan must be able to explain every rule in his own words.** Write explanations in docs and comments that help him learn the code, not just run it.

### 4.4 Email to Dana (sent by Ishan; replies pending)
The first draft was rewritten to be shorter, less ambiguous and less daunting, with Claude's best guess in brackets after each question so Dana can just say yes or give a number. At Ishan's request it uses no colons or semicolons. This is the text that was sent. **The bracketed guesses are the defaults you must implement until Dana replies.** Save it as `docs/client/email-to-dana.md`.

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

**Promise made in Q3:** late POs are flagged as late, and **Dana can type in a real arrival date**. PO date override is therefore P0.

**When Dana replies:** Ishan pastes the reply into `docs/client/dana-replies.md`. Then you update the relevant seed CSVs and config, flip the matching rows in `docs/ASSUMPTIONS.md` from "Pending Dana" to "Confirmed by Dana (date)", re-run the loader if needed, update tests, and log it in PROMPT_LOG.

### 4.5 Planned follow-up email (Ishan's task, not yours)
Midway through the build, Ishan will send Dana a short validation email with a screenshot, along the lines of "the tool says 16/20s run out around Dec 14, does that match your gut?" Make sure the dashboard looks screenshot-ready by the end of Phase 5.

---

## 5. Data audit: every trap found, with the rule to apply

Each trap has an ID (T01 to T31). Use these IDs everywhere: in `data_issues.trap_id`, in test names (`test_T01_latest_snapshot_only`), in code comments, and in `docs/DATA_AUDIT.md`. That traceability is how Ishan proves in the review that every rule exists for a reason.

### 5.1 File inventory

| File | Rows | What it is | Role |
|---|---|---|---|
| `items.csv` | 48 | Item master. Cols: item_code, description, category, storage, pack_size, sell_uom, vendor_code, shelf_life_months, status, upc, default_bin, created_date | Core |
| `inventory_on_hand.csv` | 228 | Lot-level on hand, **two nights (2026-11-14: 115 rows, 2026-11-15: 113 rows)**, 5 locations. Cols: snapshot_date, item_code, description, location, lot_no, qty, uom, pack_date, expiry_date, received_date, unit_cost, vendor_lot_ref | Core: what she has |
| `sales_lines.csv` | 15,750 | Order lines, order dates 2025-10-29 to 2026-11-15, ship dates to 2026-12-15. Cols: order_no, line_no, order_date, ship_date, customer_code, customer_name, item_code, item_description, qty, uom, unit_price, ext_price, status (INVOICED / OPEN / CANCELLED), salesperson | Core: demand history + committed open orders |
| `purchase_orders.csv` | 377 | PO lines in every status. Cols: po_no, line_no, vendor_code, item_code, order_date, expected_date, qty_ordered, qty_received, uom, unit_cost, status (Received / Closed / Open / Cancelled), incoterms, container_no, buyer | Core: what's coming |
| `vendors.csv` | 8 | Vendors. Cols: vendor_code, vendor_name, country, lead_time_days, payment_terms, currency, contact_email, phone, address | Core, with overrides |
| `customers.csv` | 52 | Customers. Types: RESTAURANT 46, GROCERY 4 (G01 Seabright Markets, G02 Pilgrim Family Grocers, G03 Narragansett Fresh Foods, G04 Bayside Co-op), INTERNAL 1 (INT01 "TRANSFER - PVD"), CRUISE 1 (CRU01 Atlantic Star Cruise Lines) | Supporting: classify non-demand by customer type |
| `price_list.csv` | 79 | Price tiers STD / GROCERY / ALL, plus FUEL-SURCH rows (3 open-ended, uom EA) | Marco, phase 2. Load into raw + a clean table, no UI |

### 5.2 Trap list

| ID | Trap | Evidence in the data | Rule |
|---|---|---|---|
| T01 | Two nights in the on-hand file | Nov 14 (115 rows) and Nov 15 (113 rows), 113 lot keys repeat | Use only `max(snapshot_date)` = 2026-11-15. Log each older row as `excluded`. Summing both nights roughly doubles stock |
| T02 | Malformed item codes | `"shr-1620 "` (lowercase + trailing space), `"Sal-Por6"`, `"COD-LOIN "` (trailing space). In inventory: 1 row on Nov 15 (`shr-1620 `, **80 cs at PVD**). In sales: 72 rows. In POs: 5 rows (incl. the cancelled 500 cs `Sal-Por6`) | Canonical code = `strip().upper()`. Store each raw variant in `item_aliases`. Log every corrected row |
| T03 | Duplicate item master rows | The three variant rows above exist in `items.csv` alongside the canonical rows, all with created_date 2021-04-12 (looks like a botched migration), mostly missing UPC/bin | Collapse to one item per canonical code. Keep the row whose raw code already equals the canonical code. Log the dropped rows |
| T04 | Status is free text | Values: `Active`, `A`, `active`, blank, `Discontinued`, `DISC` | Normalize. **Blank does NOT mean discontinued** (LOB-MEAT and PAN-PORT4 are blank and actively selling). Only `DISC`/`Discontinued` mean discontinued |
| T05 | Legacy ZZ items | 6 items start with `ZZ-`. `ZZ-SCL-0002` is marked `Active`. 4 of them hold **59 cs at Harbor** (ZZ-SHR-0001 35, ZZ-SAL-0007 12, ZZ-SCL-0002 8, ZZ-LOB-0004 4), all long expired | Lifecycle `legacy` regardless of status. Never in the order list. Their stock appears in "stuck" as write-off |
| T06 | Quietly dead items | TIL-FIL last real sale 2026-04-16 (140 cs at Harbor, vendor OCN "old"). SHR-6170 last sale 2026-03-05 (60 cs at Harbor, status blank). PAN-1012 last sale 2026-02-10 (no stock, status `A`) | Lifecycle `dormant` when there is no real demand in the last `DORMANT_NO_SALES_DAYS` (60) days AND no open PO. Never suggest reordering. Stock appears in "stuck". **Pending Dana (email Q5)**. Dana can reactivate an item via `item_settings` |
| T07 | Fresh items | 6 `FR-` items, storage FRESH, vendor BBD, sold in LB. 2,856 fresh sales lines | Lifecycle `fresh_out_of_scope`. Excluded everywhere in planning (Dana: fresh is separate) |
| T08 | Category casing | `groundfish`, `SALMON`, `SHRIMP`, `shrimp` | Normalize with strip + title case |
| T09 | Pack size is free text | `6x2.2lb`, `5kg` (metric!), `10 lb cs`, `10#`, `10/2#`, `5x2#`, `5 x 2 lb`, `15 lb case`, `16.5 lb block`, `catch wt`, `per lb`, blank | Human-verified reference table `data/reference/pack_sizes.csv` with `lb_per_case` per item (values in §6.3). A regex parser exists only to validate the table and to flag new items. Unparseable → `data_issues` error |
| T10 | Mixed units in on-hand lots | Case items with lots in LB: CAL-RING NB lot L261005-02 = 132 lb; LOB-T56 NB lot L261027-01 = 220 lb, PVD lot L261103-01 = 160 lb. Unit cost on those lots is **per lb** (2.71, 23.66, 24.66) | Convert every lot to the item's `sell_uom` using `lb_per_case`. Convert unit cost too. Keep source qty/uom/cost alongside |
| T11 | Hold and damaged pseudo-locations | Nov 15 QA-HOLD: HAD-FIL 300 cs, SHR-1620 80 cs, CRAB-SNW8 40 cs (420 total). DAMAGED: CRAB-SNW5 2, POL-FIL 3, SAL-POR4 4, SCL-U10 6, SHR-2630 5 (20 total) | Not sellable. QA-HOLD shown separately as "on hold, may come back". DAMAGED shown as not counted |
| T12 | Zero-quantity split lots | 8 rows on Nov 15 with qty 0, mostly lots with a `B` suffix (e.g. `L260911-01B`) | Skip. Log as `info` |
| T13 | Negative adjustment lines | `ADJ-2211` COD-FIL −2 cs, `ADJ-7360` SHR-2630 −6 cs, `ADJ-1069` POL-BLK −40.5 lb. No pack/expiry/received dates, all at NB | Net against the item's sellable total (conservative). Log as `warning`. Assumption, not asked of Dana |
| T14 | Expired lots | SAL-POR8 L250303-01 60 cs at HCS (expired 2026-10-20). SHR-4150 L241202-01 18 cs at PVD (expired 2026-08-30). All ZZ lots expired 2023 to 2024 | Not sellable. Shown in "stuck" as write-off |
| T15 | The six-month line | AS_OF + 6 months = **2027-05-16**. Lots inside the line: SAL-POR6 all 3 lots (300 NB + 600 HCS + 450 HCS = **1,350 cs, 1,050 at Harbor, ≈ $81,233 at cost**), SAL-POR8 L260720-02 380 cs (HCS), TIL-FIL 140 cs (HCS). SAL-POR8 L260817-02 (320 cs, expiry 2027-05-30) is just outside | Lots still count as sellable for run-out (Dana discounts them), but are flagged "inside six-month line" in "stuck" |
| T16 | Transfers recorded as sales | Customer INT01 "TRANSFER - PVD" (type INTERNAL), 378 lines, ~5,444 units | Exclude from demand by **customer type INTERNAL**, not by name |
| T17 | Samples recorded as $0 orders | 104 INVOICED lines with unit_price 0, all 1 cs | Exclude from demand. Note in DECISIONS that samples do physically consume stock (~2 cs/week total), which is negligible |
| T18 | Credits recorded as negative sales | 76 lines, order_no starts with `CM-`, negative qty | Exclude from demand (count what customers ordered). Returned goods that go back on the shelf are already reflected in the snapshot |
| T19 | Cancelled sales | 294 CANCELLED lines | Exclude |
| T20 | Cruise line one-off | Order SO-245503, 2026-03-30, CRU01: SHR-1620 330 cs + SHR-2125 240 cs | Exclude by **order number** listed in `data/reference/excluded_orders.csv`, not by customer (if the cruise line returns, its new orders count) |
| T21 | Mixed date formats | 51 sales rows have order_date and ship_date in `MM/DD/YYYY` (e.g. `01/31/2026`), the rest ISO | Parse both. US format is unambiguous here (second component reaches 31). Log as `corrected` |
| T22 | Open sales orders are committed stock | 180 OPEN lines (159 real-demand frozen lines), order dates Nov 9–15, ship dates Nov 16–Dec 15. Includes grocery holiday pre-bookings, e.g. Seabright SO-251062 **120 cs SHR-1620 shipping Dec 14**, CRAB-SNW5 80 + 70 cs shipping Dec 8 and Dec 10 | Deduct each open line on its **ship date** in the projection (ship dates before AS_OF deduct on day 0). They also count as real demand in history (by order date) |
| T23 | Censored demand (stockout hides true demand) | SHR-1620 has **zero sales from 2025-12-11 to 2026-01-02** while every other shrimp rose in December. This is last year's stockout | Seed `data/reference/stockout_periods.csv` with this window. Exclude stockout days from all rate calculations. Use category-level seasonality so one censored item can't flatten its own December |
| T24 | Duplicate PO lines | PO-260439 line 1 (BXE SHR-2630, 500 cs, open) and PO-260445 line 1 (MNP HAD-LOIN, 200 cs, open) each appear twice, identical | Drop exact duplicate rows. Log. Incoming must be 500 and 200, not 1,000 and 400 |
| T25 | PO statuses and partial receipts | Status values Received (271), Closed (86), Open (16 rows, 14 unique), Cancelled (4, incl. PO-260423 `Sal-Por6` 500 cs). PO-260376 PAN-0709: 1,000 ordered, 600 received, still Open | Received and Closed = complete. Cancelled = ignore. Only Open lines are incoming, with **remaining = ordered − received** |
| T26 | Stale PO expected dates | BlueTide dates new Vietnam POs with the old 56-day lead time: PO-260443 SHR-1620 ordered 2026-11-02, "expected" 2026-12-28, real ≈ **2027-01-25**. Overdue open POs: PO-260394 SHR-2125 800 cs expected 2026-10-05, nothing received; PO-260376 PAN-0709 remaining 400 expected 2026-09-14; PO-260407 CAL-RING 300 cs expected 2026-10-19 | ETA rule in §6.6. Flag "BlueTide date has passed". Dana can override any ETA |
| T27 | Vendor lead time problems | BXE `56` (stale; Dana says 10–12 weeks). AFS blank (Dana: ~6 weeks). DLC `"2-3 wks"` (text). MNP 14 (matches Dana). ASP 28 (not discussed) | Keep the BlueTide value (`lead_time_days_system`, parsed) and Dana's value (`vendor_settings`) separately. Effective = Dana's value if present. Seeds in §6.5 |
| T28 | Vendor table oddities | AFS payment_terms = `CAD` (currency in the wrong column). HCS = Harbor Cold Storage (a storage provider, not a seafood vendor). OCN "Oceanic Trading Corp (old)" (legacy vendor for TIL-FIL and ZZ items). BBD = day boats (fresh) | Classify `vendor_type`: `stock_supplier` (BXE, AFS, MNP, ASP, DLC), `fresh_supplier` (BBD), `service_provider` (HCS), `legacy` (OCN). Log the AFS anomaly as `flagged` |
| T29 | Price list quirks | FUEL-SURCH rows (uom EA, three open-ended effective ranges), GROCERY tier | Out of scope (Marco). Load and log only |
| T30 | Received date is not age | SAL-POR6 lots were **packed Feb–Apr 2025 but received Jul–Aug 2026**, so Dana bought already-old stock. `shelf_life_months` is blank on several items | Always use the lot's `expiry_date` for age and the six-month line. Never `received_date` or `shelf_life_months` |
| T31 | Lots disappear between nights | POL-FIL and SCL-U10 lot L260601-09 (3 cs each) exist Nov 14, gone Nov 15 | Absence in the latest snapshot means sold out, not missing data. Informational, documented in DATA_AUDIT |

### 5.3 Golden facts (assert these in `backend/tests/golden/test_real_data.py`)

These were computed directly from the raw files in the planning chat. If your loader disagrees, your loader is probably wrong. Investigate before changing a test, and if a fact itself turns out to be wrong, explain why in PROMPT_LOG.

- **G01** Latest snapshot = 2026-11-15. The 115 rows dated 2026-11-14 are excluded.
- **G02** 45 canonical items after collapsing 3 alias rows (`"COD-LOIN "`, `"Sal-Por6"`, `"shr-1620 "`).
- **G03** Lifecycle counts: active 30, dormant 3 (TIL-FIL, SHR-6170, PAN-1012), legacy 6 (all ZZ-), fresh_out_of_scope 6. Precedence: fresh > legacy > discontinued > dormant > active (so discontinued = 0, since the only DISC/Discontinued items are ZZ).
- **G04** Sellable SHR-1620 = **480 cs** (NB 260 + HCS 140 + PVD 80 from alias `shr-1620 `). On hold 80.
- **G05** Sellable LOB-T56 = **83 cs** (45 cs + 220 lb ÷ 10 + 160 lb ÷ 10).
- **G06** Sellable CAL-RING = **353 cs** (263 + 132 lb ÷ 13.2 + 80).
- **G07** ADJ netting: COD-FIL = 206 cs, SHR-2630 = 429 cs, POL-BLK = 8,478.5 lb.
- **G08** HAD-FIL sellable 170 cs, on hold 300 cs.
- **G09** Expired non-legacy lots: exactly SAL-POR8 L250303-01 (60 cs) and SHR-4150 L241202-01 (18 cs). SAL-POR8 sellable = 700. SHR-4150 sellable = 381.
- **G10** Non-expired lots of non-legacy items with expiry < 2027-05-16: exactly SAL-POR6 ×3 (1,350 cs), SAL-POR8 L260720-02 (380 cs), TIL-FIL L250602-01 (140 cs).
- **G11** Sales demand_class counts (classification order in §6.2): real_demand 12,040; fresh_out_of_scope 2,856; transfer 378; cancelled 294; sample 104; credit 76; one_off 2.
- **G12** 51 sales rows parsed from MM/DD/YYYY.
- **G13** Committed (OPEN, real demand): SHR-1620 = 201 cs, CRAB-SNW5 = 221 cs, SHR-2125 = 91 cs. 159 open real-demand lines in total.
- **G14** POs: 2 exact duplicate rows removed. 14 open lines. Incoming SHR-2630 = 500, HAD-LOIN = 200, PAN-0709 = 400, POL-BLK = 18,000 lb. PO-260423 (cancelled) contributes 0.
- **G15** ETAs: PO-260443 SHR-1620 = 2027-01-25 (BlueTide 2026-12-28). PO-260394 SHR-2125 and PO-260376 PAN-0709 are late and assumed 2026-11-23. PO-260436 PAN-0507 = 2026-12-28 (BlueTide 2026-11-30). PO-260444 LOB-T810 = 2026-11-27 (BlueTide 2026-11-23).
- **G16** Effective lead times: BXE 84, AFS 42, MNP 14, ASP 28, DLC 21. System values: BXE 56, AFS null, DLC 21 (parsed from "2-3 wks", upper bound), MNP 14, ASP 28.
- **G17** No legacy, dormant or fresh item ever appears in the order list.

---

## 6. Business rules (the definitive spec)

All tunable numbers live in **one file**, `backend/app/config/business_rules.py`, as a frozen dataclass with a docstring per field that explains the value, its source (transcript timestamp, email question, or assumption) and how to change it. Defaults:

```python
AS_OF_DATE = date(2026, 11, 16)        # env AS_OF_DATE overrides. README: treat Nov 16 as today
SIX_MONTH_LINE_MONTHS = 6              # Dana 03:30: nobody takes it with < 6 months left
DORMANT_NO_SALES_DAYS = 60             # T06. Pending Dana (email Q5)
BASE_WINDOW_DAYS = 56                  # recent demand level = last 8 weeks
SEASONAL_WINDOW_DAYS = 365             # one year of history for seasonality
SEASONAL_INDEX_MIN, SEASONAL_INDEX_MAX = 0.4, 2.5   # clamp to avoid absurd multipliers
PROJECTION_HORIZON_DAYS = 182          # 26 weeks. Beyond this we say "more than 6 months"
COVER_FORECAST_DAYS = 91               # weeks-of-cover uses the next 13 weeks of forecast
ORDER_THIS_WEEK_DAYS = 7               # status thresholds, see 6.8
ORDER_SOON_DAYS = 21
OVERDUE_PO_ASSUMED_DAYS = 7            # email Q3 default: late POs arrive within a week
DEFAULT_LEAD_TIME_DAYS = 28            # fallback only, logs a warning
DEFAULT_SAFETY_DAYS = 7
DEFAULT_ORDER_CYCLE_DAYS = 7           # Dana orders every Monday
OVERSTOCK_WEEKS = 26                   # stuck: more than 6 months of supply
HARBOR_LONG_WEEKS = 12                 # stuck: at Harbor with more than 12 weeks of supply
SELLABLE_LOCATIONS = from locations table (is_sellable = true)
```

### 6.1 Sellable stock (per item, in the item's sell_uom)
Sum of lots in the **latest snapshot** where the location is sellable (NB, PVD, HCS), qty > 0, expiry_date ≥ AS_OF (or no expiry for ADJ rows), and the item's lifecycle is `active`. **Plus** negative ADJ rows (T13). Converted per T10. Also compute and expose separately (never added in): `on_hold_qty` (QA-HOLD), `damaged_qty`, `expired_qty`.

### 6.2 Sales classification (`demand_class`), applied in this order
1. status CANCELLED → `cancelled`
2. customer_type INTERNAL → `transfer`
3. order_no starts with `CM-` or qty < 0 → `credit`
4. unit_price = 0 → `sample`
5. order_no in `excluded_orders` → `one_off`
6. item lifecycle `fresh_out_of_scope` → `fresh_out_of_scope`
7. otherwise (INVOICED or OPEN) → `real_demand`

**Real demand** = `real_demand` lines with status INVOICED or OPEN, **dated by order_date** (demand happens when the customer orders, see ADR-013). **Committed** = `real_demand` lines with status OPEN, deducted on ship_date.

### 6.3 Units and pack sizes
Plan every item in its own `sell_uom` (CS or LB). Seed `data/reference/pack_sizes.csv` (columns: item_code, pack_size_raw, lb_per_case, verified_by, note) with these human-checked values:

| Item | pack_size_raw | lb_per_case | Item | pack_size_raw | lb_per_case |
|---|---|---|---|---|---|
| CAL-RING | 6x2.2lb | 13.2 | PAN-PORT4 | 4x2.5lb | 10 |
| COD-FIL | 5kg | 11.0231 | POL-BLK | 16.5 lb block | n/a (LB item) |
| COD-LOIN | 10 lb cs | 10 | POL-BRD | 4x3lb | 12 |
| CRAB-MEAT | 6x1lb | 6 | POL-FIL | 10 lb | 10 |
| CRAB-SNW5 | 30 lb cs | 30 | SAL-CHO6 | 10lb | 10 |
| CRAB-SNW8 | 30lb | 30 | SAL-POR4 | 4x2.5lb | 10 |
| HAD-FIL | 10# | 10 | SAL-POR6 | 10 lb cs | 10 |
| HAD-LOIN | 10 lb | 10 | SAL-POR8 | 10 LB CS | 10 |
| LOB-MEAT | 6x2lb | 12 | SAL-SIDE | catch wt | n/a (LB item) |
| LOB-T56 | 10 lb cs | 10 | SAL-SIDE-SK | catch wt | n/a (LB item) |
| LOB-T810 | 10lb cs | 10 | SCL-U10 | 5 lb cs | 5 |
| PAN-0507 | 15lb | 15 | SHR-1215 | 5x2lb | 10 |
| PAN-0709 | 15 lb case | 15 | SHR-1620 | 10x2lb | 20 |
| PAN-1012 | 15lb | 15 | SHR-2125 | 10x2lb | 20 |
| SHR-2630 | 20 lb cs | 20 | SHR-3140C | 5x2# | 10 |
| SHR-4150 | 5 x 2 lb | 10 | SHR-6170 | 5x2lb | 10 |
| TIL-FIL | 15 lb cs | 15 | FR-*, ZZ-* | per lb / blank | n/a |

Conversion: LB lot of a CS item → qty ÷ lb_per_case, cost × lb_per_case. CS lot of an LB item → qty × lb_per_case (not present in data, but handle it generically). Missing factor where one is needed → exclude the lot, log `error`.

### 6.4 Item lifecycle (computed, overridable)
Precedence: `fresh_out_of_scope` (storage FRESH or code `FR-`) > `legacy` (code `ZZ-`) > `discontinued` (status DISC/Discontinued) > `dormant` (T06) > `active`. Store `lifecycle_status` and a human-readable `lifecycle_reason`. `item_settings.lifecycle_override` wins if set (audited).

### 6.5 Vendor lead times and cushion (seed `data/reference/vendor_settings_seed.csv`)

| Vendor | Country | BlueTide lead time | Effective lead time | Cushion (safety) | Source |
|---|---|---|---|---|---|
| BXE Bien Xanh | Vietnam | 56 | **84** | **14** | Call 02:25 (10–12 wks, using 12, email Q1) and 08:30 (2 wks on imports) |
| AFS Austral Frío | Chile | blank | **42** | **14** | Call 02:25 (~6 wks), import cushion |
| MNP Maritime Northern | Canada | 14 | **14** | **7** | Call 02:25. Cushion "less" than imports, 7 assumed (email Q2) |
| ASP Aleutian Shore | USA (AK) | 28 | **28** | **7** | BlueTide, unconfirmed (email Q1, Q2) |
| DLC Downeast Lobster | USA (ME) | "2-3 wks" | **21** | **7** | BlueTide text, upper bound (email Q1, Q2) |

Each vendor also gets `order_cycle_days = 7` (weekly Monday ordering). Seeds are inserted only if no row exists, so **re-running the loader never overwrites Dana's edits**.

### 6.6 Incoming supply (open POs and "handled" notes)
For each open PO line (deduped, remaining > 0, converted to sell_uom):
```
candidate = max(expected_date_system, order_date + effective_lead_time(vendor))
if Dana set an ETA override:      eta = override,                        source = "Set by Dana"
elif candidate < AS_OF:           eta = AS_OF + OVERDUE_PO_ASSUMED_DAYS, flag = "late, confirm with vendor"
else:                             eta = candidate
flag "BlueTide date has passed" whenever expected_date_system < AS_OF
flag "BlueTide date is earlier than the real lead time allows" whenever candidate > expected_date_system
```
A **handled note** with both qty and ETA adds a synthetic incoming line labelled "Your note: ordered by phone". A handled note without them only changes how the item is displayed (§6.10).

### 6.7 Demand forecast (explainable seasonal model)
This deliberately mirrors how Dana thinks ("October is slow, December won't be, I adjust in my head"): **current selling rate × seasonal multiplier**.
```
SEASON window = [AS_OF − 365 d, AS_OF − 1 d] = 2025-11-16 .. 2026-11-15
For each ACTIVE item i and month m in the window:
    days[i,m] = days of month m inside the window, minus item i's stockout days
    rate[i,m] = real_demand_qty(i, m) / days[i,m]        (skip if days = 0)
For each category c (normalized) and month m:
    cat_rate[c,m] = Σ over active items in c of rate[i,m]   (an item missing a month uses its own annual average)
    index[c,m]    = clamp(cat_rate[c,m] / mean_over_12_months(cat_rate[c,·]), MIN, MAX)
BASE window = [AS_OF − 56 d, AS_OF − 1 d] = 2026-09-21 .. 2026-11-15
base_rate[i]  = real_demand_qty(i, BASE) / (56 − stockout days in BASE)
base_index[i] = day-weighted mean of index[c, month(d)] over BASE
level[i]      = base_rate[i] / base_index[i]               # "normal-season" daily rate
forecast[i,d] = level[i] × index[c, month(d)]
```
Use only active items when building indices, so dead items like SHR-6170 don't distort the Shrimp curve. Expose for the drill-down: base_rate per week, the index for each upcoming month, and last year's monthly totals.

### 6.8 Run-out projection and status
Daily simulation from day 0 = AS_OF to PROJECTION_HORIZON_DAYS:
```
stock = sellable
each day d: stock += arrivals with eta == d
            stock −= committed lines with ship_date == d   (ship_date < AS_OF counts on day 0)
            stock −= forecast[i, d]
run_out_date = first d where stock < 0   (None if beyond horizon → "more than 6 months")
L = effective lead time, S = cushion days
new_order_arrival = AS_OF + L
order_by_date = run_out_date − L − S
Status:
  TOO_LATE         if run_out_date < AS_OF + L      ("will run out before a new order can arrive")
  ORDER_THIS_WEEK  elif order_by_date ≤ AS_OF + ORDER_THIS_WEEK_DAYS
  ORDER_SOON       elif order_by_date ≤ AS_OF + ORDER_SOON_DAYS
  OK               otherwise
  (items with no recent demand but active → NO_RECENT_SALES, not in the order list)
```
Extra outputs:
- `gap_qty` for TOO_LATE items is the demand that cannot be covered between run-out and the new order's arrival (lost-sales estimate). Show it as "You'll be short about N cs between {run_out} and {arrival}. Ask the vendor to expedite or find another source."
- `depends_on_late_po` is set when a late or overdue PO's ETA is within 14 days of the run-out date. Show it as "This depends on PO-xxxx (BlueTide said {date}, still open)."
- `weeks_of_cover` = sellable ÷ (mean forecast over the next COVER_FORECAST_DAYS × 7).

### 6.9 Suggested order quantity ("order at least")
Run a second simulation where stock is **floored at 0 before the new order arrives** (sales lost during a stockout are not backfilled), then from the arrival day keep it unfloored:
```
window = [AS_OF + L, AS_OF + L + order_cycle_days + S]
order_at_least = ceil(max(0, −min(stock over window)))
```
Plain English: "A new order placed today lands about {arrival}. To get you to the next Monday order's arrival plus {S/7} weeks of cushion, order at least {Q} {uom}." Label it **"Order at least"**, because Dana makes the final call and container or minimum-order rounding is P1.

### 6.10 "I've handled this"
- Dana can mark any item handled, with an optional qty, optional expected arrival date, and an optional note.
- If qty and ETA are given, they count as incoming (§6.6), so the status may recompute to OK.
- Handled items move to a "Handled" section on the dashboard. They are never hidden, and they show the note and its age ("Handled by Dana, Nov 16. 600 cs due about Feb 8").
- Notes stay until cleared. When a reload brings in a new open PO for that item with order_date ≥ the note's date, show "BlueTide now shows PO-xxx. Clear your note?" Never auto-delete.
- Every create and clear is audited.

### 6.11 Stuck with (lot level, rolled up per item for the dashboard)
Tags per lot, with precedence for the primary tag:
1. `EXPIRED`: expiry < AS_OF, i.e. write off.
2. `STOPPED_SELLING`: item lifecycle legacy, discontinued or dormant, with qty > 0.
3. `INSIDE_SIX_MONTHS`: expiry < AS_OF + 6 months, i.e. discount or move it now.
4. `LONG_AT_HARBOR`: location HCS and item weeks_of_cover > HARBOR_LONG_WEEKS, i.e. paying storage on stock that won't be needed for months.
5. `OVERSTOCK`: item weeks_of_cover > OVERSTOCK_WEEKS.

Also add an "At Harbor (paying storage)" badge on any stuck lot at HCS, and sort those first within each group (Walt: worst case). Value each lot at cost = qty × unit_cost_sell_uom. Sort groups in the order above and by $ within a group.

**Important nuance (demo point):** SHR-1620's 140 cs at Harbor are **not** stuck. They are needed for Christmas. Being at Harbor alone is not a stuck reason. Weeks of cover decides it.

---

## 7. Answer key (sanity check, not a target)

From the rough pandas model in the planning chat. It used slightly different details (it included dormant items in the seasonal indices and had a simpler overdue-PO rule), so **expect differences of a few days**. Statuses of the top items should match. If they don't, explain why in PROMPT_LOG before changing anything.

**Will run out before a new order can arrive (TOO_LATE):**
- **SHR-2125**, about Nov 21. On-hand barely covers 91 cs of open orders. Everything hinges on the late 800 cs (PO-260394). Should show `depends_on_late_po`.
- **LOB-T56**, about Nov 25. Only correct if the pound lots are converted (83 cs).
- **SHR-1620**, about Dec 14. 480 sellable, 201 promised (incl. 120 cs for Seabright on Dec 14). The 600 cs PO really lands about Jan 25. **This is the demo opener.**
- **PAN-0507**, about Dec 27. Looks fine with BlueTide's Nov 30 date. With the real lead time the PO lands about Dec 28.

**Order this week:** CRAB-SNW5 (about Nov 30), LOB-MEAT (about Dec 7), HAD-FIL (about Dec 9, with 300 cs on QA hold just before Lent), POL-FIL (about Dec 26), SAL-SIDE-SK (about Jan 5).

**Stuck with:**
- **SAL-POR6:** 1,350 cs, all inside the six-month line, 1,050 at Harbor, ≈ $81K at cost. At about 37 cs/week, roughly 600 cs (≈ $37K) are likely to expire unsold. That last number needs P1 lot-level projection.
- **SAL-POR8:** 60 cs expired plus 380 cs inside the line at Harbor.
- **SHR-4150:** 18 cs expired at PVD.
- **TIL-FIL:** 140 cs at Harbor, stopped selling and inside the line.
- **SHR-6170:** 60 cs at Harbor, stopped selling.
- **ZZ items:** 59 cs at Harbor, write off.
- **Not stuck:** SHR-1620 at Harbor (140 cs).

**Data trust strip totals:** not counted are 420 cs on hold, 20 cs damaged, 78 cs expired (non-legacy), and 59 cs of old ZZ stock.

---

## 8. Architecture

### 8.1 Stack (fixed by Ishan) and hosting

| Layer | Choice | Why | Tradeoff |
|---|---|---|---|
| Database | **Supabase** (managed Postgres) | Ishan's choice. Real Postgres (JSONB, constraints, migrations), free tier, dashboard for inspecting data during the review | Free projects **pause after about a week of inactivity**. Mitigated by the keep-warm ping (§15) |
| Backend | **Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, psycopg 3** | Ishan's strongest language. FastAPI gives typed request/response models and auto-generated OpenAPI docs at `/docs`, which is useful in the decisions review. pandas is used only in the one-time loader | Two deployables (API + web) instead of one |
| Frontend | **React 18 + Vite + TypeScript, React Router, TanStack Query, Tailwind CSS, Recharts, date-fns** | Ishan's React. Vite is fast and simple. TanStack Query handles loading, error and refetch states cleanly. Tailwind keeps styling in the component for fast live changes | **Confirm TypeScript vs plain JavaScript with Ishan in Phase 0.** TS catches API-shape bugs, but adds friction if he is less fluent |
| API hosting | **Render free web service** (long-running uvicorn) | Simple, a standard long-running process (no serverless connection-pool problems with Postgres), stdout logs visible in the dashboard | Free instances **sleep after ~15 minutes idle** and take up to about a minute to wake. Mitigated by the keep-warm ping and a friendly "waking up" state in the UI |
| Web hosting | **Vercel** (static Vite build) | Free, fast CDN, preview deploys per branch | Needs CORS and an SPA rewrite |
| Alternative considered | Everything on Vercel (Python serverless functions) | One deploy, no CORS | Serverless + Postgres needs transaction pooling, bundle-size limits, and harder logging. Rejected for v1 |

### 8.2 Repository layout

```
.
├── BUILD_PROMPT.md                 # this file
├── CLAUDE.md                       # short persistent context for Claude Code (§13.1)
├── README.md                       # submission README (§13.5)
├── docs/
│   ├── PROMPT_LOG.md               # every prompt, what changed, impact (§13.2)
│   ├── DECISIONS.md                # ADRs with tradeoffs (§13.3)
│   ├── ASSUMPTIONS.md              # assumptions, source, status (§13.4)
│   ├── DATA_AUDIT.md               # §5, human-readable, with test names
│   ├── DATA_LOAD_REPORT.md         # generated by the loader (row counts, issues by rule)
│   ├── DEMO_SCRIPT.md              # 10-minute demo for "Dana" (§13.6)
│   └── client/                     # assignment, transcript, email, Dana's replies
├── data/
│   ├── raw/                        # 7 CSVs, untouched
│   └── reference/                  # human-maintained seeds: Dana's knowledge and our decisions
│       ├── pack_sizes.csv
│       ├── vendor_settings_seed.csv
│       ├── locations.csv
│       ├── stockout_periods.csv
│       └── excluded_orders.csv
├── backend/
│   ├── requirements.txt, requirements-dev.txt, .env.example, alembic.ini
│   ├── migrations/                 # Alembic
│   ├── app/
│   │   ├── main.py                 # app factory, middleware, routers, exception handlers
│   │   ├── config/settings.py      # env (pydantic-settings): DATABASE_URL, AS_OF_DATE, CORS_ORIGINS, LOG_LEVEL...
│   │   ├── config/business_rules.py# ALL tunable business numbers (§6)
│   │   ├── logging_setup.py        # JSON logging, request-id contextvar
│   │   ├── middleware.py           # request id, timing, request log
│   │   ├── db/session.py, db/models.py
│   │   ├── loader/                 # one-time CSV load (pure functions + thin DB writer)
│   │   │   ├── read_raw.py, rules.py (T01..T31 as named functions), normalize.py,
│   │   │   ├── classify.py, convert.py, write.py, report.py, run.py (CLI)
│   │   ├── planning/               # PURE engine, no DB, no I/O
│   │   │   ├── types.py, seasonality.py, demand.py, supply.py,
│   │   │   ├── projection.py, ordering.py, stuck.py, explain.py
│   │   ├── services/               # DB → engine inputs → DTOs, audit + event writers
│   │   └── api/v1/                 # routers + Pydantic schemas
│   └── tests/ unit/ golden/ api/
├── frontend/
│   ├── vercel.json                 # SPA rewrite
│   └── src/ api/ pages/ components/ lib/ styles/
└── scripts/
    ├── profile_data.py             # reproduces the audit facts from raw CSVs
    └── compare_answer_key.py       # prints engine output next to §7
```

### 8.3 Data model (Postgres on Supabase)

Three layers. Every clean row points back to its raw row, so any number on screen can be traced to a line in a BlueTide file.

**Raw layer (traceability):**
- `raw_rows(id, load_run_id, source_file, source_line_number, data JSONB, row_hash)` holds every CSV row exactly as exported (strings, untrimmed). A single JSONB table means new export files need no migration (ADR-003).

**Clean layer (BlueTide data after the rules in §5 and §6). Rebuilt on every load:**
- `vendors(vendor_code PK, name, country, vendor_type, lead_time_raw, lead_time_days_system NULL, payment_terms, currency, raw_row_id)`
- `items(item_code PK, description, category, storage, pack_size_raw, lb_per_case NULL, sell_uom, vendor_code FK, shelf_life_months NULL, status_raw, lifecycle_status, lifecycle_reason, upc, created_date, raw_row_id)`
- `item_aliases(alias_code PK, item_code FK, reason)`
- `customers(customer_code PK, name, customer_type, salesperson, city, state, raw_row_id)`
- `locations(code PK, name, is_sellable, is_third_party_storage, may_return_to_stock, description)` seeded from `data/reference/locations.csv`: NB, PVD, HCS (sellable; HCS third-party), QA-HOLD (not sellable, may return), DAMAGED (not sellable)
- `inventory_lots(id, snapshot_date, item_code FK, location_code FK, lot_no, is_adjustment, qty_source, uom_source, qty_sell_uom, pack_date, expiry_date, received_date, unit_cost_source, unit_cost_sell_uom, vendor_lot_ref, raw_row_id)`, latest snapshot only
- `sales_lines(id, order_no, line_no, order_date, ship_date, customer_code FK, item_code FK, qty, uom, unit_price, ext_price, status, salesperson, demand_class, raw_row_id, UNIQUE(order_no, line_no))`
- `purchase_order_lines(id, po_no, line_no, vendor_code FK, item_code FK, order_date, expected_date_system, qty_ordered, qty_received, qty_remaining_sell_uom, uom, unit_cost, status_raw, status, container_no, raw_row_id, UNIQUE(po_no, line_no))`
- `prices(item_code, tier, price, uom, effective_from, effective_to)`, loaded for phase 2, unused
- `stockout_periods(id, item_code, start_date, end_date, source, note)` from seed
- `excluded_orders(order_no PK, reason, source)` from seed

**App layer (what Dana tells the tool). The loader NEVER truncates these:**
- `vendor_settings(vendor_code PK, lead_time_days, safety_days, order_cycle_days, source, note, updated_at, updated_by)`, seeded only if missing
- `item_settings(item_code PK, lifecycle_override NULL, safety_days_override NULL, note, updated_at, updated_by)`
- `po_eta_overrides(po_no, line_no, eta, note, updated_at, updated_by, PK(po_no, line_no))`
- `handled_flags(id, item_code, qty NULL, eta NULL, note, created_at, created_by, cleared_at NULL, cleared_by NULL, clear_reason NULL)`

**Logging layer (§10):**
- `load_runs(id, started_at, finished_at, status, as_of_date, files JSONB [{name, sha256, rows}], summary JSONB, git_sha)`
- `data_issues(id, load_run_id, source_file, source_line_number, raw_row_id, trap_id, rule_code, severity [info|warning|error], action [excluded|corrected|flagged], item_code NULL, field NULL, original_value, new_value, message)`
- `audit_log(id, occurred_at, actor, action, entity_type, entity_id, before JSONB, after JSONB, request_id)`
- `event_log(id, occurred_at, level, source [api|loader|web], event, request_id NULL, details JSONB)`
- `request_log(id, occurred_at, request_id, method, path, status, duration_ms, actor)`

**Supabase specifics:** enable Row Level Security on every table with **no policies**. This blocks Supabase's auto-generated Data API, while the backend connects with the database connection string (postgres role) and bypasses RLS. All access goes through FastAPI (ADR-015). Use numeric columns for quantities and money, `date` for business dates, and `timestamptz` (UTC) for log times.

### 8.4 Engine design
- `planning/` is **pure**: it takes dataclasses and returns dataclasses, with no DB, no clock and no I/O. That makes it unit-testable with tiny fixtures, reusable by a future nightly job, and easy to change live.
- `services/planning_service.py` loads everything in a handful of queries, builds engine inputs, runs the engine for all items, and maps the results to API DTOs.
- Compute **on request**. With about 30 items × 182 days, it runs in milliseconds. Log the duration. Add an in-memory cache keyed by (latest load_run_id, overrides version) only if a request exceeds 500 ms (ADR-004).
- `explain.py` produces the plain-English "why" steps from the same numbers the engine used, so the explanation can never disagree with the result.
- Design the projection so a lot-aware FEFO variant (P1) can plug in later without changing the API shape.

### 8.5 API (FastAPI, prefix `/api/v1`, JSON, OpenAPI at `/docs`)

| Method & path | Purpose |
|---|---|
| `GET /health` | `{status, db, as_of, last_load_at}`. Also used by the keep-warm ping |
| `GET /dashboard` | Summary sentence data, `order_items[]` (TOO_LATE, ORDER_THIS_WEEK, ORDER_SOON), `handled_items[]`, `fine_items[]`, `stuck_items[]` (item-level rollups with lot tags), `trust_strip` (on hold, damaged, expired, legacy totals), `as_of`, `data_snapshot_date` |
| `GET /items` | All items with lifecycle, status, run-out, cover (the "show everything" view) |
| `GET /items/{item_code}` | Full drill-down: item, vendor and lead time (system vs effective), sellable lots and excluded lots with reasons, committed lines, incoming lines (BlueTide date, our ETA, flags), demand history by month (last year), current weekly rate, seasonal index for coming months, daily or weekly projection series, run-out, order-by, order-at-least, gap_qty, explanation steps, active handled note, stuck tags. Code lookup is case- and space-insensitive (aliases resolve) |
| `GET /vendors` / `PATCH /vendors/{code}` | Lead time, cushion, order cycle (validated 1–365 days). Audited |
| `PATCH /purchase-orders/{po_no}/lines/{line_no}` | `{eta, note}`, where null clears the override. Audited |
| `POST /items/{code}/handled` / `DELETE /handled/{id}` | Create or clear a handled note (`{qty?, eta?, note?}` / `{reason?}`). Audited |
| `PATCH /items/{code}/settings` | Lifecycle override (e.g. "still active"), cushion override. Audited |
| `GET /data-issues/summary`, `GET /data-issues?trap_id=&file=&item=` | Data notes page |
| `GET /audit-log`, `GET /events`, `GET /load-runs` | Activity page |
| `GET /settings` | Current business rules and their sources (read-only in v1) |
| `POST /client-events` | Frontend errors and notable UI events → `event_log` (source `web`) |

**Conventions:**
- The actor comes from header `X-Actor` (default "Dana"). The UI asks "Who's using this?" once and stores the answer in localStorage. There is no auth in v1 (ADR-011).
- Every response carries `X-Request-ID`.
- Errors use the envelope `{error: {code, message, request_id}}` with plain-English messages.
- CORS is limited to `CORS_ORIGINS`.

---

## 9. UI v1 (proposal; Ishan will iterate)

**Audience and job:** Dana, VP Purchasing, non-technical and skeptical, on a laptop on Monday morning (sometimes her phone). The screen must make sense **within one minute without training**, and every number must be clickable down to its source.

### 9.1 Design tokens (grounded in the subject: cold storage, New Bedford harbor, maritime signal flags)
- **Colors:** Ice `#F2F5F6` page background (cool cold-storage grey, deliberately not cream), Hull `#FFFFFF` surfaces, Harbor ink `#13293D` primary text, Fog `#5E6E7A` secondary text, Rope `#D6DEE3` rules and borders.
- **Order statuses** (text on tint, drawn from signal-flag colors, always paired with an icon and words, never color alone):

  | Status | Text | Tint |
  |---|---|---|
  | Too late | `#B3261E` | `#FBE9E7` |
  | Order this week | `#8A5A00` | `#FFF1CC` |
  | Order soon | `#1F5F99` | `#E6F0FA` |
  | Fine | `#2E6B4E` | `#E7F3EC` |
  | Handled | `#55626C` | `#EDF0F2` |

- **Stuck tags** (text on tint):

  | Tag | Text | Tint |
  |---|---|---|
  | Expired | `#7F1D1D` | `#F9E3E3` |
  | Stopped selling | `#4A5560` | `#ECEFF1` |
  | Inside six-month line | `#9A3412` | `#FDEBDD` |
  | Long at Harbor | `#1E4E7A` | `#E3EDF6` |
  | Overstock | `#6B5B1E` | `#F4EFD9` |

- **Type:** one family, **Atkinson Hyperlegible Next** (Google Fonts; if unavailable use the original Atkinson Hyperlegible), fallback `system-ui, sans-serif`. It was designed for maximum legibility, and every digit must be unambiguous for a skeptical reader. Use `font-variant-numeric: tabular-nums` for quantities. Item names lead, codes follow in smaller Fog text. Sentence case everywhere. No all-caps labels, no eyebrow labels, no `A · B · C` meta strings, no arrows appended to buttons.
- **The one bold element: the runway bar.** Each order row has a horizontal bar. The filled length is how long current stock lasts. A marker shows when a new order placed today would land (lead time), and a hatched zone shows the cushion. If the bar ends before the marker, the row is "Too late". It is Dana's first question drawn as a picture. The item detail page shows the full projection chart in the same visual language: a stock line over 26 weeks, arrival markers, the lead-time marker, the run-out point, and Christmas and Lent 2027 shaded. Everything else stays quiet.
- **Motion:** none except responses to actions (expand, save confirmation). Respect `prefers-reduced-motion`. Visible keyboard focus. WCAG AA contrast.

### 9.2 Monday screen (web-first, ≥1280 px; stacks to one column on phones, order list first)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ Kestrel Bay ordering           Monday, November 16, 2026    Lead times  Data notes  Activity │
├─────────────────────────────────────────────────────────────────────────────────────┤
│ 4 items will run out before a new order can arrive. 5 more need an order this week.         │
│ $X of stock is inside the six-month line, $Y of it at Harbor.                                │
│ Not counted: 420 cs on hold, 20 cs damaged, 78 cs expired, 59 cs of old ZZ stock.  What we cleaned up │
├──────────────────────────────────────────────────────┬──────────────────────────────┤
│ What to order                                         │ What you're stuck with        │
│ White shrimp 16/20 EZ peel            SHR-1620        │ Atlantic salmon portion 6 oz  │
│ Too late. Runs out about Mon Dec 14 (4 weeks)         │ Inside six-month line         │
│ [██████████████░░░░░░░░░░░░▲░░░░░]                    │ 1,350 cs, 1,050 at Harbor     │
│  stock lasts 4 wks            ▲ new order lands Feb 8 │ $81,233 at cost               │
│ Order at least 260 cs. Bien Xanh, Vietnam, 12 weeks    │ ...                           │
│ [Mark as handled]                                      │                              │
│ ...                                                   │                              │
│ Handled (1)                                     ▸     │                              │
│ Everything else looks fine (21 items)           ▸     │                              │
└──────────────────────────────────────────────────────┴──────────────────────────────┘
```
(Numbers in the wireframe are illustrative. Render whatever the engine returns.)

### 9.3 Item detail
1. **Header:** name, code, vendor, status, "Mark as handled".
2. **"Why" panel** as numbered steps (a real sequence, so numbering is appropriate):
   1. what you can sell (link to lots),
   2. what's promised to customers,
   3. what's on the way (with dates, and BlueTide's date crossed out where we corrected it),
   4. how fast it's selling now and what the season does next ("December usually sells 1.3× a normal month"),
   5. so it runs out about {date},
   6. a new order placed today lands about {date},
   7. order at least {Q}.
3. **Projection chart** (the runway, enlarged).
4. **Tables:** lots by location, including the ones we didn't count and why (on hold, damaged, expired); open customer orders; open POs with an editable arrival date ("Set real date"); last 12 months of sales by month.
5. **Plain-language glossary on hover:**
   - "Time to arrive" means placing the order to having it in our building.
   - "Cushion" means extra stock for when ships slip.
   - "Promised to customers" means open orders not yet shipped.

### 9.4 Other pages
- **Lead times:** vendor, country, "BlueTide says", "You say" (editable), cushion weeks (editable), last changed by and when.
- **Data notes ("What we cleaned up and why"):** grouped by trap in plain English with counts, expandable to the original file and line number.
- **Activity:** audit log (who changed what, before and after), load runs, recent events and errors.
- **States:**
  - Loading.
  - Empty.
  - Error: plain message plus a reference id.
  - Cold start: "Waking up the server. Free hosting sleeps when idle, about 30 seconds." Show this after 3 s with no response.

### 9.5 Copy rules
Use Dana's words: "on hold", "stuck with", "six-month line", "Harbor", "runs out", "order at least", "promised to customers". Never say SKU, UOM, safety stock, lead time (without the hover), or committed. Always show units (cs or lb). Dates like "Mon Dec 14" plus a relative phrase ("in 4 weeks"). Buttons say exactly what happens ("Save arrival date", then the toast says "Arrival date saved").

---

## 10. Logging everything (P0, four layers)

1. **Application logs.**
   - JSON lines to stdout via stdlib `logging` + `python-json-logger`.
   - Every request gets `request_id`, method, path, status, duration_ms and actor.
   - Every dashboard or item computation logs item count, duration, counts by status, and a settings hash.
   - Warnings and errors include a stack trace.
   - Requests are also written to `request_log` (background task, so it never slows the response). Notable events go to `event_log`.
2. **Data load log.**
   - Every load creates a `load_runs` row with file checksums and row counts.
   - Every row excluded, corrected or flagged creates a `data_issues` row with `trap_id`, the original and new values, and a plain-English message.
   - The loader also writes `docs/DATA_LOAD_REPORT.md` (a reconciliation per file: rows read, kept, excluded and corrected by rule).
3. **Audit trail.** Every write endpoint records an `audit_log` row (actor, action, entity, before/after JSON, request_id) in the **same DB transaction** as the change.
4. **AI usage log.** `docs/PROMPT_LOG.md` (§13.2).

The frontend sends unexpected errors to `POST /client-events`. The Activity and Data notes pages make layers 2 and 3 visible to Dana and the reviewers. No secrets or full connection strings ever go in logs.

---

## 11. Priorities (the MVP board)

### 11.1 P0: mandatory, ranked
1. **Correct numbers.** Implement all T01–T31 rules, with the golden facts in §5.3 passing and visible data notes. *Why first:* Walt, "it has to be right", and Dana will check the numbers live.
2. **Run-out projection.** Sellable stock, minus promised orders by ship date, plus open POs with corrected dates, minus seasonal demand. Real lead times, statuses (§6.8), "order at least" (§6.9), gap and late-PO flags. *Why:* it is question one of the playback, and running out hurts most.
3. **Monday screen,** web-first, readable on a phone. Both answers, urgency-sorted, a one-sentence summary, the trust strip. *Why:* Walt's "one screen", and Dana's one-minute rule.
4. **Item drill-down "why".** *Why:* Dana, "I want to click in". Without it she goes back to Excel.
5. **Stuck list.** Expired, stopped selling, inside the six-month line, long at Harbor, overstock, each with $ at cost. *Why:* question two of the playback.
6. **"I've handled this"** with optional qty and arrival date. *Why:* Dana asked for it explicitly.
7. **Tell it what it knows.** Editable vendor lead times and cushion, and an editable PO arrival date. *Why:* the lead times "live in Dana's head", and the email to Dana promised she could type in real dates for late POs.
8. **Log everything,** all four layers, plus the Data notes and Activity pages. *Why:* Ishan's requirement, and it builds trust ("show me why").
9. **Ship it.** Live deploy, one-time loader, tests per trap, README, DECISIONS, ASSUMPTIONS, DEMO_SCRIPT. *Why:* the submission checklist and the live review.

### 11.2 P1: if time allows (build in this order; each has a reason it is not P0)
1. **CSV export of both lists.** Dana lives in Excel, so this aids adoption, but it doesn't answer either question. About 20 minutes, and a likely live-change request, so keep the service layer export-friendly.
2. **QA-hold "what if it clears" toggle.** The P0 default (exclude it but show it) already follows Walt's rule. The toggle is a convenience and depends on Dana's answer to email Q4.
3. **Lot-level expiry-aware projection (FEFO)** plus "projected to expire unsold". P0 already flags every lot inside the line with $. FEFO adds precision (about 600 cs of SAL-POR6) but adds simulation complexity and more to explain in a 10-minute demo. The engine is designed to accept it.
4. **Stockout detector.** Suggest zero-sales runs of 10+ days for normally busy items as possible stockouts for Dana to confirm. It can't be auto-applied without her (email Q6). The known one is seeded.
5. **Harbor $ per month.** Needs Dana's pallet rate and cases per pallet (email P.S.). Inventing a rate would break "it has to be right".
6. **Order rounding to vendor minimums or container loads.** No MOQ or container data exists in the exports. "Order at least" is honest for v1, and Dana makes the final call.
7. **Easter-aligned Lent seasonality.** Monthly indices already capture Lent (Feb to Mar in both years). The 8-day earlier start in 2027 is a small correction relative to the work.
8. **Editable business thresholds in the UI.** The config file is enough for v1. These change rarely and add surface area.
9. **Simple passcode gate.** The data is fictional, and a gate adds demo friction. A real deployment needs proper auth (P2).

### 11.3 P2: out of scope (each with a reason; list these in the README)
- **Fresh and day-boat ordering.** Dana says it is daily, separate, and she doesn't need help. The playback says "Fresh is out for now."
- **Marco's features** (availability and price for a customer order, route planning, writing emails). Walt said "Dana first", and the playback puts Marco's questions after Dana's. The price list has tier and surcharge rules that need Marco. Prices are loaded, so phase 2 starts from clean data.
- **Live BlueTide integration or a nightly ETL.** The assignment says loading once is fine, and BlueTide is ancient with no known API. The loader's rules are pure functions, reusable for a nightly feed later.
- **Creating or sending POs.** Dana orders by phone and email, and BlueTide is the system of record. Writing POs here would create a second source of truth.
- **Transfer suggestions between buildings.** Dana doesn't care which building stock is in. It would be useful later for Harbor costs, but there is no capacity or pallet data.
- **Statistical or ML forecasting.** Only one year of history exists, and explainability matters more to a skeptical Dana than marginal accuracy. Revisit with 2+ years of data.
- **User accounts and roles.** There is a single user (Dana) and the data is fictional. Auth doesn't serve either of her two questions.
- **A native mobile app.** Ishan chose web-first, and responsive web covers her occasional phone use.
- **Pricing, margin and customer analytics.** Not requested.
- **Multi-tenant support for other Nammu clients.** A future concern. Keep the code clean and the config separated so it's possible later.

---

## 12. Comment and code standards
- **Every file** starts with a header docstring or comment: purpose, how it fits the architecture, key decisions and their tradeoffs (with ADR numbers), and "How to change this" for likely edits.
- **Every function** gets a docstring: what it does, why it exists (trap ID and transcript timestamp where relevant), parameters, return value, and a tiny example for non-obvious logic.
- **Every business rule** gets an inline comment naming its trap or rule ID, e.g. `# T11: QA-HOLD is not sellable (Walt 04:40, "If I can't sell it, it isn't inventory")`.
- **Comments explain WHY**, not syntax. Err on the side of more explanation in planning and loader code. Ishan must be able to learn the system from the comments.
- Python: type hints everywhere, `ruff` for lint and format. TypeScript: strict mode, ESLint, Prettier. React components get a short JSDoc header saying what Dana sees and which API field feeds it.
- Name things in Dana's language where it touches the UI (`order_at_least`, `on_hold_qty`, `stuck_tags`).
- No magic numbers outside `business_rules.py` and the reference CSVs.

---

## 13. Docs you must create and maintain

### 13.1 `CLAUDE.md` (keep it short; you read it every session)
Include:
- a one-paragraph project summary,
- run, test and lint commands,
- an architecture map,
- the invariants (AS_OF_DATE not the clock, never touch `data/raw`, rules only in `business_rules.py` and reference CSVs, no hard-coded codes, loader never truncates app-layer tables),
- **"After every prompt from Ishan, append to docs/PROMPT_LOG.md before your final message"**,
- a pointer to this file for full context,
- the **live-change playbook** (§17).

### 13.2 `docs/PROMPT_LOG.md`
One entry per prompt, newest at the bottom, in this format:

```markdown
## #<n> | <YYYY-MM-DD HH:MM UTC> | <short title>
**Prompt (simplified):** <one or two sentences in plain English>
**What changed:** <files/modules, migrations, seeds, deploys; "nothing" is allowed>
**Impact:** <behavior, numbers on screen, data, UI, tests, docs>
**Decisions made (and by whom):** <Ishan decided X / Claude proposed Y, Ishan approved>
**AI mistakes caught or corrected:** <honest, or "none">
**Follow-ups:** <open questions, TODOs>
```

Seed it with these three entries before entry #1:

```markdown
## #0.1 | 2026-11-25 | Data audit and strategy (claude.ai, before Claude Code)
**Prompt (simplified):** Explain every file and the transcript, how to approach the take-home, rank the MVP requirements, which questions to ask Dana, and how to use AI well.
**What changed:** No repo yet. Produced a data audit (about 30 traps), a rough answer-key model, a P0/P1/P2 board, a step-by-step plan and a first email draft.
**Impact:** Defined the requirements and rules T01 to T31. Found the demo story (SHR-1620 runs out about Dec 14 because the PO date uses the stale 8-week lead time).
**Decisions made:** Claude proposed the priorities. Ishan accepted them as the starting point.
**AI mistakes caught or corrected:** Claude's first answer-key run subtracted all open customer orders on day one, which wrongly made CRAB-SNW5 look "too late". Claude corrected it to deduct each order on its ship date (now rule T22).
**Follow-ups:** Send Dana questions. Pick the stack.

## #0.2 | 2026-11-25 | Email rewrite and stack decisions (claude.ai)
**Prompt (simplified):** Rewrite the email to Dana so it is shorter, unambiguous and uses no colons or semicolons. Use Supabase, Python and React, web-first, and log everything. PDFs of traps and priorities come later.
**What changed:** Email v2 written and sent (docs/client/email-to-dana.md).
**Impact:** The bracketed guesses in the email became the app's defaults. The PO arrival-date override became P0. Logging became a P0 requirement with four layers.
**Decisions made:** Ishan chose Supabase, Python, React, web-first and full logging. Claude proposed the four logging layers and Ishan accepted.
**AI mistakes caught or corrected:** Ishan found the first email ambiguous and daunting. It was rewritten with one or two sentences per question and a default for each.
**Follow-ups:** Wait for Dana's replies. Build the Claude Code prompt.

## #0.3 | 2026-11-25 | Build prompt for Claude Code (claude.ai)
**Prompt (simplified):** Give Claude Code all background and access to the CSVs, require a prompt log, and synthesize the entire planning chat into one prompt.
**What changed:** BUILD_PROMPT.md created.
**Impact:** Defines the architecture, business rules, golden tests, UI v1, phases and documentation for the whole build.
**Decisions made:** Claude proposed Render for the API, Vercel for the web app, the seasonal model, the statuses and the UI v1. Ishan to confirm TypeScript vs JavaScript in Phase 0.
**AI mistakes caught or corrected:** None yet.
**Follow-ups:** Start Phase 0.
```

### 13.3 `docs/DECISIONS.md` (ADRs; each with Context, Decision, Alternatives, Tradeoffs, Revisit when)

Pre-filled decisions to write up properly:

- **ADR-001 Stack.** FastAPI + React + Supabase. Ishan's strengths. Typed end to end, with OpenAPI docs.
- **ADR-002 Hosting.** Render (API) + Vercel (web) + Supabase. Cold-start tradeoff and mitigation. Serverless alternative rejected.
- **ADR-003 Raw JSONB layer + clean tables + data_issues.** Full traceability. Storage duplication is trivial at this size.
- **ADR-004 Pure engine, computed on request.** Testable and always fresh. At thousands of items, move to a nightly precompute into a `plan_results` table.
- **ADR-005 Forecast = recent level × category monthly seasonality.** Mirrors Dana's mental model. Robust to censored demand and one-offs. Limits: one year of data, monthly granularity, no trend detection.
- **ADR-006 Conservative lead times and ETA re-derivation.** Use the upper end of Dana's ranges. Never trust a BlueTide date earlier than the real lead time allows. A stockout costs more than overstock.
- **ADR-007 Sellable definition and what is shown but not counted.**
- **ADR-008 Dana's knowledge stored separately from BlueTide data.** Survives reloads, shows "BlueTide says vs you say", fully audited.
- **ADR-009 Statuses and "order at least".** Order-up-to logic with lost-sales flooring. Explainable over statistically optimal. Container rounding deferred.
- **ADR-010 Four-layer logging.**
- **ADR-011 No auth in v1.** Fictional data, single user. X-Actor header for the audit trail.
- **ADR-012 Plan in each item's selling unit,** with a human-verified pack size table instead of regex at runtime.
- **ADR-013 Demand dated by order date.** Open orders are deducted by ship date. Slightly early (conservative) for pre-booked orders.
- **ADR-014 Exclusions by rule and seed data, not hard-coded names.** INTERNAL customer type, `excluded_orders.csv`.
- **ADR-015 Alembic migrations + RLS on with no policies, all access via the API.**
- **ADR-016 Category-level seasonality with clamping.** Single-item categories (Squid, Scallops) are noisy. Shrinkage toward the overall index is a future step.

### 13.4 `docs/ASSUMPTIONS.md` (table: ID, assumption, default used, source, status)

| ID | Assumption | Default | Source | Status |
|---|---|---|---|---|
| A01 | Lead times | BXE 84, AFS 42, MNP 14, ASP 28, DLC 21 days | Call + email Q1 | Pending Dana |
| A02 | Cushion | Imports 14 days, others 7 | Call + email Q2 | Pending Dana |
| A03 | Late POs | Assume arrival in 7 days, flagged | Email Q3 | Pending Dana |
| A04 | QA-HOLD | Not counted, shown separately | Call + email Q4 | Pending Dana |
| A05 | Dormant items | TIL-FIL, SHR-6170 and PAN-1012 are discontinued | Email Q5 | Pending Dana |
| A06 | Stockouts | Only SHR-1620, Dec 11, 2025 to Jan 2, 2026 | Data + email Q6 | Pending Dana |
| A07 | ADJ lines | Netted into sellable | Not asked | Assumption |
| A08 | Credits | Ignored in demand | Not asked | Assumption |
| A09 | Samples | Excluded from demand | Call | Confirmed by call |
| A10 | Cruise order | SO-245503 excluded | Call | Confirmed by call |
| A11 | Demand date | Order date | Not asked | Assumption |
| A12 | Six-month line | Measured from lot expiry | Call | Confirmed by call |
| A13 | Order cycle | Weekly | Call ("every Monday") | Confirmed by call |
| A14 | Stuck thresholds | Overstock > 26 weeks, Harbor > 12 weeks of cover | Not asked | Assumption |
| A15 | Auth | None in v1 | Not asked | Assumption |
| A16 | Harbor $/month | Hidden until the pallet rate is known | Email P.S. | Pending Dana |

### 13.5 `README.md` (required by Nammu)
Sections:
- What I built and why (with a screenshot)
- Live link and how to use it in one minute
- How it works (data flow diagram in Mermaid)
- Key assumptions (link to ASSUMPTIONS)
- Data problems found and how they're handled (summary plus a link to DATA_AUDIT and the Data notes page)
- Out of scope, with reasons (§11.3)
- What I'd do next (P1 list plus scale path)
- **How I used AI** (tools used: Claude in claude.ai for the audit and planning, Claude Code for the build; the workflow; examples where AI was wrong and how it was caught; link to PROMPT_LOG)
- Local setup, tests, deploy

### 13.6 `docs/DEMO_SCRIPT.md` (10 minutes, for a skeptical, non-technical Dana)
1. Open the Monday screen and read the summary sentence.
2. "Last December the 16/20s ran out ten days before Christmas. The tool says it's about to happen again." Click into SHR-1620 and walk the "why" steps.
3. Show BlueTide's Dec 28 PO date corrected to about Jan 25, and the 120 cs Seabright order.
4. Mark it handled with a quantity and date, and watch the status change.
5. Lead times page: "BlueTide says 8 weeks, you say 12."
6. Stuck: the Chilean salmon at Harbor, inside the six-month line, $81K at cost.
7. Data notes: "Here's everything I didn't count and why", including hold, damaged, ZZ items, transfers, samples and the cruise order.
8. Close with what's next.

---

## 14. Phases (STOP after each and wait for Ishan's "go")

**Phase 0. Orientation and scaffolding (no app code).**
- Read everything.
- Create the folder structure, CLAUDE.md, the docs skeletons (DATA_AUDIT from §5, ASSUMPTIONS, DECISIONS headings, PROMPT_LOG with seeds #0.1 to #0.3 plus #1), and the `data/reference/*.csv` seeds.
- Ask Ishan: TypeScript or JavaScript.
- Post the plan for Phase 1.

**Phase 1. Walking skeleton, deployed.**
- FastAPI with `/api/v1/health`, JSON logging, request-id middleware and the error envelope.
- SQLAlchemy models and an Alembic initial migration for all tables (RLS enabled).
- A React shell that calls `/health` and shows the as-of date.
- Deploy to Supabase + Render + Vercel following §15.
- STOP with the live URLs and a smoke-test checklist.

**Phase 2. Loader.**
- `scripts/profile_data.py`.
- Loader stages: raw capture → rules → clean tables → data_issues → load_runs → DATA_LOAD_REPORT.md.
- Unit tests per trap (`test_T01_...` to `test_T31_...` where testable) and golden tests G01–G14 and G16.
- Run it against Supabase.
- STOP with the report and test output.

**Phase 3. Planning engine.**
- Implement `planning/` (seasonality, demand, supply, projection, ordering, stuck, explain) with synthetic-fixture tests for each function, plus golden tests G15 and G17.
- Write `scripts/compare_answer_key.py` and run it.
- STOP with the comparison table and an explanation of any differences.

**Phase 4. API, overrides, audit, logging.**
- All endpoints in §8.5, audit in the same transaction, event and request logs.
- API tests using FastAPI TestClient (against `DATABASE_URL_TEST` if set, otherwise skip with a clear message).
- STOP with example responses for `/dashboard` and `/items/SHR-1620`.

**Phase 5. Frontend v1.**
- Monday screen, item detail, lead times, data notes and activity pages.
- All states, including cold start.
- Desktop first, then check at 375 px.
- STOP with screenshots of each page (desktop and phone).

**Phase 6. Hardening and docs.**
- README, final DECISIONS and ASSUMPTIONS, DEMO_SCRIPT, the live-change playbook in CLAUDE.md, a final deploy, a run through the smoke checklist on the live URL, and a PROMPT_LOG entry.
- STOP.

**Then P1** in the order of §11.2, one item per prompt, only when Ishan says so.

**Iteration protocol (after the MVP).** For each change Ishan asks for:
1. Restate it in one sentence.
2. Plan the change (files, tests, risks).
3. Implement as a small diff.
4. Add or adjust tests.
5. Run tests and the build.
6. Deploy if asked.
7. Write the PROMPT_LOG entry.

If a request conflicts with this spec or with Dana's needs, say so before changing anything.

---

## 15. Deployment runbook (free tiers)
1. **Supabase.**
   - Create a project.
   - In Connect, copy the **Session pooler** connection string. It is IPv4-compatible. The direct connection may be IPv6-only and fail from Render or a home network.
   - Use it as `DATABASE_URL=postgresql+psycopg://...?...sslmode=require`.
2. **Locally,** with `.env` set:
   - `alembic upgrade head`
   - `python -m app.loader.run` (one time; re-runnable and idempotent for the clean layer, never touches app-layer tables).
3. **Render** web service:
   - root `backend`, build `pip install -r requirements.txt`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, health check `/api/v1/health`.
   - env: `DATABASE_URL`, `AS_OF_DATE=2026-11-16`, `CORS_ORIGINS=<vercel url>`, `LOG_LEVEL=INFO`, `PYTHON_VERSION=3.12.x`.
4. **Vercel:**
   - root `frontend`, framework Vite, env `VITE_API_BASE_URL=<render url>/api/v1`.
   - `vercel.json` rewrites all paths to `/index.html` so deep links like `/items/SHR-1620` work.
5. **Keep warm.**
   - A free uptime monitor (e.g. UptimeRobot) hits `/api/v1/health` every 10 minutes. The health check touches the DB, which also prevents Supabase's inactivity pause.
   - Open the app 5 minutes before the live review anyway.
6. **Smoke test the live URL.** Dashboard loads, SHR-1620 drill-down loads, editing a lead time is audited, and the Data notes page shows counts.

---

## 16. Known risks and gotchas
- **pandas silently "fixing" codes** (stripping, NA conversion, dropping UPC leading zeros). Always read as `str` with `keep_default_na=False`.
- **Double counting.** Watch for two snapshot nights (T01), duplicate PO lines (T24), and adding on-hold stock into sellable.
- **Date handling.** Use `date`, not `datetime`, for business dates. Never use `date.today()` in logic. Remember 2028-02-29 exists (leap year).
- **Float drift on pound quantities.** Use `Decimal` or numeric in the DB and round only for display.
- **Render cold start + Supabase pause.** See §15.
- **CORS and the SPA rewrite.** These are the two most common "works locally, broken live" bugs.
- **Scope creep.** If something isn't in P0, ask before building it.

---

## 17. Live-change playbook (put this in CLAUDE.md; it is what makes a 15-minute change possible)

| Likely request | Where to change |
|---|---|
| "Count QA-HOLD as available" or "add a location" | `data/reference/locations.csv` (+ reload) or the `locations` table. For a toggle, add a param to `planning/supply.py` |
| "Change the six-month line, cushion, thresholds" | `backend/app/config/business_rules.py` |
| "Exclude another order or customer type" | `data/reference/excluded_orders.csv` or the classifier order in `loader/classify.py` |
| "Show a new number on the dashboard" | Engine output (`planning/types.py`) → DTO (`api/v1/schemas.py`) → component |
| "Export to Excel/CSV" | New endpoint reusing `planning_service`, plus a button |
| "Different cushion for one item" | `item_settings.safety_days_override` (already supported) |
| "Filter by vendor or category" | Frontend only. The dashboard already returns vendor and category |
| "Harbor cost per month" | Add pallet rate to `locations` and cases-per-pallet to `pack_sizes.csv`, then compute in `planning/stuck.py` |

Each row must be a small, tested change. If one isn't, refactor it during Phase 6.

---

## 18. Definition of done (MVP)
- [ ] Live link works on desktop and phone. Cold start is handled gracefully.
- [ ] All golden facts G01–G17 pass. Every testable trap has a named test. `pytest` is green.
- [ ] The dashboard answers both questions. Every number drills down to lots, orders, POs and source rows.
- [ ] Handled notes, lead-time edits and PO date edits work, persist across reloads, and appear in the audit log.
- [ ] All four logging layers are working and visible (Data notes, Activity).
- [ ] README, DECISIONS, ASSUMPTIONS, DATA_AUDIT, DEMO_SCRIPT and PROMPT_LOG are complete and consistent with this file.
- [ ] Ishan can explain every rule in §5 and §6 in his own words. Write the docs to make that easy.

---

## 19. Your first response

Do Phase 0 only. Start by confirming you've read this file, the transcript and the CSV headers. Then post your Phase 0 plan (including the TypeScript vs JavaScript question) and wait for Ishan's go.
