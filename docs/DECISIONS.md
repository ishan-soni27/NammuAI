# Architecture and design decisions (ADRs)

Each decision records **Context**, **Decision**, **Alternatives**, **Tradeoffs** and **Revisit when**, plus who decided.
Ishan owns every decision; "Claude proposed, Ishan approved" means the idea came from the AI and Ishan accepted it.

> **Status (Phase 0, 2026-11-25):** ADR-001 to ADR-016 are pre-decided in `BUILD_PROMPT.md` §13.3 and are listed here
> with their one-line decision. Each gets its full write-up as the code that implements it lands, and all are finished
> in Phase 6. ADR-017 and ADR-018 were made in Phase 0 and are written out in full.

---

## ADR-001 Stack: FastAPI + React + Supabase
**Decision:** Python 3.12 / FastAPI / SQLAlchemy 2 / Alembic backend, React 18 + Vite + **TypeScript (strict)** frontend,
Supabase Postgres. Typed end to end, with OpenAPI docs at `/docs`. **Decided by:** Ishan (stack). TypeScript confirmed by Ishan in Phase 0 (2026-11-25).
**Versions (Phase 1, 2026-11-25; all pinned exactly):** Python 3.12.12, FastAPI 0.165, SQLAlchemy 2.1, Alembic 1.20,
psycopg 3.3, Pydantic 2.14. React **18.3.1**, as the spec says, even though 19 is current: the spec asked for 18 and
nothing we need requires 19. **TypeScript 5.9.3, not 7.0**: typescript-eslint 8.74 supports TS below 6.1 only. Vite 8,
Tailwind CSS 4 (tokens live in CSS `@theme`, so there is no JS config), TanStack Query 5, React Router 7 in declarative mode.
Tests use **httpx2**, because Starlette 1.x's TestClient deprecates plain httpx.
Context / Alternatives / Tradeoffs / Revisit when: _to be written (BUILD_PROMPT §8.1)._

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
**Decision:** Every CSV row is stored verbatim in `raw_rows` (JSONB), clean tables point back via `raw_row_id`, and
every excluded, corrected or flagged row gets a `data_issues` row with its trap ID. Full traceability; the storage duplication
is trivial at this size. _Full write-up to come (§8.3)._

## ADR-004 Pure planning engine, computed on request
**Decision:** `planning/` takes dataclasses and returns dataclasses (no DB, clock or I/O) and runs per request. That takes
milliseconds for about 30 items × 182 days. At thousands of items, move to a nightly precompute into `plan_results`.
**Implemented 2026-11-26 (Phase 4):** `services/planning_inputs.inputs_from_db`. The BlueTide (clean-layer) inputs are cached in
memory per latest load run id (they only change when the loader runs). Dana's app-layer edits are read fresh on every request,
so an edit shows up immediately. The dashboard takes about 50 ms warm on the test database. _Full write-up to come (§8.4)._

## ADR-005 Forecast = recent level × category monthly seasonality
**Decision:** It mirrors Dana's mental model ("October is slow, December won't be"), and it is robust to censored demand and
one-offs. Limits: one year of data, monthly granularity, no trend detection.
**Implemented 2026-11-26 (Phase 3):** `planning/seasonality.py` + `planning/demand.py`. Shrimp comes out 1.5× in Nov–Dec and Groundfish 1.4× in Feb and 2.0× in Mar (Lent), matching what Dana described. _Full write-up to come (§6.7)._

