"""Permission-scoped, read-only access to provisional order analytics."""

import re
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request

from app.auth.dependencies import Permission, require_permission
from app.core.config import Settings, get_settings
from app.core.errors import DomainError
from app.core.pagination import Page
from app.db.session import get_session
from app.models import User
from app.order_analytics.repository import (
    get_key_state,
    get_latest_job,
    has_pending_job,
    query_order_checks,
    read_position,
)
from app.order_analytics.schemas import OpenDemandRead, OrderCheckRead, ReplenishmentPositionRead
from app.order_analytics.service import matching_replenishment, replenishment_reference
from app.purchase_requests.router import invalid, positive_integer, single_query_params
from app.replenishment.repository import ReplenishmentRepository

router = APIRouter(prefix="/order-analytics", tags=["order-analytics"])
Database = Annotated[object, Depends(get_session)]
Config = Annotated[Settings, Depends(get_settings)]
ForecastReader = Annotated[User, Depends(require_permission(Permission.FORECAST_READ))]
ReplenishmentReader = Annotated[User, Depends(require_permission(Permission.REPLENISHMENT_READ))]
AnomalyReader = Annotated[User, Depends(require_permission(Permission.ANOMALY_READ))]


def _queries(request, allowed):
    single_query_params(request)
    for key in request.query_params:
        if key not in allowed:
            invalid("query", key)


def _positive(request, key):
    return positive_integer(request.query_params[key], "query", key)


def _position(request, session):
    w = _positive(request, "warehouse_id")
    p = _positive(request, "product_id")
    position = read_position(session, w, p)
    if position is None:
        raise DomainError(404, "ORDER_ANALYTICS_KEY_NOT_FOUND", "Product or warehouse not found.")
    return position


def _identity(position):
    return {
        "warehouse_id": position.warehouse_id,
        "product_id": position.product_id,
        "sku": position.sku,
        "unit": position.unit,
    }


def _job_context(session, warehouse_id, product_id):
    return (
        has_pending_job(session, warehouse_id, product_id),
        get_latest_job(session, warehouse_id, product_id),
        get_key_state(session, warehouse_id, product_id),
    )


@router.get("/open-demand", response_model=OpenDemandRead)
def open_demand(
    request: Request, _: ForecastReader, session: Database, warehouse_id: str, product_id: str
):
    _queries(request, {"warehouse_id", "product_id"})
    position = _position(request, session)
    pending, job, state = _job_context(session, position.warehouse_id, position.product_id)
    data = _identity(position)
    if pending:
        return OpenDemandRead(**data, state="computing")
    if state and state.forecast_status == "failed":
        return OpenDemandRead(
            **data,
            state="failed",
            reason_code=state.forecast_reason_code,
            computed_at=state.computed_at,
        )
    if (
        job
        and job.status == "failed"
        and (
            state is None
            or state.forecast_status is None
            or job.last_error_code == "FORECAST_CONTEXT_FAILED"
        )
    ):
        return OpenDemandRead(**data, state="failed", reason_code=job.last_error_code)
    if state is None or state.forecast_status != "available":
        return OpenDemandRead(
            **data,
            state="insufficient_data",
            reason_code="BASELINE_NOT_FOUND",
            computed_at=state.computed_at if state else None,
        )
    return OpenDemandRead(
        **data,
        state="available",
        computed_at=state.computed_at,
        forecast_run_id=state.forecast_run_id,
        forecast_dataset_class=state.forecast_dataset_class,
        forecast_stale=state.forecast_stale,
        pending_quantity=position.pending_quantity,
        approved_quantity=position.approved_quantity,
        open_quantity=position.total_quantity,
        order_count=position.order_count,
    )


