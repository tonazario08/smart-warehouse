"""PostgreSQL-backed user-administration and audit contract tests."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import create_access_token, verify_password
from app.models import AuditLog, User, UserRole


@pytest.fixture
def admin(postgres_session: Session) -> User:
    user = User(
        email="admin@example.com",
        password_hash="test-hash",
        role=UserRole.ADMIN,
    )
    postgres_session.add(user)
    postgres_session.commit()
    return user


@pytest.fixture
def admin_headers(admin: User, unit_settings) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(admin.id, unit_settings)}"}


@pytest.fixture
def client_headers(postgres_session: Session, unit_settings) -> dict[str, str]:
    user = User(
        email="client@example.com",
        password_hash="test-hash",
        role=UserRole.CLIENT,
    )
    postgres_session.add(user)
    postgres_session.commit()
    return {"Authorization": f"Bearer {create_access_token(user.id, unit_settings)}"}


def add_user(
    postgres_session: Session,
    email: str,
    role: UserRole = UserRole.CLIENT,
    is_active: bool = True,
) -> User:
    user = User(email=email, password_hash="test-hash", role=role, is_active=is_active)
    postgres_session.add(user)
    postgres_session.commit()
    return user


def test_admin_can_create_a_managed_user(postgres_client, postgres_session, admin_headers) -> None:
    response = postgres_client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "email": " Operator@Example.com ",
            "password": "strong-password-1",
            "role": "warehouse",
        },
    )

    assert response.status_code == 201
    assert response.json()["email"] == "operator@example.com"
    assert response.json()["role"] == "warehouse"
    assert "password" not in response.text.lower()
    assert "password_hash" not in response.json()
    logs = postgres_client.get("/api/v1/audit-logs", headers=admin_headers).json()["items"]
    assert [(row["action"], row["after_data"]["role"]) for row in logs] == [
        ("user.created", "warehouse")
    ]
    assert "password" not in str(logs).lower()


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "a@example.com", "password": "strong-password-1", "role": "admin"},
        {
            "email": "a@example.com",
            "password": "short",
            "role": "client",
        },
        {
            "email": "a@example.com",
            "password": "strong-password-1",
            "role": "client",
            "is_active": False,
        },
    ],
)
def test_create_rejects_privileged_or_invalid_fields(
    postgres_client, admin_headers, payload
) -> None:
    response = postgres_client.post("/api/v1/users", headers=admin_headers, json=payload)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "REQUEST_VALIDATION_ERROR"


def test_admin_created_password_preserves_significant_whitespace(
    postgres_client, postgres_session, admin_headers
) -> None:
    password = "  keep leading and trailing spaces  "

    response = postgres_client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"email": "spaces@example.com", "password": password, "role": "client"},
    )
    user = postgres_session.query(User).filter_by(email="spaces@example.com").one()

    assert response.status_code == 201
    assert verify_password(password, user.password_hash)
    assert not verify_password(password.strip(), user.password_hash)


def test_create_rejects_password_over_max_length(postgres_client, admin_headers) -> None:
    response = postgres_client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"email": "oversize@example.com", "password": "x" * 129, "role": "client"},
    )

    assert response.status_code == 422


def test_status_requires_a_boolean_value(postgres_client, postgres_session, admin_headers) -> None:
    target = add_user(postgres_session, "strict-status@example.com")

    response = postgres_client.patch(
        f"/api/v1/users/{target.id}/status",
        headers=admin_headers,
        json={"is_active": "false"},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", "/api/v1/users", None),
        (
            "post",
            "/api/v1/users",
            {"email": "x@example.com", "password": "strong-password", "role": "client"},
        ),
        ("get", "/api/v1/users/1", None),
        ("patch", "/api/v1/users/1/role", {"role": "client"}),
        ("patch", "/api/v1/users/1/status", {"is_active": False}),
        ("get", "/api/v1/audit-logs", None),
        ("get", "/api/v1/audit-logs/1", None),
    ],
)
def test_user_and_audit_routes_require_admin(
    postgres_client, client_headers, method, path, payload
) -> None:
    request_options = {"headers": client_headers}
    if payload is not None:
        request_options["json"] = payload
    response = getattr(postgres_client, method)(path, **request_options)

    assert response.status_code == 403


def test_user_list_is_paginated_and_detail_is_safe(
    postgres_client, postgres_session, admin_headers
) -> None:
    first = add_user(postgres_session, "first@example.com")
    second = add_user(postgres_session, "second@example.com")

    page = postgres_client.get("/api/v1/users?page=2&page_size=1", headers=admin_headers)
    detail = postgres_client.get(f"/api/v1/users/{second.id}", headers=admin_headers)

    assert page.status_code == 200
    assert page.json()["total"] == 3
    assert page.json()["page"] == 2
    assert page.json()["page_size"] == 1
    assert [item["id"] for item in page.json()["items"]] == [first.id]
    assert detail.status_code == 200
    assert detail.json()["email"] == "second@example.com"
    assert "password_hash" not in detail.json()
    assert "password" not in detail.json()


def test_user_detail_returns_stable_not_found(postgres_client, admin_headers) -> None:
    response = postgres_client.get("/api/v1/users/99999", headers=admin_headers)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "USER_NOT_FOUND"


def test_audit_detail_returns_stable_not_found(postgres_client, admin_headers) -> None:
    response = postgres_client.get("/api/v1/audit-logs/99999", headers=admin_headers)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "AUDIT_LOG_NOT_FOUND"


def test_user_and_audit_reads_require_authentication(postgres_client) -> None:
    user_response = postgres_client.get("/api/v1/users")
    audit_response = postgres_client.get("/api/v1/audit-logs")

    assert user_response.status_code == audit_response.status_code == 401


@pytest.mark.parametrize(
    ("field", "payload"),
    [("role", {"role": "client"}), ("status", {"is_active": False})],
)
def test_admin_accounts_cannot_be_modified(
    postgres_client, postgres_session, admin, admin_headers, field, payload
) -> None:
    other_admin = add_user(postgres_session, "other-admin@example.com", UserRole.ADMIN)
    for target in (admin, other_admin):
        response = postgres_client.patch(
            f"/api/v1/users/{target.id}/{field}", headers=admin_headers, json=payload
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "ADMIN_ACCOUNT_PROTECTED"


def test_user_mutations_are_audited_with_allowlisted_snapshots(
    postgres_client, postgres_session, admin_headers
) -> None:
    target = add_user(postgres_session, "managed@example.com", UserRole.CLIENT)

    role_response = postgres_client.patch(
        f"/api/v1/users/{target.id}/role",
        headers=admin_headers,
        json={"role": "warehouse"},
    )
    status_response = postgres_client.patch(
        f"/api/v1/users/{target.id}/status",
        headers=admin_headers,
        json={"is_active": False},
    )
    logs_response = postgres_client.get("/api/v1/audit-logs?page_size=10", headers=admin_headers)

    assert role_response.status_code == status_response.status_code == 200
    assert role_response.json()["role"] == "warehouse"
    assert status_response.json()["is_active"] is False
    logs = logs_response.json()["items"]
    assert [item["action"] for item in logs] == ["user.status_changed", "user.role_changed"]
    expected_keys = {"email", "role", "is_active"}
    for log in logs:
        assert set(log["before_data"]) == expected_keys
        assert set(log["after_data"]) == expected_keys
        assert log["target_type"] == "user"
        assert log["target_id"] == target.id
        assert "password" not in str(log).lower()


@pytest.mark.parametrize(
    ("field", "payload", "error_code"),
    [
        ("role", {"role": "client"}, "USER_ROLE_UNCHANGED"),
        ("status", {"is_active": True}, "USER_STATUS_UNCHANGED"),
    ],
)
def test_unchanged_user_state_is_rejected_without_audit(
    postgres_client,
    postgres_session,
    admin_headers,
    field,
    payload,
    error_code,
) -> None:
    target = add_user(postgres_session, "unchanged@example.com")

    response = postgres_client.patch(
        f"/api/v1/users/{target.id}/{field}", headers=admin_headers, json=payload
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == error_code
    assert postgres_session.scalars(select(AuditLog)).all() == []


def test_duplicate_managed_user_email_has_stable_error(
    postgres_client, postgres_session, admin_headers
) -> None:
    add_user(postgres_session, "duplicate@example.com")

    response = postgres_client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "email": "duplicate@example.com",
            "password": "strong-password-1",
            "role": "client",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "USER_EMAIL_CONFLICT"


def test_audit_list_and_detail_are_read_only(
    postgres_client, postgres_session, admin, admin_headers
) -> None:
    target = add_user(postgres_session, "audited@example.com")
    audit = AuditLog(
        actor_user_id=admin.id,
        action="user.created",
        target_type="user",
        target_id=target.id,
        before_data={"email": target.email, "password": "never-return-this"},
        after_data={
            "email": target.email,
            "role": "client",
            "is_active": True,
            "password_hash": "never-return-this-either",
        },
    )
    postgres_session.add(audit)
    postgres_session.commit()

    listing = postgres_client.get("/api/v1/audit-logs", headers=admin_headers)
    detail = postgres_client.get(f"/api/v1/audit-logs/{audit.id}", headers=admin_headers)
    mutation = postgres_client.post("/api/v1/audit-logs", headers=admin_headers, json={})

    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert detail.status_code == 200
    assert detail.json()["id"] == audit.id
    assert detail.json()["before_data"] == {"email": "audited@example.com"}
    assert detail.json()["after_data"] == {
        "email": "audited@example.com",
        "role": "client",
        "is_active": True,
    }
    created_at = datetime.fromisoformat(detail.json()["created_at"])
    assert created_at.tzinfo is not None
    assert created_at.utcoffset() == UTC.utcoffset(created_at)
    assert listing.json()["items"][0]["before_data"] == {"email": "audited@example.com"}
    assert "never-return-this" not in detail.text
    assert mutation.status_code == 405


def test_repositories_do_not_commit(monkeypatch, postgres_session: Session) -> None:
    from app.audit.repository import AuditRepository
    from app.core.pagination import PageParams
    from app.users.repository import UserRepository

    def forbidden() -> None:
        raise AssertionError("repository called commit")

    monkeypatch.setattr(postgres_session, "commit", forbidden)

    users = UserRepository(postgres_session)
    users.list(PageParams())
    AuditRepository(postgres_session).list(PageParams())

    target = User(
        email="repository-mutation@example.com",
        password_hash="test-hash",
        role=UserRole.CLIENT,
    )
    users.add(target)
    postgres_session.flush()
    users.change_role(target, UserRole.WAREHOUSE)
    users.change_status(target, False)
    assert target.role is UserRole.WAREHOUSE
    assert target.is_active is False


def test_audit_failure_rolls_back_creation_visible_to_independent_session(
    monkeypatch,
    admin,
    postgres_session: Session,
    postgres_engine,
) -> None:
    from app.audit.repository import AuditRepository
    from app.audit.service import AuditService
    from app.users.repository import UserRepository
    from app.users.service import UserService

    def fail_add(*args, **kwargs) -> None:
        raise RuntimeError("audit persistence unavailable")

    monkeypatch.setattr(AuditRepository, "add", fail_add)
    service = UserService(
        postgres_session,
        UserRepository(postgres_session),
        AuditService(AuditRepository(postgres_session)),
    )
    with pytest.raises(RuntimeError, match="audit persistence unavailable"):
        service.create(
            admin,
            "must-rollback@example.com",
            "strong-password-1",
            UserRole.CLIENT,
        )

    with Session(postgres_engine) as independent_session:
        user = independent_session.scalar(
            select(User).where(User.email == "must-rollback@example.com")
        )
        audits = independent_session.scalars(
            select(AuditLog).where(AuditLog.action == "user.created")
        ).all()
    assert user is None
    assert all(
        audit.after_data.get("email") != "must-rollback@example.com" for audit in audits
    )


def test_unexpected_audit_failure_uses_safe_global_error_handler(
    monkeypatch, postgres_client, admin_headers
) -> None:
    from app.audit.repository import AuditRepository

    def fail_add(*args, **kwargs) -> None:
        raise RuntimeError("audit persistence unavailable")

    monkeypatch.setattr(AuditRepository, "add", fail_add)
    with TestClient(postgres_client.app, raise_server_exceptions=False) as safe_client:
        response = safe_client.post(
            "/api/v1/users",
            headers=admin_headers,
            json={
                "email": "safe-error@example.com",
                "password": "strong-password-1",
                "role": "client",
            },
        )

    assert response.status_code == 500
    assert response.json() == {
        "detail": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An internal error occurred.",
            "fields": None,
        }
    }
