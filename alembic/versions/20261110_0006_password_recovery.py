"""Add password recovery and session versions.

Revision ID: 20261110_0006
Revises: 20261105_0005
"""

import sqlalchemy as sa

from alembic import op

revision = "20261110_0006"
down_revision = "20261105_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "auth_version", sa.Integer(),
            sa.CheckConstraint("auth_version >= 0", name="ck_users_auth_version"),
            server_default="0", nullable=False,
        ),
    )
    op.create_table(
        "password_reset_tokens",
        sa.Column("user_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("digest", sa.String(64), nullable=False, unique=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_table(
        "password_recovery_budget",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requests", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("password_recovery_budget")
    op.drop_table("password_reset_tokens")
    op.drop_column("users", "auth_version")
