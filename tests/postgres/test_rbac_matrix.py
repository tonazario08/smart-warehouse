"""PostgreSQL-backed success and denial coverage for Phase 1 route actions."""

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.auth.dependencies import PERMISSION_ROLES, Permission
from app.auth.security import create_access_token, hash_password
from app.models import (
    AuditLog,
    Category,
    Inbound,
    Outbound,
    Product,
    Stock,
    StockTransaction,
    Supplier,
    TransactionType,
    User,
    UserRole,
    Warehouse,
)


def test_central_permission_mapping_matches_phase_one_capabilities() -> None:
    admin = frozenset({UserRole.ADMIN})
    warehouse = frozenset({UserRole.ADMIN, UserRole.WAREHOUSE})
    all_users = frozenset(UserRole)
    assert PERMISSION_ROLES == {
        Permission.CATALOG_READ: all_users,
        Permission.PRODUCT_WRITE: admin,
        Permission.SUPPLIER_READ: warehouse,
        Permission.SUPPLIER_WRITE: admin,
        Permission.WAREHOUSE_READ: all_users,
        Permission.WAREHOUSE_WRITE: admin,
        Permission.INVENTORY_READ: all_users,
        Permission.INVENTORY_HISTORY_READ: warehouse,
        Permission.INVENTORY_WRITE: warehouse,
        Permission.DASHBOARD_READ: admin,
        Permission.USER_MANAGE: admin,
        Permission.AUDIT_READ: admin,
    }


@pytest.fixture
def rbac_dataset(postgres_session: Session, unit_settings):
    password_hash = hash_password("strong-password-1")
    users = {
        role: User(
            email=f"matrix-{role.value}@example.com",
            password_hash=password_hash,
            role=role,
        )
        for role in UserRole
    }
    category = Category(name="Matrix category")
    free_category = Category(name="Matrix delete category")
    supplier = Supplier(name="Matrix supplier", email="matrix-supplier@example.com")
    free_supplier = Supplier(name="Matrix delete supplier", email="delete-supplier@example.com")
    product = Product(
        sku="MATRIX-001",
        name="Matrix product",
        category=category,
        supplier=supplier,
        unit="each",
        reorder_level=5,
    )
    delete_product = Product(
        sku="MATRIX-DELETE",
        name="Delete product",
        category=category,
        unit="each",
    )
    warehouse = Warehouse(code="MATRIX-01", name="Matrix warehouse", address="Matrix road")
    free_warehouse = Warehouse(code="MATRIX-DELETE", name="Delete warehouse", address="Delete road")
    postgres_session.add_all(
        [
            *users.values(),
            category,
            free_category,
            supplier,
            free_supplier,
            product,
            delete_product,
            warehouse,
            free_warehouse,
        ]
    )
    postgres_session.flush()
    inbound = Inbound(
        warehouse_id=warehouse.id,
        product_id=product.id,
        quantity=20,
        reference="MATRIX-IN",
        created_by_id=users[UserRole.WAREHOUSE].id,
    )
    outbound = Outbound(
        warehouse_id=warehouse.id,
        product_id=product.id,
        quantity=2,
        reference="MATRIX-OUT",
        created_by_id=users[UserRole.WAREHOUSE].id,
    )
    postgres_session.add_all([inbound, outbound])
    postgres_session.flush()
    stock = Stock(warehouse_id=warehouse.id, product_id=product.id, quantity=18)
    inbound_transaction = StockTransaction(
        transaction_type=TransactionType.INBOUND,
        warehouse_id=warehouse.id,
        product_id=product.id,
        quantity=inbound.quantity,
        inbound_id=inbound.id,
        created_by_id=inbound.created_by_id,
    )
    outbound_transaction = StockTransaction(
        transaction_type=TransactionType.OUTBOUND,
        warehouse_id=warehouse.id,
        product_id=product.id,
        quantity=outbound.quantity,
        outbound_id=outbound.id,
        created_by_id=outbound.created_by_id,
    )
    postgres_session.add_all([stock, inbound_transaction, outbound_transaction])
    postgres_session.flush()
    audit = AuditLog(
        actor_user_id=users[UserRole.ADMIN].id,
        action="user.created",
        target_type="user",
        target_id=users[UserRole.CLIENT].id,
        after_data={"email": users[UserRole.CLIENT].email, "role": "client", "is_active": True},
    )
    postgres_session.add(audit)
    postgres_session.commit()

    return {
        "users": users,
        "headers": {
            role: {"Authorization": f"Bearer {create_access_token(user.id, unit_settings)}"}
            for role, user in users.items()
        },
        "category": category,
        "free_category": free_category,
        "supplier": supplier,
        "free_supplier": free_supplier,
        "product": product,
        "delete_product": delete_product,
        "warehouse": warehouse,
        "free_warehouse": free_warehouse,
        "stock": stock,
        "inbound": inbound,
        "outbound": outbound,
        "inbound_transaction": inbound_transaction,
        "audit": audit,
    }


