"""Persistence boundary for administratively managed users."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.pagination import PageParams
from app.models import User, UserRole


class UserRepository:
    """Query and stage user persistence without owning transactions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self, params: PageParams) -> list[User]:
        statement = select(User).order_by(User.id).offset(params.offset).limit(params.page_size)
        return list(self.session.scalars(statement).all())

    def count(self) -> int:
        return self.session.scalar(select(func.count()).select_from(User)) or 0

    def get(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def add(self, user: User) -> None:
        self.session.add(user)

    def change_role(self, user: User, role: UserRole) -> None:
        user.role = role

    def change_status(self, user: User, is_active: bool) -> None:
        user.is_active = is_active
