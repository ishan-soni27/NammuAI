"""Dana's records and BlueTide's, matched so the same cases are never counted twice (ADR-027).

Pure (no database, no clock, no I/O), like the rest of planning/. services/planning_inputs.py
calls `reconcile_pos` and hands the engine ordinary inputs: PO lines still to come, and lots of
stock Dana received. The engine itself doesn't know where a line came from.

Why quantities and documents, not dates: BlueTide's PO lines carry a running qty_received with no
date, so "ignore anything before BlueTide's last stock count" would miscount (design review,
2026-11-26). Each PO line is matched across both sources, and received = the larger of the two.

Rules (named in tests as test_r1_..., test_r2_..., docs/DECISIONS.md ADR-027):
  R1  A PO Dana creates becomes ordinary PO lines; her expected date is an ETA override.
  R2  The same PO in both: match PO + line, else PO + item. Counted once; her quantity wins and
      any difference is flagged. A line only one side has, on a PO both know, is flagged.
  R3  Received = max(her receipts, BlueTide's qty_received). Stock she adds = what she received
      beyond BlueTide's figure (newest receipts first). Still to come = ordered - received.
  R4  BlueTide says received/closed while she still expects more: not counted; flagged (Ishan).
  R5  BlueTide says cancelled while she still expects it: not counted; flagged.
  R6  A received lot already in a BlueTide stock count dated on/after the receipt: not added again.
  R7  BlueTide shows an order invoiced while Dana's copy is open: not promised or taken again; flagged.
  R8  BlueTide shows it open while Dana's copy is shipped: hers applies, BlueTide's open line is dropped.
      (Same order in both, both open: counted once, hers. Both shipped: BlueTide's stock count already
      has it out, so her picks aren't taken again.)
  R9  Moves and adjustments (no BlueTide document): only those dated after BlueTide's stock count apply.
  R10 A pick larger than its lot: the lot stops at 0 and the rest comes from the next lot to expire in
      the same building; anything still missing is a shortfall, flagged (stock never goes below 0).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import date
from typing import Literal

from app.planning.types import LotInput, POLineInput, SaleInput

EPSILON = 0.5  # under half a case/lb counts as "the same quantity" (whole units on screen)

LineStatus = Literal["open", "shipped", "received", "cancelled"]


@dataclass(frozen=True)
class BlueTidePOLine:
    """Every BlueTide PO line (open or not), quantities in the item's selling unit."""

    po_no: str
    line_no: int
    item_code: str
    vendor_code: str
    order_date: date
    expected_date_system: date | None
    ordered: float | None  # None: no conversion to the selling unit (T10)
    received: float  # BlueTide's running qty_received, no date
    remaining: float  # the loader's figure for what is still to come (T25); 0 if not open
    status: str  # open / complete / cancelled (T25)


@dataclass(frozen=True)
class AppPOLine:
    """A line of a PO Dana created in the app."""

    po_no: str
    line_no: int
    item_code: str
    vendor_code: str
    order_date: date
    ordered: float  # selling unit
    unit_cost: float | None = None


@dataclass(frozen=True)
class LineStatusInput:
    """Dana marked a PO line (hers or BlueTide's) shipped or cancelled."""

    po_no: str
    line_no: int
    status: Literal["shipped", "cancelled"]
    shipped_on: date | None = None
    container_no: str | None = None
    cancel_reason: str | None = None


@dataclass(frozen=True)
class ReceiptInput:
    """A receipt Dana recorded against a PO line (undone receipts are left out by the caller)."""

    movement_id: int
    po_no: str
    po_line_no: int
    item_code: str
    location_code: str
    lot_no: str
    qty: float
    expiry_date: date | None
    unit_cost: float | None
    movement_date: date


@dataclass(frozen=True)
class POLineRecord:
    """One reconciled PO line: what the PO page shows and the engine counts."""

    po_no: str
    line_no: int
    item_code: str
    vendor_code: str
    order_date: date
    source: Literal["app", "bluetide", "both"]
    ordered: float
    received: float
    received_app: float
    received_bluetide: float
    remaining: float
    status: LineStatus
    counted: bool  # remaining counts as on the way
    expected_date_system: date | None  # BlueTide's date
    shipped_on: date | None
    container_no: str | None
    cancel_reason: str | None
    unit_cost: float | None
    flags: tuple[str, ...]


@dataclass(frozen=True)
class ReceivedLot:
    """Stock that exists only because Dana received it (R3), with where it came from."""

    lot: LotInput
    po_no: str
    po_line_no: int
    movement_id: int
    received_on: date


@dataclass(frozen=True)
class Reconciled:
    lines: tuple[POLineRecord, ...]
    po_inputs: tuple[POLineInput, ...]  # counted lines, for the engine
    received_lots: tuple[ReceivedLot, ...]
    skipped_receipts: tuple[tuple[int, str], ...]  # (movement id, why it isn't added as stock)