## ADR-006 Conservative lead times and ETA re-derivation
**Decision:** Use the upper end of Dana's ranges. Never trust a BlueTide PO date earlier than the real lead time allows.
A stockout costs more than overstock. See also A18 (late means on or before AS_OF).
**Updated 2026-11-26 (Dana's reply, A03):** a late PO is no longer assumed to arrive in 7 days. It is **not counted as
coming** until Dana types a real date, stays flagged, and items that only a late PO would cover are called out. This is
even more conservative than the original rule, and it's what the customer asked for. The knob is
`late_po_assumed_days` (None = don't count). _Full write-up to come (§6.5, §6.6)._

## ADR-007 Sellable definition, and what is shown but not counted
**Decision:** Sellable means latest snapshot, sellable location, qty > 0, not expired, active item, plus negative ADJ lines.
On hold, damaged, expired and legacy stock is shown separately and never added in. _Full write-up to come (§6.1)._

## ADR-008 Dana's knowledge stored separately from BlueTide data
**Decision:** App-layer tables (`vendor_settings`, `item_settings`, `po_eta_overrides`, `handled_flags`) are never
truncated by the loader. The UI shows "BlueTide says / you say", and every change is audited. _Full write-up to come (§8.3)._

## ADR-009 Statuses and "order at least"
**Decision:** Order-up-to logic with lost-sales flooring before the new order arrives. Explainable rather than statistically
optimal. Container and minimum-order rounding is deferred to P1.
**Implemented 2026-11-26:** the shortage message ends when stock really comes back. That's an earlier PO if one lands first (SHR-1620: Dec 10 → Jan 25, not the new order's Feb 8). When ordering today can't close the gap, the explanation says so instead of showing a confusing "order at least 0". _Full write-up to come (§6.8, §6.9)._

## ADR-010 Four-layer logging
**Decision:** (1) JSON app logs plus `request_log`/`event_log`, (2) `load_runs` + `data_issues` + DATA_LOAD_REPORT,
(3) `audit_log` in the same transaction as every write, (4) `docs/PROMPT_LOG.md`. **Decided by:** Ishan ("log everything"); Claude proposed the four layers. _Full write-up to come (§10)._

## ADR-011 No auth in v1
**Decision:** Fictional data and a single user. The `X-Actor` header (default "Dana") feeds the audit trail. _Full write-up to come._

## ADR-012 Plan in each item's selling unit, with a human-verified pack-size table
**Decision:** Every item is planned in its own `sell_uom` (CS or LB). Conversions use `data/reference/pack_sizes.csv`,
and a regex is used only to validate that table, never at runtime. _Full write-up to come (§6.3)._

## ADR-013 Demand dated by order date; open orders deducted by ship date
**Decision:** See A11. This is slightly early (conservative) for pre-booked orders.
**Changed 2026-11-26 (Ishan, A23): open orders are counted once.** They are deducted on their ship date and no longer also feed
the selling rate. Every past order shipped within 3 days, but this week's open orders are holiday pre-bookings, so counting
them in the rate as well double-counted December. It inflated SHR-1620's rate 47% and moved the holiday bump into November.
Holiday protection comes from the December seasonal index (shrimp 1.6×), the real 12-week lead time and order-by dates,
not from double counting. SHR-1620 is still too late (Dec 14), planning 542 cs for December vs last December's ~487 cs pace.
Extra margin, if wanted, comes from the per-item cushion. Switch: `open_orders_in_selling_rate`. _Full write-up to come (§6.2)._

## ADR-014 Exclusions by rule and seed data, not hard-coded names
**Decision:** Transfers are excluded by customer type INTERNAL, and one-offs by `data/reference/excluded_orders.csv`
(so if the cruise line returns, its new orders count). _Full write-up to come (§6.2)._

## ADR-015 Alembic migrations + RLS on with no policies; all access via the API
**Decision:** RLS on every table with no policies blocks Supabase's auto-generated Data API. The backend connects as
the postgres role through the session pooler. _Full write-up to come (§8.3)._

## ADR-016 Category-level seasonality with clamping
**Decision:** Monthly indices per normalized category from active items only, clamped to [0.4, 2.5]. Single-item
categories (Squid, Scallops) are noisy; shrinkage toward the overall index is a future step.
**Refined 2026-11-26 (A26):** a category's rate is summed **in pounds** (case items × verified lb per case). Groundfish (pollock blocks in lb, cod in cases) and Salmon (sides in lb, portions in cases) mix units; summing raw rates as §6.7 literally says would let the pound items set the pattern. _Full write-up to come (§6.7)._

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

**Decision.** The database and loader keep exact `NUMERIC`/`Decimal` quantities and money. The planning engine converts to
float at its boundary (`services/planning_inputs.py`), because rates, seasonal indices and forecasts are estimates by
nature. "Order at least" and shortfalls are rounded **up** with a 1e-9 tolerance, so 259.9999999 isn't shown as 260 and
260.0000001 doesn't become 261. Display rounds to whole cases/pounds.

**Tradeoffs.** No exact-decimal guarantees inside forecasts, which is irrelevant at this precision. Tests compare with
`pytest.approx`.

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

## ADR-026 Direction: the app becomes the main record for POs and shipments
**Date:** 2026-11-26 · **Decided by:** Ishan · **Status:** direction decided; the design (Phase 6) is waiting for "go"

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

## ADR-027 Dana's own records, matched with BlueTide's by document and quantity (rules R1-R6)
**Date:** 2026-11-26 · **Decided by:** Ishan (plan approved, with "independent of BlueTide"); design by Claude after
a design review

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

## ADR-028 Orders going out and stock moves: a ledger of picks, matched with BlueTide's orders (R7-R10)
**Date:** 2026-11-26 · **Decided by:** Ishan (Phase 6 plan, step 2 "go"); design by Claude

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

## ADR-029 Imports from the website: check first, then load; BlueTide's files or Dana's own templates
**Date:** 2026-11-26 · **Decided by:** Ishan (Phase 6 plan, step 3 "go"; "it should be able to be its own independent
system"); design by Claude after the design review

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
