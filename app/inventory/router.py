from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.auth.dependencies import Permission, require_permission
from app.core.pagination import Page, PageParams
from app.db.session import get_session
from app.inventory.repository import InventoryRepository
from app.inventory.schemas import (
    InventoryFilters,
    InventoryMovementCreate,
    InventoryMovementReadResponse,
    InventoryMovementResponse,
    StockResponse,
    TransactionFilters,
    TransactionResponse,
)
from app.inventory.service import InventoryService
from app.models import (
    Inbound,
    Outbound,
    Stock,
    StockTransaction,
    User,
)

router = APIRouter(tags=["inventory"])


def get_page_params(request: Request) -> PageParams:
    """Validate pagination query fields and report errors through the API contract."""
    try:
        return PageParams(
            page=request.query_params.get("page", 1),
            page_size=request.query_params.get("page_size", 20),
        )
    except ValidationError as error:
        raise RequestValidationError(
            [{**item, "loc": ("query", *item["loc"])} for item in error.errors()]
        ) from error


def get_inventory_filters(request: Request) -> InventoryFilters:
    """Validate strict inventory filters from query parameters."""
    values = dict(request.query_params)
    values.pop("page", None)
    values.pop("page_size", None)
    try:
        return InventoryFilters.model_validate(values)
    except ValidationError as error:
        raise RequestValidationError(
            [{**item, "loc": ("query", *item["loc"])} for item in error.errors()]
        ) from error


def get_transaction_filters(request: Request) -> TransactionFilters:
    """Validate strict inventory history filters from query parameters."""
    values = dict(request.query_params)
    values.pop("page", None)
    values.pop("page_size", None)
    try:
        return TransactionFilters.model_validate(values)
    except ValidationError as error:
        raise RequestValidationError(
            [{**item, "loc": ("query", *item["loc"])} for item in error.errors()]
        ) from error


@router.get("/stock", response_model=Page[StockResponse])
def list_stock(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.INVENTORY_READ))],
    page: Annotated[PageParams, Depends(get_page_params)],
    filters: Annotated[InventoryFilters, Depends(get_inventory_filters)],
) -> Page[StockResponse]:
    items, total = InventoryService(InventoryRepository(session)).list_stock(filters, page)
    return Page(items=items, total=total, page=page.page, page_size=page.page_size)


@router.get("/stock/{stock_id}", response_model=StockResponse)
def get_stock(
    stock_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.INVENTORY_READ))],
) -> Stock:
    return InventoryService(InventoryRepository(session)).get_stock(stock_id)


@router.get("/inbounds", response_model=Page[InventoryMovementReadResponse])
def list_inbounds(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.INVENTORY_HISTORY_READ))],
    page: Annotated[PageParams, Depends(get_page_params)],
    filters: Annotated[InventoryFilters, Depends(get_inventory_filters)],
) -> Page[InventoryMovementReadResponse]:
    items, total = InventoryService(InventoryRepository(session)).list_inbounds(filters, page)
    return Page(items=items, total=total, page=page.page, page_size=page.page_size)


@router.get("/inbounds/{inbound_id}", response_model=InventoryMovementReadResponse)
def get_inbound(
    inbound_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.INVENTORY_HISTORY_READ))],
) -> Inbound:
    return InventoryService(InventoryRepository(session)).get_inbound(inbound_id)


@router.post(
    "/inbounds", response_model=InventoryMovementResponse, status_code=status.HTTP_201_CREATED
)
def create_inbound(
    movement: InventoryMovementCreate,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_permission(Permission.INVENTORY_WRITE))],
) -> Inbound:
    return InventoryService(InventoryRepository(session)).create_inbound(user.id, movement)


@router.get("/outbounds", response_model=Page[InventoryMovementReadResponse])
def list_outbounds(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.INVENTORY_HISTORY_READ))],
    page: Annotated[PageParams, Depends(get_page_params)],
    filters: Annotated[InventoryFilters, Depends(get_inventory_filters)],
) -> Page[InventoryMovementReadResponse]:
    items, total = InventoryService(InventoryRepository(session)).list_outbounds(filters, page)
    return Page(items=items, total=total, page=page.page, page_size=page.page_size)


@router.get("/outbounds/{outbound_id}", response_model=InventoryMovementReadResponse)
def get_outbound(
    outbound_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.INVENTORY_HISTORY_READ))],
) -> Outbound:
    return InventoryService(InventoryRepository(session)).get_outbound(outbound_id)


@router.post(
    "/outbounds", response_model=InventoryMovementResponse, status_code=status.HTTP_201_CREATED
)
def create_outbound(
    movement: InventoryMovementCreate,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_permission(Permission.INVENTORY_WRITE))],
) -> Outbound:
    return InventoryService(InventoryRepository(session)).create_outbound(user.id, movement)


@router.get("/transactions", response_model=Page[TransactionResponse])
def list_transactions(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.INVENTORY_HISTORY_READ))],
    page: Annotated[PageParams, Depends(get_page_params)],
    filters: Annotated[TransactionFilters, Depends(get_transaction_filters)],
) -> Page[TransactionResponse]:
    items, total = InventoryService(InventoryRepository(session)).list_transactions(filters, page)
    return Page(items=items, total=total, page=page.page, page_size=page.page_size)


@router.get("/transactions/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.INVENTORY_HISTORY_READ))],
) -> StockTransaction:
    return InventoryService(InventoryRepository(session)).get_transaction(transaction_id)
