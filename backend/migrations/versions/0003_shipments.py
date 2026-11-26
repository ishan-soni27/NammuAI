"""Shipments and moving stock (Phase 6, step 2; ADR-028): customers, shipments, lines, movement links.

App layer: the loader never truncates these (invariant #5), no foreign keys into BlueTide's tables.
RLS is enabled on every new table (ADR-015).

Revision ID: 0003
Revises: 0002
Created: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Every table this migration creates (tests/unit/test_invariants.py checks RLS covers them all).
ALL_TABLES = ("app_customers", "shipments", "shipment_lines")


def _who() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "app_customers",
        sa.Column("customer_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("customer_type", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        *_who(),
        sa.PrimaryKeyConstraint("customer_code", name=op.f("pk_app_customers")),
    )
    op.create_table(
        "shipments",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("order_no", sa.Text(), nullable=False),
        sa.Column("customer_code", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("ship_date", sa.Date(), nullable=False),
        sa.Column("location_code", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("shipped_on", sa.Date(), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        *_who(),
        sa.CheckConstraint("status IN ('open', 'shipped', 'cancelled')", name=op.f("ck_shipments_status")),
        sa.CheckConstraint("kind IN ('customer', 'sample')", name=op.f("ck_shipments_kind")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shipments")),
        sa.UniqueConstraint("order_no", name=op.f("uq_shipments_order_no")),
    )
    op.create_table(
        "shipment_lines",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("shipment_id", sa.BigInteger(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("item_code", sa.Text(), nullable=False),
        sa.Column("qty", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.CheckConstraint("qty > 0", name=op.f("ck_shipment_lines_qty_positive")),
        sa.ForeignKeyConstraint(
            ["shipment_id"], ["shipments.id"], name=op.f("fk_shipment_lines_shipment_id_shipments")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shipment_lines")),
        sa.UniqueConstraint("shipment_id", "line_no", name=op.f("uq_shipment_lines_shipment_id_line_no")),
    )
    op.add_column("stock_movements", sa.Column("shipment_id", sa.BigInteger(), nullable=True))
    op.add_column("stock_movements", sa.Column("shipment_line_no", sa.Integer(), nullable=True))
    op.add_column("stock_movements", sa.Column("pair_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        op.f("fk_stock_movements_shipment_id_shipments"), "stock_movements", "shipments", ["shipment_id"], ["id"]
    )
    op.create_foreign_key(
        op.f("fk_stock_movements_pair_id_stock_movements"), "stock_movements", "stock_movements", ["pair_id"], ["id"]
    )

    # --- Row Level Security on every new table (ADR-015) ---------------------------------
    for table in ALL_TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    # Dana's records: never run this on production without a backup.
    op.drop_constraint(op.f("fk_stock_movements_pair_id_stock_movements"), "stock_movements", type_="foreignkey")
    op.drop_constraint(op.f("fk_stock_movements_shipment_id_shipments"), "stock_movements", type_="foreignkey")
    op.drop_column("stock_movements", "pair_id")
    op.drop_column("stock_movements", "shipment_line_no")
    op.drop_column("stock_movements", "shipment_id")
    op.drop_table("shipment_lines")
    op.drop_table("shipments")
    op.drop_table("app_customers")
