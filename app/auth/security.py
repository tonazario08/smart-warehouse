import os
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.models import UserRole

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
    user_id: int, role: UserRole, expires_delta: timedelta | None = None
) -> str:
    expires_at = datetime.now(UTC) + (expires_delta or timedelta(minutes=30))
    payload = {"sub": str(user_id), "role": role.value, "exp": expires_at}
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, object]:
    return jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])


def _jwt_secret() -> str:
    return os.getenv("JWT_SECRET", "local-development-secret-change-me")
