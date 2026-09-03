"""Create the Phase 1 Smart Warehouse schema.

Revision ID: 20260829_0001
Revises:
Create Date: 2026-08-29 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260829_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

USER_ROLE = sa.Enum(
    "admin", "warehouse", "client", name="user_role", native_enum=False, create_constraint=True
)
TRANSACTION_TYPE = sa.Enum(
    "inbound", "outbound", name="transaction_type", native_enum=False, create_constraint=True
)
REQUEST_STATUS = sa.Enum(
    "pending",
    "approved",
    "rejected",
    "fulfilled",
    name="purchase_request_status",
    native_enum=False,
    create_constraint=True,
)


def timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", USER_ROLE, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        *timestamps(),
    )
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("parent_id", sa.Integer, sa.ForeignKey("categories.id", ondelete="RESTRICT")),
        *timestamps(),
    )
    op.create_index("ix_categories_parent_id", "categories", ["parent_id"])
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("email", sa.String(320), unique=True),
        sa.Column("phone", sa.String(50)),
        sa.Column("address", sa.Text),
        *timestamps(),
    )
    op.create_table(
        "warehouses",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("address", sa.Text, nullable=False),
        sa.Column("latitude", sa.Float),
        sa.Column("longitude", sa.Float),
        *timestamps(),
    )
    op.create_table(
        "regions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        *timestamps(),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("sku", sa.String(80), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column(
            "category_id",
            sa.Integer,
            sa.ForeignKey("categories.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("supplier_id", sa.Integer, sa.ForeignKey("suppliers.id", ondelete="RESTRICT")),
        sa.Column("unit", sa.String(40), nullable=False),
        sa.Column("reorder_level", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.CheckConstraint("reorder_level >= 0", name="ck_products_reorder_level_nonnegative"),
        *timestamps(),
    )
    op.create_index("ix_products_category_id", "products", ["category_id"])
    op.create_index("ix_products_supplier_id", "products", ["supplier_id"])
    op.create_table(
        "stocks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "warehouse_id",
            sa.Integer,
            sa.ForeignKey("warehouses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.Integer,
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.CheckConstraint("quantity >= 0", name="ck_stocks_quantity_nonnegative"),
        sa.UniqueConstraint("warehouse_id", "product_id", name="uq_stocks_warehouse_product"),
        *timestamps(),
    )
    for table in ("inbounds", "outbounds"):
        op.create_table(
            table,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "warehouse_id",
                sa.Integer,
                sa.ForeignKey("warehouses.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "product_id",
                sa.Integer,
                sa.ForeignKey("products.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("quantity", sa.Integer, nullable=False),
            sa.Column("reference", sa.String(120)),
            sa.Column("note", sa.Text),
            sa.Column(
                "created_by_id",
                sa.Integer,
                sa.ForeignKey("users.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.CheckConstraint("quantity > 0", name=f"ck_{table}_quantity_positive"),
        )
        op.create_index(
            f"ix_{table}_warehouse_product_created_at",
            table,
            ["warehouse_id", "product_id", "created_at"],
        )
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("transaction_type", TRANSACTION_TYPE, nullable=False),
        sa.Column(
            "warehouse_id",
            sa.Integer,
            sa.ForeignKey("warehouses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.Integer,
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("inbound_id", sa.Integer, sa.ForeignKey("inbounds.id", ondelete="RESTRICT")),
        sa.Column("outbound_id", sa.Integer, sa.ForeignKey("outbounds.id", ondelete="RESTRICT")),
        sa.Column(
            "created_by_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("quantity > 0", name="ck_transactions_quantity_positive"),
    )
    op.create_index(
        "ix_transactions_warehouse_product_type_created_at",
        "transactions",
        ["warehouse_id", "product_id", "transaction_type", "created_at"],
    )
    op.create_table(
        "purchase_requests",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("request_number", sa.String(80), nullable=False, unique=True),
        sa.Column(
            "warehouse_id",
            sa.Integer,
            sa.ForeignKey("warehouses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.Integer,
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("status", REQUEST_STATUS, nullable=False, server_default=sa.text("'pending'")),
        sa.Column(
            "requested_by_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name="ck_purchase_requests_quantity_positive"),
        *timestamps(),
    )
    op.create_table(
        "route_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "warehouse_id",
            sa.Integer,
            sa.ForeignKey("warehouses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("region_id", sa.Integer, sa.ForeignKey("regions.id", ondelete="RESTRICT")),
        sa.Column("route_payload", sa.JSON),
        sa.Column("created_by_id", sa.Integer, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def downgrade() -> None:
    for table in (
        "route_logs",
        "purchase_requests",
        "transactions",
        "outbounds",
        "inbounds",
        "stocks",
        "products",
        "regions",
        "warehouses",
        "suppliers",
        "categories",
        "users",
    ):
        op.drop_table(table)
