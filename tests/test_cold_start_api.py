from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.auth.security import create_access_token
from app.cold_start.catalog import publish_failure, publish_report
from app.core.config import Settings
from app.db.session import get_session
from app.main import create_app
from app.models import UserRole
from tests.test_cold_start_catalog import make_report


def test_environment_fixture_gate(unit_settings):
    with pytest.raises(ValidationError):
        Settings.model_validate(
            {
                **unit_settings.model_dump(),
                "app_env": "development",
                "database_url": "postgresql+psycopg://localhost/test",
                "cold_start_allow_fixture": True,
            }
        )


def test_real_auth_permissions_status_stale_and_failure(unit_settings, tmp_path):
    report = make_report(tmp_path)
    root = tmp_path / "catalog"
    run_id = publish_report(report, root)
    settings = unit_settings.model_copy(
        update={"cold_start_catalog_root": root, "cold_start_allow_fixture": True}
    )
    app = create_app(settings)
    actor = SimpleNamespace(role=UserRole.WAREHOUSE, is_active=True, auth_version=0)

    class Session:
        def scalar(self, statement):
            return actor

        def add(self, *args):
            raise AssertionError("write")

        def commit(self):
            raise AssertionError("write")

    app.dependency_overrides[get_session] = lambda: Session()
    token = create_access_token(1, settings)
    with TestClient(app) as client:
        assert client.get("/api/v1/forecasts/cold-start/status").status_code == 401
        headers = {"Authorization": f"Bearer {token}"}
        actor.role = UserRole.CLIENT
        assert client.get("/api/v1/forecasts/cold-start/status", headers=headers).status_code == 403
        actor.role = UserRole.WAREHOUSE
        status = client.get("/api/v1/forecasts/cold-start/status", headers=headers)
        assert status.status_code == 200 and status.json()["state"] == "ready"
        assert status.json()["latest_run_id"] == run_id
        run = client.get("/api/v1/forecasts/cold-start/runs/" + run_id, headers=headers)
        assert run.status_code == 200 and run.json()["stale"] is False
        assert (
            client.get("/api/v1/forecasts/cold-start/runs/invalid", headers=headers).status_code
            == 404
        )
        assert (
            client.get(
                "/api/v1/forecasts/cold-start/runs/csv1-" + "f" * 64, headers=headers
            ).status_code
            == 404
        )
    old = report.model_copy(update={"created_at": datetime.now(UTC) - timedelta(days=8)})
    other = tmp_path / "old"
    old_id = publish_report(old, other)
    old_settings = settings.model_copy(update={"cold_start_catalog_root": other})
    old_app = create_app(old_settings)
    old_app.dependency_overrides[get_session] = lambda: Session()
    with TestClient(old_app) as client:
        assert (
            client.get("/api/v1/forecasts/cold-start/status", headers=headers).json()["state"]
            == "stale"
        )
        assert (
            client.get("/api/v1/forecasts/cold-start/runs/" + old_id, headers=headers).json()[
                "stale"
            ]
            is True
        )
    publish_failure(other, "NO_ELIGIBLE_TRAINING_SNAPSHOTS", datetime.now(UTC))
    with TestClient(old_app) as client:
        status = client.get("/api/v1/forecasts/cold-start/status", headers=headers).json()
        assert status["state"] == "unavailable" and status["latest_run_id"] is None


