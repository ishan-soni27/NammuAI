# Architecture and design decisions (ADRs)

Each decision records **Context**, **Decision**, **Alternatives**, **Tradeoffs** and **Revisit when**, plus who decided.
Ishan owns every decision; "Claude proposed, Ishan approved" means the idea came from the AI and Ishan accepted it.

> **Status (final docs phase, 2026-11-26):** every ADR is written out in full. ADR-001 to ADR-016 were pre-decided in
> Ishan's planning chat (`BUILD_PROMPT.md` §4.2, §13.3) and filled in as the code that implements them landed. Where a
> later decision overrode the spec (hosting, late POs, open orders), the ADR says so. **ADR-032 (Ishan's scope review)
> cut the record-keeping of ADR-026 to ADR-028 and narrowed ADR-029**: BlueTide stays the record, and the app is the
> weekly planning layer. Those ADRs are kept, marked, so the history reads end to end. **ADR-034 (2026-11-27) replaced
> ADR-032's boundary 4**: "today" is Boston's calendar date, not the day after the latest count.

## Index

| ADR | About | In one line |
|---|---|---|
| 001 | Stack | Python (FastAPI) backend, React + TypeScript frontend, Supabase Postgres |
| 002 | Hosting | One Vercel project (website + API as two services) and Supabase, not Render |
| 003 | Raw layer | Every CSV row kept as exported; clean rows point back; every change logged as a data note |
| 004 | Engine | A pure planning engine, run on every request; BlueTide's inputs cached per load |
| 005 | Forecast | Recent selling rate × the category's monthly season index |
| 006 | Lead times | Upper end of Dana's ranges; BlueTide PO dates corrected; late POs not counted until she dates them |
| 007 | Sellable | Only stock she can sell today counts; on hold, damaged, expired and old ZZ stock shown, not counted |
| 008 | Dana's knowledge | Her edits live in tables the loader never touches; every change audited |
| 009 | Status, order at least | Order-up-to with lost sales floored; container rounding deferred |
| 010 | Logging | Four layers: request logs, load runs and data notes, audit trail, prompt log |
| 011 | No login | One user, fictional data; the name she types goes on every change |
| 012 | Units | Each item planned in its selling unit; pounds per case from a checked table |
| 013 | Demand dates | Demand dated by order date; open orders deducted on ship date, counted once |
| 014 | Exclusions | Transfers, one-offs, samples and credits excluded by rule and seed files, not codes |
| 015 | Migrations, RLS | Alembic migrations; RLS on every table, no policies; all access through the API |
| 016 | Seasonality | Monthly index per category, in pounds, from active items, clamped to 0.4–2.5 |
| 017 | Client files | Originals untouched; byte-identical working copies under distinct names |
| 018 | Vendor types | Vendor classification in a seed file, not code |
| 019 | Reading CSVs | Python's csv module, not pandas, so values stay exactly as exported |
| 020 | Loads | One load, one transaction; raw rows kept per run; COPY from a laptop |
| 021 | Late, unknown stock | Late POs and QA-HOLD in their own bucket, never counted |
| 022 | Numbers | Floats inside the engine, exact decimals in the database |
| 023 | API tests | SQLite copy of the real data with the real writer; code stays Postgres-first |
| 024 | Screens v1 | Display choices the frontend makes, and the browser checks |
| 025 | Colours, dropdowns | Red, yellow, green, grey only; every item a dropdown; units spelled out |
| 026 | Direction | ~~The app becomes the main record for POs and shipments~~ **Superseded by 032** |
| 027 | Her POs | ~~Her records matched with BlueTide's (R1–R6)~~ **Superseded by 032** |
| 028 | Shipments, moves | ~~A ledger of picks and moves (R7–R10)~~ **Superseded by 032** |
| 029 | Imports | Upload, check, then load. **Narrowed by 032**: BlueTide's files only, every week |
| 030 | Downloads | One CSV per list, built from the screens' own code |
| 031 | Harbor cost | Her cases per pallet, pallets per lot, $30 per pallet per month, a saved table |
| 032 | Scope | **BlueTide stays the record; the app is the weekly planning layer** (cut the record-keeping) |
| 033 | The "why" | Numbers only, linked to source tables; one instruction for late-PO items; the chart writes off lost sales |
| 034 | Real calendar | **Today is Boston's date**; the numbers start at the count and are estimated up to today; red Out of stock and Overdue; "view as of" |

---

## ADR-001 Stack: FastAPI + React + Supabase
**Date:** 2026-11-25 · **Decided by:** Ishan (stack, in planning: BUILD_PROMPT §4.2, §8.1). TypeScript confirmed by
Ishan in Phase 0 (2026-11-25).

**Context.** Nammu asked for a working app with a backend, to be explained and changed live in a review. Ishan is
strongest in Python and React. Most of the work is data: cleaning seven messy exports and a planning engine, then a few
screens.

**Decision.** Python 3.12 / FastAPI / SQLAlchemy 2 / Alembic backend, React 18 + Vite + **TypeScript (strict)** frontend,
Supabase Postgres. Typed end to end, with OpenAPI docs at `/docs`.
**Versions (Phase 1, 2026-11-25; all pinned exactly):** Python 3.12.12, FastAPI 0.165, SQLAlchemy 2.1, Alembic 1.20,
psycopg 3.3, Pydantic 2.14. React **18.3.1**, as the spec says, even though 19 is current: the spec asked for 18 and
nothing we need requires 19. **TypeScript 5.9.3, not 7.0**: typescript-eslint 8.74 supports TS below 6.1 only. Vite 8,
Tailwind CSS 4 (tokens live in CSS `@theme`, so there is no JS config), TanStack Query 5, React Router 7 in declarative mode.
Tests use **httpx2**, because Starlette 1.x's TestClient deprecates plain httpx.

**Alternatives.**
- (a) Plain JavaScript frontend: less friction, but TypeScript catches API-shape mistakes before Dana sees them.
  Asked in Phase 0; Ishan chose TypeScript.
- (b) Node or Django backend: Node would mean one language, but Ishan's strength and the data work are Python. Django
  brings an admin and templates we don't need; FastAPI gives typed request models and OpenAPI docs.
- (c) A database without a dashboard (a SQLite file, a bare Postgres host): Supabase is real Postgres with a free tier
  and a table viewer that helps in the review.

**Tradeoffs.**
- Two languages and two deployables. One Vercel project hides most of that (ADR-002).
- The frontend's API types (`frontend/src/api/types.ts`) are written by hand to mirror `api/v1/schemas.py`, so a
  change to a response means editing both.
- Supabase's free tier pauses after about a week idle; a daily cron touches the database (ADR-002).

**Revisit when.**
- `types.ts` drifts from `schemas.py`: generate it from `/api/v1/openapi.json`.
- A library we need requires React 19.

## ADR-002 Hosting: one Vercel project (website + API as two services), Supabase for the database
**Date:** 2026-11-25 · **Decided by:** Ishan, in two steps. "Use Vercel, not Render" came first. Then "keep it simple,
why two projects?" led to a single project. This replaces the original plan (Render for the API), which Claude had
proposed in the planning chat.

**Context.** BUILD_PROMPT §8.1 put the Python API on Render (an always-on server) and the website on Vercel. Ishan had
never used Render. Its free tier sleeps after 15 idle minutes, takes 30–60 s to wake, and needs an uptime pinger.
Claude's next proposal, two Vercel projects (one per folder), worked, but meant two projects, two URLs, CORS and an
API-URL variable. Ishan asked for something simpler.

**Decision.** One Vercel project, configured by the repo-root `vercel.json` using Vercel **Services** (beta, all plans):
- `web` = `frontend/` (static Vite build; non-file paths fall back to index.html for deep links);
- `api` = `backend/` (FastAPI, entrypoint `app.main:app`, one serverless function for every route);
- top-level rewrites: `/api/(.*)` → `api`, then everything else → `web`. Vercel uses the first match and never falls
  back. **The API receives the original path** (`/api/v1/health`), which is why the routes are mounted at `/api/v1`.

The website and the API share one domain (https://nammu-ai.vercel.app), so there is no CORS and no API-URL variable.
The browser never talks to Supabase directly. All reads and writes go through the API, which validates, audits and runs
the planning engine. RLS with no policies blocks Supabase's public Data API (ADR-015).

**How it is wired**
- `DATABASE_URL` on Vercel uses Supabase's *transaction pooler* (port 6543), which multiplexes short-lived serverless
  connections. Prepared statements are off, so this works. Locally and for migrations we use the session pooler (5432).
- On Vercel (`VERCEL=1`) each instance keeps at most 1 + 2 DB connections (`db/session.py`).
- `vercel.json` pins functions to `iad1` (Washington, D.C., next to Supabase us-east-1) and runs a daily cron on
  `/api/v1/health`. That touches the DB, so Supabase's free tier never pauses.
- Local dev mirrors production: `npm run dev` proxies `/api` to uvicorn on :8000, so the frontend uses the same relative URLs.
- Traps found in Vercel's builder source and docs, each guarded by `tests/unit/test_deploy_config.py`:
  - any `backend/pyproject.toml` replaces requirements.txt as the dependency list, so tool config lives in `pytest.ini` / `ruff.toml`;
  - `.python-version` must be `3.12`, not a patch pin;
  - nested `vercel.json` files are dropped in favour of one root file;
  - the `/api` rewrite must come before the catch-all.

**Alternatives.**
- (a) Render for the API (original plan): rejected. A new tool, cold starts and an uptime pinger.
- (b) Two Vercel projects (`frontend/` and `backend/` as separate projects): works with zero beta features, and is
  the fallback if Services ever misbehaves. Rejected for v1 as more moving parts (two URLs, CORS, an API-URL variable).
- (c) GitHub Pages for the website: rejected. No rewrites, a base path, and CDN staleness after deploys.
- (d) Browser → Supabase directly with no backend: rejected. The planning logic is Python, edits need validation plus
  an audit row in one transaction, database keys would sit in the browser, and the assignment requires a backend.

**Tradeoffs.**
- Vercel Services is **beta**. The fallback (b) needs only a second project plus the old `frontend/vercel.json`
  rewrite and CORS origin, and no code changes.
- Serverless rules apply: no in-memory state between requests (the engine computes on request anyway, ADR-004).
  FastAPI BackgroundTasks aren't guaranteed to finish, so Phase 4 writes `request_log` rows inline.
- Vercel's free tier keeps raw runtime logs only briefly. The durable logs are our own tables (`request_log`,
  `event_log`, `audit_log`, `data_issues`).
- Vercel's docs don't say whether `crons`/`regions` apply with Services; verify in the dashboard after the first deploy.

**Revisit when.**
- Services leaves beta, or causes trouble: switch to (b).
- Long-running jobs appear (e.g. a nightly BlueTide feed): add Vercel Queues or a worker host.
- Kestrel Bay outgrows the free tiers: Vercel Pro and Supabase Pro need no code changes.

## ADR-003 Raw JSONB layer + clean tables + data_issues
**Date:** 2026-11-25 · **Decided by:** Ishan, in planning (BUILD_PROMPT §8.3, §13.3)
**Updated 2026-11-26 (ADR-032):** with weekly uploads, raw rows and data notes are kept for the newest 8 loads (A51),
and each raw row records the load that first brought it in (`origin_load_run_id`), so carried-over sales lines stay
traceable.

**Context.** Every number on screen must trace back to a line in a BlueTide file ("it has to be right"). The exports
hold 31 traps (DATA_AUDIT), so Dana and the reviewers will ask "where does this number come from, and what did you
change?"

**Decision.** Every CSV row is stored verbatim in `raw_rows` (JSONB), clean tables point back via `raw_row_id`, and
every excluded, corrected or flagged row gets a `data_issues` row with its trap ID. Full traceability; the storage duplication
is trivial at this size. Since Phase 6 the raw layer also lets a website import reuse the last load's copy of any file
Dana doesn't upload (ADR-029).

**Alternatives.**
- (a) One raw table per export with typed columns: a migration whenever an export changes, and typing "fixes" the very
  values we need to see (trailing spaces, leading zeros, blanks).
- (b) Keep only the clean tables: no way to show the original line or prove a cleaning step.
- (c) Keep the CSV files on disk only: not queryable, and a clean row can't point at its line.

**Tradeoffs.** The data is stored twice, plus about 16,500 raw rows and 4,000 data notes per load (fine at this size;
ADR-020). JSONB values are untyped strings, so ad-hoc queries need casts.

**Revisit when.** Loads become nightly (prune old runs), or raw data reaches millions of rows (move old runs to file
storage).

## ADR-004 Pure planning engine, computed on request
**Date:** 2026-11-25 · **Decided by:** Ishan, in planning (BUILD_PROMPT §8.4, §13.3)

**Context.** About 45 items, planned 182 days ahead. Dana's edits (a lead time, a PO date, "I've handled this") must
change the screen at once, and every rule must be testable on tiny made-up examples.

**Decision.** `planning/` takes dataclasses and returns dataclasses (no DB, clock or I/O) and runs per request. That takes
milliseconds for about 30 items × 182 days. At thousands of items, move to a nightly precompute into `plan_results`.
**Implemented 2026-11-26 (Phase 4):** `services/planning_inputs.inputs_from_db`. The BlueTide (clean-layer) inputs are cached in
memory per latest load run id (they only change when the loader runs). Dana's app-layer edits are read fresh on every request,
so an edit shows up immediately. The dashboard takes about 50 ms warm on the test database.

**Alternatives.**
- (a) Nightly precompute into a `plan_results` table: stale right after an edit, and one more job to run.
- (b) Compute in SQL: hard to test rule by rule, and hard to explain.
- (c) Cache the finished plan: every edit would have to invalidate it correctly. Caching only BlueTide's inputs, which
  change only on a load, is safe.

**Tradeoffs.** Every request recomputes the plan (about 60 ms for 45 items). Each Vercel instance keeps its own cache,
so a cold instance rebuilds BlueTide's inputs on its first request.

**Revisit when.** A request takes over 500 ms (§8.4), or the item count reaches the thousands: precompute nightly into
`plan_results`.

## ADR-005 Forecast = recent level × category monthly seasonality
**Date:** 2026-11-25 · **Decided by:** Ishan, in planning (BUILD_PROMPT §6.7, §13.3); Claude built the first model of it
in the planning chat (§4.1)

**Context.** Dana: "October is slow, December won't be, I adjust in my head." There is one year of sales history.
Stockouts hide demand (T23; last December's 16/20 shrimp), and one-offs like the cruise-line order would distort a
plain average.

**Decision.** A day's forecast = the item's recent selling rate (last 8 weeks, stockout days removed), divided by that
window's season index to get a normal-season level, times the category's index for that month (§6.7).
It mirrors Dana's mental model ("October is slow, December won't be"), and it is robust to censored demand and
one-offs. Limits: one year of data, monthly granularity, no trend detection.
**Implemented 2026-11-26 (Phase 3):** `planning/seasonality.py` + `planning/demand.py`. Shrimp comes out 1.5× in Nov–Dec and Groundfish 1.4× in Feb and 2.0× in Mar (Lent), matching what Dana described.

**Alternatives.**
- (a) A plain 8-week average: misses the December jump, which is how SHR-1620 ran out last year.
- (b) Last year's same weeks: one year is noisy, and stockout weeks show zero.
- (c) Statistical or ML forecasting (Holt-Winters, Prophet): needs 2+ years of data and can't be explained in a
  sentence (P2, BUILD_PROMPT §11.3).

**Tradeoffs.** The forecast steps on the 1st of each month, can't see a trend, and rests on one year of data. Items in
a category share its seasonal shape.

**Revisit when.** There are 2+ years of history, a clear trend appears, or Dana disagrees with a month's index.

## ADR-006 Conservative lead times and ETA re-derivation
**Date:** 2026-11-25 · **Decided by:** Ishan, in planning (BUILD_PROMPT §6.5, §6.6, §13.3); the late-PO rule changed by
Dana's reply (2026-11-26)

**Context.** Dana gave ranges on the call ("10 to 12 weeks" from Vietnam). BlueTide's lead-time field is stale (8 weeks
for Bien Xanh), and its PO dates were computed with it: the 600-case SHR-1620 PO shows Dec 28 but can't land before
about Jan 25. Three POs are past their date with nothing received.

**Decision.** Use the upper end of Dana's ranges. Never trust a BlueTide PO date earlier than the real lead time allows.
A stockout costs more than overstock. See also A18 (late means on or before AS_OF).
Each open line arrives on Dana's date if she set one, else on the later of BlueTide's date and order date + the real
lead time (§6.6).
**Updated 2026-11-26 (Dana's reply, A03):** a late PO is no longer assumed to arrive in 7 days. It is **not counted as
coming** until Dana types a real date, stays flagged, and items that only a late PO would cover are called out. This is
even more conservative than the original rule, and it's what the customer asked for. The knob is
`late_po_assumed_days` (None = don't count).

**Alternatives.**
- (a) Trust BlueTide's dates: hides the SHR-1620 stockout, last December's failure again.
- (b) The middle of each range (11 weeks for Vietnam): less safe, and running out is Dana's worst case.
- (c) Assume late POs arrive within a week (the email default): rejected by Dana.

**Tradeoffs.** Some items look more urgent than BlueTide suggests, and orders go in a little early (more stock to keep,
possibly at Harbor). Late POs stay out of the plan until Dana types a date.

**Revisit when.** The app holds enough of Dana's own receipts to measure each supplier's real lead time, or a supplier
confirms a faster route.

## ADR-007 Sellable definition, and what is shown but not counted
**Date:** 2026-11-25 · **Decided by:** Ishan, in planning (BUILD_PROMPT §6.1, §13.3), from Walt's rule on the call

**Context.** Walt: "If I can't sell it, it isn't inventory." BlueTide's on-hand file mixes sellable stock with QA-HOLD,
DAMAGED, expired lots, old ZZ items and two nights of counts (T01, T05, T11, T14).

**Decision.** Sellable means latest snapshot, sellable location, qty > 0, not expired, active item, plus negative ADJ lines.
On hold, damaged, expired and legacy stock is shown separately and never added in.
Since Phase 6 the lots also include Dana's receipts, moves and stock counts, under the same rule (ADR-027 to ADR-029).
QA-HOLD sits in the late-or-unknown bucket (ADR-021).

**Alternatives.**
- (a) BlueTide's total on hand: overstates what she can sell (today 420 cases on hold, 20 damaged, 78 expired and 59
  of old ZZ stock).
- (b) Drop the rest from view: Dana asked to see the stock on hold (email Q4), and expired stock is money to write off.

**Tradeoffs.** An item can show as short while cases sit on hold that may pass. The summary's "Not counted" line keeps
them in sight.

**Revisit when.** Dana wants a "what if the hold clears" view (P1 #3), or a building changes role (`locations.csv`).

## ADR-008 Dana's knowledge stored separately from BlueTide data
**Date:** 2026-11-25 · **Decided by:** Ishan, in planning (BUILD_PROMPT §8.3, §13.3)

**Context.** The loader rebuilds BlueTide's tables on every load. Dana's knowledge (real lead times, real PO dates,
"I've handled this", per-item settings) must survive every reload, and she should see where a number came from.

**Decision.** App-layer tables (`vendor_settings`, `item_settings`, `po_eta_overrides`, `handled_flags`) are never
truncated by the loader. The UI shows "BlueTide says / you say", and every change is audited.
Since Phase 6 the app layer also holds her own records (POs, shipments, stock moves, imports, the Harbor table; CLAUDE.md
invariant 5). `APP_LAYER` in `models.py` and a test keep foreign keys into BlueTide's tables out.

**Alternatives.**
- (a) Columns on BlueTide's tables: wiped on every load.
- (b) Write her changes back into the CSVs: the raw files never change (invariant 2), and BlueTide wouldn't see them.

**Tradeoffs.** Every read merges two sources (`services/planning_inputs.py`). Codes are plain text with no foreign keys,
so a code BlueTide drops leaves her record pointing at nothing; the import check lists those (ADR-029).

**Revisit when.** BlueTide is retired (ADR-026). The app layer is then the only record, and BlueTide's tables become an
import area.

## ADR-009 Statuses and "order at least"
**Date:** 2026-11-25 · **Decided by:** Ishan, in planning (BUILD_PROMPT §6.8, §6.9, §13.3)

**Context.** Dana makes the final call on quantities (she orders by phone and email). She needs "by when, and at least
how much", in numbers she can check against her own sense.

**Decision.** Order-up-to logic with lost-sales flooring before the new order arrives. Explainable rather than statistically
optimal. Container and minimum-order rounding is deferred to P1.
The status compares the run-out date with the lead time and cushion: too late, order this week (order-by within 7
days), order soon (within 21), fine. "Order at least" covers until the next Monday order's arrival plus the cushion;
sales lost during a stockout aren't added back (§6.8, §6.9).
**Implemented 2026-11-26:** the shortage message ends when stock really comes back. That's an earlier PO if one lands first (SHR-1620: Dec 10 → Jan 25, not the new order's Feb 8). When ordering today can't close the gap, the explanation says so instead of showing a confusing "order at least 0".

**Alternatives.**
- (a) Statistical safety stock or EOQ: needs demand variability and ordering costs we don't have, and is hard to explain.
- (b) "Order N weeks of supply": ignores stock already on the way.
- (c) A status with no quantity: Dana asks how much.

**Tradeoffs.** No container or minimum-order rounding (P1 #6), so the number is a floor, labelled "Order at least".

**Revisit when.** Supplier minimums or container sizes are known, or Dana's real orders differ from the suggestion week
after week.

## ADR-010 Four-layer logging
**Date:** 2026-11-25 · **Decided by:** Ishan ("log everything"); Claude proposed the four layers (BUILD_PROMPT §4.2, §10).

**Context.** Ishan asked to log everything. Reviewers and Dana need to see what was cleaned and who changed what, and
Ishan needs a record of how AI was used.

**Decision.** (1) JSON app logs plus `request_log`/`event_log`, (2) `load_runs` + `data_issues` + DATA_LOAD_REPORT,
(3) `audit_log` in the same transaction as every write, (4) `docs/PROMPT_LOG.md`.
The audit row commits with the change, so the two can't disagree. The Data and Activity pages show layers 2 and 3.

**Alternatives.**
- (a) A hosted logging service (Sentry, Datadog): another account and secret, and Dana couldn't see it.
- (b) App logs only: no record per row of what the loader changed, and no record of who changed what.
- (c) Audit rows written after the commit: could miss a change, or record one that rolled back.

**Tradeoffs.** Our tables grow with every request and every load (pruning is a later step, ADR-020). Vercel keeps its
runtime logs only briefly, so these tables are the lasting record.

**Revisit when.** `request_log` gets large (prune or sample it), or the app is in daily use (add error alerts).

## ADR-011 No auth in v1
**Date:** 2026-11-25 · **Decided by:** Ishan, in planning (BUILD_PROMPT §8.5, §11.3, §13.3)

**Context.** The data is fictional and there is one user, Dana. The review is a live demo, where a login screen only
gets in the way. The audit trail still needs a name on every change.

**Decision.** Fictional data and a single user. The `X-Actor` header (default "Dana") feeds the audit trail.
The website asks "Who's using this?" once, keeps the name in the browser (`kestrel-bay.actor`), and sends it with every
request.

**Alternatives.**
- (a) Supabase Auth or a passcode: friction in the demo. A simple passcode is P1 #9.
- (b) No name at all: the audit trail couldn't say who made a change.

**Tradeoffs.** Anyone with the link can see and change the data, and the name is self-reported, not proof. The database
itself is closed to the public (ADR-015).

**Revisit when.** Real data goes in, or a second person (Walt, Marco) uses the app: add logins and roles.

## ADR-012 Plan in each item's selling unit, with a human-verified pack-size table
**Date:** 2026-11-25 · **Decided by:** Ishan, in planning (BUILD_PROMPT §6.3, §13.3)

**Context.** Items are sold in cases or pounds, and BlueTide exports some lots of case items in pounds (T10). Pack
sizes are free text ("6x2.2lb", "10#", "5kg", "catch wt"; T09).

**Decision.** Every item is planned in its own `sell_uom` (CS or LB). Conversions use `data/reference/pack_sizes.csv`,
and a regex is used only to validate that table, never at runtime.
On every load the parser checks the table against BlueTide's pack text and flags a new or changed one (T09).

**Alternatives.**
- (a) Plan everything in pounds: Dana thinks and orders in cases for case items.
- (b) Parse the pack text at runtime: a new format would silently give a wrong number.

**Tradeoffs.** A new item needs a row in `pack_sizes.csv`, or pounds per case on her own item (Phase 6). Until then its
pound lots aren't counted, and that's flagged. Mixed-unit categories are added up in pounds for seasonality (ADR-016).

**Revisit when.** BlueTide or her own item list gives pounds per case reliably for every item.

## ADR-013 Demand dated by order date; open orders deducted by ship date
**Date:** 2026-11-25 · **Decided by:** Ishan, in planning (BUILD_PROMPT §6.2, §13.3); changed by Ishan on 2026-11-26 (A23)

**Context.** Customers order days or weeks before the ship date, and holiday orders are booked early (T22). The
questions are when demand "happens", and how to avoid counting an open order twice.

**Decision.** Past demand is dated by the customer's order date, when the need exists. Open orders come off stock on
their ship date. See A11. This is slightly early (conservative) for pre-booked orders.
**Changed 2026-11-26 (Ishan, A23): open orders are counted once.** They are deducted on their ship date and no longer also feed
the selling rate. Every past order shipped within 3 days, but this week's open orders are holiday pre-bookings, so counting
them in the rate as well double-counted December. It inflated SHR-1620's rate 47% and moved the holiday bump into November.
Holiday protection comes from the December seasonal index (shrimp 1.6×), the real 12-week lead time and order-by dates,
not from double counting. SHR-1620 is still too late (Dec 14), planning 542 cs for December vs last December's ~487 cs pace.
Extra margin, if wanted, comes from the per-item cushion. Switch: `open_orders_in_selling_rate`.

**Alternatives.**
- (a) Date demand by ship date: pre-booked demand stays hidden until it ships.
- (b) Count open orders in the selling rate and deduct them too (BUILD_PROMPT §6.2 as written): double counts the
  holiday bookings. Rejected by Ishan (A23).

**Tradeoffs.** A big early booking pulls a little demand forward in the history. Holiday margin comes from the season
index and the cushion, not from counting twice.

**Revisit when.** "Today" moves to the real date (new sales then feed the rate), or customers start booking months
ahead as a habit.

## ADR-014 Exclusions by rule and seed data, not hard-coded names
**Date:** 2026-11-25 · **Decided by:** Ishan, in planning (BUILD_PROMPT §6.2, §13.3)

**Context.** BlueTide records moves between buildings as sales to an internal customer (T16), $0 samples (T17),
credits as negative sales (T18), and a one-time cruise-line order (T20). Invariant 4 forbids item, order or customer
codes in logic.

**Decision.** Transfers are excluded by customer type INTERNAL, and one-offs by `data/reference/excluded_orders.csv`
(so if the cruise line returns, its new orders count).
Every sale is classified in a fixed order: cancelled, transfer, credit, sample, one-off, fresh, else real demand
(`loader/classify.py`, §6.2). Dana's own shipped orders go through the same classifier (ADR-028).

**Alternatives.**
- (a) Hard-code the cruise line's customer or order numbers: breaks invariant 4, and its future orders would be
  ignored forever.
- (b) Match customer names as text: fragile.

**Tradeoffs.** A new one-off needs a row in `excluded_orders.csv` and a laptop load (the website import uses the last
load's copy of the seeds, ADR-029).

**Revisit when.** One-offs become common: let Dana mark an order as a one-off in the app.

## ADR-015 Alembic migrations + RLS on with no policies; all access via the API
**Date:** 2026-11-25 · **Decided by:** Ishan, in planning (BUILD_PROMPT §8.3, §13.3)

**Context.** Supabase publishes every table through its public Data API unless RLS blocks it. The browser must never
hold database keys (ADR-002). Schema changes must be repeatable on the laptop, in tests and on production.

**Decision.** RLS on every table with no policies blocks Supabase's auto-generated Data API. The backend connects as
the postgres role through the session pooler (migrations and laptop loads) or the transaction pooler (the deployed
API, ADR-002).
Migrations 0001 to 0005 each list their tables in `ALL_TABLES` and enable RLS on them;
`tests/unit/test_invariants.py` checks that every table is covered.

**Alternatives.**
- (a) RLS policies and a browser client: database access in the browser, and validation and audit written twice.
- (b) Tables made by hand in the Supabase dashboard: not repeatable, no history.
- (c) `create_all` only: no upgrades for a live database (it's used only for test databases, ADR-023).

**Tradeoffs.** Every new table must turn RLS on in its migration (the test catches a miss). The API is the only way in.

**Revisit when.** Another client (a mobile app, a BlueTide feed) needs direct access, or real logins arrive (then
policies per user).

## ADR-016 Category-level seasonality with clamping
**Date:** 2026-11-25 · **Decided by:** Ishan, in planning (BUILD_PROMPT §6.7, §13.3); refined in Phase 3 (A26)

**Context.** Some categories have only one active item (Squid, Scallops), so one stockout or one big order swings a
month. Categories also mix case and pound items.

**Decision.** Monthly indices per normalized category from active items only, clamped to [0.4, 2.5]. Single-item
categories (Squid, Scallops) are noisy; shrinkage toward the overall index is a future step.
**Refined 2026-11-26 (A26):** a category's rate is summed **in pounds** (case items × verified lb per case). Groundfish (pollock blocks in lb, cod in cases) and Salmon (sides in lb, portions in cases) mix units; summing raw rates as §6.7 literally says would let the pound items set the pattern.

**Alternatives.**
- (a) A season index per item: one year of one item is noise.
- (b) One index for all seafood: misses Lent for groundfish and Christmas for shrimp.
- (c) Shrinkage toward the overall index: better for small categories, harder to explain. The noted next step.

**Tradeoffs.** The clamp can flatten a truly extreme month (none in this data). One-item categories stay noisy.

**Revisit when.** There are 2+ years of history, or Dana disputes a category's month.

---

## ADR-017 Client materials: original kept, byte-identical working copies under distinct names
**Date:** 2026-11-25 · **Decided by:** Ishan (Claude proposed moving the files; Ishan chose copy + keep + rename + commit both)

**Context.** Nammu's zip unpacked to `kestrel-bay/` (README, transcript, 7 CSVs). BUILD_PROMPT §2 expects
`docs/client/` and `data/raw/`. The raw exports must never change (invariant #12), and reviewers may want to see exactly what
Kestrel Bay sent.

**Decision.** Keep `kestrel-bay/` untouched and commit it. Copy byte-for-byte into
`data/raw/bluetide_<name>.csv`, `docs/client/ASSIGNMENT.md` and `docs/client/KICKOFF_TRANSCRIPT.md`, so a file search
never confuses the original with the working copy. `data/raw_checksums.sha256` lists the SHA-256 of both sides of every
pair, and `.gitattributes` marks the CSVs `-text` so git never rewrites their CRLF endings.

**Alternatives.** (a) Move the files (one copy, no duplication), rejected so the original zip stays available as a reference.
(b) Copy with the same names, rejected because two `items.csv` files are easy to confuse.

**Tradeoffs.** The repo stores the data twice (about 2 MB each, trivial). `data_issues.source_file` will say
`bluetide_items.csv`, not BlueTide's original `items.csv`. DATA_AUDIT documents the mapping, and the loader keeps the
file-name map in one place.

**Revisit when.** A live BlueTide feed replaces the one-time files (P2). The loader would then read from a drop folder
with the original names.

## ADR-018 Vendor classification lives in a seed (`data/reference/vendor_types.csv`)
**Date:** 2026-11-25 · **Decided by:** Claude proposed, Ishan approved (Phase 0 plan)

**Context.** T28 classifies vendors as stock_supplier (BXE, AFS, MNP, ASP, DLC), fresh_supplier (BBD), service_provider
(HCS) and legacy (OCN). BlueTide has no such column, and invariant #13 forbids hard-coding vendor codes in logic.
BUILD_PROMPT §8.2 lists no seed file for it.

**Decision.** Add `data/reference/vendor_types.csv` (vendor_code, vendor_type, note). The loader joins it into
`vendors.vendor_type`. A vendor missing from the seed is logged as a `data_issues` warning.

**Alternatives.** (a) Add a column to `vendor_settings_seed.csv`, rejected because that file holds Dana's editable
settings for stock suppliers only, and it's seed-if-missing. A classification should be rebuilt on every load. (b) A dict in
code, rejected by invariant #13.

**Tradeoffs.** One more small file to maintain.

**Revisit when.** BlueTide gains a vendor type field.

## ADR-019 The loader reads CSVs with Python's `csv` module, not pandas
**Date:** 2026-11-25 · **Decided by:** Claude, flagged to Ishan at the Phase 2 stop. BUILD_PROMPT §8.1 said "pandas is
used only in the one-time loader", and the approved Phase 2 plan kept pandas out of the deployed API.

**Context.** The raw layer must keep every value exactly as BlueTide wrote it: trailing spaces in codes, leading zeros in
UPCs, blanks. BUILD_PROMPT §16 warns that pandas silently "fixes" these unless every option is set just right. The cleaning
rules work row by row (T01–T31), so dataframes add little.

**Decision.** Read with `csv.DictReader` (`newline=""` for CRLF, `utf-8-sig`). Every value is a string, untouched. The
rules are plain functions over small dataclasses, and quantities use `Decimal`.

**Alternatives.** pandas with `dtype=str, keep_default_na=False` would work, but it's a large dependency and a known
source of subtle type coercion.

**Tradeoffs.** Grouping and summing are written as plain loops (`collections.Counter`/`defaultdict`). The whole pipeline
still runs in about 0.2 s on the full exports. No extra dependency, so the loader could later run inside the deployed API
(e.g. a nightly feed) without shipping pandas.

**Revisit when.** Data grows to millions of rows, or analysis-heavy features (forecasting experiments) need dataframes.

## ADR-020 One load = one transaction, raw rows kept per run, bulk writes with COPY
**Date:** 2026-11-25 · **Decided by:** Claude (implementation of BUILD_PROMPT §10 layer 2)
**Updated 2026-11-26 (ADR-032):** the same transaction now also merges sales history and prunes raw rows older than the
newest 8 loads (A50, A51); "today" for a load is the day after its own stock count (A49).

**Context.** A reload must never leave the database half-updated, and it must never touch Dana's edits (invariant #5). The
first real loads exposed two practical problems with a home connection to Supabase (about 300 ms per round trip, about
140 KB/s upload). Inserting row by row took about 5.5 minutes, and Supabase's 2-minute statement timeout cancelled a long
insert.

**Decision.**
- A `load_runs` row is created first (status running) and closed as succeeded or failed.
- Everything else (raw rows, `TRUNCATE` of the clean tables listed explicitly with no CASCADE, clean rows, seeding
  `vendor_settings` only where missing, `data_issues`, a row-count reconciliation) runs in **one transaction**.
- Bulk rows go through Postgres `COPY`. `SET LOCAL statement_timeout = '15min'` applies to that transaction only.
- Raw rows and issues are kept per load run, so history is auditable.

**Results.**
- A full load takes about 1 m 45 s from a laptop (it was about 5.5 m).
- A second load kept all five of Dana's vendor settings untouched.
- Both failed attempts rolled back completely (verified: 0 rows left).

**Alternatives.** Upserts instead of a rebuild: more code, and stale rows could linger when BlueTide deletes something.
One transaction per table: a crash could leave a mix of old and new data.

**Tradeoffs.**
- `raw_rows` and `data_issues` grow by about 16.5k and 4k rows per load, which is fine for the free tier at a handful of
  loads. A prune option for old runs is a later step.
- The Data notes page must read issues from the **latest successful** run only.
- COPY needs the session pooler (5432), which the loader uses.

**Revisit when.** Loads become nightly (prune old raw rows; run the loader near the database, e.g. a Vercel cron).

## ADR-021 Late and unknown inventory get their own bucket; the status counts only confirmed supply
**Date:** 2026-11-26 · **Decided by:** Dana (email Q3, Q4) and Ishan ("a separate section for POs that are late ... we
shouldn't count them as part of current inventory"). Implemented by Claude.

**Context.** Dana: late POs are "still coming, but I can't tell you which week ... please don't assume they'll arrive
within a week. If an item is only covered by a late PO, I want to see that." QA-HOLD stock "sometimes passes and comes
back" but can't be sold until it does. Ishan wants both visible as their own kind of inventory, never mixed into what's
on hand.

**Decision.**
- Supply has three buckets per item:
  1. **sellable now**;
  2. **on the way with a date**, counted on its arrival day;
  3. **late or unknown**: late POs with no date, plus QA-HOLD. Shown with quantities, **not counted**.
- The order status comes from a **confirmed** projection (buckets 1 and 2).
- For items with late POs, a second **if the late PO arrives today** projection runs. If it would turn the item fine, the
  item is flagged **covered only by a late PO**. The explanation also gives the "order at least" for both cases, so Dana
  doesn't double order.
- The trust strip shows the late quantity next to on hold / damaged / expired.

**Alternatives.**
- (a) Assume late POs arrive in 7 days (the email default): rejected by Dana.
- (b) Drop late POs entirely: hides that they may still come, and Ishan wants them visible.

**Tradeoffs.** Some items look more urgent than BlueTide suggests: calamari and 7-9 oz pangasius are now "order this
week". That's the point: their coverage depends on a PO nobody can date. The `late_po_assumed_days` knob restores the old
behaviour in one line.

**Revisit when.** Vendors give real ETAs, or Dana enters dates (each one moves its PO into bucket 2).

## ADR-022 Floats inside the engine, Decimals at the edges
**Date:** 2026-11-26 · **Decided by:** Claude (announced at the Phase 2 stop; no objection)

**Context.** BlueTide's quantities and money are exact (cases, pounds, dollars), and BUILD_PROMPT §16 warns about
float drift on pound quantities. The engine works with rates, season indices and forecasts, which are estimates.

**Decision.** The database and loader keep exact `NUMERIC`/`Decimal` quantities and money. The planning engine converts to
float at its boundary (`services/planning_inputs.py`), because rates, seasonal indices and forecasts are estimates by
nature. "Order at least" and shortfalls are rounded **up** with a 1e-9 tolerance, so 259.9999999 isn't shown as 260 and
260.0000001 doesn't become 261. Display rounds to whole cases/pounds.

**Alternatives.**
- (a) Decimal everywhere in the engine: verbose and slower, with no gain for estimates.
- (b) Floats in the database too: stored quantities and money would drift.

**Tradeoffs.** No exact-decimal guarantees inside forecasts, which is irrelevant at this precision. Tests compare with
`pytest.approx`.

**Revisit when.** Engine output is stored or billed as money (for example PO totals): keep that path in Decimal.

## ADR-023 API tests run on SQLite with the real loader writer; the code stays Postgres-first
**Date:** 2026-11-26 · **Decided by:** Claude (Phase 4), flagged to Ishan

**Context.** BUILD_PROMPT §14 asks for API tests "against DATABASE_URL_TEST if set, otherwise skip". There's no local
Postgres (no Docker daemon), and tests must never touch Supabase, so every API test would have been skipped. That would
leave the most change-prone code (endpoints, audit, validation) untested before the live-change session.

**Decision.**
- The models declare `JSON().with_variant(JSONB, "postgresql")` and `BigInteger().with_variant(Integer, "sqlite")`.
  Postgres DDL is byte-for-byte the same, and `alembic check` against Supabase reports no drift.
- The loader writer uses COPY / TRUNCATE / `SET LOCAL statement_timeout` on Postgres, and plain inserts / DELETE elsewhere.
- `db/sql.utc_now()` compiles to `clock_timestamp()` on Postgres and `CURRENT_TIMESTAMP` on SQLite.
- The test suite loads the **real** exports into an in-memory SQLite template with the **real** writer, once. Each test
  gets a fresh copy (sqlite3 backup) via `db.session.use_engine`.

**Alternatives.** (a) Skip API tests without a test Postgres: no coverage. (b) A Supabase test project: network-slow and
shared state. (c) Mock the repository layer: wouldn't test the SQL.

**Tradeoffs.** SQLite isn't Postgres: no JSONB operators, different timestamp storage, no COPY. The code avoids
dialect-specific SQL outside `write.py` and `db/sql.py`. Postgres-only paths are still covered by real loads (run #5) and
the live smoke test.

**Revisit when.** A CI Postgres service is available: run the same suite against it via `DATABASE_URL_TEST`.


## ADR-024 Screens v1: what the frontend decides on its own, and how it's checked
**Date:** 2026-11-26 · **Decided by:** Claude (Phase 5), flagged to Ishan

**Context.** Phase 5 turns the API into the screens in BUILD_PROMPT §9. A few display choices aren't spelled out in the
spec, and a non-technical reader will notice each of them.

**Decision.**
- **The chart never shows negative stock.** The engine's day-by-day balance goes below zero once demand can't be met;
  that's how it measures the shortage. Stock on a shelf can't be negative, so the item chart stops at zero and shades
  those days "Out of stock". The shortage itself is in the "Why" steps and on the Monday card. Below half a unit counts
  as out (display only).
- **Item names are shown in sentence case** (BlueTide's are all caps). Words with a digit or "&" and words with no
  vowels keep their letters (21/25, P&D, IQF); "8OZ" becomes "8 oz". The item code is always shown next to the name.
- **Busy seasons on the chart come from `business_rules.season_markers`** (Christmas, Lent 2027), served with the item.
  The frontend has no dates of its own. Display only: seasonality in the numbers comes from the monthly indices.
- **Lead times are edited in weeks**, stored in days (weeks × 7, rounded). The 1–365-day limit is enforced by the API.
- **The item page loads on demand.** Recharts is about 450 KB, so the Monday screen ships without it (283 KB).
- **Glossary bubbles ignore the mouse** (`pointer-events: none`). Otherwise the "on hold" bubble opened over the
  "Set real date" button just above it and swallowed the click (caught by the browser click-through).
- **Stuck lots carry the location name** ("Harbor Cold Storage", "New Bedford"), not the code.

**How it's checked.** Besides `npm run build` / `lint` / `format:check`, every page is rendered in headless Chrome
(puppeteer-core driving the installed Chrome, run from a scratch folder, not a project dependency) at 1280 px and 375 px:
no console errors, no page errors, no horizontal scroll. A scripted click-through makes every edit through the UI
against a throwaway SQLite copy of the real data (the ADR-023 path): mark handled (with quantity and date) and clear,
set a late PO's date from the Monday screen and clear it on the item page, change a lead time in weeks and back, open
the data notes, and check the Activity log lists each change.

**Alternatives.** Plot the raw negative balance (confusing: "-600 cs"); hard-code season dates in the frontend
(a second source of business dates); a UI component library (more weight for a handful of dialogs and toasts).

**Tradeoffs.**
- The browser checks run from a scratch folder, not in CI, so they only run when someone runs them.
- Sentence case can mis-case an unusual name; the item code is always next to it.
- The item page takes a moment longer the first time it opens.

**Revisit when.** Dana asks to see the shortfall on the chart itself (e.g. a "short by" line below zero), or the
browser checks move into CI.

## ADR-025 Traffic-light colours and dropdown rows on the Monday screen
**Date:** 2026-11-26 · **Decided by:** Ishan (colours chosen from two options Claude offered)

**Context.** Ishan's review of the first screens: "what is cs? what do the bars represent? what do the colours
represent? why do I have to scroll so far ... Dana will not use the website if it is cluttered." BUILD_PROMPT §9.1's
signal-flag palette (brown for "order this week", blue for "order soon", a different hue per stuck tag) read as random.

**Decision.**
- Red, yellow and green only, always with an icon and words: red = too late; yellow = order this week (solid) and order
  soon (light); green = fine; grey = handled / no recent sales / not planned. Stuck tags: expired and inside the
  six-month line red; stopped selling, long at Harbor and overstock yellow. Links and focus rings are ink, not blue.
- Every item on Monday (order list, handled, fine, stuck list) is a native `<details>` row. Closed: name, code, one key
  date, the runway bar and the status. Open: the order sentence, supplier terms, shortfall, late-PO note, on-hold stock,
  handled note and buttons. A one-line legend explains the bar.
- The summary is the headline sentence plus count tiles; the "not counted" detail folds away.
- Units are spelled out: "cases" (BlueTide's CS) and "lb", in the API's sentences too (`explain.unit_word`).
- An order-by date already past says "Order now (was due Fri Nov 13)".

**Result.** Monday with everything closed: 1,618 px tall at 1280 px (was 4,533), 3,687 px at 375 px (was 8,601).

**Supersedes.** BUILD_PROMPT §9.1's status and tag colours; ADR-024 is otherwise unchanged.

**Update (Ishan, 2026-11-26, prompt #28).** What to order, Handled and Fine are now a **grid of cards** (one column
on phones, two from 640 px), not a list: status, code, name, key date, the runway bar and how much to order. A
clicked card opens across the full row (`open:col-span-full`) and the cards after it fill in (`grid-flow-dense`).
The stuck list stays a list (it is grouped by problem with money on each row).

**Update (Ishan, 2026-11-26, prompt #29).** What to order is split into one dropdown per status, most urgent
first: **Too late** and **Order this week** start open, **Order soon** starts closed. Each header shows the status
chip, how many items, and one line on what it means; inside is the grid of cards, which no longer repeat the chip
(the coloured edge stays). Every dropdown has its own *named* Tailwind group (`group/card`, `group/section`,
`group/disclosure`, ...). A shared `group` makes a parent's open or hover state leak into everything inside it (the
bubble bug, #28, and closed cards showing "Close", #29).

**Alternatives.**
- (a) BUILD_PROMPT §9.1's signal-flag palette: Ishan found it random.
- (b) One long table of every item: dense, but wide rows and the same scrolling problem. Ishan asked for dropdowns.

**Tradeoffs.** Order this week and order soon are both yellow (solid and light), so the words and icon carry the
difference. Details are one click away instead of on screen.

**Revisit when.** Dana mixes up the two yellows, or needs to compare many items side by side (the order-list download
covers that today, ADR-030).

## ADR-026 Direction: the app becomes the main record for POs and shipments
**Date:** 2026-11-26 · **Decided by:** Ishan · **Status:** ~~direction decided; built in Phase 6 (ADR-027 to ADR-030)~~
**Superseded by ADR-032 (2026-11-26):** BlueTide stays the record. The code is on `archive/system-of-record`.

**Context.** Ishan: "This is an ERP system ... It is supposed to be a system that Dana can use for the future as well.
She needs to be able to log and track stuff." The build so far only analyses one load of BlueTide exports, because
BUILD_PROMPT §11 listed creating POs and live loading as P2.

**Decision (Ishan's answers, 2026-11-26).** Build all four: log POs and track them to received; log outgoing shipments;
upload new BlueTide files from the website; download lists to CSV. On how the app relates to BlueTide: "This would be
the system to eventually replace BlueTide, therefore it should be able to do both, add on top of BlueTide AND replace
BlueTide for these ... the design should lean towards replacing BlueTide. The app will become the main record for them."

**Consequences.** New app-owned tables that the loader never touches (invariant 5) and that hold no foreign keys into
the BlueTide tables (the loader TRUNCATEs those). Where both have the same PO or order number, the app's record wins and
the difference is flagged. Business "today" has to move forward with new data (a decision for Ishan in the Phase 6
plan). The Harbor storage calculator (P1 #1) and the README / demo phase move after this work.

**Alternatives.**
- (a) Stay a read-only tool over BlueTide's exports (BUILD_PROMPT §11.3 kept creating POs out of scope, to avoid a
  second source of truth): Ishan chose otherwise.
- (b) Replace BlueTide at once: Kestrel Bay still runs BlueTide, so the app has to work on top of it during the switch.

**Tradeoffs.** During the switch the same POs and orders live in two places, so the matching rules (R1–R10) and their
flags are needed. More to build and test. With "today" fixed at Nov 16, new records don't move the selling rate yet.

**Revisit when.** BlueTide is retired (drop its imports), or "today" switches to the real date.

## ADR-027 Dana's own records, matched with BlueTide's by document and quantity (rules R1-R6)
**Date:** 2026-11-26 · **Decided by:** Ishan (plan approved, with "independent of BlueTide"); design by Claude after
a design review
**Superseded by ADR-032 (2026-11-26):** the records and rules R1–R6 were cut (migration 0006). Archived on
`archive/system-of-record`.

**Context.** Phase 6 lets Dana keep her own records (ADR-026). The app must never count the same cases twice, must
still work when BlueTide files keep coming, and (Ishan, on approval) must work with no BlueTide data at all.

**Decision.**
- **App-layer tables** (migration 0002, RLS on, no foreign keys into BlueTide's tables, never truncated by the loader):
  `app_vendors`, `app_items` (her copy wins on the same code), `purchase_orders` + `purchase_order_lines_app` (POs she
  creates), `po_line_status` (shipped or cancelled, for any line), `stock_movements` (a ledger: receipts now; shipments,
  moves and adjustments in step 2). Undo writes a reversing row; nothing is edited or deleted.
- **One date table:** her expected date for any line (hers or BlueTide's) lives in `po_eta_overrides` (R1).
- **Matching by document and quantity, not date** (`planning/records.py`, pure). BlueTide's `qty_received` has no date,
  so "ignore anything before BlueTide's stock count" would miscount (design review).
  - R2: the same PO in both is matched by PO + line, else PO + item; counted once; her quantity wins.
  - R3: received = max(hers, BlueTide's); only the part BlueTide hasn't seen becomes stock, newest receipts first.
  - R4 (Ishan): BlueTide says received or closed while she still expects more: not counted; flagged.
  - R5: BlueTide says cancelled: not counted; flagged.
  - R6: a lot already in a BlueTide count dated on or after the receipt is not added again.
- **The engine is unchanged.** `services/planning_inputs.build_context` hands it ordinary inputs: PO lines still to
  come (with a source and flags) and lots she received. BlueTide's full PO lines and the stock count's lot keys are
  cached per load (`BlueTideFacts`).
- **Independent of BlueTide.** Her items and suppliers join BlueTide's; a test plans an item from her records alone
  (`test_the_plan_works_from_danas_records_alone_with_no_bluetide_data`).

**Verified.** All 201 earlier tests unchanged (BlueTide-only numbers identical); 23 rule tests and 17 API tests added;
`alembic check` against Supabase after the upgrade: no drift; RLS on every table.

**Known limits (next steps).**
- Buildings (`locations`) still come from the reference seeds through a load; with no load at all there are no
  buildings to receive into. Step 3 (import) fixes this.
- A new item has no sales history until step 2 (shipments) or step 3 (her sales history upload), so it shows as
  "no recent sales" until then.
- An app PO does not revive a dormant BlueTide item (dormant is set at load time).

**Alternatives.**
- (a) A date cut-off ("ignore anything before BlueTide's last count"): BlueTide's received quantity has no date, so it
  miscounts (the design review found four ways).
- (b) BlueTide always wins: her records would be overwritten on every load, against ADR-026.
- (c) The app always wins, receipts included: Ishan chose that BlueTide's receipt wins (R4).

**Tradeoffs.** More rules to explain (R1–R6 here, R7–R10 in ADR-028), each with its own test. Conflicts are flagged
for Dana, not settled silently.

**Revisit when.** BlueTide exports receipt dates (a date rule becomes safe), or BlueTide is retired.

## ADR-028 Orders going out and stock moves: a ledger of picks, matched with BlueTide's orders (R7-R10)
**Date:** 2026-11-26 · **Decided by:** Ishan (Phase 6 plan, step 2 "go"); design by Claude
**Superseded by ADR-032 (2026-11-26):** shipments, picks, moves and rules R7–R10 were cut (migration 0006). Archived
on `archive/system-of-record`.

**Context.** Step 2 of ADR-026: Dana logs orders going out (and samples), ships them, and moves stock
between buildings (Harbor costs money every month). The plan must count each case once whether or not BlueTide
also has the order, and keep working with no BlueTide data.

**Decision.**
- **Tables** (migration 0003, app layer, RLS on): `app_customers` (BlueTide's customers table is rebuilt on every
  load), `shipments` + `shipment_lines`; `stock_movements` gains `shipment_id`, `shipment_line_no` and `pair_id`.
- **An order is promised while open** (an open `SaleInput` on its ship date). **Shipping writes picks** (negative
  movements on named lots, soonest to expire first, shown before confirming and editable), and a shipped customer
  order joins the selling-rate history if `loader/classify.classify_sale` calls it real demand (samples, credits,
  one-offs and internal customers never are).
- **Matching BlueTide's orders by order number + item** (`planning/records.reconcile_shipments`): R7 (BlueTide
  invoiced, hers open: not counted again, flagged), R8 (hers shipped, BlueTide open: hers applies, counted once; both
  open: hers, once; both shipped: BlueTide's count already has it out).
- **Moves** are a paired out and in (`pair_id`); undo reverses both. R9: moves dated on or before BlueTide's stock
  count are refused and ignored. **R10:** a pick larger than its lot takes the next lot to expire in the same
  building; stock never goes below zero; any shortfall is flagged (`apply_movements`).
- **Lots carry where they came from** (BlueTide's count, received, moved), so the item page shows the same lots the
  plan counted, and lists every stock change made in the app with Undo (picks undo with their order).

**Verified.** 12 rule tests and 15 API tests on the real data; earlier numbers unchanged (268 tests);
`alembic check` against Supabase after 0003: no drift; RLS on every table; local and live click-throughs.

**Known limits.**
- With "today" fixed at Nov 16, new sales are outside the 8-week selling-rate window: they change stock and promised
  orders, not the selling rate, until "today" moves (ADR-026 follow-up).
- Shipping is all-or-nothing per order (no partial shipments yet).

**Alternatives.**
- (a) Edit a lot's quantity in place: no history and no undo.
- (b) Take shipments off item totals instead of lots: loses expiry dates, which the six-month line and the stuck list
  need.
- (c) Let a pick take a lot below zero: the planner drops negative lots silently (`planning/supply.py`), so the extra
  cases would never come off stock (R10).

**Tradeoffs.** The ledger only grows (undo adds rows). Moves must be dated after BlueTide's count.

**Revisit when.** Partial shipments are needed, or a scanner or warehouse system reports picks.

## ADR-029 Imports from the website: check first, then load; BlueTide's files or Dana's own templates
**Date:** 2026-11-26 · **Decided by:** Ishan (Phase 6 plan, step 3 "go"; "it should be able to be its own independent
system"); design by Claude after the design review
**Narrowed by ADR-032 (2026-11-26):**
- BlueTide's files only; Dana's own templates were cut.
- It's the weekly loop: each upload moves "today" to the day after its stock count, merges sales history, and keeps raw
  rows for 8 loads.
- The "stock count after today" blocker is gone; a same-night count warns.
- The upload/check/load flow below is unchanged.

**Context.** Dana must be able to bring in next week's BlueTide exports herself, or, for the app to stand without
BlueTide, her own data. The deployed API can't see `data/` (its root is `backend/`), production's database
connection (the transaction pooler) has no COPY, and Vercel caps a request at 4.5 MB.

**Decision.**
- **Three steps, always:** upload files into slots (one request per file, the bytes kept exactly so the SHA-256
  matches), **check** (a dry run that writes nothing but its report), **load** (only with the check's one-time code).
  A new file after a check needs a new check.
- **BlueTide:**
  - wrong or empty files are refused on upload (required columns per export);
  - slots left empty reuse the last load's file, rebuilt from `raw_rows`;
  - the check runs the real loader and reports **blockers** (stock count after today, older than the loaded one,
    missing files, no stored seeds), **warnings** (rows halved, same files), what would change, the cleanup count,
    and what it does to Dana's records (R4/R7 conflicts, items her records use that the files drop);
  - the load uses `write_load(use_copy=False)` in one transaction and never touches her tables;
  - stale "running" loads are marked failed first.
- **Seeds travel with each load:** `load_runs.reference` keeps `data/reference/*.csv` as read. The website's import
  uses the last load's copy, so changing a seed still means a laptop load (run #6 stored the first copy).
- **Dana's templates** (suppliers, items, customers, stock count, POs, sales history):
  - downloaded with their header row, filled in Excel, uploaded;
  - every row is checked, and codes may come from another file in the same import;
  - any problem blocks the load, listed by file, line and what to fix; the load is all-or-nothing;
  - her copy wins on the same code.
  - **A stock count** is the starting stock for the items it lists when it's newer than BlueTide's. Receipts, picks
    and moves dated on or before it are already in it.
  - **Sales history** feeds the selling rate (classified like BlueTide's sales), never stock.

**Verified.**
- 8 API tests, including a full reload of the real files through the API (numbers unchanged, her PO kept), refused
  files, after-today and older counts blocked, a full template set planned with no BlueTide data for the new item,
  and a bad row reported with its line.
- A browser click-through of both paths.
- A live import of the real stock-on-hand file through production.

**Known limits.** Buildings still come from the reference seeds (a brand-new install needs one laptop load first);
open customer orders aren't in the sales-history template (they're logged on the Shipments page); a file over
4.4 MB must be split.

**Alternatives.**
- (a) Keep loads laptop-only: Dana couldn't do it herself.
- (b) A session-pooler secret on Vercel so COPY works: one more secret; batched inserts load in about 6 seconds live.
- (c) All files in one request: over Vercel's 4.5 MB limit.
- (d) Load straight away with no check: a wrong file would replace good data.

**Tradeoffs.** Changing a seed still needs a laptop load. One bad row blocks a whole template import (A44).

**Revisit when.** Files grow past the limit (upload straight to storage), or BlueTide gets an API (a nightly feed).

## ADR-030 Download to Excel: one CSV per list, built from the screens' own code
**Date:** 2026-11-26 · **Decided by:** Ishan (Phase 6 plan, step 4 "go"); details by Claude
**Updated by ADR-032 (2026-11-26):** the shipments download went with the shipments. The PO download is now BlueTide's
open lines as the On the way page shows them (our date, BlueTide's date, late). The Harbor table download (ADR-031)
joined the list.

**Context.** Dana works in Excel and forwards lists to people who don't use the app. She needs the order list, the
stuck list, the POs, the shipments and the data notes as files.

**Decision.**
- `GET /api/v1/exports/{order-list|stuck-list|purchase-orders|shipments|data-notes}.csv`, a plain link on each page
  ("Download for Excel"); the file is named `kestrel-bay-<list>-<today>.csv`, so a folder of weekly downloads sorts.
- **Excel-friendly on purpose:**
  - UTF-8 with a byte-order mark, so names like "Austral Frío" aren't garbled;
  - dates as 2026-11-16, which Excel reads as dates in any locale;
  - numbers without units, with the unit in its own column, so columns add up;
  - statuses in her words ("Too late", "Ordered", "Left out"), "yes"/"no" for flags;
  - CRLF line ends.
- **Same numbers as the screens:** each file is built from the service the page uses (`planning_service.all_items`
  and `dashboard`, `records_service.purchase_orders`, `shipments_service.shipments`, the latest load's data issues).
  No second copy of any rule.
- **Every row, not the filtered view** (A46): the order list has every item with its status, PO and shipment files
  have every line. She filters in Excel, and nothing is silently missing.
- One row per **lot** on the stuck list and per **line** on POs and shipments, so totals can be summed.

**Verified.**
- 5 API tests on the real data: BOM, CRLF, file name, row counts against the screens' endpoints, SHR-1620's values,
  SAL-POR6's 1,050 cases at Harbor, her PO next to BlueTide's, an unknown list is a plain 404.
- Browser: each link downloads its file at 1280 px, with no sideways scrolling at 1280 or 375 px, locally and live.

**Known limits.** CSV, not .xlsx (no formatting or several sheets). Downloads aren't recorded in the activity log
(they change nothing; the request log has them).

**Alternatives.**
- (a) A formatted .xlsx: a new dependency for formatting nobody asked for; a CSV opens in Excel as is.
- (b) Download only what's filtered on screen: rows would be silently missing (A46).
- (c) Build the file in the browser: a second copy of the formatting rules, and a page doesn't hold every row (data
  notes load a page at a time).

**Tradeoffs.** No formatting, formulas or several sheets. Excel guesses each column's type (fine for ISO dates and
plain numbers).

**Revisit when.** Dana asks for formatting, or several lists in one file.

## ADR-031 Harbor storage cost: Dana's cases per pallet, pallets per lot, and her own saved table
**Date:** 2026-11-26 · **Decided by:** Ishan (prompt #17: "a harbor storage costs calculator ... they can input how
many cases fit on the pallet ... an option that adds it to a data table which they can then export later as a CSV";
"go" after Phase 6); details by Claude

**Context.** Harbor Cold Storage charges $30 per pallet per month (Dana's reply). BlueTide has no pallet data, so
the cost of the stock sitting there was hidden (A16). Walt: "Long stock sitting at Harbor is the worst case."

**Decision.**
- **A Harbor page** (nav "Harbor"): every item with stock at a paid warehouse (`is_third_party_storage`), its cases
  and lots, and why it's on the stuck list if it is.
  - Dana types **cases per pallet** per item, and pallets and dollars a month show as she types.
  - Her number is remembered in `item_settings.cases_per_pallet` (app layer, audited), by "Save" or by adding a row.
  - An item without cases per pallet shows no cost, and the summary says how many still need it. It's never guessed.
- **The rule** (pure, `planning/storage.py`; A47): each lot on its own pallets, a part pallet charged as a whole one,
  pounds turned into cases with pounds per case. The rate is `business_rules.harbor_pallet_cost_per_month`.
- **The stock is the plan's own lots**, BlueTide's count plus her receipts and moves, so moving a lot out of Harbor
  lowers the cost at once.
- **Her table** (`harbor_storage_rows`): "Add to table" (one item, all priced items, or a what-if amount for any item)
  is worked out again on the server and stored exactly as calculated, rate included, so a later change never
  rewrites it. Rows can be removed (audited), and the table downloads as `/exports/harbor-storage.csv`.

**Verified.**
- 5 unit tests for the rule.
- 4 API tests on the real data: 14 items and 2,095 cases at Harbor; SAL-POR6 at 60 a pallet is 18 pallets, $540;
  a what-if; validation; all-or-nothing; the download; remove.
- A browser click-through: live cost, Add, Save, Add all, what-if, download, remove, and a move out of Harbor
  dropping SAL-POR6 to 10 pallets, $300.
- No sideways scrolling at 1280 or 375 px.

**Known limits.** One rate for every paid warehouse (only Harbor today). No "cost so far": BlueTide's received date
isn't the date a lot reached Harbor (T30). No cost per item on Monday's stuck list yet.

**Alternatives.**
- (a) The rate and cases per pallet in the seed files (`locations.csv`, `pack_sizes.csv`; the old playbook row):
  every change needs a laptop load, and Dana can't edit them.
- (b) Pallets from each item's total cases: a lower number, but lots aren't mixed on a pallet.
- (c) A typical cases per pallet for every item: an invented number.

**Tradeoffs.** The total is only as complete as the numbers she types. Rounding each lot up errs high (A47). Saved rows
are snapshots and don't follow later stock changes.

**Revisit when.** Harbor's invoice shows a different pallet count (check the rule against it), a second paid warehouse
appears (a rate per location), or someone can supply real pallet counts.

## ADR-032 BlueTide stays the record; the app is the weekly planning layer
**Date:** 2026-11-26 · **Decided by:** Ishan (scope review in claude.ai after Phase 6; prompt log #34–#36)

**Context.**
- **Phase 6 (ADR-026 to ADR-029) made the app a second system of record.** POs, receipts, shipments, picks, moves and
  template imports were recorded in the app **and** in BlueTide.
- That needed:
  - matching rules R1–R10, so nothing was counted twice;
  - 12 extra tables;
  - assumptions A27–A45;
  - double data entry for Dana's team, which nobody on the kickoff call asked for.
- **Dana's real need** (call 00:01:10): her Monday spreadsheet, where she pulls BlueTide's reports into Excel and goes
  line by line for half a day.

**Decision.**
- **BlueTide stays the system of record, and the app replaces the Monday spreadsheet.** The weekly loop:
  1. Dana uploads the exports;
  2. everything recalculates;
  3. she looks at the two answers;
  4. she adjusts what BlueTide doesn't know;
  5. she orders, in BlueTide and by phone, as today.
- **Six boundaries** (CLAUDE.md invariants):
  1. BlueTide owns every fact (stock, sales, POs, receipts), from uploaded files only; the app never records a
     transaction.
  2. The app stores only Dana's knowledge (vendor settings, item settings including cases per pallet, PO dates,
     handled notes, the Harbor table) and the logs (uploads, load runs, data notes, audit, events, requests).
  3. Each upload refreshes BlueTide's data; sales lines accumulate (A50).
  4. ~~"Today" follows the data: the latest load's stock count + 1 day; `AS_OF_DATE` only overrides it (A49).~~
     **Superseded by ADR-034 (2026-11-27):** today is Boston's calendar date; the count's day + 1 is the *data date*.
  5. The math is deterministic, with no LLM anywhere; every number traces back to an uploaded row.
  6. No order entry, receiving, shipping, stock moves, or adding customers, items or suppliers in the app.
- **The cut, archived on tag `archive/system-of-record` (0796817):**
  - **Code:** `planning/records.py`, `records_service`, `shipments_service`, `template_import` and the shipments
    router.
  - **Routes:** PO create/ship/cancel/receive/undo, `/locations`, item and supplier creation, `/import-templates`.
  - **Tables:** 12, dropped by migration 0006 (on production they held only cancelled test records).
  - **Screens:** New PO, Shipments, New order, Items, Move stock, Add a supplier, the template import.
  - **What stays, read only:** an **On the way** page lists BlueTide's open PO lines, with "Set real date".
- **Weekly uploads made right (step 3):** derived "today", handled notes dated in business time, accumulating sales,
  raw-row retention (A49–A51), and season bands computed for any year.

**Alternatives.**
- (a) **Keep Phase 6 as built:** double data entry and ten matching rules for records BlueTide already has. Rejected.
- (b) **Fully replace BlueTide:** rejected.
  - BlueTide also runs Marco's order entry, accounting's credits, warehouse receiving and transfers, and invoicing.
  - Replacing only part of that still leaves Kestrel Bay on two systems.
  - Replacing all of it is an ERP migration.
- (c) **A live BlueTide connection:** it has no known API. Weekly uploads of its exports are the honest interface.

**Tradeoffs.**
- POs, receipts and shipments are still entered once, in BlueTide.
- The app is as fresh as the last upload (weekly). Between uploads, Dana's "I've handled this" note (with quantity and
  date) says "I ordered this" until BlueTide shows the PO, and the note then offers to clear itself.
- Raw rows older than 8 loads are pruned; summaries stay.
- The cut removed 8,070 lines of code and tests and added 627 (commits 44ef859, eb7f15a), all kept on the archive
  tag.

**Revisit when.** **Kestrel Bay asks to retire BlueTide.** Then follow the README's "Roadmap off BlueTide":
- purchasing first;
- then sales and receiving;
- BlueTide retired last;
- each kind of record owned by exactly one system at a time.

## ADR-033 The "why" as numbers, one instruction for late-PO items, a chart that writes off lost sales
**Date:** 2026-11-26 · **Decided by:** Ishan (plan step 4, the instruction's wording); details by Claude

**Context.**
- **The sentences read like a memo.** Ishan checked they weren't pre-written for the demo items (#35: the only hit was
  a colour code). They were shared templates filled from live numbers, but they still read like a memo.
- **Two lines contradicted each other.** Items only a late PO would cover said "Order at least N" and also "if the late
  PO shows up, you wouldn't need to order".
- **The chart bug** (found reading `projection.build_scenario` while planning): the chart plotted the plain balance,
  which carries sales lost during a stockout forward. So SHR-1620 showed about 218 cases when its 600-case PO lands,
  instead of about 594.

**Decision.**
- **`explain.breakdown`:** rows {key, label, qty, unit, date, detail, link}, from the same values, only those that apply.
  The rows are: can sell (by building), not counted, promised, each counted arrival (with BlueTide's date when
  corrected), each late PO, selling per week, season ahead, runs out, new order lands, short (too late only), order at
  least, and if the late PO arrives today.
  - `link` is the item-page table with the source rows.
  - It replaces `ItemDetailOut.explanation`.
- **`explain.late_po_instruction`:** one sentence, computed once and shown on the Monday card and the item page.
  - With something to order: "Order at least 127 cases, unless PO-260394 (800 cases) is really coming. Ask the supplier
    for its date and set it here, and these numbers update."
  - With nothing to order: "Nothing to order today, but … is late."
  - With several late POs, it names them all.
- **Monday cards** opened: short computed labels only, plus the instruction.
- **The chart uses the floored balance;** run-out and status still come from the plain one.
- **A reconciliation test on the real data:** can sell − promised (shipping by X) + counted arrivals (by X) − forecast
  (through X) + lost sales (through X) = chart stock on X, for 5 items × 5 dates.

**Alternatives.**
- (a) **Keep the sentences:** rejected (a memo, and harder to check).
- (b) **Compute the instruction in the browser:** rejected (two places to keep in step; the engine's is tested).
- (c) **Keep the plain chart with a note:** rejected (it misstates what's on the shelf after a stockout).

**Tradeoffs.**
- Less narrative: Dana reads a table, and the labels link to the tables that explain them.
- The can-sell note uses building codes (NB, PVD, HCS), because the pure engine has no names.

**Revisit when.** Dana asks for words back, or the chat assistant (P2) explains from these rows.

## ADR-034 Today is Boston's calendar date; the numbers start at the count and are estimated up to today
**Date:** 2026-11-27 · **Decided by:** Ishan (the real calendar, Boston time, and four answers in plan mode; prompt log
#39–#40); details by Claude. **Supersedes** ADR-032's boundary 4 and A49.

**Context.**
- **"Today" used to follow the data** (ADR-032 boundary 4): the day after the latest BlueTide stock count. Between
  uploads the app froze. If Dana skipped three weeks, an item that said "order by Nov 22" still said it on Dec 7, with
  nothing urgent about it.
- **Ishan (2026-11-26):** "This has to be a system that Dana can check any day … use a real calendar … Boston timing. It
  has to be dynamic. If Dana doesn't log anything for 3 weeks and something says to order by November 22nd, it should
  say that it is overdue or out of stock with some sort of indicator that it is urgent."
- **The catch:** BlueTide's facts are still only as fresh as the last upload. Moving "today" without saying so would
  make stale stock look current.

**Decision.**
- **Two dates:**
  - **Today** = Boston's calendar date (`America/New_York`, so 11:30 pm in Boston is still that day, and daylight saving
    is handled). It's read in one place, `config/clock.py`. `AS_OF_DATE` overrides it for the whole server (tests, a
    fixed demo), and a request can view an earlier day (below). `tzdata` ships with the API, so Vercel doesn't depend
    on the server's zone files.
  - **Data date** = the day after the latest count (`rules.data_date`, the projection's day 0).
- **What each is used for:**
  - *Measured to the data date* (what the upload knows): the selling-rate window, the season pattern, stopped selling,
    and "late" POs (A18: due on or before the data date and not received).
  - *Judged against today*: statuses, order-by, "order at least", when a new order lands (today + lead time), expiry and
    the six-month line, stuck tags, the validation of Dana's dates, and the day her edits are written on.
- **The estimate between them** (Ishan's answer 1: show both):
  - the count − expected sales − customer orders scheduled to ship + confirmed arrivals, with sales lost while out of
    stock written off;
  - cards and the item page show "At the count (Sun Nov 15)" next to "Can sell now (estimated)", in whole units, with
    the bridge rows (expired since, sold and shipped since);
  - the chart starts at today.
- **Supply nobody can confirm yet** (Ishan's answer 2: don't count it):
  - a PO due between the data date and today: "Due since your last upload", not counted;
  - a PO date Dana set that has passed: "Your date has passed", not counted;
  - a handled note whose date has passed (Ishan 2026-11-27, A25): not counted, and the item leaves the grey Handled
    group for its real status. The note stays on the card, marked.
- **Two new red statuses** (Ishan's answer 3), ranked Out of stock > Too late > Overdue > Order this week > Order soon:
  - **Out of stock:** the estimate (or the count) is gone by today. The card says "Out of stock since about Tue Nov 24";
  - **Overdue:** the order-by date has passed, but an order placed today still lands before the run-out ("Overdue by N
    days").
  - Monday gets a group and a tile for each when there are some, and the headline leads with them.
- **Freshness:** the header shows the count's age ("12 days ago"). There's a yellow banner after `stale_data_days` (7)
  and a red one after `very_stale_data_days` (14), each with a link to upload this week's files.
- **View as of** (Ishan's answer 4):
  - a header date control from the data date to today, kept for one browser tab (sessionStorage);
  - it sends `X-As-Of` on every call; downloads add `?as_of=`;
  - a yellow "Viewing as of … · Back to today" strip;
  - edits are judged against, and dated by, the viewed day;
  - a date outside the range gets a plain-English 422.
  - This is how the assignment's Monday, Nov 16, stays reviewable.
- **Uploads:** a load describes its files as of their own data date (`rules_for_load`). The check blocks a count dated
  after today, and says where the numbers will start ("Loaded, the numbers start from Mon Nov 23").

**Alternatives.**
- (a) **Keep "today" = the data** (ADR-032): rejected. It's what Ishan asked to change, and it hides urgency between
  uploads.
- (b) **Move today and keep the counted stock as if it were current:** rejected. It overstates stock: SHR-2125 would
  still look like 90 cases on Nov 27, when by the estimate it ran out on Nov 24.
- (c) **The browser's clock:** rejected. Each viewer could see a different day, and boundary 5 wants every number
  computed on the server.
- (d) **UTC:** rejected. Evenings in Boston would already show tomorrow.
- (e) **Count POs due since the upload:** rejected by Ishan (answer 2). We can't know they arrived.

**Tradeoffs.**
- Between uploads the numbers are estimates, and the longer the gap, the further off they can be. That's why there are
  two banner levels, and the count and the estimate sit side by side.
- **"Overdue" applies with no gap too:** on Nov 16, LOB-MEAT (order by Nov 13) moved from "Order this week" to
  Overdue. Monday as of Nov 16 is 3 too late, 1 overdue, 5 this week, 5 soon, 16 fine (it was 3 / 6 / 5 / 16).
- After an upload, earlier days can't be viewed: the window starts at the new data date.
- Nothing new is cached: the plan is still computed on every request (ADR-004), and only the rules are cached,
  per (count, today).

**Revisit when.**
- Dana uploads more or less often than weekly: tune `stale_data_days` and `very_stale_data_days`.
- BlueTide gets a live feed, or a daily export: the gap shrinks to a day and the estimate barely matters.
- Kestrel Bay works in another time zone: change `business_timezone`.
