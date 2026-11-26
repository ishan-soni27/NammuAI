"""Plain-English "why" steps for an item (BUILD_PROMPT §8.4, §9.3, §9.5).

Dana 00:11:00: "If it says I'm out in three weeks, I want to click in and see what I have, what
I'm selling and what's coming." These steps are built from the SAME numbers the engine used, so
the explanation can never disagree with the result.

Copy rules (§9.5): Dana's words ("promised to customers", "on hold", "runs out", "order at
least"), always with units, dates like "Mon Dec 14" plus "in 4 weeks". Never "SKU", "UOM",
"safety stock" or "committed".
"""

from __future__ import annotations

from datetime import date

from app.planning.types import CommittedLine, DemandProfile, IncomingLine, OnHand, Scenario

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


def explain(
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
    new_order_arrival: date,
    confirmed: Scenario,
    if_late_arrive: Scenario | None,
    covered_only_by_late_po: bool,
) -> tuple[str, ...]:
    """The numbered steps of the item drill-down (§9.3), as plain sentences."""
    u = sell_uom
    steps: list[str] = []

    # 1. What you can sell
    where = ", ".join(f"{loc} {qty(v, u)}" for loc, v in sorted(on_hand.sellable_by_location.items()) if v)
    not_counted = [
        f"{qty(v, u)} {label}"
        for v, label in [
            (on_hand.on_hold, "on hold"),
            (on_hand.damaged, "damaged"),
            (on_hand.expired, "expired"),
        ]
        if v > 0
    ]
    step = f"You can sell {qty(on_hand.sellable, u)} now" + (f" ({where})." if where else ".")
    if not_counted:
        step += " Not counted: " + ", ".join(not_counted) + "."
    steps.append(step)

    # 2. Promised to customers
    total = sum(c.qty for c in committed)
    if committed:
        biggest = max(committed, key=lambda c: c.qty)
        ship_dates = [c.ship_date for c in committed if c.ship_date]
        span = f", shipping {day(min(ship_dates))} to {day(max(ship_dates))}" if ship_dates else ""
        steps.append(
            f"Promised to customers: {qty(total, u)} on {len(committed)} open "
            f"order{'s' if len(committed) != 1 else ''}"
            f"{span}. Largest: {biggest.customer_name}, {qty(biggest.qty, u)}"
            + (f" on {day(biggest.ship_date)}." if biggest.ship_date else ".")
        )
    else:
        steps.append("Nothing is promised to customers yet.")

    # 3. On the way
    parts = []
    for line in incoming:
        assert line.eta is not None
        text = f"{line.reference}: {qty(line.qty, u)} arriving about {day(line.eta)}"
        if line.bluetide_date and line.bluetide_date != line.eta:
            text += f" (BlueTide said {day(line.bluetide_date)}; corrected to the real lead time)"
        parts.append(text)
    if parts:
        steps.append("On the way: " + "; ".join(parts) + ".")
    else:
        steps.append("Nothing is on the way with a date.")
    for line in late:
        said = f"BlueTide said {day(line.bluetide_date)}" if line.bluetide_date else "no date in BlueTide"
        steps.append(
            f"Late, date unknown: {line.reference}, {qty(line.qty, u)} ({said}, nothing received). "
            "Not counted until you enter a real date."
        )

    # 4. How fast it's selling, and what the season does next
    per_week = demand.base_rate_per_day * 7
    upcoming = [(as_of.month + k - 1) % 12 + 1 for k in range(0, 3)]
    season = ", ".join(f"{MONTHS[m - 1]} {demand.index_by_month.get(m, 1.0):.1f}×" for m in upcoming)
    steps.append(
        f"Selling about {qty(per_week, u)} a week over the last {weeks(demand.base_days)}. "
        f"{category} season ahead compared with an average month: {season}."
    )

    # 5. So it runs out about...
    if confirmed.run_out_date:
        steps.append(
            f"So it runs out about {day(confirmed.run_out_date)} ({relative(confirmed.run_out_date, as_of)})."
        )
    else:
        steps.append("At this rate it lasts more than 6 months.")

    # 6. A new order placed today lands about...
    steps.append(
        f"A new order placed today lands about {day(new_order_arrival)} "
        f"({vendor_name}, {weeks(lead_time_days)} from order to our building)."
    )

    # 7. Order at least / shortfall
    if confirmed.status == "TOO_LATE":
        back = confirmed.back_in_stock_date or new_order_arrival
        restocked_by = (
            "when stock already on the way lands"
            if back < new_order_arrival
            else "when a new order could land"
        )
        steps.append(
            f"That's too late: you'll be short about {qty(confirmed.gap_qty, u)} between "
            f"{day(confirmed.run_out_date or as_of)} and {day(back)} ({restocked_by}). Ask the vendor to "
            "expedite or find another source."
        )
        if confirmed.order_at_least == 0:
            steps.append(
                f"Ordering more today wouldn't close that gap: it would land {day(new_order_arrival)}, "
                "after the stock already on the way, which covers you from then on."
            )
    if confirmed.order_at_least > 0:
        steps.append(
            f"Order at least {qty(confirmed.order_at_least, u)} to get you to the next Monday order's "
            f"arrival plus {weeks(safety_days)} of cushion."
        )
    elif confirmed.status in {"OK", "NO_RECENT_SALES"}:
        steps.append("No order needed this week.")

    if late and if_late_arrive is not None:
        if covered_only_by_late_po:
            steps.append(
                "Only covered by the late PO: if it shows up now, this item would be fine"
                + (
                    f" until about {day(if_late_arrive.run_out_date)}."
                    if if_late_arrive.run_out_date
                    else " for more than 6 months."
                )
            )
        elif if_late_arrive.run_out_date != confirmed.run_out_date:
            steps.append(
                "Even if the late PO showed up today, it would only push the run-out to about "
                + (day(if_late_arrive.run_out_date) if if_late_arrive.run_out_date else "beyond 6 months")
                + "."
            )
        if if_late_arrive.order_at_least != confirmed.order_at_least:
            instead = (
                f"order at least {qty(if_late_arrive.order_at_least, u)} instead"
                if if_late_arrive.order_at_least > 0
                else "you wouldn't need to order"
            )
            steps.append(f"If the late PO does show up, {instead} (so you don't double order).")
    return tuple(steps)
