from enum import StrEnum
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.db.session import get_session
from app.models import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)


class Permission(StrEnum):
    PRODUCT_READ = "product:read"
    PRODUCT_WRITE = "product:write"
    SUPPLIER_READ = "supplier:read"
    WAREHOUSE_READ = "warehouse:read"
    WAREHOUSE_WRITE = "warehouse:write"
    INVENTORY_READ = "inventory:read"
    INVENTORY_WRITE = "inventory:write"
    DASHBOARD_READ = "dashboard:read"


PERMISSION_ROLES: dict[Permission, frozenset[UserRole]] = {
    Permission.PRODUCT_READ: frozenset(UserRole),
    Permission.PRODUCT_WRITE: frozenset({UserRole.ADMIN}),
    Permission.SUPPLIER_READ: frozenset({UserRole.ADMIN, UserRole.WAREHOUSE}),
    Permission.WAREHOUSE_READ: frozenset({UserRole.ADMIN, UserRole.WAREHOUSE, UserRole.CLIENT}),
    Permission.WAREHOUSE_WRITE: frozenset({UserRole.ADMIN}),
    Permission.INVENTORY_READ: frozenset({UserRole.ADMIN, UserRole.WAREHOUSE, UserRole.CLIENT}),
    Permission.INVENTORY_WRITE: frozenset({UserRole.ADMIN, UserRole.WAREHOUSE}),
    Permission.DASHBOARD_READ: frozenset({UserRole.ADMIN}),
}


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[Session, Depends(get_session)],
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (ValueError, KeyError, TypeError, jwt.PyJWTError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from error

    user = session.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is unavailable")
    return user


def require_permission(permission: Permission):
    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in PERMISSION_ROLES[permission]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return user

    return dependency
