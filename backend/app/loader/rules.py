"""The data-cleaning rules T01–T31 (BUILD_PROMPT §5), one builder per BlueTide file.

Every rule names its trap ID in a comment and in the data issue it logs, so a reviewer can
go from a number on screen to the Data notes page, to the line here, to the test
(`test_T01_...`), and back to the exact line in the export.

Ground rules (all pure: no DB, no clock; "today" comes from rules.as_of_date)
    - Never guess silently. Every exclusion, correction or flag becomes an Issue.
    - A row we can't read at all is excluded with an `error` issue; the load carries on.
    - Conservative when unsure: the option that makes a stockout less likely (§0 rule 4).

How to change this: find the builder for the file (build_items, build_lots, ...) and the
step with the trap ID. Keep the issue message in plain English, because Dana reads it.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from app.config.business_rules import BusinessRules
from app.loader.classify import (
    DEMAND_CLASS_MESSAGES,
    SaleFacts,
    base_lifecycle,
    classify_sale,
    final_lifecycle,
    status_kind,
)
from app.loader.convert import cost_to_sell_uom, to_sell_uom
from app.loader.normalize import (
    blank_to_none,
    canonical_code,
    normalize_category,
    parse_business_date,
    parse_decimal,
    parse_int,
    parse_lead_time_days,
    parse_pack_size_lb,
)
from app.loader.types import (
    CleanAlias,
    CleanCustomer,
    CleanItem,
    CleanLocation,
    CleanLot,
    CleanPOLine,
    CleanPrice,
    CleanSale,
    CleanVendor,
    IssueLog,
    RawFile,
    RawRecord,
    ReferenceData,
    SourceRef,
    StockoutPeriodSeed,
)

ZERO = Decimal(0)
PACK_TOLERANCE_LB = Decimal("0.001")
_CURRENCY_CODE = re.compile(r"^[A-Z]{3}$")


def fmt(qty: Decimal | None) -> str:
    """Human-friendly number for messages: 22, 10.5, 8,478.5 (never 1E+1)."""
    if qty is None:
        return "?"
    text = f"{qty:,.4f}".rstrip("0").rstrip(".")
    return text if text not in {"", "-0"} else "0"


# ---- T02: one canonical item code everywhere --------------------------------------------


class AliasRegistry:
    """Maps raw code variants ("shr-1620 ") to the canonical code and remembers them (T02).

    The remembered variants become `item_aliases` rows, so looking up "shr-1620 " in the
    API still finds SHR-1620.
    """

    def __init__(self) -> None:
        self._aliases: dict[str, CleanAlias] = {}

    def resolve(self, raw: str, source: SourceRef, issues: IssueLog, *, log_row: bool = True) -> str:
        code = canonical_code(raw)
        if raw != code:
            self._aliases.setdefault(
                raw,
                CleanAlias(
                    alias_code=raw,
                    item_code=code,
                    reason=(
                        f"Variant spelling (case or spaces) first seen in {source.file}; "
                        f"same item as {code} (T02)."
                    ),
                ),
            )
            if log_row:
                issues.add(
                    source,
                    "T02",
                    "item_code_canonicalized",
                    "info",
                    "corrected",
                    f"Item code {raw!r} read as {code} (same item, different spelling).",
                    item_code=code,
                    field="item_code",
                    original_value=raw,
                    new_value=code,
                )
        return code

    def aliases(self) -> tuple[CleanAlias, ...]:
        return tuple(sorted(self._aliases.values(), key=lambda a: a.alias_code))


# ---- T21: dates in two formats ----------------------------------------------------------


def parse_dates(record: RawRecord, columns: list[str], issues: IssueLog) -> dict[str, date | None]:
    """Parse several date columns of one row; log ONE T21 issue if any used MM/DD/YYYY.

    Raises ValueError if a date is unreadable (the caller excludes the row).
    """
    parsed: dict[str, date | None] = {}
    us_columns: list[str] = []
    for column in columns:
        value, form = parse_business_date(record.get(column))
        parsed[column] = value
        if form == "us":
            us_columns.append(column)
    if us_columns:
        issues.add(
            record.source,
            "T21",
            "us_date_format",
            "info",
            "corrected",
            "Dates written as MM/DD/YYYY (" + ", ".join(us_columns) + ") read as US month/day/year.",
            field=",".join(us_columns),
            original_value=", ".join(record.get(c) for c in us_columns),
            new_value=", ".join(str(parsed[c]) for c in us_columns),
        )
    return parsed


def _unreadable(
    record: RawRecord, issues: IssueLog, problem: Exception, item_code: str | None = None
) -> None:
    issues.add(
        record.source,
        None,
        "unreadable_row",
        "error",
        "excluded",
        f"Couldn't read this row ({problem}); left out. Check the export.",
        item_code=item_code,
    )


# ---- Vendors (T27, T28) -------------------------------------------------------------------


_VENDOR_TYPE_MESSAGES = {
    "fresh_supplier": "Fresh day-boat supplier: fresh is out of scope (T07), never planned.",
    "service_provider": "Storage/service provider, not a seafood supplier: never planned.",
    "legacy": "Old vendor (legacy items only): never planned.",
}


def build_vendors(raw: RawFile, ref: ReferenceData, issues: IssueLog) -> list[CleanVendor]:
    seeds = {s.vendor_code: s for s in ref.vendor_settings}
    vendors: list[CleanVendor] = []
    for record in raw.records:
        code = record.get("vendor_code").strip().upper()
        name = record.get("vendor_name").strip()
        lead_raw = record.get("lead_time_days")
        days, how = parse_lead_time_days(lead_raw)
        seed = seeds.get(code)

        # T27: keep BlueTide's lead time as the "system" value; Dana's number lives in vendor_settings.
        if how.startswith("upper bound"):
            issues.add(
                record.source,
                "T27",
                "lead_time_text_parsed",
                "info",
                "corrected",
                f"{name}: lead time {lead_raw!r} read as {days} days ({how}, the cautious end).",
                field="lead_time_days",
                original_value=lead_raw,
                new_value=str(days),
            )
        elif how == "unreadable":
            issues.add(
                record.source,
                "T27",
                "lead_time_unreadable",
                "warning",
                "flagged",
                f"{name}: lead time {lead_raw!r} can't be read; BlueTide's value is ignored.",
                field="lead_time_days",
                original_value=lead_raw,
            )
        if seed and days is None:
            issues.add(
                record.source,
                "T27",
                "lead_time_missing_in_bluetide",
                "info",
                "flagged",
                f"{name}: BlueTide has no lead time. Using Dana's {seed.lead_time_days} days.",
                field="lead_time_days",
                original_value=lead_raw,
                new_value=str(seed.lead_time_days),
            )
        elif seed and days != seed.lead_time_days:
            issues.add(
                record.source,
                "T27",
                "lead_time_differs_from_dana",
                "info",
                "flagged",
                f"{name}: BlueTide says {days} days, Dana says {seed.lead_time_days}. Dana's number is used.",
                field="lead_time_days",
                original_value=lead_raw,
                new_value=str(seed.lead_time_days),
            )

        # T28: classify the vendor from the seed (no vendor codes in code, ADR-018).
        vendor_type = ref.vendor_types.get(code)
        if vendor_type is None:
            vendor_type = "stock_supplier"  # conservative: its items still get planned
            issues.add(
                record.source,
                "T28",
                "vendor_type_missing",
                "warning",
                "flagged",
                f"{name} ({code}) isn't in data/reference/vendor_types.csv; treated as a stock supplier.",
            )
        elif vendor_type in _VENDOR_TYPE_MESSAGES:
            issues.add(
                record.source,
                "T28",
                f"vendor_{vendor_type}",
                "info",
                "flagged",
                f"{name}: {_VENDOR_TYPE_MESSAGES[vendor_type]}",
            )

        payment_terms = blank_to_none(record.get("payment_terms"))
        if payment_terms and _CURRENCY_CODE.match(payment_terms):
            issues.add(
                record.source,
                "T28",
                "payment_terms_looks_like_currency",
                "warning",
                "flagged",
                f"{name}: payment terms say {payment_terms!r}, which looks like a currency code in the "
                "wrong column. Left as is (not used for ordering).",
                field="payment_terms",
                original_value=payment_terms,
            )

        vendors.append(
            CleanVendor(
                vendor_code=code,
                name=name,
                country=blank_to_none(record.get("country")),
                vendor_type=vendor_type,
                lead_time_raw=blank_to_none(lead_raw),
                lead_time_days_system=days,
                payment_terms=payment_terms,
                currency=blank_to_none(record.get("currency")),
                source=record.source,
            )
        )

    known = {v.vendor_code for v in vendors}
    for seed in ref.vendor_settings:
        if seed.vendor_code not in known:
            issues.add(
                None,
                "T27",
                "seed_vendor_unknown",
                "warning",
                "flagged",
                f"vendor_settings_seed.csv has {seed.vendor_code}, which isn't in BlueTide's vendor list.",
            )
    return vendors


# ---- Items (T02, T03, T04, T05, T07, T08, T09) ------------------------------------------


@dataclass
class ItemDraft:
    """An item before its final lifecycle is known (dormant needs sales and POs, T06)."""

    item: CleanItem
    base: tuple[str, str] | None  # lifecycle settled by the master (fresh/legacy/discontinued)


def build_items(
    raw: RawFile, ref: ReferenceData, issues: IssueLog, aliases: AliasRegistry, rules: BusinessRules
) -> dict[str, ItemDraft]:
    groups: dict[str, list[RawRecord]] = defaultdict(list)
    for record in raw.records:
        groups[canonical_code(record.get("item_code"))].append(record)

    drafts: dict[str, ItemDraft] = {}
    for code, records in groups.items():
        # T03: collapse duplicate master rows; keep the row already spelled canonically.
        keeper = next((r for r in records if r.get("item_code") == code), records[0])
        for dropped in records:
            if dropped is keeper:
                continue
            aliases.resolve(dropped.get("item_code"), dropped.source, issues, log_row=False)
            issues.add(
                dropped.source,
                "T03",
                "duplicate_item_row",
                "info",
                "excluded",
                f"Duplicate item row {dropped.get('item_code')!r} (created {dropped.get('created_date')}) "
                f"dropped; kept the {code} row. The spelling is kept as an alias.",
                item_code=code,
                field="item_code",
                original_value=dropped.get("item_code"),
                new_value=code,
            )
        aliases.resolve(keeper.get("item_code"), keeper.source, issues)  # T02 if the keeper itself is odd
        try:
            drafts[code] = _build_item(code, keeper, ref, issues, rules)
        except ValueError as problem:
            _unreadable(keeper, issues, problem, code)
    return drafts


def _build_item(
    code: str, record: RawRecord, ref: ReferenceData, issues: IssueLog, rules: BusinessRules
) -> ItemDraft:
    src = record.source
    status_raw = record.get("status")
    kind = status_kind(status_raw, rules)
    # T04: status is free text. Blank is NOT discontinued.
    if kind == "blank":
        issues.add(
            src,
            "T04",
            "status_blank",
            "info",
            "flagged",
            "Status is blank: treated as active (blank does not mean discontinued).",
            item_code=code,
            field="status",
            original_value=status_raw,
        )
    elif kind == "unknown":
        issues.add(
            src,
            "T04",
            "status_unknown",
            "warning",
            "flagged",
            f"Unrecognized status {status_raw!r}: treated as active (so it is never wrongly dropped).",
            item_code=code,
            field="status",
            original_value=status_raw,
        )
    elif status_raw.strip() not in {"Active", "Discontinued"}:
        issues.add(
            src,
            "T04",
            "status_normalized",
            "info",
            "corrected",
            f"Status {status_raw!r} read as {kind}.",
            item_code=code,
            field="status",
            original_value=status_raw,
            new_value=kind,
        )

    # T08: category casing.
    category_raw = record.get("category")
    category = normalize_category(category_raw)
    if category != category_raw:
        issues.add(
            src,
            "T08",
            "category_normalized",
            "info",
            "corrected",
            f"Category {category_raw!r} read as {category!r}.",
            item_code=code,
            field="category",
            original_value=category_raw,
            new_value=category,
        )

    storage = record.get("storage").strip().upper()
    sell_uom = record.get("sell_uom").strip().upper()
    pack_raw = record.get("pack_size")
    base = base_lifecycle(code, storage, kind, rules)

    # T09: pounds per case come from the human-verified table, never from parsing text at runtime.
    pack = ref.pack_sizes.get(code)
    lb_per_case = pack.lb_per_case if pack else None
    if pack is None:
        issues.add(
            src,
            "T09",
            "pack_size_missing",
            "error",
            "flagged",
            f"No row for {code} in data/reference/pack_sizes.csv: pound lots of it can't be converted. "
            "Add it.",
            item_code=code,
            field="pack_size",
            original_value=pack_raw,
        )
    else:
        if pack.pack_size_raw != pack_raw:
            issues.add(
                src,
                "T09",
                "pack_text_changed",
                "warning",
                "flagged",
                f"BlueTide's pack text is {pack_raw!r} but the verified table was checked against "
                f"{pack.pack_size_raw!r}. Re-check data/reference/pack_sizes.csv.",
                item_code=code,
                field="pack_size",
                original_value=pack_raw,
            )
        parsed = parse_pack_size_lb(pack_raw)
        if (
            sell_uom == "CS"
            and lb_per_case is not None
            and parsed is not None
            and (abs(parsed - lb_per_case) > PACK_TOLERANCE_LB)
        ):
            issues.add(
                src,
                "T09",
                "pack_size_mismatch",
                "warning",
                "flagged",
                f"Pack text {pack_raw!r} reads as {fmt(parsed)} lb, but the verified table says "
                f"{fmt(lb_per_case)} lb per case. The table is used; please re-check.",
                item_code=code,
                field="pack_size",
                original_value=pack_raw,
                new_value=fmt(lb_per_case),
            )
        if sell_uom == "CS" and lb_per_case is None and base is None:
            issues.add(
                src,
                "T09",
                "pack_size_no_factor",
                "error",
                "flagged",
                f"{code} is sold by the case but pack_sizes.csv has no pounds per case.",
                item_code=code,
                field="pack_size",
                original_value=pack_raw,
            )

    # T05 / T07: lifecycle settled by the master.
    if base and base[0] == "legacy":
        note = " BlueTide still marks it Active." if kind == "active" else ""
        issues.add(src, "T05", "legacy_item", "info", "flagged", f"{base[1]}{note}", item_code=code)
    elif base and base[0] == "fresh_out_of_scope":
        issues.add(src, "T07", "fresh_item", "info", "flagged", base[1], item_code=code)

    item = CleanItem(
        item_code=code,
        description=record.get("description").strip(),
        category=category,
        storage=storage,
        pack_size_raw=blank_to_none(pack_raw),
        lb_per_case=lb_per_case,
        sell_uom=sell_uom,
        vendor_code=record.get("vendor_code").strip().upper(),
        shelf_life_months=parse_int(record.get("shelf_life_months")),
        status_raw=blank_to_none(status_raw),
        lifecycle_status="active",  # placeholder; finalized after sales/POs are read (T06)
        lifecycle_reason="",
        upc=blank_to_none(record.get("upc")),
        created_date=parse_business_date(record.get("created_date"))[0],
        source=src,
    )
    return ItemDraft(item=item, base=base)


def finalize_items(
    drafts: dict[str, ItemDraft],
    sales: list[CleanSale],
    po_lines: list[CleanPOLine],
    issues: IssueLog,
    rules: BusinessRules,
) -> list[CleanItem]:
    """Settle every item's lifecycle, including dormant (T06), now that sales and POs are known."""
    last_demand: dict[str, date] = {}
    for sale in sales:
        if sale.demand_class == "real_demand":
            last = last_demand.get(sale.item_code)
            if last is None or sale.order_date > last:
                last_demand[sale.item_code] = sale.order_date
    open_po_items = {
        p.item_code for p in po_lines if p.status == "open" and (p.qty_remaining_sell_uom or ZERO) > 0
    }

    items: list[CleanItem] = []
    for code, draft in sorted(drafts.items()):
        status, reason = final_lifecycle(draft.base, last_demand.get(code), code in open_po_items, rules)
        if status == "dormant":
            issues.add(draft.item.source, "T06", "dormant_item", "warning", "flagged", reason, item_code=code)
        items.append(replace(draft.item, lifecycle_status=status, lifecycle_reason=reason))
    return items


