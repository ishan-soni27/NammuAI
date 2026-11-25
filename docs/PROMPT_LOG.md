# Prompt log

One entry per prompt from Ishan, newest at the bottom (BUILD_PROMPT §13.2). It records what was asked, what changed, the impact,
who decided what, and **every AI mistake, honestly**. Entries #0.1 to #0.3 happened in claude.ai before Claude Code; from #1
on, entries are written by Claude Code before its final message in each turn.

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

## #1 | 2026-11-25 11:43 UTC | Read everything and plan Phase 0 (Claude Code, plan mode)
**Prompt (simplified):** Read BUILD_PROMPT.md and all the other files, then start planning.
**What changed:** Nothing in the repo. A plan file was written in Claude Code's plan store. This entry was written late
(at the start of Phase 0) because plan mode blocks all file writes except the plan, so working agreement #7 couldn't be
followed in that turn.
**Impact:** Confirmed the reading of BUILD_PROMPT (all 1,004 lines), the transcript, the zip README and every CSV.
Independently recomputed golden facts G01, G02, G04–G09 and G11–G14 from the raw files with the stdlib `csv` module. All
match. Found that the files live in `kestrel-bay/`, not the §2 layout, and that the folder isn't a git repo. Found an edge
case: PO-260407 (calamari) re-derives to exactly AS_OF (Aug 24 + 84 days = Nov 16), so §6.6's strict `<` wouldn't flag it
late even though email Q3 told Dana it is late. Proposed a `vendor_types.csv` seed (T28 had no home without hard-coding
vendor codes). Noted MNP's CAD currency vs lot costs with no currency column.
**Decisions made (and by whom):** Ishan chose **TypeScript**. Ishan chose to **copy** the client files rather than move them,
**keep and commit the original** `kestrel-bay/`, and give the copies distinct names (`bluetide_*.csv`, `ASSIGNMENT.md`,
`KICKOFF_TRANSCRIPT.md`). Claude had recommended moving and gitignoring; Ishan preferred keeping the original for future
reference. Ishan chose **"on or before today" = late** for POs (A18). Ishan confirmed **Dana hasn't replied**, so the email defaults stand.
**AI mistakes caught or corrected:** The plan's verification step said `file` would report "with CRLF line terminators".
macOS `file` only says "CSV text", so CRLF is verified by counting CR bytes instead (CR count = line count for all 7 files).
**Follow-ups:** Execute Phase 0.

## #2 | 2026-11-25 11:43 UTC | Phase 0 approved: scaffolding, seeds and docs
**Prompt (simplified):** Approved the Phase 0 plan (with the answers above). Do it.
**What changed:**
- `git init` on `main`; `.gitignore`; `.gitattributes` (`-text` on the raw CSVs in both locations so CRLF is never rewritten).
- Byte-identical copies: `data/raw/bluetide_*.csv` (7), `docs/client/ASSIGNMENT.md`, `docs/client/KICKOFF_TRANSCRIPT.md`;
  `data/raw_checksums.sha256` (18 lines, original and copy side by side). The original `kestrel-bay/` is committed untouched.
- `docs/client/email-to-dana.md` (verbatim §4.4 + a map of each question to its seed/config), `docs/client/dana-replies.md` (empty).
- Seeds: `data/reference/{pack_sizes (45 rows), vendor_settings_seed (5), vendor_types (8, new), locations (5),
  stockout_periods (1), excluded_orders (1)}.csv` + `data/reference/README.md`.