def _mutation_tables(path_key: str) -> tuple[type, ...]:
    if path_key in {"/api/v1/products", "product", "delete_product"}:
        return (Product,)
    if path_key in {"/api/v1/categories", "category", "free_category"}:
        return (Category,)
    if path_key in {"/api/v1/suppliers", "supplier", "free_supplier"}:
        return (Supplier,)
    if path_key in {"/api/v1/warehouses", "warehouse", "free_warehouse"}:
        return (Warehouse,)
    if path_key in {"/api/v1/inbounds", "/api/v1/outbounds"}:
        return (Stock, Inbound, Outbound, StockTransaction)
    if path_key in {"/api/v1/users", "role_user", "status_user"}:
        return (User, AuditLog)
    raise AssertionError(f"no persisted-state snapshot is defined for {path_key}")


def _persisted_state_snapshot(engine: Engine, path_key: str) -> dict[str, tuple[tuple, ...]]:
    snapshot = {}
    with Session(engine) as session:
        for model in _mutation_tables(path_key):
            mapper = inspect(model)
            columns = [getattr(model, column.key) for column in mapper.column_attrs]
            rows = session.execute(select(*columns).order_by(*mapper.primary_key)).all()
            snapshot[model.__tablename__] = tuple(tuple(row) for row in rows)
    return snapshot


_ROUTE_ACTIONS = [
        ("products list", "get", "/api/v1/products", set(UserRole), 200, None),
        ("product detail", "get", "product", set(UserRole), 200, None),
        ("product create", "post", "/api/v1/products", {UserRole.ADMIN}, 201, "product"),
        ("product update", "put", "product", {UserRole.ADMIN}, 200, "product"),
        ("product delete", "delete", "delete_product", {UserRole.ADMIN}, 204, None),
        ("categories list", "get", "/api/v1/categories", set(UserRole), 200, None),
        ("category detail", "get", "category", set(UserRole), 200, None),
        ("category create", "post", "/api/v1/categories", {UserRole.ADMIN}, 201, "category"),
        ("category update", "put", "category", {UserRole.ADMIN}, 200, "category"),
        ("category delete", "delete", "free_category", {UserRole.ADMIN}, 204, None),
        (
            "suppliers list",
            "get",
            "/api/v1/suppliers",
            {UserRole.ADMIN, UserRole.WAREHOUSE},
            200,
            None,
        ),
        ("supplier detail", "get", "supplier", {UserRole.ADMIN, UserRole.WAREHOUSE}, 200, None),
        ("supplier create", "post", "/api/v1/suppliers", {UserRole.ADMIN}, 201, "supplier"),
        ("supplier update", "put", "supplier", {UserRole.ADMIN}, 200, "supplier"),
        ("supplier delete", "delete", "free_supplier", {UserRole.ADMIN}, 204, None),
        ("warehouses list", "get", "/api/v1/warehouses", set(UserRole), 200, None),
        ("warehouse detail", "get", "warehouse", set(UserRole), 200, None),
        ("warehouse create", "post", "/api/v1/warehouses", {UserRole.ADMIN}, 201, "warehouse"),
        ("warehouse update", "put", "warehouse", {UserRole.ADMIN}, 200, "warehouse"),
        ("warehouse delete", "delete", "free_warehouse", {UserRole.ADMIN}, 204, None),
        ("stock list", "get", "/api/v1/stock", set(UserRole), 200, None),
        ("stock detail", "get", "stock", set(UserRole), 200, None),
        (
            "inbound list",
            "get",
            "/api/v1/inbounds",
            {UserRole.ADMIN, UserRole.WAREHOUSE},
            200,
            None,
        ),
        ("inbound detail", "get", "inbound", {UserRole.ADMIN, UserRole.WAREHOUSE}, 200, None),
        (
            "inbound create",
            "post",
            "/api/v1/inbounds",
            {UserRole.ADMIN, UserRole.WAREHOUSE},
            201,
            "movement",
        ),
        (
            "outbound list",
            "get",
            "/api/v1/outbounds",
            {UserRole.ADMIN, UserRole.WAREHOUSE},
            200,
            None,
        ),
        ("outbound detail", "get", "outbound", {UserRole.ADMIN, UserRole.WAREHOUSE}, 200, None),
        (
            "outbound create",
            "post",
            "/api/v1/outbounds",
            {UserRole.ADMIN, UserRole.WAREHOUSE},
            201,
            "movement",
        ),
        (
            "transaction list",
            "get",
            "/api/v1/transactions",
            {UserRole.ADMIN, UserRole.WAREHOUSE},
            200,
            None,
        ),
        (
            "transaction detail",
            "get",
            "inbound_transaction",
            {UserRole.ADMIN, UserRole.WAREHOUSE},
            200,
            None,
        ),
        ("dashboard stats", "get", "/api/v1/dashboard/stats", {UserRole.ADMIN}, 200, None),
        ("current user", "get", "/api/v1/auth/me", set(UserRole), 200, None),
        ("users list", "get", "/api/v1/users", {UserRole.ADMIN}, 200, None),
        ("user detail", "get", "client_user", {UserRole.ADMIN}, 200, None),
        ("user create", "post", "/api/v1/users", {UserRole.ADMIN}, 201, "user"),
        ("user role update", "patch", "role_user", {UserRole.ADMIN}, 200, "role"),
        ("user status update", "patch", "status_user", {UserRole.ADMIN}, 200, "status"),
        ("audit list", "get", "/api/v1/audit-logs", {UserRole.ADMIN}, 200, None),
        ("audit detail", "get", "audit", {UserRole.ADMIN}, 200, None),
]