# ---- Customers and locations --------------------------------------------------------------


def build_customers(raw: RawFile, issues: IssueLog) -> list[CleanCustomer]:
    customers = []
    for record in raw.records:
        customers.append(
            CleanCustomer(
                customer_code=record.get("customer_code").strip(),
                name=record.get("customer_name").strip(),
                customer_type=record.get("customer_type").strip().upper(),
                salesperson=blank_to_none(record.get("salesperson")),
                city=blank_to_none(record.get("city")),
                state=blank_to_none(record.get("state")),
                source=record.source,
            )
        )
    return customers


def build_locations(ref: ReferenceData) -> list[CleanLocation]:
    return [
        CleanLocation(
            code=s.code,
            name=s.name,
            is_sellable=s.is_sellable,
            is_third_party_storage=s.is_third_party_storage,
            may_return_to_stock=s.may_return_to_stock,
            description=s.description,
        )
        for s in ref.locations
    ]


# ---- On hand (T01, T02, T05, T10, T11, T12, T13, T14, T31) --------------------------------


def latest_snapshot(raw: RawFile) -> date:
    """The newest stock count in the on-hand file (T01: the file holds two nights; the latest counts).

    "Today" is the day after it (business_rules.rules_for_snapshot), so a load can work out its own
    business date before any other rule runs.
    """
    latest_text = max(record.get("snapshot_date").strip() for record in raw.records)
    latest = parse_business_date(latest_text)[0]
    if latest is None:
        raise ValueError(f"The stock file's snapshot date {latest_text!r} isn't a date.")
    return latest


