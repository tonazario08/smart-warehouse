"""Authenticated, read-only forecast catalog routes."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query, Request
from pydantic import BaseModel, ConfigDict

from app.auth.dependencies import Permission, require_permission
from app.core.config import Settings, get_settings
from app.core.errors import DomainError, ErrorResponse
from app.core.pagination import Page
from app.db.session import get_session
from app.forecasting.repository import ForecastRepository
from app.forecasting.schemas import PredictionRow
from app.forecasting.service import ForecastService
from app.models import User

router = APIRouter(
    prefix="/forecasts",
    tags=["forecasts"],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)


class ForecastRead(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    manifest: dict
    metrics: dict | None
    binding: dict | None
    entity: dict | None
    applicability: Literal["retrospective", "operational"]
    stale: bool | None
    fixture_label: str | None


class ForecastStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    state: Literal["ready", "unavailable", "failed"]
    reason_code: str | None
    latest: ForecastRead | None
    latest_failure_code: str | None = None


def service(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[object, Depends(get_session)],
) -> ForecastService:
    return ForecastService(
        ForecastRepository(
            settings.forecast_catalog_root, allow_fixture=settings.forecast_allow_fixture
        ),
        session,
    )


def keys(allowed):
    def check(request: Request):
        values = request.query_params.multi_items()
        seen = set()
        for key, _ in values:
            if key not in allowed or key in seen:
                raise DomainError(422, "REQUEST_VALIDATION_ERROR", "Invalid query parameters.")
            seen.add(key)

    return check


Actor = Annotated[User, Depends(require_permission(Permission.FORECAST_READ))]
Service = Annotated[ForecastService, Depends(service)]


@router.get("/status", response_model=ForecastStatus, dependencies=[Depends(keys({"mode"}))])
def status(actor: Actor, forecast: Service, mode: Literal["research", "operational"]):
    return forecast.status(actor, mode)


@router.get(
    "/runs",
    response_model=Page[ForecastRead],
    dependencies=[Depends(keys({"mode", "page", "page_size"}))],
)
def list_runs(
    actor: Actor,
    forecast: Service,
    mode: Literal["research", "operational"],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return forecast.list_runs(actor, mode, page, page_size)


@router.get("/runs/{run_id}", response_model=ForecastRead, dependencies=[Depends(keys(set()))])
def get_run(actor: Actor, forecast: Service, run_id: str = Path(pattern=r"^frv1-[0-9a-f]{64}$")):
    return forecast._view(forecast.get_run(actor, run_id))


@router.get(
    "/runs/{run_id}/predictions",
    response_model=Page[PredictionRow],
    dependencies=[Depends(keys({"page", "page_size", "horizon", "algorithm"}))],
)
def predictions(
    actor: Actor,
    forecast: Service,
    run_id: str = Path(pattern=r"^frv1-[0-9a-f]{64}$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    horizon: int | None = Query(None, ge=1, le=7, json_schema_extra={"enum": [1, 7, None]}),
    algorithm: Literal["persistence", "seasonal_naive", "xgboost"] | None = None,
):
    if horizon is not None and horizon not in (1, 7):
        raise DomainError(422, "REQUEST_VALIDATION_ERROR", "Invalid query parameters.")
    run = forecast.get_run(actor, run_id)
    forecast._binding(run)
    rows = [
        r
        for r in run.rows
        if (horizon is None or r.horizon == horizon)
        and (algorithm is None or r.algorithm == algorithm)
    ]
    rows.sort(key=lambda row: (row.origin, row.lead, row.horizon, row.algorithm, row.series_key))
    start = (page - 1) * page_size
    return {
        "items": rows[start : start + page_size],
        "total": len(rows),
        "page": page,
        "page_size": page_size,
    }
