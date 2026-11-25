from datetime import timedelta

import jwt
import pytest
from pydantic import SecretStr

from app.auth.security import create_access_token, hash_password
from app.models import User, UserRole


def test_registration_forbids_role_and_always_creates_client(
    postgres_client, postgres_session
) -> None:
    rejected = postgres_client.post(
        "/api/v1/auth/register",
        json={"email": "person@example.com", "password": "strong-password", "role": "admin"},
    )
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["code"] == "REQUEST_VALIDATION_ERROR"

    created = postgres_client.post(
        "/api/v1/auth/register",
        json={"email": " Person@Example.com ", "password": "strong-password"},
    )

    assert created.status_code == 201
    assert created.json()["email"] == "person@example.com"
    assert created.json()["role"] == "client"
    assert "password_hash" not in created.json()
    user = postgres_session.query(User).filter_by(email="person@example.com").one()
    assert user.role is UserRole.CLIENT
    assert user.password_hash != "strong-password"


def test_duplicate_registration_returns_specific_email_conflict(postgres_client) -> None:
    payload = {"email": "duplicate@example.com", "password": "strong-password"}
    assert postgres_client.post("/api/v1/auth/register", json=payload).status_code == 201

    response = postgres_client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "USER_EMAIL_CONFLICT"


def test_access_token_contains_only_identity_and_lifecycle_claims(unit_settings) -> None:
    custom_secret = "distinct-custom-jwt-secret-with-more-than-32-characters"
    settings = unit_settings.model_copy(
        update={"jwt_expire_minutes": 5, "jwt_secret_key": SecretStr(custom_secret)}
    )
    token = create_access_token(23, settings)
    claims = jwt.decode(token, custom_secret, algorithms=["HS256"])

    assert set(claims) == {"sub", "iat", "exp"}
    assert claims["sub"] == "23"
    assert claims["exp"] - claims["iat"] == 300
    with pytest.raises(jwt.InvalidTokenError):
        jwt.decode(
            token,
            unit_settings.jwt_secret_key.get_secret_value(),
            algorithms=["HS256"],
        )


def test_missing_and_disabled_users_have_same_login_error(
    postgres_client, postgres_session
) -> None:
    disabled_user = User(
        email="disabled@example.com",
        password_hash=hash_password("strong-password"),
        role=UserRole.CLIENT,
        is_active=False,
    )
    postgres_session.add(disabled_user)
    postgres_session.commit()

    disabled = postgres_client.post(
        "/api/v1/auth/login",
        json={"email": "disabled@example.com", "password": "strong-password"},
    )
    missing = postgres_client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "strong-password"},
    )

    assert disabled.status_code == missing.status_code == 401
    assert disabled.json() == missing.json()
    assert disabled.json()["detail"]["code"] == "INVALID_CREDENTIALS"


def test_current_user_reloads_database_role_and_rejects_disabled_user(
    postgres_client, postgres_session, unit_settings
) -> None:
    user = User(
        email="client@example.com", password_hash="not-used", role=UserRole.CLIENT, is_active=True
    )
    postgres_session.add(user)
    postgres_session.commit()
    token = create_access_token(user.id, unit_settings)

    assert jwt.decode(
        token, unit_settings.jwt_secret_key.get_secret_value(), algorithms=["HS256"]
    )["sub"] == str(user.id)
    assert postgres_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    ).json()["role"] == "client"

    user.is_active = False
    postgres_session.commit()
    rejected = postgres_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert rejected.status_code == 401


def test_expired_access_token_is_rejected(postgres_client, postgres_session, unit_settings) -> None:
    user = User(email="expired@example.com", password_hash="unused", role=UserRole.CLIENT)
    postgres_session.add(user)
    postgres_session.commit()
    token = create_access_token(user.id, unit_settings, timedelta(seconds=-1))

    response = postgres_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401
