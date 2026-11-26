"""Supply side of the plan: what is on hand, and what is on the way (BUILD_PROMPT §6.1, §6.5, §6.6).

On hand (sellable stock, per item, in its selling unit) = lots in the latest snapshot where
  - the location is sellable (NB, PVD, HCS per data/reference/locations.csv, T11),
  - the lot is not expired: expiry >= AS_OF (T14); lots inside the six-month line still count (T15),
  PLUS negative adjustment lines (T13), which have no expiry.
Shown separately and NEVER added in: on hold (QA-HOLD, may come back), damaged, expired.
Walt 00:04:40: "If I can't sell it, it isn't inventory." Dana's Q4: "until it does I can't sell it."

On the way = open PO lines + Dana's "I've handled this" notes that have a quantity and a date.
  candidate = max(BlueTide date, order date + real lead time)   (BlueTide dates are stale, T26)
  - Dana typed a date            -> that date ("Set by <who typed it>")
  - candidate ON OR BEFORE today -> LATE (A18). Not counted as coming (Dana's Q3 answer, 2026-11-26:
                                    "please don't assume they'll arrive within a week"). It goes to
                                    the late list, shown in its own section (P0 #2a), until she enters
                                    a date. rules.late_po_assumed_days can turn counting back on.
  - otherwise                    -> candidate

How to change this
  - "Count QA-HOLD as available": pass count_on_hold_as_sellable=True to summarize_on_hand.
  - "Assume late POs arrive in N days": set late_po_assumed_days in business_rules.py.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from app.config.business_rules import BusinessRules
from app.planning.types import (
    EtaOverrideInput,
    HandledNoteInput,
    IncomingLine,
    ItemSettingInput,
    LocationInput,
    LotInput,
    OnHand,
    POLineInput,
    VendorInput,
    VendorSettingInput,
)

__all__ = [
    "LocationInput",
    "LotInput",
    "OnHand",
    "effective_lead_time_days",
    "incoming_for_item",
    "summarize_on_hand",
    "vendor_terms",
]


def summarize_on_hand(
    lots: list[LotInput] | tuple[LotInput, ...],
    locations: list[LocationInput] | tuple[LocationInput, ...],
    as_of: date,
    *,
    count_on_hold_as_sellable: bool = False,
) -> dict[str, OnHand]:
    """Split every lot into sellable / on hold / damaged / expired, per item.

    Example: SHR-1620 on Nov 15 has NB 260 + HCS 140 + PVD 80 (sellable, 480) and
    QA-HOLD 80 (on hold), so OnHand(sellable=480, on_hold=80) (golden fact G04).
    A lot at an unknown location is treated as not sellable (conservative, A21).
    """
    by_code = {loc.code: loc for loc in locations}
    result: dict[str, OnHand] = defaultdict(OnHand)
    for lot in lots:
        if lot.qty is None:
            continue  # unconvertible quantity: excluded and logged by the loader (T10)
        qty = float(lot.qty)
        summary = result[lot.item_code]
        location = by_code.get(lot.location_code)
        if location is None or not location.is_sellable:
            if location is not None and location.may_return_to_stock:
                if count_on_hold_as_sellable:
                    _add_sellable(summary, lot.location_code, qty)
                else:
                    summary.on_hold += qty  # T11: QA-HOLD, "sometimes it passes and comes back"
            else:
                summary.damaged += qty  # T11: DAMAGED (or unknown location), not counted
        elif lot.is_adjustment:
            _add_sellable(summary, lot.location_code, qty)  # T13: negative ADJ lines net against sellable
        elif lot.expiry_date is not None and lot.expiry_date < as_of:
            summary.expired += qty  # T14: past expiry, a write-off
        elif qty > 0:
            _add_sellable(summary, lot.location_code, qty)
    return dict(result)


def _add_sellable(summary: OnHand, location_code: str, qty: float) -> None:
    summary.sellable += qty
    summary.sellable_by_location[location_code] = summary.sellable_by_location.get(location_code, 0.0) + qty


def effective_lead_time_days(
    dana_days: int | None, bluetide_days: int | None, default_days: int
) -> tuple[int, str]:
    """The lead time the plan uses, and where it came from (T27, §6.5).

    Dana's number wins (she knows the real lead times, 00:02:25), then BlueTide's, then the
    fallback default (which should never be needed for a seeded vendor).
    Example: effective_lead_time_days(84, 56, 28) -> (84, "Dana")
    """
    if dana_days is not None:
        return dana_days, "Dana"
    if bluetide_days is not None:
        return bluetide_days, "BlueTide"
    return default_days, "default"


def vendor_terms(
    vendor: VendorInput | None,
    setting: VendorSettingInput | None,
    item_setting: ItemSettingInput | None,
    rules: BusinessRules,
) -> tuple[int, str, int, int]:
    """(lead time days, its source, cushion days, order cycle days) for one item's vendor.

    Cushion: the item's own override wins, then the vendor's setting, then the default.
    """
    lead, source = effective_lead_time_days(
        setting.lead_time_days if setting else None,
        vendor.lead_time_days_system if vendor else None,
        rules.default_lead_time_days,
    )
    if item_setting and item_setting.safety_days_override is not None:
        safety = item_setting.safety_days_override
    elif setting:
        safety = setting.safety_days
    else:
        safety = rules.default_safety_days
    cycle = setting.order_cycle_days if setting else rules.default_order_cycle_days
    return lead, source, safety, cycle


def po_arrival(
    line: POLineInput, lead_time_days: int, override: EtaOverrideInput | None, rules: BusinessRules
) -> IncomingLine:
    """When a PO line will really arrive, why we think so, and what's suspicious about it (§6.6).

    Examples (AS_OF 2026-11-16, Vietnam lead time 84 days):
      PO-260443 ordered Nov 2, BlueTide says Dec 28 -> Jan 25, 2027 ("Real lead time")
      PO-260407 ordered Aug 24, BlueTide said Oct 19 -> candidate Nov 16 = today -> LATE, no date
    """
    as_of = rules.as_of_date
    bluetide = line.expected_date_system
    real = line.order_date + timedelta(days=lead_time_days)
    candidate = max(bluetide, real) if bluetide else real
    flags: list[str] = []
    if bluetide is not None and bluetide < as_of:
        flags.append("BlueTide date has passed")
    if bluetide is not None and candidate > bluetide:
        flags.append("BlueTide date is earlier than the real lead time allows")
    reference = f"{line.po_no} line {line.line_no}"
    po = {"po_no": line.po_no, "line_no": line.line_no}

    if override is not None:
        return IncomingLine(
            "po",
            reference,
            line.qty_remaining,
            override.eta,
            f"Set by {override.set_by}",
            bluetide,
            False,
            tuple(flags),
            **po,
        )
    if candidate <= as_of:  # A18: should already be here, nothing received
        flags.append("Late: confirm with vendor")
        if rules.late_po_assumed_days is None:  # Dana Q3: don't assume an arrival date
            return IncomingLine(
                "po",
                reference,
                line.qty_remaining,
                None,
                "Late: date unknown",
                bluetide,
                True,
                tuple(flags),
                **po,
            )
        eta = as_of + timedelta(days=rules.late_po_assumed_days)
        return IncomingLine(
            "po",
            reference,
            line.qty_remaining,
            eta,
            f"Late: assumed {rules.late_po_assumed_days} days",
            bluetide,
            True,
            tuple(flags),
            **po,
        )
    source = "BlueTide date" if bluetide is not None and candidate == bluetide else "Real lead time"
    return IncomingLine(
        "po", reference, line.qty_remaining, candidate, source, bluetide, False, tuple(flags), **po
    )


def incoming_for_item(
    po_lines: list[POLineInput],
    lead_time_days: int,
    overrides: dict[tuple[str, int], EtaOverrideInput],
    handled_notes: list[HandledNoteInput],
    rules: BusinessRules,
) -> tuple[list[IncomingLine], list[IncomingLine]]:
    """Split an item's supply into (dated: counted, late without a date: shown separately)."""
    dated: list[IncomingLine] = []
    late: list[IncomingLine] = []
    for line in po_lines:
        arrival = po_arrival(line, lead_time_days, overrides.get((line.po_no, line.line_no)), rules)
        (late if arrival.eta is None else dated).append(arrival)
    for note in handled_notes:
        if note.qty is None or note.eta is None:
            continue  # a note without both only changes how the item is displayed (§6.10)
        flags = ("Your date has passed; counted as arriving today",) if note.eta < rules.as_of_date else ()
        dated.append(
            IncomingLine(
                "handled_note",
                f"Your note #{note.note_id}",
                note.qty,
                max(note.eta, rules.as_of_date),
                "Your note: ordered by phone",
                None,
                False,
                flags,
            )
        )
    dated.sort(key=lambda i: (i.eta or date.max, i.reference))
    return dated, late


def lot_status(
    lot: LotInput, location: LocationInput | None, as_of: date, six_month_line: date
) -> tuple[bool, str]:
    """(counted as sellable?, why) for one lot, in Dana's words, for the item drill-down (§9.3)."""
    if lot.qty is None:
        return False, "Not counted: no pounds-per-case to convert this lot (see Data notes)."
    if location is None:
        return False, "Not counted: unknown location."
    if not location.is_sellable:
        if location.may_return_to_stock:
            return False, "On QA hold: may come back, but can't be sold until it's released. Not counted."
        return False, "Damaged: not counted."
    if lot.is_adjustment:
        return True, "Stock adjustment: netted against what you can sell."
    if lot.expiry_date is not None and lot.expiry_date < as_of:
        return False, f"Expired {lot.expiry_date:%b %d, %Y}: not counted, a write-off."
    if lot.expiry_date is not None and lot.expiry_date < six_month_line:
        return (
            True,
            f"Counted, but inside the six-month line (expires {lot.expiry_date:%b %d, %Y}): "
            "discount or move it.",
        )
    return True, "Counted."
