"""One test per data trap for the item master and on-hand file (docs/DATA_AUDIT.md)."""

from __future__ import annotations

from decimal import Decimal

from app.planning.supply import LocationInput, LotInput, summarize_on_hand
from tests.unit.loader.factories import RULES, issues, item, load, lot, reference, sale


def _on_hand(result):
    d = result.dataset
    return summarize_on_hand(
        [
            LotInput(
                lot.item_code,
                lot.location_code,
                lot.lot_no,
                lot.qty_sell_uom,
                lot.expiry_date,
                lot.is_adjustment,
            )
            for lot in d.lots
        ],
        [LocationInput(x.code, x.is_sellable, x.may_return_to_stock) for x in d.locations],
        RULES.as_of_date,
    )


# ---- Item master ------------------------------------------------------------------------


def test_T02_item_codes_canonicalized() -> None:
    r = load(lots=[lot(item_code="shr-1620 ", location="PVD", qty="80")], sales=[sale(item_code="Shr-1620")])
    assert {lot.item_code for lot in r.dataset.lots} == {"SHR-1620"}
    assert {s.item_code for s in r.dataset.sales} == {"SHR-1620"}
    assert {a.alias_code for a in r.dataset.aliases} == {"shr-1620 ", "Shr-1620"}
    assert len(issues(r, "T02")) == 2 and all(i.action == "corrected" for i in issues(r, "T02"))


def test_T03_duplicate_item_rows_collapsed() -> None:
    canonical = item(upc="030931011872")
    duplicate = item(item_code="shr-1620 ", upc="", created_date="2021-04-12", pack_size="10/2#")
    r = load(items=[duplicate, canonical])  # duplicate first: the canonical spelling must still win
    assert len(r.dataset.items) == 1
    kept = r.dataset.items[0]
    assert kept.item_code == "SHR-1620" and kept.upc == "030931011872" and kept.pack_size_raw == "10x2lb"
    assert [i.action for i in issues(r, "T03")] == ["excluded"]
    assert "shr-1620 " in {a.alias_code for a in r.dataset.aliases}


def test_T04_blank_status_is_not_discontinued() -> None:
    r = load(items=[item(status="")], sales=[sale(order_date="2026-11-10")])
    assert r.dataset.items[0].lifecycle_status == "active"
    assert issues(r, "T04")[0].rule_code == "status_blank"
    r = load(items=[item(status="DISC")])
    assert r.dataset.items[0].lifecycle_status == "discontinued"
    r = load(items=[item(status="A")])
    assert r.dataset.items[0].lifecycle_status == "active"
    assert issues(r, "T04")[0].action == "corrected"


def test_T05_zz_items_are_legacy() -> None:
    zz = item(item_code="ZZ-SCL-0002", status="Active", pack_size="", vendor_code="BXE")
    r = load(
        items=[zz],
        lots=[lot(item_code="ZZ-SCL-0002", location="HCS", qty="8", expiry_date="2024-01-01")],
        sales=[sale(item_code="ZZ-SCL-0002")],  # even recent sales don't revive a ZZ item
        ref=reference(pack_sizes={"ZZ-SCL-0002": None}),
    )
    assert r.dataset.items[0].lifecycle_status == "legacy"
    assert {i.rule_code for i in issues(r, "T05")} == {"legacy_item", "legacy_stock"}
    assert "still marks it Active" in issues(r, "T05")[0].message


def test_T06_dormant_items_detected() -> None:
    quiet = sale(order_date="2026-04-16", ship_date="2026-04-17")  # 214 days before AS_OF
    r = load(sales=[quiet])
    assert r.dataset.items[0].lifecycle_status == "dormant"
    assert "Apr 16, 2026" in r.dataset.items[0].lifecycle_reason
    # An open PO means Dana is restocking it on purpose: not dormant.
    from tests.unit.loader.factories import po

    r = load(sales=[quiet], pos=[po()])
    assert r.dataset.items[0].lifecycle_status == "active"
    # A sale inside the 60-day window keeps it active.
    r = load(sales=[sale(order_date="2026-09-20")])
    assert r.dataset.items[0].lifecycle_status == "active"


def test_T07_fresh_items_out_of_scope() -> None:
    fresh = item(item_code="FR-COD", storage="FRESH", sell_uom="LB", pack_size="per lb", vendor_code="BXE")
    r = load(
        items=[fresh],
        lots=[lot(item_code="FR-COD", uom="LB")],
        sales=[sale(item_code="FR-COD", uom="LB")],
        ref=reference(pack_sizes={"FR-COD": None}),
    )
    assert r.dataset.items[0].lifecycle_status == "fresh_out_of_scope"
    assert r.dataset.sales[0].demand_class == "fresh_out_of_scope"


