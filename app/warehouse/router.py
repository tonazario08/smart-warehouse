"""Authenticated warehouse API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.auth.dependencies import Permission, require_permission
from app.core.pagination import Page, PageParams
from app.db.session import get_session
from app.models import User, Warehouse
from app.warehouse.repository import WarehouseRepository
from app.warehouse.schemas import WarehouseResponse, WarehouseWrite
from app.warehouse.service import WarehouseService

router = APIRouter(prefix="/warehouses", tags=["warehouses"])


def _warehouse_service(session: object) -> WarehouseService:
    return WarehouseService(session, WarehouseRepository(session))


@router.get("", response_model=Page[WarehouseResponse])
def list_warehouses(
    params: Annotated[PageParams, Depends()],
    session: Annotated[object, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.WAREHOUSE_READ))],
    search: Annotated[str | None, Query()] = None,
) -> Page[Warehouse]:
    return _warehouse_service(session).list(params, search)


@router.get("/{warehouse_id}", response_model=WarehouseResponse)
def get_warehouse(
    warehouse_id: int,
    session: Annotated[object, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.WAREHOUSE_READ))],
) -> Warehouse:
    return _warehouse_service(session).get(warehouse_id)


@router.post("", response_model=WarehouseResponse, status_code=status.HTTP_201_CREATED)
def create_warehouse(
    request: WarehouseWrite,
    session: Annotated[object, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.WAREHOUSE_WRITE))],
) -> Warehouse:
    return _warehouse_service(session).create(request)


@router.put("/{warehouse_id}", response_model=WarehouseResponse)
def update_warehouse(
    warehouse_id: int,
    request: WarehouseWrite,
    session: Annotated[object, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.WAREHOUSE_WRITE))],
) -> Warehouse:
    return _warehouse_service(session).update(warehouse_id, request)


@router.delete("/{warehouse_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_warehouse(
    warehouse_id: int,
    session: Annotated[object, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.WAREHOUSE_WRITE))],
) -> Response:
    _warehouse_service(session).delete(warehouse_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
