"""Persistence boundary for category records."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.pagination import PageParams
from app.models import Category


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
