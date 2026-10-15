from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import Settings

JWT_ALGORITHM = "HS256"
password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_access_token(
    user_id: int, settings: Settings, expires_delta: timedelta | None = None
) -> str:
    if not isinstance(settings, Settings):
        raise TypeError("settings must be a Settings instance")
    issued_at = datetime.now(UTC)
    lifetime = (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.jwt_expire_minutes)
    )
    payload = {"sub": str(user_id), "iat": issued_at, "exp": issued_at + lifetime}
    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str, settings: Settings) -> dict[str, object]:
    return jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
        options={"require": ["sub", "iat", "exp"]},
    )
