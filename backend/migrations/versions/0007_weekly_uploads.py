"""Weekly uploads (ADR-032, step 3): handled notes dated in business time, sales lines that accumulate
across uploads with their origin, and room to clear old upload bytes.

- handled_flags.created_on: the business day a note was written (AS_OF then). Existing notes were all
  written while "today" was 2026-11-16, so they're backfilled with that date.
- raw_rows.origin_load_run_id: the load whose upload first brought the row in (backfilled with the
  row's own load). A load re-stores the older sales lines it keeps; this keeps them traceable.
- upload_files.content becomes nullable: bytes of uploads outside the newest N loads are cleared
  (business_rules.raw_rows_keep_loads); name, sha256 and row count stay.

Additive only, so it runs safely BEFORE the code that uses it is deployed (the old code ignores it).

Revision ID: 0007
Revises: 0006
Created: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Every table this migration creates (none: only columns; RLS is already on all three tables).
# tests/unit/test_invariants.py reads this.
ALL_TABLES: tuple[str, ...] = ()


def upgrade() -> None:
    op.add_column("handled_flags", sa.Column("created_on", sa.Date(), nullable=True))
    op.execute("UPDATE handled_flags SET created_on = DATE '2026-11-16' WHERE created_on IS NULL")
    op.add_column("raw_rows", sa.Column("origin_load_run_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        op.f("fk_raw_rows_origin_load_run_id_load_runs"), "raw_rows", "load_runs", ["origin_load_run_id"], ["id"]
    )
    op.execute("UPDATE raw_rows SET origin_load_run_id = load_run_id WHERE origin_load_run_id IS NULL")
    op.alter_column("upload_files", "content", existing_type=sa.LargeBinary(), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE upload_files SET content = ''::bytea WHERE content IS NULL")
    op.alter_column("upload_files", "content", existing_type=sa.LargeBinary(), nullable=False)
    op.drop_constraint(op.f("fk_raw_rows_origin_load_run_id_load_runs"), "raw_rows", type_="foreignkey")
    op.drop_column("raw_rows", "origin_load_run_id")
    op.drop_column("handled_flags", "created_on")
