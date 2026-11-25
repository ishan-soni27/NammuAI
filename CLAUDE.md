# CLAUDE.md: Kestrel Bay ordering app

**Full context lives in `BUILD_PROMPT.md`. Read it at the start of every session.** This file is the short version.

## Project
Nammu take-home for Ishan Soni. We're building a small web app for Dana Okafor (VP Purchasing, Kestrel Bay Seafood, a
frozen seafood distributor) that answers two questions on Monday morning: **what will run out before a new order can
arrive, and what is she stuck with** (stock inside the six-month line, or long stock at Harbor). It counts only sellable
stock and real demand, every number drills down to its source rows, and Dana can tell it what it doesn't know (lead
times, PO dates, "I've handled this"). Stack: FastAPI + SQLAlchemy + Alembic (Python 3.12) → Supabase Postgres;
React + Vite + TypeScript (strict) → Vercel; API on Render. Ishan decides; Claude implements, explains and flags.

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
backend/app/services/        DB → engine inputs → DTOs; audit + event writers
backend/app/api/v1/          FastAPI routers + Pydantic schemas (prefix /api/v1, OpenAPI at /docs)
backend/tests/               unit/ (per trap), golden/ (real data, G01–G17), api/
frontend/src/                api/ pages/ components/ lib/ styles/
scripts/                     profile_data.py, compare_answer_key.py
```

## Commands
```bash
# Backend (Python 3.12.12: /opt/homebrew/bin/python3.12)
cd backend && /opt/homebrew/bin/python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env                # then paste the Supabase *session pooler* URL into DATABASE_URL
alembic upgrade head                # create/upgrade tables (RLS on every table)
python -m app.loader.run            # one-time load (idempotent for the clean layer)  [Phase 2]
uvicorn app.main:app --reload       # http://localhost:8000/docs
pytest                              # all tests (never touches the real DB; see tests/conftest.py)
ruff check . && ruff format --check .

# Frontend (Node >= 22.12)
cd frontend && npm install
cp .env.example .env.local          # VITE_API_BASE_URL=http://localhost:8000/api/v1
npm run dev                         # http://localhost:5173
npm run build && npm run lint && npm run format:check

# Raw data integrity (any time)
shasum -a 256 -c data/raw_checksums.sha256
```

## Deploy
- API: Render Blueprint from `render.yaml` (root `backend`, health check `/api/v1/health`). Secrets: `DATABASE_URL`, `CORS_ORIGINS`.
- Web: Vercel, root `frontend`, env `VITE_API_BASE_URL=<render url>/api/v1`. `frontend/vercel.json` rewrites deep links to index.html.
- Migrations run from a laptop (`alembic upgrade head`), not on deploy.

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
- A PO whose re-derived ETA is **on or before** AS_OF counts as late (`<=`, not `<`), so PO-260407 gets ETA Nov 23 (A18).
