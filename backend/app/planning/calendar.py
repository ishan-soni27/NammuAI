"""Business-date helpers. Never reads the clock: "today" is always passed in (AS_OF_DATE).

How to change this: add helpers here only if they are pure date arithmetic.
"""

from __future__ import annotations

import calendar
from datetime import date


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
