"""Strict schemas for managed user administration."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StrictBool, field_validator

from app.models import UserRole


class ManagedRole(StrEnum):
    CLIENT = "client"
    WAREHOUSE = "warehouse"


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: ManagedRole

    @field_validator("email", mode="before")
    @classmethod
    def strip_email(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).lower()


class UserRoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: ManagedRole


class UserStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: StrictBool


class ManagedUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    email: EmailStr
    role: UserRole
    is_active: bool
