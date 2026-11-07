"""Fixture-gated anomaly API delegating to the service layer."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query

from app.anomalies import service
from app.anomalies.service import (
    AlertDetail,
    AlertList,
    AnomalyReviewRequest,
    AnomalyReviewResult,
    ReviewList,
    ReviewStatus,
    StatusView,
)
from app.auth.dependencies import Permission, get_current_user, require_permission
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import User

router = APIRouter(prefix="/anomalies", tags=["anomalies"])
Db = Annotated[object, Depends(get_session)]
Config = Annotated[Settings, Depends(get_settings)]


def _fresh_user(actor: Annotated[User, Depends(get_current_user)], session: Db) -> User:
    return service._fresh_actor(session, actor)


Actor = Annotated[User, Depends(require_permission(Permission.ANOMALY_READ, _fresh_user))]
Reviewer = Annotated[User, Depends(require_permission(Permission.ANOMALY_REVIEW, _fresh_user))]


@router.get("/status", response_model=StatusView)
def status(actor: Actor, session: Db, settings: Config):
    return service.status(actor, session, settings)


@router.get("", response_model=AlertList)
def list_alerts(
    actor: Actor,
    session: Db,
    settings: Config,
    page: Annotated[int, Query(ge=1, le=10000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: ReviewStatus | None = None,
):
    return service.list_alerts(actor, session, settings, page, page_size, status)


@router.get("/{alert_id}", response_model=AlertDetail)
def detail(alert_id: str, actor: Actor, session: Db, settings: Config):
    return service.detail(alert_id, actor, session, settings)


@router.get("/{alert_id}/reviews", response_model=ReviewList)
def reviews(alert_id: str, actor: Actor, session: Db, settings: Config):
    return service.reviews(alert_id, actor, session, settings)


@router.patch("/{alert_id}/review", response_model=AnomalyReviewResult)
def review(
    alert_id: str,
    request: AnomalyReviewRequest,
    actor: Reviewer,
    session: Db,
    settings: Config,
    key: Annotated[UUID, Header(alias="Idempotency-Key")],
):
    return service.review(alert_id, request, actor, session, settings, key)
