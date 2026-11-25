"""PostgreSQL-backed product API and transaction contract tests."""

import pytest
from sqlalchemy.orm import Session

from app.auth.security import create_access_token
from app.master_data.repository import ProductRepository
from app.models import (
    Category,
    Inbound,
    Outbound,
    Product,
    PurchaseRequest,
    Stock,
    StockTransaction,
    Supplier,
    TransactionType,
    User,
    UserRole,
    Warehouse,
)


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


@pytest.fixture
def category(postgres_session: Session) -> Category:
    value = Category(name="Hardware")
    postgres_session.add(value)
    postgres_session.commit()
    return value


def create_product(postgres_client, headers, category_id: int, sku: str, **fields):
    payload = {"sku": sku, "name": "Bolt", "category_id": category_id, "unit": "each"}
    payload.update(fields)
    response = postgres_client.post(
        "/api/v1/products",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_product_reads_require_authentication_and_all_approved_roles(
    postgres_client, role_headers, category
):
    anonymous = postgres_client.get("/api/v1/products")
    assert anonymous.status_code == 401
    assert anonymous.json()["detail"]["code"] == "AUTHENTICATION_REQUIRED"
    product = create_product(
        postgres_client, role_headers[UserRole.ADMIN], category.id, "SKU-001"
    )

    for role in UserRole:
        listing = postgres_client.get("/api/v1/products", headers=role_headers[role])
        response = postgres_client.get(
            f"/api/v1/products/{product['id']}", headers=role_headers[role]
        )
        assert listing.status_code == 200
        assert product in listing.json()["items"]
        assert response.status_code == 200
        assert response.json() == product


@pytest.mark.parametrize("method", ["post", "put", "delete"])
@pytest.mark.parametrize("role", [UserRole.WAREHOUSE, UserRole.CLIENT, None])
def test_product_mutations_are_admin_only(
    postgres_client, role_headers, category, method: str, role: UserRole | None
):
    admin = role_headers[UserRole.ADMIN]
    product = create_product(postgres_client, admin, category.id, "SKU-RESTRICTED")
    headers = role_headers[role] if role is not None else None
    path = "/api/v1/products"
    options: dict[str, object] = {"headers": headers}
    if method == "post":
        options["json"] = {
            "sku": "SKU-OTHER", "name": "Other", "category_id": category.id, "unit": "each"
        }
    else:
        path = f"{path}/{product['id']}"
        if method == "put":
            options["json"] = {
                "sku": product["sku"], "name": "Changed", "category_id": category.id,
                "unit": "each"
            }

    response = getattr(postgres_client, method)(path, **options)
    assert response.status_code == (401 if role is None else 403)


def test_product_create_normalizes_sku_and_text_and_preserves_nullable_supplier(
    postgres_client, role_headers, category
):
    product = create_product(
        postgres_client,
        role_headers[UserRole.ADMIN],
        category.id,
        "  sku-001 ",
        name="  Steel Bolt  ",
        description="  zinc coated  ",
        unit="  box  ",
        supplier_id=None,
    )

    assert product["sku"] == "SKU-001"
    assert product["name"] == "Steel Bolt"
    assert product["description"] == "zinc coated"
    assert product["unit"] == "box"
    assert product["supplier_id"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {"sku": "SKU-1", "name": "Bolt", "category_id": 1, "unit": "each", "extra": 1},
        {"sku": "  ", "name": "Bolt", "category_id": 1, "unit": "each"},
        {"sku": "SKU-1", "name": "Bolt", "category_id": 1, "unit": "  "},
        {"sku": "SKU-1", "name": "Bolt", "category_id": 1, "unit": "each", "reorder_level": -1},
    ],
)
def test_product_create_rejects_extra_or_invalid_fields(postgres_client, role_headers, payload):
    response = postgres_client.post(
        "/api/v1/products", headers=role_headers[UserRole.ADMIN], json=payload
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "REQUEST_VALIDATION_ERROR"


def test_product_update_rejects_extra_fields(postgres_client, role_headers, category):
    product = create_product(
        postgres_client, role_headers[UserRole.ADMIN], category.id, "SKU-UPDATE"
    )
    response = postgres_client.put(
        f"/api/v1/products/{product['id']}",
        headers=role_headers[UserRole.ADMIN],
        json={
            "sku": product["sku"], "name": "Changed", "category_id": category.id,
            "unit": "each", "unexpected": True
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "REQUEST_VALIDATION_ERROR"


def test_product_filters_share_total_and_results_are_stably_ordered(
    postgres_client, role_headers, postgres_session: Session, category
):
    admin = role_headers[UserRole.ADMIN]
    supplier_a = Supplier(name="A Supply")
    supplier_b = Supplier(name="B Supply")
    other_category = Category(name="Fasteners")
    postgres_session.add_all([supplier_a, supplier_b, other_category])
    postgres_session.commit()
    first = create_product(
        postgres_client, admin, category.id, "SKU-A", supplier_id=supplier_a.id
    )
    second = create_product(
        postgres_client, admin, category.id, "SKU-B", supplier_id=supplier_b.id,
        is_active=False,
    )
    create_product(
        postgres_client, admin, other_category.id, "SKU-C", supplier_id=supplier_a.id
    )

    filtered = postgres_client.get(
        f"/api/v1/products?search=sku-&category_id={category.id}&supplier_id={supplier_a.id}"
        "&is_active=true&page_size=1",
        headers=admin,
    )
    next_page = postgres_client.get(
        f"/api/v1/products?category_id={category.id}&page=2&page_size=1",
        headers=admin,
    )

    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"] == [first]
    assert next_page.json()["total"] == 2
    assert next_page.json()["items"] == [second]


def test_product_missing_references_have_stable_errors(postgres_client, role_headers, category):
    headers = role_headers[UserRole.ADMIN]
    missing_category = postgres_client.post(
        "/api/v1/products", headers=headers,
        json={"sku": "SKU-X", "name": "Bolt", "category_id": 987654, "unit": "each"},
    )
    missing_supplier = postgres_client.post(
        "/api/v1/products", headers=headers,
        json={
            "sku": "SKU-Y", "name": "Bolt", "category_id": category.id,
            "supplier_id": 987654, "unit": "each"
        },
    )

    assert missing_category.status_code == 422
    assert missing_category.json()["detail"]["code"] == "CATEGORY_NOT_FOUND"
    assert missing_supplier.status_code == 422
    assert missing_supplier.json()["detail"]["code"] == "SUPPLIER_NOT_FOUND"


def test_product_sku_conflict_and_missing_product_errors_are_stable(
    postgres_client, role_headers, category
):
    headers = role_headers[UserRole.ADMIN]
    create_product(postgres_client, headers, category.id, "SKU-DUP")
    conflict = postgres_client.post(
        "/api/v1/products", headers=headers,
        json={"sku": " sku-dup ", "name": "Duplicate", "category_id": category.id, "unit": "each"},
    )
    missing_get = postgres_client.get("/api/v1/products/987654", headers=headers)
    missing_update = postgres_client.put(
        "/api/v1/products/987654", headers=headers,
        json={"sku": "SKU-MISSING", "name": "Missing", "category_id": category.id, "unit": "each"},
    )
    missing_delete = postgres_client.delete("/api/v1/products/987654", headers=headers)

    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "PRODUCT_SKU_CONFLICT"
    for missing in (missing_get, missing_update, missing_delete):
        assert missing.status_code == 404
        assert missing.json()["detail"]["code"] == "PRODUCT_NOT_FOUND"


def test_product_update_conflict_rolls_back_all_fields(
    postgres_client, postgres_session: Session, role_headers, category
):
    first = Product(sku="SKU-FIRST", name="First", category_id=category.id, unit="each")
    second = Product(sku="SKU-SECOND", name="Second", category_id=category.id, unit="each")
    postgres_session.add_all([first, second])
    postgres_session.commit()
    response = postgres_client.put(
        f"/api/v1/products/{second.id}",
        headers=role_headers[UserRole.ADMIN],
        json={"sku": first.sku, "name": "Changed", "category_id": category.id, "unit": "box"},
    )
    postgres_session.expire_all()
    persisted = postgres_session.get(Product, second.id)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "PRODUCT_SKU_CONFLICT"
    assert persisted.sku == "SKU-SECOND"
    assert persisted.name == "Second"
    assert persisted.unit == "each"


@pytest.mark.parametrize(
    "reference_table",
    ["stocks", "inbounds", "outbounds", "transactions", "purchase_requests"],
)
def test_product_delete_in_use_preserves_each_reference(
    postgres_client, postgres_session, role_headers, category, reference_table
):
    warehouse = Warehouse(code="MAIN", name="Main Warehouse", address="Main Road")
    postgres_session.add(warehouse)
    postgres_session.flush()
    product = Product(sku="SKU-IN-USE", name="Bolt", category_id=category.id, unit="each")
    postgres_session.add(product)

    admin = postgres_session.query(User).filter_by(role=UserRole.ADMIN).one()
    if reference_table == "transactions":
        # The linked movement uses a companion product so the transaction's product FK
        # is the only reference to the product being deleted. The DB enforces the movement link.
        movement_product = Product(
            sku="SKU-MOVEMENT", name="Movement", category_id=category.id, unit="each"
        )
        postgres_session.add(movement_product)
        postgres_session.flush()
        movement = Inbound(
            warehouse_id=warehouse.id,
            product_id=movement_product.id,
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
            warehouse_id=warehouse.id,
            product_id=product.id,
            quantity=1,
            created_by_id=admin.id,
        )
    elif reference_table == "outbounds":
        reference = Outbound(
            warehouse_id=warehouse.id,
            product_id=product.id,
            quantity=1,
            created_by_id=admin.id,
        )
    else:
        reference = PurchaseRequest(
            request_number="REQ-PRODUCT-IN-USE",
            warehouse_id=warehouse.id,
            product_id=product.id,
            quantity=1,
            requested_by_id=admin.id,
        )

    postgres_session.add(reference)
    postgres_session.commit()
    reference_id = reference.id
    assert ProductRepository(postgres_session).has_references(product.id)

    response = postgres_client.delete(
        f"/api/v1/products/{product.id}", headers=role_headers[UserRole.ADMIN]
    )
    postgres_session.expire_all()
    persisted = postgres_session.get(Product, product.id)
    persisted_reference = postgres_session.get(type(reference), reference_id)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "PRODUCT_IN_USE"
    assert persisted is not None
    assert persisted_reference is not None
