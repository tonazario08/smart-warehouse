"""Safe response schemas for administrative audit records."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from app.audit.models import USER_AUDIT_FIELDS
from app.core.pagination import Page


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    actor_user_id: int
    action: str
    target_type: str
    target_id: int
    before_data: dict[str, Any] | None
    after_data: dict[str, Any] | None
    created_at: datetime

    @field_validator("before_data", "after_data", mode="before")
    @classmethod
    def filter_user_payload(cls, value: object) -> object:
        if value is None or not isinstance(value, dict):
            return value
        return {key: value[key] for key in USER_AUDIT_FIELDS if key in value}

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Audit timestamps must be timezone-aware")
        return value.astimezone(UTC)


class AuditLogPage(Page[AuditLogResponse]):
    pass
