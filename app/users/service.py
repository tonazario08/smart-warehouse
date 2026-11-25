"""User-administration use cases and transaction ownership."""

from collections.abc import Mapping
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit.service import AuditService, user_audit_snapshot
from app.auth.security import hash_password
from app.core.errors import DomainError
from app.core.pagination import Page, PageParams
from app.models import User, UserRole
from app.users.repository import UserRepository


def _is_email_conflict(error: IntegrityError) -> bool:
    original = error.orig
    sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
    constraint = getattr(getattr(original, "diag", None), "constraint_name", None)
    return sqlstate == "23505" and constraint in {"users_email_key", "uq_users_email_lower"}


class UserService:
    """Apply administrative user changes and their audit rows atomically."""

    def __init__(
        self,
        session: Session,
        users: UserRepository,
        audit: AuditService,
    ) -> None:
        self.session = session
        self.users = users
        self.audit = audit

    def list(self, params: PageParams) -> Page[User]:
        return Page[User](
            items=self.users.list(params),
            total=self.users.count(),
            page=params.page,
            page_size=params.page_size,
        )

    def get(self, user_id: int) -> User:
        user = self.users.get(user_id)
        if user is None:
            raise DomainError(404, "USER_NOT_FOUND", "User was not found.")
        return user

    def create(self, actor: User, email: str, password: str, role: UserRole) -> User:
        self._require_managed_role(role)
        user = User(
            email=email,
            password_hash=hash_password(password),
            role=role,
        )
        try:
            self.users.add(user)
            self.session.flush()
            self.audit.record_user_event(actor, "user.created", None, user)
            self.session.commit()
            self.session.refresh(user)
            return user
        except IntegrityError as error:
            self.session.rollback()
            if _is_email_conflict(error):
                raise DomainError(
                    409, "USER_EMAIL_CONFLICT", "Email is already registered."
                ) from error
            raise
        except Exception:
            self.session.rollback()
            raise

    def change_role(self, actor: User, target_id: int, role: UserRole) -> User:
        target = self.get(target_id)
        self._protect_admin(target, actor)
        self._require_managed_role(role)
        new_role = role
        if target.role is new_role:
            raise DomainError(409, "USER_ROLE_UNCHANGED", "User already has this role.")

        before = user_audit_snapshot(target)
        self.users.change_role(target, new_role)
        return self._persist_event(actor, "user.role_changed", before, target)

    def change_status(self, actor: User, target_id: int, is_active: bool) -> User:
        target = self.get(target_id)
        self._protect_admin(target, actor)
        if target.is_active is is_active:
            raise DomainError(409, "USER_STATUS_UNCHANGED", "User already has this status.")

        before = user_audit_snapshot(target)
        self.users.change_status(target, is_active)
        return self._persist_event(actor, "user.status_changed", before, target)

    @staticmethod
    def _protect_admin(target: User, actor: User) -> None:
        if target.role is UserRole.ADMIN or target.id == actor.id:
            raise DomainError(
                409,
                "ADMIN_ACCOUNT_PROTECTED",
                "Admin accounts cannot be modified.",
            )

    @staticmethod
    def _require_managed_role(role: UserRole) -> None:
        if role not in {UserRole.CLIENT, UserRole.WAREHOUSE}:
            raise DomainError(
                422,
                "USER_ROLE_INVALID",
                "Only client or warehouse roles are allowed.",
            )

    def _persist_event(
        self,
        actor: User,
        action: str,
        before: Mapping[str, Any],
        after: User,
    ) -> User:
        try:
            self.audit.record_user_event(actor, action, before, after)
            self.session.commit()
            self.session.refresh(after)
            return after
        except Exception:
            self.session.rollback()
            raise
