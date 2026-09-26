from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import IntegrityError

from app.main import create_app


def test_validation_error_uses_stable_contract(test_client: TestClient) -> None:
    """Invalid request payloads expose the API's stable validation-error envelope."""
    response = test_client.post("/api/v1/auth/login", json={"email": "bad"})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "REQUEST_VALIDATION_ERROR"
    assert "fields" in detail


def test_configured_api_prefix_applies_to_router_endpoints(unit_settings) -> None:
    """Configured API prefixes must apply consistently to included routers."""
    settings = unit_settings.model_copy(update={"api_v1_prefix": "/internal/v1"})

    response = TestClient(create_app(settings)).post(
        "/internal/v1/auth/login", json={"email": "bad"}
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "REQUEST_VALIDATION_ERROR"


def test_framework_not_found_uses_common_error_contract(test_client: TestClient) -> None:
    """Router misses must use the common structured error envelope."""
    response = test_client.get("/route-that-does-not-exist")

    assert response.status_code == 404
    assert response.json() == {
        "detail": {"code": "HTTP_404_ERROR", "message": "Not Found", "fields": None}
    }


def test_application_http_error_uses_common_error_contract(unit_settings) -> None:
    """Application HTTP errors retain the common error envelope."""
    application = create_app(unit_settings)

    @application.get("/test/application-http-error")
    def application_http_error() -> None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    response = TestClient(application).get("/test/application-http-error")

    assert response.status_code == 401
    assert response.json() == {
        "detail": {"code": "HTTP_401_ERROR", "message": "Invalid credentials", "fields": None}
    }


def test_integrity_error_uses_safe_conflict_contract(unit_settings) -> None:
    """Integrity conflicts remain safe structured client conflicts."""
    application = create_app(unit_settings)

    @application.post("/test/integrity-error")
    def integrity_error() -> None:
        raise IntegrityError(
            "INSERT INTO users (email) VALUES ('duplicate@example.com')",
            {},
            Exception("duplicate email detail that must not escape"),
        )

    response = TestClient(application, raise_server_exceptions=False).post("/test/integrity-error")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "DATABASE_CONFLICT"
    assert "duplicate@example.com" not in response.text
    assert "duplicate email detail" not in response.text


def test_http_server_error_hides_internal_exception_details(unit_settings) -> None:
    """HTTP-originated server failures do not reflect internal details."""
    application = create_app(unit_settings)

    @application.get("/test/http-server-error")
    def http_server_error() -> None:
        raise HTTPException(status_code=500, detail="secret internal detail")

    response = TestClient(application, raise_server_exceptions=False).get("/test/http-server-error")

    assert response.status_code == 500
    assert response.json() == {
        "detail": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An internal error occurred.",
            "fields": None,
        }
    }
    assert "secret internal detail" not in response.text


def test_unhandled_error_hides_internal_exception_details(unit_settings) -> None:
    """Unexpected exception text never reaches the client response."""
    application: FastAPI = create_app(unit_settings)

    @application.get("/test/unhandled-error")
    def unhandled_error() -> None:
        raise RuntimeError("secret internal detail")

    response = TestClient(application, raise_server_exceptions=False).get("/test/unhandled-error")

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "INTERNAL_SERVER_ERROR"
    assert "secret internal detail" not in response.text


def test_validation_error_does_not_reflect_validator_exception_text(unit_settings) -> None:
    """A validator's exception may contain secrets and must stay out of responses."""

    class SensitiveRequest(BaseModel):
        value: str

        @field_validator("value")
        @classmethod
        def reject_value(cls, value: str) -> str:
            raise ValueError("SQL password=do-not-disclose")

    application = create_app(unit_settings)

    @application.post("/test/sensitive-validation")
    def sensitive_validation(_: SensitiveRequest) -> None:
        pass

    response = TestClient(application).post("/test/sensitive-validation", json={"value": "bad"})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "REQUEST_VALIDATION_ERROR"
    assert "value" in response.json()["detail"]["fields"]
    assert "do-not-disclose" not in response.text
    assert "password=" not in response.text
