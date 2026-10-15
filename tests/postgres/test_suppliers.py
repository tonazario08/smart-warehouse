"""PostgreSQL-backed supplier API, validation, and transaction contract tests."""

import pytest
from sqlalchemy.orm import Session

from app.auth.security import create_access_token
from app.models import Category, Product, Supplier, User, UserRole


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


def create_supplier(
    client, headers: dict[str, str], name: str, **fields: object
) -> dict[str, object]:
    response = client.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": name, **fields},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_supplier_reads_require_authentication_and_staff_permission(postgres_client, role_headers):
    anonymous_list = postgres_client.get("/api/v1/suppliers")
    anonymous_detail = postgres_client.get("/api/v1/suppliers/1")
    client_list = postgres_client.get(
        "/api/v1/suppliers", headers=role_headers[UserRole.CLIENT]
    )
    client_detail = postgres_client.get(
        "/api/v1/suppliers/1", headers=role_headers[UserRole.CLIENT]
    )

    for response in (anonymous_list, anonymous_detail):
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "AUTHENTICATION_REQUIRED"
    assert client_list.status_code == client_detail.status_code == 403


def test_supplier_read_is_available_to_admin_and_warehouse(postgres_client, role_headers):
    supplier = create_supplier(
        postgres_client, role_headers[UserRole.ADMIN], "Main Supply", email="sales@example.com"
    )

    for role in (UserRole.ADMIN, UserRole.WAREHOUSE):
        listing = postgres_client.get("/api/v1/suppliers", headers=role_headers[role])
        detail = postgres_client.get(
            f"/api/v1/suppliers/{supplier['id']}", headers=role_headers[role]
        )
        assert listing.status_code == detail.status_code == 200
        assert listing.json()["items"] == [supplier]
        assert detail.json() == supplier


@pytest.mark.parametrize("method", ["post", "put", "delete"])
@pytest.mark.parametrize("role", [UserRole.WAREHOUSE, UserRole.CLIENT, None])
def test_supplier_mutations_are_admin_only(postgres_client, role_headers, method: str, role):
    supplier = create_supplier(postgres_client, role_headers[UserRole.ADMIN], "Main Supply")
    headers = role_headers[role] if role is not None else None
    path = "/api/v1/suppliers"
    options: dict[str, object] = {"headers": headers}
    if method == "post":
        options["json"] = {"name": "Restricted"}
    else:
        path = f"{path}/{supplier['id']}"
        if method == "put":
            options["json"] = {"name": "Restricted"}

    response = getattr(postgres_client, method)(path, **options)
    assert response.status_code == (401 if role is None else 403)