def build_lots(
    raw: RawFile,
    items: dict[str, ItemDraft],
    locations: list[CleanLocation],
    issues: IssueLog,
    aliases: AliasRegistry,
    rules: BusinessRules,
) -> tuple[date, list[CleanLot]]:
    """Return (latest snapshot date, clean lots of the latest snapshot)."""
    by_location = {loc.code: loc for loc in locations}
    snapshots: dict[str, list[RawRecord]] = defaultdict(list)
    for record in raw.records:
        snapshots[record.get("snapshot_date").strip()].append(record)
    latest_text = max(snapshots)
    latest = latest_snapshot(raw)

    # T01: the file holds two nights; only the latest counts. Summing both ~doubles stock.
    for snapshot_text, records in sorted(snapshots.items()):
        if snapshot_text == latest_text:
            continue
        for record in records:
            issues.add(
                record.source,
                "T01",
                "older_snapshot_row",
                "info",
                "excluded",
                f"From the {snapshot_text} snapshot; only the latest ({latest_text}) is used.",
                item_code=canonical_code(record.get("item_code")),
            )

    # T31: lots present the night before but gone in the latest snapshot sold out.
    latest_keys = {_lot_key(r) for r in snapshots[latest_text]}
    for snapshot_text, records in sorted(snapshots.items()):
        if snapshot_text == latest_text:
            continue
        for record in records:
            try:
                qty = parse_decimal(record.get("qty")) or ZERO
            except ValueError:
                continue  # an unreadable old row can't tell us anything about the latest night
            if qty > 0 and _lot_key(record) not in latest_keys:
                code, location, lot_no = _lot_key(record)
                issues.add(
                    record.source,
                    "T31",
                    "lot_gone_in_latest",
                    "info",
                    "flagged",
                    f"Lot {lot_no} of {code} at {location} ({fmt(qty)} {record.get('uom')}) was in the "
                    f"{snapshot_text} snapshot but not {latest_text}: sold out, not missing data.",
                    item_code=code,
                )

    lots: list[CleanLot] = []
    for record in snapshots[latest_text]:
        try:
            lot = _build_lot(record, latest, items, by_location, issues, aliases, rules)
        except ValueError as problem:
            _unreadable(record, issues, problem, canonical_code(record.get("item_code")))
            continue
        if lot is not None:
            lots.append(lot)
    return latest, lots


