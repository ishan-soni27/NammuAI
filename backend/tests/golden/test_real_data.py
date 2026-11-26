"""Golden facts (BUILD_PROMPT §5.3) asserted on the REAL BlueTide exports.

These numbers were computed straight from the raw files in the planning chat, and
re-checked independently in Phase 0 (docs/DATA_AUDIT.md). If the loader disagrees, the
loader is probably wrong: investigate before touching a number here, and record any
genuine correction in docs/PROMPT_LOG.md.

Runs the pure pipeline only (no database), so it is fast and safe to run anywhere.
G15 (PO arrival dates) and G17 (nothing dead in the order list) need the planning engine
and arrive in Phase 3.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal

import pytest

from app.config.business_rules import BusinessRules
from app.loader.pipeline import build_dataset
from app.loader.read_raw import read_all_raw
from app.loader.reference import load_reference
from app.loader.types import LoadResult
from app.planning.calendar import add_months
from app.planning.supply import LocationInput, LotInput, OnHand, effective_lead_time_days, summarize_on_hand

RULES = BusinessRules()  # defaults: AS_OF 2026-11-16


@pytest.fixture(scope="module")
def result() -> LoadResult:
    return build_dataset(read_all_raw(), load_reference(), RULES)


@pytest.fixture(scope="module")
def on_hand(result: LoadResult) -> dict[str, OnHand]:
    d = result.dataset
    lots = [
        LotInput(
            lot.item_code, lot.location_code, lot.lot_no, lot.qty_sell_uom, lot.expiry_date, lot.is_adjustment
        )
        for lot in d.lots
    ]
    locations = [LocationInput(x.code, x.is_sellable, x.may_return_to_stock) for x in d.locations]
    return summarize_on_hand(lots, locations, RULES.as_of_date)


def D(value: str) -> Decimal:
    return Decimal(value)


def test_G01_latest_snapshot_only(result: LoadResult) -> None:
    assert str(result.dataset.snapshot_date) == "2026-11-15"
    assert {str(lot.snapshot_date) for lot in result.dataset.lots} == {"2026-11-15"}
    older = [i for i in result.issues if i.trap_id == "T01"]
    assert len(older) == 115 and all(i.action == "excluded" for i in older)


def test_G02_45_canonical_items_after_collapsing_aliases(result: LoadResult) -> None:
    assert len(result.dataset.items) == 45
    assert {a.alias_code for a in result.dataset.aliases} == {"COD-LOIN ", "Sal-Por6", "shr-1620 "}
    assert len([i for i in result.issues if i.trap_id == "T03"]) == 3


def test_G03_lifecycle_counts(result: LoadResult) -> None:
    counts = Counter(i.lifecycle_status for i in result.dataset.items)
    assert counts == {"active": 30, "dormant": 3, "legacy": 6, "fresh_out_of_scope": 6}
    dormant = {i.item_code for i in result.dataset.items if i.lifecycle_status == "dormant"}
    assert dormant == {"TIL-FIL", "SHR-6170", "PAN-1012"}
    legacy = {i.item_code for i in result.dataset.items if i.lifecycle_status == "legacy"}
    assert all(code.startswith("ZZ-") for code in legacy) and len(legacy) == 6


def test_G04_shr_1620_sellable_480_on_hold_80(on_hand: dict[str, OnHand]) -> None:
    shr = on_hand["SHR-1620"]
    assert shr.sellable == 480
    assert shr.sellable_by_location == {"NB": 260, "HCS": 140, "PVD": 80}  # PVD 80 came in as "shr-1620 "
    assert shr.on_hold == 80


def test_G05_lob_t56_83_cases_after_pound_conversion(on_hand: dict[str, OnHand]) -> None:
    assert on_hand["LOB-T56"].sellable == 83  # 45 cs + 220 lb / 10 + 160 lb / 10


def test_G06_cal_ring_353_cases(on_hand: dict[str, OnHand]) -> None:
    assert on_hand["CAL-RING"].sellable == 353  # 263 + 132 lb / 13.2 + 80


def test_G07_adjustments_netted(on_hand: dict[str, OnHand]) -> None:
    assert on_hand["COD-FIL"].sellable == 206
    assert on_hand["SHR-2630"].sellable == 429
    assert on_hand["POL-BLK"].sellable == D("8478.5")


def test_G08_had_fil_170_sellable_300_on_hold(on_hand: dict[str, OnHand]) -> None:
    assert on_hand["HAD-FIL"].sellable == 170
    assert on_hand["HAD-FIL"].on_hold == 300


def test_G09_expired_lots_of_in_scope_items(result: LoadResult, on_hand: dict[str, OnHand]) -> None:
    # In scope = not legacy and not fresh (docs/DATA_AUDIT.md note on G09/G10).
    out_of_scope = {
        i.item_code for i in result.dataset.items if i.lifecycle_status in {"legacy", "fresh_out_of_scope"}
    }
    expired = {
        (lot.item_code, lot.lot_no, lot.qty_sell_uom)
        for lot in result.dataset.lots
        if lot.expiry_date
        and lot.expiry_date < RULES.as_of_date
        and lot.qty_sell_uom
        and lot.qty_sell_uom > 0
        and lot.item_code not in out_of_scope
    }
    assert expired == {("SAL-POR8", "L250303-01", 60), ("SHR-4150", "L241202-01", 18)}
    assert on_hand["SAL-POR8"].sellable == 700
    assert on_hand["SHR-4150"].sellable == 381


def test_G10_lots_inside_the_six_month_line(result: LoadResult) -> None:
    line = add_months(RULES.as_of_date, RULES.six_month_line_months)
    assert str(line) == "2027-05-16"
    out_of_scope = {
        i.item_code for i in result.dataset.items if i.lifecycle_status in {"legacy", "fresh_out_of_scope"}
    }
    inside = defaultdict(Decimal)
    for lot in result.dataset.lots:
        if (
            lot.item_code not in out_of_scope
            and lot.expiry_date
            and RULES.as_of_date <= lot.expiry_date < line
            and lot.qty_sell_uom
            and lot.qty_sell_uom > 0
        ):
            inside[(lot.item_code, lot.lot_no if lot.item_code != "SAL-POR6" else "*")] += lot.qty_sell_uom
    assert dict(inside) == {
        ("SAL-POR6", "*"): 1350,
        ("SAL-POR8", "L260720-02"): 380,
        ("TIL-FIL", "L250602-01"): 140,
    }
    sal_por6_harbor = sum(
        lot.qty_sell_uom
        for lot in result.dataset.lots
        if lot.item_code == "SAL-POR6" and lot.location_code == "HCS"
    )
    assert sal_por6_harbor == 1050


def test_G11_demand_class_counts(result: LoadResult) -> None:
    assert Counter(s.demand_class for s in result.dataset.sales) == {
        "real_demand": 12040,
        "fresh_out_of_scope": 2856,
        "transfer": 378,
        "cancelled": 294,
        "sample": 104,
        "credit": 76,
        "one_off": 2,
    }


def test_G12_51_rows_with_us_dates(result: LoadResult) -> None:
    us = [
        i
        for i in result.issues
        if i.trap_id == "T21" and i.source and i.source.file == "bluetide_sales_lines.csv"
    ]
    assert len(us) == 51


def test_G13_committed_open_orders(result: LoadResult) -> None:
    committed: dict[str, Decimal] = defaultdict(Decimal)
    lines = 0
    for s in result.dataset.sales:
        if s.status == "OPEN" and s.demand_class == "real_demand":
            committed[s.item_code] += s.qty
            lines += 1
    assert committed["SHR-1620"] == 201
    assert committed["CRAB-SNW5"] == 221
    assert committed["SHR-2125"] == 91
    assert lines == 159


def test_G14_purchase_orders(result: LoadResult) -> None:
    assert len([i for i in result.issues if i.trap_id == "T24"]) == 2
    open_lines = [p for p in result.dataset.po_lines if p.status == "open"]
    assert len(open_lines) == 14
    incoming: dict[str, Decimal] = defaultdict(Decimal)
    for p in open_lines:
        incoming[p.item_code] += p.qty_remaining_sell_uom or 0
    assert incoming["SHR-2630"] == 500
    assert incoming["HAD-LOIN"] == 200
    assert incoming["PAN-0709"] == 400
    assert incoming["POL-BLK"] == 18000
    cancelled = [p for p in result.dataset.po_lines if p.po_no == "PO-260423"]
    assert cancelled and all(p.status == "cancelled" and p.qty_remaining_sell_uom == 0 for p in cancelled)


def test_G16_lead_times_system_and_effective(result: LoadResult) -> None:
    system = {v.vendor_code: v.lead_time_days_system for v in result.dataset.vendors}
    assert {k: system[k] for k in ["BXE", "AFS", "DLC", "MNP", "ASP"]} == {
        "BXE": 56,
        "AFS": None,
        "DLC": 21,
        "MNP": 14,
        "ASP": 28,
    }
    seeds = {s.vendor_code: s.lead_time_days for s in load_reference().vendor_settings}
    effective = {
        code: effective_lead_time_days(seeds.get(code), system[code], RULES.default_lead_time_days)[0]
        for code in ["BXE", "AFS", "MNP", "ASP", "DLC"]
    }
    assert effective == {"BXE": 84, "AFS": 42, "MNP": 14, "ASP": 28, "DLC": 21}


def test_no_errors_on_the_real_exports(result: LoadResult) -> None:
    errors = [i for i in result.issues if i.severity == "error"]
    assert errors == [], errors[:3]


def test_every_issue_names_a_trap_or_is_a_row_error(result: LoadResult) -> None:
    for issue in result.issues:
        assert issue.trap_id or issue.rule_code in {"unreadable_row", "unknown_item", "unknown_customer"}


# ---- Phase 3: the planning engine on the real data (G15, G17) ------------------------------------

from datetime import date  # noqa: E402

from app.planning.engine import plan  # noqa: E402
from app.planning.types import PlanResult  # noqa: E402
from app.services.planning_inputs import inputs_from_dataset  # noqa: E402


@pytest.fixture(scope="module")
def engine_result(result: LoadResult) -> PlanResult:
    return plan(inputs_from_dataset(result.dataset, load_reference().vendor_settings), RULES)


def test_G15_purchase_order_arrival_dates(engine_result: PlanResult) -> None:
    by_po = {
        line.reference.split()[0]: line
        for p in engine_result.items
        for line in p.incoming + p.late_incoming
        if line.source == "po"
    }
    assert by_po["PO-260443"].eta == date(2027, 1, 25)  # SHR-1620: BlueTide said Dec 28 (stale 8-week date)
    assert by_po["PO-260443"].bluetide_date == date(2026, 12, 28)
    # Late and NOT counted (Dana 2026-11-26, Q3). PO-260407 is late because it lands exactly today (A18).
    for po_no in ["PO-260394", "PO-260376", "PO-260407"]:
        assert by_po[po_no].is_late and by_po[po_no].eta is None, po_no
    assert by_po["PO-260436"].eta == date(2026, 12, 28)  # PAN-0507: BlueTide said Nov 30
    assert by_po["PO-260444"].eta == date(2026, 11, 27)  # LOB-T810: BlueTide said Nov 23


def test_G17_nothing_dead_or_fresh_in_the_order_list(engine_result: PlanResult) -> None:
    urgent = {"TOO_LATE", "ORDER_THIS_WEEK", "ORDER_SOON"}
    in_list = [p for p in engine_result.items if p.confirmed.status in urgent]
    assert in_list, "the order list shouldn't be empty on the real data"
    assert all(p.lifecycle_status == "active" for p in in_list)
    for p in engine_result.items:
        if p.lifecycle_status in {"legacy", "dormant", "fresh_out_of_scope", "discontinued"}:
            assert p.confirmed.status == "NOT_PLANNED", p.item.item_code


def test_stuck_list_and_trust_strip_on_real_data(engine_result: PlanResult) -> None:
    # Structural checks from §6.11 / §7 (not tuned numbers): SAL-POR6 is all inside the six-month
    # line with 1,050 at Harbor; SHR-1620's Harbor stock is NOT stuck; the trust strip adds up.
    stuck = {s.item_code: s for s in engine_result.stuck}
    assert stuck["SAL-POR6"].qty == 1350 and stuck["SAL-POR6"].qty_at_harbor == 1050
    assert all("INSIDE_SIX_MONTHS" in lot.tags for lot in stuck["SAL-POR6"].lots)
    assert "SHR-1620" not in stuck
    assert {"TIL-FIL", "SHR-6170"} <= {c for c, s in stuck.items() if s.primary_tag == "STOPPED_SELLING"}
    t = engine_result.trust
    assert (t.on_hold, t.damaged, t.expired, t.legacy) == ({"CS": 420}, {"CS": 20}, {"CS": 78}, {"CS": 59})
    assert t.late_po_qty == {"CS": 1500}  # 800 + 400 + 300, shown as late, not counted
