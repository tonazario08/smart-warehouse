from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.auth.dependencies import get_current_user
from app.auth.repository import UserRepository
from app.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.auth.security import create_access_token
from app.auth.service import AuthService
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, session: Annotated[object, Depends(get_session)]) -> User:
    return AuthService(session, UserRepository(session)).register(request.email, request.password)


@router.post("/login", response_model=TokenResponse)
def login(
    request: LoginRequest,
    session: Annotated[object, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    service = AuthService(session, UserRepository(session))
    user = service.authenticate(request.email, request.password)
    return TokenResponse(access_token=create_access_token(user.id, settings), user=user)


@router.get("/me", response_model=UserResponse)
def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user
