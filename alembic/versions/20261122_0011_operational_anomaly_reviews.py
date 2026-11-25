"""Append-only operational anomaly review history, without backfill."""

import sqlalchemy as sa

from alembic import op

revision = "20261122_0011"
down_revision = "20261122_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operational_anomaly_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "transaction_id",
            sa.Integer(),
            sa.ForeignKey("operational_anomaly_jobs.transaction_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(25), nullable=False),
        sa.Column("note", sa.String(1000), nullable=False),
        sa.Column(
            "actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("result_digest", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.UniqueConstraint("transaction_id", "version", name="uq_operational_review_version"),
        sa.UniqueConstraint(
            "transaction_id", "actor_id", "idempotency_key", name="uq_operational_review_key"
        ),
        sa.CheckConstraint("version > 0", name="ck_operational_review_version"),
        sa.CheckConstraint(
            "decision IN ('confirmed_business_issue', 'legitimate', 'insufficient_evidence')",
            name="ck_operational_review_decision",
        ),
        sa.CheckConstraint(
            "length(trim(note)) BETWEEN 1 AND 1000", name="ck_operational_review_note"
        ),
        sa.CheckConstraint(
            "length(result_digest) = 64 AND length(request_digest) = 64",
            name="ck_operational_review_digest",
        ),
    )


def downgrade() -> None:
    op.drop_table("operational_anomaly_reviews")
