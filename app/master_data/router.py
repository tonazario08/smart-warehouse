"""Authenticated category routes and master-data route composition."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import Permission, require_permission
from app.core.pagination import Page, PageParams
from app.db.session import get_session
from app.master_data._legacy_router import router as legacy_router
from app.master_data.repository import CategoryRepository, SupplierRepository
from app.master_data.schemas import (
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    SupplierCreate,
    SupplierResponse,
    SupplierUpdate,
)
from app.master_data.service import CategoryService, SupplierService
from app.models import Category, Supplier, User

router = APIRouter(tags=["master-data"])


def _category_service(session: Session) -> CategoryService:
    return CategoryService(session, CategoryRepository(session))


def _supplier_service(session: Session) -> SupplierService:
    return SupplierService(session, SupplierRepository(session))


@router.get("/categories", response_model=Page[CategoryResponse])
def list_categories(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.CATALOG_READ))],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[CategoryResponse]:
    return _category_service(session).list(PageParams(page=page, page_size=page_size))


@router.get("/categories/{category_id}", response_model=CategoryResponse)
def get_category(
    category_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.CATALOG_READ))],
) -> Category:
    return _category_service(session).get(category_id)


@router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    request: CategoryCreate,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.PRODUCT_WRITE))],
) -> Category:
    return _category_service(session).create(request)


@router.put("/categories/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    request: CategoryUpdate,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.PRODUCT_WRITE))],
) -> Category:
    return _category_service(session).update(category_id, request)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.PRODUCT_WRITE))],
) -> None:
    _category_service(session).delete(category_id)


@router.get("/suppliers", response_model=Page[SupplierResponse])
def list_suppliers(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.SUPPLIER_READ))],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=320)] = None,
) -> Page[SupplierResponse]:
    params = PageParams(page=page, page_size=page_size)
    return _supplier_service(session).list(params, search)


@router.get("/suppliers/{supplier_id}", response_model=SupplierResponse)
def get_supplier(
    supplier_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.SUPPLIER_READ))],
) -> Supplier:
    return _supplier_service(session).get(supplier_id)


@router.post(
    "/suppliers",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_supplier(
    request: SupplierCreate,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.SUPPLIER_WRITE))],
) -> Supplier:
    return _supplier_service(session).create(request)


@router.put("/suppliers/{supplier_id}", response_model=SupplierResponse)
def update_supplier(
    supplier_id: int,
    request: SupplierUpdate,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.SUPPLIER_WRITE))],
) -> Supplier:
    return _supplier_service(session).update(supplier_id, request)


@router.delete("/suppliers/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier(
    supplier_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.SUPPLIER_WRITE))],
) -> None:
    _supplier_service(session).delete(supplier_id)


router.include_router(legacy_router)
