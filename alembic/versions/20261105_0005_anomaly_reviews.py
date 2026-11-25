"""Add immutable anomaly batches and versioned review history.

Revision ID: 20261105_0005
Revises: 20261019_0004
"""

import sqlalchemy as sa

from alembic import op

revision = "20261105_0005"
down_revision = "20261019_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "anomaly_runs",
        sa.Column("run_id", sa.String(69), primary_key=True),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "imported_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
    )
    op.create_table(
        "anomaly_alerts",
        sa.Column("id", sa.String(69), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(69),
            sa.ForeignKey("anomaly_runs.run_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("source_record_key", sa.String(69), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("review_status", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("run_id", "source_record_key", name="uq_anomaly_alert_source"),
        sa.CheckConstraint(
            "review_status IN ('new','confirmed','dismissed')", name="ck_anomaly_alert_status"
        ),
        sa.CheckConstraint("version >= 1", name="ck_anomaly_alert_version"),
    )
    op.create_index("ix_anomaly_alerts_run_id", "anomaly_alerts", ["run_id"])
    op.create_table(
        "anomaly_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "alert_id",
            sa.String(69),
            sa.ForeignKey("anomaly_alerts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("expected_version", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("actor_user_id", "idempotency_key", name="uq_anomaly_review_actor_key"),
        sa.CheckConstraint(
            "decision IN ('confirmed','dismissed')", name="ck_anomaly_review_decision"
        ),
        sa.CheckConstraint("expected_version >= 1", name="ck_anomaly_review_version"),
        sa.CheckConstraint("length(note) BETWEEN 1 AND 500", name="ck_anomaly_review_note"),
    )
    op.create_index("ix_anomaly_reviews_alert_id", "anomaly_reviews", ["alert_id"])


def downgrade():
    op.drop_index("ix_anomaly_reviews_alert_id", table_name="anomaly_reviews")
    op.drop_table("anomaly_reviews")
    op.drop_index("ix_anomaly_alerts_run_id", table_name="anomaly_alerts")
    op.drop_table("anomaly_alerts")
    op.drop_table("anomaly_runs")