def test_corrupt_status_and_io_fail_closed(unit_settings, tmp_path, monkeypatch):
    from app.cold_start import catalog

    report = make_report(tmp_path)
    root = tmp_path / "catalog"
    run_id = publish_report(report, root)
    settings = unit_settings.model_copy(
        update={"cold_start_catalog_root": root, "cold_start_allow_fixture": True}
    )
    app = create_app(settings)

    class Session:
        def scalar(self, statement):
            return SimpleNamespace(role=UserRole.ADMIN, is_active=True, auth_version=0)

    app.dependency_overrides[get_session] = lambda: Session()
    token = create_access_token(1, settings)
    headers = {"Authorization": f"Bearer {token}"}
    with TestClient(app) as client:
        path = root / run_id
        original = path.read_bytes()
        path.write_bytes(b"corrupt")
        status = client.get("/api/v1/forecasts/cold-start/status", headers=headers)
        assert status.status_code == 409
        assert (
            client.get("/api/v1/forecasts/cold-start/runs/" + run_id, headers=headers).status_code
            == 409
        )
        path.write_bytes(original)

        def fail(*args, **kwargs):
            raise OSError("sensitive filesystem detail")

        monkeypatch.setattr(catalog, "_bounded_read", fail)
        response = client.get("/api/v1/forecasts/cold-start/runs/" + run_id, headers=headers)
        assert response.status_code == 503
        assert "sensitive filesystem detail" not in response.text


def test_hidden_fixture_future_and_published_failed_state(unit_settings, tmp_path):
    report = make_report(tmp_path)
    root = tmp_path / "catalog"
    future = report.model_copy(update={"created_at": datetime.now(UTC) + timedelta(days=1)})
    run_id = publish_report(future, root)
    settings = unit_settings.model_copy(
        update={"cold_start_catalog_root": root, "cold_start_allow_fixture": True}
    )
    actor = SimpleNamespace(role=UserRole.ADMIN, is_active=True, auth_version=0)

    class Session:
        def scalar(self, statement):
            return actor

    app = create_app(settings)
    app.dependency_overrides[get_session] = lambda: Session()
    headers = {"Authorization": f"Bearer {create_access_token(1, settings)}"}
    with TestClient(app) as client:
        assert (
            client.get("/api/v1/forecasts/cold-start/status", headers=headers).json()["state"]
            == "stale"
        )
        assert client.get("/api/v1/forecasts/cold-start/runs/" + run_id, headers=headers).json()[
            "stale"
        ]
    hidden = create_app(settings.model_copy(update={"cold_start_allow_fixture": False}))
    hidden.dependency_overrides[get_session] = lambda: Session()
    with TestClient(hidden) as client:
        assert (
            client.get("/api/v1/forecasts/cold-start/runs/" + run_id, headers=headers).status_code
            == 404
        )
        assert (
            client.get("/api/v1/forecasts/cold-start/status", headers=headers).json()["state"]
            == "unavailable"
        )
    publish_failure(root, "EVALUATION_FAILED", datetime.now(UTC) + timedelta(days=2))
    with TestClient(app) as client:
        status = client.get("/api/v1/forecasts/cold-start/status", headers=headers).json()
        assert status["state"] == "failed" and status["reason_code"] == "EVALUATION_FAILED"


def test_all_null_predictions_give_unavailable_status(unit_settings, tmp_path):
    from app.cold_start.benchmark import evaluate_cold_start
    from app.cold_start.dataset import load_fixture_dataset
    from tests.cold_start_helpers import fixture_config

    source = tmp_path / "source"
    source.mkdir()
    report = evaluate_cold_start(load_fixture_dataset(fixture_config(source, count=4), source))
    report = report.model_copy(update={"created_at": datetime.now(UTC)})
    root = tmp_path / "catalog"
    publish_report(report, root)
    settings = unit_settings.model_copy(
        update={"cold_start_catalog_root": root, "cold_start_allow_fixture": True}
    )
    app = create_app(settings)

    class Session:
        def scalar(self, statement):
            return SimpleNamespace(role=UserRole.ADMIN, is_active=True, auth_version=0)

    app.dependency_overrides[get_session] = lambda: Session()
    headers = {"Authorization": f"Bearer {create_access_token(1, settings)}"}
    with TestClient(app) as client:
        status = client.get("/api/v1/forecasts/cold-start/status", headers=headers).json()
        assert (
            status["state"] == "unavailable" and status["reason_code"] == "NO_ELIGIBLE_PREDICTIONS"
        )
        assert status["latest_run_id"] is None
