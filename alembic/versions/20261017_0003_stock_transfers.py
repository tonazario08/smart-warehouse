"""Add immediate stock transfers and honest movement provenance.

Revision ID: 20261017_0003
Revises: 20260904_0002
"""

import sqlalchemy as sa

from alembic import op

revision = "20261017_0003"
down_revision = "20260904_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_transfers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "source_warehouse_id",
            sa.Integer(),
            sa.ForeignKey("warehouses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "destination_warehouse_id",
            sa.Integer(),
            sa.ForeignKey("warehouses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("reference", sa.String(120), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("source_quantity_before", sa.Integer(), nullable=False),
        sa.Column("source_quantity_after", sa.Integer(), nullable=False),
        sa.Column("destination_quantity_before", sa.Integer(), nullable=False),
        sa.Column("destination_quantity_after", sa.Integer(), nullable=False),
        sa.Column(
            "outbound_id",
            sa.Integer(),
            sa.ForeignKey("outbounds.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "inbound_id",
            sa.Integer(),
            sa.ForeignKey("inbounds.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "outbound_transaction_id",
            sa.Integer(),
            sa.ForeignKey("transactions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "inbound_transaction_id",
            sa.Integer(),
            sa.ForeignKey("transactions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.UniqueConstraint("created_by_id", "idempotency_key", name="uq_transfers_actor_key"),
        sa.UniqueConstraint("outbound_id", name="uq_transfers_outbound"),
        sa.UniqueConstraint("inbound_id", name="uq_transfers_inbound"),
        sa.UniqueConstraint("outbound_transaction_id", name="uq_transfers_outbound_transaction"),
        sa.UniqueConstraint("inbound_transaction_id", name="uq_transfers_inbound_transaction"),
        sa.CheckConstraint(
            "source_warehouse_id <> destination_warehouse_id",
            name="ck_transfers_distinct_warehouses",
        ),
        sa.CheckConstraint(
            "quantity BETWEEN 1 AND 2147483647", name="ck_transfers_quantity_bounds"
        ),
        sa.CheckConstraint(
            "source_quantity_before BETWEEN 0 AND 2147483647 AND "
            "source_quantity_after BETWEEN 0 AND 2147483647 AND "
            "destination_quantity_before BETWEEN 0 AND 2147483647 AND "
            "destination_quantity_after BETWEEN 0 AND 2147483647",
            name="ck_transfers_balance_bounds",
        ),
    )
    op.create_index("ix_transfers_created_at_id", "stock_transfers", ["created_at", "id"])
    op.create_table(
        "movement_provenance",
        sa.Column(
            "transaction_id",
            sa.Integer(),
            sa.ForeignKey("transactions.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column(
            "transfer_id",
            sa.Integer(),
            sa.ForeignKey("stock_transfers.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.CheckConstraint(
            "purpose IN ('legacy_unknown', 'standard_inbound', 'standard_outbound', "
            "'transfer_in', 'transfer_out')",
            name="ck_provenance_purpose",
        ),
        sa.CheckConstraint(
            "(purpose IN ('transfer_in', 'transfer_out') AND transfer_id IS NOT NULL) OR "
            "(purpose IN ('legacy_unknown', 'standard_inbound', 'standard_outbound') "
            "AND transfer_id IS NULL)",
            name="ck_provenance_transfer_link",
        ),
    )
    op.create_index("ix_provenance_transfer_id", "movement_provenance", ["transfer_id"])
    op.execute(
        sa.text(
            "INSERT INTO movement_provenance (transaction_id,purpose,transfer_id) "
            "SELECT id,'legacy_unknown',NULL FROM transactions"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_provenance_transfer_id", table_name="movement_provenance")
    op.drop_table("movement_provenance")
    op.drop_index("ix_transfers_created_at_id", table_name="stock_transfers")
    op.drop_table("stock_transfers")
