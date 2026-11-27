# CLAUDE.md: Kestrel Bay ordering app

**Full context lives in `BUILD_PROMPT.md`. Read it at the start of every session.** This file is the short version,
and where they differ this file and `docs/DECISIONS.md` win (later decisions by Ishan).

## Project
Nammu take-home for Ishan Soni. A small web app for Dana Okafor (VP Purchasing, Kestrel Bay Seafood, a frozen seafood
distributor) that **replaces her Monday spreadsheet**. Every Monday she uploads BlueTide's exports, everything
recalculates, and the app answers two questions (on any day: "today" is Boston's calendar date, ADR-034):
- **what will run out before a new order can arrive;**
- **what is she stuck with** (stock inside the six-month line, or long stock at Harbor).

It counts only sellable stock and real demand, every number drills down to its source rows, and Dana can tell it what
it doesn't know (lead times, PO dates, "I've handled this", cases per pallet). **BlueTide stays the system of record**
(ADR-032).

Stack: FastAPI + SQLAlchemy + Alembic (Python 3.12) → Supabase Postgres; React + Vite + TypeScript (strict). The
website and the API run in one Vercel project (two services). Ishan decides; Claude implements, explains and flags.

## After every prompt from Ishan
**Append an entry to `docs/PROMPT_LOG.md` before your final message** (format in BUILD_PROMPT §13.2). No exceptions,
including tiny prompts, no-op prompts and prompts where you made a mistake. Log AI mistakes honestly.

## Working rules (BUILD_PROMPT §0)
- Phases with STOP points (§14). Post a plan at the start of each phase and wait for "go".
- Never invent or silently change a business rule. If something is ambiguous, ask. If you must proceed, pick the
  **conservative** option (a stockout is less likely), record it in `docs/ASSUMPTIONS.md`, and tell Ishan.
- Never tune logic to match the answer key (§7). Explain differences instead.
- Small conventional commits (`feat(loader): …`, `fix(planning): …`, `test: …`, `docs: …`). Never commit `.env`.
- Prove it works: run `pytest`, `ruff`, `npm run build` and `npm run lint`, and paste the key output.
- Every find-and-replace edit asserts that it matched (the formatter reshapes code; an unchecked edit fails silently).

## Boundaries (Ishan, ADR-032; never break these)
1. **BlueTide owns every fact** (stock, sales, POs, receipts). Facts come only from uploaded BlueTide files; the app
   never records a transaction.
2. **The app stores only Dana's knowledge and the logs.**
   - Knowledge: `vendor_settings`, `item_settings` (including cases per pallet), `po_eta_overrides`, `handled_flags`,
     `harbor_storage_rows`.
   - Logs: `uploads`, `upload_files`, `load_runs`, `data_issues`, `audit_log`, `event_log`, `request_log`.
3. **Each upload refreshes BlueTide's data.** Stock, open POs, items, suppliers and customers come from the latest
   upload. Sales lines **accumulate** (merged by order + line; the new file wins; A50).
4. **"Today" is Boston's calendar date** (ADR-034, superseding "today follows the data"). It's read on the server,
   in one place (`config/clock.business_today`, `America/New_York`), never in the browser.
   - The **data date** = the latest successful load's stock count + 1 day (`rules.data_date`, the projection's day 0;
     2026-11-16 with the current data). What the upload knows is measured to it (selling rate, season, late POs).
     Deadlines, statuses, expiry and Dana's dates are judged against today.
   - Between the two, stock is **estimated** and always shown next to the count. POs due since the upload, PO dates
     that have passed and handled notes whose date has passed are **not counted** (A53–A54, A25).
   - A load describes its own files as of their data date (`rules_for_load`).
   - `AS_OF_DATE` overrides today for the whole server (tests, a fixed demo). `X-As-Of` / `?as_of=` (the header's
     "View as of") shows a day between the data date and today.
5. **The math is deterministic, with no LLM anywhere.** Every number traces back to an uploaded row.
6. **No order entry, receiving, shipping, stock moves, or adding customers, items or suppliers in the app.** That
   was Phase 6, cut by ADR-032 and archived on the git tag `archive/system-of-record`.

## Invariants (never break these)
1. **Business dates come from the request's rules (boundary 4), never a bare clock call.** `config/clock.py` is the
   only place a business date is read from the clock (Boston); everything else takes `rules.as_of_date` (today, or the
   viewed day) and `rules.day_zero` (the data date). Log and audit timestamps use real UTC.
