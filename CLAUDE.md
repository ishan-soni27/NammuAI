# CLAUDE.md: Kestrel Bay ordering app

**Full context lives in `BUILD_PROMPT.md`. Read it at the start of every session.** This file is the short version.

## Project
Nammu take-home for Ishan Soni. We're building a small web app for Dana Okafor (VP Purchasing, Kestrel Bay Seafood, a
frozen seafood distributor) that answers two questions on Monday morning: **what will run out before a new order can
arrive, and what is she stuck with** (stock inside the six-month line, or long stock at Harbor). It counts only sellable
stock and real demand, every number drills down to its source rows, and Dana can tell it what it doesn't know (lead
times, PO dates, "I've handled this"). Stack: FastAPI + SQLAlchemy + Alembic (Python 3.12) → Supabase Postgres;
React + Vite + TypeScript (strict). The website and the API run in one Vercel project (two services). Ishan decides;
Claude implements, explains and flags.

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

## Invariants (never break these)
1. **Today is `AS_OF_DATE` (2026-11-16, env-configurable), never the system clock**, for any business date. Log and audit timestamps use real UTC.
2. **Never modify `data/raw/` or `kestrel-bay/`.** `kestrel-bay/` is the original zip, kept for reference.
   `data/raw/bluetide_*.csv` are byte-identical working copies (`shasum -a 256 -c data/raw_checksums.sha256`).
   All cleaning happens in code, and every change is logged to `data_issues`.
3. **Business numbers live only in `backend/app/config/business_rules.py` and `data/reference/*.csv`.** No magic numbers elsewhere.
4. **No hard-coded item, order, customer or vendor codes in logic.** Use seeds (`data/reference/`) or customer_type/vendor_type.
5. **The loader never truncates app-layer tables** (`vendor_settings`, `item_settings`, `po_eta_overrides`, `handled_flags`).
   Vendor settings seeds are inserted only if missing.
6. Read raw CSVs as strings (`dtype=str, keep_default_na=False`). They are CRLF. Use `Decimal`/numeric for quantities and money, and `date` for business dates.
7. Trap IDs (T01–T31) and golden facts (G01–G17) appear in code comments, test names and `docs/DATA_AUDIT.md`.

## Where things are
```
BUILD_PROMPT.md              spec (source of truth)
kestrel-bay/                 ORIGINAL client zip, untouched
docs/client/                 ASSIGNMENT.md, KICKOFF_TRANSCRIPT.md, email-to-dana.md, dana-replies.md
docs/                        PROMPT_LOG, DECISIONS (ADRs), ASSUMPTIONS, DATA_AUDIT, DATA_LOAD_REPORT, DEMO_SCRIPT
data/raw/bluetide_*.csv      working copies of the 7 BlueTide exports (loader reads these)
data/reference/*.csv         human-maintained seeds (pack sizes, lead times, locations, stockouts, excluded orders)
backend/app/config/          settings.py (env), business_rules.py (ALL tunable numbers)
backend/app/loader/          one-time CSV load: read_raw → rules (T01..T31) → normalize/classify/convert → write → report
backend/app/planning/        PURE engine (no DB/clock/I/O): seasonality, demand, supply, projection, ordering, stuck, explain
backend/app/services/        planning_inputs (DB → engine inputs, cached per load), planning_service, presenters (→ DTOs),
                             audit (audit rows in the same transaction, request_log, event_log)
backend/app/api/v1/          routers: health, items (dashboard/drill-down/handled/settings), suppliers (vendors, PO dates),
                             activity (data notes, audit, events, load runs, settings); schemas.py; docs at /api/v1/docs
backend/tests/               unit/ (per trap), golden/ (real data, G01–G17), api/
frontend/src/                api/ pages/ components/ lib/ styles/
scripts/                     profile_data.py (independent fact check), compare_answer_key.py (engine vs §7), set_database_password.py
```

