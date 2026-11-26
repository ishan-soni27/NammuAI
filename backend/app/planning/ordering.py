"""How much to order: "order at least" (BUILD_PROMPT §6.9, ADR-009).

Labelled "order at least" on screen because Dana makes the final call; container and
minimum-order rounding is P1 (no MOQ or container data in the exports).
In plain English: "A new order placed today lands about {arrival}. To get you to the next Monday
order's arrival plus {cushion} of cushion, order at least {Q}."
"""

from __future__ import annotations

import math

EPSILON = 1e-9


def order_at_least(
    floored_stock: list[float], lead_time_days: int, cycle_days: int, safety_days: int
) -> float:
    """Smallest order placed today that keeps stock above zero from its arrival until the NEXT
    Monday order could arrive, plus the cushion (§6.9):

        window = [today + L, today + L + order cycle + S]
        order at least = ceil(max(0, -lowest stock in that window))

    Uses the floored simulation, because stock that ran out before the order lands can't be
    "paid back" by it: those sales are already lost. Rounded UP (with a float tolerance).
    """
    start = lead_time_days
    end = min(lead_time_days + cycle_days + safety_days, len(floored_stock) - 1)
    if start > end:
        return 0.0
    lowest = min(floored_stock[start : end + 1])
    return float(math.ceil(max(0.0, -lowest) - EPSILON)) if lowest < -EPSILON else 0.0
