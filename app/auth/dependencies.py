from enum import StrEnum
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.repository import UserRepository
from app.auth.security import decode_access_token
from app.core.config import Settings, get_settings
from app.core.errors import DomainError
from app.db.session import get_session
from app.models import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)


class Permission(StrEnum):
    CATALOG_READ = "catalog:read"
    PRODUCT_WRITE = "product:write"
    SUPPLIER_READ = "supplier:read"
    SUPPLIER_WRITE = "supplier:write"
    WAREHOUSE_READ = "warehouse:read"
    WAREHOUSE_WRITE = "warehouse:write"
    INVENTORY_READ = "inventory:read"
    INVENTORY_HISTORY_READ = "inventory:history:read"
    INVENTORY_WRITE = "inventory:write"
    DASHBOARD_READ = "dashboard:read"
    USER_MANAGE = "user:manage"
    AUDIT_READ = "audit:read"


PERMISSION_ROLES: dict[Permission, frozenset[UserRole]] = {
    Permission.CATALOG_READ: frozenset(UserRole),
    Permission.PRODUCT_WRITE: frozenset({UserRole.ADMIN}),
    Permission.SUPPLIER_READ: frozenset({UserRole.ADMIN, UserRole.WAREHOUSE}),
    Permission.SUPPLIER_WRITE: frozenset({UserRole.ADMIN}),
    Permission.WAREHOUSE_READ: frozenset({UserRole.ADMIN, UserRole.WAREHOUSE, UserRole.CLIENT}),
    Permission.WAREHOUSE_WRITE: frozenset({UserRole.ADMIN}),
    Permission.INVENTORY_READ: frozenset({UserRole.ADMIN, UserRole.WAREHOUSE, UserRole.CLIENT}),
    Permission.INVENTORY_HISTORY_READ: frozenset({UserRole.ADMIN, UserRole.WAREHOUSE}),
    Permission.INVENTORY_WRITE: frozenset({UserRole.ADMIN, UserRole.WAREHOUSE}),
    Permission.DASHBOARD_READ: frozenset({UserRole.ADMIN}),
    Permission.USER_MANAGE: frozenset({UserRole.ADMIN}),
    Permission.AUDIT_READ: frozenset({UserRole.ADMIN}),
}


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    if credentials is None:
        raise DomainError(
            status.HTTP_401_UNAUTHORIZED,
            "AUTHENTICATION_REQUIRED",
            "Authentication required.",
        )
    try:
        payload = decode_access_token(credentials.credentials, settings)
        user_id = int(payload["sub"])
    except (ValueError, KeyError, TypeError, jwt.PyJWTError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from error

    user = UserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise DomainError(401, "INVALID_CREDENTIALS", "Invalid authentication credentials.")
    return user


def require_permission(permission: Permission):
    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in PERMISSION_ROLES[permission]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return user

    return dependency
