import pytest
from pydantic import ValidationError

from app.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.models import User, UserRole


@pytest.mark.parametrize("schema", [RegisterRequest, LoginRequest])
def test_auth_requests_normalize_email_and_reject_extra_fields(schema) -> None:
    request = schema.model_validate(
        {"email": " Person@Example.com ", "password": "long password 123"}
    )

    assert request.email == "person@example.com"
    with pytest.raises(ValidationError):
        schema.model_validate(
            {"email": "person@example.com", "password": "long password 123", "role": "admin"}
        )


@pytest.mark.parametrize("password", ["short", "p" * 129])
def test_registration_rejects_passwords_outside_supported_length(password: str) -> None:
    with pytest.raises(ValidationError):
        RegisterRequest.model_validate({"email": "person@example.com", "password": password})


def test_user_response_never_exposes_password_hash() -> None:
    user = User(
        id=7,
        email="person@example.com",
        password_hash="secret-hash",
        role=UserRole.CLIENT,
        is_active=True,
    )
    response = UserResponse.model_validate(user)

    assert response.model_dump() == {
        "id": 7,
        "email": "person@example.com",
        "role": "client",
        "is_active": True,
    }
    assert "password_hash" not in TokenResponse.model_fields
