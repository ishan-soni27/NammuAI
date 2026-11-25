# Reference seeds: what Dana knows that BlueTide doesn't

These CSVs are **maintained by people, not exported from BlueTide**. They hold business facts that would otherwise be
hard-coded (BUILD_PROMPT invariant #13): pack sizes, real lead times, which locations count, known stockouts, and orders
to ignore. Edit them in a spreadsheet or text editor, commit, and re-run the loader. Every row cites its source
(a transcript timestamp, an email question, or a trap ID from `docs/DATA_AUDIT.md`).

| File | What it holds | Used for | How the loader treats it |
|---|---|---|---|
| `pack_sizes.csv` | `lb_per_case` for each of the 45 canonical items, checked by a person | T09/T10: converting LB lots of case items (and the reverse) | Rebuilt into `items.lb_per_case` on every load. A regex parser only *validates* this table and flags new items |
| `vendor_settings_seed.csv` | Dana's lead time, cushion (safety days) and order cycle per stock supplier | T27, §6.5: run-out, order-by date, "order at least" | **Inserted only if the vendor has no row yet**, so re-running the loader never overwrites Dana's edits made in the app |
| `vendor_types.csv` | stock_supplier / fresh_supplier / service_provider / legacy per vendor | T28: only stock suppliers are planned | Rebuilt on every load |
| `locations.csv` | Which locations are sellable, third-party (Harbor), or may return to stock (QA-HOLD) | T11, §6.1: sellable stock; "At Harbor" badges | Rebuilt on every load |
| `stockout_periods.csv` | Known stockout windows (inclusive dates) | T23, §6.7: those days are left out of selling-rate calculations | Rebuilt on every load |
| `excluded_orders.csv` | One-off orders that aren't real demand | T20, §6.2: `demand_class = one_off` | Rebuilt on every load |

**Common edits**
- Dana confirms a lead time → change `vendor_settings_seed.csv` *and* update the vendor on the Lead times page (the seed
  won't overwrite an existing row).
- Dana reports another stockout → add a row to `stockout_periods.csv`.
- A new item appears in BlueTide → add its `lb_per_case` to `pack_sizes.csv`. The loader logs an `error` in
  `data_issues` until you do.
