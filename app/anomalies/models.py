"""Persisted fixture anomaly batches, review events and verified outbound links."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnomalyRun(Base):
    __tablename__ = "anomaly_runs"
    run_id: Mapped[str] = mapped_column(String(69), primary_key=True)
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    imported_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class AnomalyAlert(Base):
    __tablename__ = "anomaly_alerts"
    __table_args__ = (
        UniqueConstraint("run_id", "source_record_key", name="uq_anomaly_alert_source"),
        CheckConstraint(
            "review_status IN ('new','confirmed','dismissed')", name="ck_anomaly_alert_status"
        ),
        CheckConstraint("version >= 1", name="ck_anomaly_alert_version"),
    )
    id: Mapped[str] = mapped_column(String(69), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("anomaly_runs.run_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    source_record_key: Mapped[str] = mapped_column(String(69), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    review_status: Mapped[str] = mapped_column(String(16), nullable=False, default="new")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class AnomalyReview(Base):
    __tablename__ = "anomaly_reviews"
    __table_args__ = (
        UniqueConstraint("actor_user_id", "idempotency_key", name="uq_anomaly_review_actor_key"),
        CheckConstraint("decision IN ('confirmed','dismissed')", name="ck_anomaly_review_decision"),
        CheckConstraint("expected_version >= 1", name="ck_anomaly_review_version"),
        CheckConstraint("length(note) BETWEEN 1 AND 500", name="ck_anomaly_review_note"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    alert_id: Mapped[str] = mapped_column(
        ForeignKey("anomaly_alerts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    actor_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    expected_version: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AnomalyOutboundLink(Base):
    """One private demo provenance link per anomaly alert; no business mutation."""

    __tablename__ = "anomaly_outbound_links"
    __table_args__ = (
        CheckConstraint(
            "length(bundle_id) = 69 AND substr(bundle_id, 1, 5) = 'ddv1-'",
            name="ck_anomaly_outbound_link_bundle_id",
        ),
        CheckConstraint(
            "length(source_checksum) = 64", name="ck_anomaly_outbound_link_source_checksum"
        ),
        CheckConstraint(
            "length(source_fingerprint) = 64", name="ck_anomaly_outbound_link_source_fingerprint"
        ),
        CheckConstraint("length(trim(unit)) > 0", name="ck_anomaly_outbound_link_unit"),
    )

    alert_id: Mapped[str] = mapped_column(
        ForeignKey("anomaly_alerts.id", ondelete="RESTRICT"), primary_key=True
    )
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    outbound_id: Mapped[int] = mapped_column(
        ForeignKey("outbounds.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    demo_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    bundle_id: Mapped[str] = mapped_column(String(69), nullable=False)
    source_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
