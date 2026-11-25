"""Private durable results for operational B2B anomaly scoring."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OperationalAnomalyJob(Base):
    __tablename__ = "operational_anomaly_jobs"
    __table_args__ = (
        Index("ix_operational_anomaly_job_due", "status", "available_at", "id"),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_operational_anomaly_job_status",
        ),
        CheckConstraint("attempts BETWEEN 0 AND 5", name="ck_operational_anomaly_job_attempts"),
        CheckConstraint(
            "(status = 'running' AND claim_token IS NOT NULL AND lease_expires_at IS NOT NULL) "
            "OR (status <> 'running' AND claim_token IS NULL AND lease_expires_at IS NULL)",
            name="ck_operational_anomaly_job_claim",
        ),
        CheckConstraint(
            "(status IN ('succeeded', 'failed')) = (completed_at IS NOT NULL)",
            name="ck_operational_anomaly_job_completed",
        ),
        CheckConstraint(
            "(status = 'succeeded') = (result IS NOT NULL)",
            name="ck_operational_anomaly_job_result",
        ),
        CheckConstraint("quantity > 0", name="ck_operational_anomaly_job_quantity"),
        CheckConstraint("length(trim(unit)) > 0", name="ck_operational_anomaly_job_unit"),
        CheckConstraint(
            "artifact_digest IS NULL OR length(artifact_digest) = 64",
            name="ck_operational_anomaly_job_artifact_digest",
        ),
        CheckConstraint(
            "length(source_fingerprint) = 64",
            name="ck_operational_anomaly_job_source_fingerprint",
        ),
        CheckConstraint(
            "coverage_digest IS NULL OR length(coverage_digest) = 64",
            name="ck_operational_anomaly_job_coverage_digest",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"), unique=True
    )
    outbound_id: Mapped[int] = mapped_column(
        ForeignKey("outbounds.id", ondelete="RESTRICT"), unique=True
    )
    purchase_request_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_requests.id", ondelete="RESTRICT"), unique=True
    )
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    quantity: Mapped[int]
    unit: Mapped[str] = mapped_column(String(40))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), server_default="queued")
    attempts: Mapped[int] = mapped_column(server_default="0")
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claim_token: Mapped[UUID | None] = mapped_column(Uuid())
    artifact_digest: Mapped[str | None] = mapped_column(String(64))
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    coverage_digest: Mapped[str | None] = mapped_column(String(64))
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    result: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OperationalAnomalyReview(Base):
    __tablename__ = "operational_anomaly_reviews"
    __table_args__ = (
        UniqueConstraint("transaction_id", "version", name="uq_operational_review_version"),
        UniqueConstraint(
            "transaction_id", "actor_id", "idempotency_key", name="uq_operational_review_key"
        ),
        CheckConstraint("version > 0", name="ck_operational_review_version"),
        CheckConstraint(
            "decision IN ('confirmed_business_issue', 'legitimate', 'insufficient_evidence')",
            name="ck_operational_review_decision",
        ),
        CheckConstraint("length(trim(note)) BETWEEN 1 AND 1000", name="ck_operational_review_note"),
        CheckConstraint(
            "length(result_digest) = 64 AND length(request_digest) = 64",
            name="ck_operational_review_digest",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("operational_anomaly_jobs.transaction_id", ondelete="RESTRICT")
    )
    version: Mapped[int]
    decision: Mapped[str] = mapped_column(String(25))
    note: Mapped[str] = mapped_column(String(1000))
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    result_digest: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[UUID] = mapped_column(Uuid())
    request_digest: Mapped[str] = mapped_column(String(64))
