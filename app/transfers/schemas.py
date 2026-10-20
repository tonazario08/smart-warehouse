"""Transfer API boundary models."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.inventory.schemas import MAX_STOCK_QUANTITY

PositiveInteger = Annotated[int, Field(strict=True, ge=1, le=MAX_STOCK_QUANTITY)]
MovementPurpose = Literal[
    "legacy_unknown", "standard_inbound", "standard_outbound", "transfer_in", "transfer_out",
    "purchase_request_fulfillment",
]


class TransferCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_warehouse_id: PositiveInteger
    destination_warehouse_id: PositiveInteger
    product_id: PositiveInteger
    quantity: PositiveInteger
    reference: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("reference", "note", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        return value.strip() or None if isinstance(value, str) else value

    @model_validator(mode="after")
    def distinct_warehouses(self) -> "TransferCreate":
        if self.source_warehouse_id == self.destination_warehouse_id:
            raise ValueError("Source and destination warehouses must differ.")
        return self


class TransferFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_warehouse_id: PositiveInteger | None = None
    destination_warehouse_id: PositiveInteger | None = None
    product_id: PositiveInteger | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None

    @field_validator("created_from", "created_to", mode="before")
    @classmethod
    def parse_iso_datetime(cls, value: object) -> datetime | None:
        if value is None or isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        raise ValueError("Datetime filters must be ISO timestamps.")

    @field_validator("created_from", "created_to")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Datetime filters must include a timezone.")
        return value

    @model_validator(mode="after")
    def validate_date_range(self) -> "TransferFilters":
        if self.created_from and self.created_to and self.created_from > self.created_to:
            raise ValueError("created_from must not be after created_to.")
        return self


class ProvenanceFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: PositiveInteger | None = None
    transfer_id: PositiveInteger | None = None
    purpose: MovementPurpose | None = None


class TransferResponse(TransferCreate):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    created_by_id: int
    created_at: datetime
    outbound_id: int
    inbound_id: int
    outbound_transaction_id: int
    inbound_transaction_id: int
    source_quantity_before: int
    source_quantity_after: int
    destination_quantity_before: int
    destination_quantity_after: int


class MovementProvenanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    transaction_id: int
    purpose: MovementPurpose
    transfer_id: int | None
