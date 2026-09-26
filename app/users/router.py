"""Admin-only HTTP routes for managed user accounts."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.audit.repository import AuditRepository
from app.audit.service import AuditService
from app.auth.dependencies import Permission, require_permission
from app.core.pagination import Page, PageParams
from app.db.session import get_session
from app.models import User, UserRole
from app.users.repository import UserRepository
from app.users.schemas import (
    ManagedUserResponse,
    UserCreate,
    UserRoleUpdate,
    UserStatusUpdate,
)
from app.users.service import UserService

router = APIRouter(prefix="/users", tags=["users"])


def _service(session: Session) -> UserService:
    return UserService(
        session,
        UserRepository(session),
        AuditService(AuditRepository(session)),
    )


@router.post("", response_model=ManagedUserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    request: UserCreate,
    session: Annotated[Session, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission(Permission.USER_MANAGE))],
) -> User:
    return _service(session).create(
        actor, request.email, request.password, UserRole(request.role.value)
    )


@router.get("", response_model=Page[ManagedUserResponse])
def list_users(
    params: Annotated[PageParams, Depends()],
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.USER_MANAGE))],
) -> Page[ManagedUserResponse]:
    return _service(session).list(params)


@router.get("/{user_id}", response_model=ManagedUserResponse)
def get_user(
    user_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.USER_MANAGE))],
) -> User:
    return _service(session).get(user_id)


@router.patch("/{user_id}/role", response_model=ManagedUserResponse)
def change_user_role(
    user_id: int,
    request: UserRoleUpdate,
    session: Annotated[Session, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission(Permission.USER_MANAGE))],
) -> User:
    return _service(session).change_role(actor, user_id, UserRole(request.role.value))


@router.patch("/{user_id}/status", response_model=ManagedUserResponse)
def change_user_status(
    user_id: int,
    request: UserStatusUpdate,
    session: Annotated[Session, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission(Permission.USER_MANAGE))],
) -> User:
    return _service(session).change_status(actor, user_id, request.is_active)
