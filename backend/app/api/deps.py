"""Request dependencies shared by the routers.

`request_rules`: the business rules for this request (ADR-034).
  - today      = Boston's calendar date (config/clock.py), or the AS_OF_DATE override (tests, a fixed demo);
  - data date  = the day after the latest successful load's BlueTide stock count (the projection starts there,
                 and the stock between it and today is estimated);
  - view as of = a viewer may look at an earlier day (the header's "view as of" switch sends X-As-Of; a plain
                 download link sends ?as_of=). It must fall between the data date and today; edits made while
                 viewing are dated by that day.
"""

from __future__ import annotations

from datetime import date

from fastapi import Depends, Header, Query
from sqlalchemy.orm import Session

from app.config.business_rules import BusinessRules, data_date_of, rules_for, server_today
from app.db.session import get_db
from app.errors import AppError
from app.planning.explain import day
from app.services.planning_inputs import latest_load


def _view_date(raw: str | None) -> date | None:
    if not raw or not raw.strip():
        return None
    try:
        return date.fromisoformat(raw.strip())
    except ValueError as error:
        raise AppError(422, "bad_view_date", f"{raw!r} isn't a date (use YYYY-MM-DD).") from error


def request_rules(
    db: Session = Depends(get_db),
    x_as_of: str | None = Header(default=None, alias="X-As-Of", include_in_schema=False),
    as_of: str | None = Query(default=None, include_in_schema=False),
) -> BusinessRules:
    snapshot = latest_load(db).snapshot_date
    today = server_today()
    view = _view_date(x_as_of) or _view_date(as_of)
    if view is None:
        return rules_for(snapshot, today)
    earliest = data_date_of(snapshot) or view
    latest = max(today, earliest)
    if not earliest <= view <= latest:
        raise AppError(
            422,
            "view_date_out_of_range",
            f"You can view from {day(earliest)} (the day after BlueTide's latest stock count) to today, "
            f"{day(latest)}.",
        )
    return rules_for(snapshot, view)
