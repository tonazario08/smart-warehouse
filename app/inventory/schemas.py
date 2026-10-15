from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import TransactionType

MAX_STOCK_QUANTITY = 2_147_483_647


class InventoryFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    warehouse_id: int | None = Field(default=None, gt=0)
    product_id: int | None = Field(default=None, gt=0)
    created_from: datetime | None = None
    created_to: datetime | None = None

    @field_validator("created_from", "created_to")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Datetime filters must include a timezone.")
        return value

    @model_validator(mode="after")
    def validate_date_range(self) -> "InventoryFilters":
        if (
            self.created_from is not None
            and self.created_to is not None
            and self.created_from > self.created_to
        ):
            raise ValueError("created_from must not be after created_to.")
        return self


class TransactionFilters(InventoryFilters):
    transaction_type: TransactionType | None = None


class InventoryMovementCreate(BaseModel):
    warehouse_id: int
    product_id: int
    quantity: int = Field(gt=0, le=MAX_STOCK_QUANTITY)
    reference: str | None = Field(default=None, max_length=120)
    note: str | None = None


class InventoryMovementResponse(InventoryMovementCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int


class InventoryMovementReadResponse(InventoryMovementCreate):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    created_by_id: int
    created_at: datetime


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    transaction_type: str
    warehouse_id: int
    product_id: int
    quantity: int
    inbound_id: int | None
    outbound_id: int | None
    created_by_id: int
    created_at: datetime


class StockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    warehouse_id: int
    product_id: int
    quantity: int
    created_at: datetime
