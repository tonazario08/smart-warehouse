"""Additive authorized transfer routes with operation-local retry responses."""

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
from app.transfers.repository import TransferRepository
from app.transfers.schemas import (
    MovementProvenanceResponse,
    ProvenanceFilters,
    TransferCreate,
    TransferFilters,
    TransferResponse,
)
from app.transfers.service import TransferService

router = APIRouter(tags=["transfers"])
WriteActor = Annotated[User, Depends(require_permission(Permission.INVENTORY_WRITE))]
ReadActor = Annotated[User, Depends(require_permission(Permission.INVENTORY_HISTORY_READ))]
Database = Annotated[object, Depends(get_session)]


def invalid(location: str, field: str) -> None:
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


def query_models(request: Request, filter_model):
    values = dict(request.query_params)
    for field in values:
        if len(request.query_params.getlist(field)) != 1:
            invalid("query", field)
    paging = {
        field: positive_integer(values.pop(field), "query", field)
        for field in ["page", "page_size"]
        if field in values
    }
    for field in filter_model.model_fields:
        if field.endswith("_id") and field in values:
            values[field] = positive_integer(values[field], "query", field)
    try:
        return filter_model.model_validate(values), PageParams(**paging)
    except ValidationError as error:
        raise RequestValidationError(
            [{**item, "loc": ("query", *item["loc"])} for item in error.errors()]
        ) from error


@router.post(
    "/transfers",
    response_model=TransferResponse,
    status_code=201,
    description="Create one immediate atomic transfer. The UUID is owned by the current actor. "
    "Same normalized body/key replays the original result with 200; a different body returns 409. "
    "After an uncertain result retry exactly the same body and key.",
    openapi_extra={
        "parameters": [
            {
                "in": "header",
                "name": "Idempotency-Key",
                "required": True,
                "schema": {"type": "string", "format": "uuid"},
                "description": "Actor-owned durable transfer UUID.",
            }
        ]
    },
    responses={
        200: {"model": TransferResponse, "description": "Authorized original-result replay."},
        503: {
            "model": ErrorResponse,
            "description": "Retry the exact same request; commit outcome may be unknown.",
            "headers": {"Retry-After": {"schema": {"type": "integer", "const": 1}}},
        },
    },
)
def create_transfer(
    request: Request, body: TransferCreate, actor: WriteActor, session: Database, response: Response
):
    values = request.headers.getlist("Idempotency-Key")
    if len(values) != 1:
        invalid("header", "Idempotency-Key")
    key = parse_uuid(values[0], "header", "Idempotency-Key")
    try:
        transfer, replay = TransferService(TransferRepository(session)).create(actor.id, key, body)
    except DomainError as error:
        if error.code != "TRANSFER_RETRY_REQUIRED":
            raise
        return JSONResponse(
            status_code=503,
            headers={"Retry-After": "1"},
            content={
                "detail": {
                    "code": error.code,
                    "message": error.message,
                    "fields": error.fields,
                }
            },
        )
    response.status_code = 200 if replay else 201
    return transfer


@router.get("/transfers", response_model=Page[TransferResponse])
def list_transfers(request: Request, actor: ReadActor, session: Database):
    filters, page = query_models(request, TransferFilters)
    items, total = TransferService(TransferRepository(session)).list(filters, page)
    return Page(items=items, total=total, page=page.page, page_size=page.page_size)


@router.get("/transfers/by-key/{key}", response_model=TransferResponse)
def get_own_key(key: str, actor: ReadActor, session: Database):
    return TransferService(TransferRepository(session)).get_by_key(
        actor.id, parse_uuid(key, "path", "key")
    )


@router.get("/transfers/{transfer_id}", response_model=TransferResponse)
def get_transfer(transfer_id: str, actor: ReadActor, session: Database):
    return TransferService(TransferRepository(session)).get(
        positive_integer(transfer_id, "path", "transfer_id")
    )


@router.get("/movement-provenance", response_model=Page[MovementProvenanceResponse])
def list_provenance(request: Request, actor: ReadActor, session: Database):
    filters, page = query_models(request, ProvenanceFilters)
    items, total = TransferService(TransferRepository(session)).list_provenance(filters, page)
    return Page(items=items, total=total, page=page.page, page_size=page.page_size)
