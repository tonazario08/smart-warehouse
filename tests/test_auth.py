from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth.security import create_access_token
from app.db.base import Base
from app.db.session import get_session
from app.main import create_app
from app.models import User, UserRole


def make_client(unit_settings) -> tuple[TestClient, Session, object]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    application = create_app(unit_settings)
    application.dependency_overrides[get_session] = lambda: session
    return TestClient(application), session, engine


def test_access_token_helper_requires_explicit_settings() -> None:
    with pytest.raises(TypeError, match="settings must be a Settings instance"):
        create_access_token(23, UserRole.ADMIN)


def test_registration_always_creates_a_client_and_hashes_password(unit_settings) -> None:
    test_client, session, engine = make_client(unit_settings)
    try:
        response = test_client.post(
            "/api/v1/auth/register",
            json={"email": " Person@Example.com ", "password": "strong-password"},
        )

        assert response.status_code == 201
        assert response.json()["email"] == "person@example.com"
        assert response.json()["role"] == "client"
        assert "password_hash" not in response.json()
        user = session.scalar(select(User).where(User.email == "person@example.com"))
        assert user is not None
        assert user.role is UserRole.CLIENT
        assert user.password_hash != "strong-password"
    finally:
        test_client.close()
        session.close()
        engine.dispose()


def test_public_registration_rejects_role_injection(unit_settings) -> None:
    test_client, session, engine = make_client(unit_settings)
    try:
        response = test_client.post(
            "/api/v1/auth/register",
            json={"email": "admin@example.com", "password": "strong-password", "role": "admin"},
        )

        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "REQUEST_VALIDATION_ERROR"
        assert session.scalar(select(User)) is None
    finally:
        test_client.close()
        session.close()
        engine.dispose()


def test_login_returns_token_without_authoritative_role(unit_settings) -> None:
    test_client, session, engine = make_client(unit_settings)
    try:
        test_client.post(
            "/api/v1/auth/register",
            json={"email": "operator@example.com", "password": "strong-password"},
        )

        response = test_client.post(
            "/api/v1/auth/login",
            json={"email": "operator@example.com", "password": "strong-password"},
        )

        assert response.status_code == 200
        token = response.json()["access_token"]
        claims = jwt.decode(
            token,
            unit_settings.jwt_secret_key.get_secret_value(),
            algorithms=["HS256"],
        )
        assert set(claims) == {"sub", "iat", "exp"}
        assert "password_hash" not in response.json()["user"]
    finally:
        test_client.close()
        session.close()
        engine.dispose()


def test_unknown_and_wrong_password_login_are_indistinguishable(unit_settings) -> None:
    test_client, session, engine = make_client(unit_settings)
    try:
        test_client.post(
            "/api/v1/auth/register",
            json={"email": "known@example.com", "password": "strong-password"},
        )
        wrong_password = test_client.post(
            "/api/v1/auth/login",
            json={"email": "known@example.com", "password": "incorrect-password"},
        )
        unknown_user = test_client.post(
            "/api/v1/auth/login",
            json={"email": "missing@example.com", "password": "incorrect-password"},
        )

        assert wrong_password.status_code == unknown_user.status_code == 401
        assert wrong_password.json() == unknown_user.json()
        assert wrong_password.json()["detail"]["code"] == "INVALID_CREDENTIALS"
    finally:
        test_client.close()
        session.close()
        engine.dispose()


def test_current_user_uses_database_state_and_rejects_expired_tokens(unit_settings) -> None:
    test_client, session, engine = make_client(unit_settings)
    try:
        user = User(email="user@example.com", password_hash="unused", role=UserRole.CLIENT)
        session.add(user)
        session.commit()
        token = jwt.encode(
            {
                "sub": str(user.id),
                "role": "admin",
                "iat": datetime.now(UTC),
                "exp": datetime.now(UTC) + timedelta(minutes=5),
            },
            unit_settings.jwt_secret_key.get_secret_value(),
            algorithm="HS256",
        )
        response = test_client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["role"] == "client"

        expired = create_access_token(user.id, unit_settings, timedelta(seconds=-1))
        rejected = test_client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"}
        )
        assert rejected.status_code == 401

        user.is_active = False
        session.commit()
        disabled = test_client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert disabled.status_code == 401
    finally:
        test_client.close()
        session.close()
        engine.dispose()