2. **Never modify `data/raw/` or `kestrel-bay/`.** `kestrel-bay/` is the original zip, kept for reference.
   `data/raw/bluetide_*.csv` are byte-identical working copies (`shasum -a 256 -c data/raw_checksums.sha256`).
   All cleaning happens in code, and every change is logged to `data_issues`.
3. **Business numbers live only in `backend/app/config/business_rules.py` and `data/reference/*.csv`.** No magic
   numbers elsewhere. Every load stores a copy of `data/reference/*.csv` on its load run; the website's import uses the
   last copy (ADR-029).
4. **No hard-coded item, order, customer or vendor codes in logic.** Use seeds (`data/reference/`) or
   customer_type/vendor_type.
5. **The loader never truncates app-layer tables** (`vendor_settings`, `item_settings`, `po_eta_overrides`,
   `handled_flags`, `harbor_storage_rows`, `uploads`, `upload_files`; `APP_LAYER` in models.py). They never get
   foreign keys into BlueTide's tables. Vendor settings seeds are inserted only if missing. Raw rows and data notes are
   kept for the newest `raw_rows_keep_loads` (8) loads; load-run summaries forever (A51).
6. Read raw CSVs as strings. They are CRLF. Use `Decimal`/numeric for quantities and money, and `date` for business
   dates.
7. Trap IDs (T01–T31) and golden facts (G01–G17) appear in code comments, test names and `docs/DATA_AUDIT.md`.

## Where things are
```
BUILD_PROMPT.md              spec (source of truth, overridden where DECISIONS / this file say so)
kestrel-bay/                 ORIGINAL client zip, untouched
docs/client/                 ASSIGNMENT.md, KICKOFF_TRANSCRIPT.md, email-to-dana.md, dana-replies.md
docs/                        PROMPT_LOG, DECISIONS (ADRs), ASSUMPTIONS, DATA_AUDIT, DATA_LOAD_REPORT, DEMO_SCRIPT, PRIORITIES,
                             images/ (README screenshots)
data/raw/bluetide_*.csv      working copies of the 7 BlueTide exports (the laptop loader reads these)
data/reference/*.csv         human-maintained seeds (pack sizes, lead times, locations, stockouts, excluded orders)
backend/app/config/          settings.py (env; AS_OF_DATE is an optional override), business_rules.py (ALL tunable numbers;
                             rules_for(count, today) / rules_for_load; server_today), clock.py (Boston's date, ADR-034)
backend/app/loader/          read_raw → rules (T01..T31) → normalize/classify/convert → write (one transaction; retention)
                             → report; accumulate (sales history merge), history (read an earlier load's rows back)
backend/app/planning/        PURE engine (no DB/clock/I/O): seasonality, demand, supply, projection, ordering, stuck,
                             explain (numbers-only breakdown + the late-PO instruction; ADR-033), storage (Harbor pallets
                             and $), calendar (add_months, Easter, season bands)
backend/app/services/        planning_inputs (DB → engine inputs: BlueTide cached per load + Dana's knowledge fresh),
                             planning_service (plan, item page, On the way), presenters (→ DTOs), import_service (weekly
                             uploads: check, then load), export_service (CSV downloads), harbor_service, health_service,
                             audit (audit rows in the same transaction, request_log, event_log)
backend/app/api/             deps.py (request_rules: today, or the X-As-Of view, for this request); v1/ routers: health, items (dashboard,
                             drill-down, handled notes, item settings), suppliers (vendors, real PO dates),
                             purchase_orders (On the way, read only), imports (upload, check, load), exports (CSV),
                             harbor (storage cost, saved table), activity (data notes, audit, events, load runs, settings);
                             schemas.py; docs at /api/v1/docs
backend/tests/               unit/ (per trap, engine, merge, calendar), golden/ (real data: G01–G17, chart reconciliation),
                             api/ (SQLite copy of the real data)
frontend/src/                api/ (client, types mirroring schemas.py, queries.ts = one hook per endpoint + edits)
                             pages/ (Monday, Item, OnTheWay, LeadTimes = Suppliers, Harbor, Data, DataNotes, Activity),
                             components/ (OrderRow, StatusGroup, RunwayBar, DownloadLink, ProjectionChart, StuckList,
                             SetPoDate, MarkHandledDialog, ImportPanel, Term = hover glossary, ...),
                             lib/ (dates, format, names, actor, reportError), styles/ (§9.1 tokens)
scripts/                     profile_data.py (independent fact check), compare_answer_key.py (engine vs §7),
                             set_database_password.py, check_cron.py (Vercel's daily cron, logged as actor "Vercel cron")
```

