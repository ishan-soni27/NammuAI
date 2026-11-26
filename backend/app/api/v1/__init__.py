"""Version 1 of the API. `api_router` collects every v1 router; main.py mounts it at /api/v1.

    health.py      GET /health
    items.py       Monday screen, items, drill-down, handled notes, item settings
    suppliers.py   lead times (vendors) and real PO arrival dates
    purchase_orders.py  On the way: BlueTide's open PO lines (read only)
    imports.py     weekly uploads of BlueTide's files from the website
    exports.py     download any list as a CSV for Excel
    harbor.py      Harbor storage cost: cases per pallet, pallets, $ a month, her saved table
    activity.py    data notes, audit log, events, load runs, settings, client events

How to add an endpoint group: create `app/api/v1/<name>.py` with `router = APIRouter()`,
then include it below.
"""

from fastapi import APIRouter

from app.api.v1 import (
    activity,
    exports,
    harbor,
    health,
    imports,
    items,
    purchase_orders,
    suppliers,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(items.router)
api_router.include_router(suppliers.router)
api_router.include_router(purchase_orders.router)
api_router.include_router(imports.router)
api_router.include_router(exports.router)
api_router.include_router(harbor.router)
api_router.include_router(activity.router)
