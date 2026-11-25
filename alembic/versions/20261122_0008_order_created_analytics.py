"""Durable B2B order analytics jobs and provisional results."""

import sqlalchemy as sa

from alembic import op

revision = "20261122_0008"
down_revision = "20261113_0007"
branch_labels = None
depends_on = None


def _purchase_request_key(*, primary_key=False):
    return sa.Column(
        "purchase_request_id",
        sa.Integer(),
        sa.ForeignKey("purchase_requests.id", ondelete="RESTRICT"),
        primary_key=primary_key,
        nullable=False,
    )


def _sku_key(name, table, *, primary_key=False):
    return sa.Column(
        name,
        sa.Integer(),
        sa.ForeignKey(f"{table}.id", ondelete="RESTRICT"),
        primary_key=primary_key,
        nullable=False,
    )


def upgrade():
    op.create_table(
        "order_analytics_jobs",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        _purchase_request_key(),
        _sku_key("warehouse_id", "warehouses"),
        _sku_key("product_id", "products"),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("claim_token", sa.Uuid()),
        sa.Column("last_error_code", sa.String(80)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("purchase_request_id", name="uq_order_analytics_job_purchase_request"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_order_analytics_job_status",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_order_analytics_job_attempts"),
        sa.CheckConstraint(
            "(status = 'running' AND claim_token IS NOT NULL AND lease_expires_at IS NOT NULL) "
            "OR (status <> 'running' AND claim_token IS NULL)",
            name="ck_order_analytics_job_claim",
        ),
    )
    op.create_index(
        "ix_order_analytics_job_due", "order_analytics_jobs", ["status", "available_at", "id"]
    )
    op.create_index(
        "ix_order_analytics_job_key",
        "order_analytics_jobs",
        ["warehouse_id", "product_id", "status"],
    )

    op.create_table(
        "order_analytics_order_checks",
        _purchase_request_key(primary_key=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("flagged", sa.Boolean()),
        sa.Column("reason_code", sa.String(80)),
        sa.Column("rule_id", sa.String(80), nullable=False),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("median", sa.Float()),
        sa.Column("mad", sa.Float()),
        sa.Column("score", sa.Float()),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('available', 'insufficient_data', 'failed')",
            name="ck_order_analytics_order_check_status",
        ),
        sa.CheckConstraint("sample_count >= 0", name="ck_order_analytics_order_check_samples"),
    )

    op.create_table(
        "order_analytics_key_states",
        _sku_key("warehouse_id", "warehouses", primary_key=True),
        _sku_key("product_id", "products", primary_key=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("forecast_status", sa.String(24)),
        sa.Column("forecast_run_id", sa.String(80)),
        sa.Column("forecast_dataset_class", sa.String(40)),
        sa.Column("forecast_stale", sa.Boolean()),
        sa.Column("forecast_reason_code", sa.String(80)),
        sa.Column("replenishment_status", sa.String(24)),
        sa.Column("replenishment_run_id", sa.String(80)),
        sa.Column("replenishment_dataset_class", sa.String(40)),
        sa.Column("replenishment_reason_code", sa.String(80)),
        sa.Column("replenishment_demo_run_id", sa.String(80)),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("row_version >= 1", name="ck_order_analytics_key_version"),
    )


def downgrade():
    op.drop_table("order_analytics_key_states")
    op.drop_table("order_analytics_order_checks")
    op.drop_index("ix_order_analytics_job_key", table_name="order_analytics_jobs")
    op.drop_index("ix_order_analytics_job_due", table_name="order_analytics_jobs")
    op.drop_table("order_analytics_jobs")