def _qty(value: float) -> str:
    return f"{round(value):,}"


def _match(
    app_lines: Sequence[AppPOLine], bluetide: Sequence[BlueTidePOLine]
) -> list[tuple[AppPOLine | None, BlueTidePOLine | None]]:
    """R2: pair lines of the same PO, by line number first, then by item."""
    by_key = {(b.po_no, b.line_no): b for b in bluetide}
    used: set[tuple[str, int]] = set()
    pairs: list[tuple[AppPOLine | None, BlueTidePOLine | None]] = []
    unmatched: list[AppPOLine] = []
    for a in app_lines:
        b = by_key.get((a.po_no, a.line_no))
        if b is not None and b.item_code == a.item_code:
            used.add((b.po_no, b.line_no))
            pairs.append((a, b))
        else:
            unmatched.append(a)
    for a in unmatched:
        b = next(
            (
                x
                for x in bluetide
                if x.po_no == a.po_no and x.item_code == a.item_code and (x.po_no, x.line_no) not in used
            ),
            None,
        )
        if b is not None:
            used.add((b.po_no, b.line_no))
        pairs.append((a, b))
    pairs.extend((None, b) for b in bluetide if (b.po_no, b.line_no) not in used)
    return pairs


def reconcile_pos(
    bluetide: Sequence[BlueTidePOLine],
    app_lines: Sequence[AppPOLine],
    statuses: Iterable[LineStatusInput],
    receipts: Iterable[ReceiptInput],
    snapshot_lots: frozenset[tuple[str, str, str]] = frozenset(),
    snapshot_date: date | None = None,
) -> Reconciled:
    status_by_key = {(s.po_no, s.line_no): s for s in statuses}
    receipts_by_key: dict[tuple[str, int], list[ReceiptInput]] = defaultdict(list)
    for r in receipts:
        receipts_by_key[(r.po_no, r.po_line_no)].append(r)
    bluetide_pos = {b.po_no for b in bluetide}
    app_pos = {a.po_no for a in app_lines}

    lines: list[POLineRecord] = []
    po_inputs: list[POLineInput] = []
    received_lots: list[ReceivedLot] = []
    skipped: list[tuple[int, str]] = []

    for a, b in _match(app_lines, bluetide):
        base = a or b
        assert base is not None
        key = (base.po_no, base.line_no)
        flags: list[str] = []
        status_in = status_by_key.get(key)
        got = receipts_by_key.get(key, [])
        received_app = sum(r.qty for r in got)
        received_bt = b.received if b is not None else 0.0

        if a is not None and b is not None:
            source: Literal["app", "bluetide", "both"] = "both"
            ordered = a.ordered
            if b.line_no != a.line_no:
                flags.append(f"BlueTide numbers this line {b.line_no}")
            if b.ordered is not None and abs(b.ordered - a.ordered) >= EPSILON:
                flags.append(f"BlueTide has {_qty(b.ordered)} on this line; yours ({_qty(a.ordered)}) counts")
            remaining = max(0.0, ordered - max(received_app, received_bt))
            if received_bt - received_app >= EPSILON:
                unrecorded = _qty(received_bt - received_app)
                flags.append(f"BlueTide shows {unrecorded} received that isn't recorded here")
        elif a is not None:
            source = "app"
            ordered = a.ordered
            if a.po_no in bluetide_pos:
                flags.append("BlueTide's copy of this PO doesn't have this line")
            remaining = max(0.0, ordered - received_app)
        else:
            assert b is not None
            source = "bluetide"
            ordered = b.ordered if b.ordered is not None else b.remaining + b.received
            if b.po_no in app_pos:
                flags.append("Only in BlueTide's copy of this PO")
            extra = max(0.0, received_app - received_bt)
            remaining = max(0.0, b.remaining - extra)
        received = max(received_app, received_bt)
        dana_status = status_in.status if status_in is not None else None
        ours = source != "bluetide" or received_app > 0  # Dana has a stake in this line

        status: LineStatus
        counted = False
        if dana_status == "cancelled":
            status = "cancelled"
        elif b is not None and b.status == "cancelled":
            status = "cancelled"
            if ours and remaining >= EPSILON:  # R5
                flags.append("BlueTide says this line was cancelled. Not counted; check with the supplier")
        elif b is not None and b.status == "complete":
            status = "received"
            if ours and remaining >= EPSILON:  # R4 (Ishan): BlueTide's receipt wins
                flags.append("BlueTide closed this line as received. The rest isn't counted; check it")
            remaining = 0.0
        elif remaining < EPSILON:
            status = "received" if received >= EPSILON else "open"
            if received < EPSILON:
                flags.append("Nothing left to come in BlueTide's figures (see data notes)")
        else:
            status = "shipped" if dana_status == "shipped" else "open"
            counted = True

        record = POLineRecord(
            po_no=base.po_no,
            line_no=base.line_no,
            item_code=base.item_code,
            vendor_code=base.vendor_code,
            order_date=base.order_date,
            source=source,
            ordered=ordered,
            received=received,
            received_app=received_app,
            received_bluetide=received_bt,
            remaining=remaining,
            status=status,
            counted=counted,
            expected_date_system=b.expected_date_system if b is not None else None,
            shipped_on=status_in.shipped_on if status_in else None,
            container_no=status_in.container_no if status_in else None,
            cancel_reason=status_in.cancel_reason if status_in else None,
            unit_cost=a.unit_cost if a is not None else None,
            flags=tuple(flags),
        )
        lines.append(record)
        if counted:
            po_inputs.append(
                POLineInput(
                    po_no=record.po_no,
                    line_no=record.line_no,
                    item_code=record.item_code,
                    vendor_code=record.vendor_code,
                    order_date=record.order_date,
                    expected_date_system=record.expected_date_system,
                    qty_remaining=remaining,
                    source="bluetide" if source == "bluetide" else "app",
                    flags=record.flags,
                )
            )

        # R3: only what Dana received beyond BlueTide's figure becomes stock, newest receipts first.
        extra = max(0.0, received_app - received_bt)
        for r in sorted(got, key=lambda x: (x.movement_date, x.movement_id), reverse=True):
            if extra < EPSILON:
                skipped.append((r.movement_id, "Already in BlueTide's received quantity for this line"))
                continue
            take = min(r.qty, extra)
            extra -= take
            lot_key = (r.item_code, r.location_code, r.lot_no)
            if lot_key in snapshot_lots and snapshot_date is not None and snapshot_date >= r.movement_date:
                skipped.append((r.movement_id, f"Lot {r.lot_no} is already in BlueTide's stock count"))  # R6
                continue
            received_lots.append(
                ReceivedLot(
                    lot=LotInput(
                        item_code=r.item_code,
                        location_code=r.location_code,
                        lot_no=r.lot_no,
                        qty=take,
                        expiry_date=r.expiry_date,
                        is_adjustment=False,
                        unit_cost=r.unit_cost,
                    ),
                    po_no=r.po_no,
                    po_line_no=r.po_line_no,
                    movement_id=r.movement_id,
                    received_on=r.movement_date,
                )
            )

    lines.sort(key=lambda x: (x.po_no, x.line_no))
    return Reconciled(tuple(lines), tuple(po_inputs), tuple(received_lots), tuple(skipped))


