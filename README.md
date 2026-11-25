# Kestrel Bay ordering

> **Work in progress (Phase 0 of 6).** This is the README stub. The full submission README (what was built and why, the live
> link, assumptions, scope, next steps, and how AI was used) lands in Phase 6.

A small web app for Dana Okafor, VP Purchasing at Kestrel Bay Seafood. On Monday morning it answers two questions: **what
will run out before a new order can arrive**, and **what is she stuck with**. It counts only sellable stock and real demand,
and every number can be traced back to a line in the BlueTide exports.

- Spec and full context: [`BUILD_PROMPT.md`](BUILD_PROMPT.md)
- Data problems found and the rule for each: [`docs/DATA_AUDIT.md`](docs/DATA_AUDIT.md)
- Assumptions and their status: [`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md)
- Design decisions: [`docs/DECISIONS.md`](docs/DECISIONS.md)
- How AI was used, prompt by prompt: [`docs/PROMPT_LOG.md`](docs/PROMPT_LOG.md)
- Original client materials (untouched): [`kestrel-bay/`](kestrel-bay/). Working copies: `data/raw/`, `docs/client/`
