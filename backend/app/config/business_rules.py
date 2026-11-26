"""Every tunable business number, in one file (BUILD_PROMPT §6).

Purpose
    If Dana, Walt or a reviewer asks "where does 6 months / 2 weeks / 60 days come from?",
    the answer is here. Each field records what it means, where the value came from
    (a transcript timestamp, an email question, or an assumption ID from
    docs/ASSUMPTIONS.md) and how to change it. That text is stored as field *metadata*
    so `GET /api/v1/settings` can show it to Dana verbatim. The docs and the running app
    therefore can't disagree.

How it fits
    The planning engine (`app/planning/`) is pure: it receives a `BusinessRules` instance
    as an argument and never imports settings or reads the clock. Services build the
    instance with `get_business_rules()` and pass it in. Tests construct their own
    instance with `dataclasses.replace(rules, ...)` to try other values.

What is NOT here
    - Per-vendor lead times and cushion: those are Dana's knowledge and live in the
      `vendor_settings` table (seeded from data/reference/vendor_settings_seed.csv,
      editable on the Lead times page).
    - Which locations are sellable: `locations` table (data/reference/locations.csv).
    - Pack sizes, stockout windows, excluded orders: data/reference/*.csv.

How to change this
    Edit the default below, update the "source" text if the reason changed, run
    `pytest`, and log the change in docs/PROMPT_LOG.md. For a live demo tweak without a
    deploy, AS_OF_DATE can also come from the environment. The others are deliberately
    code-reviewed constants (P1 item 8 would make some editable in the UI).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, fields, replace
from datetime import date
from functools import lru_cache
from typing import Any

from app.config.settings import get_settings


def _rule(default: Any, *, doc: str, source: str, unit: str = "") -> Any:
    """Declare a rule field with its explanation attached as metadata.

    `doc` is plain English for Dana. `source` says why the value is what it is.
    `unit` is shown next to the value ("days", "weeks", "x").
    """
    return field(default=default, metadata={"doc": doc, "source": source, "unit": unit})


@dataclass(frozen=True)
class BusinessRules:
    """The business rules the planning engine runs on. Immutable on purpose.

    Frozen so a request can never mutate the shared rules by accident. To try a
    different value, build a new instance: `replace(rules, overstock_weeks=30)`.
    """

    # ---- Dates -------------------------------------------------------------------------
    as_of_date: date = _rule(
        date(2026, 11, 16),
        doc="The date the tool treats as 'today' for run-out, expiry and lead times.",
        source="Assignment README: 'Treat Monday, November 16, 2026 as today.' "
        "Overridable with the AS_OF_DATE env var. Never the computer's clock.",
    )

    # ---- Stuck with (§6.11) ------------------------------------------------------------
    six_month_line_months: int = _rule(
        6,
        unit="months",
        doc="A lot with less than this much life left (by its expiry date) is inside "
        "the six-month line: discount it or move it now.",
        source="Dana 00:03:30: 'nobody will take it with less than six months left.' (A12, T15)",
    )
    overstock_weeks: int = _rule(
        26,
        unit="weeks",
        doc="More than this many weeks of supply on hand counts as overstock.",
        source="Assumption A14 (not asked). 26 weeks = 6 months of supply.",
    )
    harbor_long_weeks: int = _rule(
        12,
        unit="weeks",
        doc="Stock at Harbor Cold Storage when the item has more than this many weeks "
        "of supply: paying storage on stock that won't be needed for months.",
        source="Walt 00:03:30: 'Long stock sitting at Harbor is the worst case.' "
        "Threshold is assumption A14.",
    )
    harbor_pallet_cost_per_month: float = _rule(
        30.0,
        unit="dollars per pallet per month",
        doc="What Harbor Cold Storage charges to keep one pallet for a month. The Harbor page turns "
        "cases into pallets with the cases per pallet Dana types for each item.",
        source="Dana's reply, 2026-11-26 (P.S.): 'Harbor charges $30 per pallet per month.' (A16)",
    )
    cases_per_pallet_max: int = _rule(
        1000,
        unit="cases",
        doc="Largest number of cases per pallet Dana can type, to catch a typo like 6000 for 60.",
        source="Assumption A48: a typo guard, far above any pallet of frozen seafood cases.",
    )

    # ---- How BlueTide marks things (labels from the call; used by the loader) ------------
    # Not numbers, but business facts all the same: kept here so no code or prefix is
    # hard-coded in logic (invariant #4) and each one has a source.
    legacy_code_prefix: str = _rule(
        "ZZ-",
        doc="Item codes starting with this are old-system leftovers: never ordered, any "
        "stock is a write-off.",
        source="Dana 00:04:40: 'Anything starting with ZZ is from the old system.' (T05)",
    )
    fresh_code_prefix: str = _rule(
        "FR-",
        doc="Item codes starting with this are fresh fish from the day boats: out of scope.",
        source="Dana 00:00:00: fresh is 'a separate thing ... I don't need help with it.' (T07)",
    )
    fresh_storage_value: str = _rule(
        "FRESH",
        doc="Items whose storage column says this are fresh: out of scope.",
        source="items.csv storage column (T07)",
    )
    discontinued_status_values: tuple[str, ...] = _rule(
        ("disc", "discontinued"),
        doc="Item status values (any capitalisation) that mean discontinued. A BLANK status "
        "does NOT mean discontinued.",
        source="T04: LOB-MEAT and PAN-PORT4 have blank status and are actively selling.",
    )
    active_status_values: tuple[str, ...] = _rule(
        ("active", "a"),
        doc="Item status values (any capitalisation) that mean active.",
        source="T04: items.csv uses 'Active', 'A' and 'active'.",
    )
    credit_order_prefix: str = _rule(
        "CM-",
        doc="Sales order numbers starting with this are credits (returns), not demand.",
        source="Marco 00:06:50: returns are entered by accounting as a credit. (T18)",
    )
    internal_customer_type: str = _rule(
        "INTERNAL",
        doc="Sales to customers of this type are building-to-building transfers, not demand.",
        source="Marco 00:06:50: transfers are entered as a sale to 'TRANSFER - PVD'. Matched by "
        "customer type, not name. (T16, ADR-014)",
    )
    adjustment_lot_prefix: str = _rule(
        "ADJ-",
        doc="On-hand lines with this lot prefix are stock adjustments, netted into sellable stock.",
        source="T13: ADJ-2211, ADJ-7360, ADJ-1069 (assumption A07).",
    )

    # ---- Item lifecycle (§6.4) ---------------------------------------------------------
    dormant_no_sales_days: int = _rule(
        60,
        unit="days",
        doc="An item with no real sales in this many days and no open PO is treated "
        "as stopped selling: never suggested for reorder.",
        source="T06. Dana 00:04:40: 'Some items we just stopped buying.' Confirmed by Dana 2026-11-26 for "
        "TIL-FIL, SHR-6170 and PAN-1012: 'we've stopped carrying all three' (A05).",
    )

    # ---- Demand forecast (§6.7) --------------------------------------------------------
    base_window_days: int = _rule(
        56,
        unit="days",
        doc="How far back we look to measure the current selling rate (last 8 weeks).",
        source="BUILD_PROMPT §6.7. Long enough to smooth weekly noise, short enough to "
        "reflect the current level.",
    )
    seasonal_window_days: int = _rule(
        365,
        unit="days",
        doc="History used to learn each category's month-by-month pattern.",
        source="BUILD_PROMPT §6.7. The exports hold one year of sales.",
    )
    seasonal_index_min: float = _rule(
        0.4,
        unit="x",
        doc="Lowest allowed seasonal multiplier (a month can't be forecast below 0.4x a normal month).",
        source="BUILD_PROMPT §6.7 / ADR-016. Clamp guards against noisy small categories.",
    )
    seasonal_index_max: float = _rule(
        2.5,
        unit="x",
        doc="Highest allowed seasonal multiplier.",
        source="BUILD_PROMPT §6.7 / ADR-016.",
    )

    open_orders_in_selling_rate: bool = _rule(
        False,
        doc="Whether open (not yet shipped) customer orders ALSO count toward the recent selling rate. "
        "They are always deducted from stock on their ship date. False (the setting) counts each "
        "order once. True would count holiday pre-bookings twice (once in the rate that drives the "
        "forecast, once when they ship), and would put the holiday bump in November instead of December.",
        source="Decided by Ishan 2026-11-26 (A23): count once. BUILD_PROMPT §6.2 counted them in the "
        "rate too. "
        "Data check: all 11,881 past orders shipped within 3 days of ordering, but this week's open orders "
        "are mostly holiday pre-bookings 1–4+ weeks ahead. Holiday protection is unaffected: SHR-1620 still "
        "plans 542 cs for December (last December's pace was ~487 cs) and is still flagged too late.",
    )

    # ---- Run-out projection and status (§6.8) -------------------------------------------
    projection_horizon_days: int = _rule(
        182,
        unit="days",
        doc="How far ahead the run-out projection looks. Beyond this we say 'more than 6 months'.",
        source="BUILD_PROMPT §6.8. 26 weeks covers the longest lead time (12 weeks) twice.",
    )
    cover_forecast_days: int = _rule(
        91,
        unit="days",
        doc="Weeks of cover = stock ÷ average weekly forecast over this many days ahead.",
        source="BUILD_PROMPT §6.8. 13 weeks of forward demand.",
    )
    order_this_week_days: int = _rule(
        7,
        unit="days",
        doc="If the latest safe order date is within this many days, the item is 'Order this week'.",
        source="BUILD_PROMPT §6.8. Dana orders every Monday (00:01:10).",
    )
    order_soon_days: int = _rule(
        21,
        unit="days",
        doc="If the latest safe order date is within this many days, the item is 'Order soon'.",
        source="BUILD_PROMPT §6.8. A three-week heads-up.",
    )
    late_po_dependency_days: int = _rule(
        14,
        unit="days",
        doc="If a late PO is due within this many days of an item's run-out date, the "
        "item is marked as depending on that PO.",
        source="BUILD_PROMPT §6.8 (depends_on_late_po).",
    )

    # ---- Incoming supply (§6.6) --------------------------------------------------------
    late_po_assumed_days: int | None = _rule(
        None,
        unit="days",
        doc="A late PO is one that should already be here (its re-derived arrival date is ON OR "
        "BEFORE today) but hasn't been received. None = it is NOT counted as coming until Dana "
        "types in a real date; it stays flagged as late, and any item that only a late PO would "
        "cover is called out. A number = assume late POs arrive that many days after today.",
        source="Dana's email 2026-11-26 (Q3): 'Flag them as late, but please don't assume they'll "
        "arrive within a week. If an item is only covered by a late PO, I want to see that.' "
        "Replaces the email default of 7 days (A03). 'On or before' decided by Ishan 2026-11-25 (A18).",
    )

    # ---- Fallbacks when Dana hasn't told us (§6.5) -------------------------------------
    default_lead_time_days: int = _rule(
        28,
        unit="days",
        doc="Lead time used only if a vendor has no lead time from Dana or BlueTide. "
        "Logged as a warning when used.",
        source="BUILD_PROMPT §6.5 fallback. Should never be needed with the seeded vendors.",
    )
    default_safety_days: int = _rule(
        7,
        unit="days",
        doc="Cushion used if a vendor has none set.",
        source="BUILD_PROMPT §6.5 fallback. Matches the non-import cushion (A02).",
    )
    default_order_cycle_days: int = _rule(
        7,
        unit="days",
        doc="Days between orders, used if a vendor has none set.",
        source="Dana 00:01:10: 'Every Monday.' (A13)",
    )

    # ---- Season markers on the item chart (§9.1) -------------------------------------------
    season_markers: tuple[tuple[str, date, date], ...] = _rule(
        (
            ("Christmas", date(2026, 12, 25), date(2026, 12, 25)),
            ("Lent 2027", date(2027, 2, 10), date(2027, 3, 28)),
        ),
        doc="Busy seasons drawn on the item chart: (label, first day, last day). Display only; the "
        "forecast learns seasonality from last year's sales, not from these dates.",
        source="BUILD_PROMPT §9.1 (Christmas and Lent 2027 shaded) and §3.8: Lent 2027 runs from "
        "Ash Wednesday Feb 10 to Easter Mar 28. Dana 00:07:55: 'Lent is huge ... the holidays are crab, "
        "shrimp and lobster tails.'",
    )

    # ---- Validation bounds for Dana's edits (§8.5) --------------------------------------
    setting_days_min: int = _rule(
        1,
        unit="days",
        doc="Smallest lead time / cushion / order cycle Dana can type in.",
        source="BUILD_PROMPT §8.5 (validated 1–365 days).",
    )
    setting_days_max: int = _rule(
        365,
        unit="days",
        doc="Largest lead time / cushion / order cycle Dana can type in.",
        source="BUILD_PROMPT §8.5 (validated 1–365 days).",
    )

    # ---- Helpers -----------------------------------------------------------------------
    def describe(self) -> list[dict[str, Any]]:
        """Every rule with its current value, unit, explanation and source.

        Feeds `GET /api/v1/settings` (Phase 4). Example item:
        {"name": "six_month_line_months", "value": 6, "unit": "months", "doc": "...", "source": "..."}
        """
        out: list[dict[str, Any]] = []
        for f in fields(self):
            value = getattr(self, f.name)
            out.append(
                {
                    "name": f.name,
                    "value": value.isoformat() if isinstance(value, date) else value,
                    "unit": f.metadata.get("unit", ""),
                    "doc": f.metadata.get("doc", ""),
                    "source": f.metadata.get("source", ""),
                }
            )
        return out

    def fingerprint(self) -> str:
        """Short, stable hash of all values, logged with every computation (§10).

        If two log lines show different fingerprints, the rules changed between them.
        """
        payload = json.dumps(asdict(self), default=str, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:12]


@lru_cache
def get_business_rules() -> BusinessRules:
    """The rules for this process: the defaults above plus the AS_OF_DATE from the environment."""
    return replace(BusinessRules(), as_of_date=get_settings().as_of_date)
