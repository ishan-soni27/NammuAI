"""Classification rules: what kind of sale is this, and is this item still alive?

Both answer Walt's complaint that the current reports "count things that aren't really
there" (00:04:40). The playback says to count "real demand: no hold, no damaged, no dead
items, no transfers, no samples".

How to change this ("exclude another order or customer type", BUILD_PROMPT §17)
    - Another one-off order: add it to data/reference/excluded_orders.csv (no code change).
    - Another kind of non-demand: add a step to `classify_sale` IN THE RIGHT ORDER, add its
      label to DEMAND_CLASSES in app/db/models.py, and add a test.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.config.business_rules import BusinessRules

# ---- Sales: demand_class (BUILD_PROMPT §6.2) --------------------------------------------


@dataclass(frozen=True)
class SaleFacts:
    """The few facts about a sales line that decide its class."""

    status: str  # INVOICED / OPEN / CANCELLED
    customer_type: str | None
    order_no: str
    qty: Decimal
    unit_price: Decimal
    item_lifecycle: str


def classify_sale(facts: SaleFacts, excluded_order_nos: set[str], rules: BusinessRules) -> str:
    """Return the line's demand_class. The ORDER of the checks matters and follows §6.2.

    1. cancelled           status CANCELLED (T19)
    2. transfer            customer type INTERNAL, e.g. "TRANSFER - PVD" (T16)
    3. credit              order starts with CM- or qty < 0: a return (T18)
    4. sample              unit price 0: Marco's free samples (T17)
    5. one_off             order listed in data/reference/excluded_orders.csv: the cruise (T20)
    6. fresh_out_of_scope  fresh item (T07)
    7. real_demand         everything else (INVOICED or OPEN)

    Example: a $0 line to a restaurant -> "sample". A cancelled transfer is "cancelled",
    because cancelled is checked first.
    """
    if facts.status.upper() == "CANCELLED":
        return "cancelled"
    if (facts.customer_type or "").upper() == rules.internal_customer_type.upper():
        return "transfer"
    if facts.order_no.upper().startswith(rules.credit_order_prefix.upper()) or facts.qty < 0:
        return "credit"
    if facts.unit_price == 0:
        return "sample"
    if facts.order_no in excluded_order_nos:
        return "one_off"
    if facts.item_lifecycle == "fresh_out_of_scope":
        return "fresh_out_of_scope"
    return "real_demand"


# Plain-English reasons for the Data notes page, keyed by demand_class.
DEMAND_CLASS_MESSAGES: dict[str, tuple[str, str]] = {
    # class: (trap_id, message)
    "cancelled": ("T19", "Cancelled order line: not demand."),
    "transfer": ("T16", "Transfer between our own buildings (internal customer): not demand."),
    "credit": ("T18", "Credit / return (negative quantity or CM- order): not counted as demand."),
    "sample": ("T17", "Free sample ($0 line): not counted as demand."),
    "one_off": ("T20", "One-off order listed in excluded_orders.csv (e.g. the cruise line): not demand."),
    "fresh_out_of_scope": ("T07", "Fresh item: fresh is a separate daily process and out of scope."),
}


# ---- Items: lifecycle (BUILD_PROMPT §6.4) ------------------------------------------------


def status_kind(status_raw: str, rules: BusinessRules) -> str:
    """Normalize BlueTide's free-text status (T04) to "active", "discontinued", "blank" or "unknown".

    Blank is its own kind and is NOT discontinued: LOB-MEAT and PAN-PORT4 have a blank
    status and sell every week. Examples: "A" -> "active", "DISC" -> "discontinued".
    """
    value = status_raw.strip().lower()
    if not value:
        return "blank"
    if value in rules.discontinued_status_values:
        return "discontinued"
    if value in rules.active_status_values:
        return "active"
    return "unknown"


def base_lifecycle(item_code: str, storage: str, status: str, rules: BusinessRules) -> tuple[str, str] | None:
    """Lifecycle decided by the item master alone, or None if sales must decide (dormant/active).

    Precedence (§6.4): fresh > legacy > discontinued > dormant > active.
    """
    if storage.strip().upper() == rules.fresh_storage_value.upper() or item_code.startswith(
        rules.fresh_code_prefix
    ):
        return "fresh_out_of_scope", "Fresh item from the day boats: handled separately, not planned here."
    if item_code.startswith(rules.legacy_code_prefix):
        return "legacy", (
            f"Old-system item ({rules.legacy_code_prefix} code): never reordered, any stock is a write-off."
        )
    if status == "discontinued":
        return "discontinued", "Marked discontinued in BlueTide."
    return None


def final_lifecycle(
    base: tuple[str, str] | None,
    last_real_demand: date | None,
    has_open_po: bool,
    rules: BusinessRules,
) -> tuple[str, str]:
    """Add the dormant check (T06) for items the master didn't already settle.

    Dormant = no real demand in the last DORMANT_NO_SALES_DAYS days AND no open PO. An item
    with an open PO is being restocked on purpose, so it stays active even if quiet.
    Example: TIL-FIL last sold 2026-04-16, no PO -> ("dormant", "No real sales since Apr 16, 2026 ...").
    """
    if base is not None:
        return base
    cutoff = rules.as_of_date - timedelta(days=rules.dormant_no_sales_days)
    if (last_real_demand is None or last_real_demand < cutoff) and not has_open_po:
        since = f"since {last_real_demand:%b %d, %Y}" if last_real_demand else "in the past year"
        return "dormant", (
            f"No real sales {since} ({rules.dormant_no_sales_days}+ days) and no open PO: treated as "
            "stopped selling. Pending Dana (email Q5)."
        )
    return "active", "Selling."
