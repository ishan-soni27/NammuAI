"""BlueTide stays the record (ADR-032): drop the Phase 6 record-keeping tables.

Ishan's scope review: the app had become a second system of record (POs, receipts, shipments,
picks, moves, template imports), with matching rules R1-R10 and double data entry for Dana's team.
BlueTide owns every fact; the app keeps only Dana's knowledge and the logs. The code that used
these tables is archived on the git tag `archive/system-of-record`.

Before this ran on production, the 12 tables held only "Claude (live click-through)" test records:
PO KB-00001 (cancelled), order SH-00001 (cancelled) and 8 stock movements that net to zero.

Also narrows uploads.kind to 'bluetide' (Dana's own templates were cut; no template upload existed).

Downgrade re-creates the 12 tables EMPTY, from the original migrations (0002, 0003, and 0004's three
tables), so the schema can go back; the data does not come back.

Revision ID: 0006
Revises: 0005
Created: 2026-11-26
"""

from collections.abc import Sequence
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Every table this migration creates (none: it only drops). tests/unit/test_invariants.py reads this.
ALL_TABLES: tuple[str, ...] = ()

# Children before parents (foreign keys inside this set, and into uploads).
DROPPED = (
    "stock_movements",
    "shipment_lines",
    "shipments",
    "app_customers",
    "po_line_status",
    "purchase_order_lines_app",
    "purchase_orders",
    "app_items",
    "app_vendors",
    "stock_count_lines",
    "stock_counts",
    "app_sales_lines",
)


def upgrade() -> None:
    for table in DROPPED:
        op.drop_table(table)
    op.drop_constraint(op.f("ck_uploads_kind"), "uploads", type_="check")
    op.create_check_constraint(op.f("ck_uploads_kind"), "uploads", "kind IN ('bluetide')")


def _migration(name: str):  # noqa: ANN202 - an Alembic revision module
    path = Path(__file__).with_name(name)
    spec = spec_from_file_location(f"kb_migration_{path.stem}", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _now(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)


def downgrade() -> None:
    # The schema only: the records themselves are gone (they were test records; see the docstring).
    op.drop_constraint(op.f("ck_uploads_kind"), "uploads", type_="check")
    op.create_check_constraint(op.f("ck_uploads_kind"), "uploads", "kind IN ('bluetide', 'template')")
    _migration("0002_dana_records.py").upgrade()  # app_vendors .. stock_movements, with RLS
    _migration("0003_shipments.py").upgrade()  # app_customers, shipments, shipment_lines, with RLS
    # 0004's three record tables (its uploads tables were never dropped).
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
    for table in ("stock_counts", "stock_count_lines", "app_sales_lines"):
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
