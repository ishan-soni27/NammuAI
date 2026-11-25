"""Small, pure parsing and normalizing helpers used by the loader rules.

Each function turns one messy BlueTide string into a clean value, and says how it did it,
so the caller can log a `corrected` data issue when something changed.

How to change this: add a helper here when a new kind of messy value appears, with a
docstring example and a unit test in tests/unit/loader/test_normalize.py.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

DateFormat = Literal["iso", "us", "blank"]

_US_DATE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# "56", "2-3 wks", "3 weeks", "10 days", "6 wk"
_LEAD_TIME = re.compile(
    r"^\s*(?P<low>\d+)\s*(?:-\s*(?P<high>\d+))?\s*(?P<unit>d|day|days|w|wk|wks|week|weeks)?\s*$",
    re.IGNORECASE,
)
# One "<count> x <size> <unit>" or "<size> <unit>" chunk, e.g. "6x2.2lb", "10/2#", "5 x 2 lb", "5kg"
_PACK = re.compile(
    # (?![a-z]) instead of \b: "\b" never matches after "#" at the end of "10#".
    r"^\s*(?:(?P<count>\d+)\s*[x/]\s*)?(?P<size>\d+(?:\.\d+)?)\s*(?P<unit>lbs|lb|#|kg)(?![a-z])",
    re.IGNORECASE,
)
LB_PER_KG = Decimal("2.20462")


def canonical_code(raw: str) -> str:
    """The one true item code: trimmed and upper-cased (T02).

    Examples: "shr-1620 " -> "SHR-1620", "Sal-Por6" -> "SAL-POR6", "COD-LOIN " -> "COD-LOIN".
    """
    return raw.strip().upper()


def normalize_category(raw: str) -> str:
    """Trim and title-case a category (T08): "groundfish" -> "Groundfish", "SHRIMP" -> "Shrimp"."""
    return raw.strip().title()


def blank_to_none(raw: str) -> str | None:
    """Trimmed value, or None if it is empty. Used for optional text columns (UPC stays a string)."""
    value = raw.strip()
    return value or None


def parse_business_date(raw: str) -> tuple[date | None, DateFormat]:
    """Parse "2026-01-31" (ISO) or "01/31/2026" (US month/day/year) (T21).

    US format is safe to assume here: in these exports the second component reaches 31, so
    it can only be the day. Raises ValueError for anything else. Blank -> (None, "blank").
    Examples: "2026-01-31" -> (date(2026, 1, 31), "iso"); "01/31/2026" -> (date(2026, 1, 31), "us").
    """
    value = raw.strip()
    if not value:
        return None, "blank"
    if _ISO_DATE.match(value):
        return date.fromisoformat(value), "iso"
    if _US_DATE.match(value):
        return datetime.strptime(value, "%m/%d/%Y").date(), "us"
    raise ValueError(f"unrecognized date {raw!r}")


def parse_decimal(raw: str) -> Decimal | None:
    """Exact decimal (no float drift on pound quantities, §16). Blank -> None.

    Example: "2789.6" -> Decimal("2789.6"). Raises ValueError for non-numbers.
    """
    value = raw.strip()
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"not a number: {raw!r}") from exc


def parse_int(raw: str) -> int | None:
    """Whole number or None if blank. "24" -> 24. Raises ValueError for "24.5" or text."""
    value = raw.strip()
    return int(value) if value else None


def parse_lead_time_days(raw: str) -> tuple[int | None, str]:
    """BlueTide's lead time in days, plus how we read it (T27).

    Plain numbers are days. Ranges take the UPPER bound, because a longer lead time means
    ordering earlier, and running out hurts more than overstock (ADR-006).
    Examples: "56" -> (56, "days"); "2-3 wks" -> (21, "upper bound of a range in weeks");
              "" -> (None, "blank"); "about a month" -> (None, "unreadable").
    """
    value = raw.strip()
    if not value:
        return None, "blank"
    match = _LEAD_TIME.match(value)
    if not match:
        return None, "unreadable"
    number = int(match["high"] or match["low"])
    in_weeks = (match["unit"] or "d").lower().startswith("w")
    days = number * 7 if in_weeks else number
    if match["high"]:
        return days, f"upper bound of a range in {'weeks' if in_weeks else 'days'}"
    return days, "weeks" if in_weeks else "days"


def parse_pack_size_lb(raw: str) -> Decimal | None:
    """Pounds per case from free-text pack size, or None if it can't be read (T09).

    Used ONLY to cross-check data/reference/pack_sizes.csv (the human-verified source of
    truth, ADR-012) and to flag new items. Never used to convert stock at runtime.
    Examples: "6x2.2lb" -> 13.2; "10/2#" -> 20 (# means lb); "5kg" -> 11.0231;
              "15 lb case" -> 15; "catch wt" -> None; "" -> None.
    """
    match = _PACK.match(raw or "")
    if not match:
        return None
    count = Decimal(match["count"]) if match["count"] else Decimal(1)
    size = Decimal(match["size"])
    pounds = count * size
    if match["unit"].lower() == "kg":
        pounds = pounds * LB_PER_KG
    return pounds
