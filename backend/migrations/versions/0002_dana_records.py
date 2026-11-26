"""Dana's own records (Phase 6, step 1; ADR-026, ADR-027): suppliers, items, POs, PO line status, stock ledger.

All app layer: the loader never truncates these (invariant #5), and none has a foreign key into the
BlueTide (clean) tables. RLS is enabled on every new table (ADR-015; see 0001's docstring).

Revision ID: 0002
Revises: 0001
Created: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Every table this migration creates (tests/unit/test_invariants.py checks RLS covers them all).
ALL_TABLES = (
    "app_vendors",
    "app_items",
    "purchase_orders",
    "purchase_order_lines_app",
    "po_line_status",
    "stock_movements",
)


def _who() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "app_vendors",
        sa.Column("vendor_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        *_who(),
        sa.PrimaryKeyConstraint("vendor_code", name=op.f("pk_app_vendors")),
    )
    op.create_table(
        "app_items",
        sa.Column("item_code", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("sell_uom", sa.Text(), nullable=False),
        sa.Column("lb_per_case", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column("vendor_code", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        *_who(),
        sa.CheckConstraint("sell_uom IN ('CS', 'LB')", name=op.f("ck_app_items_sell_uom")),
        sa.CheckConstraint("status IN ('active', 'discontinued')", name=op.f("ck_app_items_status")),
        sa.CheckConstraint(
            "lb_per_case IS NULL OR lb_per_case > 0", name=op.f("ck_app_items_lb_per_case_positive")
        ),
        sa.PrimaryKeyConstraint("item_code", name=op.f("pk_app_items")),
    )
    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("po_no", sa.Text(), nullable=False),
        sa.Column("vendor_code", sa.Text(), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        *_who(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_purchase_orders")),
        sa.UniqueConstraint("po_no", name=op.f("uq_purchase_orders_po_no")),
    )
    op.create_table(
        "purchase_order_lines_app",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("po_id", sa.BigInteger(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("item_code", sa.Text(), nullable=False),
        sa.Column("qty_ordered", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.CheckConstraint("qty_ordered > 0", name=op.f("ck_purchase_order_lines_app_qty_positive")),
        sa.ForeignKeyConstraint(
            ["po_id"], ["purchase_orders.id"], name=op.f("fk_purchase_order_lines_app_po_id_purchase_orders")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_purchase_order_lines_app")),
        sa.UniqueConstraint("po_id", "line_no", name=op.f("uq_purchase_order_lines_app_po_id_line_no")),
    )
    op.create_table(
        "po_line_status",
        sa.Column("po_no", sa.Text(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("shipped_on", sa.Date(), nullable=True),
        sa.Column("container_no", sa.Text(), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=False),
        sa.CheckConstraint("status IN ('shipped', 'cancelled')", name=op.f("ck_po_line_status_status")),
        sa.PrimaryKeyConstraint("po_no", "line_no", name=op.f("pk_po_line_status")),
    )
    op.create_table(
        "stock_movements",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("movement_date", sa.Date(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("item_code", sa.Text(), nullable=False),
        sa.Column("location_code", sa.Text(), nullable=False),
        sa.Column("lot_no", sa.Text(), nullable=False),
        sa.Column("qty", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("unit_cost", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column("po_no", sa.Text(), nullable=True),
        sa.Column("po_line_no", sa.Integer(), nullable=True),
        sa.Column("reverses_id", sa.BigInteger(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('receipt', 'shipment', 'sample', 'move_out', 'move_in', 'adjustment')",
            name=op.f("ck_stock_movements_kind"),
        ),
        sa.CheckConstraint("qty <> 0", name=op.f("ck_stock_movements_qty_not_zero")),
        sa.ForeignKeyConstraint(
            ["reverses_id"], ["stock_movements.id"], name=op.f("fk_stock_movements_reverses_id_stock_movements")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_movements")),
    )
    op.create_index("ix_stock_movements_item", "stock_movements", ["item_code"], unique=False)
    op.create_index("ix_stock_movements_po_line", "stock_movements", ["po_no", "po_line_no"], unique=False)

    # --- Row Level Security on every new table (ADR-015) ---------------------------------
    for table in ALL_TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    # Dana's records: never run this on production without a backup (it drops her POs and receipts).
    op.drop_index("ix_stock_movements_po_line", table_name="stock_movements")
    op.drop_index("ix_stock_movements_item", table_name="stock_movements")
    op.drop_table("stock_movements")
    op.drop_table("po_line_status")
    op.drop_table("purchase_order_lines_app")
    op.drop_table("purchase_orders")
    op.drop_table("app_items")
    op.drop_table("app_vendors")
