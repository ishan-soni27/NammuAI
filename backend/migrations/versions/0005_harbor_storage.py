"""Harbor storage cost (P1 #1; ADR-031): cases per pallet per item, and the rows Dana saves.

App layer (harbor_storage_rows, and the new item_settings column): the loader never truncates
them (invariant #5), no foreign keys into BlueTide's tables. RLS on the new table (ADR-015).

Revision ID: 0005
Revises: 0004
Created: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Every table this migration creates (tests/unit/test_invariants.py checks RLS covers them all).
ALL_TABLES = ("harbor_storage_rows",)


def upgrade() -> None:
    op.add_column("item_settings", sa.Column("cases_per_pallet", sa.Integer(), nullable=True))
    op.create_check_constraint(
        op.f("ck_item_settings_cases_per_pallet_positive"),
        "item_settings",
        "cases_per_pallet IS NULL OR cases_per_pallet > 0",
    )
    op.create_table(
        "harbor_storage_rows",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("item_code", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("cases", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("lots", sa.Integer(), nullable=False),
        sa.Column("cases_per_pallet", sa.Integer(), nullable=False),
        sa.Column("pallets", sa.Integer(), nullable=False),
        sa.Column("rate_per_pallet_month", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("cost_per_month", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.CheckConstraint("kind IN ('at_harbor', 'what_if')", name=op.f("ck_harbor_storage_rows_kind")),
        sa.CheckConstraint("cases >= 0", name=op.f("ck_harbor_storage_rows_cases_not_negative")),
        sa.CheckConstraint(
            "cases_per_pallet > 0", name=op.f("ck_harbor_storage_rows_cases_per_pallet_positive")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_harbor_storage_rows")),
    )
    # --- Row Level Security on every new table (ADR-015) ---------------------------------
    for table in ALL_TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    # Dana's records: never run this on production without a backup.
    op.drop_table("harbor_storage_rows")
    op.drop_constraint(op.f("ck_item_settings_cases_per_pallet_positive"), "item_settings", type_="check")
    op.drop_column("item_settings", "cases_per_pallet")
