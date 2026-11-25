"""Authentication use cases and their transaction ownership."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.repository import UserRepository
from app.auth.security import hash_password, verify_password
from app.core.errors import DomainError
from app.models import User, UserRole


class AuthService:
    """Register and authenticate users without putting business rules in routes."""

    def __init__(self, session: Session, users: UserRepository) -> None:
        self.session = session
        self.users = users

    def register(self, email: str, password: str) -> User:
        user = User(
            email=email,
            password_hash=hash_password(password),
            role=UserRole.CLIENT,
        )
        try:
            self.users.add(user)
            self.session.commit()
            self.session.refresh(user)
            return user
        except IntegrityError as error:
            self.session.rollback()
            raise DomainError(
                409, "USER_EMAIL_CONFLICT", "Email is already registered."
            ) from error

    def authenticate(self, email: str, password: str) -> User:
        user = self.users.get_by_email(email)
        if (
            user is None
            or not user.is_active
            or not verify_password(password, user.password_hash)
        ):
            raise DomainError(401, "INVALID_CREDENTIALS", "Invalid email or password.")
        return user