def _lot_key(record: RawRecord) -> tuple[str, str, str]:
    return (
        canonical_code(record.get("item_code")),
        record.get("location").strip(),
        record.get("lot_no").strip(),
    )


def _build_lot(
    record: RawRecord,
    snapshot: date,
    items: dict[str, ItemDraft],
    by_location: dict[str, CleanLocation],
    issues: IssueLog,
    aliases: AliasRegistry,
    rules: BusinessRules,
) -> CleanLot | None:
    src = record.source
    code = aliases.resolve(record.get("item_code"), src, issues)  # T02
    draft = items.get(code)
    if draft is None:
        issues.add(
            src,
            None,
            "unknown_item",
            "error",
            "excluded",
            f"Item {code} isn't in the item master; lot left out.",
            item_code=code,
        )
        return None
    item = draft.item
    location_code = record.get("location").strip()
    location = by_location.get(location_code)
    if location is None:
        issues.add(
            src,
            None,
            "unknown_location",
            "error",
            "excluded",
            f"Location {location_code!r} isn't in data/reference/locations.csv; lot left out.",
            item_code=code,
        )
        return None

    qty = parse_decimal(record.get("qty"))
    if qty is None:
        raise ValueError("blank quantity")
    lot_no = record.get("lot_no").strip()
    uom = record.get("uom").strip().upper()

    # T12: zero-quantity split lots ("B" suffix) carry nothing.
    if qty == 0:
        issues.add(
            src,
            "T12",
            "zero_qty_lot",
            "info",
            "excluded",
            f"Lot {lot_no} has quantity 0 (an empty split lot); skipped.",
            item_code=code,
        )
        return None

    dates = parse_dates(record, ["pack_date", "expiry_date", "received_date"], issues)
    cost = parse_decimal(record.get("unit_cost"))

    # T13: negative adjustment lines, netted into sellable stock (conservative, A07).
    is_adjustment = lot_no.upper().startswith(rules.adjustment_lot_prefix.upper()) or qty < 0
    if is_adjustment:
        issues.add(
            src,
            "T13",
            "adjustment_line",
            "warning",
            "flagged",
            f"Stock adjustment {lot_no} of {fmt(qty)} {uom} at {location_code}: netted against sellable "
            "stock (the cautious choice; assumption A07).",
            item_code=code,
        )

    # T10: convert to the item's selling unit with the verified pounds per case.
    qty_sell = to_sell_uom(qty, uom, item.sell_uom, item.lb_per_case)
    cost_sell = cost_to_sell_uom(cost, uom, item.sell_uom, item.lb_per_case)
    if uom != item.sell_uom:
        if qty_sell is None:
            issues.add(
                src,
                "T10",
                "unit_conversion_impossible",
                "error",
                "flagged",
                f"Lot {lot_no} is in {uom} but {code} sells in {item.sell_uom} and has no pounds per case; "
                "not counted until pack_sizes.csv has it.",
                item_code=code,
                field="uom",
                original_value=uom,
            )
        else:
            issues.add(
                src,
                "T10",
                "unit_converted",
                "info",
                "corrected",
                f"Lot {lot_no}: {fmt(qty)} {uom} read as {fmt(qty_sell)} {item.sell_uom} "
                f"({fmt(item.lb_per_case)} lb per case); cost ${fmt(cost)}/{uom.lower()} -> "
                f"${fmt(cost_sell)}/{item.sell_uom.lower()}.",
                item_code=code,
                field="qty",
                original_value=f"{qty} {uom}",
                new_value=f"{fmt(qty_sell)} {item.sell_uom}",
            )

    # T11: QA-HOLD / DAMAGED show up as on hand but can't be sold.
    if not location.is_sellable:
        meaning = (
            "on hold, may come back (shown separately, not counted)"
            if location.may_return_to_stock
            else "damaged, written off eventually (not counted)"
        )
        issues.add(
            src,
            "T11",
            f"not_sellable_{location_code.lower()}",
            "info",
            "flagged",
            f"{fmt(qty_sell)} {item.sell_uom} of {code} at {location_code}: {meaning}.",
            item_code=code,
        )

    # T14: expired lots are a write-off, not stock.
    expiry = dates["expiry_date"]
    if expiry is not None and expiry < rules.as_of_date and location.is_sellable and not is_adjustment:
        issues.add(
            src,
            "T14",
            "expired_lot",
            "info",
            "flagged",
            f"Lot {lot_no} of {code} ({fmt(qty_sell)} {item.sell_uom} at {location_code}) expired on "
            f"{expiry:%b %d, %Y}: not sellable, shown as a write-off.",
            item_code=code,
        )

    # T05: stock of old-system ZZ items is a write-off.
    if draft.base and draft.base[0] == "legacy":
        issues.add(
            src,
            "T05",
            "legacy_stock",
            "info",
            "flagged",
            f"{fmt(qty_sell)} {item.sell_uom} of old-system item {code} at {location_code}: write-off.",
            item_code=code,
        )

    return CleanLot(
        snapshot_date=snapshot,
        item_code=code,
        location_code=location_code,
        lot_no=lot_no,
        is_adjustment=is_adjustment,
        qty_source=qty,
        uom_source=uom,
        qty_sell_uom=qty_sell,
        pack_date=dates["pack_date"],
        expiry_date=expiry,
        received_date=dates["received_date"],
        unit_cost_source=cost,
        unit_cost_sell_uom=cost_sell,
        vendor_lot_ref=blank_to_none(record.get("vendor_lot_ref")),
        source=src,
    )