def test_T08_category_casing_normalized() -> None:
    r = load(items=[item(category="  groundfish ")])
    assert r.dataset.items[0].category == "Groundfish"
    assert issues(r, "T08")[0].original_value == "  groundfish "


def test_T09_pack_size_table_matches_parser() -> None:
    # Verified table agrees with the text: no warning.
    assert issues(load(ref=reference(pack_sizes={"SHR-1620": "20"})), "T09") == []
    # Table disagrees with what the text says: flagged for a human to re-check, table still wins.
    r = load(ref=reference(pack_sizes={"SHR-1620": "25"}))
    assert [i.rule_code for i in issues(r, "T09")] == ["pack_size_mismatch"]
    assert r.dataset.items[0].lb_per_case == 25
    # A new item missing from the table is an error.
    r = load(ref=reference(pack_sizes={}))
    assert issues(r, "T09")[0].severity == "error"


# ---- On hand ------------------------------------------------------------------------------


def test_T01_latest_snapshot_only() -> None:
    r = load(lots=[lot(snapshot_date="2026-11-14", qty="100"), lot(snapshot_date="2026-11-15", qty="90")])
    assert [lot.qty_sell_uom for lot in r.dataset.lots] == [Decimal("90")]  # not 190
    assert [i.action for i in issues(r, "T01")] == ["excluded"]


def test_T10_lb_lots_converted_to_cases() -> None:
    lob = item(item_code="LOB-T56", pack_size="10 lb cs", vendor_code="BXE")
    r = load(
        items=[lob],
        lots=[lot(item_code="LOB-T56", qty="220", uom="LB", unit_cost="23.66")],
        sales=[sale(item_code="LOB-T56")],
        ref=reference(pack_sizes={"LOB-T56": "10"}),
    )
    converted = r.dataset.lots[0]
    assert (converted.qty_sell_uom, converted.unit_cost_sell_uom) == (Decimal("22"), Decimal("236.60"))
    assert (converted.qty_source, converted.uom_source) == (Decimal("220"), "LB")  # original kept
    assert issues(r, "T10")[0].action == "corrected"
    # No factor -> not counted, logged as an error.
    r = load(
        items=[lob],
        lots=[lot(item_code="LOB-T56", qty="220", uom="LB")],
        ref=reference(pack_sizes={"LOB-T56": None}),
    )
    assert r.dataset.lots[0].qty_sell_uom is None
    assert any(i.severity == "error" for i in issues(r, "T10"))


def test_T11_hold_and_damaged_not_sellable() -> None:
    r = load(
        lots=[
            lot(location="NB", qty="260", lot_no="A"),
            lot(location="QA-HOLD", qty="80", lot_no="B"),
            lot(location="DAMAGED", qty="5", lot_no="C"),
        ]
    )
    oh = _on_hand(r)["SHR-1620"]
    assert (oh.sellable, oh.on_hold, oh.damaged) == (260, 80, 5)
    assert len(issues(r, "T11")) == 2


def test_T12_zero_qty_lots_skipped() -> None:
    r = load(lots=[lot(lot_no="L260911-01B", qty="0"), lot(lot_no="L260911-01", qty="10")])
    assert [lot.lot_no for lot in r.dataset.lots] == ["L260911-01"]
    assert issues(r, "T12")[0].action == "excluded"


def test_T13_adj_lines_netted() -> None:
    r = load(
        lots=[
            lot(qty="208"),
            lot(lot_no="ADJ-2211", qty="-2", expiry_date="", pack_date="", received_date="", unit_cost=""),
        ]
    )
    assert _on_hand(r)["SHR-1620"].sellable == 206
    assert issues(r, "T13")[0].severity == "warning"


def test_T14_expired_lots_not_sellable() -> None:
    r = load(
        lots=[
            lot(lot_no="OLD", qty="18", expiry_date="2026-08-30", location="PVD"),
            lot(lot_no="NEW", qty="5"),
        ]
    )
    oh = _on_hand(r)["SHR-1620"]
    assert (oh.sellable, oh.expired) == (5, 18)
    assert "Aug 30, 2026" in issues(r, "T14")[0].message


def test_T31_missing_lot_means_sold_out() -> None:
    r = load(
        lots=[lot(snapshot_date="2026-11-14", lot_no="L260601-09", qty="3"), lot(lot_no="OTHER", qty="10")]
    )
    assert [lot.lot_no for lot in r.dataset.lots] == ["OTHER"]  # nothing invented for the vanished lot
    assert issues(r, "T31")[0].action == "flagged"
