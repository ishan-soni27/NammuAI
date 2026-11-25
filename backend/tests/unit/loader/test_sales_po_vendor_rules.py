"""One test per data trap for sales, purchase orders, vendors and prices (docs/DATA_AUDIT.md)."""

from __future__ import annotations

from decimal import Decimal

from app.planning.supply import effective_lead_time_days
from tests.unit.loader.factories import customer, issues, load, po, price, reference, sale, vendor

# ---- Sales --------------------------------------------------------------------------------


def _classes(result) -> list[str]:
    return [s.demand_class for s in result.dataset.sales]


def test_T16_transfers_excluded_by_customer_type() -> None:
    # Matched by customer TYPE, not the name "TRANSFER - PVD" (ADR-014).
    internal = customer(customer_code="INT01", customer_name="Anything At All", customer_type="INTERNAL")
    r = load(customers=[customer(), internal], sales=[sale(customer_code="INT01"), sale(order_no="SO-2")])
    assert _classes(r) == ["transfer", "real_demand"]


def test_T17_zero_dollar_samples_excluded() -> None:
    r = load(sales=[sale(unit_price="0", ext_price="0", qty="1")])
    assert _classes(r) == ["sample"]


def test_T18_credits_excluded() -> None:
    r = load(sales=[sale(order_no="CM-9102", qty="-2", ext_price="-300"), sale(order_no="SO-3", qty="-1")])
    assert _classes(r) == ["credit", "credit"]


def test_T19_cancelled_sales_excluded() -> None:
    # Cancelled wins even for a $0 transfer: the order of the checks follows §6.2.
    internal = customer(customer_code="INT01", customer_type="INTERNAL")
    r = load(customers=[internal], sales=[sale(status="CANCELLED", customer_code="INT01", unit_price="0")])
    assert _classes(r) == ["cancelled"]


def test_T20_one_off_order_excluded_by_order_no() -> None:
    cruise = customer(customer_code="CRU01", customer_type="CRUISE")
    r = load(
        customers=[cruise],
        sales=[
            sale(order_no="SO-245503", customer_code="CRU01", qty="330"),
            sale(order_no="SO-300001", customer_code="CRU01", qty="40"),
        ],  # if they come back, it counts
        ref=reference(excluded_orders=["SO-245503"]),
    )
    assert _classes(r) == ["one_off", "real_demand"]


def test_T21_us_dates_parsed() -> None:
    r = load(sales=[sale(order_date="01/31/2026", ship_date="02/02/2026")])
    s = r.dataset.sales[0]
    assert (str(s.order_date), str(s.ship_date)) == ("2026-01-31", "2026-02-02")
    t21 = issues(r, "T21")
    assert len(t21) == 1 and t21[0].field == "order_date,ship_date"


def test_open_orders_are_real_demand_and_keep_their_ship_date() -> None:
    # T22 groundwork: OPEN lines count as demand (by order date) and keep the ship date for the projection.
    r = load(sales=[sale(status="OPEN", order_date="2026-11-12", ship_date="2026-12-14", qty="120")])
    s = r.dataset.sales[0]
    assert (s.demand_class, str(s.ship_date), s.qty) == ("real_demand", "2026-12-14", Decimal("120"))


# ---- Purchase orders ------------------------------------------------------------------------


def test_T24_duplicate_po_lines_dropped() -> None:
    line = po(po_no="PO-260439", item_code="SHR-1620", qty_ordered="500")
    r = load(pos=[line, dict(line)])
    assert len(r.dataset.po_lines) == 1
    assert r.dataset.po_lines[0].qty_remaining_sell_uom == 500  # not 1,000
    assert issues(r, "T24")[0].action == "excluded"


def test_T25_only_open_po_remaining_is_incoming() -> None:
    r = load(
        pos=[
            po(po_no="PO-A", status="Open", qty_ordered="1000", qty_received="600"),
            po(po_no="PO-B", status="Received", qty_ordered="300", qty_received="300"),
            po(po_no="PO-C", status="Closed", qty_ordered="200", qty_received="200"),
            po(po_no="PO-D", status="Cancelled", qty_ordered="500", qty_received="0"),
        ]
    )
    remaining = {p.po_no: (p.status, p.qty_remaining_sell_uom) for p in r.dataset.po_lines}
    assert remaining == {
        "PO-A": ("open", 400),
        "PO-B": ("complete", 0),
        "PO-C": ("complete", 0),
        "PO-D": ("cancelled", 0),
    }
    assert {i.rule_code for i in issues(r, "T25")} == {"po_partially_received", "po_cancelled"}


def test_T26_overdue_open_po_flagged() -> None:
    # Phase 2 only flags it; Phase 3 re-derives the arrival date (test_T26_po_eta_rederived).
    r = load(
        pos=[po(po_no="PO-260394", expected_date="2026-10-05"), po(po_no="PO-OK", expected_date="2026-12-28")]
    )
    flagged = issues(r, "T26")
    assert len(flagged) == 1 and "PO-260394" in flagged[0].message


# ---- Vendors and prices -----------------------------------------------------------------------


def test_T27_effective_lead_time_prefers_dana() -> None:
    r = load(vendors=[vendor(lead_time_days="56")])
    assert r.dataset.vendors[0].lead_time_days_system == 56
    assert issues(r, "T27")[0].rule_code == "lead_time_differs_from_dana"
    assert effective_lead_time_days(84, 56, 28) == (84, "Dana")
    assert effective_lead_time_days(None, 56, 28) == (56, "BlueTide")
    assert effective_lead_time_days(None, None, 28) == (28, "default")
    # Text ranges take the upper bound (cautious), e.g. "2-3 wks" -> 21 days.
    r = load(vendors=[vendor(lead_time_days="2-3 wks")], ref=reference(vendor_settings=[]))
    assert r.dataset.vendors[0].lead_time_days_system == 21


def test_T28_vendor_types_classified() -> None:
    harbor = vendor(vendor_code="HCS", vendor_name="Harbor Cold Storage", lead_time_days="")
    odd = vendor(vendor_code="AFS", vendor_name="Austral Frio", payment_terms="CAD", lead_time_days="")
    r = load(
        vendors=[vendor(), harbor, odd],
        ref=reference(vendor_types={"BXE": "stock_supplier", "HCS": "service_provider"}),
    )
    types = {v.vendor_code: v.vendor_type for v in r.dataset.vendors}
    assert types == {"BXE": "stock_supplier", "HCS": "service_provider", "AFS": "stock_supplier"}
    rules = {i.rule_code for i in issues(r, "T28")}
    assert {"vendor_service_provider", "vendor_type_missing", "payment_terms_looks_like_currency"} <= rules


def test_T29_price_list_loaded_not_used() -> None:
    r = load(prices=[price(), price(item_code="FUEL-SURCH", price_tier="ALL", uom="EA", price="18.00")])
    assert len(r.dataset.prices) == 2
    assert {i.rule_code for i in issues(r, "T29")} == {"price_list_phase_2", "price_not_an_item"}


# ---- Robustness ---------------------------------------------------------------------------------


def test_unreadable_row_is_excluded_not_fatal() -> None:
    r = load(sales=[sale(qty="five"), sale(order_no="SO-2")])
    assert [s.order_no for s in r.dataset.sales] == ["SO-2"]
    errors = [i for i in r.issues if i.severity == "error"]
    assert errors and errors[0].rule_code == "unreadable_row"
