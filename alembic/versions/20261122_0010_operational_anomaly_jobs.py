"""Add an operational B2B anomaly outbox, with no historical backfill."""

import sqlalchemy as sa

from alembic import op

revision = "20261122_0010"
down_revision = "20261122_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operational_anomaly_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "transaction_id",
            sa.Integer(),
            sa.ForeignKey("transactions.id", ondelete="RESTRICT"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "outbound_id",
            sa.Integer(),
            sa.ForeignKey("outbounds.id", ondelete="RESTRICT"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "purchase_request_id",
            sa.Integer(),
            sa.ForeignKey("purchase_requests.id", ondelete="RESTRICT"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "warehouse_id",
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
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit", sa.String(40), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), server_default="queued", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("claim_token", sa.Uuid()),
        sa.Column("artifact_digest", sa.String(64)),
        sa.Column("source_fingerprint", sa.String(64), nullable=False),
        sa.Column("coverage_digest", sa.String(64)),
        sa.Column("last_error_code", sa.String(80)),
        sa.Column("result", sa.JSON(none_as_null=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_operational_anomaly_job_status",
        ),
        sa.CheckConstraint("attempts BETWEEN 0 AND 5", name="ck_operational_anomaly_job_attempts"),
        sa.CheckConstraint(
            "(status = 'running' AND claim_token IS NOT NULL AND lease_expires_at IS NOT NULL) "
            "OR (status <> 'running' AND claim_token IS NULL AND lease_expires_at IS NULL)",
            name="ck_operational_anomaly_job_claim",
        ),
        sa.CheckConstraint(
            "(status IN ('succeeded', 'failed')) = (completed_at IS NOT NULL)",
            name="ck_operational_anomaly_job_completed",
        ),
        sa.CheckConstraint(
            "(status = 'succeeded') = (result IS NOT NULL)",
            name="ck_operational_anomaly_job_result",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_operational_anomaly_job_quantity"),
        sa.CheckConstraint("length(trim(unit)) > 0", name="ck_operational_anomaly_job_unit"),
        sa.CheckConstraint(
            "artifact_digest IS NULL OR length(artifact_digest) = 64",
            name="ck_operational_anomaly_job_artifact_digest",
        ),
        sa.CheckConstraint(
            "length(source_fingerprint) = 64",
            name="ck_operational_anomaly_job_source_fingerprint",
        ),
        sa.CheckConstraint(
            "coverage_digest IS NULL OR length(coverage_digest) = 64",
            name="ck_operational_anomaly_job_coverage_digest",
        ),
    )
    op.create_index(
        "ix_operational_anomaly_job_due",
        "operational_anomaly_jobs",
        ["status", "available_at", "id"],
    )


def downgrade() -> None:
    op.drop_table("operational_anomaly_jobs")