# ---- Step 2: shipments, picks and moves (R7-R10) ----------------------------------------------

ShipmentStatus = Literal["open", "shipped", "cancelled"]


@dataclass(frozen=True)
class AppShipmentLine:
    """One line of an order Dana logged (see services/planning_inputs for how it's built)."""

    shipment_id: int
    order_no: str
    line_no: int
    item_code: str
    customer_name: str
    kind: Literal["customer", "sample"]
    order_date: date
    ship_date: date
    status: ShipmentStatus
    qty: float
    is_real_demand: bool  # loader/classify.classify_sale said real_demand (samples never are)


@dataclass(frozen=True)
class MovementInput:
    """A stock change Dana recorded (not a receipt; undone ones are left out by the caller)."""

    movement_id: int
    kind: str  # shipment / sample / move_out / move_in / adjustment
    item_code: str
    location_code: str
    lot_no: str
    qty: float  # signed: - out of the building, + into it
    expiry_date: date | None
    unit_cost: float | None
    movement_date: date
    shipment_id: int | None = None


@dataclass(frozen=True)
class ShipmentLineRecord:
    order_no: str
    line_no: int
    item_code: str
    status: ShipmentStatus
    promised: bool  # counts as promised to a customer (an open order)
    taken_from_stock: bool  # its picks come out of the stock the plan uses
    counts_as_demand: bool  # feeds the selling rate
    flags: tuple[str, ...]


@dataclass(frozen=True)
class ShipmentsReconciled:
    lines: tuple[ShipmentLineRecord, ...]
    sales: tuple[SaleInput, ...]  # Dana's lines the engine should see
    drop_bluetide_open: frozenset[tuple[str, str]]  # (order, item) of BlueTide open lines replaced by hers
    applied_shipments: frozenset[int]  # shipment ids whose picks are taken from stock


