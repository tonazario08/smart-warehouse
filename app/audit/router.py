"""Admin-only, read-only HTTP routes for administrative audit history."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.audit.repository import AuditRepository
from app.audit.schemas import AuditLogPage, AuditLogResponse
from app.auth.dependencies import Permission, require_permission
from app.core.errors import DomainError
from app.core.pagination import PageParams
from app.db.session import get_session
from app.models import AuditLog, User

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=AuditLogPage)
def list_audit_logs(
    params: Annotated[PageParams, Depends()],
    session: Annotated[object, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.AUDIT_READ))],
    action: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    target_type: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    target_id: Annotated[int | None, Query(ge=1)] = None,
) -> AuditLogPage:
    repository = AuditRepository(session)
    return AuditLogPage(
        items=repository.list(params, action=action, target_type=target_type, target_id=target_id),
        total=repository.count(action=action, target_type=target_type, target_id=target_id),
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/{audit_log_id}", response_model=AuditLogResponse)
def get_audit_log(
    audit_log_id: int,
    session: Annotated[object, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.AUDIT_READ))],
) -> AuditLog:
    audit_log = AuditRepository(session).get(audit_log_id)
    if audit_log is None:
        raise DomainError(404, "AUDIT_LOG_NOT_FOUND", "Audit log was not found.")
    return audit_log