@pytest.mark.parametrize(
    ("name", "method", "path_key", "allowed", "success_status", "payload_key", "role"),
    [(*action, role) for action in _ROUTE_ACTIONS for role in UserRole],
)
def test_route_action_matrix_uses_valid_success_payloads_for_each_allowed_role(
    postgres_client,
    postgres_engine,
    rbac_dataset,
    name: str,
    method: str,
    path_key: str,
    allowed: set[UserRole],
    success_status: int,
    payload_key: str | None,
    role: UserRole,
) -> None:
    data = rbac_dataset
    targets = {
        "product": f"/api/v1/products/{data['product'].id}",
        "delete_product": f"/api/v1/products/{data['delete_product'].id}",
        "category": f"/api/v1/categories/{data['category'].id}",
        "free_category": f"/api/v1/categories/{data['free_category'].id}",
        "supplier": f"/api/v1/suppliers/{data['supplier'].id}",
        "free_supplier": f"/api/v1/suppliers/{data['free_supplier'].id}",
        "warehouse": f"/api/v1/warehouses/{data['warehouse'].id}",
        "free_warehouse": f"/api/v1/warehouses/{data['free_warehouse'].id}",
        "stock": f"/api/v1/stock/{data['stock'].id}",
        "inbound": f"/api/v1/inbounds/{data['inbound'].id}",
        "outbound": f"/api/v1/outbounds/{data['outbound'].id}",
        "inbound_transaction": f"/api/v1/transactions/{data['inbound_transaction'].id}",
        "client_user": f"/api/v1/users/{data['users'][UserRole.CLIENT].id}",
        "role_user": f"/api/v1/users/{data['users'][UserRole.CLIENT].id}/role",
        "status_user": f"/api/v1/users/{data['users'][UserRole.WAREHOUSE].id}/status",
        "audit": f"/api/v1/audit-logs/{data['audit'].id}",
    }
    path = targets.get(path_key, path_key)
    payloads = {
        "product": {
            "sku": "MATRIX-NEW",
            "name": "Updated matrix product",
            "category_id": data["category"].id,
            "unit": "each",
            "reorder_level": 5,
        },
        "category": {"name": "Updated matrix category"},
        "supplier": {"name": "Updated matrix supplier", "email": "updated@example.com"},
        "warehouse": {
            "code": "MATRIX-UPDATED",
            "name": "Updated matrix warehouse",
            "address": "Updated road",
        },
        "movement": {
            "warehouse_id": data["warehouse"].id,
            "product_id": data["product"].id,
            "quantity": 1,
            "reference": f"{name}-movement",
        },
        "user": {
            "email": "matrix-created@example.com",
            "password": "strong-password-1",
            "role": "client",
        },
        "role": {"role": "warehouse"},
        "status": {"is_active": False},
    }
    if path_key == "/api/v1/products":
        payloads["product"] = {
            "sku": "MATRIX-CREATED",
            "name": "Created matrix product",
            "category_id": data["category"].id,
            "unit": "each",
        }
    if path_key == "/api/v1/categories":
        payloads["category"] = {"name": "Created matrix category"}
    if path_key == "/api/v1/suppliers":
        payloads["supplier"] = {"name": "Created matrix supplier", "email": "created@example.com"}
    if path_key == "/api/v1/warehouses":
        payloads["warehouse"] = {
            "code": "MATRIX-CREATED",
            "name": "Created matrix warehouse",
            "address": "Created road",
        }

    def send(role: UserRole):
        current_path = path
        json_payload = payloads[payload_key].copy() if payload_key else None
        if payload_key == "movement":
            json_payload["reference"] += f"-{role.value}"
        if payload_key == "user":
            json_payload["email"] = f"matrix-created-{role.value}@example.com"
        options = {"headers": data["headers"][role]}
        if json_payload is not None:
            options["json"] = json_payload
        if method == "delete":
            return postgres_client.delete(current_path, **options)
        return getattr(postgres_client, method)(current_path, **options)

    is_allowed = role in allowed
    is_mutation = method in {"post", "put", "patch", "delete"}
    before = (
        _persisted_state_snapshot(postgres_engine, path_key)
        if is_mutation and not is_allowed
        else None
    )
    response = send(role)
    expected_status = success_status if is_allowed else 403
    assert response.status_code == expected_status, (
        f"{name}, role={role.value}: {response.status_code} {response.text}"
    )
    if is_mutation and not is_allowed:
        after = _persisted_state_snapshot(postgres_engine, path_key)
        assert after == before, f"{name}, denied role={role.value} changed persisted state"


