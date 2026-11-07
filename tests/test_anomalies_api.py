import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth.security import create_access_token
from app.db.base import Base
from app.db.session import get_session
from app.main import create_app
from app.models import User, UserRole


@pytest.fixture
def client_and_headers(unit_settings):
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        users = [
            User(
                email=f"api-{role.value}@example.test", password_hash="x", role=role, is_active=True
            )
            for role in UserRole
        ]
        session.add_all(users)
        session.commit()
        app = create_app(unit_settings)
        app.dependency_overrides[get_session] = lambda: session
        headers = {
            user.role.value: {
                "Authorization": f"Bearer {create_access_token(user.id, unit_settings)}"
            }
            for user in users
        }
        with TestClient(app) as client:
            yield client, headers, session, users
    engine.dispose()


def test_auth_and_default_fixture_hidden(client_and_headers):
    client, headers, _, _ = client_and_headers
    root = "/api/v1/anomalies"
    assert client.get(root + "/status").status_code == 401
    for path in ("/status", "", "/alv1-" + "a" * 64, "/alv1-" + "a" * 64 + "/reviews"):
        assert client.get(root + path, headers=headers["client"]).status_code == 403
    assert client.get(root + "/status", headers=headers["admin"]).json()["state"] == "unavailable"
    assert client.get(root, headers=headers["warehouse"]).json()["items"] == []
    assert client.get(root + "/alv1-" + "a" * 64, headers=headers["admin"]).status_code == 404


def test_invalid_filters_and_review_input_are_rejected(client_and_headers):
    client, headers, _, _ = client_and_headers
    root = "/api/v1/anomalies"
    assert client.get(root + "?page=0", headers=headers["admin"]).status_code == 422
    assert client.get(root + "?status=other", headers=headers["admin"]).status_code == 422
    assert (
        client.patch(
            root + "/alv1-" + "a" * 64 + "/review", headers=headers["client"], json={}
        ).status_code
        == 403
    )


def test_old_token_observes_current_role_and_activity(client_and_headers):
    from sqlalchemy import update

    client, headers, session, users = client_and_headers
    admin = next(u for u in users if u.role == UserRole.ADMIN)
    assert client.get("/api/v1/anomalies/status", headers=headers["admin"]).status_code == 200
    session.execute(
        update(User).where(User.id == admin.id).values(role=UserRole.CLIENT),
        execution_options={"synchronize_session": False},
    )
    session.commit()
    assert client.get("/api/v1/anomalies/status", headers=headers["admin"]).status_code == 403
    session.execute(
        update(User).where(User.id == admin.id).values(is_active=False),
        execution_options={"synchronize_session": False},
    )
    session.commit()
    assert client.get("/api/v1/anomalies/status", headers=headers["admin"]).status_code == 401
