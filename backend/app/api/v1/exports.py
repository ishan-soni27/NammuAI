"""Download to Excel (Phase 6 step 4; P0 #13).

GET /exports/{name}.csv   name: order-list | stuck-list | purchase-orders | shipments | data-notes |
                          harbor-storage

UTF-8 with a byte-order mark, dates as YYYY-MM-DD, numbers without units and a unit column, statuses
in Dana's words. Built from the same services as the screens (services/export_service.py).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.config.business_rules import BusinessRules, get_business_rules
from app.db.session import get_db
from app.errors import AppError
from app.services.export_service import EXPORTS

router = APIRouter(tags=["Download to Excel"])


@router.get("/exports/{name}.csv", response_class=Response)
def export_csv(
    name: str, db: Session = Depends(get_db), rules: BusinessRules = Depends(get_business_rules)
) -> Response:
    build = EXPORTS.get(name)
    if build is None:
        raise AppError(404, "unknown_export", f"There's no download called {name!r}.")
    # Named with the business date, so a folder of weekly downloads sorts itself.
    file_name = f"kestrel-bay-{name}-{rules.as_of_date.isoformat()}.csv"
    return Response(
        content=build(db, rules),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )
