"""Five authorized, read-only GIS endpoints."""

import re
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, Request
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from app.auth.dependencies import Permission, require_permission
from app.core.config import Settings, get_settings
from app.core.errors import DomainError, ErrorResponse
from app.db.session import get_session
from app.gis.repository import GISRepository
from app.gis.service import (
    GISService,
    Heatmap,
    PolicyContext,
    RouteInput,
    RouteRead,
    SnapshotStatus,
    WarehouseOptions,
    WarehouseOptionsInput,
)
from app.inventory.schemas import MAX_STOCK_QUANTITY
from app.models import User

router = APIRouter(
    prefix="/gis",
    tags=["gis"],
    responses={code: {"model": ErrorResponse} for code in (401, 403, 404, 422)},
)
ReadActor = Annotated[User, Depends(require_permission(Permission.GIS_READ))]
RouteActor = Annotated[User, Depends(require_permission(Permission.GIS_ROUTE))]


def get_gis_service(
    request: Request,
    session: Annotated[object, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> GISService:
    return GISService(GISRepository(session), request.app.state.gis_catalog, settings)


Service = Annotated[GISService, Depends(get_gis_service)]


def _parse_id(value: str) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,10}", value):
        raise ValueError("invalid ID")
    return int(value)


def _parse_date(value: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("invalid date")
    return date.fromisoformat(value)


type QueryId = Annotated[int, BeforeValidator(_parse_id), Field(ge=1, le=MAX_STOCK_QUANTITY)]
type QueryDate = Annotated[date, BeforeValidator(_parse_date)]


class _Query(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HeatmapQuery(_Query):
    product_id: QueryId
    start_date: QueryDate
    end_date: QueryDate


class PolicyQuery(_Query):
    run_id: str = Field(pattern=r"^rrv1-[0-9a-f]{64}$")
    product_id: QueryId
    warehouse_id: QueryId


def _reject_ambiguous_query(request: Request, *, empty: bool = False) -> None:
    query = request.query_params
    if (empty and query) or len(query) != len(query.multi_items()):
        raise DomainError(422, "REQUEST_VALIDATION_ERROR", "Invalid query parameters.")


@router.get("/status", response_model=SnapshotStatus)
def status(request: Request, actor: ReadActor, service: Service) -> SnapshotStatus:
    _reject_ambiguous_query(request, empty=True)
    return service.status()


@router.post("/warehouse-options", response_model=WarehouseOptions)
def warehouse_options(
    request: Request, body: WarehouseOptionsInput, actor: RouteActor, service: Service
) -> WarehouseOptions:
    _reject_ambiguous_query(request, empty=True)
    return service.warehouse_options(actor, body)


@router.post("/route", response_model=RouteRead)
def route(
    request: Request, body: Annotated[RouteInput, Body()], actor: RouteActor, service: Service
) -> RouteRead:
    _reject_ambiguous_query(request, empty=True)
    return service.route(actor, body)


@router.get("/heatmap", response_model=Heatmap)
def heatmap(
    request: Request, query: Annotated[HeatmapQuery, Query()], actor: ReadActor, service: Service
) -> Heatmap:
    _reject_ambiguous_query(request)
    return service.heatmap(query.product_id, query.start_date, query.end_date)


@router.get("/policy-context", response_model=PolicyContext)
def policy_context(
    request: Request, query: Annotated[PolicyQuery, Query()], actor: ReadActor, service: Service
) -> PolicyContext:
    _reject_ambiguous_query(request)
    return service.policy_context(actor, query.run_id, query.product_id, query.warehouse_id)