@router.get("/replenishment-position", response_model=ReplenishmentPositionRead)
def replenishment_position(
    request: Request,
    _: ReplenishmentReader,
    session: Database,
    settings: Config,
    warehouse_id: str,
    product_id: str,
    view: Literal["operational", "demo"] = "operational",
    algorithm: Literal["persistence", "seasonal_naive", "xgboost"] = "xgboost",
    lead_time: int = 1,
    service: Decimal = Decimal(".90"),
    policy: Literal["baseline", "proposed"] = "proposed",
    reference_date: date | None = None,
    run_id: str | None = None,
):
    _queries(
        request,
        {
            "warehouse_id",
            "product_id",
            "view",
            "algorithm",
            "lead_time",
            "service",
            "policy",
            "reference_date",
            "run_id",
        },
    )
    if run_id is not None and (view != "demo" or not re.fullmatch(r"rrv1-[0-9a-f]{64}", run_id)):
        invalid("query", "run_id")
    if lead_time not in {1, 7}:
        invalid("query", "lead_time")
    if service not in {Decimal(".80"), Decimal(".90"), Decimal(".95")}:
        invalid("query", "service")
    position = _position(request, session)
    pending, job, state = _job_context(session, position.warehouse_id, position.product_id)
    data = dict(
        _identity(position),
        on_hand=position.on_hand,
        open_quantity=position.total_quantity,
        projected_quantity=position.projected_quantity,
    )
    if pending:
        return ReplenishmentPositionRead(**data, state="computing")
    if position.on_hand is None:
        return ReplenishmentPositionRead(
            **data,
            state="insufficient_data",
            reason_code="STOCK_ROW_MISSING",
            computed_at=state.computed_at if state else None,
        )
    if state and state.replenishment_status == "failed":
        return ReplenishmentPositionRead(
            **data,
            state="failed",
            reason_code=state.replenishment_reason_code,
            computed_at=state.computed_at,
        )
    if (
        job
        and job.status == "failed"
        and (
            state is None
            or state.replenishment_status is None
            or job.last_error_code == "REPLENISHMENT_CONTEXT_FAILED"
        )
    ):
        return ReplenishmentPositionRead(**data, state="failed", reason_code=job.last_error_code)
    demo = view == "demo"
    if run_id is None and state is not None:
        run_id = state.replenishment_demo_run_id if demo else state.replenishment_run_id
    if run_id and settings.replenishment_catalog_root is not None:
        repository = ReplenishmentRepository(
            settings.replenishment_catalog_root, allow_fixture=settings.replenishment_allow_fixture
        )
        try:
            snapshot = repository.scoped(run_id, ("operational",))
            reference = (
                replenishment_reference(
                    snapshot,
                    algorithm=algorithm,
                    lead_time=lead_time,
                    service=service,
                    policy=policy,
                    reference_date=reference_date,
                )
                if snapshot
                and matching_replenishment(
                    snapshot, position.warehouse_id, position.product_id, position.unit, demo=demo
                )
                else None
            )
        except (ValueError, OSError):
            return ReplenishmentPositionRead(
                **data, state="failed", reason_code="REPLENISHMENT_CATALOG_INVALID"
            )
        if reference is not None:
            rop, day, eoq = reference
            return ReplenishmentPositionRead(
                **data,
                state="available",
                recommendation=not demo and position.projected_quantity <= rop,
                computed_at=state.computed_at if state else None,
                rop=rop,
                rop_date=day,
                eoq=eoq,
                run_id=run_id,
                dataset_class=snapshot["manifest"]["dataset_class"],
            )
    return ReplenishmentPositionRead(
        **data,
        state="insufficient_data",
        reason_code="DEMO_ROP_NOT_FOUND" if demo else "OPERATIONAL_ROP_NOT_FOUND",
        computed_at=state.computed_at if state else None,
    )


@router.get("/order-checks", response_model=Page[OrderCheckRead])
def order_checks(
    request: Request,
    _: AnomalyReader,
    session: Database,
    purchase_request_id: str | None = None,
    warehouse_id: str | None = None,
    product_id: str | None = None,
    page: str = "1",
    page_size: str = "20",
):
    _queries(request, {"purchase_request_id", "warehouse_id", "product_id", "page", "page_size"})
    if purchase_request_id is not None:
        if warehouse_id is not None or product_id is not None:
            invalid("query", "purchase_request_id")
        request_id, w, p = _positive(request, "purchase_request_id"), None, None
    else:
        if warehouse_id is None:
            invalid("query", "warehouse_id")
        if product_id is None:
            invalid("query", "product_id")
        request_id, w, p = (
            None,
            _positive(request, "warehouse_id"),
            _positive(request, "product_id"),
        )
    number = positive_integer(page, "query", "page")
    size = positive_integer(page_size, "query", "page_size")
    if size > 100:
        invalid("query", "page_size")
    rows, total = query_order_checks(
        session,
        purchase_request_id=request_id,
        warehouse_id=w,
        product_id=p,
        page=number,
        page_size=size,
    )
    items = []
    for order, job, check in rows:
        identity = {
            "purchase_request_id": order.id,
            "warehouse_id": order.warehouse_id,
            "product_id": order.product_id,
        }
        if job.status in {"queued", "running"}:
            items.append(OrderCheckRead(**identity, state="computing"))
        elif check is None:
            items.append(
                OrderCheckRead(**identity, state="failed", reason_code=job.last_error_code)
            )
        else:
            items.append(
                OrderCheckRead(
                    **identity,
                    state=check.status,
                    **{
                        f: getattr(check, f)
                        for f in (
                            "reason_code",
                            "computed_at",
                            "flagged",
                            "rule_id",
                            "rule_version",
                            "sample_count",
                            "median",
                            "mad",
                            "score",
                            "label",
                        )
                    },
                )
            )
    return Page(items=items, total=total, page=number, page_size=size)
