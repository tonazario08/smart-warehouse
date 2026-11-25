"""Read-only replenishment API authority and contract checks."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.auth.dependencies import get_current_user
from app.core.config import Settings
from app.models import UserRole


def test_fixture_gate_only_in_test_or_integration(unit_settings):
    fields = dict(
        app_env="development",
        database_url="postgresql+psycopg://x:x@localhost/x",
        jwt_secret_key="test-key",
        replenishment_allow_fixture=True,
        _env_file=None,
    )
    with pytest.raises(ValidationError):
        Settings(**fields)
    assert Settings(**{**fields, "app_env": "integration"}).replenishment_allow_fixture


def test_unconfigured_status_and_scoped_authority(unit_settings):
    from app.main import create_app

    app = create_app(unit_settings)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=UserRole.WAREHOUSE)
    with TestClient(app) as client:
        response = client.get("/api/v1/replenishment/status?mode=operational")
        assert response.status_code == 200
        assert response.json()["reason_code"] == "NO_REVIEWED_POLICY_INPUTS"
        listing = client.get("/api/v1/replenishment/runs?mode=operational")
        assert listing.status_code == 200 and listing.json()["total"] == 0
        assert client.get("/api/v1/replenishment/status?mode=research").status_code == 403
        assert (
            client.get("/api/v1/replenishment/runs?mode=operational&mode=research").status_code
            == 422
        )
        assert client.get("/api/v1/replenishment/runs?mode=operational&extra=1").status_code == 422
        assert client.get("/api/v1/replenishment/runs?mode=operational&page=0").status_code == 422
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=UserRole.CLIENT)
    with TestClient(app) as client:
        assert client.get("/api/v1/replenishment/status?mode=operational").status_code == 403


def test_warehouse_cannot_probe_research_directory(unit_settings, tmp_path, monkeypatch):
    from pathlib import Path

    from app.main import create_app

    run_id = "rrv1-" + "a" * 64
    folder = tmp_path / "research" / run_id
    folder.mkdir(parents=True)
    (folder / "public-manifest.json").write_text("invalid", encoding="utf8")
    original = Path.iterdir

    def guarded(path):
        if "research" in path.parts:
            raise AssertionError("research directory probed")
        return original(path)

    monkeypatch.setattr(Path, "iterdir", guarded)
    app = create_app(unit_settings.model_copy(update={"replenishment_catalog_root": tmp_path}))
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=UserRole.WAREHOUSE)
    with TestClient(app) as client:
        assert client.get("/api/v1/replenishment/runs/" + run_id).status_code == 404
        assert client.get("/api/v1/replenishment/runs?mode=operational").json()["total"] == 0


def test_synthetic_artifact_read_binding_filters_snapshot_and_failure(
    unit_settings, tmp_path, monkeypatch
):
    from app.db.session import get_session
    from app.main import create_app
    from app.models import Product, Warehouse
    from app.replenishment.artifacts import publish_catalog, publish_failure, publish_run
    from app.replenishment.calibration import calibrate
    from app.replenishment.inputs import load_inputs
    from app.replenishment.simulation import simulate
    from tests.replenishment_helpers import operational_context

    bundle, forecast, auth, config = operational_context(tmp_path)
    inputs = load_inputs(forecast, bundle, config, auth)
    result = simulate(inputs, calibrate(inputs, config), config)
    published = publish_run(inputs, config, result, auth, tmp_path / "runs")
    catalog = tmp_path / "replenishment-catalog"
    public = publish_catalog(published.path, auth, catalog)

    class Session:
        product = SimpleNamespace(id=1, name="Synthetic product", sku="SYN", unit="unit")
        warehouse = SimpleNamespace(id=2, name="Synthetic warehouse", code="SYN-W")

        def get(self, model, key):
            return (
                self.product
                if model is Product and key == 1
                else self.warehouse
                if model is Warehouse and key == 2
                else None
            )

    session = Session()
    app = create_app(
        unit_settings.model_copy(
            update={"replenishment_catalog_root": catalog, "replenishment_allow_fixture": True}
        )
    )
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=UserRole.WAREHOUSE)
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as client:
        status = client.get("/api/v1/replenishment/status?mode=operational")
        assert status.status_code == 200 and status.json()["state"] == "ready"
        assert status.json()["latest"]["fixture_label"] == "Dữ liệu kiểm thử"
        run = client.get("/api/v1/replenishment/runs/" + published.run_id)
        assert run.status_code == 200
        view = run.json()
        assert view["entity"]["product_id"] == 1 and view["entity"]["warehouse_id"] == 2
        assert len(view["summaries"]) == 36 and all(
            "rop_min" in x and "rop_max" in x for x in view["summaries"]
        )
        base = (
            "/api/v1/replenishment/runs/"
            + published.run_id
            + "/days?algorithm=xgboost&lead_time=7&policy=proposed"
        )
        one = client.get(base + "&service=.8&page=1&page_size=7")
        two = client.get(base + "&service=0.80&page=1&page_size=7")
        assert one.status_code == two.status_code == 200 and one.json() == two.json()
        assert one.json()["total"] == 178 and len(one.json()["items"]) == 7
        import app.replenishment.repository as repository

        verify = repository.verify_public_projection
        days_path = public / "days.jsonl"
        original_days = days_path.read_bytes()

        def mutate_after_verification(path, **kwargs):
            snapshot = verify(path, **kwargs)
            days_path.write_bytes(b"{}\n")
            return snapshot

        monkeypatch.setattr(repository, "verify_public_projection", mutate_after_verification)
        try:
            checked = client.get(base + "&service=.8&page=1&page_size=7")
            assert checked.status_code == 200 and checked.json() == one.json()
        finally:
            days_path.write_bytes(original_days)
            monkeypatch.setattr(repository, "verify_public_projection", verify)
        assert client.get(base + "&service=.90&service=.8").status_code == 422
        assert client.get(base + "&service=.85").status_code == 422
        assert client.get(base + "&service=NaN").status_code == 422
        assert client.get(base + "&lead_time=2").status_code == 422
        session.product.unit = "different"
        assert client.get("/api/v1/replenishment/runs/" + published.run_id).status_code == 409
        unavailable = client.get("/api/v1/replenishment/status?mode=operational")
        assert unavailable.status_code == 200 and unavailable.json()["state"] == "unavailable"
        assert unavailable.json()["reason_code"] == "BINDING_UNAVAILABLE"
        assert client.get("/api/v1/replenishment/runs?mode=operational").status_code == 409
        assert client.get(base + "&service=.8").status_code == 409
        session.product = None
        assert (
            client.get("/api/v1/replenishment/status?mode=operational").json()["reason_code"]
            == "BINDING_UNAVAILABLE"
        )
        session.product = SimpleNamespace(id=1, name="Synthetic product", sku="SYN", unit="unit")
        session.product.unit = "unit"
        with pytest.raises(ValueError, match="failure was not observed"):
            publish_failure(config, auth, catalog, "FORECAST_STALE")
        from datetime import date

        stale_config = config.model_copy(update={"evaluation_end": date(2023, 2, 1)})
        publish_failure(stale_config, auth, catalog, "FORECAST_STALE")
        failed = client.get("/api/v1/replenishment/status?mode=operational")
        assert failed.status_code == 200 and failed.json()["state"] == "failed"
        assert failed.json()["reason_code"] == "FORECAST_STALE"
        (public / "days.jsonl").unlink()
        assert client.get("/api/v1/replenishment/runs/" + published.run_id).status_code == 409
    assert public.name == published.run_id


def test_missing_configured_catalog_is_unavailable(unit_settings, tmp_path):
    from app.main import create_app

    app = create_app(
        unit_settings.model_copy(update={"replenishment_catalog_root": tmp_path / "missing"})
    )
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=UserRole.ADMIN)
    with TestClient(app) as client:
        response = client.get("/api/v1/replenishment/status?mode=operational")
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "REPLENISHMENT_CATALOG_UNAVAILABLE"


def test_api_import_does_not_require_optional_ml_packages():
    import subprocess
    import sys

    code = """import importlib.metadata, sys
