from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_session
from app.main import create_app


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
