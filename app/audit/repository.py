"""Persistence boundary for append-only administrative audit logs."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.core.pagination import PageParams


class AuditRepository:
    """Query and stage audit records without committing or mutating history."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, audit_log: AuditLog) -> None:
        self.session.add(audit_log)

    def list(self, params: PageParams) -> list[AuditLog]:
        statement = (
            select(AuditLog)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset(params.offset)
            .limit(params.page_size)
        )
        return list(self.session.scalars(statement).all())

    def count(self) -> int:
        return self.session.scalar(select(func.count()).select_from(AuditLog)) or 0

    def get(self, audit_log_id: int) -> AuditLog | None:
        return self.session.get(AuditLog, audit_log_id)
