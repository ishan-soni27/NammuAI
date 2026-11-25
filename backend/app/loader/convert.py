"""Unit conversion: plan every item in its own selling unit, CS or LB (T10, §6.3, ADR-012).

Dana today "converts in her head" (00:01:10). The loader does it once, with the
human-verified pounds-per-case in data/reference/pack_sizes.csv, and keeps the original
quantity, unit and cost next to the converted ones so nothing is hidden.

    LB lot of a CS item:  qty / lb_per_case,  cost (per lb) * lb_per_case
    CS lot of an LB item: qty * lb_per_case,  cost (per case) / lb_per_case
    Same unit:            unchanged
    Missing factor:       None (the caller logs an error and the lot is not counted)

Example: LOB-T56 (10 lb cases) lot of 220 LB at $23.66/lb -> 22 CS at $236.60/cs (golden G05).
"""

from __future__ import annotations

from decimal import Decimal

UNITS = {"CS", "LB"}


def to_sell_uom(qty: Decimal, uom: str, sell_uom: str, lb_per_case: Decimal | None) -> Decimal | None:
    """Convert a quantity into the item's selling unit, or None if it can't be done safely."""
    uom, sell_uom = uom.strip().upper(), sell_uom.strip().upper()
    if uom == sell_uom:
        return qty
    if uom not in UNITS or sell_uom not in UNITS or not lb_per_case:
        return None
    return qty / lb_per_case if sell_uom == "CS" else qty * lb_per_case


def cost_to_sell_uom(
    cost: Decimal | None, uom: str, sell_uom: str, lb_per_case: Decimal | None
) -> Decimal | None:
    """Convert a unit cost into cost per selling unit (the inverse of the quantity rule)."""
    if cost is None:
        return None
    uom, sell_uom = uom.strip().upper(), sell_uom.strip().upper()
    if uom == sell_uom:
        return cost
    if uom not in UNITS or sell_uom not in UNITS or not lb_per_case:
        return None
    return cost * lb_per_case if sell_uom == "CS" else cost / lb_per_case
