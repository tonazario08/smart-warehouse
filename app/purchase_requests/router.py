"""Additive current-role request APIs; parsing and retry errors stay local."""

import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.auth.dependencies import Permission, require_permission
from app.core.errors import DomainError, ErrorResponse
from app.core.pagination import Page, PageParams
from app.db.session import get_session
from app.models import User
from app.purchase_requests.repository import PurchaseRequestRepository
from app.purchase_requests.schemas import (
    PurchaseRequestAction,
    PurchaseRequestCreate,
    PurchaseRequestFilters,
    PurchaseRequestReject,
    PurchaseRequestResponse,
)
from app.purchase_requests.service import PurchaseRequestService

ERRORS = {code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 422)}
ERRORS[503] = {
    "model": ErrorResponse,
    "description": "Outcome may be uncertain. Retry the same identity/action.",
    "headers": {"Retry-After": {"schema": {"type": "integer", "const": 1}}},
}
router = APIRouter(prefix="/purchase-requests", tags=["purchase-requests"], responses=ERRORS)
ReadActor = Annotated[User, Depends(require_permission(Permission.PURCHASE_REQUEST_READ))]
CreateActor = Annotated[User, Depends(require_permission(Permission.PURCHASE_REQUEST_CREATE))]
ReviewActor = Annotated[User, Depends(require_permission(Permission.PURCHASE_REQUEST_REVIEW))]
FulfillActor = Annotated[User, Depends(require_permission(Permission.PURCHASE_REQUEST_FULFILL))]
Database = Annotated[object, Depends(get_session)]


def invalid(location: str, field: str):
    raise RequestValidationError(
        [{"loc": (location, field), "msg": "Invalid value.", "type": "value_error"}]
    )


def positive_integer(value: str, location: str, field: str) -> int:
    if len(value) > 10 or not re.fullmatch(r"[0-9]+", value) or not 1 <= int(value) <= 2147483647:
        invalid(location, field)
    return int(value)


def parse_uuid(value: str, location: str, field: str) -> UUID:
    try:
        return UUID(value)
    except (ValueError, TypeError, AttributeError):
        invalid(location, field)


def query_models(request: Request, actor: User):
    values = dict(request.query_params)
    for field in values:
        if len(request.query_params.getlist(field)) != 1:
            invalid("query", field)
    if actor.role == "client" and "requested_by_id" in values:
        invalid("query", "requested_by_id")
    paging = {
        field: positive_integer(values.pop(field), "query", field)
        for field in ("page", "page_size")
        if field in values
    }
    for field in ("warehouse_id", "product_id", "requested_by_id"):
        if field in values:
            values[field] = positive_integer(values[field], "query", field)
    try:
        return PurchaseRequestFilters.model_validate(values), PageParams(**paging)
    except ValidationError as error:
        raise RequestValidationError(
            [{**item, "loc": ("query", *item["loc"])} for item in error.errors()]
        ) from error


def service(session):
    return PurchaseRequestService(PurchaseRequestRepository(session))


def write_result(operation):
    try:
        return operation()
    except DomainError as error:
        if error.code != "PURCHASE_REQUEST_RETRY_REQUIRED":
            raise
        return JSONResponse(
            status_code=503,
            headers={"Retry-After": "1"},
            content={
                "detail": {"code": error.code, "message": error.message, "fields": error.fields}
            },
        )


