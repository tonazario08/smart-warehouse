"""Issue recovery links and update account credentials in PostgreSQL."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from urllib.parse import urlencode

from sqlalchemy import and_, case, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.password_mail import PasswordMailer, send_password_email
from app.auth.recovery_models import PasswordRecoveryBudget, PasswordResetToken
from app.auth.repository import UserRepository
from app.auth.security import hash_password, verify_password
from app.core.errors import DomainError
from app.db.session import get_engine
from app.models import User

logger = logging.getLogger(__name__)
RECOVERY_TTL = timedelta(minutes=30)
RECOVERY_COOLDOWN = timedelta(minutes=5)
RECOVERY_REQUESTS_PER_MINUTE = 60


@contextmanager
def _redact_database_errors(session: Session) -> Iterator[None]:
    try:
        yield
    except SQLAlchemyError:
        with suppress(SQLAlchemyError):
            session.rollback()
        logger.warning("Password operation could not complete in the database")
        raise DomainError(
            503, "PASSWORD_OPERATION_UNAVAILABLE", "Password operation unavailable."
        ) from None


def admit_recovery_request(session: Session) -> bool:
    """Reserve one shared slot without looking up the requested account."""
    window = datetime.now(UTC).replace(second=0, microsecond=0)
    budget = PasswordRecoveryBudget
    statement = insert(budget).values(id=1, window_start=window, requests=1)
    next_window = budget.window_start < statement.excluded.window_start
    statement = statement.on_conflict_do_update(
        index_elements=[budget.id],
        set_={
            "window_start": statement.excluded.window_start,
            "requests": case((next_window, 1), else_=budget.requests + 1),
        },
        where=or_(
            next_window,
            and_(budget.window_start == window, budget.requests < RECOVERY_REQUESTS_PER_MINUTE),
        ),
    ).returning(budget.id)
    with _redact_database_errors(session):
        admitted = session.scalar(statement) is not None
        session.commit()
    return admitted


def _digest(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def issue_password_reset(
    database_url: str, origin: str, email: str, mailer: PasswordMailer
) -> None:
    """Run outside the request and only send after the reset record is committed."""
    try:
        with Session(get_engine(database_url)) as session:
            session.execute(text("SET LOCAL lock_timeout = '2s'"))
            session.execute(text("SET LOCAL statement_timeout = '5s'"))
            user = UserRepository(session).lock_by_email(email)
            if user is None or not user.is_active:
                return
            now = datetime.now(UTC)
            record = session.get(PasswordResetToken, user.id)
            if record is not None and now - record.issued_at < RECOVERY_COOLDOWN:
                return
            token = token_urlsafe(32)
            if record is None:
                record = PasswordResetToken(user_id=user.id)
                session.add(record)
            record.digest = _digest(token)
            record.issued_at = now
            record.expires_at = now + RECOVERY_TTL
            record.revoked_at = None
            session.commit()
    except Exception:
        logger.warning("Password recovery request could not be processed")
        return

    link = f"{origin}/reset-password#{urlencode({'token': token})}"
    send_password_email(
        mailer,
        email,
        "Đặt lại mật khẩu Smart Warehouse",
        f"Mở liên kết trong vòng 30 phút để đặt lại mật khẩu:\n{link}\n\n"
        "Nếu bạn không yêu cầu, hãy bỏ qua email này.",
    )


def _check_confirmation(new_password: str, confirmation: str) -> None:
    if new_password != confirmation:
        raise DomainError(422, "PASSWORD_CONFIRMATION_MISMATCH", "Passwords must match.")


def _reject_password_reuse(reused: bool) -> None:
    if reused:
        raise DomainError(422, "PASSWORD_REUSE", "New password must differ from current password.")


def _replace_password(
    session: Session, user: User, record: PasswordResetToken | None, password: str
) -> str:
    email = user.email
    user.password_hash = hash_password(password)
    user.auth_version += 1
    if record is not None:
        record.revoked_at = datetime.now(UTC)
    session.commit()
    return email


def change_password(
    session: Session, actor: User, current_password: str, password: str, confirmation: str
) -> str:
    _check_confirmation(password, confirmation)
    version = actor.auth_version
    with _redact_database_errors(session):
        user = UserRepository(session).lock_by_id(actor.id)
        if user is None or not user.is_active or user.auth_version != version:
            raise DomainError(401, "INVALID_CREDENTIALS", "Invalid authentication credentials.")
        if not verify_password(current_password, user.password_hash):
            raise DomainError(400, "CURRENT_PASSWORD_INVALID", "Current password is incorrect.")
        _reject_password_reuse(password == current_password)
        return _replace_password(session, user, session.get(PasswordResetToken, user.id), password)


def reset_password(session: Session, token: str, password: str, confirmation: str) -> str:
    _check_confirmation(password, confirmation)
    digest = _digest(token)
    invalid = DomainError(400, "INVALID_RESET_TOKEN", "Invalid or expired password reset link.")
    with _redact_database_errors(session):
        user_id = session.scalar(select(PasswordResetToken.user_id).where(
            PasswordResetToken.digest == digest
        ))
        if user_id is None:
            raise invalid

        user = UserRepository(session).lock_by_id(user_id)
        record = session.get(PasswordResetToken, user_id)
        if (
            user is None or not user.is_active or record is None or record.digest != digest
            or record.revoked_at is not None or record.expires_at <= datetime.now(UTC)
        ):
            raise invalid
        _reject_password_reuse(verify_password(password, user.password_hash))
        return _replace_password(session, user, record, password)


def notify_password_replaced(mailer: PasswordMailer, recipient: str) -> None:
    send_password_email(
        mailer,
        recipient,
        "Mật khẩu Smart Warehouse đã thay đổi",
        "Mật khẩu của bạn đã được thay đổi. Nếu bạn không thực hiện thao tác này, "
        "hãy liên hệ quản trị viên.",
    )
