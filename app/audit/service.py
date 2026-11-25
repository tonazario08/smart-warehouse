"""Administrative audit use cases and safe user snapshots."""

from collections.abc import Mapping
from typing import Any

from app.audit.models import USER_AUDIT_FIELDS, AuditLog
from app.audit.repository import AuditRepository
from app.models import User

USER_AUDIT_ACTIONS = frozenset(
    {"user.created", "user.role_changed", "user.status_changed"}
)


def user_audit_snapshot(user: User) -> dict[str, str | bool]:
    """Return only the user attributes approved for administrative audit."""
    return {
        "email": user.email,
        "role": user.role.value,
        "is_active": user.is_active,
    }


def _allowlisted_snapshot(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {field: value[field] for field in USER_AUDIT_FIELDS if field in value}


class AuditService:
    """Build allowlisted audit rows; the caller owns their transaction."""

    def __init__(self, repository: AuditRepository) -> None:
        self.repository = repository

    def record_user_event(
        self,
        actor: User,
        action: str,
        before: Mapping[str, Any] | None,
        after: User,
    ) -> AuditLog:
        if action not in USER_AUDIT_ACTIONS:
            raise ValueError("Unsupported administrative user audit action")

        audit_log = AuditLog(
            actor_user_id=actor.id,
            action=action,
            target_type="user",
            target_id=after.id,
            before_data=_allowlisted_snapshot(before),
            after_data=user_audit_snapshot(after),
        )
        self.repository.add(audit_log)
        return audit_log