- Empty §8.2 folder skeleton (`.gitkeep`).
- Docs: `CLAUDE.md`, `docs/DATA_AUDIT.md`, `docs/ASSUMPTIONS.md` (A01–A18), `docs/DECISIONS.md` (ADR-001–016 headings, ADR-017/018 full), `README.md` stub, this log.
**Impact:** No app behavior yet. The seeds were validated against the raw data: pack_sizes covers exactly the 45 canonical
codes, and each pack_size_raw equals the canonical item's text; every CS item outside ZZ has a factor; vendor_types covers all 8
vendors; location codes match the on-hand file. `shasum -c` passes for all 18 files.
**Decisions made (and by whom):** Claude made five commits instead of the four in the plan (the folder skeleton got its own
commit). Claude added `data/reference/README.md` (not in the plan) to explain how each seed is used and which ones the loader overwrites.
**AI mistakes caught or corrected:** While re-checking G09/G10 for DATA_AUDIT, Claude's first script included fresh lots
(FR-FLK L261104-01 is expired, and all FR lots fall inside the six-month line), because BUILD_PROMPT words those facts as
"non-legacy". Corrected by scoping G09/G10 to in-scope items (not legacy, not fresh), which is consistent with T07 and the
"78 cs expired" trust-strip total. Documented in DATA_AUDIT. This is a wording clarification, not a rule change.
**Follow-ups:** Ishan to eyeball `data/reference/pack_sizes.csv` and `vendor_settings_seed.csv` (they're marked as from
BUILD_PROMPT §6.3/§6.5, not independently verified by a person yet). Phase 1 needs: a Supabase project, a GitHub repo
(public or private?), and Render + Vercel accounts.

## #3 | 2026-11-25 12:12 UTC | GitHub repo + Supabase ready → Phase 1 walking skeleton
**Prompt (simplified):** "I've created the GitHub repo (ishan-soni27/NammuAI) and the Supabase project." Interpreted as the
go-ahead for Phase 1, since those were the two prerequisites Claude asked for.
**What changed:**
- Git: added `origin` and pushed `main` (the repo was empty and public).
- Backend: `app/main.py` (factory), `config/settings.py`, `config/business_rules.py` (all §6 numbers, each with doc + source
  metadata), `logging_setup.py` (JSON lines), `middleware.py` (request id, actor, timing, 500 safety net), `errors.py`
  (envelope), `db/models.py` (all 21 tables in §8.3), `db/session.py`, `services/health_service.py`, `api/v1/health.py`,
  `api/v1/schemas.py`. Alembic setup and migration `0001_initial_schema` (RLS on all 21 tables + alembic_version).
  Pinned `requirements*.txt`, `pyproject.toml` (pytest + ruff), `.env.example`, `.python-version`.
- Tests: 58 (health states, request id/actor, error envelope incl. CORS headers on a 500, config, invariants).
- Frontend: Vite + React 18 + TS strict + Tailwind 4 tokens + TanStack Query + React Router; header with the business
  date, status panel, loading/error/cold-start states, `vercel.json`, ESLint + Prettier.
- `render.yaml` Blueprint. CLAUDE.md commands/deploy section; DECISIONS ADR-001 (versions) and ADR-002 (deploy notes).
**Impact:** The API boots without a database and reports `db: not_configured` (no crash loop). `pytest`: 58 passed.
`ruff check` + `ruff format --check`: clean. `npm run build`, `npm run lint` and `npm run format:check`: clean. A real
uvicorn run served `/api/v1/health` and `/docs`, and a CORS preflight with X-Actor/X-Request-ID from localhost:5173 was allowed.
**Not done yet (blocked on Ishan):** the migration hasn't run against Supabase (no `backend/.env` yet), and nothing is deployed to Render or Vercel.
**Decisions made (and by whom):** Claude chose these, pending Ishan's review:
- `/health` always returns 200 and reports DB trouble instead of failing, so Render doesn't restart the API while Supabase wakes up.
- App-layer tables get no FKs into the clean layer, so a reload can't cascade-delete Dana's edits. A test enforces it.
- The 500 safety net lives in the middleware, inside CORS, so crashes reach the browser readable.
- React 18 kept per the spec; TypeScript 5.9 instead of 7.0 (typescript-eslint compatibility); httpx2 for tests.
- Migrations run from a laptop, not on deploy.
- Two numbers that were inline in the spec moved into `business_rules.py`: the 14-day late-PO window (§6.8) and the
  1–365 edit bounds (§8.5).