# ---- Sales (T02, T07, T16–T21) ------------------------------------------------------------


def build_sales(
    raw: RawFile,
    items: dict[str, ItemDraft],
    customer_types: dict[str, str],
    ref: ReferenceData,
    issues: IssueLog,
    aliases: AliasRegistry,
    rules: BusinessRules,
) -> list[CleanSale]:
    excluded_orders = {o.order_no for o in ref.excluded_orders}
    sales: list[CleanSale] = []
    for record in raw.records:
        src = record.source
        try:
            code = aliases.resolve(record.get("item_code"), src, issues)  # T02
            draft = items.get(code)
            if draft is None:
                issues.add(
                    src,
                    None,
                    "unknown_item",
                    "error",
                    "excluded",
                    f"Item {code} isn't in the item master; sales line left out.",
                    item_code=code,
                )
                continue
            customer_code = record.get("customer_code").strip()
            if customer_code not in customer_types:
                issues.add(
                    src,
                    None,
                    "unknown_customer",
                    "error",
                    "excluded",
                    f"Customer {customer_code} isn't in the customer list; sales line left out.",
                    item_code=code,
                )
                continue
            dates = parse_dates(record, ["order_date", "ship_date"], issues)  # T21
            order_date = dates["order_date"]
            if order_date is None:
                raise ValueError("blank order date")
            qty = parse_decimal(record.get("qty"))
            unit_price = parse_decimal(record.get("unit_price"))
            ext_price = parse_decimal(record.get("ext_price"))
            line_no = parse_int(record.get("line_no"))
            if qty is None or unit_price is None or ext_price is None or line_no is None:
                raise ValueError("blank quantity, price or line number")
            status = record.get("status").strip().upper()
            order_no = record.get("order_no").strip()
            item = draft.item

            uom = record.get("uom").strip().upper()
            if uom != item.sell_uom:  # T10 (not seen in sales today, handled the same way as lots)
                converted = to_sell_uom(qty, uom, item.sell_uom, item.lb_per_case)
                if converted is None:
                    issues.add(
                        src,
                        "T10",
                        "unit_conversion_impossible",
                        "error",
                        "excluded",
                        f"Sold in {uom} but {code} sells in {item.sell_uom} with no pounds per case; "
                        "left out.",
                        item_code=code,
                    )
                    continue
                issues.add(
                    src,
                    "T10",
                    "unit_converted",
                    "info",
                    "corrected",
                    f"{fmt(qty)} {uom} read as {fmt(converted)} {item.sell_uom}.",
                    item_code=code,
                )
                qty, uom = converted, item.sell_uom

            lifecycle = draft.base[0] if draft.base else "active"
            demand_class = classify_sale(
                SaleFacts(
                    status=status,
                    customer_type=customer_types[customer_code],
                    order_no=order_no,
                    qty=qty,
                    unit_price=unit_price,
                    item_lifecycle=lifecycle,
                ),
                excluded_orders,
                rules,
            )
            if demand_class != "real_demand":  # T07, T16–T20
                trap, message = DEMAND_CLASS_MESSAGES[demand_class]
                issues.add(src, trap, f"sale_{demand_class}", "info", "excluded", message, item_code=code)

            sales.append(
                CleanSale(
                    order_no=order_no,
                    line_no=line_no,
                    order_date=order_date,
                    ship_date=dates["ship_date"],
                    customer_code=customer_code,
                    item_code=code,
                    qty=qty,
                    uom=uom,
                    unit_price=unit_price,
                    ext_price=ext_price,
                    status=status,
                    salesperson=blank_to_none(record.get("salesperson")),
                    demand_class=demand_class,
                    source=src,
                )
            )
        except ValueError as problem:
            _unreadable(record, issues, problem, canonical_code(record.get("item_code")))
    return sales


