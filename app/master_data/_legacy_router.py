"""Product routes pending their planned repository and service slice."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import Permission, require_permission
from app.db.session import get_session
from app.master_data.schemas import (
    Page,
    ProductCreate,
    ProductResponse,
)
from app.models import Category, Product, Supplier, User

router = APIRouter(tags=["master-data"])


def _page[T](session: Session, model: type[T], page: int, page_size: int) -> Page[T]:
    items = session.scalars(select(model).offset((page - 1) * page_size).limit(page_size)).all()
    total = session.scalar(select(func.count()).select_from(model)) or 0
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/products", response_model=Page[ProductResponse])
def list_products(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page:
    return _page(session, Product, page, page_size)


@router.get("/products/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, session: Annotated[Session, Depends(get_session)]) -> Product:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    request: ProductCreate,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.PRODUCT_WRITE))],
) -> Product:
    if session.get(Category, request.category_id) is None:
        raise HTTPException(status_code=422, detail="Category does not exist")
    if request.supplier_id is not None and session.get(Supplier, request.supplier_id) is None:
        raise HTTPException(status_code=422, detail="Supplier does not exist")
    product = Product(**request.model_dump())
    session.add(product)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Product SKU already exists") from error
    session.refresh(product)
    return product


@router.put("/products/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    request: ProductCreate,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.PRODUCT_WRITE))],
) -> Product:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    if session.get(Category, request.category_id) is None:
        raise HTTPException(status_code=422, detail="Category does not exist")
    if request.supplier_id is not None and session.get(Supplier, request.supplier_id) is None:
        raise HTTPException(status_code=422, detail="Supplier does not exist")
    for field, value in request.model_dump().items():
        setattr(product, field, value)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Product SKU already exists") from error
    session.refresh(product)
    return product


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.PRODUCT_WRITE))],
) -> None:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    try:
        session.delete(product)
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(
            status_code=409, detail="Product is referenced by inventory data"
        ) from error
