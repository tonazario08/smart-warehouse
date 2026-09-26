from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_session
from app.main import create_app


def test_legacy_health_endpoint_remains_available(unit_settings) -> None:
    """Existing clients can continue to use the original health URL."""
    response = TestClient(create_app(unit_settings)).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_liveness_does_not_touch_database() -> None:
    """Liveness remains available when the database dependency is unavailable."""
    application = create_app()

    def unavailable_database():
        raise AssertionError("Liveness must not resolve the database dependency.")

    application.dependency_overrides[get_session] = unavailable_database
    response = TestClient(application).get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness_reports_database_failure(unit_settings) -> None:
    """Readiness translates database failures without exposing database details."""

    class BrokenSession:
        def execute(self, _statement):
            raise SQLAlchemyError("database detail that must not escape")

    application = create_app(unit_settings)
    application.dependency_overrides[get_session] = lambda: BrokenSession()

    response = TestClient(application, raise_server_exceptions=False).get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "DATABASE_UNAVAILABLE"
    assert "database detail" not in response.text


def test_readiness_executes_database_probe(unit_settings) -> None:
    """Readiness succeeds only after the configured session executes SELECT 1."""

    class ProbeSession:
        def execute(self, statement):
            if str(statement) != "SELECT 1":
                raise AssertionError("Readiness must execute SELECT 1.")
            return 1

    application = create_app(unit_settings)
    application.dependency_overrides[get_session] = lambda: ProbeSession()

    response = TestClient(application).get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
