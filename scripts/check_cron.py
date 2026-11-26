"""Show when Vercel's daily cron last called the API (it keeps Supabase from pausing; vercel.json).

The middleware logs those calls with actor "Vercel cron" (app/middleware.actor_for). Run from
backend/ with its virtualenv active, so it reads DATABASE_URL from backend/.env:

    cd backend && source .venv/bin/activate && python ../scripts/check_cron.py

Prints the last 10 cron calls (UTC). Nothing listed = it hasn't fired since this logging was
added; check the Vercel dashboard (Project -> Settings -> Cron Jobs) instead. Reads only.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import create_engine, text  # noqa: E402

from app.config.settings import get_settings  # noqa: E402

engine = create_engine(get_settings().database_url)
with engine.connect() as conn:
    rows = conn.execute(
        text(
            "select occurred_at, path, status from request_log "
            "where actor = 'Vercel cron' order by occurred_at desc limit 10"
        )
    ).all()
if not rows:
    print("No cron calls logged yet. The schedule is daily at 12:00 UTC (any time in that hour on Hobby).")
for occurred_at, path, status in rows:
    print(f"{occurred_at:%Y-%m-%d %H:%M} UTC  {path}  {status}")
