"""Add actor-scoped idempotency columns to inbounds and outbounds.

Revision ID: 20261125_0013
Revises: 20261122_0012
"""

import sqlalchemy as sa

from alembic import op

revision = "20261125_0013"
down_revision = "20261122_0012"
branch_labels = None
depends_on = None

TABLES = ("inbounds", "outbounds")


def _columns():
    return (
        sa.Column("idempotency_key", sa.Uuid(), nullable=True),
        sa.Column("request_fingerprint", sa.String(64), nullable=True),
    )


def _constraint_name(table: str) -> str:
    return f"uq_{table}_actor_key"


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "sqlite":
        for table in TABLES:
            with op.batch_alter_table(table) as batch:
                for column in _columns():
                    batch.add_column(column)
                batch.create_unique_constraint(
                    _constraint_name(table), ["created_by_id", "idempotency_key"]
                )
        return
    for table in TABLES:
        for column in _columns():
            op.add_column(table, column)
        op.create_unique_constraint(
            _constraint_name(table), table, ["created_by_id", "idempotency_key"]
        )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "sqlite":
        for table in TABLES:
            with op.batch_alter_table(table) as batch:
                batch.drop_constraint(_constraint_name(table), type_="unique")
                batch.drop_column("request_fingerprint")
                batch.drop_column("idempotency_key")
        return
    for table in TABLES:
        op.drop_constraint(_constraint_name(table), table, type_="unique")
        op.drop_column(table, "request_fingerprint")
        op.drop_column(table, "idempotency_key")