**AI mistakes caught or corrected:**
- Autogenerating the migration against SQLite (there's no local Postgres or Docker) rendered SQLite-flavoured defaults
  (`CURRENT_TIMESTAMP`) and an unimported `Text()`. Caught in review and hand-fixed; the offline SQL render was then checked
  (22 CREATE TABLE, 22 ENABLE RLS).
- The first `env.py` swapped the engine's pool through a private attribute. Replaced it with a proper `pooled=False`
  option on `make_engine`.
- Two smaller ones: the first request log duplicated the actor field (removed); the first `errors.py` used a ternary
  that ruff reformatted into something unreadable (rewritten).
**Follow-ups:** Ishan creates `backend/.env` with the Supabase session-pooler URL, then Claude runs `alembic upgrade head`
and verifies RLS. Ishan creates the Render Blueprint and the Vercel project; Claude smoke-tests the live URLs.
UptimeRobot keep-warm in Phase 6 (or sooner if Ishan wants).

## #4 | 2026-11-25 12:15 UTC | What's needed from Supabase; GitHub Pages instead of Vercel?
**Prompt (simplified):** What exactly does Claude need from Supabase, and can GitHub Pages replace Vercel?
**What changed:** Nothing in the code. This log entry only.
**Impact:** None yet. Explained that the only Supabase input is the session-pooler connection string (no API keys,
no tables or policies made by hand). Laid out the GitHub Pages tradeoffs: no rewrites, so deep links need a 404.html
fallback; a /NammuAI/ base path; deploys through GitHub Actions; up to about 10 minutes of CDN caching after a deploy.
**Decisions made (and by whom):** Pending Ishan: Vercel (the spec, ADR-002) or GitHub Pages. Claude recommended Vercel
for clean deep links and fast deploys during the live change, but said Pages is workable.
**AI mistakes caught or corrected:** None.
**Follow-ups:** Ishan to pick a host and add backend/.env. If Pages, update ADR-002 and add the workflow + Vite base path.

## #5 | 2026-11-25 12:21 UTC | Why Render and render.yaml? Why not Supabase's API? How to set up Vercel
**Prompt (simplified):** It must be a real full-stack app that works in the future. Why aren't we using Supabase's API,
why do we have Render and a YAML file, and what are the Vercel setup steps? Ishan chose Vercel for the frontend.
**What changed:** Nothing in the code. This log entry only.
**Impact:** Explained the three-part architecture: Vercel serves the website, Render runs the Python API, and Supabase
stores all data, including every edit Dana makes. render.yaml is only Render's settings file. Explained why the
browser doesn't call Supabase's auto-generated API directly: the planning logic is Python, writes need validation and
an audit row in the same transaction, and no database keys should sit in the browser. Gave the Vercel setup steps.
**Decisions made (and by whom):** Ishan chose Vercel over GitHub Pages for the frontend (ADR-002 unchanged). Claude
recommended keeping Render for the API, and offered "API on Vercel too" as the alternative if Ishan wants one platform.
Pending Ishan.
**AI mistakes caught or corrected:** None. In hindsight, Claude should have explained the hosting pieces in plain
words in Phase 1 before handing over deploy steps.
**Follow-ups:** Ishan: backend/.env, keep or drop Render, Vercel project. Claude: migration, CORS, smoke test.

## #6 | 2026-11-25 12:35 UTC | Vercel is live; what goes in the env vars; what to pick in Supabase "Connect"
**Prompt (simplified):** Vercel is deployed at https://nammu-ai.vercel.app/. What goes in Environment Variables, and what
should the Supabase project be connected with?
**What changed:** `frontend/src/api/client.ts` (a blank VITE_API_BASE_URL now falls back; a 2xx that isn't JSON raises a
visible error). `frontend/src/pages/MondayPage.tsx` (the status panel shows which API the site is calling).
**Impact:** Claude checked the live site with curl. The root and the deep link /items/SHR-1620 both return 200, so the SPA
rewrite works. But the built bundle had an **empty** API base URL: the Vercel variable was saved blank, so every call
went to the website itself, got HTML back, and the page rendered blank with no error. After the fix the page shows
"couldn't reach the server" until Render is up, and the status panel names the API URL.
**Decisions made (and by whom):** Supabase "Connect" → Connection String → URI → Session pooler (Claude's advice). Don't use
the Supabase–Vercel integration or the app-framework keys: the browser never talks to Supabase directly. The Vercel
variable gets its real value once Render is deployed.
**AI mistakes caught or corrected:** **Claude's bug.** `??` only falls back on undefined, not on an empty string, and
`response.json().catch(() => null)` let a non-JSON 200 pass as data. Found by inspecting the live bundle, not by a test.
The frontend has no unit tests yet (the spec's gate is build + lint); a client test is worth adding in Phase 5.
**Follow-ups:** Ishan: backend/.env, deploy Render, then set VITE_API_BASE_URL and redeploy. Claude: set Render
CORS_ORIGINS to https://nammu-ai.vercel.app.

## #7 | 2026-11-25 12:52 UTC | Supabase connection string shared; where is Render?
**Prompt (simplified):** Shared the Supabase session-pooler string (with the password placeholder, no secret) and asked
where to find Render.
**What changed:** `render.yaml` now has `region: virginia`. Created local `backend/.env` (gitignored, not committed) with
that string plus `?sslmode=require` and both CORS origins, leaving the password for Ishan to fill in.
**Impact:** The API will run in the same AWS region as the database (us-east-1), so there are no cross-country round trips
per query. The region has to be set before the Render service exists, because Render can't move a service later.
Tests still pass with a real .env present (58), which confirms conftest isolation.
**Decisions made (and by whom):** Claude matched the Render region to Supabase. Ishan's message implies Render stays for the API.
**AI mistakes caught or corrected:** None.
**Follow-ups:** Ishan: put the password in backend/.env, then create the Render account and Blueprint. Claude: run
`alembic upgrade head`, verify RLS, smoke-test.

## #8 | 2026-11-25 13:13 UTC | "Nowhere to put the password"; why Render? → API moves to Vercel; database created
**Prompt (simplified):** There's nowhere in backend/.env for the password. Why Render? Ishan has never needed it for full-stack sites.
**What changed:**
- `scripts/set_database_password.py`: hidden prompt, URL-encodes the password, writes it into DATABASE_URL. Tested on a
  scratch copy with a nasty password; the real file was untouched by the test.
- **Ishan chose Vercel for the API** (AskUserQuestion; Claude now recommended it).
  - `render.yaml` deleted; `backend/vercel.json` added (region iad1 + daily cron on /health).
  - `backend/pyproject.toml` replaced by `pytest.ini` + `ruff.toml`.
  - `.python-version` changed 3.12.12 → 3.12; requirements comments moved onto their own lines.
  - Settings now read `VERCEL_GIT_COMMIT_SHA` and `VERCEL`; the DB pool is 1+2 on serverless.
  - Comments de-Rendered; cold-start copy updated (seconds, not 30 s).
  - New `tests/unit/test_deploy_config.py` (7 guards).
- ADR-002 rewritten; CLAUDE.md deploy section + decision list updated.
- **Database created in Supabase:** `alembic upgrade head` (revision 0001).
**Impact:**
- Supabase now has 22 tables (21 + alembic_version), all with RLS on and no policies. Proven with a rolled-back row: the
  backend role saw 1 row, Supabase's public `anon` role saw 0, and an anon insert was rejected by RLS.
- `/health` against the real DB: `status: ok, db: ok, schema_ready: true`.
- The transaction pooler (6543) was verified with repeated statements.
- 66 tests pass; ruff, ESLint, Prettier and the build are clean.
**Decisions made (and by whom):** Ishan: API on Vercel (ADR-002). Claude: transaction pooler for the deployed API and
session pooler for migrations, the iad1 region, the daily cron as Supabase keep-alive, and tool config out of pyproject.
**AI mistakes caught or corrected:**
- **The original pyproject.toml would have broken the Vercel deploy.** Reading Vercel's builder source showed that any
  pyproject.toml becomes the dependency list and requirements.txt is ignored. Claude had created that file in Phase 1
  for tool settings only. Caught before any deploy, now guarded by a test.
- The `.env` placeholder design invited a mistake: Ishan's password went in with the square brackets still around it, and
  Supabase rejected it. Claude diagnosed this without printing the secret, confirmed the bracket-less password connects,
  then fixed the file (value never shown). The helper script prevents it next time.
- Claude's first version of the cron test assumed `route.path` on FastAPI 0.165's included routers. Rewritten to call the route.
- On "why Render": the build prompt's choice was passed along without checking it against Ishan's experience until he asked.
**Follow-ups:** Ishan creates the Vercel API project (root `backend`) with DATABASE_URL (port 6543), CORS_ORIGINS and
APP_ENV, then sets VITE_API_BASE_URL on the web project and redeploys. Claude smoke-tests both live URLs.

## #9 | 2026-11-25 13:27 UTC | "Why two projects? Keep it simple" → one Vercel project with two services
**Prompt (simplified):** Is this the most efficient way? Ishan has never needed two separate projects for a backend; keep it simple.
**What changed:** Root `vercel.json` added. It declares Vercel Services: `web` = frontend/, `api` = backend/
(`app.main:app`), rewrites `/api/(.*)` → api and the rest → web, region iad1, daily cron.
`backend/vercel.json` and `frontend/vercel.json` deleted. Frontend changes:
- `client.ts` defaults to the same-site `/api/v1`; VITE_API_BASE_URL is now an optional override;
- `vite.config.ts` dev proxy `/api` → :8000;
- `.env.example` and comments updated.

`tests/unit/test_deploy_config.py` was rewritten for the single-project layout (69 tests now). CLAUDE.md deploy
section and ADR-002 were rewritten.
**Impact:** One project, one URL. The API will live at https://nammu-ai.vercel.app/api/v1, so there's no CORS, no
API-URL variable and no second project. Verified locally: the browser address :5173/api/v1/health went through the Vite
proxy to FastAPI, then to Supabase, and returned `status: ok`. The deep link /items/SHR-1620 served the app. Until Ishan
changes the existing project's Root Directory to the repo root, the live site is temporarily without the API and without
deep-link fallback.
**Decisions made (and by whom):** Ishan: one project. Claude: Vercel Services via an explicit root config rather than
layout auto-detection, which the builder source shows is feature-flagged. Two projects stays the documented fallback.
**AI mistakes caught or corrected:**
- **The two-project setup in #8 was more complex than needed.** Claude didn't check for Vercel's single-project Services
  feature before recommending it. Found only after Ishan pushed back.
- Claude's script for the local end-to-end check first used a wrong relative path to uvicorn. Fixed on rerun.

What the verification found, from Vercel's source and docs rather than memory:
- Services is beta on all plans.
- The FastAPI service receives the unstripped path (prefix stripping only applies to the legacy experimentalServices).
- Layout auto-detection is behind a flag, hence the explicit config.
**Follow-ups:** Ishan: in the nammu-ai project set Root Directory to the repo root (empty), the Framework Preset to
"Other" if Vercel asks, add DATABASE_URL (6543) and APP_ENV, then redeploy. Claude: smoke-test the live site + API, and
confirm the cron and region took effect.

## #10 | 2026-11-25 13:32 UTC | Where do DATABASE_URL and APP_ENV go?
**Prompt (simplified):** Where exactly do we add DATABASE_URL and APP_ENV?
**What changed:** Nothing in the repo. Claude copied the production DATABASE_URL (the backend/.env value with port 5432
switched to 6543, the transaction pooler) to Ishan's clipboard with `pbcopy`, so it never appeared in chat and the
port didn't have to be edited by hand.
**Impact:** Ishan can paste the value into Vercel → nammu-ai → Settings → Environment Variables.
**Decisions made (and by whom):** Claude: apply both variables to all environments (Production + Preview) and mark
DATABASE_URL as Sensitive.
**AI mistakes caught or corrected:** None. In hindsight, #9's instructions named the setting without saying where it lives in the dashboard.
**Follow-ups:** Ishan sets the Root Directory to the repo root, adds the two variables and redeploys. Claude smoke-tests.

## #11 | 2026-11-25 13:36 UTC | Secret or config?
**Prompt (simplified):** In Vercel, should DATABASE_URL and APP_ENV be "secret" or "config"?
**What changed:** Nothing in the repo.
**Impact:** DATABASE_URL is a secret (it contains the database password). APP_ENV is plain config (not sensitive).
**Decisions made (and by whom):** Claude advised; Ishan to set.
**AI mistakes caught or corrected:** None.
**Follow-ups:** Redeploy, then Claude smoke-tests.
