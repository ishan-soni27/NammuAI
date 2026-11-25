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
