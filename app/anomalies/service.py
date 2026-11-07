"""Atomic, authorization-checked fixture catalog import and review."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.export import canonical_json
from app.analytics.schemas import Contract
from app.anomalies import repository
from app.anomalies.catalog import (
    PublicAlert,
    PublicAnomalyRun,
    PublicExplanation,
    PublicPartition,
    PublicPayload,
)
from app.anomalies.models import AnomalyAlert, AnomalyReview, AnomalyRun
from app.core.config import Settings
from app.core.errors import DomainError
from app.models.domain import User, UserRole

ReviewStatus = Literal["new", "confirmed", "dismissed"]


class AnomalyReviewRequest(Contract):
    expected_version: int = Field(ge=1)
    decision: Literal["confirmed", "dismissed"]
    note: str = Field(min_length=1, max_length=500)

    @field_validator("note")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("note is required")
        return value


class AnomalyReviewResult(Contract):
    alert_id: str
    status: Literal["confirmed", "dismissed"]
    version: int
    review_id: UUID
    replayed: bool


class ImportedRun(Contract):
    run_id: str
    alert_count: int
    replayed: bool


def _conflict():
    return DomainError(409, "ANOMALY_CONFLICT", "Anomaly state conflict.")


class AnomalyService:
    def __init__(self, session: Session, *, app_env: str, allow_fixture: bool):
        self.session = session
        self.app_env = app_env
        self.allow_fixture = allow_fixture

    def _authorize(self, actor_id: int):
        actor = repository.lock_actor(self.session, actor_id)
        if actor is None or not actor.is_active:
            raise DomainError(401, "INVALID_CREDENTIALS", "Invalid authentication credentials.")
        if actor.role not in (UserRole.ADMIN, UserRole.WAREHOUSE):
            raise DomainError(403, "FORBIDDEN", "Permission denied.")
        if self.app_env not in ("test", "integration") or self.allow_fixture is not True:
            raise DomainError(404, "NOT_FOUND", "Not found.")

    def import_run(self, actor: int, verified_run: PublicAnomalyRun) -> ImportedRun:
        with self.session.begin_nested():
            self._authorize(actor)
            body = canonical_json(verified_run.payload)
            payload = PublicPayload.model_validate_json(body)
            digest = hashlib.sha256(body).hexdigest()
            if verified_run.run_id != "arv1-" + digest or canonical_json(payload) != body:
                raise ValueError("catalog identity mismatch")
            payload_json = json.loads(body)
            inserted = repository.insert_run(
                self.session,
                {
                    "run_id": verified_run.run_id,
                    "digest": digest,
                    "payload": payload_json,
                    "imported_at": datetime.now(UTC),
                    "imported_by": actor,
                },
            )
            if inserted is None:
                previous = repository.get_run(self.session, verified_run.run_id)
                if (
                    previous is None
                    or previous.digest != digest
                    or canonical_json(previous.payload) != body
                ):
                    raise _conflict()
                return ImportedRun(
                    run_id=verified_run.run_id, alert_count=len(payload.alerts), replayed=True
                )
            for alert in payload.alerts:
                alert_id = (
                    "alv1-"
                    + hashlib.sha256(
                        canonical_json([verified_run.run_id, alert.source_record_key])
                    ).hexdigest()
                )
                self.session.add(
                    AnomalyAlert(
                        id=alert_id,
                        run_id=verified_run.run_id,
                        source_record_key=alert.source_record_key,
                        payload=json.loads(canonical_json(alert)),
                        review_status="new",
                        version=1,
                    )
                )
            self.session.flush()
            return ImportedRun(
                run_id=verified_run.run_id, alert_count=len(payload.alerts), replayed=False
            )

    def review_alert(
        self, actor: int, alert_id: str, key: UUID, request: AnomalyReviewRequest
    ) -> AnomalyReviewResult:
        request = AnomalyReviewRequest.model_validate(request.model_dump())
        fingerprint = hashlib.sha256(
            canonical_json({"alert_id": alert_id, **request.model_dump()})
        ).hexdigest()
        with self.session.begin_nested():
            self._authorize(actor)
            repository.lock_key(self.session, actor, key)
            existing = repository.get_review(self.session, actor, key)
            if existing is not None:
                if existing.request_fingerprint != fingerprint:
                    raise _conflict()
                return AnomalyReviewResult(
                    alert_id=existing.alert_id,
                    status=existing.decision,
                    version=existing.expected_version + 1,
                    review_id=existing.id,
                    replayed=True,
                )
            alert = repository.lock_alert(self.session, alert_id)
            if alert is None:
                raise DomainError(404, "NOT_FOUND", "Not found.")
            if alert.version != request.expected_version or alert.review_status == request.decision:
                raise _conflict()
            review = AnomalyReview(
                id=uuid4(),
                alert_id=alert_id,
                actor_user_id=actor,
                expected_version=request.expected_version,
                decision=request.decision,
                note=request.note,
                idempotency_key=key,
                request_fingerprint=fingerprint,
                created_at=datetime.now(UTC),
            )
            alert.review_status = request.decision
            alert.version += 1
            self.session.add(review)
            self.session.flush()
            return AnomalyReviewResult(
                alert_id=alert_id,
                status=review.decision,
                version=alert.version,
                review_id=review.id,
                replayed=False,
            )


class StatusView(BaseModel):
    state: Literal["available", "unavailable"]
    dataset_class: Literal["fixture"] | None
    real_precision_recall: Literal["NOT VERIFIED"] = "NOT VERIFIED"


class AlertView(BaseModel):
    alert_id: str
    run_id: str
    source_record_key: str
    occurred_at: datetime
    score: float
    threshold: float
    review_status: ReviewStatus
    version: int


class AlertList(BaseModel):
    items: list[AlertView]
    total: int
    page: int
    page_size: int


class RunSummary(BaseModel):
    input_version: str
    feature_version: str
    model_version: str
    created_at: datetime
    partitions: tuple[PublicPartition, PublicPartition, PublicPartition]
    score_definition: str
    dataset_class: Literal["fixture"]
    synthetic_disclaimer: Literal["synthetic fixture; attribution is not causal"] = (
        "synthetic fixture; attribution is not causal"
    )
    real_precision_recall: Literal["NOT VERIFIED"] = "NOT VERIFIED"


class AlertDetail(AlertView):
    features: tuple[float, float, float, float, float, float]
    feature_order: tuple[str, ...]
    explanation: PublicExplanation
    run: RunSummary


class ReviewView(BaseModel):
    review_id: UUID
    actor_user_id: int
    decision: Literal["confirmed", "dismissed"]
    note: str
    created_at: datetime
    version: int


class ReviewList(BaseModel):
    items: list[ReviewView]


def _enabled(settings: Settings) -> bool:
    return settings.app_env in ("test", "integration") and settings.anomalies_allow_fixture


def _fresh_actor(session: Session, actor: User) -> User:
    fresh = session.scalar(
        select(User).where(User.id == actor.id).execution_options(populate_existing=True)
    )
    if fresh is None or not fresh.is_active:
        raise DomainError(401, "INVALID_CREDENTIALS", "Invalid authentication credentials.")
    if fresh.role not in (UserRole.ADMIN, UserRole.WAREHOUSE):
        raise DomainError(403, "FORBIDDEN", "Permission denied.")
    return fresh


def _not_found():
    return DomainError(404, "ANOMALY_NOT_FOUND", "Anomaly not found.")


def _checked_payload(run: AnomalyRun) -> PublicPayload:
    try:
        body = canonical_json(run.payload)
        digest = hashlib.sha256(body).hexdigest()
        payload = PublicPayload.model_validate_json(body)
        if (
            digest != run.digest
            or run.run_id != "arv1-" + digest
            or canonical_json(payload) != body
        ):
            raise ValueError("invalid imported run")
        return payload
    except (ValueError, TypeError, KeyError):
        raise DomainError(409, "ANOMALY_CATALOG_INVALID", "Anomaly catalog is invalid.") from None


def _checked_alert(alert: AnomalyAlert, run: AnomalyRun):
    payload = _checked_payload(run)
    try:
        public = PublicAlert.model_validate_json(canonical_json(alert.payload))
        expected = (
            "alv1-"
            + hashlib.sha256(canonical_json([run.run_id, alert.source_record_key])).hexdigest()
        )
        if (
            alert.id != expected
            or alert.source_record_key != public.source_record_key
            or not any(public == item for item in payload.alerts)
        ):
            raise ValueError("invalid imported alert")
    except (ValueError, TypeError, KeyError):
        raise DomainError(409, "ANOMALY_CATALOG_INVALID", "Anomaly catalog is invalid.") from None
    return payload, public


def _get_alert(session: Session, alert_id: str):
    row = session.execute(
        select(AnomalyAlert, AnomalyRun)
        .join(AnomalyRun, AnomalyRun.run_id == AnomalyAlert.run_id)
        .where(AnomalyAlert.id == alert_id)
    ).first()
    if row is None:
        raise _not_found()
    alert, run = row
    payload, public = _checked_alert(alert, run)
    return alert, run, payload, public


def _view(alert: AnomalyAlert, run: AnomalyRun, payload: PublicPayload, public: PublicAlert):
    return AlertView(
        alert_id=alert.id,
        run_id=run.run_id,
        source_record_key=alert.source_record_key,
        occurred_at=public.occurred_at,
        score=public.score,
        threshold=payload.threshold,
        review_status=alert.review_status,
        version=alert.version,
    )


def status(actor: User, session: Session, settings: Settings):
    _fresh_actor(session, actor)
    if not _enabled(settings):
        return StatusView(state="unavailable", dataset_class=None)
    run = session.scalar(
        select(AnomalyRun).order_by(AnomalyRun.imported_at.desc(), AnomalyRun.run_id).limit(1)
    )
    if run is None:
        return StatusView(state="unavailable", dataset_class=None)
    _checked_payload(run)
    return StatusView(state="available", dataset_class="fixture")


def list_alerts(
    actor: User,
    session: Session,
    settings: Settings,
    page: int = 1,
    page_size: int = 20,
    status: ReviewStatus | None = None,
):
    _fresh_actor(session, actor)
    if not _enabled(settings):
        return AlertList(items=[], total=0, page=page, page_size=page_size)
    query = select(AnomalyAlert, AnomalyRun).join(
        AnomalyRun, AnomalyRun.run_id == AnomalyAlert.run_id
    )
    count = select(func.count()).select_from(AnomalyAlert)
    if status is not None:
        query = query.where(AnomalyAlert.review_status == status)
        count = count.where(AnomalyAlert.review_status == status)
    rows = session.execute(
        query.order_by(AnomalyAlert.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = []
    for alert, run in rows:
        payload, public = _checked_alert(alert, run)
        items.append(_view(alert, run, payload, public))
    return AlertList(items=items, total=session.scalar(count), page=page, page_size=page_size)


def detail(alert_id: str, actor: User, session: Session, settings: Settings):
    _fresh_actor(session, actor)
    if not _enabled(settings):
        raise _not_found()
    alert, run, payload, public = _get_alert(session, alert_id)
    summary = RunSummary(
        input_version=payload.input_version,
        feature_version=payload.feature_version,
        model_version=payload.model_version,
        created_at=payload.created_at,
        partitions=payload.partitions,
        score_definition=payload.score_definition,
        dataset_class=payload.dataset_class,
    )
    return AlertDetail(
        **_view(alert, run, payload, public).model_dump(),
        features=public.features,
        feature_order=payload.feature_order,
        explanation=public.explanation,
        run=summary,
    )


def reviews(alert_id: str, actor: User, session: Session, settings: Settings):
    _fresh_actor(session, actor)
    if not _enabled(settings):
        raise _not_found()
    _get_alert(session, alert_id)
    rows = session.scalars(
        select(AnomalyReview)
        .where(AnomalyReview.alert_id == alert_id)
        .order_by(AnomalyReview.created_at, AnomalyReview.id)
    ).all()
    return ReviewList(
        items=[
            ReviewView(
                review_id=r.id,
                actor_user_id=r.actor_user_id,
                decision=r.decision,
                note=r.note,
                created_at=r.created_at,
                version=r.expected_version + 1,
            )
            for r in rows
        ]
    )


def review(
    alert_id: str,
    request: AnomalyReviewRequest,
    actor: User,
    session: Session,
    settings: Settings,
    key: UUID,
):
    _fresh_actor(session, actor)
    if not _enabled(settings):
        raise _not_found()
    _get_alert(session, alert_id)
    try:
        result = AnomalyService(
            session, app_env=settings.app_env, allow_fixture=settings.anomalies_allow_fixture
        ).review_alert(actor.id, alert_id, key, request)
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise
