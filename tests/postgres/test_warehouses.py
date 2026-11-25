"""PostgreSQL-backed warehouse API and protected-delete contract tests."""

import pytest
from sqlalchemy.orm import Session

from app.auth.security import create_access_token
from app.models import (
    Category,
    Inbound,
    Outbound,
    Product,
    PurchaseRequest,
    RouteLog,
    Stock,
    StockTransaction,
    TransactionType,
    User,
    UserRole,
    Warehouse,
)
from app.warehouse.repository import WarehouseRepository


@pytest.fixture
def role_headers(postgres_session: Session, unit_settings) -> dict[UserRole, dict[str, str]]:
    headers: dict[UserRole, dict[str, str]] = {}
    for role in UserRole:
        user = User(email=f"{role.value}@example.com", password_hash="test-hash", role=role)
        postgres_session.add(user)
        postgres_session.flush()
        headers[role] = {"Authorization": f"Bearer {create_access_token(user.id, unit_settings)}"}
    postgres_session.commit()
    return headers


def create_warehouse(postgres_client, headers, code: str, **fields):
    payload = {"code": code, "name": f"{code} warehouse", "address": f"{code} road"}
    payload.update(fields)
    response = postgres_client.post("/api/v1/warehouses", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_warehouse_reads_require_authentication_and_allow_all_roles(
    postgres_client, role_headers
):
    anonymous = postgres_client.get("/api/v1/warehouses")
    assert anonymous.json()["detail"]["code"] == "AUTHENTICATION_REQUIRED"
    warehouse = create_warehouse(postgres_client, role_headers[UserRole.ADMIN], "HCM-01")

    for role in UserRole:
        response = postgres_client.get("/api/v1/warehouses", headers=role_headers[role])
        detail = postgres_client.get(
            f"/api/v1/warehouses/{warehouse['id']}", headers=role_headers[role]
        )
        assert response.status_code == 200
        assert warehouse in response.json()["items"]
        assert detail.status_code == 200
        assert detail.json() == warehouse


@pytest.mark.parametrize("method", ["post", "put", "delete"])
@pytest.mark.parametrize("role", [UserRole.WAREHOUSE, UserRole.CLIENT, None])
def test_warehouse_mutations_are_admin_only(postgres_client, role_headers, method, role):
    admin = role_headers[UserRole.ADMIN]
    warehouse = create_warehouse(postgres_client, admin, "LOCKED")
    options = {"headers": role_headers[role] if role is not None else None}
    path = "/api/v1/warehouses"
    if method == "post":
        options["json"] = {"code": "OTHER", "name": "Other", "address": "Other road"}
    else:
        path = f"{path}/{warehouse['id']}"
        if method == "put":
            options["json"] = {"code": "LOCKED", "name": "Changed", "address": "New road"}

    response = getattr(postgres_client, method)(path, **options)
    assert response.status_code == (401 if role is None else 403)


@pytest.mark.parametrize(
    "coordinates",
    [
        {"latitude": 10.0},
        {"longitude": 106.0},
        {"latitude": -90.01, "longitude": 0},
        {"latitude": 90.01, "longitude": 0},
        {"latitude": 0, "longitude": -180.01},
        {"latitude": 0, "longitude": 180.01},
    ],
)
def test_invalid_warehouse_coordinates_return_stable_validation_error(
    postgres_client, role_headers, coordinates
):
    response = postgres_client.post(
        "/api/v1/warehouses",
        headers=role_headers[UserRole.ADMIN],
        json={"code": "BAD-COORD", "name": "Bad Coordinates", "address": "Road", **coordinates},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "REQUEST_VALIDATION_ERROR"


def test_warehouse_coordinates_can_be_omitted_or_at_inclusive_bounds(
    postgres_client, role_headers
):
    headers = role_headers[UserRole.ADMIN]
    omitted = create_warehouse(postgres_client, headers, "NO-COORD")
    bounded = create_warehouse(
        postgres_client, headers, "EDGE-COORD", latitude=-90, longitude=180
    )

    assert omitted["latitude"] is None and omitted["longitude"] is None
    assert bounded["latitude"] == -90 and bounded["longitude"] == 180


@pytest.mark.parametrize(
    "payload",
    [
        {"code": "X", "name": "Name", "address": "Road", "extra": True},
        {"code": "X", "name": "   ", "address": "Road"},
        {"code": "X", "name": "Name", "address": "  "},
    ],
)
def test_warehouse_create_rejects_extra_and_blank_fields(postgres_client, role_headers, payload):
    response = postgres_client.post(
        "/api/v1/warehouses", headers=role_headers[UserRole.ADMIN], json=payload
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "REQUEST_VALIDATION_ERROR"


def test_warehouse_create_normalizes_code_and_text_and_returns_utc_timestamps(
    postgres_client, role_headers
):
    warehouse = create_warehouse(
        postgres_client,
        role_headers[UserRole.ADMIN],
        "  hcm-02 ",
        name="  South Hub  ",
        address="  2 Le Loi  ",
    )

    assert warehouse["code"] == "HCM-02"
    assert warehouse["name"] == "South Hub"
    assert warehouse["address"] == "2 Le Loi"
    assert warehouse["created_at"].endswith("Z") or warehouse["created_at"].endswith("+00:00")
    assert warehouse["updated_at"].endswith("Z") or warehouse["updated_at"].endswith("+00:00")


def test_warehouse_search_pagination_and_count_share_filters(postgres_client, role_headers):
    headers = role_headers[UserRole.ADMIN]
    first = create_warehouse(postgres_client, headers, "HCM-A", name="Central Hub")
    create_warehouse(postgres_client, headers, "HN-B", name="North Depot", address="Central road")
    create_warehouse(postgres_client, headers, "DN-C", name="East Depot")

    filtered = postgres_client.get(
        "/api/v1/warehouses?search=CENTRAL&page=1&page_size=1", headers=headers
    )
    next_page = postgres_client.get(
        "/api/v1/warehouses?search=central&page=2&page_size=1", headers=headers
    )

    assert filtered.status_code == 200
    assert filtered.json()["total"] == 2
    assert filtered.json()["items"] == [first]
    assert next_page.json()["total"] == 2
    assert next_page.json()["items"][0]["address"] == "Central road"


def test_warehouse_conflict_missing_errors_and_update_rollback_are_stable(
    postgres_client, postgres_session: Session, role_headers
):
    headers = role_headers[UserRole.ADMIN]
    first = create_warehouse(postgres_client, headers, "DUP-CODE", name="First Warehouse")
    second = create_warehouse(postgres_client, headers, "SECOND", name="Second Warehouse")
    conflict = postgres_client.post(
        "/api/v1/warehouses", headers=headers,
        json={"code": " dup-code ", "name": "Third Warehouse", "address": "Road"},
    )
    update_conflict = postgres_client.put(
        f"/api/v1/warehouses/{second['id']}", headers=headers,
        json={"code": "SECOND-CHANGED", "name": first["name"], "address": "Changed road"},
    )
    missing_get = postgres_client.get("/api/v1/warehouses/987654", headers=headers)
    missing_update = postgres_client.put(
        "/api/v1/warehouses/987654", headers=headers,
        json={"code": "MISSING", "name": "Missing", "address": "Road"},
    )
    missing_delete = postgres_client.delete("/api/v1/warehouses/987654", headers=headers)
    postgres_session.expire_all()
    persisted = postgres_session.get(Warehouse, second["id"])

    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "WAREHOUSE_CONFLICT"
    assert update_conflict.status_code == 409
    assert update_conflict.json()["detail"]["code"] == "WAREHOUSE_CONFLICT"
    assert persisted.code == "SECOND" and persisted.name == "Second Warehouse"
    for response in (missing_get, missing_update, missing_delete):
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "WAREHOUSE_NOT_FOUND"


@pytest.mark.parametrize(
    "reference_table",
    ["stocks", "inbounds", "outbounds", "transactions", "purchase_requests", "route_logs"],
)
def test_warehouse_delete_in_use_preserves_each_reference(
    postgres_client, postgres_session: Session, role_headers, reference_table: str
):
    admin_headers = role_headers[UserRole.ADMIN]
    admin = postgres_session.query(User).filter_by(role=UserRole.ADMIN).one()
    warehouse = Warehouse(code="IN-USE", name="In Use Warehouse", address="Reference road")
    category = Category(name="Warehouse reference category")
    postgres_session.add(category)
    postgres_session.flush()
    product = Product(
        sku="WH-REFERENCE", name="Reference product", category_id=category.id, unit="each"
    )
    postgres_session.add_all([warehouse, product])
    postgres_session.flush()

    if reference_table == "transactions":
        movement_warehouse = Warehouse(
            code="MOVEMENT", name="Movement Warehouse", address="Movement road"
        )
        postgres_session.add(movement_warehouse)
        postgres_session.flush()
        movement = Inbound(
            warehouse_id=movement_warehouse.id,
            product_id=product.id,
            quantity=1,
            created_by_id=admin.id,
        )
        postgres_session.add(movement)
        postgres_session.flush()
        reference = StockTransaction(
            transaction_type=TransactionType.INBOUND,
            warehouse_id=warehouse.id,
            product_id=product.id,
            quantity=1,
            inbound_id=movement.id,
            created_by_id=admin.id,
        )
    elif reference_table == "stocks":
        reference = Stock(warehouse_id=warehouse.id, product_id=product.id, quantity=1)
    elif reference_table == "inbounds":
        reference = Inbound(
            warehouse_id=warehouse.id, product_id=product.id, quantity=1, created_by_id=admin.id
        )
    elif reference_table == "outbounds":
        reference = Outbound(
            warehouse_id=warehouse.id, product_id=product.id, quantity=1, created_by_id=admin.id
        )
    elif reference_table == "purchase_requests":
        reference = PurchaseRequest(
            request_number="REQ-WH-REFERENCE", warehouse_id=warehouse.id,
            product_id=product.id, quantity=1, requested_by_id=admin.id,
        )
    else:
        reference = RouteLog(warehouse_id=warehouse.id, created_by_id=admin.id)
    postgres_session.add(reference)
    postgres_session.commit()
    warehouse_id, reference_id = warehouse.id, reference.id
    assert WarehouseRepository(postgres_session).has_references(warehouse_id)

    response = postgres_client.delete(f"/api/v1/warehouses/{warehouse_id}", headers=admin_headers)
    postgres_session.expire_all()

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "WAREHOUSE_IN_USE"
    assert postgres_session.get(Warehouse, warehouse_id) is not None
    assert postgres_session.get(type(reference), reference_id) is not None