## Commands
```bash
# Backend (Python 3.12.12: /opt/homebrew/bin/python3.12)
cd backend && /opt/homebrew/bin/python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env                # paste the Supabase *session pooler* URL (port 5432) into DATABASE_URL
python3 ../scripts/set_database_password.py   # puts the password in safely (hidden, URL-encoded)
alembic upgrade head                # create/upgrade tables (RLS on every table)
python -m app.loader.run            # load data/raw (~2 min from a laptop; merges sales with the stored history; the data
                                    #  date = the files' stock count + 1; writes docs/DATA_LOAD_REPORT.md; stores the seeds the
                                    #  website's import uses). Weekly, Dana uploads on /data instead
python -m app.loader.run --dry-run  # run every rule + write the report, touch no database (no history merge)
uvicorn app.main:app --reload       # API docs: http://localhost:8000/api/v1/docs
pytest                              # all tests; never touches the real DB (API tests use a SQLite copy of the real data, ADR-023)
ruff check . && ruff format --check .
python ../scripts/check_cron.py     # when Vercel's daily cron last called the API

# Frontend (Node >= 22.12)
cd frontend && npm install
npm run dev                         # http://localhost:5173 (proxies /api to the API on :8000)
npm run build && npm run lint && npm run format:check

# Raw data integrity + independent re-check of the audit facts (from the repo root; system python3 is fine)
shasum -a 256 -c data/raw_checksums.sha256
python3 scripts/profile_data.py
```

