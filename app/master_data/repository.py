"""Persistence boundaries for master-data records."""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.pagination import PageParams
from app.models import Category, Product, Supplier


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