original = importlib.metadata.version
def check(name):
    if name.lower() in ('numpy','scipy','xgboost'):
        raise AssertionError('optional metadata requested')
    return original(name)
importlib.metadata.version = check
import app.replenishment.router
assert not any(name in sys.modules for name in ('numpy','scipy','xgboost'))
"""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr


def test_binding_status_is_unavailable_and_other_reads_fail_closed():
    from app.core.errors import DomainError
    from app.models import UserRole
    from app.replenishment.service import ReplenishmentService

    snapshot = {
        "manifest": {
            "binding": {"product_id": 1, "warehouse_id": 2, "unit": "unit"},
            "applicability": "fixture_scenario",
            "dataset_class": "fixture",
        }
    }

    class Repo:
        def index(self, mode):
            return ((datetime(2022, 1, 1, tzinfo=UTC), "id", "path"),)

        def latest_failure(self, mode):
            return None

        def snapshot(self, path):
            return snapshot

        def scoped(self, run_id, scopes):
            return snapshot

    class Session:
        def get(self, model, key):
            return None

    from datetime import UTC, datetime

    svc = ReplenishmentService(Repo(), Session())
    actor = SimpleNamespace(role=UserRole.WAREHOUSE)
    assert svc.status(actor, "operational") == {
        "state": "unavailable",
        "reason_code": "BINDING_UNAVAILABLE",
        "latest": None,
    }
    with pytest.raises(DomainError) as error:
        svc.list_runs(actor, "operational", 1, 20)
    assert error.value.code == "REPLENISHMENT_BINDING_UNAVAILABLE"
    with pytest.raises(DomainError):
        svc._view(svc.get(actor, "id"), detail=True)


def test_research_permission_is_backend_authority(unit_settings, tmp_path, monkeypatch):
    from app.auth.dependencies import PERMISSION_ROLES, Permission
    from app.main import create_app

    monkeypatch.setitem(PERMISSION_ROLES, Permission.REPLENISHMENT_RESEARCH_READ, frozenset())
    app = create_app(unit_settings.model_copy(update={"replenishment_catalog_root": tmp_path}))
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=UserRole.ADMIN)
    with TestClient(app) as client:
        response = client.get("/api/v1/replenishment/status?mode=research")
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "REPLENISHMENT_FORBIDDEN"


def test_list_verifies_only_selected_page():
    from app.replenishment.service import ReplenishmentService

    class Repo:
        calls = []

        def index(self, mode):
            return tuple((None, str(i), str(i)) for i in range(50))

        def snapshot(self, path):
            self.calls.append(path)
            return {
                "manifest": {
                    "binding": None,
                    "applicability": "research_scenario",
                    "dataset_class": "research",
                }
            }

    repo = Repo()
    service = ReplenishmentService(repo, None)
    page = service.list_runs(SimpleNamespace(role=UserRole.ADMIN), "research", 2, 7)
    assert page["total"] == 50 and len(page["items"]) == 7
    assert repo.calls == [str(i) for i in range(7, 14)]
