"""Harbor storage cost (P1 #1; ADR-031).

GET    /harbor-storage            what's at Harbor: cases, cases per pallet, pallets, $ a month, her table
POST   /harbor-storage/rows       add lines to her table (what's there now, or a what-if amount)
DELETE /harbor-storage/rows/{id}  take a row out of her table
Her cases per pallet is also editable on its own: PATCH /items/{code}/settings {"cases_per_pallet": 60}.
The table downloads as GET /exports/harbor-storage.csv.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1 import schemas as s
from app.config.business_rules import BusinessRules, get_business_rules
from app.db.session import get_db
from app.services import harbor_service

router = APIRouter(tags=["Harbor storage"])


@router.get("/harbor-storage", response_model=s.HarborOut)
def harbor_storage(
    db: Session = Depends(get_db), rules: BusinessRules = Depends(get_business_rules)
) -> s.HarborOut:
    return harbor_service.harbor(db, rules)


@router.post("/harbor-storage/rows", response_model=s.HarborOut)
def add_rows(
    body: s.HarborRowsIn, db: Session = Depends(get_db), rules: BusinessRules = Depends(get_business_rules)
) -> s.HarborOut:
    return harbor_service.add_rows(db, rules, body)


@router.delete("/harbor-storage/rows/{row_id}", response_model=s.HarborOut)
def delete_row(
    row_id: int, db: Session = Depends(get_db), rules: BusinessRules = Depends(get_business_rules)
) -> s.HarborOut:
    return harbor_service.delete_row(db, rules, row_id)
