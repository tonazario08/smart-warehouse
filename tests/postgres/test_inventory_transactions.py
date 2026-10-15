"""PostgreSQL-backed inventory write atomicity and API contract tests."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.auth.security import create_access_token
from app.core.errors import DomainError
from app.inventory.repository import InventoryRepository
from app.inventory.schemas import InventoryMovementCreate
from app.inventory.service import InventoryService
from app.models import (
    Category,
    Inbound,
    Outbound,
    Product,
    Stock,
    StockTransaction,
    TransactionType,
    User,
    Warehouse,
)


@pytest.fixture
def inventory_data(postgres_session: Session):
    operator = User(email="inventory-operator@example.com", password_hash="test", role="warehouse")
    admin = User(email="inventory-admin@example.com", password_hash="test", role="admin")
    client = User(email="inventory-client@example.com", password_hash="test", role="client")
    warehouse = Warehouse(code="TX-01", name="Transaction warehouse", address="Test road")
    product = Product(
        sku="TX-SKU-01",
        name="Transaction product",
        category=Category(name="Transaction"),
        unit="each",
    )
    postgres_session.add_all([operator, admin, client, warehouse, product])
    postgres_session.commit()
    service = InventoryService(InventoryRepository(postgres_session))
    return {
        "session": postgres_session,
        "operator": operator,
        "admin": admin,
        "client": client,
        "warehouse": warehouse,
        "product": product,
        "service": service,
    }


def count_rows(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_successful_movements_commit_stock_and_one_linked_business_audit(inventory_data) -> None:
    data = inventory_data
    session = data["session"]
    movement = InventoryMovementCreate(
        warehouse_id=data["warehouse"].id,
        product_id=data["product"].id,
        quantity=8,
        reference="PO-1",
        note="receipt",
    )

    inbound = data["service"].create_inbound(data["operator"].id, movement)
    outbound = data["service"].create_outbound(
        data["operator"].id, movement.model_copy(update={"quantity": 3, "reference": "SO-1"})
    )

    stock = session.scalar(select(Stock))
    assert stock is not None and stock.quantity == 5
    assert count_rows(session, Inbound) == 1
    assert count_rows(session, Outbound) == 1
    transactions = list(session.scalars(select(StockTransaction).order_by(StockTransaction.id)))
    assert [(row.transaction_type, row.inbound_id, row.outbound_id) for row in transactions] == [
        (TransactionType.INBOUND, inbound.id, None),
        (TransactionType.OUTBOUND, None, outbound.id),
    ]
    assert [row.quantity for row in transactions] == [8, 3]
    assert count_rows(session, AuditLog) == 0


def test_inbound_stock_overflow_returns_conflict_without_partial_writes(
    postgres_client, inventory_data, unit_settings
) -> None:
    data = inventory_data
    session = data["session"]
    session.add(
        Stock(
            warehouse_id=data["warehouse"].id,
            product_id=data["product"].id,
            quantity=2_147_483_647,
        )
    )
    session.commit()
    token = create_access_token(data["operator"].id, unit_settings)

    response = postgres_client.post(
        "/api/v1/inbounds",
        json={
            "warehouse_id": data["warehouse"].id,
            "product_id": data["product"].id,
            "quantity": 1,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "STOCK_QUANTITY_LIMIT_EXCEEDED"
    session.expire_all()
    assert session.scalar(select(Stock)).quantity == 2_147_483_647
    for model in (Inbound, Outbound, StockTransaction, AuditLog):
        assert count_rows(session, model) == 0


@pytest.mark.parametrize("resource", ["inbounds", "outbounds"])
@pytest.mark.parametrize("invalid", [{"quantity": 2_147_483_648}, {"reference": "R" * 121}])
def test_inventory_write_rejects_database_bound_violations_without_writes(
    postgres_client, inventory_data, unit_settings, resource: str, invalid: dict
) -> None:
    data = inventory_data
    token = create_access_token(data["operator"].id, unit_settings)
    response = postgres_client.post(
        f"/api/v1/{resource}",
        json={
            "warehouse_id": data["warehouse"].id,
            "product_id": data["product"].id,
            "quantity": 1,
            **invalid,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "REQUEST_VALIDATION_ERROR"
    assert next(iter(invalid)) in detail["fields"]
    for model in (Stock, Inbound, Outbound, StockTransaction, AuditLog):
        assert count_rows(data["session"], model) == 0


def test_rejected_outbound_rolls_back_without_partial_movement_or_audit(inventory_data) -> None:
    data = inventory_data
    session = data["session"]
    session.add(
        Stock(
            warehouse_id=data["warehouse"].id,
            product_id=data["product"].id,
            quantity=2,
        )
    )
    session.commit()
    movement = InventoryMovementCreate(
        warehouse_id=data["warehouse"].id,
        product_id=data["product"].id,
        quantity=3,
    )

    with pytest.raises(DomainError) as error:
        data["service"].create_outbound(data["operator"].id, movement)

    assert error.value.code == "INSUFFICIENT_STOCK"
    session.expire_all()
    assert session.scalar(select(Stock)).quantity == 2
    assert count_rows(session, Outbound) == 0
    assert count_rows(session, StockTransaction) == 0
    assert count_rows(session, AuditLog) == 0


def test_unexpected_failure_after_outbound_flush_rolls_back_all_writes(
    inventory_data, monkeypatch
) -> None:
    data = inventory_data
    session = data["session"]
    session.add(
        Stock(
            warehouse_id=data["warehouse"].id,
            product_id=data["product"].id,
            quantity=5,
        )
    )
    session.commit()

    def fail_transaction_insert(outbound: Outbound, actor_id: int) -> StockTransaction:
        raise RuntimeError("simulated stock-transaction persistence failure")

    monkeypatch.setattr(
        data["service"].repository,
        "add_stock_transaction_for_outbound",
        fail_transaction_insert,
    )
    movement = InventoryMovementCreate(
        warehouse_id=data["warehouse"].id,
        product_id=data["product"].id,
        quantity=3,
    )

    with pytest.raises(RuntimeError, match="simulated stock-transaction persistence failure"):
        data["service"].create_outbound(data["operator"].id, movement)

    session.expire_all()
    assert session.scalar(select(Stock)).quantity == 5
    assert count_rows(session, Outbound) == 0
    assert count_rows(session, StockTransaction) == 0
    assert count_rows(session, AuditLog) == 0


def test_inventory_write_routes_keep_response_shape_and_enforce_write_rbac(
    postgres_client, inventory_data, unit_settings
) -> None:
    data = inventory_data
    movement = {
        "warehouse_id": data["warehouse"].id,
        "product_id": data["product"].id,
        "quantity": 6,
    }
    admin_headers = {
        "Authorization": f"Bearer {create_access_token(data['admin'].id, unit_settings)}"
    }
    operator_headers = {
        "Authorization": f"Bearer {create_access_token(data['operator'].id, unit_settings)}"
    }
    client_headers = {
        "Authorization": f"Bearer {create_access_token(data['client'].id, unit_settings)}"
    }

    for resource in ("inbounds", "outbounds"):
        forbidden = postgres_client.post(
            f"/api/v1/{resource}", json=movement, headers=client_headers
        )
        assert forbidden.status_code == 403
    inbound_response = postgres_client.post(
        "/api/v1/inbounds", json=movement, headers=operator_headers
    )
    outbound_response = postgres_client.post(
        "/api/v1/outbounds",
        json={**movement, "quantity": 2},
        headers=admin_headers,
    )

    expected_fields = {"id", "warehouse_id", "product_id", "quantity", "reference", "note"}
    assert inbound_response.status_code == 201, inbound_response.text
    assert outbound_response.status_code == 201, outbound_response.text
    assert set(inbound_response.json()) == expected_fields
    assert set(outbound_response.json()) == expected_fields
