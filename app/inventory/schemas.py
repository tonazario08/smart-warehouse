from pydantic import BaseModel, ConfigDict, Field


class InventoryMovementCreate(BaseModel):
    warehouse_id: int
    product_id: int
    quantity: int = Field(gt=0)
    reference: str | None = None
    note: str | None = None


class InventoryMovementResponse(InventoryMovementCreate):
    id: int


class TransactionResponse(BaseModel):
    id: int
    transaction_type: str
    warehouse_id: int
    product_id: int
    quantity: int


class StockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    warehouse_id: int
    product_id: int
    quantity: int
