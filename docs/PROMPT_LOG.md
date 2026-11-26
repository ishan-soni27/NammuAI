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
