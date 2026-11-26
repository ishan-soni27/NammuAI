"""Purchase orders: BlueTide's and Dana's in one list, and everything she can do to them (Phase 6 step 1).

GET    /purchase-orders?status=open|late|received|cancelled|all&q=   one list, matched (R1-R6)
GET    /purchase-orders/{po_no}
POST   /purchase-orders                                    create a PO (KB-00001 if no number)
POST   /purchase-orders/{po_no}/lines/{line_no}/ship       mark a line shipped (container, new date)
POST   /purchase-orders/{po_no}/lines/{line_no}/cancel     cancel a line
DELETE /purchase-orders/{po_no}/lines/{line_no}/status     undo "shipped" or "cancelled"
POST   /purchase-orders/{po_no}/lines/{line_no}/receive    receive stock: qty, building, lot, expiry
POST   /stock-movements/{movement_id}/undo                 reverse a receipt (the history stays)

The expected date of a line is set with the existing PATCH /purchase-orders/{po_no}/lines/{line_no}
(suppliers.py), for BlueTide's lines and Dana's alike. Every write is audited (services/audit.py).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1 import schemas as s
from app.config.business_rules import BusinessRules, get_business_rules
from app.db.session import get_db
from app.services import records_service as svc

router = APIRouter(tags=["Purchase orders"])


@router.get("/purchase-orders", response_model=list[s.POOut])
def list_purchase_orders(
    status: Literal["open", "late", "received", "cancelled", "all"] = "open",
    q: str | None = Query(default=None, max_length=80),
    db: Session = Depends(get_db),
    rules: BusinessRules = Depends(get_business_rules),
) -> list[s.POOut]:
    return svc.purchase_orders(db, rules, status, q)


@router.get("/purchase-orders/{po_no}", response_model=s.POOut)
def get_purchase_order(
    po_no: str, db: Session = Depends(get_db), rules: BusinessRules = Depends(get_business_rules)
) -> s.POOut:
    return svc.purchase_order(db, rules, po_no)


@router.post("/purchase-orders", response_model=s.POOut, status_code=201)
def create_purchase_order(
    body: s.POCreateIn, db: Session = Depends(get_db), rules: BusinessRules = Depends(get_business_rules)
) -> s.POOut:
    """Dana places an order. It counts as on the way at once, on its expected date."""
    return svc.create_purchase_order(db, rules, body)


@router.post("/purchase-orders/{po_no}/lines/{line_no}/ship", response_model=s.POOut)
def ship_line(
    po_no: str,
    line_no: int,
    body: s.POShipIn,
    db: Session = Depends(get_db),
    rules: BusinessRules = Depends(get_business_rules),
) -> s.POOut:
    return svc.ship_line(db, rules, po_no, line_no, body)


@router.post("/purchase-orders/{po_no}/lines/{line_no}/cancel", response_model=s.POOut)
def cancel_line(
    po_no: str,
    line_no: int,
    body: s.POCancelIn,
    db: Session = Depends(get_db),
    rules: BusinessRules = Depends(get_business_rules),
) -> s.POOut:
    return svc.cancel_line(db, rules, po_no, line_no, body)


@router.delete("/purchase-orders/{po_no}/lines/{line_no}/status", response_model=s.POOut)
def reopen_line(
    po_no: str,
    line_no: int,
    db: Session = Depends(get_db),
    rules: BusinessRules = Depends(get_business_rules),
) -> s.POOut:
    return svc.reopen_line(db, rules, po_no, line_no)


@router.post("/purchase-orders/{po_no}/lines/{line_no}/receive", response_model=s.POOut, status_code=201)
def receive_line(
    po_no: str,
    line_no: int,
    body: s.POReceiveIn,
    db: Session = Depends(get_db),
    rules: BusinessRules = Depends(get_business_rules),
) -> s.POOut:
    """Stock arrived. It becomes a lot in that building (and counts for the six-month line)."""
    return svc.receive_line(db, rules, po_no, line_no, body)


@router.post("/stock-movements/{movement_id}/undo", response_model=s.MovementOut, status_code=201)
def undo_movement(movement_id: int, body: s.UndoIn, db: Session = Depends(get_db)) -> s.MovementOut:
    return svc.undo_movement(db, movement_id, body)
