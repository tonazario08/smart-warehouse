from pydantic import BaseModel, ConfigDict, Field


class WarehouseCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    address: str = Field(min_length=1)
    latitude: float | None = None
    longitude: float | None = None


class WarehouseResponse(WarehouseCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
