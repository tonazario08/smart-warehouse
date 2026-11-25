from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.auth.dependencies import get_current_user
from app.core.config import Settings
from app.models import UserRole


def test_fixture_serving_is_only_available_to_test_or_integration(unit_settings):
    fields = dict(
        app_env="development",
        database_url="postgresql+psycopg://x:x@localhost/x",
        jwt_secret_key="test-key",
        forecast_allow_fixture=True,
        _env_file=None,
    )
    with pytest.raises(ValidationError):
        Settings(**fields)
    assert Settings(**{**fields, "app_env": "integration"}).forecast_allow_fixture


def test_auth_and_scope_precede_catalog_access(unit_settings, tmp_path):
    from app.main import create_app

    app = create_app(unit_settings.model_copy(update={"forecast_catalog_root": tmp_path}))
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=UserRole.WAREHOUSE)
    with TestClient(app) as client:
        assert client.get("/api/v1/forecasts/status?mode=research").status_code == 403
        assert client.get("/api/v1/forecasts/status?mode=operational").status_code == 200
        assert client.get("/api/v1/forecasts/runs?mode=operational&page=0").status_code == 422
        assert (
            client.get("/api/v1/forecasts/runs?mode=operational&mode=research").status_code == 422
        )


def test_warehouse_never_opens_research_for_guessed_id(unit_settings, tmp_path, monkeypatch):
    from pathlib import Path

    from app.main import create_app

    run_id = "frv1-" + "a" * 64
    (tmp_path / "research" / run_id).mkdir(parents=True)
    (tmp_path / "research" / run_id / "public-manifest.json").write_text("invalid")
    original = Path.iterdir

    def guarded(path):
        if "research" in path.parts:
            raise AssertionError("unauthorized directory access")
        return original(path)

    monkeypatch.setattr(Path, "iterdir", guarded)
    app = create_app(unit_settings.model_copy(update={"forecast_catalog_root": tmp_path}))
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=UserRole.WAREHOUSE)
    with TestClient(app) as client:
        assert client.get("/api/v1/forecasts/runs/" + run_id).status_code == 404
        assert client.get("/api/v1/forecasts/runs?mode=operational").json()["total"] == 0


def test_research_access_uses_research_permission(unit_settings, tmp_path, monkeypatch):
    from app.auth.dependencies import PERMISSION_ROLES, Permission
    from app.main import create_app

    monkeypatch.setitem(PERMISSION_ROLES, Permission.FORECAST_RESEARCH_READ, frozenset())
    app = create_app(unit_settings.model_copy(update={"forecast_catalog_root": tmp_path}))
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=UserRole.ADMIN)
    with TestClient(app) as client:
        assert client.get("/api/v1/forecasts/status?mode=research").status_code == 403


def test_horizon_openapi_and_runtime_match(unit_settings, tmp_path):
    from app.main import create_app

    app = create_app(unit_settings.model_copy(update={"forecast_catalog_root": tmp_path}))
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=UserRole.ADMIN)
    with TestClient(app) as client:
        operation = client.get("/openapi.json").json()["paths"][
            "/api/v1/forecasts/runs/{run_id}/predictions"
        ]["get"]
        schema = next(
            item["schema"] for item in operation["parameters"] if item["name"] == "horizon"
        )
        assert schema["enum"] == [1, 7, None]
        run_id = "frv1-" + "a" * 64
        assert (
            client.get(f"/api/v1/forecasts/runs/{run_id}/predictions?horizon=7").status_code == 404
        )
        assert (
            client.get(f"/api/v1/forecasts/runs/{run_id}/predictions?horizon=2").status_code == 422
        )


def test_unsupported_public_schema_has_specific_safe_error(unit_settings, tmp_path):
    from app.main import create_app

    run_id = "frv1-" + "b" * 64
    run = tmp_path / "research" / run_id
    run.mkdir(parents=True)
    (run / "public-manifest.json").write_text(
        '{"schema_version":"forecast-public-run/9"}', encoding="utf-8"
    )
    app = create_app(unit_settings.model_copy(update={"forecast_catalog_root": tmp_path}))
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=UserRole.ADMIN)
    with TestClient(app) as client:
        response = client.get("/api/v1/forecasts/runs/" + run_id)
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "FORECAST_SCHEMA_UNSUPPORTED"


def test_status_exposes_only_scoped_published_failure(unit_settings, tmp_path):
    from app.forecasting.artifacts import publish_failure, write_failure_receipt
    from app.main import create_app
    from tests.forecasting_helpers import config

    receipt = write_failure_receipt(config(), tmp_path / "output", "FIT_FAILED")
    publish_failure(receipt, tmp_path / "catalog")
    settings = unit_settings.model_copy(
        update={"forecast_catalog_root": tmp_path / "catalog", "forecast_allow_fixture": True}
    )
    app = create_app(settings)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=UserRole.ADMIN)
    with TestClient(app) as client:
        response = client.get("/api/v1/forecasts/status?mode=research")
        assert response.status_code == 200 and response.json()["state"] == "failed"
        assert response.json()["reason_code"] == "FIT_FAILED"
        assert response.json()["latest_failure_code"] == "FIT_FAILED"
        assert client.get("/api/v1/forecasts/runs?mode=research").json()["total"] == 0
