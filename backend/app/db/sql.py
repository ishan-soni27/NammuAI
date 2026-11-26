"""Small portable SQL helpers.

utc_now(): the CURRENT wall-clock time on the database server, for log and audit timestamps
(invariant #1: logs and audits use real UTC time; business dates use AS_OF). On Postgres this is
clock_timestamp(), not now(): now() returns the time the TRANSACTION started, which made a
5-minute load look like it took 4 seconds (PROMPT_LOG #15). Elsewhere (SQLite in tests) it is
CURRENT_TIMESTAMP.
"""

from __future__ import annotations

from sqlalchemy import DateTime
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement


class utc_now(FunctionElement):  # noqa: N801 - reads like a SQL function at call sites
    type = DateTime(timezone=True)
    inherit_cache = True


@compiles(utc_now, "postgresql")
def _pg_utc_now(element, compiler, **kw) -> str:  # noqa: ANN001
    return "clock_timestamp()"


@compiles(utc_now)
def _default_utc_now(element, compiler, **kw) -> str:  # noqa: ANN001
    return "CURRENT_TIMESTAMP"
