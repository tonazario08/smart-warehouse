"""Persistent work and provisional results for B2B purchase requests."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrderAnalyticsJob(Base):
    __tablename__ = "order_analytics_jobs"
    __table_args__ = (
        UniqueConstraint("purchase_request_id", name="uq_order_analytics_job_purchase_request"),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_order_analytics_job_status",
        ),
        CheckConstraint("attempts >= 0", name="ck_order_analytics_job_attempts"),
        CheckConstraint(
            "(status = 'running' AND claim_token IS NOT NULL AND lease_expires_at IS NOT NULL) "
            "OR (status <> 'running' AND claim_token IS NULL)",
            name="ck_order_analytics_job_claim",
        ),
        Index("ix_order_analytics_job_due", "status", "available_at", "id"),
        Index("ix_order_analytics_job_key", "warehouse_id", "product_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    purchase_request_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_requests.id", ondelete="RESTRICT")
    )
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(16), server_default="queued")
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claim_token: Mapped[UUID | None] = mapped_column(Uuid)
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OrderAnalyticsOrderCheck(Base):
    __tablename__ = "order_analytics_order_checks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('available', 'insufficient_data', 'failed')",
            name="ck_order_analytics_order_check_status",
        ),
        CheckConstraint("sample_count >= 0", name="ck_order_analytics_order_check_samples"),
    )

    purchase_request_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_requests.id", ondelete="RESTRICT"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(24))
    flagged: Mapped[bool | None] = mapped_column(Boolean)
    reason_code: Mapped[str | None] = mapped_column(String(80))
    rule_id: Mapped[str] = mapped_column(String(80))
    rule_version: Mapped[int]
    sample_count: Mapped[int]
    median: Mapped[float | None] = mapped_column(Float)
    mad: Mapped[float | None] = mapped_column(Float)
    score: Mapped[float | None] = mapped_column(Float)
    label: Mapped[str] = mapped_column(String(80))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OrderAnalyticsKeyState(Base):
    __tablename__ = "order_analytics_key_states"
    __table_args__ = (CheckConstraint("row_version >= 1", name="ck_order_analytics_key_version"),)

    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), primary_key=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), primary_key=True
    )
    row_version: Mapped[int] = mapped_column(Integer, server_default="1")
    forecast_status: Mapped[str | None] = mapped_column(String(24))
    forecast_run_id: Mapped[str | None] = mapped_column(String(80))
    forecast_dataset_class: Mapped[str | None] = mapped_column(String(40))
    forecast_stale: Mapped[bool | None] = mapped_column(Boolean)
    forecast_reason_code: Mapped[str | None] = mapped_column(String(80))
    replenishment_status: Mapped[str | None] = mapped_column(String(24))
    replenishment_run_id: Mapped[str | None] = mapped_column(String(80))
    replenishment_dataset_class: Mapped[str | None] = mapped_column(String(40))
    replenishment_reason_code: Mapped[str | None] = mapped_column(String(80))
    replenishment_demo_run_id: Mapped[str | None] = mapped_column(String(80))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
