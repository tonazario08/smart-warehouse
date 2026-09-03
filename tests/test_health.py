from fastapi.testclient import TestClient


def test_health_endpoint_reports_ready_service() -> None:
    """A missing or misconfigured application health route must be observable."""
    from app.main import create_app

    response = TestClient(create_app()).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
