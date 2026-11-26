"""The numbers-only "why" for an item, and the one instruction for late-PO items (ADR-033).

Dana 00:11:00: "If it says I'm out in three weeks, I want to click in and see what I have, what
I'm selling and what's coming." Ishan (2026-11-26): show that as numbers, not sentences that read
like a memo. `breakdown` returns one row per number the engine used, with its date and a link to the
table on the item page that holds the source rows, so the "why" can never disagree with the result.

Copy rules (§9.5): Dana's words ("promised to customers", "on hold", "runs out", "order at
least"), always with units. Never "SKU", "UOM", "safety stock" or "committed".
"""

from __future__ import annotations

from datetime import date

from app.planning.types import BreakdownRow, CommittedLine, DemandProfile, IncomingLine, OnHand, Scenario

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# Units spelled out for Dana (Ishan, 2026-11-26: "what is cs?"). BlueTide's codes stay in the data.
UNIT_WORDS: dict[str, tuple[str, str]] = {"CS": ("case", "cases"), "LB": ("lb", "lb")}


def unit_word(uom: str, value: float) -> str:
    """'cases' / 'case' / 'lb'. An unknown code is shown lower-cased, as BlueTide wrote it."""
    one, many = UNIT_WORDS.get(uom.upper(), (uom.lower(), uom.lower()))
    return one if round(value) == 1 else many


def qty(value: float, uom: str) -> str:
    """'480 cases', '8,479 lb'. Whole units: Dana counts cases, and pounds don't need decimals here."""
    return f"{round(value):,} {unit_word(uom, value)}"


def day(value: date) -> str:
    """'Mon Dec 14'."""
    return f"{value:%a %b} {value.day}"


def relative(value: date, as_of: date) -> str:
    """'today', 'in 5 days', 'in 4 weeks', '3 days ago'."""
    days = (value - as_of).days
    if days == 0:
        return "today"
    if days < 0:
        return f"{-days} day{'s' if days != -1 else ''} ago"
    if days < 14:
        return f"in {days} day{'s' if days != 1 else ''}"
    return f"in {round(days / 7)} weeks"


def weeks(days: int) -> str:
    return f"{days // 7} week{'s' if days // 7 != 1 else ''}" if days % 7 == 0 else f"{days} days"


def _late_list(late: tuple[IncomingLine, ...], u: str) -> str:
    """'PO-260394 (800 cases)', or 'PO-x (N cases) and PO-y (M cases)'."""
    parts = [f"{line.po_no or line.reference} ({qty(line.qty, u)})" for line in late]
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def late_po_instruction(sell_uom: str, order_at_least: float, late: tuple[IncomingLine, ...]) -> str:
    """The one instruction for an item that only a late PO would cover (Dana Q3; wording Ishan's).

    Replaces two lines that contradicted each other ("Order at least N" and "if the late PO shows up
    you wouldn't need to order"). Examples:
      "Order at least 127 cases, unless PO-260394 (800 cases) is really coming. Ask the supplier for its
       date and set it here, and these numbers update."
      "Nothing to order today, but PO-260376 (400 cases) is late. Ask the supplier ..."
    """
    pos = _late_list(late, sell_uom)
    ask = "Ask the supplier for its date and set it here, and these numbers update."
    if len(late) > 1:
        ask = "Ask the suppliers for their dates and set them here, and these numbers update."
    if order_at_least > 0:
        coming = "is" if len(late) == 1 else "are"
        return f"Order at least {qty(order_at_least, sell_uom)}, unless {pos} {coming} really coming. {ask}"
    late_word = "is" if len(late) == 1 else "are"
    return f"Nothing to order today, but {pos} {late_word} late. {ask}"


