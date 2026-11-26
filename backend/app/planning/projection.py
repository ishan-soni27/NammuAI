"""Day-by-day run-out projection and the order status (BUILD_PROMPT §6.8).

Dana's first question, as arithmetic: "what will run out before a new order could get here?"

    stock = sellable today
    each day d (0 = AS_OF):  + arrivals due that day (dated POs, Dana's notes)
                             - customer orders shipping that day (T22; overdue ones count on day 0)
                             - forecast demand for that day
    run-out = the first day stock goes below zero

    new order lands  = today + lead time (L)
    order-by date    = run-out - L - cushion (S)
    TOO_LATE         run-out < today + L     (it runs out before ANY new order can arrive)
    ORDER_THIS_WEEK  order-by <= today + 7
    ORDER_SOON       order-by <= today + 21
    OK               otherwise (including "lasts beyond the 26-week horizon")
    NO_RECENT_SALES  active, nothing sold in 8 weeks and nothing promised: not in the order list

How to change this: thresholds are in business_rules.py (order_this_week_days, order_soon_days,
projection_horizon_days).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

from app.config.business_rules import BusinessRules
from app.planning.ordering import order_at_least
from app.planning.types import ProjectionPoint, Scenario, Status

EPSILON = 1e-9  # float tolerance: 259.9999999 cases is 260, and -0.0000001 is not "ran out"


@dataclass(frozen=True)
class Simulation:
    end_of_day_stock: list[float]  # one value per day 0..horizon
    lost_before_floor: float  # demand that couldn't be met while stock was floored at zero
    last_lost_day: int | None  # the last day (before the floor ends) with unmet demand


def simulate(
    start_stock: float,
    arrivals: dict[int, float],
    shipments: dict[int, float],
    forecast: list[float],
    *,
    floor_before_day: int | None = None,
) -> Simulation:
    """Run the day-by-day stock balance.

    With `floor_before_day=L`, stock can't go below zero before the new order lands: sales lost
    during a stockout are lost, not backfilled later (§6.9, "lost-sales flooring").
    """
    stock = start_stock
    lost = 0.0
    last_lost: int | None = None
    out: list[float] = []
    for day, demand in enumerate(forecast):
        stock += arrivals.get(day, 0.0)
        stock -= shipments.get(day, 0.0)
        stock -= demand
        if floor_before_day is not None and day < floor_before_day and stock < 0:
            lost += -stock
            last_lost = day
            stock = 0.0
        out.append(stock)
    return Simulation(out, lost, last_lost)


def first_negative_day(stock: list[float]) -> int | None:
    return next((day for day, value in enumerate(stock) if value < -EPSILON), None)


def classify(
    run_out: date | None, lead_time_days: int, safety_days: int, rules: BusinessRules
) -> tuple[Status, date | None]:
    """(status, order-by date) from the run-out date. See the table in the module docstring."""
    as_of = rules.as_of_date
    if run_out is None:
        return "OK", None
    order_by = run_out - timedelta(days=lead_time_days + safety_days)
    if run_out < as_of + timedelta(days=lead_time_days):
        return "TOO_LATE", order_by
    if order_by <= as_of + timedelta(days=rules.order_this_week_days):
        return "ORDER_THIS_WEEK", order_by
    if order_by <= as_of + timedelta(days=rules.order_soon_days):
        return "ORDER_SOON", order_by
    return "OK", order_by


def build_scenario(
    start_stock: float,
    arrivals: dict[int, float],
    shipments: dict[int, float],
    forecast: list[float],
    lead_time_days: int,
    safety_days: int,
    cycle_days: int,
    rules: BusinessRules,
) -> Scenario:
    """One complete projection: run-out, status, order-at-least and the shortfall."""
    as_of = rules.as_of_date
    plain = simulate(start_stock, arrivals, shipments, forecast)
    day = first_negative_day(plain.end_of_day_stock)
    run_out = as_of + timedelta(days=day) if day is not None else None
    status, order_by = classify(run_out, lead_time_days, safety_days, rules)

    floored = simulate(start_stock, arrivals, shipments, forecast, floor_before_day=lead_time_days)
    order_qty = order_at_least(floored.end_of_day_stock, lead_time_days, cycle_days, safety_days)
    gap = float(math.ceil(floored.lost_before_floor - EPSILON)) if status == "TOO_LATE" else 0.0
    # Stock comes back the day after the last unmet demand: an earlier PO (e.g. SHR-1620's 600 cs on
    # Jan 25) or, at the latest, the new order. The shortage message uses this date, not always L.
    back_in_stock = None
    if status == "TOO_LATE":
        back_day = floored.last_lost_day + 1 if floored.last_lost_day is not None else lead_time_days
        back_in_stock = as_of + timedelta(days=min(back_day, lead_time_days))

    points = tuple(
        ProjectionPoint(as_of + timedelta(days=d), round(value, 3))
        for d, value in enumerate(plain.end_of_day_stock)
    )
    return Scenario(run_out, status, order_by, order_qty, gap, back_in_stock, points)
