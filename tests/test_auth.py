from collections.abc import Iterator
from datetime import timedelta

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_session
from app.main import create_app
from app.models import User, UserRole


@pytest.fixture
def client() -> Iterator[tuple[TestClient, Session]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    application = create_app()
    application.dependency_overrides[get_session] = lambda: session
    with TestClient(application) as test_client:
        yield test_client, session
    session.close()
    engine.dispose()


def test_register_hashes_password_and_returns_user(client: tuple[TestClient, Session]) -> None:
    test_client, session = client

    response = test_client.post(
        "/api/v1/auth/register",
        json={"email": "admin@example.com", "password": "strong-password", "role": "admin"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "admin@example.com"
    assert body["role"] == "admin"
    user = session.scalar(select(User).where(User.email == "admin@example.com"))
    assert user is not None
    assert user.password_hash != "strong-password"


def test_login_returns_jwt_with_required_claims(client: tuple[TestClient, Session]) -> None:
    test_client, _ = client
    test_client.post(
        "/api/v1/auth/register",
        json={"email": "operator@example.com", "password": "strong-password", "role": "warehouse"},
    )

    response = test_client.post(
        "/api/v1/auth/login",
        json={"email": "operator@example.com", "password": "strong-password"},
    )

    assert response.status_code == 200
    token = response.json()["access_token"]
    claims = jwt.decode(token, "local-development-secret-change-me", algorithms=["HS256"])
    assert {"sub", "role", "exp"} <= claims.keys()


def test_invalid_login_is_rejected(client: tuple[TestClient, Session]) -> None:
    test_client, _ = client
    response = test_client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "wrong"},
    )

    assert response.status_code == 401


def test_protected_endpoint_uses_database_role_not_stale_jwt_role(
    client: tuple[TestClient, Session],
) -> None:
    test_client, session = client
    user = User(email="user@example.com", password_hash="hash", role=UserRole.CLIENT)
    session.add(user)
    session.commit()

    from app.auth.security import create_access_token

    token = create_access_token(user_id=user.id, role=UserRole.ADMIN)
    response = test_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["role"] == "client"


def test_invalid_token_is_rejected(client: tuple[TestClient, Session]) -> None:
    test_client, _ = client

    response = test_client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"})

    assert response.status_code == 401


def test_expired_token_is_rejected(client: tuple[TestClient, Session]) -> None:
    test_client, session = client
    user = User(email="expired@example.com", password_hash="hash", role=UserRole.CLIENT)
    session.add(user)
    session.commit()

    from app.auth.security import create_access_token

    token = create_access_token(user.id, user.role, expires_delta=timedelta(seconds=-1))
    response = test_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_registration_rejects_guest_role(client: tuple[TestClient, Session]) -> None:
    test_client, _ = client

    response = test_client.post(
        "/api/v1/auth/register",
        json={"email": "guest@example.com", "password": "strong-password", "role": "guest"},
    )

    assert response.status_code == 422


def test_dashboard_permission_allows_admin_and_rejects_client() -> None:
    from app.auth.dependencies import Permission, require_permission

    admin = User(email="admin@example.com", password_hash="hash", role=UserRole.ADMIN)
    client_user = User(email="client@example.com", password_hash="hash", role=UserRole.CLIENT)
    assert require_permission(Permission.DASHBOARD_READ)(admin) is admin
    with pytest.raises(HTTPException) as error:
        require_permission(Permission.DASHBOARD_READ)(client_user)
    assert error.value.status_code == 403
