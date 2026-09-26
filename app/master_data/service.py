"""Category use cases and transaction ownership."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.core.pagination import Page, PageParams
from app.master_data.repository import CategoryRepository
from app.master_data.schemas import CategoryCreate, CategoryUpdate
from app.models import Category


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
