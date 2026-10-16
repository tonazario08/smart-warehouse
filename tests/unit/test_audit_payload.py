"""Pure tests for the administrative audit payload boundary."""

from app.audit.service import user_audit_snapshot
from app.models import User, UserRole


def test_user_audit_snapshot_contains_only_allowlisted_fields() -> None:
    user = User(
        id=42,
        email="operator@example.com",
        password_hash="secret-hash",
        role=UserRole.WAREHOUSE,
        is_active=True,
    )

    snapshot = user_audit_snapshot(user)

    assert snapshot == {
        "email": "operator@example.com",
        "role": "warehouse",
        "is_active": True,
    }
    assert not {"password", "password_hash", "token", "secret"} & snapshot.keys()