@router.post(
    "",
    response_model=PurchaseRequestResponse,
    status_code=201,
    description="Client-owned creation without reservation. Same actor/key/normalized body returns "
    "200 with CURRENT persisted status/decision/fulfillment, never a cached pending snapshot. "
    "After uncertainty recover by the same creation key, "
    "or explicitly retry the exact same body/key.",
    openapi_extra={
        "parameters": [
            {
                "in": "header",
                "name": "Idempotency-Key",
                "required": True,
                "schema": {"type": "string", "format": "uuid"},
                "description": "Actor-owned creation UUID.",
            }
        ]
    },
    responses={
        200: {"model": PurchaseRequestResponse, "description": "Current-state create replay."},
        201: {
            "headers": {
                "Location": {"schema": {"type": "string"}, "description": "API detail URI."}
            }
        },
    },
)
def create_purchase_request(
    request: Request,
    body: PurchaseRequestCreate,
    actor: CreateActor,
    session: Database,
    response: Response,
):
    values = request.headers.getlist("Idempotency-Key")
    if len(values) != 1:
        invalid("header", "Idempotency-Key")
    key = parse_uuid(values[0], "header", "Idempotency-Key")
    result = write_result(lambda: service(session).create(actor, key, body))
    if isinstance(result, JSONResponse):
        return result
    row, replay = result
    response.status_code = 200 if replay else 201
    if not replay:
        response.headers["Location"] = request.url.path.rstrip("/") + f"/{row.id}"
    return row


@router.get(
    "",
    response_model=Page[PurchaseRequestResponse],
    description="Newest created_at/id first; inclusive aware ISO dates, conjunctive filters. "
    "Clients see only their own rows/counts and cannot submit requested_by_id.",
    openapi_extra={
        "parameters": [
            {"name": field, "in": "query", "required": False, "schema": schema}
            for field, schema in [
                (
                    "status",
                    {"type": "string", "enum": ["pending", "approved", "rejected", "fulfilled"]},
                ),
                *[
                    (field, {"type": "integer", "minimum": 1, "maximum": 2147483647})
                    for field in ("warehouse_id", "product_id", "requested_by_id", "page")
                ],
                ("page_size", {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}),
                *[
                    (field, {"type": "string", "format": "date-time"})
                    for field in ("created_from", "created_to")
                ],
            ]
        ]
    },
)
def list_purchase_requests(request: Request, actor: ReadActor, session: Database):
    filters, page = query_models(request, actor)
    items, total = service(session).list(actor, filters, page)
    return Page(items=items, total=total, page=page.page, page_size=page.page_size)


@router.get(
    "/by-key/{key}",
    response_model=PurchaseRequestResponse,
    description="Only the current actor's own creation key, never another client's key.",
)
def get_by_key(key: str, actor: ReadActor, session: Database):
    return service(session).get_by_key(actor, parse_uuid(key, "path", "key"))


@router.get(
    "/{request_id}",
    response_model=PurchaseRequestResponse,
    description="Client owner or staff; nonexistent and other-client IDs return the same404.",
)
def get_purchase_request(request_id: str, actor: ReadActor, session: Database):
    return service(session).get(actor, positive_integer(request_id, "path", "request_id"))


@router.post(
    "/{request_id}/approve",
    response_model=PurchaseRequestResponse,
    description="Admin decision only; no reservation. "
    "Repeated approval preserves original decision.",
)
def approve(request_id: str, body: PurchaseRequestAction, actor: ReviewActor, session: Database):
    return write_result(
        lambda: service(session).approve(actor, positive_integer(request_id, "path", "request_id"))
    )


@router.post(
    "/{request_id}/reject",
    response_model=PurchaseRequestResponse,
    description="Admin rejects pending; replay only with identical normalized reason.",
)
def reject(request_id: str, body: PurchaseRequestReject, actor: ReviewActor, session: Database):
    return write_result(
        lambda: service(session).reject(
            actor, positive_integer(request_id, "path", "request_id"), body
        )
    )


@router.post(
    "/{request_id}/fulfill",
    response_model=PurchaseRequestResponse,
    description="Admin/warehouse explicitly exports approved quantity once. Recover by GET detail "
    "and retry the same request ID, never a fresh standalone outbound.",
)
def fulfill(request_id: str, body: PurchaseRequestAction, actor: FulfillActor, session: Database):
    return write_result(
        lambda: service(session).fulfill(actor, positive_integer(request_id, "path", "request_id"))
    )
