"""Version 1 of the API. `api_router` collects every v1 router; main.py mounts it at /api/v1.

    health.py      GET /health
    items.py       Monday screen, items, drill-down, handled notes, item settings
    suppliers.py   lead times (vendors) and PO arrival dates
    activity.py    data notes, audit log, events, load runs, settings, client events

How to add an endpoint group: create `app/api/v1/<name>.py` with `router = APIRouter()`,
then include it below.
"""

from fastapi import APIRouter

from app.api.v1 import activity, health, items, suppliers

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(items.router)
api_router.include_router(suppliers.router)
api_router.include_router(activity.router)
