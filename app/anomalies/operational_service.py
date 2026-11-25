"""Read-side service for operational outcomes; no model loading or writes."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select, true
from sqlalchemy.orm import Session

from app.anomalies.operational_features import VerifiedOutboundView, resolve_lineage
from app.anomalies.operational_models import OperationalAnomalyJob
from app.anomalies.operational_result import FeatureVector, OperationalResult
from app.core.config import Settings
from app.core.errors import DomainError


class Summary(BaseModel):
    transaction_id: int
    state: Literal["pending", "unavailable", "normal", "flagged", "failed"]
    reason_code: str | None = None
    evaluated_at: datetime | None = None
    score: float | None = None
    threshold: float | None = None
    model_version: str | None = None
    feature_version: str | None = None
    base_value: float | None = None
    contributions: FeatureVector | None = None
    dataset_class: Literal["operational", "synthetic_test"] | None = None


class OperationalVoucherView(VerifiedOutboundView):
    dataset_class: Literal["operational", "synthetic_test"]


class Results(BaseModel):
    items: list[Summary]
    total: int
    page: int
    page_size: int


def _summary(job: OperationalAnomalyJob):
    if job.status in {"queued", "running"}:
        return Summary(transaction_id=job.transaction_id, state="pending")
    if job.status == "succeeded":
        try:
            result = OperationalResult.model_validate(job.result)
            return Summary(
                transaction_id=job.transaction_id,
                evaluated_at=job.completed_at,
                **result.model_dump(exclude={"input_fingerprint"}),
            )
        except ValidationError:
            pass
    return Summary(
        transaction_id=job.transaction_id,
        evaluated_at=job.completed_at,
        state="failed",
        reason_code="PROCESSING_FAILED",
    )


def _visibility(settings: Settings):
    if settings.app_env == "test" and settings.operational_anomaly_allow_synthetic_test:
        return true()
    # Synthetic scored results must not appear when an isolated DB is copied elsewhere.
    kind = OperationalAnomalyJob.result["dataset_class"].as_string()
    return kind.is_distinct_from("synthetic_test")


def _lookup(session: Session, settings: Settings, transaction_id: int):
    record = session.scalar(
        select(OperationalAnomalyJob).where(
            OperationalAnomalyJob.transaction_id == transaction_id, _visibility(settings)
        )
    )
    if record is None:
        raise DomainError(404, "OPERATIONAL_ANOMALY_NOT_FOUND", "Result not found.")
    return record


def results(session: Session, settings: Settings, page: int, page_size: int):
    visibility = _visibility(settings)
    rows = session.scalars(
        select(OperationalAnomalyJob)
        .where(visibility)
        .order_by(OperationalAnomalyJob.occurred_at.desc(), OperationalAnomalyJob.transaction_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return Results(
        items=[_summary(row) for row in rows],
        total=session.scalar(
            select(func.count()).select_from(OperationalAnomalyJob).where(visibility)
        ),
        page=page,
        page_size=page_size,
    )


def result(session: Session, settings: Settings, transaction_id: int):
    return _summary(_lookup(session, settings, transaction_id))


def outbound(session: Session, settings: Settings, transaction_id: int):
    record = _lookup(session, settings, transaction_id)
    summary = _summary(record)
    voucher = resolve_lineage(session, record) if summary.state == "flagged" else None
    if voucher is None or summary.dataset_class is None:
        raise DomainError(404, "OPERATIONAL_OUTBOUND_NOT_FOUND", "Voucher not found.")
    return OperationalVoucherView(**voucher.model_dump(), dataset_class=summary.dataset_class)
