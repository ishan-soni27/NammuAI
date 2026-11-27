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

## #12 | 2026-11-25 13:46 UTC | Vercel build warnings → live smoke test passes; Phase 1 done
**Prompt (simplified):** Pasted two Vercel build warnings: npm "Unknown env config cache-dir", and engines ">=22.12" auto-upgrading Node majors.
**What changed:** `frontend/package.json` engines `>=22.12` → `22.x` (and the lockfile), so Vercel can't silently move
to a new Node major. The cache-dir warning comes from Vercel's build image (no .npmrc in the repo), so no action.
**Impact:** Live smoke test of https://nammu-ai.vercel.app (one project, two services):
- `/` → 200 HTML; `/items/SHR-1620` → 200 HTML (deep-link fallback works);
- `/api/v1/health` → `{"status":"ok","db":"ok","schema_ready":true,"as_of":"2026-11-16","version":"3b6e32c"}`;
- `/api/v1/does-not-exist` → our 404 envelope, which proves /api/* reaches FastAPI with the path intact;
- `x-vercel-id` shows iad1::iad1 (the function runs next to Supabase); the X-Request-ID echo and HEAD both work.

Health takes about 1.0–1.3 s per call from here (TLS + DB round trips). It'll be measured server-side in Phase 4.
**Phase 1 is complete.** The walking skeleton runs on browser → Vercel (web + API) → Supabase.
**Decisions made (and by whom):** Claude: pin Node 22.x, matching the local Node 22.14.
**AI mistakes caught or corrected:** `>=22.12` in Phase 1 was an open-ended engines range. Caught by Vercel's warning.
**Follow-ups:** Ishan: glance at the page ("Everything is connected"), and check Settings → Cron Jobs shows the daily
/api/v1/health job. Next: Phase 2 (loader) plan, waiting for "go".

## #13 | 2026-11-25 13:47 UTC | Visual check of the live page
**Prompt (simplified):** Pasted what the live page shows: "Monday, November 16, 2026", "Everything is connected", server
up, database connected, no BlueTide data loaded yet, version 3b6e32c at /api/v1.
**What changed:** Nothing in the repo.
**Impact:** Ishan confirmed the Phase 1 page renders correctly in a real browser. Claude could only check HTTP responses,
so this closes that gap. The business date shows from the API, the status sentences are correct, and the relative
/api/v1 base works.
**Decisions made (and by whom):** None.
**AI mistakes caught or corrected:** None.
**Follow-ups:** Cron Jobs check in the Vercel dashboard is still pending. Phase 2 (loader) is waiting for Ishan's "go".

## #14 | 2026-11-25 13:55 UTC | "go": Phase 2, the loader
**Prompt (simplified):** Go ahead with Phase 2 (the loader), as planned.
**What changed (built in this turn, committed after #15):**
- `backend/app/loader/`: `read_raw`, `reference`, `normalize`, `classify`, `convert`, `rules` (T01–T31, one
  builder per file), `pipeline` (pure), `write`, `report`, `run` (CLI), `types`.
- `backend/app/planning/supply.py` (on-hand breakdown per §6.1, `effective_lead_time_days`) and `calendar.py` (`add_months`).
- Load labels moved into `business_rules.py` (ZZ-, FR-, FRESH, CM-, INTERNAL, ADJ-, status words) so no code is hard-coded.
- Tests: 29 per-trap rule tests, parser/reference/planning tests, and 17 golden tests on the real files (151 total).
**Impact:** The pipeline reproduces every golden fact it can. The first real load **failed** (see below) and the turn
ended when the network dropped mid-way, so this entry was written in #15.
**Decisions made (and by whom):** Claude chose Python's `csv` module over pandas for the loader (ADR-019, a deviation
from BUILD_PROMPT §8.1, flagged at the Phase 2 stop).
**AI mistakes caught or corrected:**
- **Writer bug:** it dropped every field named `source`, which also wiped the seeds' provenance text. The DB's NOT NULL
  on `excluded_orders.source` caught it on the first real load; the transaction rolled back (0 rows left, verified).
- The 5 s connect timeout (right for the API) was too tight for a laptop, so recording that failure also timed out and
  left load run #1 stuck at "running". Claude closed it by hand with the real reason, and added an event_log note.
- Pack-size regex: `\b` never matches after `#` in "10#". Caught by smoke-testing before any test was written.
- A test factory with blank pack text made the T09 test fail. That was a fixture bug, and the T09 check itself was right.
- The invariant test caught `datetime.now()` in run.py. It's a legitimate report timestamp, now marked `# clock-ok`.
**Follow-ups:** Finish the load.

## #15 | 2026-11-25 14:45 UTC | "Try now, the network is back" → Phase 2 done
**Prompt (simplified):** The network is back; try the load again.
**What changed:**
- `write.py`: bulk rows via Postgres COPY; `SET LOCAL statement_timeout = '15min'` for the load transaction only;
  `finished_at` uses `clock_timestamp()`.
- `session.py`/`env.py`/`run.py`: a configurable connect timeout (30 s from a laptop).
- `scripts/profile_data.py` (independent re-derivation, stdlib only).
- Docs:
  - `DATA_LOAD_REPORT.md` (generated);
  - DATA_AUDIT (two new findings: LB POs for LOB-T56, a 4th "FUEL SURCHARGE" price row; Phase 2 status);
  - ASSUMPTIONS A19–A22 (conservative defaults for unknown status, vendor type, location, fully received open PO);
  - DECISIONS ADR-019 (csv not pandas), ADR-020 (one transaction, COPY, raw rows per run);
  - CLAUDE.md commands.
**Impact:**
- **Load run #4 succeeded in 1 m 46 s** (run #2 had succeeded in about 5.5 m before COPY).
- 16,542 raw rows, 4,047 data issues, 0 errors.
- The second load **kept all 5 vendor_settings untouched** (invariant #5 shown working).
- Every golden fact was re-checked three ways: pytest goldens, profile_data.py, and SQL on Supabase.
- Every clean row links to its raw row.
- The live `/api/v1/health` now reports `last_load_at`.
**Decisions made (and by whom):** Claude: COPY + per-transaction timeout (ADR-020); the four conservative defaults
(A19–A22) are recorded as assumptions for Ishan to review.
**AI mistakes caught or corrected:**
- Run #3 hit Supabase's 2-minute statement timeout. Measuring the network (about 300 ms round trip, 140 KB/s upload)
  showed it is bandwidth-bound, so COPY alone wasn't enough; hence the per-transaction timeout.
- `now()` returns the transaction START time, so run #2's recorded duration (4 s) is wrong; it really took about 5.5 m.
  Fixed with clock_timestamp() for future runs. Run #2's row is left as history rather than rewritten.
**Follow-ups:** The Data notes page (Phase 4) must read issues from the latest successful run only. Pruning old raw
rows is a later step. Phase 3 (planning engine) plan is waiting for "go".

## #16 | 2026-11-26 05:15 UTC | Dana's reply to the six questions
**Prompt (simplified):** Ishan pasted the email as sent and Dana's reply.
**What changed:**
- `docs/client/dana-replies.md`: the reply, verbatim, plus a table of what each answer changed.
- `business_rules.py`: `overdue_po_assumed_days = 7` replaced by `late_po_assumed_days = None` (don't count late POs
  until Dana enters a date); the dormant rule's source now cites her confirmation.
- `loader/classify.py` + `loader/rules.py`: "Pending Dana" wording removed; the T26 message now says late POs aren't counted.
- Seeds: `vendor_settings_seed.csv`, `locations.csv` and `stockout_periods.csv` got provenance notes citing her
  answers. **No numbers changed.**
- Docs: ASSUMPTIONS A01, A02, A04, A05, A06 → Confirmed by Dana; **A03 → Changed by Dana**; A16 → rate known
  (/pallet/month), cases per pallet unknown. DATA_AUDIT T06, T26 rule and G15 amended. ADR-006 note.
  email-to-dana.md and CLAUDE.md updated.
- Database:
  - **Load run #5** (63 s, 0 errors) refreshed the clean layer and kept all five vendor_settings rows.
  - Those rows' provenance notes were updated by a one-off script, with one `audit_log` row each (actor Ishan, action
    `vendor_settings.confirm_from_email`). Values were asserted unchanged before updating.
**Impact:**
- Every email default is confirmed except Q3. **Late POs (PO-260394 SHR-2125 800 cs, PO-260376 PAN-0709 400 cs,
  PO-260407 CAL-RING 300 cs) will not count as incoming at all** in Phase 3.
- Items they would cover must be called out. Expect SHR-2125, PAN-0709 and CAL-RING to look worse than the §7 answer
  key, which assumed arrival around Nov 23. This is a client-driven change, not tuning.
- Golden fact G15 is amended accordingly.
**Decisions made (and by whom):**
- **Dana** changed the late-PO rule.
- **Claude's reading, to confirm with Ishan:** "don't assume they'll arrive within a week" means don't count them
  until she types a date (the cautious reading), rather than assuming some later date.
- "Only covered by a late PO" will be shown when an item looks fine only if its late PO arrives.
**AI mistakes caught or corrected:** None. Before touching any number, Claude checked that the confirmed values already
matched the seeds and the DB (they did).
**Follow-ups:**
- Confirm the Q3 reading.
- Harbor $ per month needs cases per pallet (or pallets in use) per item. Suggest asking in the planned validation email (§4.5).
- Phase 3 is waiting for "go".

## #17 | 2026-11-26 05:27 UTC | Late-inventory section, Harbor cost calculator, chatbot later, "why the .ini files / ruff?", start Phase 3
**Prompt (simplified):** Put late POs in their own section (arriving, but not current inventory), with a section for
unknown/late inventory. Build a Harbor storage cost calculator (/pallet; Dana types cases per pallet; save rows to a
table; CSV export) as its own section. A chatbot is for later; priorities first. Why so many .ini files, and what is
ruff? Begin Phase 3.
**What changed:**
- `docs/PRIORITIES.md` (new): P0 #2a late/unknown inventory bucket; P1 #1 Harbor storage cost calculator (absorbs old
  P1 #5 and part of #1); P2 chat assistant.
- **Phase 3 engine** in `backend/app/planning/`:
  - `types`, `seasonality` (monthly category index, in pounds), `demand` (8-week rate → level → daily forecast);
  - `supply` (on hand; PO arrival dates: Dana > real lead time > BlueTide; late = no date);
  - `projection` (day-by-day run-out, status, shortage and when stock comes back), `ordering` (order at least, lost-sales floor);
  - `stuck` (lot tags + Harbor badge + $), `explain` (plain-English steps), `engine` (orchestrates, two scenarios).
- `services/planning_inputs.py`: maps the clean dataset to engine inputs.
- Tests: 30 engine tests (traps T15/T22/T23/T26/T30, statuses, flooring, late-PO bucket, handled notes, overrides,
  stuck precedence, trust strip) + golden G15, G17 and a stuck/trust check → **184 total**.
- `scripts/compare_answer_key.py`.
- `business_rules.open_orders_in_selling_rate` switch (default per spec).
- Docs: ASSUMPTIONS A23–A26; DECISIONS ADR-005/009/016 notes, ADR-021 (late bucket), ADR-022 (floats in engine);
  DATA_AUDIT Phase 3 status; CLAUDE.md.
**Impact:** The engine plans all 45 items in about 60 ms. Versus the §7 answer key (current rules):
- **SHR-2125** Nov 21 (+0d), **LOB-T56** Nov 25 (+0d), **SHR-1620** Dec 10 (−4d), **PAN-0507** Dec 26 (−1d): all too late, same as the key.
- HAD-FIL, POL-FIL and SAL-SIDE-SK are "this week", 1–2 days earlier than the key.
- **CRAB-SNW5 and LOB-MEAT flip to "too late"**: their run-outs land 1 day before a new order could arrive (knife-edge).
  Either way the action is the same: order today and expedite (shortfalls of 13 cs and 2 cs).
- New in the list: **CAL-RING and PAN-0709**, because their late POs no longer count. Both are flagged "covered only
  by a late PO", as Dana asked. SAL-CHO6 and SHR-1215 have order-by dates at the this-week boundary.
- The stuck list and trust strip match the key exactly (SAL-POR6 1,350 cs, 1,050 at Harbor, $81,232; 420/20/78/59;
  SHR-1620 at Harbor not stuck). Plus 1,500 cs of late POs shown, not counted.
**Decisions made (and by whom):**
- Ishan: the late/unknown section, the Harbor calculator as P1 #1, chatbot as P2.
- Claude, flagged:
  - seasonality summed in pounds (A26);
  - the "covered only by a late PO" test uses the best case "arrives today" (A24);
  - floats in the engine (ADR-022).
- **Pending Ishan:** `open_orders_in_selling_rate` (A23). The data shows every past order shipped within 3 days,
  but this week's open orders are holiday pre-bookings, so the spec counts them twice. Kept as spec'd (cautious) for now.
**AI mistakes caught or corrected:**
- The first SHR-1620 explanation said the shortage lasted until the new order (Feb 8). In fact the 600 cs PO restocks
  Jan 25, and "order at least 0" looked like a bug. Added `back_in_stock_date` and an explanation line.
- Claude's first T22 test assumed an open order didn't affect the rate. It does (spec §6.2), and investigating that led
  to the A23 finding.
- The comparison script formatted dates through strftime ("10"); fixed.
**Follow-ups:** Ishan: decide A23; confirm A24/A26. Phase 4 (API) is waiting for "go".

## #18 | 2026-11-26 05:57 UTC | "What have you built? Does the site work?" + count open orders once + "does this still fix the holiday problem?"
**Prompt (simplified):** What's done so far, and does the site actually work? Ishan agreed to count open customer orders
once, then asked whether that still fixes Dana's problem of not keeping up with holiday demand.
**What changed:**
- `business_rules.open_orders_in_selling_rate` False (was True per §6.2), with doc/source citing the decision and data.
- Test renamed `test_open_orders_count_once_by_default`.
- `scripts/compare_answer_key.py`: the third scenario is now "spec-6.2".
- ASSUMPTIONS A23 → Decided by Ishan; ADR-013 note; CLAUDE.md. This entry was written after plan mode, which blocks writes.
**Impact:**
- **Status answered honestly:** the site is live and connected, and the data is loaded and verified. The engine works
  in code (184 tests). But **Dana can't see any ordering information yet**: the API serves only `/health` (Phase 4) and
  the screens don't exist (Phase 5).
- **Numbers after the change:**
  - SHR-1620 too late, **Dec 14** (= the answer key, "ten days before Christmas"), 53 cs/wk.
  - SHR-2125 too late Nov 24, now also flagged **covered only by its late PO**. LOB-T56 too late Nov 28.
  - CRAB-SNW5 and LOB-MEAT are "this week" (no longer knife-edge too late). PAN-0507 is fine: its corrected PO lands
    Dec 28 before it runs out. POL-FIL is "soon".
  - The stuck list and trust strip are unchanged.
- **Holiday question, checked with data:** holiday protection comes from the December seasonal index (shrimp 1.6×,
  learned from all shrimp so SHR-1620's own stockout can't hide December), the real 12-week lead time, and order-by
  dates (SHR-1620 needed ordering by ~Sep 7). The switch doesn't touch these.
  - Counting once, SHR-1620 plans 542 cs for December. Last December's pace before it ran out was ~487 cs, so the plan
    is still above it.
  - The spec rule planned 656 cs and put the holiday bump in November.
  - This December can't be fixed by ordering from Vietnam. The tool flags it 4 weeks ahead with ~382 cs short until
    Jan 25: expedite or find another source. Used every Monday, it warns in September.
**Decisions made (and by whom):** Ishan: count open orders once. Claude: extra holiday margin, if wanted, should come
from the per-item cushion, not double counting.
**AI mistakes caught or corrected:**
- Claude's new test chained `pytest.approx` inside `<`, which doesn't work. Split into two asserts.
- Ishan's sentence ("count open customer orders in the selling rate") read as the opposite of the recommendation.
  Claude asked instead of guessing.
**Follow-ups:** Phase 4 (API) is waiting for "go".

## #19 | 2026-11-26 06:15 UTC | "go": Phase 4, the API
**Prompt (simplified):** Go ahead with Phase 4.
**What changed:**
- **Endpoints** (`backend/app/api/v1/`; docs at /api/v1/docs):
  - `items.py`: dashboard, items, drill-down, handled notes, item settings;
  - `suppliers.py`: vendors, PO arrival dates;
  - `activity.py`: data notes, audit log, events, load runs, settings, client events.
- **Services:** `planning_inputs.inputs_from_db` (clean layer cached per load run, Dana's edits fresh),
  `planning_service`, `presenters` (Monday-screen assembly + summary sentences), `audit` (audit row in the same
  transaction; request_log; event_log).
- **Middleware:** a request_log row after every response (worker thread, never failing the request); unhandled errors
  go to event_log.
- **Portability for tests (ADR-023):**
  - JSON/BIGINT model variants;
  - the writer uses COPY/TRUNCATE on Postgres, insert/DELETE elsewhere;
  - `db/sql.utc_now()`;
  - `db.session.use_engine`.
- 17 API tests on a SQLite copy of the real data, loaded by the real writer.
- `planning/supply.lot_status`; ItemPlan carries the vendor country; PO dates say "Set by <who>".
- Docs: ADR-004 note, ADR-023, CLAUDE.md, PRIORITIES statuses.
**Impact:**
- **The API now serves everything the screens need.** 201 tests pass; ruff is clean.
- `alembic check` against Supabase: no schema drift.
- **Live smoke test on https://nammu-ai.vercel.app:**
  - all 12 read endpoints return 200 with the same numbers as the tests;
  - the summary reads "3 items will run out before a new order can arrive. 6 more need an order this week and 5 should
    be ordered soon. 3 items would only be covered if a late PO shows up. $108,799 of stock is inside the six-month
    line, $90,970 of it at Harbor. Not counted: 420 cs on hold, 20 cs damaged, 78 cs expired, 59 cs of old ZZ stock,
    1,500 cs on late POs with no arrival date."
- **Server time inside the API** (from request_log): dashboard ~220 ms average (137–542), drill-down ~165 ms, health
  13–203 ms. The 1–2 s seen from this laptop is its slow link (connect + TLS alone 0.4–2 s).
- **Live audited edit:** a PO date was set and cleared on PO-260394 (actor "Claude (smoke test)"). The item moved from
  late to dated and back; both audit rows are present; a bad lead time got the plain-English 422.
**Decisions made (and by whom):** Claude:
- SQLite-based API tests (ADR-023) instead of skipping them;
- an in-memory cache of BlueTide inputs per load run (ADR-004);
- notes and PO dates in the past are rejected;
- cushion follows the spec's 1–365 days;
- docs moved to /api/v1/docs.
**AI mistakes caught or corrected:**
- `clock_timestamp()` doesn't exist in SQLite. Caught by the first SQLite load; added a portable `utc_now()`.
- A circular import (audit ↔ middleware) was avoided by moving DEFAULT_ACTOR into logging_setup.
- A leftover placeholder function in items.py was removed.
- The health GET+HEAD route produced a duplicate OpenAPI id. Split it.
- **Claude's smoke-test script used `path` as a loop variable.** In zsh that overwrites PATH, so curl "wasn't found".
- The live test showed PO dates labelled "Set by Dana" even when someone else set them. Now "Set by <who>".
**Follow-ups:** Phase 5 (the screens) is waiting for "go". The two smoke-test audit rows stay in the log as an honest record.

## #20 | 2026-11-26 06:17 UTC | "claude doctor"
**Prompt (simplified):** Ishan typed `claude doctor`, the Claude Code CLI's health check for its own installation.
**What changed:** Nothing in the repo. This log entry only.
**Impact:** None on the project. It's a Claude Code command, not part of the app. Claude didn't run it itself because it
opens an interactive screen. Claude pointed Ishan to `/doctor` (or `! claude doctor`) to run it in this session.
**Decisions made (and by whom):** None.
**AI mistakes caught or corrected:** None.
**Follow-ups:** Phase 5 (the screens) is still waiting for "go".

## #21 | 2026-11-26 09:48 UTC | "claude doctor" (again)
**Prompt (simplified):** `claude doctor` again.
**What changed:** Nothing in the repo. Written late because plan mode was active.
**Impact:** Claude ran `claude doctor` read-only (stdin closed, time limit):
- **No installation issues found**: native install, v2.1.332, darwin-arm64.
- The API answered in 1.2 s and sign-in in 1.6 s.
- Auto-updates are enabled, but the **last update attempt failed (install_failed) on 2026-11-26**. Not urgent; Ishan
  can run `! claude update` or `/doctor`.
- Remote Control is off by org policy.
**Decisions made (and by whom):** Claude didn't update Claude Code itself, because that changes Ishan's installation.
**AI mistakes caught or corrected:** None.
**Follow-ups:** None for the project.

## #22 | 2026-11-26 09:48 UTC | "go": Phase 5, the screens
**Prompt (simplified):** Go ahead with Phase 5 (plan approved: Monday screen, item page with chart, lead times, data
notes, activity, and all states).
**What changed:**
- **Backend (small):**
  - `business_rules.season_markers` (Christmas 2026, Lent 2027) served on the item page;
  - stuck lots carry `location_name`;
  - tests for both.
- **Frontend** (`frontend/src/`):
  - `api/types.ts` mirrors every schema; `api/queries.ts` has one hook per endpoint plus the edits (each toast says
    what happened);
  - **Monday screen:** summary sentences, what isn't counted, then *What to order* (runway bar, run-out and order-by
    dates, order at least, supplier terms, shortfall, "Only covered by a late PO", Mark as handled), then Handled,
    **Late or unknown** (late POs with Set real date, stock on hold) and *Everything else looks fine*, and *What you're
    stuck with* (grouped by tag, Harbor lots first and badged, $ at cost);
  - **Item page:** numbered "Why" steps; the 26-week chart (stock line, if-the-late-PO-arrives line, out-of-stock band,
    new-order and run-out markers, arrivals, busy seasons) with a week-by-week table twin; lots (counted or not, and
    why); promised to customers; on the way with Set real date / Change date / Clear date; sales by month with the
    season index; item settings;
  - **Lead times** (edited in weeks), **Data notes** (rows 50 at a time with file, line and the original CSV values),
    **Activity** (before and after, loads, events and errors);
  - shared: header nav, "Using as: <name> · change", the one-time "Who's using this?" prompt, hover glossary, loading /
    cold-start / error states, browser errors reported to `/client-events`;
  - the item page loads on demand (Recharts), so the Monday bundle is 283 KB.
- Docs: ADR-024, PRIORITIES (P0 #2a–#8 done), CLAUDE.md frontend map.
**Impact:**
- **Dana can now use the app.** https://nammu-ai.vercel.app shows both answers on one screen. Every number links to
  its item page, and every edit is saved with her name and shows up in Activity.
- Checks: 201 backend tests pass; ruff, `npm run build`, `npm run lint` and `format:check` are clean; raw checksums OK.
- **Browser checks** (headless Chrome, every page at 1280 px and 375 px, local and live): no console errors, no page
  errors, no sideways scrolling.
- **Click-through through the UI, local** (throwaway SQLite copy of the real data):
  - mark SHR-1620 handled with 400 cs arriving Dec 10: it moves to Handled and counts as on the way; clear it;
  - set PO-260394's real date from the Monday screen, see "Set by <name>" on the item page, clear it;
  - change Downeast Lobster from 3 to 4 weeks (28 days) and back;
  - open T01's rows; the Activity log lists every change.
- **The same click-through on live**, labelled "Claude (live click-through)" and reverted. Four audit rows record it.
  The lead-time step was skipped on live, because saving would replace the note that records Dana's email confirmation.
  Live is back to 0 handled and the same 3 late POs.
**Decisions made (and by whom):** Ishan approved the Phase 5 plan. Claude decided (ADR-024):
- season windows live in business_rules.py, not the frontend;
- lead times are edited in weeks;
- the chart stops at zero and shades "Out of stock" instead of plotting negative stock;
- item names are shown in sentence case next to the code;
- Recharts 3.11.1 is pinned and loads only on the item page;
- stuck lots show location names.
**AI mistakes caught or corrected:**
- **The first chart plotted the engine's balance below zero** ("-1,200 cs"). The engine uses negatives to measure the
  shortage; a shelf can't hold negative stock. Caught in the screenshots, fixed with the out-of-stock band.
- **The "on hold" hover bubble swallowed clicks.** It opened over the "Set real date" button just above it and stayed
  open while the mouse was on it. Caught by the browser click-through; the bubble now ignores the mouse.
- **The phone layout scrolled sideways:**
  - hidden hover bubbles still took up width, so they're now `display: none` until hover;
  - grid cards grew to fit their tables, so they now have `min-w-0`;
  - on live only (where Activity has rows), a screen-reader-only word escaped its table's scroll box, so table scroll
    boxes are now `position: relative`.
- **SHR-1620's card said "Too late" and "Nothing needs ordering today" together.** The engine was right: PO-260443
  lands Jan 25, before a new order could (Feb 8). The card now says ordering more today won't close the gap.
- Small copy fixes: doubled brackets in the shortage line, "Yes. Counted.", and "No sales in the last 8 weeks" (a
  hard-coded number, replaced with words).
- **Tool-use slip:** a long bash heredoc that wrote the click-through script was blocked by a safety check. It deleted
  nothing. Re-done with the file tool.
- **The click-through's own bug:** it checked the handled note while its section was still closed. Fixed in the script,
  not the app.
**Follow-ups:**
- Phase 6 (README, DEMO_SCRIPT, final docs) is waiting for "go".
- Still open: Vercel cron registration (Ishan to confirm); Harbor cases per pallet (P1 #1).
- Known nits, not fixed: at 375 px the chart's season labels ("Christmas", "Lent 2027") can overlap the "New order
  lands" label, and 4-column tables scroll sideways inside their card.
- Live screenshots (every page, 1280 px and 375 px, plus the first-visit prompt and Activity after the click-through)
  are in `docs/screenshots/phase5/` (6 MB, not committed; Ishan decides whether some go into the README).
- The preview, screenshot and click-through scripts live in the session scratch folder. If Ishan wants them in the
  repo (e.g. `scripts/ui_check.mjs`), that's a small Phase 6 task.

## #23 | 2026-11-26 10:45 UTC | "How do I run or check the site? Is it on Vercel? Do I need to redeploy?"
**Prompt (simplified):** How do I run the site or check it? Is it on Vercel, and do I need to redeploy?
**What changed:** Nothing in the app. This log entry only (committed locally; it goes out with the next push).
**Impact:** Claude checked, read-only:
- the live site serves the newest bundle (index-AumSq0EA.js);
- /api/v1/health reports version `e117ace` (the latest commit on main) with the database ok;
- GitHub shows Vercel's status for e117ace as "Deployment has completed".
So no redeploy is needed. Every push to main deploys automatically. Claude explained how to run it locally and which
checks to run.
**Decisions made (and by whom):** None.
**AI mistakes caught or corrected:** None.
**Follow-ups:** Phase 6 is waiting for "go".

## #24 | 2026-11-26 11:05 UTC | "What is cs? What do the bars and colours mean? Too cluttered. Where is the logging?"
**Prompt (simplified):** What is "cs", and what do the bars and colours mean? There's too much scrolling and clutter.
Make each item a dropdown with the name and bar visible, and use red, yellow and green, not blue. This is an ERP
system: Dana must be able to log and track her future imports and exports, not just analyse old files.
**What changed:**
- Ishan answered three questions:
  - colours red / yellow / yellow / green;
  - build all four logging features (POs to received, outgoing shipments, BlueTide uploads, CSV downloads);
  - the app becomes the main record and should eventually replace BlueTide.
- **Redesign (done, live):**
  - `OrderRow` dropdown rows replace the order cards;
  - stuck list rows are dropdowns too;
  - traffic-light tokens; no blue anywhere;
  - count tiles plus a fold-away "not counted" line;
  - a legend for the bar;
  - "cases" spelled out in the frontend and in the API's sentences (`explain.unit_word`);
  - "Order now (was due ...)" for past order-by dates;
  - the chart's unit moved into its title.
- Docs:
  - ADR-025 (colours and rows) and ADR-026 (the app becomes the main record);
  - CLAUDE.md, Ishan's decisions;
  - PRIORITIES: P0 #10–#13 added, and P2 "creating POs" and "live loading" moved up.
- `docs/screenshots/redesign/` (not committed).
**Impact:**
- **The Monday page is much shorter with everything closed:**
  - 1,618 px tall at 1280 px wide, down from 4,533;
  - 3,687 px at 375 px wide, down from 8,601.
- **Checks:**
  - 201 backend tests pass;
  - ruff, build, lint and format are clean;
  - every page loads without errors and without sideways scrolling at 1280 px and 375 px, locally and live;
  - the click-through passes locally (all edits) and live (handled note and PO date, labelled
    "Claude (live click-through)" and reverted).
- Live data is back to 0 handled and 3 late POs.
**Decisions made (and by whom):**
- Ishan: the colour mapping, the four features, and that the app becomes the main record.
- Claude: order soon is a lighter yellow than order this week; stuck tags red for expired and six-month line,
  yellow for the rest.
**AI mistakes caught or corrected:**
- **Claude built only what the spec scoped (analysis of one load) and didn't flag the ERP gap.** Ishan's expectation
  that Dana can log future work was reasonable for "a system she can use". Claude should have raised it at the
  Phase 5 plan.
- The first redesign cut long names off with "…" on desktop. Fixed.
- A past order-by date showed as "Order by Fri Nov 13". It now says "Order now".
- The `git rm` of the old card component needed `-f` because the colour rename had touched it. That's the only file
  removed, and it was replaced by `OrderRow.tsx`.
**Follow-ups:** The Phase 6 plan (logging and tracking) is posted and waiting for "go" plus two decisions: how
business "today" moves, and the order of the steps.

## #25 | 2026-11-26 11:20 UTC | "plan the logging phase now"
**Prompt (simplified):** Write the detailed plan for Phase 6: Dana logs and tracks her own work (POs, outgoing
shipments, BlueTide uploads, CSV downloads).
**What changed:** Nothing in the app. Claude read the engine inputs (`planning/types.py`), the PO arrival rule
(`planning/supply.py`), how inputs are built (`services/planning_inputs.py`), the loader writer (TRUNCATE of the clean
tables), the app tables, the AS_OF setting and the deploy config. It then wrote the Phase 6 plan in plan mode for
Ishan's approval. This entry is updated when the plan is approved or changed.
**Impact:** Plan only. A design review (a planning agent reading the code) found six blockers in the first draft,
which the plan fixed:
- a date cut-off would miscount, because BlueTide's qty_received has no date (matching by document and quantity instead);
- the reference seeds aren't deployed with the API;
- COPY doesn't work through the production pooler;
- one-file uploads need checks;
- the RLS test only read migration 0001;
- the cache can't answer the matching questions.

**Decisions made (and by whom):** Ishan (four questions): today stays fixed at Nov 16 and switches later; BlueTide's
receipt wins over an open app line; steps POs → shipments → upload → CSV; stop after each. Plan approved (see #26).
**AI mistakes caught or corrected:** Claude's earlier recommendation (prompt #24) was "today = the day after the newest
BlueTide snapshot". That breaks once the app replaces BlueTide: with no more uploads, "today" would never move. The
plan corrects it.
**Follow-ups:** Approval of the plan.

## #26 | 2026-11-26 12:40 UTC | Plan approved: "use auto mode ... it should be able to be its own independent system"
**Prompt (simplified):** Yes, go ahead in auto mode. But the system must not depend on BlueTide: it should work as its
own independent system, where Dana uploads her own information and the system calculates with it.
**What changed (step 6.1, POs; plus independence foundations):**
- The plan was amended (independence): BlueTide becomes one optional source, Dana's items and suppliers are added in
  the app, and step 3 becomes "Import" (BlueTide's files or her own templates).
- **Migration 0002** (applied to Supabase; `alembic check`: no drift; RLS on every table): `app_vendors`, `app_items`,
  `purchase_orders`, `purchase_order_lines_app`, `po_line_status`, `stock_movements`.
- **`planning/records.py`** (pure): rules R1–R6 match her records with BlueTide's by document and quantity.
  `planning_inputs.build_context` caches BlueTide facts per load and merges her items, suppliers, POs and receipts.
  The engine is unchanged.
- **API:**
  - `/purchase-orders` (list, create, ship, cancel, reopen, receive), `/stock-movements/{id}/undo`, `/locations`;
  - `POST /vendors`, `POST /items`, `PATCH /items/{code}/details`, `GET /item-details`;
  - PO dates work for her own lines;
  - the item page shows received lots;
  - the handled-note hint sees her POs.
- **Screens:** Purchase orders (dropdown rows; receive, ship, date, cancel, reopen, undo), New PO (prefilled from
  "Create a PO" on Monday and on the item page), Items (add and edit), Suppliers (was Lead times; add a supplier).
- Docs: ADR-027, A27–A33, CLAUDE.md (invariant 5, code map, playbook, decisions), PRIORITIES (P0 #10 done).
**Impact:**
- **Checks:**
  - 241 backend tests pass: the 201 earlier ones unchanged, 23 rule tests, 17 API tests;
  - ruff, build, lint and format are clean; the raw files are unchanged.
- **Browser checks, local and live:** every page at 1280 px and 375 px with no errors and no sideways scrolling.
- **Local click-through:**
  - "Create a PO" from the SHR-1620 row → KB-00001, counted as on the way;
  - receive 150 into New Bedford (stock +150), then undo;
  - mark shipped, then cancel;
  - add supplier Gloucester Fillet Co. and item KB-COD6, then a PO for it (counted).
- **Live:**
  - the earlier click-through passes;
  - the PO check (create, receive 150, undo, ship, cancel) passes, labelled "Claude (live click-through)";
  - the live Monday numbers are back to the start (3 / 6 / 5 / 16, 0 handled, 3 late POs);
  - the test PO stays as **KB-00001, cancelled**, so Dana's first real PO will be KB-00002.
- Screenshots: `docs/screenshots/phase6-step1/` (not committed).
**Decisions made (and by whom):**
- Ishan: approved the plan and its proposed defaults; added "independent of BlueTide"; auto mode.
- Claude:
  - case items need pounds per case (A33);
  - a computed expected date already in the past is refused (A32);
  - auto numbers KB-00001 and so on (A31);
  - the supplier code is made from the name.
**AI mistakes caught or corrected:**
- **The first draft's date cut-off rule was wrong** (caught by the design review): BlueTide's receipts have no date.
- **The first PO status logic was tangled.** Claude rewrote it into one rule per branch before testing.
- **Two R4 tests expected the wrong thing:**
  - if BlueTide shows a line fully received, the app expects nothing more, so there's no conflict;
  - the flag Dana needs is "BlueTide shows N received that isn't recorded here", which was added.
- **One API test had the arithmetic wrong.** The app was right: 600 + 250 still to come.
- **A file edit stopped halfway:** a second replacement targeted text the first had already removed. Nothing was
  written; Claude re-ran it.
- **Click-through script bugs:**
  - helpers were passed the page instead of an element;
  - the live run waited for a 4-second success message on a slow connection.
  The app worked both times (the server returned 201); the live check was finished by waiting for the server's reply.
**Follow-ups:**
- **Step 6.2** (shipments and moving stock) is waiting for "go".
- Known limits (ADR-027):
  - buildings still come from a load;
  - new items have no sales history until step 2 or 3;
  - an app PO doesn't revive a dormant BlueTide item.

## #27 | 2026-11-26 14:40 UTC | "go to step 2 now": shipments and moving stock
**Prompt (simplified):** Start step 2 of Phase 6.
**What changed:**
- **Migration 0003** (applied to Supabase; `alembic check`: no drift; RLS on every table): `app_customers`,
  `shipments`, `shipment_lines`; stock movements link to their order and to the other half of a move.
- **Rules R7–R10** in `planning/records.py` (pure):
  - an order BlueTide shows invoiced isn't counted again (R7);
  - Dana's copy wins when BlueTide still shows it open, counted once (R8);
  - moves count only if dated after BlueTide's stock count (R9);
  - a pick larger than its lot takes the next lot to expire in the same building, never below 0, with any shortfall
    flagged (R10).
- **Planning inputs:**
  - her orders are classified like BlueTide's sales (`classify_sale`);
  - open orders are promised on their ship date;
  - shipped orders take their picks and feed the selling rate;
  - lots carry where they came from.
- **API:** `/customers`, `/shipments` (create, list, `/picks`, ship, cancel, undo-ship), `/stock-moves`,
  `/stock-lots?item=`, `/stock-movements?item=`. Undo reverses both halves of a move.
- **Screens:**
  - Shipments page (overdue orders red);
  - New order, with "add a customer";
  - Ship shows the lots to take first, soonest to expire and editable;
  - "Move to New Bedford" on Harbor lots in the stuck list, and "Move" on item-page lots;
  - the item page lists stock changes made in the app, with Undo;
  - Activity labels for every new action.
- Docs: ADR-028, A34–A40, CLAUDE.md (invariant 5, code map, playbook), PRIORITIES (P0 #11 done).
**Impact:**
- **Checks:**
  - 268 backend tests pass: 12 new rule tests and 15 new API tests; the earlier numbers are unchanged;
  - ruff, build, lint and format are clean; the raw files are unchanged.
- **Browser checks, local and live:** every page at 1280 px and 375 px, no errors and no sideways scrolling.
- **Local click-through:**
  - add a customer, then log SH-00001 (promised +40);
  - ship it with the picks shown first (New Bedford −40, no longer promised);
  - undo shipped (stock back), then cancel;
  - move 100 cases of SAL-POR6 from Harbor to New Bedford using the stuck list (Harbor 1,050 → 950);
  - undo the move on the item page.
  The earlier PO and Monday click-throughs still pass.
- **Live:**
  - the same flow, labelled "Claude (live click-through)", using an existing customer (no permanent test customer)
    and reversed;
  - live is back to the start: 3 / 6 / 5 / 16, SHR-1620 480 sellable and 201 promised, SAL-POR6 1,050 at Harbor;
  - the test order stays as **SH-00001, cancelled**, so Dana's first real order will be SH-00002.
- Screenshots: `docs/screenshots/phase6-step2/` (not committed).
**Decisions made (and by whom):**
- Ishan: "go" for step 2. R7 and R10 were approved with the plan.
- Claude:
  - orders to our own buildings are refused, so Dana uses Move stock (A38);
  - open samples are promised but never counted as demand (A39);
  - new customers default to Restaurant (A40);
  - shipping is all-or-nothing per order for now;
  - picks of a shipment are undone with the order, not one by one.
**AI mistakes caught or corrected:**
- **One edit silently didn't apply.** Claude used a find-and-replace with no check that it matched; the formatter had
  already reshaped the target lines. As a result, the refresh after an edit didn't include shipments, picks, stock
  lots or customers. The click-through caught it: a new customer didn't appear in the list. Fixed, and the other
  unchecked replacements in this step were reviewed (they either asserted their match or are used by code that now
  compiles).
- **The first "new customer" defaulted to the Cruise type** (alphabetically first). It now defaults to Restaurant.
- **Format-skip markers left lines too long.** They were removed and the formatter wrapped the lines.
- A `useEffect` that copied the pick plan into state broke a React lint rule. The form now starts from the plan
  instead.
- **Moves had no Undo on any screen at first.** Claude added "Stock changes in the app" on the item page, with Undo.
- Expiry dates in the ship panel had no year. Added.
**Follow-ups:**
- **Step 6.3 (Import):** BlueTide's files or Dana's own templates, from the website. Waiting for "go".
- Still open:
  - buildings come from a load;
  - new sales don't move the selling rate until "today" moves;
  - partial shipments.

## #28 | 2026-11-26 15:20 UTC | "the definitions cover the text when I click an item ... make What to Order a grid"
**Prompt (simplified):** Step 3 can wait. Clicking an item in "What to order" shows every word's definition at once,
covering the text. They should only show when you hover the word itself. Also make the What to order items a grid,
not a list, so it looks better.
**What changed:**
- **Bubble fix** (`components/Term.tsx`): the bubbles used Tailwind's plain `group`, which also matched the item's
  dropdown (`<details className="group">`). So opening or hovering an item opened every bubble inside it. They now
  use a named group (`group/term`) and open only on their own word's hover or keyboard focus.
- **Grid of cards** (`components/OrderRow.tsx`, `MondayPage.tsx`):
  - What to order, Handled and Fine are cards, one column on phones and two from 640 px;
  - each card shows the status, code, name, key date, the bar and how much to order;
  - a clicked card opens across the row and the cards after it fill in.
- **Duplicate names refused:** a supplier or customer with the same name as an existing one is now refused (409).
  Re-running a test had silently created GFC2 and GFC3.
- ADR-025 updated.
**Impact:**
- **Browser check (local and live):**
  - after opening a card and moving the mouse over it, no bubbles are visible;
  - hovering "cushion" shows exactly one bubble ("Cushion means extra stock for when ships slip.");
  - an opened card spans the full row;
  - every page at 1280 px and 375 px has no errors and no sideways scrolling.
- 270 backend tests pass (2 new); the frontend build, lint and format are clean; the Monday, PO and shipment
  click-throughs pass locally.
**Decisions made (and by whom):**
- Ishan: show the bubbles only on hover, and lay out the items as a grid.
- Claude: two columns inside the What to order half of the page (the stuck list stays beside it); an opened card
  takes the full row; the stuck list stays a list; duplicate names are refused.
**AI mistakes caught or corrected:**
- **Claude's own bug.** The step-1 bubble fix (`pointer-events-none`) didn't catch the shared `group` class, so this
  shipped to live until Ishan saw it.
- **The first card version spilled its opened details under the next cards** (the header was set to fill the card's
  height). Caught in the screenshot before committing.
- The PO click-through stopped on re-run because its test item already existed in the preview database (test data,
  not an app bug). It also showed duplicate supplier names were allowed; fixed.
**Follow-ups:** Step 6.3 (Import) waits until Ishan says go.

## #29 | 2026-11-26 15:55 UTC | "categorize Too Late, Order This Week and Order Soon into their own dropdowns"
**Prompt (simplified):** Before step 3, put Too late, Order this week and Order soon into their own dropdowns, each
holding its cards.
**What changed:**
- **`components/StatusGroup.tsx`:** one dropdown per status. The header shows the chip, the item count and a
  one-line meaning, and a coloured edge marks the section. Inside is the grid of cards.
  - Too late and Order this week start open (they need action this week); Order soon starts closed.
  - Cards inside a status dropdown don't repeat its chip.
- **Fix:** every dropdown now has its own named Tailwind group: card, section, disclosure, stuck, po, shipment and
  item. With the shared `group` from #28, closed cards inside an open section ("Everything else looks fine") showed
  "Close" and a turned arrow. That bug was live after #28 and is fixed here.
- ADR-025 updated.
**Impact:**
- **Section check (local and live):**
  - three sections in order: Too late (3, open), Order this week (6, open), Order soon (5, closed);
  - no card repeats its section's chip;
  - 31 closed cards all show "Details".
- **Bubble check still passes:** none appear when a card opens; hovering "cushion" shows only its own.
- Every page at 1280 px and 375 px has no errors and no sideways scrolling.
- The Monday, PO and shipment click-throughs pass locally, on a fresh database. 270 backend tests pass; the
  frontend build, lint and format are clean.
**Decisions made (and by whom):**
- Ishan: one dropdown per status.
- Claude: Too late and Order this week start open and Order soon closed; no repeated chips; Handled, Late or unknown
  and Fine stay as they were (below the three).
**AI mistakes caught or corrected:**
- **The #28 grid shipped a second shared-`group` bug.** Closed cards inside an open section looked open. Claude
  found it by listing every `group` use before nesting more dropdowns.
- **Two mistakes in Claude's own section check:**
  - it found chips by their rounded corners, but the stock bar is rounded too;
  - it compared against `undefined`, but values come back from the browser as JSON, where that becomes `null`.
  Both were fixed in the check; the app was right.
**Follow-ups:** Step 6.3 (Import) is next, when Ishan says go.

## #30 | 2026-11-26 18:40 UTC | "go": step 3, Import
**Prompt (simplified):** Start step 3 of Phase 6: imports from the website.
**What changed:**
- **Loader:**
  - `read_raw_bytes`, with upload checks: required columns per export, no empty files;
  - `write_load(use_copy=False)` for production, because its database connection has no COPY;
  - `load_runs.reference` keeps the seed CSVs from each load.
- **Migration 0004** (applied to Supabase; no drift; RLS on every table): `uploads`, `upload_files`, `stock_counts`,
  `stock_count_lines`, `app_sales_lines`, and the `load_runs.reference` column.
- **`services/import_service.py`** (BlueTide): upload into slots, then check, then load.
  - Empty slots reuse the last load's file, rebuilt from `raw_rows`.
  - Blockers: a stock count after today or older than the loaded one, missing files, no stored seeds.
  - Warnings: rows halved, the same files as last time.
  - The check also shows what would change, the cleanup count, and conflicts with Dana's records.
  - The load needs a one-time code. Stale running loads are marked failed first.
- **`services/template_import.py`** (Dana's own templates: suppliers, items, customers, stock count, POs, sales
  history): every row is checked, problems block the load with file and line, and the load is all-or-nothing.
  - **Planning:** her newest stock count is the starting stock for the items it lists when it's newer than
    BlueTide's; her sales history feeds the selling rate.
- **API:** `/imports` (start, PUT files, check, load, discard), `/import-templates/{slot}.csv`.
- **Data page** (replaces Data notes):
  - Load new BlueTide files, or Load your own spreadsheets;
  - slots with Choose file, template downloads, the check report, Load, Start over;
  - past imports;
  - the data notes fold away below.
- **Production:** migration 0004 applied; **one laptop load (run #6)** so production has a stored copy of the seeds.
  Same files, so the same numbers, and all five suppliers' settings were kept.
- Docs: ADR-029, A41–A45, CLAUDE.md (invariants 3 and 5, code map, playbook, commands), PRIORITIES (P0 #12 done),
  the data load report for run #6.
**Impact:**
- **Checks:** 278 backend tests pass (8 new import tests on the real data). Ruff, build, lint and format are clean.
  The raw files are unchanged.
- **Local click-through:**
  - BlueTide: upload the stock-on-hand file, check ("same files: nothing changes"), load; the numbers stay
    3/6/5/16;
  - templates: a bad items row is blocked with its line ("pounds per case is needed"); then suppliers, items and a
    stock count load, and KB-COD6 shows 120 cases from Gloucester Fillet Co.
- **Live:**
  - the BlueTide import of the real stock-on-hand file passes through production (load run #7, **6 seconds**), with
    the numbers unchanged;
  - every page has no errors and no sideways scrolling at 1280 px and 375 px;
  - the section and Monday click-throughs pass.
  The template path wasn't run on live, because it would add permanent test records.
- Screenshots: `docs/screenshots/phase6-step3/` (not committed).
**Decisions made (and by whom):**
- Ishan: "go".
- Claude:
  - template rows are all-or-nothing (A44);
  - imported POs whose arrival has passed load as late (A45);
  - sales history covers past sales only; open orders go on the Shipments page;
  - upload checks apply to website uploads only, so the laptop loader's behaviour is unchanged;
  - the data notes fold away on the Data page.
**AI mistakes caught or corrected:**
- **The new column check first applied to every read.** That broke a reader test that uses a tiny made-up file, so
  the check now applies to uploads only.
- **Format-skip markers again stopped the formatter from wrapping long lines.** Removed.
- **An edit to the API client didn't match after the formatter had reshaped it.** The edit's own check caught it and
  wrote nothing; it was redone directly.
- On re-runs, the PO click-through stops at "add supplier" because the import test had already added that supplier
  to the same preview database. That's test data: the app correctly refuses the duplicate name.
**Follow-ups:**
- **Step 6.4** (CSV downloads) is next, when Ishan says go.
- Known limits:
  - a brand-new install needs one laptop load for the buildings;
  - files over 4.4 MB must be split;
  - "today" is still fixed at Nov 16.

## #31 | 2026-11-26 19:05 UTC | "go": step 4, Download to Excel
**Prompt (simplified):** Start step 4 of Phase 6: CSV downloads.
**What changed:**
- **`services/export_service.py`** builds five CSVs from the same services as the screens:
  - the order list (every item, its status, run-out and order-by dates, how much to order, supplier, stock numbers);
  - the stuck list (one row per lot: problem, building, at Harbor, quantity, expiry, value at cost);
  - purchase orders (one row per line, yours and BlueTide's, with arrival and who set it);
  - shipments (one row per line, with the lots taken);
  - data notes (every change the loader made in the latest load, with file and line).
  All are UTF-8 with a BOM, with ISO dates, plain numbers plus a unit column, her words for statuses, and CRLF.
- **`api/v1/exports.py`:** `GET /exports/{list}.csv`, file named `kestrel-bay-<list>-2026-11-16.csv`; an unknown
  list is a plain 404.
- **Website:** a `DownloadLink` ("Download for Excel") next to What to order and What you're stuck with on Monday, and
  in the headers of Purchase orders, Shipments and Data.
- Docs: ADR-030, A46, PRIORITIES (P0 #13 done), CLAUDE.md (code map, playbook row for downloads).
**Impact:**
- **Checks:** 283 backend tests pass (5 new export tests on the real data). Ruff, build, lint and format are clean.
- **Local:** each link downloads its file in a headless browser; no sideways scrolling at 1280 or 375 px.
- **Live (version b37f46d):** all five downloads return 200 in 1–3 seconds, with a BOM. The order list's statuses
  match Monday (3 too late, 6 this week, 5 soon, 16 fine), SHR-1620 reads 480 can sell, 201 promised and 600 on the
  way, and SAL-POR6 has 1,050 cases at Harbor. The browser check passes on the live site too.
- Screenshots: `docs/screenshots/phase6-step4/` (not committed).
**Decisions made (and by whom):**
- Ishan: "go".
- Claude:
  - a download holds every row, not the filter on screen (A46);
  - one row per lot or line, so columns sum;
  - CSV rather than .xlsx (no new library; opens in Excel as is);
  - downloads aren't put in the activity log, because they change nothing.
**AI mistakes caught or corrected:**
- **Format-skip markers again.** The first draft packed several columns per line with `# fmt: skip`; they were
  removed before the first lint, and the formatter put one column per line. One long header line in the router was
  split by hand.
- A screenshot-stitching script failed because Pillow isn't installed for the system Python; each screenshot was
  checked on its own instead. No effect on the app.
- **Wrong log dates.** Entries #30 and #31 were first dated Nov 27 UTC. The laptop is on IST (UTC+5:30), so it's
  Nov 27 locally but Nov 26 in UTC. Both are corrected to real UTC (#30 from its commit time, 18:42 UTC).
**Follow-ups:**
- **Phase 6 is done.** Next, when Ishan says: the Harbor storage calculator (P1 #1), then the README and demo phase.
- Still open: Ishan to confirm the Vercel cron.

## #32 | 2026-11-26 19:30 UTC | "go": P1 #1, the Harbor storage cost calculator
**Prompt (simplified):** Start the next item, the Harbor storage calculator (Ishan's spec from prompt #17: Dana
types how many cases fit on a pallet; $30 per pallet per month; add rows to a table; export it as CSV).
**What changed:**
- **Rule** (`planning/storage.py`, pure): each lot on its own pallets, a part pallet charged whole, pounds turned
  into cases with pounds per case; no cost without her cases per pallet.
- **Settings:** `business_rules.harbor_pallet_cost_per_month` = 30 (Dana's reply) and `cases_per_pallet_max` = 1,000
  (a typo guard).
- **Migration 0005** (applied to Supabase; no drift; RLS on): `item_settings.cases_per_pallet` and
  `harbor_storage_rows`.
- **API:**
  - `GET /harbor-storage`;
  - `POST /harbor-storage/rows` (what's at Harbor now, or a what-if amount; worked out on the server; all or
    nothing; remembers her cases per pallet);
  - `DELETE /harbor-storage/rows/{id}`;
  - `PATCH /items/{code}/settings` accepts `cases_per_pallet`;
  - `/exports/harbor-storage.csv`.
  All writes are audited.
- **Website:** a new **Harbor** page (nav). It has a summary, one row per item (cases per pallet, a live cost, Save,
  Add to table), "Add all", "Work out another amount", and "Your table" with Remove and "Download your table for
  Excel". The Activity page has labels for the new actions. On a phone, the box, the cost and the button share one line.
- Docs: ADR-031, A16 updated, A47–A48, PRIORITIES (P1 #1 done; P1 #2 was done as P0 #13), CLAUDE.md (invariant 5,
  code map, playbook).
**Impact:**
- **Checks:** 292 backend tests pass (5 new unit and 4 new API tests). Ruff, build, lint and format are clean.
- **Local click-through:**
  - typing 60 for SAL-POR6 shows $540 a month (18 pallets);
  - Add to table; Save; Add all; a what-if (300 cases at 80 a pallet = 4 pallets, $120);
  - the download has every row; Remove works;
  - moving 450 cases of SAL-POR6 to New Bedford drops Harbor to 600 cases, 10 pallets, $300;
  - no sideways scrolling at 1280 or 375 px.
- **Live (version 50ab3ca):** the same click-through passes as "Claude (live click-through)". It removed its rows
  and cleared the cases per pallet it typed, so Harbor shows 0 saved rows and no remembered numbers again. Monday is
  unchanged at 3/6/5/16. What's left: three item-settings rows with every value empty (SAL-POR6, TIL-FIL, SHR-1620),
  and their audit entries.
- Screenshots: `docs/screenshots/p1-harbor/` (not committed).
**Decisions made (and by whom):**
- Ishan: "go"; the calculator's shape (prompt #17).
- Claude:
  - pallets are counted per lot, and a part pallet is charged whole (A47, flagged);
  - a what-if is worked out as one lot;
  - cases per pallet is remembered per item, including from a what-if;
  - the rate lives in `business_rules` (not `locations.csv`), so no reload was needed;
  - no "cost so far", because the received date isn't the date a lot reached Harbor (T30);
  - saved rows aren't totalled, because rows from different days would double count.
**AI mistakes caught or corrected:**
- **Two wrong numbers in my own tests.** I added up Harbor's cases as 1,975 by hand (the real total is 2,095) and
  called the audit endpoint `/audit` (it's `/audit-log`). The tests were fixed; the app was right.
- **A deletion in a test script.** The click-through script I first wrote emptied its downloads folder. The safety
  check blocked it, and it was rewritten to use a new folder per run. The older download-check script had the same
  line and was run once more before I noticed (it only touched my own scratch downloads); it's now fixed the same way.
- **The click helper failed on the fold-out heading,** because the heading also contains its arrow. Fixed.
- **Edits that didn't match.** Two find-and-replace edits missed because the formatter had reshaped the code (as in
  #30). Each edit's own check caught it, and they were redone.
- **The first phone layout was too tall:** the button wrapped under every row. The row was tightened.
**Follow-ups:**
- Next, when Ishan says: the README / DEMO_SCRIPT / final docs phase.
- Possible later: the Harbor $ a month beside each Harbor lot on Monday's stuck list; a rate per warehouse if there's
  ever more than one.
- Still open: Ishan to confirm the Vercel cron.

## #33 | 2026-11-26 19:55 UTC | "go, how do I confirm the vercel cron": the final docs phase
**Prompt (simplified):** Start the README / demo / final docs phase (BUILD_PROMPT §14's last phase), and explain how
to confirm the Vercel cron.
**What changed:**
- **The cron, confirmable from our own log:**
  - calls with Vercel's `vercel-cron/…` User-Agent and no X-Actor are now logged as actor **"Vercel cron"**
    (`middleware.actor_for`, with a test);
  - `scripts/check_cron.py` lists the last ten.
  - Before this change, nothing could prove the cron had fired: every request without a name was logged as "Dana",
    and the user agent isn't stored. There were two unnamed health calls on Nov 26 in the 12:00 UTC hour, but my own
    curl checks look the same.
- **README.md**, the full submission per §13.5:
  - what it does and why, with three live screenshots in `docs/images/`;
  - the live link and one minute of use;
  - what's on each page;
  - how it works (a Mermaid diagram, parsed and rendered with Mermaid 11 to check it);
  - key assumptions, and the answer-key comparison explained;
  - data problems (4,047 notes);
  - out of scope (updated for Phase 6), next steps and the scale path;
  - how AI was used, with nine real mistakes and how each was caught;
  - local setup, tests and deploy;
  - a docs map.
- **docs/DEMO_SCRIPT.md** (new): 10 minutes for Dana, with every number read from the live site and every button
  label checked in the code, plus "before the demo", undo steps and "if something goes wrong".
- **docs/DECISIONS.md**:
  - every ADR now has Context, Decision, Alternatives, Tradeoffs and Revisit when, plus who decided;
  - ADR-001 and 003–016 were written out from BUILD_PROMPT §13.3 and the code, and 022, 024–031 were completed;
  - there's an index table at the top;
  - ADR-030's date was corrected.
  The first draft was written by a parallel Claude helper and spot-checked (claims sourced, no decision changed, only
  placeholders removed).
- **ASSUMPTIONS:** A18 no longer says the late calamari PO gets an ETA (since Dana's reply it isn't counted until she
  types a date).
- **CLAUDE.md:** a playbook row for "pretend today is a different day" (`AS_OF_DATE`), and `check_cron.py` in the map.
**Impact:**
- **Checks:** 293 backend tests pass. Ruff, build, lint and format are clean.
- **Live (version d5b106d):**
  - the smoke test passes as "Claude (final smoke test)": mark handled and clear it, set a PO date and clear it, data
    notes with file and line, 6 activity entries. Both test edits were reversed;
  - all 12 pages have no errors and no sideways scrolling at 1280 or 375 px;
  - all five downloads work;
  - Monday is unchanged at 3/6/5/16.
- The lead-time edit was skipped on live, as in earlier phases, because it would overwrite the source note on a
  supplier Dana confirmed. It's covered by the API tests and the local click-through.
**Decisions made (and by whom):**
- Ishan: "go".
- Claude:
  - the README lists nine AI mistakes from the log, each with how it was caught;
  - the demo script undoes everything it changes;
  - the diagram reads top to bottom (narrower on GitHub);
  - cron calls are named in the request log rather than adding a user-agent column (no migration).
**AI mistakes caught or corrected:**
- **Guessed labels and timestamps in the first demo script draft:**
  - "Details" (the link is "See why and all the numbers");
  - "Clear" (it's "Clear this note");
  - quote times 00:13 and 00:05 (they're 00:11:00 and 00:04:40);
  - SAL-POR8 called fully expired (only its 60-case lot is).
  All were checked against the code, the transcript and the live data, then fixed.
- **Three wrong README claims, caught the same way:**
  - business rules "shown to Dana" (only through the API; no page uses them);
  - "Shipments moves stock" (moves are on the item page and the stuck list);
  - "order at least" described loosely.
  The answer-key paragraph also overclaimed ("every other difference comes from two decisions"); SHR-1215 is a
  this-week boundary case, now said plainly.
- **The first diagram's box titles were cut off** in the render. Shortened.
**Follow-ups:**
- **Cron:** after 12:00 UTC on Nov 27, run `cd backend && source .venv/bin/activate && python ../scripts/check_cron.py`,
  or look at Vercel → Project → Settings → Cron Jobs.
- **Screenshots:** `docs/screenshots/` (all phases) is still uncommitted; only the three README images are in the repo.
- Then P1 items as Ishan chooses, or the review.

## #34 | 2026-11-26 (claude.ai) | Ishan's scope review: BlueTide stays the record
**Prompt (simplified):** Ishan reviewed the app in claude.ai after Phase 6, from a zip of the repo, and felt it had
drifted from what Dana needs and become too complicated.
**What changed (the conclusions, decided by Ishan):**
1. **The app had become a second system of record.** POs, receipts, shipments, picks, moves and template imports were
   recorded in the app and in BlueTide. That needed matching rules R1–R10, 12 extra tables and assumptions A27–A45. It
   also meant double data entry for Dana's team, which nobody on the kickoff call asked for.
2. **Fully replacing BlueTide was considered and rejected.** BlueTide also does Marco's order entry, accounting's
   credits, warehouse receiving, transfers and invoicing. Replacing only part of it leaves the client on two systems,
   and replacing all of it is an ERP migration.
3. **Decision: BlueTide stays the system of record, and the app replaces Dana's Monday spreadsheet.** Every Monday she
   uploads the exports, everything recalculates, and the app stores only what BlueTide doesn't know. Moving off
   BlueTide becomes a README roadmap item, done one job at a time, with each kind of record owned by exactly one
   system.
4. **The "why" text becomes a numbers-only breakdown,** because the sentences read like a memo. They aren't pre-written
   (see #35).
**The six boundaries (to go into CLAUDE.md):**
- BlueTide owns every fact (stock, sales, POs, receipts), from uploaded files only; the app never records a
  transaction.
- The app stores only Dana's knowledge and the logs.
- Each upload refreshes BlueTide's data, and sales lines accumulate.
- "Today" follows the data: the latest load's snapshot + 1 day, with `AS_OF_DATE` as an override only.
- The math is deterministic, with no LLM anywhere.
- No order entry, receiving, shipping, stock moves, or adding customers, items or suppliers in the app.
**Impact:** a five-step plan (#36): archive and cut; weekly uploads; numbers-only "why"; docs and deploy.
**Decisions made (and by whom):** Ishan, all of the above.
**AI mistakes caught or corrected:** The system-of-record expansion doubled the rules and Dana's data entry. Caught by
Ishan.
**Follow-ups:** #36.

## #35 | 2026-11-26 (Ishan, terminal) | Are the "why" explanations pre-written?
**Prompt (simplified):** Ishan worried the item explanations were hard-coded for the demo items, and checked:
`grep -rn "SHR-2125\|562\|Nov 24" backend/app frontend/src`.
**What changed:** nothing.
**Impact:** The only hit was a false positive: "562" inside the colour `#55626c`. `explain.py` is shared templates
filled from live numbers, so no item's text is pre-written. The sentences are still being replaced with a
numbers-only breakdown (#36, step 4), because they read like a memo.
**Decisions made (and by whom):** Ishan: verify, then replace the sentences anyway.
**AI mistakes caught or corrected:** none (it was a verification).
**Follow-ups:** #36, step 4.

## #36 | 2026-11-26 20:08 UTC | "Read this whole message ... plan mode": cut to the weekly planning layer
**Prompt (simplified):** Ishan's plan, in five steps, each ending in a STOP:
1. Read the code and post a plan.
2. Archive the current state on `archive/system-of-record`, then cut everything that records transactions (12
   tables, the matching rules, the PO/shipment/template screens).
3. Make weekly uploads work: derived "today", handled-note dates, sales that accumulate, import checks, raw-row
   retention, computed season bands.
4. Replace the "why" sentences with a numbers-only breakdown and one instruction for late-PO items; add a
   reconciliation test.
5. Docs, deploy and log.

He asked two questions in the plan: (a) the instruction's wording; (b) the retention count.

### Step 1: plan (plan mode; approved without changes)
**What I checked** (read-only; full list in the approved plan):
- **Live data in the 12 tables:** only test records from "Claude (live click-through)": PO KB-00001 (cancelled),
  order SH-00001 (cancelled), and 8 stock movements (a receipt, a pick and a Harbor→New Bedford move, each with its
  undo; they net to zero). App items, suppliers, customers, stock counts and sales are empty.
- **Ishan's list missed some pieces:**
  - `app_shipment_prefix`;
  - the `AppVendor` merge in GET/PATCH `/vendors`;
  - `AppItem` in `resolve_item_code`;
  - app POs in the handled hint;
  - `POLineInput.source/flags`;
  - the import's R4/R7 conflict checks;
  - `PORow`, three status chips, the item page's move and stock-changes parts, and "Add a supplier".
- **The handled-note date bug is real** (`build_context` dates notes with `rules.as_of_date` when it reads them).
- **A load must use the new files' snapshot + 1 day as "today",** because the loader uses AS_OF for expiry, stale PO
  dates and dormant items.
- **Raw rows don't record which load first brought them in.** Step 3 adds `origin_load_run_id`.
- **Storage:** 47 MB of raw rows for 5 loads (about 9.4 MB per load).
- **The sales merge key works:** order_no + line_no is unique across 15,750 rows, and the history is about 12.5 months.
- **A chart bug:** the item chart plots the plain balance, so after a stockout it shows SHR-1620 at about 218 cases
  instead of about 590 when the Jan 25 PO lands. It's fixed in step 4, and the reconciliation test includes lost
  sales.
- **Vercel:** Ishan should check that `AS_OF_DATE` isn't set there, because it would pin "today".
**Decisions made (and by whom):**
- Ishan approved the plan as written:
  - (a) the default instruction wording, with variants for "order at least 0" and several late POs;
  - (b) keep 8 loads of raw rows, and clear older uploads' file bytes;
  - deploy at the end of each step, in an order that never breaks live.

### Step 2: archive, then cut (approved plan; STOP after)
**What changed:**
- **Archive:** tag `archive/system-of-record` on 0796817, pushed before anything was deleted.
- **Backend, removed:**
  - `planning/records.py`, `services/records_service.py`, `shipments_service.py` and `template_import.py`;
  - `api/v1/shipments.py`;
  - the PO write routes, the stock-movement undo, `/locations`;
  - `/item-details`, `POST /items`, `PATCH /items/{code}/details`, `POST /vendors`, `/import-templates`;
  - `app_po_prefix` and `app_shipment_prefix`;
  - `POLineInput.source/flags`;
  - the import's checks against Dana's own records.
- **Backend, changed:**
  - `GET /purchase-orders` = BlueTide's open lines as the plan counts them (`planning_service.on_the_way`), searchable;
  - the PO-date PATCH looks the line up in the clean layer: 404 if missing, 409 if fully received or cancelled, 422
    for a past date, audited as before;
  - `build_context` = the cached clean layer + vendor/item settings, PO dates and handled notes;
  - item-page lots come from BlueTide's rows;
  - `IncomingLine` carries `po_no` and `line_no` (no more parsing "PO-x line n");
  - the PO export = open BlueTide lines with our date, BlueTide's date and the late flag; the shipments export is
    gone;
  - the import check warns about open handled notes on items the new files drop.
- **Models and migration:**
  - 12 models removed; `APP_LAYER` = vendor_settings, item_settings, po_eta_overrides, handled_flags,
    harbor_storage_rows, uploads, upload_files;
  - `uploads.kind` = 'bluetide' only;
  - **migration 0006** drops the 12 tables. Its downgrade re-creates them empty from 0002/0003 and 0004's
    definitions (both directions rendered offline before running).
- **Website:**
  - removed: NewPOPage, NewShipmentPage, ShipmentsPage, ItemsPage, MoveStockDialog, ShipmentRow, PORow, three
    chips, "Create a PO", "Move to New Bedford", the item page's moves and stock changes, the template import, and
    "Add a supplier";
  - **On the way** (`/on-the-way`; `/purchase-orders` redirects): late lines first, our date vs BlueTide's, Set real
    date / Change date, Download for Excel;
  - nav: Monday · On the way · Suppliers · Harbor · Data · Activity;
  - Activity keeps the labels of removed actions so the old audit rows still read.
- **Tests:**
  - deleted `test_records.py` and `test_shipments.py`;
  - `test_purchase_orders.py` is now 4 read-only tests: the open list matches the clean layer, search, a real date
    moves a late line into the counted ones, the cut routes are gone;
  - the import tests check that Dana's date, note and pallet number survive a reload;
  - the export tests cover the new PO file;
  - `test_invariants` follows dropped tables and guards against their return.
**Impact:**
- **Checks:** 226 backend tests pass (was 293; 67 went with the cut features). The 20 golden tests (G01–G17) pass.
  Ruff, build, lint and format are clean, and the raw-file checksums match.
- **Regression, local and live:**
  - Monday **3 / 6 / 5 / 16**, 0 handled, **3 late POs, 1,500 cases**;
  - SHR-1620 **480 can sell, 201 promised, runs out Dec 14**;
  - 14 open lines on the way, 3 of them late.
- **Order on live:**
  - pushed and waited for version eb7f15a;
  - rechecked the 12 tables (unchanged: only the test records);
  - ran **0006 on Supabase**, then `alembic check`: no drift, and none of the 12 tables is left.
- **Live smoke test:**
  - 10 pages (8 screens plus 2 old links that redirect) with no errors and no sideways scrolling at 1280 or 375 px;
  - mark handled and clear it; set a PO date from Monday and clear it; set and clear a date on On the way;
  - data notes with file and line;
  - Activity rows.
- Screenshots: `tmp/shots/live-cut/` (not committed).
**Decisions made (and by whom):**
- Ishan: the cut list and the plan.
- Claude:
  - On the way lives at `/on-the-way`, and old links redirect;
  - the PO-date 409 says "fully received" or "cancelled";
  - Activity keeps the old action labels;
  - the import check keeps one useful warning (notes on dropped items).
**AI mistakes caught or corrected:**
- **The router registry still imported the deleted `shipments` module.** The first `import app.main` failed on it,
  and it was fixed before any test ran.
- **The Harbor page still told Dana to "add pounds per case on the Items page",** a page that no longer exists.
  Caught by a grep for removed features; it now says the pounds per case comes from BlueTide's item file.
- **My pre-drop check counted every line row as "not by the test user".** The line tables have no author column.
  They were the line rows of the test PO and order, as the plan check had shown, so nothing new was there.
- Two lines over the length limit after edits (fixed); the type checker then listed the screens still using cut
  hooks, and each was fixed.
**Follow-ups:** step 3 (weekly uploads) when Ishan says go. **Ishan:** check that `AS_OF_DATE` isn't set on Vercel.

### Step 3: make weekly uploads work ("go"; STOP after)
**What changed:**
- **"Today" follows the data:**
  - `settings.as_of_date` is an optional override (blank = follow the data);
  - `business_rules.rules_for_snapshot` = the stock count + 1 day, cached per snapshot;
  - every router uses `api/deps.request_rules` (the latest load), and health derives it from its own DB check, so it
    still answers when the database is down;
  - the laptop loader and the import's check and load work out "today" from the **uploaded** stock file
    (`pipeline.snapshot_date_of`), so expiry, late POs and dormant items are judged as of that week;
  - the header shows "Monday, November 16, 2026 · BlueTide stock count of Sun Nov 15";
  - with today's data, AS_OF is still 2026-11-16;
  - the tests stopped pinning `AS_OF_DATE`, so the API tests exercise the derivation;
  - `backend/.env`'s `AS_OF_DATE` line was commented out (only that line) and `.env.example` documents it as
    optional.
- **Handled notes:**
  - `handled_flags.created_on` (migration 0007; the 9 existing notes backfilled with 2026-11-16) is set from AS_OF on
    create;
  - the engine gets it, instead of re-dating every note to "today";
  - the "BlueTide now shows PO-x" hint compares each PO's order date with the note's own day.
- **Sales accumulate:**
  - `loader/accumulate.merge_sales` (pure) merges by order + line: the new file wins, and older lines it no longer
    lists are kept;
  - `loader/history.raw_file_from_run` reads the previous load's rows back with their origin;
  - `raw_rows.origin_load_run_id` (0007; 82,710 rows backfilled) and `SourceRef.origin` keep every carried-over line
    traceable;
  - data notes on those lines name their load ("bluetide_sales_lines.csv (load #1)");
  - the check reports new / changed / same / kept, and warns under a year of history (the existing
    `seasonal_window_days`, not a new number);
  - the laptop loader merges the same way; a dry run can't, and says so.
- **Import checks:** "stock count after today" is gone; "older than the loaded one" still blocks; a same-night count
  warns; the check shows "Loading them makes today Mon Nov 23".
- **Retention:**
  - `raw_rows_keep_loads = 8`;
  - `write_load(keep_loads=)` deletes old data notes and then raw rows inside the load transaction, and clears old
    uploads' file bytes (`upload_files.content` nullable in 0007);
  - the run's summary lists the pruned loads; load runs stay;
  - both the laptop loader and the import pass it.
- **Season bands:** `planning/calendar.easter` (anonymous Gregorian) and `season_markers(start, end)`; the fixed
  `business_rules.season_markers` is gone.
**Impact:**
- **Checks:** 238 backend tests pass (12 new). They include:
  - Lent 2027 = Feb 10–Mar 28 and Lent 2028 = Mar 1–Apr 16;
  - "today" derived, overridden, or with no load;
  - next week's count makes today Mon Nov 23, and the load used it;
  - recent-weeks-only sales keep the history: same line count, rate, season and Monday, and the kept lines trace to
    load #1;
  - an OPEN line now INVOICED updates without duplicating, plus one new line: SHR-1620's promised goes 201 → 91;
  - the under-a-year warning;
  - a note's business day and the hint;
  - retention keeps exactly the newest 2 of 3 loads' raw rows and notes, all summaries, and clears the old upload's
    bytes.
  Ruff, build, lint and format are clean, and the raw-file checksums match.
- **Local browser check:**
  - uploading this week's stock + sales files: the check says today stays Mon Nov 16, 15,750 sales lines the same,
    and warns about the same night; loading it leaves Monday unchanged at 3/6/5/16;
  - then next week's stock count (a scratch copy with dates +7): the check says today becomes Mon Nov 23; after
    loading, the header and dashboard say Monday, November 23, 2026;
  - every page has no errors and no sideways scrolling.
- **Live:**
  - ran **0007 on Supabase first** (additive; no drift), then pushed;
  - version 98e995b: health as_of 2026-11-16 with snapshot_date 2026-11-15; Monday 3/6/5/16, 3 late POs (1,500
    cases); SHR-1620 480 / 201 / Dec 14; chart bands Christmas and Lent 2027;
  - the page sweep and the edit click-through pass;
  - **an upload check ran on production** (stock + sales files: today stays Mon Nov 16, 15,750 the same,
    same-night warning) and was discarded with "Start over", so nothing was loaded.
**Decisions made (and by whom):**
- Ishan: the step as planned, retention 8 with upload bytes cleared.
- Claude:
  - health derives "today" without a request session;
  - carried-over data notes name their load in the file column;
  - "under a year" reuses `seasonal_window_days`;
  - never-loaded uploads older than the oldest kept load also lose their bytes.
**AI mistakes caught or corrected:**
- **A hard-coded "12 months"** in the first import-check draft would have broken invariant 3 (numbers live in
  `business_rules`). Replaced with the existing `seasonal_window_days` before any test ran.
- **A wrong assertion in my own test:** it expected a sales summary in a check that uploaded no sales file. Fixed the
  test; the app was right.
- **`Path.read_text(newline=...)` is Python 3.13+,** and the backend runs 3.12, so a test helper failed. It now reads
  bytes and decodes them.
- **The `.env.example` invariant test only counted uncommented keys,** so documenting `AS_OF_DATE` as an optional,
  commented example failed it. The test now accepts commented examples; its intent (every setting documented) stands.
- **An edit didn't apply** because the formatter had already wrapped the target line. The edit's check caught it and
  wrote nothing, and the code was already right.
- **I ran the checksum command from the wrong folder,** which reported 18 files missing. Re-run from the repo root:
  all match.
**Follow-ups:**
- Step 4 (numbers-only "why") when Ishan says go.
- **Ishan:** check Vercel for `AS_OF_DATE`. Live shows Nov 16 either way today, so I can't tell from outside whether
  it's set.

### Step 4: numbers-only "why" ("go"; STOP after)
**What changed:**
- **`planning/explain.breakdown`** replaces `explain()`. It returns `BreakdownRow`s {key, label, qty, unit, date,
  detail, link}, built from the same values the engine used, only the rows that apply:
  - can sell (by building);
  - not counted;
  - promised (orders, ship span, largest);
  - each counted arrival (our date, plus BlueTide's when corrected);
  - each late PO;
  - selling per week (last 8 weeks);
  - season ahead (next 3 months);
  - runs out;
  - new order lands;
  - short (too late only);
  - order at least (a past order-by date reads "order now (was due …)");
  - if the late PO arrives today.

  `link` points at the item-page table with the source rows (`#have`, `#promised`, `#on-the-way`, `#late`, `#demand`,
  `#chart`). `ItemDetailOut.breakdown` replaces `explanation`.
- **`late_po_instruction`**, the one sentence for items only a late PO would cover (Ishan's wording, with the "0 to
  order" and several-PO variants). It's on `ItemCard.instruction`, the Monday card and the item page, and replaces
  the two lines that contradicted each other.
- **The chart uses the floored balance:** lost sales are lost. SHR-1620 now lands at 594 cases on Jan 25, not about
  218. Run-out and status are unchanged.
- **Item page:** the "Why" card is a compact table (label linking to its table, quantity, date, note), with the
  instruction on top, and the anchors are on the cards.
- **Monday cards** opened: short labels only (runs out, order by, order at least, new order lands, short, on hold,
  late POs) plus the instruction. The paragraphs are gone.
**Impact:**
- **Checks:** 269 backend tests pass (31 new), including:
  - SHR-1620's ten rows, value by value;
  - the three live instructions (SHR-2125, CAL-RING, PAN-0709) and the several-PO wording;
  - a past order-by date reading "order now";
  - **the reconciliation on the real data: can sell − promised (shipping by X) + counted arrivals (by X) − forecast
    (through X) + lost sales (through X) = chart stock**, for SHR-1620, LOB-T56, SAL-POR6, CRAB-SNW5 and SHR-2125 on
    days 0, 7, 30, 60 and 120;
  - with no stockout (SAL-POR6) the loss is 0;
  - SHR-1620's chart is at 0 the day before its PO and about 594 on Jan 25.
  Ruff, build, lint and format are clean, and the raw-file checksums match.
- **Local and live (version f842a35):**
  - the breakdown and Monday-card checks pass at 1280 and 375 px, and every breakdown link has a target;
  - the page sweep and edit click-through pass;
  - Monday is 3/6/5/16 with 3 late POs (1,500 cases); SHR-1620 is 480 / 201 / Dec 14, short 382 until Jan 25;
  - the three instructions show.
  No migration was needed.
**Decisions made (and by whom):**
- Ishan: the breakdown fields, the rows, and the instruction wording (a).
- Claude:
  - the engine's row field is `on` (the API's `date`), because a field named `date` would shadow its own type in
    Pydantic;
  - building codes (NB, PVD, HCS) in the can-sell note, because the engine has no names;
  - "order at least" shows the order-by date when it's still ahead;
  - the chart fix (found while planning, approved with the plan).
**AI mistakes caught or corrected:**
- **A past order-by date in the date column.** My first draft put SHR-2125's order-by date, Tue Aug 18 (long past),
  in the "Order at least" row's date column. Caught reading the printed rows before writing any test; now the date
  is blank and the note says "order now (was due Tue Aug 18)".
- **An edit missed** because the formatter had already wrapped the target line. Its check caught it, nothing was
  written, and the code was already right.
- **Four existing tests matched sentence text** ("Only covered by the late PO", "You can sell 480 cases now"). They
  now assert the rows and the instruction. That was expected, but it's noted here because it's where a silent
  regression would have hidden.
**Follow-ups:** step 5 (docs, deploy, log) when Ishan says go. **Ishan:** still check Vercel for `AS_OF_DATE`.

## #37 | 2026-11-26 21:12 UTC | "what do u need me to check and where on vercel"
**Prompt (simplified):** What exactly should Ishan check on Vercel, and where?
**What changed:** nothing (an answer).
**Impact:**
- Ishan checks Vercel → the project → Settings → Environment Variables for `AS_OF_DATE`, in every environment
  (Production, Preview, Development).
- If it's there, delete it and redeploy, because env changes apply only to new deployments.
- Why: since step 3 "today" follows the data (the latest stock count + 1 day), and `AS_OF_DATE` is an override that
  would freeze it. Live shows Nov 16 either way today, so it can't be told from outside.
- Expected variables: `DATABASE_URL` (the transaction pooler, port 6543) and `APP_ENV=production`; nothing else is
  needed.
**Decisions made (and by whom):** none yet (Ishan to check).
**AI mistakes caught or corrected:** none.
**Follow-ups:** step 5 when Ishan says go.

### Step 5: docs, deploy, log ("go do step 5"; STOP after)
**What changed:**
- **DECISIONS:**
  - **ADR-032** "BlueTide stays the record; the app is the weekly planning layer": the scope-review context, the six
    boundaries, the cut list (archived on the tag), the rejected alternatives (keep Phase 6; replace BlueTide; a live
    connection), the tradeoffs, and "Revisit when Kestrel Bay asks to retire BlueTide";
  - **ADR-033**: the numbers-only why, one instruction, a chart that writes off lost sales;
  - ADR-026/027/028 marked **superseded** and ADR-029 **narrowed** (not deleted);
  - ADR-003/020/030 carry update notes; the index and status note are updated.
- **ASSUMPTIONS:**
  - A27–A40 and A43–A45 are "Retired (ADR-032)" (17 rows);
  - A42 is revised for the new checks (older blocks, same night warns, newer moves today);
  - A46 is updated (no shipments file);
  - new **A49** (derived today), **A50** (sales accumulation), **A51** (raw-row retention);
  - the stale "assume a week" note under A18 is fixed.
- **PRIORITIES:**
  - P0 #10 and #11 → "Cut, archived on `archive/system-of-record`";
  - #12 → weekly BlueTide uploads only;
  - #13 → done (open PO lines and the Harbor table, no shipments);
  - #4 → the numbers-only why;
  - P2 now lists "recording transactions in the app" and "replacing BlueTide" with reasons.
- **CLAUDE.md** (rewritten):
  - the six boundaries;
  - invariant 5's table list and retention;
  - the code map (deps, accumulate, history, calendar, explain), commands and deploy order (additive migrations
    before the push, drops after; no `AS_OF_DATE` on Vercel);
  - the playbook: the PO/shipment/template rows removed; rows for the why, the instruction, the sales merge and
    retention; the AS_OF row says "derived; `AS_OF_DATE` overrides";
  - "Decisions already made": ADR-026 marked superseded.
- **README** (rewritten):
  - **What I built** (the weekly loop: upload, look, adjust, order);
  - the one-minute tour using the breakdown and the SHR-2125 instruction;
  - the pages;
  - a new diagram (with the sales merge and "today = the stock count + 1"; parsed and rendered with Mermaid 11);
  - **What I cut and why**;
  - **Roadmap off BlueTide** (purchasing first, then sales and receiving, BlueTide retired last, each record owned by
    one system at a time);
  - assumptions A49–A51;
  - out of scope;
  - the AI section, which now leads with the scope expansion Ishan caught and adds the chart bug;
  - four fresh live screenshots (Monday, SHR-1620, On the way, Harbor).
- **DEMO_SCRIPT** (rewritten):
  - the PO, shipment and move steps are gone;
  - new: the SHR-1620 card labels and the Why table with its links, and the SHR-2125 instruction with "Set real date"
    on On the way;
  - verified on the real data: with Dec 4 it's still too late but **short 123 until Dec 4** instead of 562 until
    Feb 8, and order at least is 0;
  - the Monday upload (check, then Start over).
**Impact:**
- **Deploy:**
  - migration 0006 ran on Supabase in step 2 and 0007 in step 3 (both through the session pooler), so step 5 is docs
    only;
  - the live version is **be1fa8b**: health as_of 2026-11-16, snapshot 2026-11-15.
- **Live smoke test (actor "Claude (final smoke test)"):**
  - Monday **3/6/5/16**, 0 handled, 3 late POs (1,500 cases);
  - SHR-1620 **480 / 201 / Dec 14**;
  - all 12 pages: no errors and no sideways scrolling;
  - **set and cleared a real PO date** on Monday, on the item page and on On the way, audited as `po_eta.set` /
    `po_eta.clear`;
  - **an upload check ran** (today stays Mon Nov 16, 15,750 sales lines the same, same-night warning) and was
    discarded.
- Tests are unchanged from step 4: 269 pass.
**Decisions made (and by whom):**
- Ishan: the step 5 list.
- Claude:
  - ADR-033 as its own record (the code already referred to it);
  - README screenshots: On the way in place of the second Harbor image, with Harbor kept;
  - the demo's upload step checks and then discards, rather than loading.
**AI mistakes caught or corrected:**
- **A made-up number.** The first ADR-032 draft said "about 4,000 lines" were cut. I measured it before committing:
  8,070 deleted and 627 added. Corrected.
- **The README misquoted Ishan.** Its first draft put "an ERP system Dana can log her work in" in quotation marks,
  but those weren't his words (#24). It's now a paraphrase. It also said "19 assumptions" when 17 were retired
  (A41/A42 survive). Fixed.
- **A wrong button label.** The demo script said to click "Clear" next to a date; the button is "Clear date".
  Checked against `SetPoDate.tsx` and fixed.
- **A refused write.** The README rewrite was refused because I had edited the file with a script after reading it.
  I re-read it (it was my own last version, nothing else) before writing.
**Follow-ups:**
- **Ishan:** check Vercel → Settings → Environment Variables for `AS_OF_DATE` (see #37). Still unreported.
- `docs/screenshots/` (per-phase screenshots) and `codebase.zip` are untracked and not committed.
- After that: P1 items as Ishan chooses, or the review.

## #38 | 2026-11-26 21:30 UTC | "It isn't there, do we need to commit the screenshots, you can commit. What do you mean by P1 work of choosing or review?"
**Prompt (simplified):** `AS_OF_DATE` isn't set on Vercel. Should the screenshots be committed? What did "P1 work or
the review" mean?
**What changed:**
- **Vercel confirmed clean:** no `AS_OF_DATE`, so "today" follows the data in production too (boundary 4). Nothing to
  do. That closes #37's follow-up.
- **`docs/screenshots/` is now in `.gitignore`, not committed:**
  - it's 72 images, 36 MB, against a 7.8 MB repo history, and every Vercel deploy clones the repo;
  - many show screens that were cut;
  - the README's four screenshots are already committed in `docs/images/`.
  - The prompt log already marks those folders "(not committed)".
**Impact:** `git status` is clean. No app change.
**Decisions made (and by whom):** Ishan left the screenshots to Claude; Claude chose to ignore them rather than commit
them, offering a small before/after set for the review if wanted.
**AI mistakes caught or corrected:** "P1 work of your choosing or the review" was jargon without explanation; it's now
explained (P1 = the next-priority list in docs/PRIORITIES.md; the review = Nammu's live walkthrough).
**Follow-ups:** Ishan picks: P1 items, review prep, or both.

## #39 | 2026-11-27 05:56 UTC (logged) | "This has to be a system that Dana can check any day ... use a real calendar ... Boston timing"
**Prompt (simplified):** Use a real calendar in Boston time, so Dana can check the app on any day. What are the
implications, and what has to change? Example: if she uploads nothing for 3 weeks and an item says "order by Nov 22",
it must say it's overdue or out of stock, with an urgent indicator.
**Ishan's answers (plan mode):**
1. Stale stock: show **both** the count as BlueTide reported it and an estimate for today.
2. POs due since the last count: **don't count them**.
3. Urgency: **red, new statuses**.
4. The assignment's Nov 16: an in-app **"view as of"** switch.
Plan approved. This is step 1 (build, deploy, STOP); step 2 (docs) waits for "go".
**What changed (commits 8077988, b96ed15, b735186):**
- **Two dates (ADR-034, to be written in step 2):**
  - *Today* = Boston's calendar date (`config/clock.py`, the one clock read; `America/New_York`, with `tzdata` in
    requirements for Vercel); `AS_OF_DATE` still overrides it for tests and demos;
  - *data date* = the day after BlueTide's count, where the projection starts.
  - Measured to the data date: the selling rate, the season pattern and "late" POs (A18).
  - Judged against today: statuses, order-by, when a new order lands (today + lead time), expiry, the six-month line,
    and the validation of Dana's dates.
- **The estimate between them:** the count − expected sales − scheduled customer orders, with sales lost while out of
  stock written off. The chart starts today. Cards and the item page show both "At the count (Sun Nov 15)" and "Can
  sell now (estimated)" (whole units, so the rows add up exactly).
- **New red statuses:**
  - **Out of stock** (the estimate is gone by today) and **Overdue** (the order-by date has passed, but an order
    today still lands in time), ranked Out of stock > Too late > Overdue > Order this week > Order soon;
  - Monday groups and tiles (shown only when non-zero); "Overdue by N days"; "Out of stock since about Tue Nov 24";
  - the headline leads with them;
  - status words in the download.
- **Supply:** a PO due between the data date and today is not counted ("Due since your last upload"), and neither is a
  date Dana set that has passed ("Your date has passed"). Both are flagged on Monday and on On the way.
- **View as of:**
  - a date control in the header, limited to the data date through today, kept for this browser tab only;
  - it sends `X-As-Of` on every call, and downloads add `?as_of=`;
  - a yellow "Viewing as of … · Back to today" strip; edits are judged against the viewed day;
  - an out-of-range date gets a plain-English 422.
- **Freshness:** the header reads "BlueTide count of Sun Nov 15 (12 days ago)". There's a yellow banner after 7 days
  and a red one after 14 (`stale_data_days`, `very_stale_data_days`), with a link to "Upload this week's files".
  Health reports `data_date`, `days_since_count` and both thresholds.
- **Uploads:** a load describes its files as of their own data date (`rules_for_load`). A count dated after Boston's
  today is blocked. The check now says "Loaded, the numbers start from Mon Nov 16" (it used to say "makes today").
- **Tests:** 274 → 327. New:
  - engine (`tests/unit/planning/test_real_calendar.py`): Ishan's 3-week example, the estimate, POs due since,
    expiry in the gap, no change with no gap;
  - reconciliation extended over an 11-day gap on the real data;
  - API (`tests/api/test_real_calendar.py`): today vs the Nov 16 view, the 422s, downloads, edits judged against the
    view, health.
  - Clock tests: Boston vs UTC at midnight, and the DST changeover.
**Impact (real data, count of Sun Nov 15):**
- **Today, Fri Nov 27:** 1 out of stock (SHR-2125, since about Nov 24), 5 too late (+CRAB-SNW5, LOB-MEAT, SCL-U10),
  7 overdue (HAD-FIL 6 days, SAL-SIDE-SK 10, SHR-1215 7, CAL-RING 5, POL-FIL 2, SAL-CHO6 3, LOB-T810 3),
  3 this week, 7 soon, 7 fine.
- **Viewed as of Mon Nov 16:** 3 too late, **1 overdue (LOB-MEAT: order by Nov 13)**, 5 this week, 5 soon, 16 fine.
  It used to be 3 / 6 / 5 / 16: LOB-MEAT moved from "Order this week" to the new red "Overdue", because its order-by
  date was already 3 days past. Every golden fact (G01–G17) still holds.
- **Simulated 3 weeks (override Dec 7):** 3 out of stock, 9 too late, 5 overdue, and a red banner. Ishan's "order by
  Nov 22" item on the real data (CAL-RING) reads **Too late**, because its 12-week lead time can't land in time any
  more. The synthetic test with a longer cushion shows "Overdue by 15 days".
- **Live (b735186), checked 2026-11-27 ~06:00 UTC:**
  - health shows `as_of` 2026-11-27, so Vercel reads Boston's date;
  - Monday today and as of Nov 16 match the numbers above, at 1280 and 375 px, with no errors and no sideways scroll;
  - `X-As-Of: 2026-11-15` → 422; the download with `?as_of=2026-11-16` is named for Nov 16;
  - PO-260444 shows "Due since your last upload: not counted";
  - an upload check ran ("Loaded, the numbers start from Mon Nov 16", 15,750 sales lines the same) and was discarded.
  - **PO-260394, set and cleared in both views** (actor "Claude (live smoke test)"):
    - Nov 20 is refused today ("already passed") but accepted while viewing Nov 16, and today then reads it as "Your
      date has passed" (not counted);
    - with Dec 4 set today, SHR-2125 is short 123 until Dec 4;
    - all four edits are audited (`po_eta.set` / `po_eta.clear`), and the PO has no date again.
  - Screenshots: `docs/screenshots/real-calendar/` (not committed).
**Decisions made (and by whom):**
- Ishan: the four answers above.
- Claude (conservative or mechanical; to be recorded in ASSUMPTIONS in step 2):
  - "Overdue" also applies with no gap (LOB-MEAT on Nov 16), since its order-by date really has passed;
  - zero counted stock on the data date reads "Out of stock" (it was "Too late");
  - a lot that expires between the count and today is dropped from today's stock;
  - the staleness banners count from the count's date and appear after 7 and 14 days;
  - while viewing an earlier day, the age is measured to that day, so there's no stale banner on Nov 16;
  - the estimate is rounded to whole units;
  - the one late-PO instruction disappears once an item is already out of stock (a late PO arriving today can't
    prevent that); its late POs are still listed.
**AI mistakes caught or corrected:**
- **The plan overpromised.** It said that with no gap "everything is exactly as now". That was wrong for LOB-MEAT: the
  new Overdue status changes its group on Nov 16. The tests caught it, and it's flagged above.
- **The plan's "today" list was incomplete.** It left out LOB-T810 and SCL-U10, which change once POs due since the
  count stop being counted (PO-260444 is due Nov 27).
- **A wrong sentence, caught before commit.** "Loading them makes today Mon Nov 16" would have been false with a real
  calendar. Reworded.
- **A false alarm from my own check script.** It read each group's first line (the icon) and reported missing
  groups. I fixed the script, not the site.
- I ran `python`/`pytest` without activating the venv once ("command not found"), then re-ran correctly.
**Follow-ups:**
- **Step 2 (after "go"):** ADR-034, ASSUMPTIONS rows, CLAUDE.md (boundary 4, invariant 1, playbook), README and
  DEMO_SCRIPT (start by switching the view to Nov 16).
- **Question for Ishan:** a handled note whose arrival date has passed still counts as arriving today (the older
  §6.10 rule). With a real calendar this happens between uploads. The conservative choice, matching answer 2, is to
  stop counting it until an upload shows it.

## #40 | 2026-11-27 06:20 UTC (logged) | "go, and yes stop counting passed handled notes. I have a few questions, if I upload something will it change the predictions for the future?"
**Prompt (simplified):** Go on step 2 (docs). Yes, stop counting handled notes whose date has passed. Does an upload
change the predictions?
**What changed:**
- **Handled notes whose date has passed** (commit 05109dd, A25 rewritten):
  - **not counted** once their date is before today (they used to count as arriving today);
  - the note stays on the card and the item page, marked "Its date has passed …" (yellow);
  - the item **leaves the grey Handled group** for its real status. That part is my call (conservative): otherwise a
    possibly out-of-stock item would sit in grey;
  - API: `HandledNoteOut.date_passed`, and `counts_as_incoming` is false once the date passes;
  - tests: engine (before vs after its date) and API (a note written while viewing Nov 16 for Nov 20: Handled on Nov 16,
    back in Too late on Nov 27, not in On the way).
- **Item page:** on a day after the count, customer orders due before today are greyed and labelled "shipped by now
  (estimated)". This matches the Why table, which counts only orders still to ship. I found the mismatch while checking
  the screenshots.
- **`scripts/compare_answer_key.py`** crashed on the new statuses (KeyError 'OVERDUE'). Fixed. It now shows LOB-MEAT as
  overdue where the key says "this week".
- **Docs (step 2):**
  - **ADR-034** "Today is Boston's calendar date"; ADR-032's boundary 4 is marked superseded, and the index updated.
  - **ASSUMPTIONS:** A18 (late = due on or before the data date), A25 (rewritten), A49 (superseded), and new **A52–A59**
    (today, the estimate, unconfirmed supply, the red statuses, the stale levels, view as of, the late-PO instruction
    once out of stock, a count dated after today).
  - **CLAUDE.md:** boundary 4 and invariant 1 rewritten; the playbook gains "View as of", the stale thresholds, the
    time zone and the estimate; the decisions list gains the real calendar.
  - **README:** the "today" note, the weekly loop with a "Between uploads" list, statuses, assumptions, the
    answer-key notes, and the four screenshots retaken on live as of Nov 16.
  - **DEMO_SCRIPT:** set View as of to Nov 16 before starting; the new tiles (3 / 1 / 5 / 5 / 16, with LOB-MEAT's
    overdue explained); a new "Any day: back to today" minute (Nov 27's numbers as the example); the new upload-check
    wording; and what to do if the view is out of range.
  - All the demo numbers were re-read from live in the Nov 16 view.
**Impact:**
- 329 tests pass, ruff is clean, and the website builds, lints and is formatted.
- Live after deploy: see below.
- Nov 16 view: no change (no handled notes exist).
**Decisions made (and by whom):**
- Ishan: stop counting passed handled notes.
- Claude:
  - such an item goes back to its status group;
  - the README screenshots use the Nov 16 view, so they match the text and don't go stale daily;
  - the "shipped by now" label.
**AI mistakes caught or corrected:**
- `compare_answer_key.py` wasn't updated in step 1 and crashed on 'OVERDUE'. I found it while writing the README's
  answer-key notes.
- The first ADR-034 draft said "the cache is keyed by (count, today)". In fact only the rules are cached; the plan is
  computed on every request. Corrected after checking `planning_inputs.py`.
- Step 1 left the Promised table out of step with the Why table on days after the count. Fixed above.
**Answer to Ishan's question (does an upload change the predictions?):** yes, every number is recomputed from the new
files. See the report for details.
**Follow-ups:** none required. Note that once newer files are uploaded, Nov 16 can no longer be viewed: the view starts
the day after the latest count.
