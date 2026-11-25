"""Public projections omit all client-identifying details."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

State = Literal["computing", "available", "insufficient_data", "failed"]


class ContextRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    warehouse_id: int
    product_id: int
    sku: str
    unit: str
    state: State
    reason_code: str | None = None
    computed_at: datetime | None = None


class OpenDemandRead(ContextRead):
    forecast_run_id: str | None = None
    forecast_dataset_class: str | None = None
    forecast_stale: bool | None = None
    pending_quantity: int | None = None
    approved_quantity: int | None = None
    open_quantity: int | None = None
    order_count: int | None = None


class ReplenishmentPositionRead(ContextRead):
    on_hand: int | None
    open_quantity: int
    projected_quantity: int | None
    rop: float | None = None
    rop_date: date | None = None
    eoq: int | None = None
    recommendation: bool = False
    dataset_class: str | None = None
    run_id: str | None = None


class OrderCheckRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purchase_request_id: int
    warehouse_id: int
    product_id: int
    state: State
    reason_code: str | None = None
    computed_at: datetime | None = None
    flagged: bool | None = None
    rule_id: str | None = None
    rule_version: int | None = None
    sample_count: int | None = None
    median: float | None = None
    mad: float | None = None
    score: float | None = None
    label: str | None = None
