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
from app.models import Category, User, UserRole


@pytest.fixture
def client() -> Iterator[tuple[TestClient, Session]]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    admin = User(email="admin@example.com", password_hash=hash_password("password"), role="admin")
    warehouse = User(
        email="warehouse@example.com", password_hash=hash_password("password"), role="warehouse"
    )
    client_user = User(
        email="client@example.com", password_hash=hash_password("password"), role="client"
    )
    session.add_all([admin, warehouse, client_user])
    session.commit()
    application = create_app()
    application.dependency_overrides[get_session] = lambda: session
    with TestClient(application) as test_client:
        yield test_client, session
    session.close()
    engine.dispose()


def auth_headers(session: Session, role: UserRole) -> dict[str, str]:
    user = session.query(User).filter_by(role=role).first()
    assert user is not None
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def test_categories_are_publicly_readable_and_paginated(
    client: tuple[TestClient, Session],
) -> None:
    test_client, session = client
    session.add(Category(name="Hardware"))
    session.commit()

    response = test_client.get("/api/v1/categories?page=1&page_size=20")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["name"] == "Hardware"


def test_only_admin_can_create_category(client: tuple[TestClient, Session]) -> None:
    test_client, session = client

    response = test_client.post(
        "/api/v1/categories",
        json={"name": "Hardware"},
        headers=auth_headers(session, UserRole.CLIENT),
    )
    assert response.status_code == 403

    response = test_client.post(
        "/api/v1/categories",
        json={"name": "Hardware"},
        headers=auth_headers(session, UserRole.ADMIN),
    )
    assert response.status_code == 201


def test_product_requires_existing_category_and_is_publicly_readable(
    client: tuple[TestClient, Session],
) -> None:
    test_client, session = client
    category = Category(name="Hardware")
    session.add(category)
    session.commit()

    response = test_client.post(
        "/api/v1/products",
        json={"sku": "SKU-001", "name": "Bolt", "category_id": category.id, "unit": "each"},
        headers=auth_headers(session, UserRole.ADMIN),
    )
    assert response.status_code == 201
    product_id = response.json()["id"]

    response = test_client.get(f"/api/v1/products/{product_id}")
    assert response.status_code == 200
    assert response.json()["sku"] == "SKU-001"


def test_supplier_read_requires_staff_and_write_requires_admin(
    client: tuple[TestClient, Session],
) -> None:
    test_client, session = client
    response = test_client.get("/api/v1/suppliers", headers=auth_headers(session, UserRole.CLIENT))
    assert response.status_code == 403

    response = test_client.post(
        "/api/v1/suppliers",
        json={"name": "Main Supplier", "email": "supplier@example.com"},
        headers=auth_headers(session, UserRole.WAREHOUSE),
    )
    assert response.status_code == 403

    response = test_client.post(
        "/api/v1/suppliers",
        json={"name": "Main Supplier", "email": "supplier@example.com"},
        headers=auth_headers(session, UserRole.ADMIN),
    )
    assert response.status_code == 201


def test_admin_can_update_and_delete_product(client: tuple[TestClient, Session]) -> None:
    test_client, session = client
    category = Category(name="Hardware")
    session.add(category)
    session.commit()
    response = test_client.post(
        "/api/v1/products",
        json={"sku": "SKU-002", "name": "Bolt", "category_id": category.id, "unit": "each"},
        headers=auth_headers(session, UserRole.ADMIN),
    )
    product_id = response.json()["id"]

    response = test_client.put(
        f"/api/v1/products/{product_id}",
        json={"sku": "SKU-002", "name": "Steel Bolt", "category_id": category.id, "unit": "box"},
        headers=auth_headers(session, UserRole.ADMIN),
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Steel Bolt"

    response = test_client.delete(
        f"/api/v1/products/{product_id}", headers=auth_headers(session, UserRole.ADMIN)
    )
    assert response.status_code == 204


def test_duplicate_product_sku_returns_conflict(client: tuple[TestClient, Session]) -> None:
    test_client, session = client
    category = Category(name="Hardware")
    session.add(category)
    session.commit()
    payload = {"sku": "DUP-001", "name": "Bolt", "category_id": category.id, "unit": "each"}
    headers = auth_headers(session, UserRole.ADMIN)
    assert test_client.post("/api/v1/products", json=payload, headers=headers).status_code == 201
    assert test_client.post("/api/v1/products", json=payload, headers=headers).status_code == 409
