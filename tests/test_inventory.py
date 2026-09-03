from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_session
from app.main import create_app
from app.models import (
    Category,
    Inbound,
    Outbound,
    Product,
    Stock,
    StockTransaction,
    User,
    Warehouse,
)


@pytest.fixture
def inventory_client() -> Iterator[tuple[TestClient, Session, Warehouse, Product, User]]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    user = User(
        email="operator@example.com", password_hash=hash_password("password"), role="warehouse"
    )
    warehouse = Warehouse(code="HCM-01", name="Central", address="1 Nguyen Hue")
    product = Product(sku="SKU-001", name="Bolt", category=Category(name="Hardware"), unit="each")
    session.add_all([user, warehouse, product])
    session.commit()
    application = create_app()
    application.dependency_overrides[get_session] = lambda: session
    with TestClient(application) as test_client:
        yield test_client, session, warehouse, product, user
    session.close()
    engine.dispose()


def auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def test_inbound_increments_stock_and_writes_audit_transaction(
    inventory_client: tuple[TestClient, Session, Warehouse, Product, User],
) -> None:
    test_client, session, warehouse, product, user = inventory_client

    response = test_client.post(
        "/api/v1/inbounds",
        json={"warehouse_id": warehouse.id, "product_id": product.id, "quantity": 12},
        headers=auth(user),
    )

    assert response.status_code == 201
    assert session.scalar(select(Stock).where(Stock.warehouse_id == warehouse.id)).quantity == 12
    assert session.scalar(select(Inbound)) is not None
    transaction = session.scalar(select(StockTransaction))
    assert transaction is not None
    assert transaction.transaction_type.value == "inbound"


def test_outbound_decrements_stock_and_rejects_insufficient_quantity(
    inventory_client: tuple[TestClient, Session, Warehouse, Product, User],
) -> None:
    test_client, session, warehouse, product, user = inventory_client
    session.add(Stock(warehouse_id=warehouse.id, product_id=product.id, quantity=5))
    session.commit()

    response = test_client.post(
        "/api/v1/outbounds",
        json={"warehouse_id": warehouse.id, "product_id": product.id, "quantity": 3},
        headers=auth(user),
    )
    assert response.status_code == 201
    assert session.scalar(select(Stock).where(Stock.warehouse_id == warehouse.id)).quantity == 2

    response = test_client.post(
        "/api/v1/outbounds",
        json={"warehouse_id": warehouse.id, "product_id": product.id, "quantity": 10},
        headers=auth(user),
    )
    assert response.status_code == 409
    assert session.scalar(select(Outbound)).quantity == 3
    assert len(session.scalars(select(StockTransaction)).all()) == 1


def test_stock_list_is_read_only_and_available_to_inventory_read_roles(
    inventory_client: tuple[TestClient, Session, Warehouse, Product, User],
) -> None:
    test_client, session, warehouse, product, user = inventory_client
    session.add(Stock(warehouse_id=warehouse.id, product_id=product.id, quantity=5))
    session.commit()

    response = test_client.get(
        f"/api/v1/stock?warehouse_id={warehouse.id}", headers=auth(user)
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": session.scalar(select(Stock.id)),
            "warehouse_id": warehouse.id,
            "product_id": product.id,
            "quantity": 5,
        }
    ]
