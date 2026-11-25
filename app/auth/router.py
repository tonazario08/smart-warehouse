from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, status

from app.auth.dependencies import get_current_user
from app.auth.password_mail import PasswordMailer, get_password_mailer
from app.auth.password_recovery import (
    admit_recovery_request,
    change_password,
    issue_password_reset,
    notify_password_replaced,
    reset_password,
)
from app.auth.repository import UserRepository
from app.auth.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)
from app.auth.security import create_access_token
from app.auth.service import AuthService
from app.core.config import Settings, get_settings
from app.core.errors import DomainError
from app.db.session import get_session
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])
DbSession = Annotated[object, Depends(get_session)]
PasswordEmail = Annotated[PasswordMailer | None, Depends(get_password_mailer)]


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, session: DbSession) -> User:
    return AuthService(session, UserRepository(session)).register(request.email, request.password)


@router.post("/login", response_model=TokenResponse)
def login(
    request: LoginRequest,
    session: DbSession,
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    service = AuthService(session, UserRepository(session))
    user = service.authenticate(request.email, request.password)
    return TokenResponse(
        access_token=create_access_token(user.id, settings, auth_version=user.auth_version),
        user=user,
    )


@router.get("/me", response_model=UserResponse)
def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(
    request: ForgotPasswordRequest,
    background: BackgroundTasks,
    session: DbSession,
    settings: Annotated[Settings, Depends(get_settings)],
    mailer: PasswordEmail,
) -> ForgotPasswordResponse:
    origin = settings.password_recovery_origin
    if mailer is None or origin is None:
        raise DomainError(503, "PASSWORD_RECOVERY_UNAVAILABLE", "Password recovery is unavailable.")
    if admit_recovery_request(session):
        background.add_task(
            issue_password_reset, settings.database_url, origin, request.email, mailer
        )
    return ForgotPasswordResponse(message="If the account is eligible, a reset link will be sent.")


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def replace_forgotten_password(
    request: ResetPasswordRequest,
    background: BackgroundTasks,
    session: DbSession,
    mailer: PasswordEmail,
) -> None:
    if mailer is None:
        raise DomainError(503, "PASSWORD_RECOVERY_UNAVAILABLE", "Password recovery is unavailable.")
    recipient = reset_password(
        session, request.token.get_secret_value(), request.new_password.get_secret_value(),
        request.confirm_password.get_secret_value(),
    )
    background.add_task(notify_password_replaced, mailer, recipient)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def replace_current_password(
    request: ChangePasswordRequest,
    background: BackgroundTasks,
    session: DbSession,
    actor: Annotated[User, Depends(get_current_user)],
    mailer: PasswordEmail,
) -> None:
    recipient = change_password(
        session, actor, request.current_password.get_secret_value(),
        request.new_password.get_secret_value(), request.confirm_password.get_secret_value(),
    )
    if mailer is not None:
        background.add_task(notify_password_replaced, mailer, recipient)
