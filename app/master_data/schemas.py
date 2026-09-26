from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StrictInt,
    StrictStr,
    field_validator,
)


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int


class CategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: StrictStr = Field(min_length=1, max_length=120)
    parent_id: StrictInt | None = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class CategoryUpdate(CategoryCreate):
    pass


class CategoryResponse(CategoryCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int


class _SupplierFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: StrictStr = Field(min_length=1, max_length=200)
    email: EmailStr | None = Field(default=None, max_length=320)
    phone: StrictStr | None = Field(default=None, max_length=50)
    address: StrictStr | None = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("email", mode="before")
    @classmethod
    def strip_email(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr | None) -> str | None:
        return str(value).lower() if value is not None else None

    @field_validator("phone", "address", mode="before")
    @classmethod
    def strip_optional_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("Must not be blank.")
        return normalized


class SupplierCreate(_SupplierFields):
    pass


class SupplierUpdate(_SupplierFields):
    pass


class SupplierResponse(_SupplierFields):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

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
