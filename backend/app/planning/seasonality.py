"""Monthly seasonality per category (BUILD_PROMPT §6.7, ADR-005, ADR-016).

Dana: "right now last month's sales is October, which is slow, and December won't be. I know
that, so I adjust in my head" (00:07:55). This module makes that adjustment explicit: for each
category, how busy is each month compared with an average month?

    window        = the last 365 days before AS_OF (2025-11-16 .. 2026-11-15)
    rate[i, m]    = item i's real demand in month m / the days of month m in the window,
                    leaving out item i's known stockout days (T23; e.g. SHR-1620's Dec 11 – Jan 2)
    cat_rate[c,m] = SUM over ACTIVE items i in category c of rate[i, m], IN POUNDS
    index[c, m]   = cat_rate[c, m] / (average of cat_rate[c, ·] over the 12 months), clamped

Two deliberate details:
  - Active items only, so dead items (SHR-6170) and one-offs can't distort the Shrimp curve.
    Because the index is per CATEGORY, SHR-1620's censored December can't flatten its own
    December either: the other shrimp carry it.
  - Pounds, not "units". A category can mix items sold by the case with items sold by the pound
    (Groundfish: pollock blocks in lb and cod in cases; Salmon: sides in lb and portions in
    cases). Summing raw rates would let the pound items swamp the pattern. Each case item is
    converted with its verified pounds-per-case (data/reference/pack_sizes.csv, ADR-012).
    BUILD_PROMPT §6.7 sums raw rates; this fixes the units without changing the idea.

How to change this: the clamp limits and window are in business_rules.py. A finer model
(e.g. Easter-aligned Lent, P1 #7) would replace `compute_seasonal_index` and keep its output shape.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from app.config.business_rules import BusinessRules
from app.planning.types import ItemInput, SaleInput, StockoutInput


def window_days(as_of: date, days: int) -> list[date]:
    """The `days` calendar days ending the day BEFORE as_of (as_of itself has no sales yet)."""
    return [as_of - timedelta(days=offset) for offset in range(days, 0, -1)]


def real_demand_by_day(sales: list[SaleInput] | tuple[SaleInput, ...]) -> dict[str, dict[date, float]]:
    """Real demand per item per ORDER date (ADR-013: demand happens when the customer orders)."""
    out: dict[str, dict[date, float]] = defaultdict(lambda: defaultdict(float))
    for sale in sales:
        out[sale.item_code][sale.order_date] += sale.qty
    return out


def stockout_days(stockouts: list[StockoutInput] | tuple[StockoutInput, ...]) -> dict[str, set[date]]:
    """Every day an item was known to be out of stock (inclusive windows, T23)."""
    out: dict[str, set[date]] = defaultdict(set)
    for s in stockouts:
        day = s.start_date
        while day <= s.end_date:
            out[s.item_code].add(day)
            day += timedelta(days=1)
    return out


def pounds_factor(item: ItemInput) -> float:
    """Multiply an item's rate by this to get pounds per day (1 for items sold by the pound)."""
    if item.sell_uom == "CS" and item.lb_per_case:
        return item.lb_per_case
    return 1.0


def item_monthly_rates(demand: dict[date, float], out_days: set[date], days: list[date]) -> dict[int, float]:
    """Average daily demand per calendar month over `days`, skipping stockout days.

    A month with no countable days (fully stocked out) uses the item's own annual average.
    """
    qty_by_month: dict[int, float] = defaultdict(float)
    days_by_month: dict[int, int] = defaultdict(int)
    for day in days:
        if day in out_days:
            continue  # T23: a stockout day says nothing about demand
        qty_by_month[day.month] += demand.get(day, 0.0)
        days_by_month[day.month] += 1
    counted_days = sum(days_by_month.values())
    annual_avg = sum(qty_by_month.values()) / counted_days if counted_days else 0.0
    months = {day.month for day in days}
    return {m: (qty_by_month[m] / days_by_month[m] if days_by_month[m] else annual_avg) for m in months}


def compute_seasonal_index(
    items: list[ItemInput] | tuple[ItemInput, ...],
    demand_by_item: dict[str, dict[date, float]],
    out_days_by_item: dict[str, set[date]],
    rules: BusinessRules,
) -> dict[str, dict[int, float]]:
    """category -> {month 1..12: multiplier}. 1.0 = an average month; 1.5 = 50% busier.

    Only active items should be passed in (the caller filters).
    Example: if Shrimp sells 1,200 lb/day in December and 800 lb/day in an average month,
    index["Shrimp"][12] = 1.5.
    """
    days = window_days(rules.day_zero, rules.seasonal_window_days)  # known sales end at the data date
    cat_rate: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for item in items:
        rates = item_monthly_rates(
            demand_by_item.get(item.item_code, {}), out_days_by_item.get(item.item_code, set()), days
        )
        factor = pounds_factor(item)
        for month, rate in rates.items():
            cat_rate[item.category][month] += rate * factor

    index: dict[str, dict[int, float]] = {}
    for category, by_month in cat_rate.items():
        average = sum(by_month.values()) / len(by_month) if by_month else 0.0
        index[category] = {
            month: (
                _clamp(by_month[month] / average, rules.seasonal_index_min, rules.seasonal_index_max)
                if average > 0
                else 1.0
            )
            for month in range(1, 13)
        }
    return index


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
