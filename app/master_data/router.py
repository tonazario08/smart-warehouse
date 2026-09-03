from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import Permission, require_permission
from app.db.session import get_session
from app.master_data.schemas import (
    CategoryCreate,
    CategoryResponse,
    Page,
    ProductCreate,
    ProductResponse,
    SupplierCreate,
    SupplierResponse,
)
from app.models import Category, Product, Supplier, User

router = APIRouter(tags=["master-data"])


def _page[T](session: Session, model: type[T], page: int, page_size: int) -> Page[T]:
    items = session.scalars(select(model).offset((page - 1) * page_size).limit(page_size)).all()
    total = session.scalar(select(func.count()).select_from(model)) or 0
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/categories", response_model=Page[CategoryResponse])
def list_categories(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page:
    return _page(session, Category, page, page_size)


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
    if request.parent_id is not None and session.get(Category, request.parent_id) is None:
        raise HTTPException(status_code=422, detail="Parent category does not exist")
    category = Category(**request.model_dump())
    session.add(category)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Category already exists") from error
    session.refresh(category)
    return category


@router.put("/categories/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    request: CategoryCreate,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.PRODUCT_WRITE))],
) -> Category:
    category = session.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    if request.parent_id == category_id:
        raise HTTPException(status_code=422, detail="Category cannot be its own parent")
    if request.parent_id is not None and session.get(Category, request.parent_id) is None:
        raise HTTPException(status_code=422, detail="Parent category does not exist")
    category.name = request.name
    category.parent_id = request.parent_id
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Category already exists") from error
    session.refresh(category)
    return category


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.PRODUCT_WRITE))],
) -> None:
    category = session.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    try:
        session.delete(category)
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Category is still referenced") from error


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


@router.get("/suppliers", response_model=Page[SupplierResponse])
def list_suppliers(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    _: Annotated[User, Depends(require_permission(Permission.SUPPLIER_READ))] = None,
) -> Page:
    return _page(session, Supplier, page, page_size)


@router.get("/suppliers/{supplier_id}", response_model=SupplierResponse)
def get_supplier(
    supplier_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.SUPPLIER_READ))],
) -> Supplier:
    supplier = session.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@router.post("/suppliers", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
def create_supplier(
    request: SupplierCreate,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.PRODUCT_WRITE))],
) -> Supplier:
    supplier = Supplier(**request.model_dump())
    session.add(supplier)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Supplier already exists") from error
    session.refresh(supplier)
    return supplier


@router.put("/suppliers/{supplier_id}", response_model=SupplierResponse)
def update_supplier(
    supplier_id: int,
    request: SupplierCreate,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.PRODUCT_WRITE))],
) -> Supplier:
    supplier = session.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    for field, value in request.model_dump().items():
        setattr(supplier, field, value)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Supplier already exists") from error
    session.refresh(supplier)
    return supplier


@router.delete("/suppliers/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier(
    supplier_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.PRODUCT_WRITE))],
) -> None:
    supplier = session.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    try:
        session.delete(supplier)
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Supplier is still referenced") from error
