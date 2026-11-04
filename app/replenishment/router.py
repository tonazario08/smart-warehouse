"""Authenticated read-only replenishment catalog endpoints."""

from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query, Request
from pydantic import BaseModel, ConfigDict

from app.auth.dependencies import get_current_user
from app.core.config import Settings, get_settings
from app.core.errors import DomainError, ErrorResponse
from app.core.pagination import Page
from app.db.session import get_session
from app.models import User
from app.replenishment.repository import ReplenishmentRepository
from app.replenishment.schemas import SimulationDay
from app.replenishment.service import ReplenishmentService

router = APIRouter(
    prefix="/replenishment",
    tags=["replenishment"],
    responses={code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 422, 503)},
)


class ReplenishmentRead(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    manifest: dict
    calibration: dict | None
    summaries: list[dict] | None
    applicability: Literal["research_scenario", "fixture_scenario"]
    fixture_label: str | None
    stale: bool | None
    reason_codes: list[str]
    entity: dict | None


class ReplenishmentStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    state: Literal["ready", "unavailable", "failed"]
    reason_code: str | None
    latest: ReplenishmentRead | None


def service(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[object, Depends(get_session)],
):
    return ReplenishmentService(
        ReplenishmentRepository(
            settings.replenishment_catalog_root, allow_fixture=settings.replenishment_allow_fixture
        ),
        session,
    )


def keys(allowed):
    def check(request: Request):
        seen = set()
        for key, _ in request.query_params.multi_items():
            if key not in allowed or key in seen:
                raise DomainError(422, "REQUEST_VALIDATION_ERROR", "Invalid query parameters.")
            seen.add(key)

    return check


Actor = Annotated[User, Depends(get_current_user)]
Service = Annotated[ReplenishmentService, Depends(service)]


@router.get("/status", response_model=ReplenishmentStatus, dependencies=[Depends(keys({"mode"}))])
def status(actor: Actor, repo: Service, mode: Literal["operational", "research"]):
    return repo.status(actor, mode)


@router.get(
    "/runs",
    response_model=Page[ReplenishmentRead],
    dependencies=[Depends(keys({"mode", "page", "page_size"}))],
)
def runs(
    actor: Actor,
    repo: Service,
    mode: Literal["operational", "research"],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return repo.list_runs(actor, mode, page, page_size)


@router.get("/runs/{run_id}", response_model=ReplenishmentRead, dependencies=[Depends(keys(set()))])
def detail(actor: Actor, repo: Service, run_id: str = Path(pattern=r"^rrv1-[0-9a-f]{64}$")):
    return repo._view(repo.get(actor, run_id), detail=True)


@router.get(
    "/runs/{run_id}/days",
    response_model=Page[SimulationDay],
    dependencies=[
        Depends(keys({"algorithm", "lead_time", "service", "policy", "page", "page_size"}))
    ],
)
def days(
    actor: Actor,
    repo: Service,
    run_id: str = Path(pattern=r"^rrv1-[0-9a-f]{64}$"),
    algorithm: Literal["persistence", "seasonal_naive", "xgboost"] = "xgboost",
    lead_time: int = Query(1, ge=1, le=7),
    service: Decimal = Decimal(".90"),
    policy: Literal["baseline", "proposed"] = "proposed",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    if (
        lead_time not in (1, 7)
        or not service.is_finite()
        or service not in (Decimal(".80"), Decimal(".90"), Decimal(".95"))
    ):
        raise DomainError(422, "REQUEST_VALIDATION_ERROR", "Invalid query parameters.")
    snapshot = repo.get(actor, run_id)
    repo._view(snapshot, detail=False)
    rows = snapshot["days"][(algorithm, lead_time, format(service, ".2f"), policy)]
    start = (page - 1) * page_size
    return {
        "items": list(rows[start : start + page_size]),
        "total": len(rows),
        "page": page,
        "page_size": page_size,
    }
