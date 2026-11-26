"""Imports from the website (Phase 6 step 3; ADR-029): BlueTide's exports or Dana's own templates.

GET    /imports                          recent imports (newest first)
POST   /imports                          start one: {"kind": "bluetide" | "template"}
GET    /imports/{id}
PUT    /imports/{id}/files/{slot}?name=  upload one file (the CSV as the raw request body)
POST   /imports/{id}/check               the dry run: what would change, blockers, warnings
POST   /imports/{id}/load                load it, with the check's one-time code
DELETE /imports/{id}                     discard it
GET    /import-templates/{slot}.csv      an empty template for Excel (header row only)

Each file goes in its own request (Vercel caps a request at 4.5 MB). See services/import_service.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.v1 import schemas as s
from app.config.business_rules import BusinessRules, get_business_rules
from app.db.session import get_db
from app.errors import AppError
from app.services import import_service as svc
from app.services import template_import

router = APIRouter(tags=["Imports"])


@router.get("/imports", response_model=list[s.ImportOut])
def list_imports(db: Session = Depends(get_db)) -> list[s.ImportOut]:
    return svc.imports(db)


@router.post("/imports", response_model=s.ImportOut, status_code=201)
def start_import(body: s.ImportCreateIn, db: Session = Depends(get_db)) -> s.ImportOut:
    return svc.create_import(db, body.kind)


@router.get("/imports/{upload_id}", response_model=s.ImportOut)
def get_import(upload_id: int, db: Session = Depends(get_db)) -> s.ImportOut:
    return svc.import_detail(db, upload_id)


@router.put("/imports/{upload_id}/files/{slot}", response_model=s.ImportOut)
async def put_file(
    upload_id: int,
    slot: str,
    request: Request,
    name: str = Query(min_length=1, max_length=200),
    db: Session = Depends(get_db),
) -> s.ImportOut:
    """The file's bytes are the request body, exactly as on disk (so its SHA-256 matches)."""
    content = await request.body()
    return svc.put_file(db, upload_id, slot, name, content)


@router.post("/imports/{upload_id}/check", response_model=s.ImportOut)
def check_import(
    upload_id: int, db: Session = Depends(get_db), rules: BusinessRules = Depends(get_business_rules)
) -> s.ImportOut:
    return svc.check(db, rules, upload_id)


@router.post("/imports/{upload_id}/load", response_model=s.ImportOut)
def load_import(
    upload_id: int,
    body: s.ImportLoadIn,
    db: Session = Depends(get_db),
    rules: BusinessRules = Depends(get_business_rules),
) -> s.ImportOut:
    return svc.load(db, rules, upload_id, body.confirm_code)


@router.delete("/imports/{upload_id}", response_model=s.ImportOut)
def discard_import(upload_id: int, db: Session = Depends(get_db)) -> s.ImportOut:
    return svc.discard(db, upload_id)


@router.get("/import-templates/{slot}.csv", response_class=Response)
def download_template(slot: str) -> Response:
    if slot not in template_import.TEMPLATES:
        raise AppError(404, "unknown_template", f"There's no template called {slot!r}.")
    return Response(
        content="﻿" + template_import.template_csv(slot),  # BOM: Excel opens UTF-8 correctly
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="kestrel-bay-{slot}.csv"'},
    )
