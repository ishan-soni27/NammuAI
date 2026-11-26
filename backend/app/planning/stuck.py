"""What Dana is stuck with (BUILD_PROMPT §6.11): Dana's second question, lot by lot.

Each lot at a sellable location gets every tag that applies; the most serious one is its
PRIMARY tag (this order):
  1. EXPIRED            expiry before today: write it off (T14)
  2. STOPPED_SELLING    the item is legacy, discontinued or dormant (T05, T06; Dana Q5:
                        "Flag what's left at Harbor so I can clear it")
  3. INSIDE_SIX_MONTHS  expiry within six months: discount it or move it now (T15; Dana 00:03:30)
  4. LONG_AT_HARBOR     at Harbor while the item has more than 12 weeks of supply: paying storage
                        on stock that won't be needed for months (Walt 00:03:30: "the worst case")
  5. OVERSTOCK          the item has more than 26 weeks of supply

Being at Harbor is NOT a reason on its own: SHR-1620's 140 cases at Harbor are needed for
Christmas, so weeks of cover decides (the demo point in §6.11).
Lots at Harbor get an "At Harbor (paying storage)" badge and sort first within their group.
Value = qty × unit cost per selling unit ("$ at cost", A17).
Age is ALWAYS judged from the lot's expiry date, never its received date (T30: SAL-POR6 was
packed in early 2025 but received in mid 2026).

Fresh items are out of scope (T07) and never listed. QA-HOLD and DAMAGED stock is shown in the
trust strip, not here.
"""

from __future__ import annotations

from collections import defaultdict

from app.config.business_rules import BusinessRules
from app.planning.calendar import add_months
from app.planning.types import ItemInput, LocationInput, LotInput, StuckItem, StuckLot, StuckTag

TAG_ORDER: tuple[StuckTag, ...] = (
    "EXPIRED",
    "STOPPED_SELLING",
    "INSIDE_SIX_MONTHS",
    "LONG_AT_HARBOR",
    "OVERSTOCK",
)
STOPPED_LIFECYCLES = {"legacy", "discontinued", "dormant"}


def lot_tags(
    lot: LotInput,
    lifecycle: str,
    weeks_of_cover: float | None,
    location: LocationInput,
    rules: BusinessRules,
) -> list[StuckTag]:
    """Every stuck reason that applies to one lot, most serious first. [] = not stuck.

    weeks_of_cover None means no demand is expected at all (infinite cover).
    """
    tags: list[StuckTag] = []
    as_of = rules.as_of_date
    six_month_line = add_months(as_of, rules.six_month_line_months)
    cover = float("inf") if weeks_of_cover is None else weeks_of_cover
    if lot.expiry_date is not None and lot.expiry_date < as_of:
        tags.append("EXPIRED")
    if lifecycle in STOPPED_LIFECYCLES:
        tags.append("STOPPED_SELLING")
    if lot.expiry_date is not None and as_of <= lot.expiry_date < six_month_line:
        tags.append("INSIDE_SIX_MONTHS")
    if location.is_third_party_storage and cover > rules.harbor_long_weeks:
        tags.append("LONG_AT_HARBOR")
    if cover > rules.overstock_weeks:
        tags.append("OVERSTOCK")
    return tags


def stuck_list(
    lots: list[LotInput] | tuple[LotInput, ...],
    items: dict[str, ItemInput],
    lifecycle_by_item: dict[str, str],
    weeks_of_cover_by_item: dict[str, float | None],
    locations: list[LocationInput] | tuple[LocationInput, ...],
    rules: BusinessRules,
) -> list[StuckItem]:
    """Stuck lots rolled up per item, most serious group first, then Harbor first, then by $."""
    by_location = {loc.code: loc for loc in locations}
    per_item: dict[str, list[StuckLot]] = defaultdict(list)
    for lot in lots:
        item = items.get(lot.item_code)
        location = by_location.get(lot.location_code)
        if item is None or location is None or not location.is_sellable:
            continue  # QA-HOLD / DAMAGED live in the trust strip
        lifecycle = lifecycle_by_item.get(lot.item_code, item.lifecycle_status)
        if lifecycle == "fresh_out_of_scope" or lot.is_adjustment or lot.qty is None or lot.qty <= 0:
            continue
        tags = lot_tags(lot, lifecycle, weeks_of_cover_by_item.get(lot.item_code), location, rules)
        if not tags:
            continue
        value = lot.qty * lot.unit_cost if lot.unit_cost is not None else None
        per_item[lot.item_code].append(
            StuckLot(
                item_code=lot.item_code,
                description=item.description,
                lot_no=lot.lot_no,
                location_code=lot.location_code,
                qty=lot.qty,
                sell_uom=item.sell_uom,
                expiry_date=lot.expiry_date,
                value_at_cost=value,
                tags=tuple(tags),
                primary_tag=tags[0],
                at_harbor=location.is_third_party_storage,
            )
        )

    rollups: list[StuckItem] = []
    for code, stuck_lots in per_item.items():
        stuck_lots.sort(
            key=lambda s: (TAG_ORDER.index(s.primary_tag), not s.at_harbor, -(s.value_at_cost or 0))
        )
        item = items[code]
        rollups.append(
            StuckItem(
                item_code=code,
                description=item.description,
                sell_uom=item.sell_uom,
                primary_tag=min((s.primary_tag for s in stuck_lots), key=TAG_ORDER.index),
                qty=sum(s.qty for s in stuck_lots),
                qty_at_harbor=sum(s.qty for s in stuck_lots if s.at_harbor),
                value_at_cost=sum(s.value_at_cost or 0.0 for s in stuck_lots),
                lots=tuple(stuck_lots),
            )
        )
    rollups.sort(key=lambda r: (TAG_ORDER.index(r.primary_tag), -(r.qty_at_harbor > 0), -r.value_at_cost))
    return rollups
