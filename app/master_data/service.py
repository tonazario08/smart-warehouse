"""Category use cases and transaction ownership."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.core.pagination import Page, PageParams
from app.master_data.repository import (
    CategoryRepository,
    ProductRepository,
    SupplierRepository,
)
from app.master_data.schemas import (
    CategoryCreate,
    CategoryUpdate,
    ProductCreate,
    ProductUpdate,
    SupplierCreate,
    SupplierUpdate,
)
from app.models import Category, Product, Supplier


def _constraint_name(error: IntegrityError) -> str | None:
    original = error.orig
    return getattr(getattr(original, "diag", None), "constraint_name", None)


class CategoryService:
    """Apply category business rules and commit or roll back each mutation."""

    def __init__(self, session: Session, categories: CategoryRepository) -> None:
        self.session = session
        self.categories = categories

    def list(self, params: PageParams) -> Page[Category]:
        return Page[Category](
            items=self.categories.list(params),
            total=self.categories.count(),
            page=params.page,
            page_size=params.page_size,
        )

    def get(self, category_id: int) -> Category:
        category = self.categories.get(category_id)
        if category is None:
            raise DomainError(404, "CATEGORY_NOT_FOUND", "Category was not found.")
        return category

    def create(self, request: CategoryCreate) -> Category:
        self._validate_parent(request.parent_id)
        category = Category(name=request.name.strip(), parent_id=request.parent_id)
        try:
            self.categories.add(category)
            self.session.commit()
            self.session.refresh(category)
            return category
        except IntegrityError as error:
            self.session.rollback()
            self._raise_integrity_error(error)
            raise
        except Exception:
            self.session.rollback()
            raise

    def update(self, category_id: int, request: CategoryUpdate) -> Category:
        category = self.get(category_id)
        self._validate_parent(request.parent_id)
        self._validate_parent_cycle(category.id, request.parent_id)
        self.categories.update(category, request.name.strip(), request.parent_id)
        return self._commit_or_conflict(category)

    def delete(self, category_id: int) -> None:
        category = self.get(category_id)
        try:
            self.categories.delete(category)
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise DomainError(
                409,
                "CATEGORY_IN_USE",
                "Category is referenced by another record.",
            ) from error
        except Exception:
            self.session.rollback()
            raise

    def _validate_parent(self, parent_id: int | None) -> None:
        if parent_id is not None and self.categories.get(parent_id) is None:
            raise DomainError(422, "CATEGORY_NOT_FOUND", "Parent category does not exist.")

    def _validate_parent_cycle(self, category_id: int, parent_id: int | None) -> None:
        cursor = self.categories.get(parent_id) if parent_id is not None else None
        visited: set[int] = set()
        while cursor is not None:
            if cursor.id == category_id or cursor.id in visited:
                raise DomainError(
                    422,
                    "CATEGORY_PARENT_CYCLE",
                    "Category hierarchy contains a cycle.",
                )
            visited.add(cursor.id)
            cursor = (
                self.categories.get(cursor.parent_id) if cursor.parent_id is not None else None
            )

    def _commit_or_conflict(self, category: Category) -> Category:
        try:
            self.session.commit()
            self.session.refresh(category)
            return category
        except IntegrityError as error:
            self.session.rollback()
            self._raise_integrity_error(error)
            raise
        except Exception:
            self.session.rollback()
            raise

    @staticmethod
    def _raise_integrity_error(error: IntegrityError) -> None:
        if _constraint_name(error) == "categories_name_key":
            raise DomainError(
                409,
                "CATEGORY_NAME_CONFLICT",
                "Category name already exists.",
            ) from error


class SupplierService:
    """Apply supplier business rules and own supplier transactions."""

    def __init__(self, session: Session, suppliers: SupplierRepository) -> None:
        self.session = session
        self.suppliers = suppliers

    def list(self, params: PageParams, search: str | None = None) -> Page[Supplier]:
        return Page[Supplier](
            items=self.suppliers.list(params, search),
            total=self.suppliers.count(search),
            page=params.page,
            page_size=params.page_size,
        )

    def get(self, supplier_id: int) -> Supplier:
        supplier = self.suppliers.get(supplier_id)
        if supplier is None:
            raise DomainError(404, "SUPPLIER_NOT_FOUND", "Supplier was not found.")
        return supplier

    def create(self, request: SupplierCreate) -> Supplier:
        supplier = Supplier(**request.model_dump())
        try:
            self.suppliers.add(supplier)
            self.session.commit()
            self.session.refresh(supplier)
            return supplier
        except IntegrityError as error:
            self.session.rollback()
            raise DomainError(
                409, "SUPPLIER_CONFLICT", "Supplier already exists."
            ) from error
        except Exception:
            self.session.rollback()
            raise

    def update(self, supplier_id: int, request: SupplierUpdate) -> Supplier:
        supplier = self.get(supplier_id)
        self.suppliers.update(
            supplier,
            name=request.name,
            email=request.email,
            phone=request.phone,
            address=request.address,
        )
        return self._commit_or_conflict(supplier)

    def delete(self, supplier_id: int) -> None:
        supplier = self.get(supplier_id)
        if self.suppliers.has_products(supplier_id):
            raise DomainError(
                409,
                "SUPPLIER_IN_USE",
                "Supplier is referenced by another record.",
            )
        try:
            self.suppliers.delete(supplier)
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise DomainError(
                409,
                "SUPPLIER_IN_USE",
                "Supplier is referenced by another record.",
            ) from error
        except Exception:
            self.session.rollback()
            raise

    def _commit_or_conflict(self, supplier: Supplier) -> Supplier:
        try:
            self.session.commit()
            self.session.refresh(supplier)
            return supplier
        except IntegrityError as error:
            self.session.rollback()
            raise DomainError(
                409, "SUPPLIER_CONFLICT", "Supplier already exists."
            ) from error
        except Exception:
            self.session.rollback()
            raise


class ProductService:
    """Apply product business rules and own product transactions."""

    def __init__(
        self,
        session: Session,
        products: ProductRepository,
        categories: CategoryRepository,
        suppliers: SupplierRepository,
    ) -> None:
        self.session = session
        self.products = products
        self.categories = categories
        self.suppliers = suppliers

    def list(
        self,
        params: PageParams,
        *,
        search: str | None = None,
        category_id: int | None = None,
        supplier_id: int | None = None,
        is_active: bool | None = None,
    ) -> Page[Product]:
        filters = {
            "search": search,
            "category_id": category_id,
            "supplier_id": supplier_id,
            "is_active": is_active,
        }
        return Page[Product](
            items=self.products.list(params, **filters),
            total=self.products.count(**filters),
            page=params.page,
            page_size=params.page_size,
        )

    def get(self, product_id: int) -> Product:
        product = self.products.get(product_id)
        if product is None:
            raise DomainError(404, "PRODUCT_NOT_FOUND", "Product was not found.")
        return product

    def create(self, request: ProductCreate) -> Product:
        values = request.model_dump()
        self._validate_references(values["category_id"], values["supplier_id"])
        product = Product(**values)
        try:
            self.products.add(product)
            self.session.commit()
            self.session.refresh(product)
            return product
        except IntegrityError as error:
            self.session.rollback()
            self._raise_integrity_error(error)
            raise
        except Exception:
            self.session.rollback()
            raise

    def update(self, product_id: int, request: ProductUpdate) -> Product:
        product = self.get(product_id)
        values = request.model_dump()
        self._validate_references(values["category_id"], values["supplier_id"])
        self.products.update(product, values)
        return self._commit_or_conflict(product)

    def delete(self, product_id: int) -> None:
        product = self.get(product_id)
        if self.products.has_references(product_id):
            raise DomainError(409, "PRODUCT_IN_USE", "Product is referenced by other records.")
        try:
            self.products.delete(product)
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise DomainError(
                409, "PRODUCT_IN_USE", "Product is referenced by other records."
            ) from error
        except Exception:
            self.session.rollback()
            raise

    def _validate_references(self, category_id: int, supplier_id: int | None) -> None:
        if self.categories.get(category_id) is None:
            raise DomainError(422, "CATEGORY_NOT_FOUND", "Category does not exist.")
        if supplier_id is not None and self.suppliers.get(supplier_id) is None:
            raise DomainError(422, "SUPPLIER_NOT_FOUND", "Supplier does not exist.")

    def _commit_or_conflict(self, product: Product) -> Product:
        try:
            self.session.commit()
            self.session.refresh(product)
            return product
        except IntegrityError as error:
            self.session.rollback()
            self._raise_integrity_error(error)
            raise
        except Exception:
            self.session.rollback()
            raise

    @staticmethod
    def _raise_integrity_error(error: IntegrityError) -> None:
        if _constraint_name(error) in {"products_sku_key", "uq_products_sku_upper"}:
            raise DomainError(
                409, "PRODUCT_SKU_CONFLICT", "Product SKU already exists."
            ) from error
