"""PostgreSQL-backed category API and hierarchy contract tests."""

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.security import create_access_token
from app.models import Category, Product, User, UserRole


@pytest.fixture
def role_headers(postgres_session: Session, unit_settings) -> dict[UserRole, dict[str, str]]:
    headers: dict[UserRole, dict[str, str]] = {}
    for role in UserRole:
        user = User(
            email=f"{role.value}@example.com",
            password_hash="test-hash",
            role=role,
        )
        postgres_session.add(user)
        postgres_session.flush()
        headers[role] = {
            "Authorization": f"Bearer {create_access_token(user.id, unit_settings)}"
        }
    postgres_session.commit()
    return headers


def create_category(
    client,
    headers: dict[str, str],
    name: str,
    parent_id: int | None = None,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/categories",
        headers=headers,
        json={"name": name, "parent_id": parent_id},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_category_reads_require_authentication(postgres_client) -> None:
    list_response = postgres_client.get("/api/v1/categories")
    detail_response = postgres_client.get("/api/v1/categories/1")

    assert list_response.status_code == detail_response.status_code == 401
    assert list_response.json()["detail"]["code"] == "AUTHENTICATION_REQUIRED"
    assert detail_response.json()["detail"]["code"] == "AUTHENTICATION_REQUIRED"


def test_all_authenticated_roles_can_list_and_get_categories(
    postgres_client, role_headers, postgres_session: Session
) -> None:
    category = Category(name="Hardware")
    postgres_session.add(category)
    postgres_session.commit()

    for headers in role_headers.values():
        listing = postgres_client.get("/api/v1/categories", headers=headers)
        detail = postgres_client.get(f"/api/v1/categories/{category.id}", headers=headers)

        assert listing.status_code == detail.status_code == 200
        assert listing.json()["items"][0]["name"] == "Hardware"
        assert detail.json()["id"] == category.id


def test_category_list_uses_bounded_pagination(postgres_client, role_headers) -> None:
    for name in ("Hardware", "Tools", "Fasteners"):
        create_category(postgres_client, role_headers[UserRole.ADMIN], name)

    response = postgres_client.get(
        "/api/v1/categories?page=2&page_size=1", headers=role_headers[UserRole.CLIENT]
    )

    assert response.status_code == 200
    assert response.json()["total"] == 3
    assert response.json()["page"] == 2
    assert response.json()["page_size"] == 1
    assert len(response.json()["items"]) == 1


@pytest.mark.parametrize("role", [UserRole.CLIENT, UserRole.WAREHOUSE])
@pytest.mark.parametrize("method", ["post", "put", "delete"])
def test_category_mutations_are_admin_only(
    postgres_client, role_headers, method: str, role: UserRole
) -> None:
    category = create_category(postgres_client, role_headers[UserRole.ADMIN], "Hardware")
    options: dict[str, object] = {"headers": role_headers[role]}
    path = "/api/v1/categories"
    if method == "post":
        options["json"] = {"name": "Restricted"}
    else:
        path = f"{path}/{category['id']}"
        if method == "put":
            options["json"] = {"name": "Restricted"}

    response = getattr(postgres_client, method)(path, **options)

    assert response.status_code == 403


def test_admin_can_create_update_and_delete_category(postgres_client, role_headers) -> None:
    headers = role_headers[UserRole.ADMIN]
    created = create_category(postgres_client, headers, "  Hardware  ")
    updated = postgres_client.put(
        f"/api/v1/categories/{created['id']}",
        headers=headers,
        json={"name": "Tools", "parent_id": None},
    )
    deleted = postgres_client.delete(f"/api/v1/categories/{created['id']}", headers=headers)

    assert created["name"] == "Hardware"
    assert updated.status_code == 200
    assert updated.json()["name"] == "Tools"
    assert deleted.status_code == 204


def test_category_detail_returns_stable_not_found(postgres_client, role_headers) -> None:
    response = postgres_client.get(
        "/api/v1/categories/99999", headers=role_headers[UserRole.CLIENT]
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "CATEGORY_NOT_FOUND"


def test_category_rejects_invalid_parent_reference(postgres_client, role_headers) -> None:
    response = postgres_client.post(
        "/api/v1/categories",
        headers=role_headers[UserRole.ADMIN],
        json={"name": "Orphan", "parent_id": 99999},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "CATEGORY_NOT_FOUND"


def test_category_rejects_duplicate_name_with_stable_conflict(
    postgres_client, role_headers
) -> None:
    headers = role_headers[UserRole.ADMIN]
    create_category(postgres_client, headers, "Hardware")

    response = postgres_client.post(
        "/api/v1/categories", headers=headers, json={"name": "Hardware"}
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CATEGORY_NAME_CONFLICT"


def test_category_name_conflict_rolls_back_update(
    postgres_client, postgres_session: Session, role_headers
) -> None:
    headers = role_headers[UserRole.ADMIN]
    existing = Category(name="Hardware")
    changed = Category(name="Tools")
    postgres_session.add_all([existing, changed])
    postgres_session.commit()

    response = postgres_client.put(
        f"/api/v1/categories/{changed.id}",
        headers=headers,
        json={"name": "Hardware"},
    )
    postgres_session.expire_all()

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CATEGORY_NAME_CONFLICT"
    assert postgres_session.get(Category, changed.id).name == "Tools"


def test_category_rejects_direct_parent_cycle(postgres_client, role_headers) -> None:
    headers = role_headers[UserRole.ADMIN]
    category = create_category(postgres_client, headers, "Root")

    response = postgres_client.put(
        f"/api/v1/categories/{category['id']}",
        headers=headers,
        json={"name": "Root", "parent_id": category["id"]},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "CATEGORY_PARENT_CYCLE"


def test_category_rejects_multi_level_indirect_parent_cycle(
    postgres_client, role_headers
) -> None:
    headers = role_headers[UserRole.ADMIN]
    root = create_category(postgres_client, headers, "Root")
    child = create_category(postgres_client, headers, "Child", root["id"])
    grandchild = create_category(postgres_client, headers, "Grandchild", child["id"])

    response = postgres_client.put(
        f"/api/v1/categories/{root['id']}",
        headers=headers,
        json={"name": "Root", "parent_id": grandchild["id"]},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "CATEGORY_PARENT_CYCLE"


def test_category_cycle_walk_terminates_on_existing_corrupt_cycle(
    postgres_client, postgres_session: Session, role_headers
) -> None:
    root = Category(name="Root")
    first = Category(name="First")
    second = Category(name="Second")
    postgres_session.add_all([root, first, second])
    postgres_session.flush()
    first.parent_id = second.id
    second.parent_id = first.id
    postgres_session.commit()
    postgres_session.execute(
        text("SET CONSTRAINTS ALL IMMEDIATE")
    )

    response = postgres_client.put(
        f"/api/v1/categories/{root.id}",
        headers=role_headers[UserRole.ADMIN],
        json={"name": "Root", "parent_id": first.id},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "CATEGORY_PARENT_CYCLE"


def test_category_cannot_be_deleted_while_product_references_it(
    postgres_client, postgres_session: Session, role_headers
) -> None:
    category = Category(name="Hardware")
    postgres_session.add(category)
    postgres_session.flush()
    postgres_session.add(
        Product(sku="SKU-001", name="Bolt", category_id=category.id, unit="each")
    )
    postgres_session.commit()

    response = postgres_client.delete(
        f"/api/v1/categories/{category.id}", headers=role_headers[UserRole.ADMIN]
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CATEGORY_IN_USE"


def test_category_request_schema_forbids_extra_fields(postgres_client, role_headers) -> None:
    response = postgres_client.post(
        "/api/v1/categories",
        headers=role_headers[UserRole.ADMIN],
        json={"name": "Hardware", "is_active": False},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "REQUEST_VALIDATION_ERROR"


def test_category_request_schema_rejects_blank_trimmed_name(postgres_client, role_headers) -> None:
    response = postgres_client.post(
        "/api/v1/categories",
        headers=role_headers[UserRole.ADMIN],
        json={"name": "   "},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "REQUEST_VALIDATION_ERROR"
