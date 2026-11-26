"""Business-date helpers. Never reads the clock: "today" is always passed in (AS_OF_DATE).

How to change this: add helpers here only if they are pure date arithmetic.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta


def add_months(start: date, months: int) -> date:
    """Add calendar months, clamping the day to the end of the target month.

    Used for the six-month line (T15): AS_OF + 6 months. Examples:
        add_months(date(2026, 11, 16), 6) -> date(2027, 5, 16)
        add_months(date(2026, 8, 31), 6)  -> date(2027, 2, 28)   (no Feb 31)
        add_months(date(2027, 8, 31), 6)  -> date(2028, 2, 29)   (leap year, §16)
    """
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def easter(year: int) -> date:
    """Easter Sunday (Gregorian), by the anonymous Gregorian algorithm (Meeus/Jones/Butcher).

    Examples: easter(2027) -> date(2027, 3, 28); easter(2028) -> date(2028, 4, 16).
    """
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    month, day = divmod(h + m - 7 * n + 114, 31)
    return date(year, month, day + 1)


def season_markers(start: date, end: date) -> list[tuple[str, date, date]]:
    """The busy seasons to shade on an item chart covering start..end: (label, first day, last day).

    Christmas (Dec 25) and Lent (Ash Wednesday = Easter - 46 days, to Easter) for every year the
    chart touches. Display only: the forecast learns seasonality from sales, not from these dates
    (Dana 00:07:55: "Lent is huge ... the holidays are crab, shrimp and lobster tails").
    Example: season_markers(date(2026, 11, 16), date(2027, 5, 17)) ->
        [("Christmas", 2026-12-25, 2026-12-25), ("Lent 2027", 2027-02-10, 2027-03-28)]
    """
    out: list[tuple[str, date, date]] = []
    for year in range(start.year, end.year + 1):
        sunday = easter(year)
        lent = (f"Lent {year}", sunday - timedelta(days=46), sunday)
        christmas = ("Christmas", date(year, 12, 25), date(year, 12, 25))
        for label, first, last in (lent, christmas):
            if last >= start and first <= end:
                out.append((label, first, last))
    return sorted(out, key=lambda x: x[1])