# ---- Purchase orders (T02, T10, T24, T25, T26) --------------------------------------------

_PO_STATUS = {"received": "complete", "closed": "complete", "open": "open", "cancelled": "cancelled"}


def build_po_lines(
    raw: RawFile,
    items: dict[str, ItemDraft],
    vendor_codes: set[str],
    issues: IssueLog,
    aliases: AliasRegistry,
    rules: BusinessRules,
) -> list[CleanPOLine]:
    lines: list[CleanPOLine] = []
    first_seen: dict[str, SourceRef] = {}
    for record in raw.records:
        src = record.source
        # T24: exact duplicate rows would double the incoming quantity (1,000 instead of 500).
        if record.row_hash in first_seen:
            issues.add(
                src,
                "T24",
                "duplicate_po_row",
                "info",
                "excluded",
                f"Exact duplicate of line {first_seen[record.row_hash].line} "
                f"({record.get('po_no')} line {record.get('line_no')}); dropped so it isn't counted twice.",
                item_code=canonical_code(record.get("item_code")),
            )
            continue
        first_seen[record.row_hash] = src
        try:
            line = _build_po_line(record, items, vendor_codes, issues, aliases, rules)
        except ValueError as problem:
            _unreadable(record, issues, problem, canonical_code(record.get("item_code")))
            continue
        if line is not None:
            lines.append(line)
    return lines


