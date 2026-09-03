from pydantic import BaseModel, ConfigDict, Field


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    parent_id: int | None = None


class CategoryResponse(CategoryCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = None


class SupplierResponse(SupplierCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    category_id: int
    supplier_id: int | None = None
    unit: str = Field(min_length=1, max_length=40)
    reorder_level: int = Field(default=0, ge=0)
    is_active: bool = True


class ProductResponse(ProductCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
