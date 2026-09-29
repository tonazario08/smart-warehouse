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

    @staticmethod
    def _predicates(
        action: str | None, target_type: str | None, target_id: int | None
    ) -> list:
        predicates = []
        if action is not None:
            predicates.append(AuditLog.action == action)
        if target_type is not None:
            predicates.append(AuditLog.target_type == target_type)
        if target_id is not None:
            predicates.append(AuditLog.target_id == target_id)
        return predicates

    def list(
        self, params: PageParams, *, action: str | None = None,
        target_type: str | None = None, target_id: int | None = None,
    ) -> list[AuditLog]:
        statement = (
            select(AuditLog)
            .where(*self._predicates(action, target_type, target_id))
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset(params.offset)
            .limit(params.page_size)
        )
        return list(self.session.scalars(statement).all())

    def count(
        self, *, action: str | None = None,
        target_type: str | None = None, target_id: int | None = None,
    ) -> int:
        statement = select(func.count()).select_from(AuditLog).where(
            *self._predicates(action, target_type, target_id)
        )
        return self.session.scalar(statement) or 0

    def get(self, audit_log_id: int) -> AuditLog | None:
        return self.session.get(AuditLog, audit_log_id)
