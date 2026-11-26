"""Orders going out, and moving stock between buildings (Phase 6 step 2).

GET  /customers                             BlueTide's customers and Dana's
POST /customers                             add a customer
GET  /shipments?status=open|shipped|cancelled|all&q=
GET  /shipments/{order_no}
POST /shipments                             log an order (SH-00001 if no number); open = promised
GET  /shipments/{order_no}/picks            the lots that would be taken, soonest to expire first
POST /shipments/{order_no}/ship             ship it (those picks, or the ones Dana chose)
POST /shipments/{order_no}/cancel           cancel an open order
POST /shipments/{order_no}/undo-ship        it didn't go: picks back into their lots, order open again
GET  /stock-lots?item=CODE                  an item's lots as the plan counts them now
POST /stock-moves                           move stock between buildings (e.g. Harbor -> New Bedford)

Matching with BlueTide's orders: planning/records.py (R7-R10). Every write is audited.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1 import schemas as s
from app.config.business_rules import BusinessRules, get_business_rules
from app.db.session import get_db
from app.services import planning_service
from app.services import shipments_service as svc

router = APIRouter(tags=["Shipments and moving stock"])


@router.get("/customers", response_model=list[s.CustomerOut])
def list_customers(db: Session = Depends(get_db)) -> list[s.CustomerOut]:
    return svc.customers(db)


@router.post("/customers", response_model=s.CustomerOut, status_code=201)
def create_customer(
    body: s.CustomerCreateIn,
    db: Session = Depends(get_db),
    rules: BusinessRules = Depends(get_business_rules),
) -> s.CustomerOut:
    return svc.create_customer(db, rules, body)


@router.get("/shipments", response_model=list[s.ShipmentOut])
def list_shipments(
    status: Literal["open", "shipped", "cancelled", "all"] = "open",
    q: str | None = Query(default=None, max_length=80),
    db: Session = Depends(get_db),
    rules: BusinessRules = Depends(get_business_rules),
) -> list[s.ShipmentOut]:
    return svc.shipments(db, rules, status, q)


@router.get("/shipments/{order_no}", response_model=s.ShipmentOut)
def get_shipment(
    order_no: str, db: Session = Depends(get_db), rules: BusinessRules = Depends(get_business_rules)
) -> s.ShipmentOut:
    return svc.shipment(db, rules, order_no)


@router.post("/shipments", response_model=s.ShipmentOut, status_code=201)
def create_shipment(
    body: s.ShipmentCreateIn,
    db: Session = Depends(get_db),
    rules: BusinessRules = Depends(get_business_rules),
) -> s.ShipmentOut:
    """An order going out. It counts as promised to the customer on its ship date."""
    return svc.create_shipment(db, rules, body)


@router.get("/shipments/{order_no}/picks", response_model=s.PickPlanOut)
def pick_plan(
    order_no: str, db: Session = Depends(get_db), rules: BusinessRules = Depends(get_business_rules)
) -> s.PickPlanOut:
    return svc.pick_plan(db, rules, order_no)


@router.post("/shipments/{order_no}/ship", response_model=s.ShipmentOut)
def ship(
    order_no: str,
    body: s.ShipIn,
    db: Session = Depends(get_db),
    rules: BusinessRules = Depends(get_business_rules),
) -> s.ShipmentOut:
    return svc.ship(db, rules, order_no, body)


@router.post("/shipments/{order_no}/cancel", response_model=s.ShipmentOut)
def cancel(
    order_no: str,
    body: s.CancelIn,
    db: Session = Depends(get_db),
    rules: BusinessRules = Depends(get_business_rules),
) -> s.ShipmentOut:
    return svc.cancel(db, rules, order_no, body)


@router.post("/shipments/{order_no}/undo-ship", response_model=s.ShipmentOut)
def undo_ship(
    order_no: str,
    body: s.CancelIn,
    db: Session = Depends(get_db),
    rules: BusinessRules = Depends(get_business_rules),
) -> s.ShipmentOut:
    return svc.undo_ship(db, rules, order_no, body)


@router.get("/stock-lots", response_model=list[s.StockLotOut])
def stock_lots(
    item: str = Query(min_length=1, max_length=40),
    db: Session = Depends(get_db),
    rules: BusinessRules = Depends(get_business_rules),
) -> list[s.StockLotOut]:
    return svc.stock_lots(db, rules, planning_service.resolve_item_code(db, item))


@router.post("/stock-moves", response_model=list[s.MovementOut], status_code=201)
def move_stock(
    body: s.MoveIn, db: Session = Depends(get_db), rules: BusinessRules = Depends(get_business_rules)
) -> list[s.MovementOut]:
    """Move part or all of a lot to another building. Undo it with POST /stock-movements/{id}/undo."""
    return svc.move_stock(db, rules, body)