def test_admin_supplier_crud_normalizes_and_preserves_optional_nulls(postgres_client, role_headers):
    headers = role_headers[UserRole.ADMIN]
    created = create_supplier(
        postgres_client,
        headers,
        "  Main Supply  ",
        email=" SALES@Example.COM ",
        phone="  +1 555 0100  ",
        address="  1 Warehouse Road  ",
    )
    empty_optional = create_supplier(postgres_client, headers, "No Contact")
    updated = postgres_client.put(
        f"/api/v1/suppliers/{created['id']}",
        headers=headers,
        json={"name": "  Updated Supply ", "email": None, "phone": None, "address": None},
    )
    deleted = postgres_client.delete(f"/api/v1/suppliers/{empty_optional['id']}", headers=headers)

    assert created == {
        "id": created["id"],
        "name": "Main Supply",
        "email": "sales@example.com",
        "phone": "+1 555 0100",
        "address": "1 Warehouse Road",
    }
    assert empty_optional["email"] is empty_optional["phone"] is empty_optional["address"] is None
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated Supply"
    assert updated.json()["email"] is updated.json()["phone"] is updated.json()["address"] is None
    assert deleted.status_code == 204


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "Main Supply", "unknown": "value"},
        {"name": "   "},
        {"name": "Main Supply", "email": "not-an-email"},
        {"name": "Main Supply", "email": "   "},
        {"name": "Main Supply", "phone": "   "},
        {"name": "Main Supply", "address": "   "},
    ],
)
def test_supplier_create_rejects_extra_invalid_or_blank_fields(
    postgres_client, role_headers, payload: dict[str, str]
):
    response = postgres_client.post(
        "/api/v1/suppliers", headers=role_headers[UserRole.ADMIN], json=payload
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "REQUEST_VALIDATION_ERROR"


def test_supplier_update_rejects_extra_fields(postgres_client, role_headers):
    supplier = create_supplier(postgres_client, role_headers[UserRole.ADMIN], "Main Supply")
    response = postgres_client.put(
        f"/api/v1/suppliers/{supplier['id']}",
        headers=role_headers[UserRole.ADMIN],
        json={"name": "Updated Supply", "is_active": False},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "REQUEST_VALIDATION_ERROR"


def test_supplier_list_search_is_case_insensitive_and_pagination_is_stable(
    postgres_client, role_headers
):
    headers = role_headers[UserRole.ADMIN]
    create_supplier(postgres_client, headers, "Alpha Supply", email="alpha@example.com")
    create_supplier(postgres_client, headers, "Beta Supply", phone="555-0100")
    create_supplier(postgres_client, headers, "Gamma Supply", email="gamma@example.com")

    page = postgres_client.get(
        "/api/v1/suppliers?page=2&page_size=1", headers=headers
    )
    found_by_email = postgres_client.get("/api/v1/suppliers?search=GAMMA@EXAMPLE", headers=headers)
    found_by_phone = postgres_client.get("/api/v1/suppliers?search=555-0100", headers=headers)

    assert page.status_code == 200
    assert page.json()["total"] == 3
    assert page.json()["page"] == 2
    assert page.json()["page_size"] == 1
    assert [item["name"] for item in page.json()["items"]] == ["Beta Supply"]
    assert [item["name"] for item in found_by_email.json()["items"]] == ["Gamma Supply"]
    assert [item["name"] for item in found_by_phone.json()["items"]] == ["Beta Supply"]


def test_supplier_list_rejects_unbounded_pagination(postgres_client, role_headers):
    response = postgres_client.get(
        "/api/v1/suppliers?page=0&page_size=101", headers=role_headers[UserRole.ADMIN]
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "REQUEST_VALIDATION_ERROR"


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "Main Supply", "email": "sales@example.com"},
        {"name": "Other Supply", "email": " SALES@example.com "},
    ],
)
def test_supplier_unique_conflicts_have_stable_error_and_safe_message(
    postgres_client, role_headers, payload: dict[str, str]
):
    headers = role_headers[UserRole.ADMIN]
    create_supplier(postgres_client, headers, "Main Supply", email="sales@example.com")

    response = postgres_client.post("/api/v1/suppliers", headers=headers, json=payload)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SUPPLIER_CONFLICT"
    assert "postgres" not in response.text.lower()
    assert "constraint" not in response.text.lower()


def test_supplier_update_conflict_rolls_back_changes(
    postgres_client, postgres_session, role_headers
):
    first = Supplier(name="First Supply", email="first@example.com")
    second = Supplier(name="Second Supply", email="second@example.com")
    postgres_session.add_all([first, second])
    postgres_session.commit()

    response = postgres_client.put(
        f"/api/v1/suppliers/{second.id}",
        headers=role_headers[UserRole.ADMIN],
        json={"name": "First Supply", "email": "changed@example.com"},
    )
    postgres_session.expire_all()

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SUPPLIER_CONFLICT"
    persisted = postgres_session.get(Supplier, second.id)
    assert persisted.name == "Second Supply"
    assert persisted.email == "second@example.com"


def test_supplier_missing_get_update_and_delete_return_stable_not_found(
    postgres_client, role_headers
):
    headers = role_headers[UserRole.ADMIN]
    detail = postgres_client.get("/api/v1/suppliers/99999", headers=headers)
    update = postgres_client.put(
        "/api/v1/suppliers/99999", headers=headers, json={"name": "Missing"}
    )
    delete = postgres_client.delete("/api/v1/suppliers/99999", headers=headers)

    for response in (detail, update, delete):
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "SUPPLIER_NOT_FOUND"


def test_supplier_cannot_be_deleted_while_product_references_it(
    postgres_client, postgres_session: Session, role_headers
):
    category = Category(name="Hardware")
    supplier = Supplier(name="Referenced Supply")
    postgres_session.add_all([category, supplier])
    postgres_session.flush()
    product = Product(
        sku="SKU-SUPPLIER-001",
        name="Bolt",
        category_id=category.id,
        supplier_id=supplier.id,
        unit="each",
    )
    postgres_session.add(product)
    postgres_session.commit()

    response = postgres_client.delete(
        f"/api/v1/suppliers/{supplier.id}", headers=role_headers[UserRole.ADMIN]
    )
    postgres_session.expire_all()
    persisted_product = postgres_session.get(Product, product.id)

    assert persisted_product.supplier_id == supplier.id
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SUPPLIER_IN_USE"
    assert "postgres" not in response.text.lower()
