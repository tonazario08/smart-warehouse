from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StrictBool,
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


class _ProductFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: StrictStr = Field(min_length=1, max_length=80)
    name: StrictStr = Field(min_length=1, max_length=200)
    description: StrictStr | None = None
    category_id: StrictInt
    supplier_id: StrictInt | None = None
    unit: StrictStr = Field(min_length=1, max_length=40)
    reorder_level: StrictInt = Field(default=0, ge=0)
    is_active: StrictBool = True

    @field_validator("sku", mode="before")
    @classmethod
    def normalize_sku(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("name", "unit", mode="before")
    @classmethod
    def strip_required_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ProductCreate(_ProductFields):
    pass


class ProductUpdate(_ProductFields):
    pass


class ProductResponse(_ProductFields):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
