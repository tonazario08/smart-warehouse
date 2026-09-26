"""Persistence boundaries for master-data records."""

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.core.pagination import PageParams
from app.models import (
    Category,
    Inbound,
    Outbound,
    Product,
    PurchaseRequest,
    Stock,
    StockTransaction,
    Supplier,
)


class CategoryRepository:
    """Query and stage category persistence without owning transactions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self, params: PageParams) -> list[Category]:
        statement = (
            select(Category)
            .order_by(Category.id)
            .offset(params.offset)
            .limit(params.page_size)
        )
        return list(self.session.scalars(statement).all())

    def count(self) -> int:
        return self.session.scalar(select(func.count()).select_from(Category)) or 0

    def get(self, category_id: int) -> Category | None:
        return self.session.get(Category, category_id)

    def add(self, category: Category) -> None:
        self.session.add(category)

    def update(self, category: Category, name: str, parent_id: int | None) -> None:
        category.name = name
        category.parent_id = parent_id

    def delete(self, category: Category) -> None:
        self.session.delete(category)


class SupplierRepository:
    """Query and stage supplier persistence without owning transactions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self, params: PageParams, search: str | None = None) -> list[Supplier]:
        statement = select(Supplier)
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    Supplier.name.ilike(pattern),
                    Supplier.email.ilike(pattern),
                    Supplier.phone.ilike(pattern),
                    Supplier.address.ilike(pattern),
                )
            )
        statement = (
            statement.order_by(Supplier.id)
            .offset(params.offset)
            .limit(params.page_size)
        )
        return list(self.session.scalars(statement).all())

    def count(self, search: str | None = None) -> int:
        statement = select(func.count()).select_from(Supplier)
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    Supplier.name.ilike(pattern),
                    Supplier.email.ilike(pattern),
                    Supplier.phone.ilike(pattern),
                    Supplier.address.ilike(pattern),
                )
            )
        return self.session.scalar(statement) or 0

    def get(self, supplier_id: int) -> Supplier | None:
        return self.session.get(Supplier, supplier_id)

    def add(self, supplier: Supplier) -> None:
        self.session.add(supplier)

    def update(
        self,
        supplier: Supplier,
        *,
        name: str,
        email: str | None,
        phone: str | None,
        address: str | None,
    ) -> None:
        supplier.name = name
        supplier.email = email
        supplier.phone = phone
        supplier.address = address

    def delete(self, supplier: Supplier) -> None:
        self.session.delete(supplier)

    def has_products(self, supplier_id: int) -> bool:
        statement = select(Product.id).where(Product.supplier_id == supplier_id).limit(1)
        return self.session.scalar(statement) is not None


class ProductRepository:
    """Query and stage product persistence without owning transactions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _filters(
        *,
        search: str | None,
        category_id: int | None,
        supplier_id: int | None,
        is_active: bool | None,
    ):
        filters = []
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    Product.sku.ilike(pattern),
                    Product.name.ilike(pattern),
                    Product.description.ilike(pattern),
                )
            )
        if category_id is not None:
            filters.append(Product.category_id == category_id)
        if supplier_id is not None:
            filters.append(Product.supplier_id == supplier_id)
        if is_active is not None:
            filters.append(Product.is_active.is_(is_active))
        return filters

    def list(
        self,
        params: PageParams,
        *,
        search: str | None = None,
        category_id: int | None = None,
        supplier_id: int | None = None,
        is_active: bool | None = None,
    ) -> list[Product]:
        statement = select(Product).where(
            *self._filters(
                search=search,
                category_id=category_id,
                supplier_id=supplier_id,
                is_active=is_active,
            )
        )
        statement = (
            statement.order_by(Product.id)
            .offset(params.offset)
            .limit(params.page_size)
        )
        return list(self.session.scalars(statement).all())

    def count(
        self,
        *,
        search: str | None = None,
        category_id: int | None = None,
        supplier_id: int | None = None,
        is_active: bool | None = None,
    ) -> int:
        statement = select(func.count()).select_from(Product).where(
            *self._filters(
                search=search,
                category_id=category_id,
                supplier_id=supplier_id,
                is_active=is_active,
            )
        )
        return self.session.scalar(statement) or 0

    def get(self, product_id: int) -> Product | None:
        return self.session.get(Product, product_id)

    def add(self, product: Product) -> None:
        self.session.add(product)

    @staticmethod
    def update(product: Product, values: dict[str, object]) -> None:
        for field, value in values.items():
            setattr(product, field, value)

    def delete(self, product: Product) -> None:
        self.session.delete(product)

    def has_references(self, product_id: int) -> bool:
        references = (
            exists(select(Stock.id).where(Stock.product_id == product_id)),
            exists(select(Inbound.id).where(Inbound.product_id == product_id)),
            exists(select(Outbound.id).where(Outbound.product_id == product_id)),
            exists(select(StockTransaction.id).where(StockTransaction.product_id == product_id)),
            exists(select(PurchaseRequest.id).where(PurchaseRequest.product_id == product_id)),
        )
        return bool(self.session.scalar(select(or_(*references))))
