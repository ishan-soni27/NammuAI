"""Imports from the website (Phase 6, step 3; ADR-029): uploads and their files, Dana's stock counts
and sales history, and a copy of the reference seeds on every load run.

App layer (uploads, upload_files, stock_counts, stock_count_lines, app_sales_lines): the loader never
truncates them (invariant #5), no foreign keys into BlueTide's tables. RLS on every new table (ADR-015).

Revision ID: 0004
Revises: 0003
Created: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Every table this migration creates (tests/unit/test_invariants.py checks RLS covers them all).
ALL_TABLES = ("uploads", "upload_files", "stock_counts", "stock_count_lines", "app_sales_lines")


def _now(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)


def upgrade() -> None:
    op.add_column("load_runs", sa.Column("reference", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_table(
        "uploads",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confirm_code", sa.Text(), nullable=True),
        sa.Column("load_run_id", sa.BigInteger(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        _now("created_at"),
        sa.Column("created_by", sa.Text(), nullable=False),
        _now("updated_at"),
        sa.Column("updated_by", sa.Text(), nullable=False),
        sa.CheckConstraint("kind IN ('bluetide', 'template')", name=op.f("ck_uploads_kind")),
        sa.CheckConstraint(
            "status IN ('open', 'checked', 'loaded', 'failed', 'discarded')", name=op.f("ck_uploads_status")
        ),
        sa.ForeignKeyConstraint(["load_run_id"], ["load_runs.id"], name=op.f("fk_uploads_load_run_id_load_runs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_uploads")),
    )
    op.create_table(
        "upload_files",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("upload_id", sa.BigInteger(), nullable=False),
        sa.Column("slot", sa.Text(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("rows", sa.Integer(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        _now("created_at"),
        sa.ForeignKeyConstraint(["upload_id"], ["uploads.id"], name=op.f("fk_upload_files_upload_id_uploads")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_upload_files")),
        sa.UniqueConstraint("upload_id", "slot", name=op.f("uq_upload_files_upload_id_slot")),
    )
    op.create_table(
        "stock_counts",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("count_date", sa.Date(), nullable=False),
        sa.Column("upload_id", sa.BigInteger(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        _now("created_at"),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["upload_id"], ["uploads.id"], name=op.f("fk_stock_counts_upload_id_uploads")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_counts")),
    )
    op.create_table(
        "stock_count_lines",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("count_id", sa.BigInteger(), nullable=False),
        sa.Column("item_code", sa.Text(), nullable=False),
        sa.Column("location_code", sa.Text(), nullable=False),
        sa.Column("lot_no", sa.Text(), nullable=False),
        sa.Column("qty", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("unit_cost", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.CheckConstraint("qty >= 0", name=op.f("ck_stock_count_lines_qty_not_negative")),
        sa.ForeignKeyConstraint(
            ["count_id"], ["stock_counts.id"], name=op.f("fk_stock_count_lines_count_id_stock_counts")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_count_lines")),
    )
    op.create_table(
        "app_sales_lines",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("upload_id", sa.BigInteger(), nullable=True),
        sa.Column("order_no", sa.Text(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("ship_date", sa.Date(), nullable=True),
        sa.Column("customer_code", sa.Text(), nullable=False),
        sa.Column("item_code", sa.Text(), nullable=False),
        sa.Column("qty", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=14, scale=4), nullable=True),
        _now("created_at"),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.CheckConstraint("qty > 0", name=op.f("ck_app_sales_lines_qty_positive")),
        sa.ForeignKeyConstraint(["upload_id"], ["uploads.id"], name=op.f("fk_app_sales_lines_upload_id_uploads")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_sales_lines")),
        sa.UniqueConstraint("order_no", "line_no", name=op.f("uq_app_sales_lines_order_no_line_no")),
    )

    # --- Row Level Security on every new table (ADR-015) ---------------------------------
    for table in ALL_TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    # Dana's records: never run this on production without a backup.
    op.drop_table("app_sales_lines")
    op.drop_table("stock_count_lines")
    op.drop_table("stock_counts")
    op.drop_table("upload_files")
    op.drop_table("uploads")
    op.drop_column("load_runs", "reference")
