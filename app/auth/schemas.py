from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

from app.models import UserRole


class _EmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def strip_email(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).lower()


class RegisterRequest(_EmailRequest):
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(_EmailRequest):
    password: str


class ForgotPasswordRequest(_EmailRequest):
    pass


class ForgotPasswordResponse(BaseModel):
    message: str


class _PasswordReplacement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_password: SecretStr = Field(min_length=12, max_length=128)
    confirm_password: SecretStr = Field(min_length=12, max_length=128)


class ResetPasswordRequest(_PasswordReplacement):
    token: SecretStr = Field(min_length=1, max_length=128)


class ChangePasswordRequest(_PasswordReplacement):
    current_password: SecretStr = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    email: str
    role: UserRole
    is_active: bool


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str = "bearer"
    user: UserResponse