def _build_po_line(
    record: RawRecord,
    items: dict[str, ItemDraft],
    vendor_codes: set[str],
    issues: IssueLog,
    aliases: AliasRegistry,
    rules: BusinessRules,
) -> CleanPOLine | None:
    src = record.source
    code = aliases.resolve(record.get("item_code"), src, issues)  # T02
    draft = items.get(code)
    vendor_code = record.get("vendor_code").strip().upper()
    if draft is None or vendor_code not in vendor_codes:
        issues.add(
            src,
            None,
            "unknown_item_or_vendor",
            "error",
            "excluded",
            f"Item {code} or vendor {vendor_code} isn't known; PO line left out.",
            item_code=code,
        )
        return None
    item = draft.item
    po_no = record.get("po_no").strip()
    status_raw = record.get("status").strip()
    status = _PO_STATUS.get(status_raw.lower())
    if status is None:
        issues.add(
            src,
            "T25",
            "po_status_unknown",
            "error",
            "excluded",
            f"{po_no}: unknown status {status_raw!r}; line left out.",
            item_code=code,
        )
        return None

    dates = parse_dates(record, ["order_date", "expected_date"], issues)
    if dates["order_date"] is None:
        raise ValueError("blank order date")
    qty_ordered = parse_decimal(record.get("qty_ordered"))
    qty_received = parse_decimal(record.get("qty_received")) or ZERO
    line_no = parse_int(record.get("line_no"))
    if qty_ordered is None or line_no is None:
        raise ValueError("blank quantity or line number")
    uom = record.get("uom").strip().upper()

    # T25: only Open lines are incoming, and only what hasn't arrived yet.
    remaining = ZERO
    if status == "open":
        remaining_source = qty_ordered - qty_received
        converted = to_sell_uom(remaining_source, uom, item.sell_uom, item.lb_per_case)
        if converted is None:
            issues.add(
                src,
                "T10",
                "unit_conversion_impossible",
                "error",
                "flagged",
                f"{po_no} is in {uom} but {code} sells in {item.sell_uom} with no pounds per case; "
                "its quantity can't be counted.",
                item_code=code,
            )
        remaining = converted if converted is not None else ZERO
        if qty_received > 0:
            issues.add(
                src,
                "T25",
                "po_partially_received",
                "info",
                "flagged",
                f"{po_no}: {fmt(qty_received)} of {fmt(qty_ordered)} {uom} received; the other "
                f"{fmt(remaining_source)} are still coming.",
                item_code=code,
            )
        if remaining <= 0:
            issues.add(
                src,
                "T25",
                "po_open_but_complete",
                "warning",
                "flagged",
                f"{po_no} is Open but fully received; nothing more is counted as coming.",
                item_code=code,
            )
        # T26: BlueTide's date is whatever the vendor said at order time; nobody updates it.
        expected = dates["expected_date"]
        if expected is not None and expected < rules.as_of_date and remaining > 0:
            issues.add(
                src,
                "T26",
                "po_date_passed",
                "warning",
                "flagged",
                f"{po_no}: BlueTide said it would arrive {expected:%b %d, %Y}, but nothing more has been "
                "received. The plan re-checks the date with the real lead time; a PO that is late is "
                "not counted as coming until Dana types in a real date.",
                item_code=code,
            )
    elif status == "cancelled":
        issues.add(
            src,
            "T25",
            "po_cancelled",
            "info",
            "excluded",
            f"{po_no}: cancelled, so nothing is coming ({fmt(qty_ordered)} {uom} ignored).",
            item_code=code,
        )

    if uom != item.sell_uom and status == "open" and remaining > 0:
        issues.add(
            src,
            "T10",
            "unit_converted",
            "info",
            "corrected",
            f"{po_no}: ordered in {uom}; the remaining quantity is counted as {fmt(remaining)} "
            f"{item.sell_uom}.",
            item_code=code,
        )
    elif uom != item.sell_uom:
        issues.add(
            src,
            "T10",
            "po_unit_differs",
            "info",
            "flagged",
            f"{po_no} was entered in {uom} although {code} sells in {item.sell_uom} (already closed, "
            "so nothing to count).",
            item_code=code,
        )

    return CleanPOLine(
        po_no=po_no,
        line_no=line_no,
        vendor_code=vendor_code,
        item_code=code,
        order_date=dates["order_date"],
        expected_date_system=dates["expected_date"],
        qty_ordered=qty_ordered,
        qty_received=qty_received,
        qty_remaining_sell_uom=remaining,
        uom=uom,
        unit_cost=parse_decimal(record.get("unit_cost")),
        status_raw=status_raw,
        status=status,
        container_no=blank_to_none(record.get("container_no")),
        source=src,
    )


