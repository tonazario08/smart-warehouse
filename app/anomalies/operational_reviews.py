"""Append-only human feedback for verified operational model alerts."""

import hashlib
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.export import canonical_json
from app.anomalies.operational_features import resolve_lineage
from app.anomalies.operational_models import OperationalAnomalyJob, OperationalAnomalyReview
from app.anomalies.operational_service import _summary, _visibility
from app.anomalies.service import _fresh_actor
from app.core.config import Settings
from app.core.errors import DomainError
from app.models import User
from app.models.domain import to_utc

ReviewDecision = Literal["confirmed_business_issue", "legitimate", "insufficient_evidence"]


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    expected_version: int = Field(ge=0, lt=2**31 - 1)
    decision: ReviewDecision
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class ReviewView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version: int
    decision: ReviewDecision
    note: str
    actor_id: int
    reviewed_at: datetime

    @field_validator("reviewed_at", mode="before")
    @classmethod
    def normalize_timestamp(cls, value: object) -> object:
        return to_utc(value) if isinstance(value, datetime) else value


class ReviewPage(BaseModel):
    items: list[ReviewView]
    total: int
    page: int
    page_size: int
    current_version: int


def _conflict():
    return DomainError(409, "OPERATIONAL_ANOMALY_REVIEW_CONFLICT", "Review state conflict.")


def _unavailable():
    return DomainError(404, "OPERATIONAL_ANOMALY_NOT_FOUND", "Result not found.")


def _digest(value):
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _target(session, settings, transaction_id, *, write):
    # A shared lock makes list totals and rows consistent with the writer's
    # exclusive lock; multiple writers for one alert serialize before CAS.
    job = session.scalar(
        select(OperationalAnomalyJob)
        .where(
            OperationalAnomalyJob.transaction_id == transaction_id,
            OperationalAnomalyJob.status == "succeeded",
            _visibility(settings),
        )
        .with_for_update(read=not write)
    )
    if (
        job is None
        or _summary(job).state != "flagged"
        or job.artifact_digest is None
        or job.coverage_digest is None
        or resolve_lineage(session, job) is None
    ):
        raise _unavailable()
    digest = _digest(
        {
            "artifact": job.artifact_digest,
            "coverage": job.coverage_digest,
            "source": job.source_fingerprint,
            "result": job.result,
        }
    )
    conditions = OperationalAnomalyReview.transaction_id == transaction_id
    latest = session.scalar(
        select(OperationalAnomalyReview)
        .where(conditions)
        .order_by(OperationalAnomalyReview.version.desc())
        .limit(1)
    )
    if latest is not None and latest.result_digest != digest:
        raise _unavailable()
    return digest, conditions, latest


def history(session: Session, settings: Settings, actor: User, transaction_id, page, page_size):
    _fresh_actor(session, actor)
    digest, scope, latest = _target(session, settings, transaction_id, write=False)
    rows = session.scalars(
        select(OperationalAnomalyReview)
        .where(scope, OperationalAnomalyReview.result_digest == digest)
        .order_by(OperationalAnomalyReview.version.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    count = session.scalar(
        select(func.count())
        .select_from(OperationalAnomalyReview)
        .where(scope, OperationalAnomalyReview.result_digest == digest)
    )
    return ReviewPage(
        items=[ReviewView.model_validate(row) for row in rows],
        total=count,
        page=page,
        page_size=page_size,
        current_version=latest.version if latest else 0,
    )


def record(session: Session, settings: Settings, actor: User, transaction_id, key: UUID, body):
    fresh = _fresh_actor(session, actor)
    try:
        digest, scope, latest = _target(session, settings, transaction_id, write=True)
        payload = _digest(body.model_dump())
        replay = session.scalar(
            select(OperationalAnomalyReview).where(
                scope,
                OperationalAnomalyReview.actor_id == fresh.id,
                OperationalAnomalyReview.idempotency_key == key,
            )
        )
        if replay is not None:
            if replay.result_digest != digest or replay.request_digest != payload:
                raise _conflict()
            return ReviewView.model_validate(replay)
        version = latest.version if latest else 0
        if version != body.expected_version:
            raise _conflict()
        row = OperationalAnomalyReview(
            transaction_id=transaction_id,
            version=version + 1,
            decision=body.decision,
            note=body.note,
            actor_id=fresh.id,
            reviewed_at=datetime.now(UTC),
            result_digest=digest,
            idempotency_key=key,
            request_digest=payload,
        )
        session.add(row)
        session.flush()
        result = ReviewView.model_validate(row)
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise
