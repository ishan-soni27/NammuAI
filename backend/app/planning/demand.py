"""How fast an item is selling now, and the daily forecast ahead (BUILD_PROMPT §6.7, ADR-005).

The model is the one Dana runs in her head: current selling rate × what the season does next.

    base_rate  = real demand over the last 8 weeks / the days counted (stockout days left out, T23)
    base_index = how seasonal those 8 weeks were (day-weighted average of the category index)
    level      = base_rate / base_index        "what this item sells in a normal month"
    forecast d = level × index[category, month of d]

Example: SHR-1620 sold about 6 cs/day in late Sep to mid Nov, when shrimp runs at 0.8× an average
month. Its normal level is 6 / 0.8 = 7.5 cs/day, so a 1.4× December forecasts 10.5 cs/day.

How to change this: the 8-week window is BASE_WINDOW_DAYS in business_rules.py.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.config.business_rules import BusinessRules
from app.planning.seasonality import window_days
from app.planning.types import DemandProfile


def demand_profile(
    demand: dict[date, float],
    out_days: set[date],
    index_by_month: dict[int, float],
    rules: BusinessRules,
) -> DemandProfile:
    """Measure the current rate and turn it into a normal-season level for one item."""
    base_days = [d for d in window_days(rules.as_of_date, rules.base_window_days) if d not in out_days]
    base_qty = sum(demand.get(d, 0.0) for d in base_days)
    base_rate = base_qty / len(base_days) if base_days else 0.0
    base_index = (
        sum(index_by_month.get(d.month, 1.0) for d in base_days) / len(base_days) if base_days else 1.0
    )
    level = base_rate / base_index if base_index > 0 else base_rate

    history: dict[str, float] = {}
    for day in window_days(rules.as_of_date, rules.seasonal_window_days):
        key = f"{day:%Y-%m}"
        history[key] = history.get(key, 0.0) + demand.get(day, 0.0)

    return DemandProfile(
        base_rate_per_day=base_rate,
        base_days=len(base_days),
        base_index=base_index,
        level_per_day=level,
        index_by_month=dict(index_by_month),
        monthly_history=history,
    )


def daily_forecast(profile: DemandProfile, as_of: date, horizon_days: int) -> list[float]:
    """Forecast demand for day 0 (as_of) through day `horizon_days`, inclusive."""
    return [
        profile.level_per_day * profile.index_by_month.get((as_of + timedelta(days=d)).month, 1.0)
        for d in range(horizon_days + 1)
    ]