## Commands
```bash
# Backend (Python 3.12.12: /opt/homebrew/bin/python3.12)
cd backend && /opt/homebrew/bin/python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env                # paste the Supabase *session pooler* URL (port 5432) into DATABASE_URL
python3 ../scripts/set_database_password.py   # puts the password in safely (hidden, URL-encoded)
alembic upgrade head                # create/upgrade tables (RLS on every table)
python -m app.loader.run            # load BlueTide CSVs (~2 min from a laptop; safe to re-run; writes docs/DATA_LOAD_REPORT.md)
python -m app.loader.run --dry-run  # run every rule + write the report, touch no database
uvicorn app.main:app --reload       # API docs: http://localhost:8000/api/v1/docs
pytest                              # all tests; never touches the real DB (API tests use a SQLite copy of the real data, ADR-023)
ruff check . && ruff format --check .

# Frontend (Node >= 22.12)
cd frontend && npm install
npm run dev                         # http://localhost:5173 (proxies /api to the API on :8000)
npm run build && npm run lint && npm run format:check

# Raw data integrity + independent re-check of the audit facts (any time, system python3 is fine)
shasum -a 256 -c data/raw_checksums.sha256
python3 scripts/profile_data.py
```

## Deploy (ONE Vercel project, two services; ADR-002)
- The repo-root `vercel.json` declares Vercel **Services** (beta): `web` = `frontend/` (Vite) and `api` = `backend/`
  (FastAPI, entrypoint `app.main:app`). `/api/*` goes to the API **with the path intact**; everything else goes to the
  website, which falls back to index.html for deep links. Same domain (https://nammu-ai.vercel.app), so no CORS and
  no API-URL variable.
- Project settings: Root Directory = repo root (empty). Env vars: `DATABASE_URL` = Supabase **transaction pooler**
  (port 6543), `APP_ENV=production`. Vite only exposes `VITE_*` vars to the browser, so the DB URL never reaches the bundle.
- `vercel.json` also pins region iad1 (next to Supabase us-east-1) and a daily cron on /api/v1/health so Supabase never pauses.
- Locally, `npm run dev` proxies `/api` to uvicorn on :8000 (vite.config.ts): same relative URLs as production.
- Migrations and the loader run from a laptop through the **session pooler (5432)**, never on deploy. The loader
  needs it for Postgres COPY, and does everything in one transaction (ADR-020).
- **Never add a `backend/pyproject.toml` without a `[project]` table** (Vercel would ignore requirements.txt), and keep a
  single `vercel.json` at the root. Both are guarded by tests/unit/test_deploy_config.py.

## Live-change playbook (BUILD_PROMPT §17)
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

Each row should be a small, tested change. If one isn't, refactor it in Phase 6.

## Decisions already made by Ishan (beyond BUILD_PROMPT)
- Frontend is **TypeScript** (strict).
- Client files are **copied** (originals in `kestrel-bay/`, committed). Copies have distinct names (`bluetide_*.csv`, `ASSIGNMENT.md`, `KICKOFF_TRANSCRIPT.md`).
- A PO whose re-derived ETA is **on or before** AS_OF counts as late (`<=`, not `<`), so PO-260407 is late (A18).
- **Dana's reply (2026-11-26, docs/client/dana-replies.md):** every email default confirmed EXCEPT late POs. They are
  **not counted as coming** until she types a real date (`late_po_assumed_days = None`), and items only a late PO would
  cover must be called out. BUILD_PROMPT §6.6 / §7 still describe the old "+7 days" rule; this overrides it.
  Harbor costs $30/pallet/month (cases per pallet still unknown).
- **Late / unknown inventory is its own bucket** (Ishan + Dana, ADR-021): late POs and QA-HOLD are shown, never counted; status
  uses confirmed supply only; a best-case "if the late PO arrives" run flags items *covered only by a late PO*.
- **Priorities live in `docs/PRIORITIES.md`.** P0 first. Next after P0: a Harbor storage cost calculator (Dana types cases
  per pallet; $30/pallet/month; save to a table; CSV export). A chat assistant is P2 (later).
- **Open orders are counted once** (Ishan 2026-11-26, A23): deducted on their ship date, NOT added to the selling rate
  (`open_orders_in_selling_rate = False`; BUILD_PROMPT §6.2 said both). Holiday caution comes from seasonality + cushion.
- **One Vercel project hosts both the website and the API** (Vercel Services), not Render + Vercel (2026-11-25, ADR-002).
  BUILD_PROMPT §8.1/§15 still say Render; this overrides it.
