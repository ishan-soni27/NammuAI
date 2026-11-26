"""On the way: BlueTide's open PO lines, as the plan counts them (ADR-032).

GET /purchase-orders?q=   every open BlueTide PO line with something still to come: our arrival date
                          (Dana's, the real lead time, or BlueTide's), BlueTide's own date, and whether
                          it's late (late = not counted until Dana sets a real date; Dana Q3).

BlueTide owns the POs: they are created, shipped and received there and arrive here with each upload.
The one thing Dana adds is the real arrival date: PATCH /purchase-orders/{po}/lines/{line} (suppliers.py).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import request_rules
from app.api.v1 import schemas as s
from app.config.business_rules import BusinessRules
from app.db.session import get_db
from app.services import planning_service

router = APIRouter(tags=["On the way"])


@router.get("/purchase-orders", response_model=list[s.OnTheWayLineOut])
def on_the_way(
    q: str | None = Query(None, max_length=60, description="Search PO, item code, item name or supplier."),
    db: Session = Depends(get_db),
    rules: BusinessRules = Depends(request_rules),
) -> list[s.OnTheWayLineOut]:
    return planning_service.on_the_way(db, rules, q)
