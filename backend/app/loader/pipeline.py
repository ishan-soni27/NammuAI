"""Run every cleaning rule over the raw exports and return the clean dataset (pure, no DB).

Order matters, because some rules need the results of others:
    vendors -> items (master only) -> customers -> locations
    -> sales (needs "is this item fresh?")
    -> purchase orders
    -> final item lifecycle (dormant needs sales + open POs, T06)
    -> on-hand lots (need each item's selling unit and pounds per case)
    -> prices, seeds

Used by run.py (then write.py stores the result) and by the golden tests, which assert the
facts in BUILD_PROMPT §5.3 directly on this output without touching a database.
"""

from __future__ import annotations

from collections import Counter

from app.config.business_rules import BusinessRules
from app.loader import rules as R
from app.loader.types import CleanDataset, FileStats, IssueLog, LoadResult, RawFile, ReferenceData


def build_dataset(raw: dict[str, RawFile], ref: ReferenceData, business_rules: BusinessRules) -> LoadResult:
    """Apply T01–T31 to the raw files. Never raises for bad BlueTide data: it logs issues instead."""
    issues = IssueLog()
    aliases = R.AliasRegistry()

    vendors = R.build_vendors(raw["vendors"], ref, issues)
    item_drafts = R.build_items(raw["items"], ref, issues, aliases, business_rules)
    customers = R.build_customers(raw["customers"], issues)
    locations = R.build_locations(ref)
    sales = R.build_sales(
        raw["sales_lines"],
        item_drafts,
        {c.customer_code: c.customer_type for c in customers},
        ref,
        issues,
        aliases,
        business_rules,
    )
    po_lines = R.build_po_lines(
        raw["purchase_orders"], item_drafts, {v.vendor_code for v in vendors}, issues, aliases, business_rules
    )
    items = R.finalize_items(item_drafts, sales, po_lines, issues, business_rules)
    snapshot_date, lots = R.build_lots(
        raw["inventory_on_hand"], item_drafts, locations, issues, aliases, business_rules
    )
    item_codes = {i.item_code for i in items}
    prices = R.build_prices(raw["price_list"], item_codes, issues)
    stockouts = R.check_stockouts(ref.stockout_periods, item_codes, issues)

    dataset = CleanDataset(
        snapshot_date=snapshot_date,
        vendors=tuple(vendors),
        items=tuple(items),
        aliases=aliases.aliases(),
        customers=tuple(customers),
        locations=tuple(locations),
        lots=tuple(lots),
        sales=tuple(sales),
        po_lines=tuple(po_lines),
        prices=tuple(prices),
        stockout_periods=tuple(stockouts),
        excluded_orders=ref.excluded_orders,
    )
    stored_by_file = Counter(
        row.source.file for rows in (vendors, items, customers, lots, sales, po_lines, prices) for row in rows
    )
    return LoadResult(
        dataset=dataset,
        issues=tuple(issues.issues),
        raw_files=tuple(raw.values()),
        file_stats=tuple(_file_stats(f, stored_by_file[f.file_name], issues) for f in raw.values()),
    )


def _file_stats(raw_file: RawFile, rows_stored: int, issues: IssueLog) -> FileStats:
    by_action: Counter[str] = Counter()
    for issue in issues.issues:
        if issue.source is not None and issue.source.file == raw_file.file_name:
            by_action[issue.action] += 1
    return FileStats(
        file_name=raw_file.file_name,
        sha256=raw_file.sha256,
        rows_read=len(raw_file.records),
        rows_stored=rows_stored,
        issues_by_action=dict(by_action),
    )
