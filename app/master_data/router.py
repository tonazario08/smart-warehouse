"""Authenticated category routes and master-data route composition."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import Permission, require_permission
from app.core.pagination import Page, PageParams
from app.db.session import get_session
from app.master_data._legacy_router import router as legacy_router
from app.master_data.repository import CategoryRepository
from app.master_data.schemas import CategoryCreate, CategoryResponse, CategoryUpdate
from app.master_data.service import CategoryService
from app.models import Category, User

router = APIRouter(tags=["master-data"])


def _category_service(session: Session) -> CategoryService:
    return CategoryService(session, CategoryRepository(session))


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


router.include_router(legacy_router)