def reconcile_shipments(
    app_lines: Sequence[AppShipmentLine], bluetide_orders: dict[tuple[str, str], str]
) -> ShipmentsReconciled:
    """Match Dana's orders with BlueTide's by order number + item (R7, R8). Pure."""
    records: list[ShipmentLineRecord] = []
    sales: list[SaleInput] = []
    drop: set[tuple[str, str]] = set()
    applied: set[int] = set()
    not_applied: set[int] = set()
    for a in app_lines:
        key = (a.order_no, a.item_code)
        bt = bluetide_orders.get(key)
        flags: list[str] = []
        promised = taken = demand = False
        if bt is not None and bt != "INVOICED":
            drop.add(key)  # her copy is the main one (counted once)
        if a.status == "cancelled":
            if bt == "INVOICED":
                flags.append("BlueTide shows this order invoiced (shipped), but it's cancelled here")
        elif bt == "INVOICED":
            if a.status == "open":  # R7
                flags.append(
                    "BlueTide shows this order invoiced (shipped). Not counted again; mark it shipped here"
                )
            # shipped in both: BlueTide's stock count already has it out, and its sale is in the history
            not_applied.add(a.shipment_id)
        elif a.status == "open":
            promised = True
            if bt == "CANCELLED":
                flags.append("BlueTide says this order was cancelled; still counted as promised here")
        else:  # shipped, BlueTide open or unknown (R8)
            taken = True
            demand = a.is_real_demand
        if promised:
            sales.append(
                SaleInput(a.item_code, a.order_no, a.customer_name, a.order_date, a.ship_date, a.qty, True)
            )
        if demand:
            sales.append(
                SaleInput(a.item_code, a.order_no, a.customer_name, a.order_date, a.ship_date, a.qty, False)
            )
        if taken:
            applied.add(a.shipment_id)
        records.append(
            ShipmentLineRecord(
                a.order_no, a.line_no, a.item_code, a.status, promised, taken, demand, tuple(flags)
            )
        )
    return ShipmentsReconciled(
        tuple(records), tuple(sales), frozenset(drop), frozenset(applied - not_applied)
    )


@dataclass(frozen=True)
class LotRecord:
    """A lot the plan counts, with where it came from (shown on the item page)."""

    lot: LotInput
    origin: Literal["bluetide", "received", "moved"]
    note: str | None = None


def apply_movements(
    lots: Sequence[LotRecord],
    movements: Sequence[MovementInput],
    applied_shipments: frozenset[int],
    snapshot_date: date | None,
    sellable_locations: frozenset[str],
) -> tuple[tuple[LotRecord, ...], tuple[str, ...]]:
    """Apply Dana's picks, moves and adjustments to the lots (R9, R10). Pure; stock never goes below 0."""
    qty = [r.lot.qty or 0.0 for r in lots]
    records = list(lots)
    flags: list[str] = []

    def counts(m: MovementInput) -> bool:
        if m.kind in ("shipment", "sample"):
            return m.shipment_id in applied_shipments
        return snapshot_date is None or m.movement_date > snapshot_date  # R9

    for m in sorted((m for m in movements if counts(m)), key=lambda x: (x.movement_date, x.movement_id)):
        if m.qty > 0:
            i = next(
                (
                    i
                    for i, r in enumerate(records)
                    if (r.lot.item_code, r.lot.location_code, r.lot.lot_no)
                    == (m.item_code, m.location_code, m.lot_no)
                    and not r.lot.is_adjustment
                ),
                None,
            )
            if i is None:
                records.append(
                    LotRecord(
                        LotInput(
                            m.item_code, m.location_code, m.lot_no, 0.0, m.expiry_date, False, m.unit_cost
                        ),
                        "moved",
                        "Moved here in the app",
                    )
                )
                qty.append(0.0)
                i = len(records) - 1
            qty[i] += m.qty
            continue
        need = -m.qty
        exact = [
            i
            for i, r in enumerate(records)
            if (r.lot.item_code, r.lot.location_code, r.lot.lot_no)
            == (m.item_code, m.location_code, m.lot_no)
            and not r.lot.is_adjustment
        ]
        others = sorted(
            (
                i
                for i, r in enumerate(records)
                if r.lot.item_code == m.item_code
                and r.lot.location_code == m.location_code
                and r.lot.location_code in sellable_locations
                and not r.lot.is_adjustment
                and i not in exact
            ),
            key=lambda i: (records[i].lot.expiry_date or date.max, records[i].lot.lot_no),
        )
        for i in exact + others:  # R10: the named lot first, then the next to expire in that building
            take = min(qty[i], need)
            if take > 0:
                qty[i] -= take
                need -= take
            if need < EPSILON:
                break
        if need >= EPSILON:
            flags.append(
                f"{_qty(need)} of {m.item_code} taken from {m.location_code} lot {m.lot_no} that the stock "
                "doesn't have (shortfall)"
            )
    out = tuple(replace(r, lot=replace(r.lot, qty=q)) for r, q in zip(records, qty, strict=True))
    return out, tuple(flags)
