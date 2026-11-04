"""Strict customer-request inputs and explicit, non-secret response projections."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.inventory.schemas import MAX_STOCK_QUANTITY
from app.models.domain import PurchaseRequestStatus

PositiveInteger = Annotated[int, Field(strict=True, ge=1, le=MAX_STOCK_QUANTITY)]


class StrictBoundary(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PurchaseRequestCreate(StrictBoundary):
    warehouse_id: PositiveInteger
    product_id: PositiveInteger
    quantity: PositiveInteger
    note: str | None = Field(default=None, strict=True, max_length=2000)

    @field_validator("note", mode="before")
    @classmethod
    def normalize_note(cls, value: object) -> object:
        return value.strip() or None if isinstance(value, str) else value


class PurchaseRequestReject(StrictBoundary):
    rejection_reason: str = Field(strict=True, min_length=1, max_length=1000)

    @field_validator("rejection_reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class PurchaseRequestAction(StrictBoundary):
    pass


class PurchaseRequestFilters(StrictBoundary):
    status: PurchaseRequestStatus | None = None
    warehouse_id: PositiveInteger | None = None
    product_id: PositiveInteger | None = None
    requested_by_id: PositiveInteger | None = None
    created_from: AwareDatetime | None = None
    created_to: AwareDatetime | None = None

    @field_validator("created_from", "created_to", mode="before")
    @classmethod
    def parse_iso_timestamp(cls, value: object) -> datetime | None:
        if value is None or isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        raise ValueError("Datetime filters must be timezone-aware ISO timestamps.")

    @model_validator(mode="after")
    def validate_range(self) -> "PurchaseRequestFilters":
        if self.created_from and self.created_to and self.created_from > self.created_to:
            raise ValueError("created_from must not be after created_to.")
        return self


class PurchaseRequestDecisionResponse(StrictBoundary):
    kind: Literal["approved", "rejected"]
    actor_id: int
    decided_at: AwareDatetime
    rejection_reason: str | None


class PurchaseRequestFulfillmentResponse(StrictBoundary):
    outbound_id: int
    transaction_id: int
    actor_id: int
    fulfilled_at: AwareDatetime
    quantity_before: int
    quantity_after: int


class PurchaseRequestResponse(StrictBoundary):
    id: int
    request_number: str
    warehouse_id: int
    product_id: int
    quantity: int
    status: PurchaseRequestStatus
    requested_by_id: int
    created_at: AwareDatetime
    updated_at: AwareDatetime
    workflow_managed: bool
    note: str | None
    decision: PurchaseRequestDecisionResponse | None
    fulfillment: PurchaseRequestFulfillmentResponse | None
