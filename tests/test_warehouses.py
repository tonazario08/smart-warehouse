from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_session
from app.main import create_app
from app.models import User, UserRole


@pytest.fixture
def client() -> Iterator[tuple[TestClient, Session]]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add_all(
        [
            User(email="admin@example.com", password_hash=hash_password("password"), role="admin"),
            User(
                email="warehouse@example.com",
                password_hash=hash_password("password"),
                role="warehouse",
            ),
            User(
                email="client@example.com", password_hash=hash_password("password"), role="client"
            ),
        ]
    )
    session.commit()
    application = create_app()
    application.dependency_overrides[get_session] = lambda: session
    with TestClient(application) as test_client:
        yield test_client, session
    session.close()
    engine.dispose()


def headers(session: Session, role: UserRole) -> dict[str, str]:
    user = session.query(User).filter_by(role=role).first()
    assert user is not None
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def test_warehouse_read_is_allowed_to_client_and_write_is_admin_only(
    client: tuple[TestClient, Session],
) -> None:
    test_client, session = client
    payload = {"code": "HCM-01", "name": "Central", "address": "1 Nguyen Hue"}

    response = test_client.post(
        "/api/v1/warehouses", json=payload, headers=headers(session, UserRole.CLIENT)
    )
    assert response.status_code == 403

    response = test_client.post(
        "/api/v1/warehouses", json=payload, headers=headers(session, UserRole.ADMIN)
    )
    assert response.status_code == 201
    warehouse_id = response.json()["id"]

    response = test_client.get(
        f"/api/v1/warehouses/{warehouse_id}", headers=headers(session, UserRole.CLIENT)
    )
    assert response.status_code == 200
    assert response.json()["code"] == "HCM-01"
