"""Version 1 of the API. `api_router` collects every v1 router; main.py mounts it at /api/v1.

How to add an endpoint group: create `app/api/v1/<name>.py` with `router = APIRouter()`,
then include it below.
"""

from fastapi import APIRouter

from app.api.v1 import health

api_router = APIRouter()
api_router.include_router(health.router)