def breakdown(
    *,
    as_of: date,
    sell_uom: str,
    on_hand: OnHand,
    committed: tuple[CommittedLine, ...],
    incoming: tuple[IncomingLine, ...],
    late: tuple[IncomingLine, ...],
    demand: DemandProfile,
    category: str,
    vendor_name: str,
    lead_time_days: int,
    safety_days: int,
    horizon_days: int,
    new_order_arrival: date,
    confirmed: Scenario,
    if_late_arrive: Scenario | None,
) -> tuple[BreakdownRow, ...]:
    """The rows that apply, in reading order: what you have, what's promised, what's coming, how fast
    it sells, so when it runs out, and what to do. Each number is the one the engine used."""
    u = sell_uom
    rows: list[BreakdownRow] = []
    rows.append(
        BreakdownRow(
            "can_sell",
            "Can sell now",
            on_hand.sellable,
            unit_word(u, on_hand.sellable),
            detail=" · ".join(
                f"{loc} {round(v):,}" for loc, v in sorted(on_hand.sellable_by_location.items()) if v
            )
            or None,
            link="#have",
        )
    )
    not_counted = [
        (label, v)
        for label, v in (
            ("on hold", on_hand.on_hold),
            ("damaged", on_hand.damaged),
            ("expired", on_hand.expired),
        )
        if v > 0
    ]
    if not_counted:
        total = sum(v for _, v in not_counted)
        rows.append(
            BreakdownRow(
                "not_counted",
                "Not counted",
                total,
                unit_word(u, total),
                detail=" · ".join(f"{label} {round(v):,}" for label, v in not_counted),
                link="#have",
            )
        )
    if committed:
        total = sum(c.qty for c in committed)
        biggest = max(committed, key=lambda c: c.qty)
        dates = [c.ship_date for c in committed if c.ship_date]
        span = f", shipping {day(min(dates))} to {day(max(dates))}" if dates else ""
        largest = f"; largest {biggest.customer_name} {round(biggest.qty):,}" + (
            f" on {day(biggest.ship_date)}" if biggest.ship_date else ""
        )
        n = len(committed)
        rows.append(
            BreakdownRow(
                "promised",
                "Promised to customers",
                total,
                unit_word(u, total),
                detail=f"{n} open order{'s' if n != 1 else ''}{span}{largest}",
                link="#promised",
            )
        )
    for line in incoming:
        if line.eta_source.startswith("Set by"):
            note = ("date " + line.eta_source[0].lower() + line.eta_source[1:]) + (
                f"; BlueTide said {day(line.bluetide_date)}" if line.bluetide_date else ""
            )
        elif line.bluetide_date and line.bluetide_date != line.eta:
            note = f"BlueTide says {day(line.bluetide_date)}; the real lead time says later"
        else:
            note = line.eta_source.lower() if line.source == "po" else "your handled note"
        rows.append(
            BreakdownRow(
                "on_the_way",
                f"On the way: {line.reference}",
                line.qty,
                unit_word(u, line.qty),
                on=line.eta,
                detail=note,
                link="#on-the-way",
            )
        )
    for line in late:
        said = f"BlueTide said {day(line.bluetide_date)}" if line.bluetide_date else "no date in BlueTide"
        rows.append(
            BreakdownRow(
                "late",
                f"Late, not counted: {line.reference}",
                line.qty,
                unit_word(u, line.qty),
                detail=f"{said}; nothing received",
                link="#late",
            )
        )
    per_week = demand.base_rate_per_day * 7
    rows.append(
        BreakdownRow(
            "selling",
            "Selling now",
            round(per_week, 1),
            f"{unit_word(u, per_week)} a week",
            detail=f"last {weeks(demand.base_days)}",
            link="#demand",
        )
    )
    upcoming = [(as_of.month + k - 1) % 12 + 1 for k in range(0, 3)]
    rows.append(
        BreakdownRow(
            "season",
            "Season ahead",
            detail=f"{category}: "
            + " · ".join(f"{MONTHS[m - 1]} {demand.index_by_month.get(m, 1.0):.1f}×" for m in upcoming),
            link="#demand",
        )
    )
    rows.append(
        BreakdownRow(
            "runs_out",
            "Runs out",
            on=confirmed.run_out_date,
            detail=relative(confirmed.run_out_date, as_of)
            if confirmed.run_out_date
            else f"not within {weeks(horizon_days)}",
            link="#chart",
        )
    )
    rows.append(
        BreakdownRow(
            "new_order_lands",
            "A new order placed today lands",
            on=new_order_arrival,
            detail=f"{vendor_name}, {weeks(lead_time_days)} to arrive + {weeks(safety_days)} cushion",
            link="#chart",
        )
    )
    if confirmed.status == "TOO_LATE":
        back = confirmed.back_in_stock_date or new_order_arrival
        by = "stock on the way lands" if back < new_order_arrival else "a new order lands"
        rows.append(
            BreakdownRow(
                "short",
                "Short",
                confirmed.gap_qty,
                unit_word(u, confirmed.gap_qty),
                on=confirmed.run_out_date,
                detail=f"until {day(back)}, when {by}",
                link="#chart",
            )
        )
    if confirmed.status in ("TOO_LATE", "ORDER_THIS_WEEK", "ORDER_SOON") or confirmed.order_at_least > 0:
        order_by = confirmed.order_by_date
        on = order_by if order_by and order_by >= as_of else None  # the date column: order by
        if confirmed.order_at_least == 0 and confirmed.status == "TOO_LATE":
            on, note = None, f"an order today lands {day(new_order_arrival)}, after the stock on the way"
        elif confirmed.order_at_least == 0:
            note = "nothing needed today; order by this date"
        else:
            note = f"covers to next Monday's order + {weeks(safety_days)} cushion"
            if order_by and order_by < as_of:
                note = f"order now (was due {day(order_by)}); {note}"
        rows.append(
            BreakdownRow(
                "order_at_least",
                "Order at least",
                confirmed.order_at_least,
                unit_word(u, confirmed.order_at_least),
                on=on,
                detail=note,
                link="#chart",
            )
        )
    if late and if_late_arrive is not None:
        runs = (
            f"runs out {day(if_late_arrive.run_out_date)}"
            if if_late_arrive.run_out_date
            else f"lasts beyond {weeks(horizon_days)}"
        )
        order = (
            f"order at least {qty(if_late_arrive.order_at_least, u)}"
            if if_late_arrive.order_at_least > 0
            else "nothing to order"
        )
        rows.append(
            BreakdownRow(
                "if_late_arrives",
                "If the late PO arrives today",
                detail=f"{runs} · {order}",
                link="#late",
            )
        )
    return tuple(rows)
