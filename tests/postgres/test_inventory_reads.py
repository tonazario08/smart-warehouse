"""PostgreSQL-backed inventory read API contract tests."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.auth.security import create_access_token
from app.models import (
    Category,
    Inbound,
    Outbound,
    Product,
    Stock,
    StockTransaction,
    TransactionType,
    User,
    UserRole,
    Warehouse,
)


@pytest.fixture
def inventory_roles(postgres_session: Session, unit_settings):
    headers = {}
    users = {}
    for role in UserRole:
        user = User(email=f"inventory-{role.value}@example.com", password_hash="test", role=role)
        postgres_session.add(user)
        postgres_session.flush()
        users[role] = user
        headers[role] = {"Authorization": f"Bearer {create_access_token(user.id, unit_settings)}"}
    warehouse = Warehouse(code="INV-01", name="Inventory warehouse", address="Warehouse road")
    category = Category(name="Inventory category")
    product = Product(
        sku="INV-SKU-01", name="Inventory product", category=category, unit="each"
    )
    postgres_session.add_all([warehouse, product])
    postgres_session.flush()

    created_at = datetime(2026, 1, 1, tzinfo=UTC)
    inbound_rows = [
        Inbound(
            warehouse_id=warehouse.id,
            product_id=product.id,
            quantity=quantity,
            reference=f"IN-{index}",
            note=f"Inbound {index}",
            created_by_id=users[UserRole.WAREHOUSE].id,
            created_at=created_at + timedelta(days=index),
        )
        for index, quantity in enumerate((5, 7), start=1)
    ]
    outbound = Outbound(
        warehouse_id=warehouse.id,
        product_id=product.id,
        quantity=3,
        reference="OUT-1",
        note="Outbound 1",
        created_by_id=users[UserRole.WAREHOUSE].id,
        created_at=created_at + timedelta(days=3),
    )
    postgres_session.add_all([*inbound_rows, outbound])
    postgres_session.flush()
    transactions = [
        StockTransaction(
            transaction_type=TransactionType.INBOUND,
            warehouse_id=warehouse.id,
            product_id=product.id,
            quantity=inbound.quantity,
            inbound_id=inbound.id,
            created_by_id=inbound.created_by_id,
            created_at=inbound.created_at,
        )
        for inbound in inbound_rows
    ]
    transactions.append(
        StockTransaction(
            transaction_type=TransactionType.OUTBOUND,
            warehouse_id=warehouse.id,
            product_id=product.id,
            quantity=outbound.quantity,
            outbound_id=outbound.id,
            created_by_id=outbound.created_by_id,
            created_at=outbound.created_at,
        )
    )
    stock = Stock(warehouse_id=warehouse.id, product_id=product.id, quantity=9)
    postgres_session.add_all([*transactions, stock])
    postgres_session.commit()
    return {
        "headers": headers,
        "warehouse": warehouse,
        "product": product,
        "inbounds": inbound_rows,
        "outbound": outbound,
        "transactions": transactions,
        "stock": stock,
    }


@pytest.mark.parametrize("resource", ["stock", "inbounds", "outbounds", "transactions"])
def test_inventory_collections_are_paginated_filtered_and_have_count_parity(
    postgres_client, inventory_roles, resource
):
    data = inventory_roles
    response = postgres_client.get(
        f"/api/v1/{resource}?page=1&page_size=1&warehouse_id={data['warehouse'].id}",
        headers=data["headers"][UserRole.WAREHOUSE],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size"}
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert len(body["items"]) == 1
    assert body["total"] == {"stock": 1, "inbounds": 2, "outbounds": 1, "transactions": 3}[resource]


@pytest.mark.parametrize(
    ("resource", "row_key"),
    [
        ("stock", "stock"),
        ("inbounds", "inbounds"),
        ("outbounds", "outbound"),
        ("transactions", "transactions"),
    ],
)
def test_inventory_detail_routes_return_only_read_contract_fields(
    postgres_client, inventory_roles, resource, row_key
):
    data = inventory_roles
    record = data[row_key][0] if isinstance(data[row_key], list) else data[row_key]
    response = postgres_client.get(
        f"/api/v1/{resource}/{record.id}", headers=data["headers"][UserRole.WAREHOUSE]
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == record.id
    assert body["warehouse_id"] == data["warehouse"].id
    assert body["product_id"] == data["product"].id
    assert body["quantity"] == record.quantity
    assert (
        datetime.fromisoformat(body["created_at"].replace("Z", "+00:00")).utcoffset()
        == UTC.utcoffset(None)
    )
    if resource == "stock":
        assert set(body) == {"id", "warehouse_id", "product_id", "quantity", "created_at"}
    else:
        assert "created_by_id" in body
    if resource == "transactions":
        assert set(body) == {
            "id",
            "transaction_type",
            "warehouse_id",
            "product_id",
            "quantity",
            "inbound_id",
            "outbound_id",
            "created_by_id",
            "created_at",
        }
        assert body["transaction_type"] == record.transaction_type.value
        assert "inbound_id" in body
        assert "outbound_id" in body
    elif resource != "stock":
        assert set(body) == {
            "id",
            "warehouse_id",
            "product_id",
            "quantity",
            "reference",
            "note",
            "created_by_id",
            "created_at",
        }
        assert body["reference"] == record.reference
        assert body["note"] == record.note


def test_inventory_filters_use_same_predicates_for_items_and_total(
    postgres_client, inventory_roles
):
    data = inventory_roles
    warehouse = data["warehouse"].id
    product = data["product"].id
    response = postgres_client.get(
        f"/api/v1/transactions?warehouse_id={warehouse}&product_id={product}"
        "&transaction_type=inbound&created_from=2026-01-02T00:00:00Z"
        "&created_to=2026-01-02T23:59:59Z",
        headers=data["headers"][UserRole.WAREHOUSE],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert [item["quantity"] for item in body["items"]] == [5]


@pytest.mark.parametrize(
    "query",
    [
        "warehouse_id=0",
        "product_id=-1",
        "created_from=2026-01-03T00:00:00Z&created_to=2026-01-02T00:00:00Z",
        "created_from=2026-01-01T00:00:00",
        "unexpected=1",
    ],
)
def test_invalid_inventory_filters_return_validation_error(postgres_client, inventory_roles, query):
    response = postgres_client.get(
        f"/api/v1/stock?{query}", headers=inventory_roles["headers"][UserRole.ADMIN]
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "REQUEST_VALIDATION_ERROR"


def test_transaction_filter_rejects_unknown_transaction_type(postgres_client, inventory_roles):
    response = postgres_client.get(
        "/api/v1/transactions?transaction_type=transfer",
        headers=inventory_roles["headers"][UserRole.ADMIN],
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "REQUEST_VALIDATION_ERROR"


@pytest.mark.parametrize(
    ("resource", "error_code"),
    [
        ("stock", "STOCK_NOT_FOUND"),
        ("inbounds", "INBOUND_NOT_FOUND"),
        ("outbounds", "OUTBOUND_NOT_FOUND"),
        ("transactions", "TRANSACTION_NOT_FOUND"),
    ],
)
def test_inventory_detail_missing_records_have_resource_specific_errors(
    postgres_client, inventory_roles, resource, error_code
):
    response = postgres_client.get(
        f"/api/v1/{resource}/999999", headers=inventory_roles["headers"][UserRole.WAREHOUSE]
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == error_code


def test_stock_reads_allow_all_roles_but_movement_history_is_admin_and_warehouse_only(
    postgres_client, inventory_roles
):
    for role in UserRole:
        assert postgres_client.get(
            "/api/v1/stock", headers=inventory_roles["headers"][role]
        ).status_code == 200

        for resource in ("inbounds", "outbounds", "transactions"):
            response = postgres_client.get(
                f"/api/v1/{resource}", headers=inventory_roles["headers"][role]
            )
            assert response.status_code == (403 if role == UserRole.CLIENT else 200)

    assert (
        postgres_client.get("/api/v1/stock").json()["detail"]["code"]
        == "AUTHENTICATION_REQUIRED"
    )
    assert postgres_client.get("/api/v1/inbounds").status_code == 401


def test_inventory_history_is_ordered_newest_first_and_stably_by_id(
    postgres_client, inventory_roles, postgres_session: Session
):
    data = inventory_roles
    data["transactions"][1].created_at = data["transactions"][0].created_at
    postgres_session.commit()
    response = postgres_client.get(
        "/api/v1/transactions", headers=data["headers"][UserRole.WAREHOUSE]
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [
        item.id
        for item in sorted(
            data["transactions"],
            key=lambda item: (item.created_at, item.id),
            reverse=True,
        )
    ]
