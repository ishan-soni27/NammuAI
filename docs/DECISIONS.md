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

## ADR-002 Hosting: Render (API) + Vercel (web) + Supabase (DB)
**Decision:** Long-running uvicorn on Render's free tier, static Vite build on Vercel, managed Postgres on Supabase.
Cold starts are mitigated by a keep-warm ping and a "waking up" UI state. The all-on-Vercel serverless option was rejected.
**Decided by:** Claude proposed, Ishan approved. The Render service is defined in `render.yaml` (a Blueprint) rather than
configured by hand, so the settings live in the repo. Migrations run from a laptop, not on deploy: Render's free tier has
no pre-deploy hook, and running them in the build step would migrate on every push. `/health` always returns 200 and
*reports* database trouble, so Render's health check never restarts a healthy API while Supabase wakes up.
_Full write-up to come (§8.1, §15)._

## ADR-003 Raw JSONB layer + clean tables + data_issues
**Decision:** Every CSV row is stored verbatim in `raw_rows` (JSONB), clean tables point back via `raw_row_id`, and
every excluded, corrected or flagged row gets a `data_issues` row with its trap ID. Full traceability; the storage duplication
is trivial at this size. _Full write-up to come (§8.3)._

## ADR-004 Pure planning engine, computed on request
**Decision:** `planning/` takes dataclasses and returns dataclasses (no DB, clock or I/O) and runs per request. That takes
milliseconds for about 30 items × 182 days. At thousands of items, move to a nightly precompute into `plan_results`. _Full write-up to come (§8.4)._

## ADR-005 Forecast = recent level × category monthly seasonality
**Decision:** It mirrors Dana's mental model ("October is slow, December won't be"), and it is robust to censored demand and
one-offs. Limits: one year of data, monthly granularity, no trend detection. _Full write-up to come (§6.7)._

## ADR-006 Conservative lead times and ETA re-derivation
**Decision:** Use the upper end of Dana's ranges. Never trust a BlueTide PO date earlier than the real lead time allows.
A stockout costs more than overstock. See also A18 (late means on or before AS_OF). _Full write-up to come (§6.5, §6.6)._

## ADR-007 Sellable definition, and what is shown but not counted
**Decision:** Sellable means latest snapshot, sellable location, qty > 0, not expired, active item, plus negative ADJ lines.
On hold, damaged, expired and legacy stock is shown separately and never added in. _Full write-up to come (§6.1)._

## ADR-008 Dana's knowledge stored separately from BlueTide data
**Decision:** App-layer tables (`vendor_settings`, `item_settings`, `po_eta_overrides`, `handled_flags`) are never
truncated by the loader. The UI shows "BlueTide says / you say", and every change is audited. _Full write-up to come (§8.3)._

## ADR-009 Statuses and "order at least"
**Decision:** Order-up-to logic with lost-sales flooring before the new order arrives. Explainable rather than statistically
optimal. Container and minimum-order rounding is deferred to P1. _Full write-up to come (§6.8, §6.9)._

## ADR-010 Four-layer logging
**Decision:** (1) JSON app logs plus `request_log`/`event_log`, (2) `load_runs` + `data_issues` + DATA_LOAD_REPORT,
(3) `audit_log` in the same transaction as every write, (4) `docs/PROMPT_LOG.md`. **Decided by:** Ishan ("log everything"); Claude proposed the four layers. _Full write-up to come (§10)._

## ADR-011 No auth in v1
**Decision:** Fictional data and a single user. The `X-Actor` header (default "Dana") feeds the audit trail. _Full write-up to come._

## ADR-012 Plan in each item's selling unit, with a human-verified pack-size table
**Decision:** Every item is planned in its own `sell_uom` (CS or LB). Conversions use `data/reference/pack_sizes.csv`,
and a regex is used only to validate that table, never at runtime. _Full write-up to come (§6.3)._

## ADR-013 Demand dated by order date; open orders deducted by ship date
**Decision:** See A11. This is slightly early (conservative) for pre-booked orders. _Full write-up to come (§6.2)._

## ADR-014 Exclusions by rule and seed data, not hard-coded names
**Decision:** Transfers are excluded by customer type INTERNAL, and one-offs by `data/reference/excluded_orders.csv`
(so if the cruise line returns, its new orders count). _Full write-up to come (§6.2)._

## ADR-015 Alembic migrations + RLS on with no policies; all access via the API
**Decision:** RLS on every table with no policies blocks Supabase's auto-generated Data API. The backend connects as
the postgres role through the session pooler. _Full write-up to come (§8.3)._

## ADR-016 Category-level seasonality with clamping
**Decision:** Monthly indices per normalized category from active items only, clamped to [0.4, 2.5]. Single-item
categories (Squid, Scallops) are noisy; shrinkage toward the overall index is a future step. _Full write-up to come (§6.7)._

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