# ---- Prices (T29) ---------------------------------------------------------------------------


def build_prices(raw: RawFile, item_codes: set[str], issues: IssueLog) -> list[CleanPrice]:
    """Loaded for Marco's phase 2 (price questions), not used by the ordering screen (T29)."""
    issues.add(
        None,
        "T29",
        "price_list_phase_2",
        "info",
        "flagged",
        "Price list loaded for phase 2 (Marco's pricing questions); not used by the ordering screen.",
    )
    prices: list[CleanPrice] = []
    for record in raw.records:
        code = canonical_code(record.get("item_code"))
        try:
            price = parse_decimal(record.get("price"))
            if price is None:
                raise ValueError("blank price")
            dates = parse_dates(record, ["effective_from", "effective_to"], issues)
        except ValueError as problem:
            _unreadable(record, issues, problem)
            continue
        if code not in item_codes:
            issues.add(
                record.source,
                "T29",
                "price_not_an_item",
                "info",
                "flagged",
                f"{record.get('item_code')!r} isn't an item (looks like a surcharge, "
                f"{record.get('uom')} {record.get('price')}); kept for phase 2.",
                field="item_code",
                original_value=record.get("item_code"),
            )
        prices.append(
            CleanPrice(
                item_code=code,
                tier=record.get("price_tier").strip().upper(),
                price=price,
                uom=record.get("uom").strip().upper(),
                effective_from=dates["effective_from"],
                effective_to=dates["effective_to"],
                source=record.source,
            )
        )
    return prices


# ---- Seeds that refer to items ----------------------------------------------------------


def check_stockouts(
    seeds: tuple[StockoutPeriodSeed, ...], item_codes: set[str], issues: IssueLog
) -> list[StockoutPeriodSeed]:
    """Keep stockout windows (T23) only for known items; flag the rest."""
    kept = []
    for seed in seeds:
        if seed.item_code in item_codes:
            kept.append(seed)
        else:
            issues.add(
                None,
                "T23",
                "stockout_unknown_item",
                "error",
                "flagged",
                f"stockout_periods.csv mentions {seed.item_code}, which isn't an item; ignored.",
            )
    return kept
