"""Add production integrity constraints and administrative audit persistence.

Revision ID: 20260904_0002
Revises: 20260829_0001
Create Date: 2026-09-04 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260904_0002"
down_revision: str | Sequence[str] | None = "20260829_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _normalization_collisions() -> list[str]:
    connection = op.get_bind()
    checks = (
        (
            "users.email",
            "SELECT 1 FROM users GROUP BY lower(trim(email)) HAVING count(*) > 1 LIMIT 1",
        ),
        (
            "products.sku",
            "SELECT 1 FROM products GROUP BY upper(trim(sku)) HAVING count(*) > 1 LIMIT 1",
        ),
        (
            "warehouses.code",
            "SELECT 1 FROM warehouses GROUP BY upper(trim(code)) HAVING count(*) > 1 LIMIT 1",
        ),
    )
    return [label for label, query in checks if connection.execute(sa.text(query)).first()]


def upgrade() -> None:
    collisions = _normalization_collisions()
    if collisions:
        fields = ", ".join(collisions)
        raise RuntimeError(
            f"Migration blocked by normalization collisions in: {fields}. "
            "Resolve duplicate legacy values before retrying the upgrade."
        )

    op.execute("UPDATE users SET email = lower(trim(email))")
    op.execute("UPDATE products SET sku = upper(trim(sku))")
    op.execute("UPDATE warehouses SET code = upper(trim(code))")

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "actor_user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("target_type", sa.String(80), nullable=False),
        sa.Column("target_id", sa.Integer, nullable=False),
        sa.Column("before_data", sa.JSON),
        sa.Column("after_data", sa.JSON),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_target_id", "audit_logs", ["target_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    with op.batch_alter_table("warehouses") as batch_op:
        batch_op.create_check_constraint(
            "ck_warehouses_code_normalized", "code = upper(trim(code))"
        )
        batch_op.create_check_constraint(
            "ck_warehouses_coordinates_paired_and_ranged",
            "(latitude IS NULL AND longitude IS NULL) OR "
            "(latitude IS NOT NULL AND longitude IS NOT NULL AND "
            "latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)",
        )
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.create_check_constraint(
            "ck_transactions_exactly_one_movement",
            "(transaction_type = 'inbound' AND inbound_id IS NOT NULL AND outbound_id IS NULL) OR "
            "(transaction_type = 'outbound' AND outbound_id IS NOT NULL AND inbound_id IS NULL)",
        )
    op.create_index("uq_users_email_lower", "users", [sa.text("lower(email)")], unique=True)
    op.create_index("uq_products_sku_upper", "products", [sa.text("upper(sku)")], unique=True)
    op.create_index(
        "uq_warehouses_code_upper", "warehouses", [sa.text("upper(code)")], unique=True
    )


def downgrade() -> None:
    op.drop_index("uq_warehouses_code_upper", table_name="warehouses")
    op.drop_index("uq_products_sku_upper", table_name="products")
    op.drop_index("uq_users_email_lower", table_name="users")

    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_constraint("ck_transactions_exactly_one_movement", type_="check")
    with op.batch_alter_table("warehouses") as batch_op:
        batch_op.drop_constraint("ck_warehouses_coordinates_paired_and_ranged", type_="check")
        batch_op.drop_constraint("ck_warehouses_code_normalized", type_="check")

    op.drop_table("audit_logs")
