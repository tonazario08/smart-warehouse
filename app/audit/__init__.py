"""Administrative audit domain."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.audit.models import AuditLog

__all__ = ["AuditLog"]


def __getattr__(name: str) -> object:
    if name == "AuditLog":
        from app.audit.models import AuditLog

        return AuditLog
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