def test_anonymous_requests_cannot_access_sensitive_phase_one_routes(postgres_client) -> None:
    for path in (
        "/api/v1/products",
        "/api/v1/warehouses",
        "/api/v1/stock",
        "/api/v1/inbounds",
        "/api/v1/dashboard/stats",
        "/api/v1/users",
        "/api/v1/audit-logs",
    ):
        assert postgres_client.get(path).status_code == 401, path


def test_public_registration_and_managed_user_creation_cannot_assign_admin(
    postgres_client, rbac_dataset
) -> None:
    registration = postgres_client.post(
        "/api/v1/auth/register",
        json={
            "email": "public-admin@example.com",
            "password": "strong-password-1",
            "role": "admin",
        },
    )
    managed = postgres_client.post(
        "/api/v1/users",
        headers=rbac_dataset["headers"][UserRole.ADMIN],
        json={
            "email": "managed-admin@example.com",
            "password": "strong-password-1",
            "role": "admin",
        },
    )

    assert registration.status_code == 422
    assert registration.json()["detail"]["code"] == "REQUEST_VALIDATION_ERROR"
    assert managed.status_code == 422
    assert managed.json()["detail"]["code"] == "REQUEST_VALIDATION_ERROR"


def test_public_registration_and_login_complete_the_anonymous_auth_routes(postgres_client) -> None:
    registration = postgres_client.post(
        "/api/v1/auth/register",
        json={"email": "matrix-public@example.com", "password": "strong-password-1"},
    )
    login = postgres_client.post(
        "/api/v1/auth/login",
        json={"email": "matrix-public@example.com", "password": "strong-password-1"},
    )

    assert registration.status_code == 201
    assert registration.json()["role"] == "client"
    assert login.status_code == 200
    assert login.json()["user"]["email"] == "matrix-public@example.com"
    assert "access_token" in login.json()