## Deploy (ONE Vercel project, two services; ADR-002)
- The repo-root `vercel.json` declares Vercel **Services** (beta): `web` = `frontend/` (Vite) and `api` = `backend/`
  (FastAPI, entrypoint `app.main:app`). `/api/*` goes to the API **with the path intact**; everything else goes to the
  website, which falls back to index.html for deep links. Same domain (https://nammu-ai.vercel.app), so no CORS and
  no API-URL variable.
- Project settings: Root Directory = repo root (empty). Env vars: `DATABASE_URL` = Supabase **transaction pooler**
  (port 6543), `APP_ENV=production`. **No `AS_OF_DATE`** (it would freeze "today"). Vite only exposes `VITE_*` vars to
  the browser, so the DB URL never reaches the bundle.
- `vercel.json` also pins region iad1 (next to Supabase us-east-1) and a daily cron on /api/v1/health so Supabase never
  pauses.
- Locally, `npm run dev` proxies `/api` to uvicorn on :8000 (vite.config.ts): same relative URLs as production.
- Migrations and the laptop loader run through the **session pooler (5432)**, never on deploy. Order matters: an
  additive migration runs before the push; a migration that drops something runs after the new code is live.
- **Never add a `backend/pyproject.toml` without a `[project]` table** (Vercel would ignore requirements.txt), and keep a
  single `vercel.json` at the root. Both are guarded by tests/unit/test_deploy_config.py.

## Live-change playbook (BUILD_PROMPT §17)
| Likely request | Where to change |
|---|---|
| "Pretend today is a different day" | A day between the data date and today: the header's **View as of** (this tab only; `X-As-Of`). A day past today, or for the whole server: set `AS_OF_DATE` (Vercel → Settings → Environment Variables, then redeploy; locally `backend/.env`) and remove it afterwards |
| "Ask for the upload sooner or later" | `stale_data_days` (yellow banner) and `very_stale_data_days` (red) in `business_rules.py` |
| "Run in another time zone" | `business_timezone` in `business_rules.py` (tests in `tests/unit/test_config.py`) |
| "Change how stock between the count and today is estimated" | `planning/projection.build_scenario` (`stock_now`) and `engine.py`; the bridge rows in `explain.breakdown`; pinned by `tests/golden/test_reconciliation.py` and `tests/unit/planning/test_real_calendar.py` |
| "Count QA-HOLD as available" or "add a location" | `data/reference/locations.csv` (+ a laptop load) or the `locations` table. For a toggle, add a param to `planning/supply.py` |
| "Change the six-month line, cushion, thresholds" | `backend/app/config/business_rules.py` |
| "Keep more (or fewer) loads' raw rows" | `raw_rows_keep_loads` in `business_rules.py` |
| "Exclude another order or customer type" | `data/reference/excluded_orders.csv` or the classifier order in `loader/classify.py` |
| "Show a new number on the dashboard" | Engine output (`planning/types.py`) → DTO (`api/v1/schemas.py`) → component |
| "Add a row to the item's why" | `planning/explain.breakdown` (a `BreakdownRow` with a `link` to its table) + a test in `tests/api/test_breakdown.py` |
| "Change the late-PO instruction" | `planning/explain.late_po_instruction` (Ishan's wording; tests pin it) |
| "Add a column to a download" or "a new download" | `services/export_service.py` (header + row, plus `EXPORTS` for a new one), then `<DownloadLink list=...>` on the page |
| "Different cushion for one item" | `item_settings.safety_days_override` (already supported) |
| "Change what blocks an upload" | `services/import_service._check_bluetide` (blockers vs warnings) |
| "Merge sales history differently" | `loader/accumulate.merge_sales` / `sales_key` (+ `tests/unit/loader/test_accumulate.py`) |
| "Filter by vendor or category" | Frontend only. The dashboard already returns vendor and category |
| "Change the Harbor rate" or "how pallets are counted" | Rate: `harbor_pallet_cost_per_month` in `business_rules.py`. Pallets: `planning/storage.pallets_needed` (+ `palletsFor` preview in `HarborPage.tsx`) |
| "Let Dana enter a PO / receive / ship in the app" | Not a small change: it breaks boundary 1 (ADR-032). The old code is on `archive/system-of-record`; see the README's "Roadmap off BlueTide" |

Each row should be a small, tested change.

## Decisions already made by Ishan (beyond BUILD_PROMPT)
- Frontend is **TypeScript** (strict).
- Client files are **copied** (originals in `kestrel-bay/`, committed). Copies have distinct names (`bluetide_*.csv`,
  `ASSIGNMENT.md`, `KICKOFF_TRANSCRIPT.md`).
- A PO whose re-derived ETA is **on or before** the data date counts as late (`<=`, not `<`), so PO-260407 is late
  (A18). Due after it but by today: "due since your last upload", not counted (A54).
- **Real calendar (Ishan, 2026-11-26/27, ADR-034):** today is Boston's date. Ishan's four answers were:
  - show both the count and the estimate;
  - don't count POs due since the count;
  - red, new statuses: **Out of stock** and **Overdue**;
  - a "View as of" switch, which keeps the assignment's Nov 16 reviewable.

  Ishan also chose to stop counting handled notes whose date has passed (A25). Stale banners show after 7 and 14 days.
- **Dana's reply (2026-11-26, docs/client/dana-replies.md):** every email default was confirmed EXCEPT late POs. They
  are **not counted as coming** until she types a real date (`late_po_assumed_days = None`), and items only a late PO
  would cover must be called out. BUILD_PROMPT §6.6 / §7 still describe the old "+7 days" rule; this overrides it.
  Harbor costs $30/pallet/month.
- **Late / unknown inventory is its own bucket** (Ishan + Dana, ADR-021): late POs and QA-HOLD are shown, never counted;
  status uses confirmed supply only; a best-case "if the late PO arrives" run flags items *covered only by a late PO*,
  and those get **one instruction** (ADR-033).
- **Priorities live in `docs/PRIORITIES.md`.** P0 is done, and so is P1 #1 (the Harbor calculator, ADR-031). A chat
  assistant is P2, and could only explain, never compute (boundary 5).
- **Open orders are counted once** (Ishan 2026-11-26, A23): deducted on their ship date, NOT added to the selling rate
  (`open_orders_in_selling_rate = False`; BUILD_PROMPT §6.2 said both). Holiday caution comes from seasonality and the
  cushion.
- **Screens (Ishan, 2026-11-26, ADR-025):**
  - traffic lights only: red = out of stock, too late, overdue (and expired / inside the six-month line); yellow =
    order this week / order soon (and stopped selling, long at Harbor, overstock); green = fine; grey = handled; no
    blue;
  - each item on Monday is a card in a dropdown group;
  - units spelled out ("cases", not "cs");
  - the "why" is numbers, not sentences (ADR-033).
- **BlueTide stays the record (Ishan's scope review, 2026-11-26, ADR-032).** ADR-026 ("the app becomes the system of
  record") is **superseded**, and ADR-027/028 with it. The Phase 6 record-keeping (POs, receipts, shipments, picks,
  moves, her own items, suppliers, stock counts, templates) was cut by migration 0006 and archived on the tag
  `archive/system-of-record`. Weekly BlueTide uploads (ADR-029, narrowed), CSV downloads and the Harbor calculator stay.
  Moving off BlueTide is a README roadmap item: one job at a time, each record owned by one system.
- **One Vercel project hosts both the website and the API** (Vercel Services), not Render + Vercel (2026-11-25,
  ADR-002). BUILD_PROMPT §8.1/§15 still say Render; this overrides it.
