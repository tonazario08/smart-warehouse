"""One authentic paired fixture, plus verification of the read-only boundary."""

import json
from hashlib import sha256
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.db.session import get_session
from app.main import create_app
from app.models import Product, UserRole, Warehouse
from app.replenishment.pilot import threshold
from tests.replenishment_helpers import operational_context

BASE = "/api/v1/replenishment/runs/"


@pytest.mark.parametrize(("position", "expected"), [
    (13, "at_or_below"), (14, "at_or_below"), (15, "above"),
])
def test_threshold_explicitly_includes_equality(position, expected):
    assert threshold(position, 14) == expected


def test_actual_paired_artifacts_roles_identity_and_tamper(unit_settings, tmp_path):
    from app.replenishment.artifacts import publish_catalog, publish_run
    from app.replenishment.calibration import calibrate
    from app.replenishment.inputs import load_inputs
    from app.replenishment.simulation import simulate

    bundle, forecast, auth, config = operational_context(
        tmp_path / "fixture", product_id=2, warehouse_id=2,
    )
    inputs = load_inputs(forecast, bundle, config, auth)
    run = publish_run(inputs, config, simulate(inputs, calibrate(inputs, config), config),
                      auth, tmp_path / "policy-runs")
    policy = publish_catalog(run.path, auth, tmp_path / "policy-catalog")
    settings = unit_settings.model_copy(update={
        "forecast_catalog_root": forecast.parent.parent,
        "forecast_allow_fixture": True,
        "replenishment_catalog_root": policy.parent.parent,
        "replenishment_allow_fixture": True,
    })

    class Session:
        unit = "unit"
        sku = "M7-E2E-SYNTHETIC"

        def get(self, model, pk):
            assert pk == 2
            if model is Product:
                return SimpleNamespace(id=2, name="Fixture", sku=self.sku, unit=self.unit,
                                       is_active=True)
            if model is Warehouse:
                return SimpleNamespace(id=2, name="Fixture", code="M7-E2E-SYNTHETIC",
                                       is_active=True)
            raise AssertionError("unexpected DB access")

    session = Session()
    actor = SimpleNamespace(role=UserRole.ADMIN)
    app = create_app(settings)
    path = BASE + run.run_id + "/forecast-pilot"
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as client:
        assert client.get(path).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: actor
        for role in (UserRole.ADMIN, UserRole.WAREHOUSE):
            actor.role = role
            response = client.get(path)
            assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
            summary = response.json()
            assert summary["state"] == "ready" and summary["reason_code"] is None
            pilot = summary["pilot"]
            assert pilot["forecast_run_id"] == forecast.name
            assert pilot["replenishment_run_id"] == run.run_id
            assert (pilot["warehouse_id"], pilot["product_id"], pilot["unit"]) == (2, 2, "unit")
            assert pilot["lead_time"] == 7 and pilot["service_level"] == "0.90"
            assert pilot["scenario_day"] > pilot["origin"]
            assert pilot["forecast_during_lead_time"] == "14"
            assert pilot["rop"] == 14 and pilot["safety_stock"] == "0"
            assert pilot["holdout_wape"] == "0"
        assert client.get(path + "?lead_time=1").status_code == 422
        actor.role = UserRole.CLIENT
        assert client.get(path).status_code == 403
        actor.role = UserRole.WAREHOUSE
        for field, bad in [("unit", "each"), ("sku", "REAL-ID-REUSED")]:
            original = getattr(session, field)
            setattr(session, field, bad)
            assert client.get(path).json()["state"] == "unavailable"
            setattr(session, field, original)
        hidden = client.get(BASE + "rrv1-" + "0" * 64 + "/forecast-pilot")
        assert hidden.status_code == 404

        # A reprojected byte stream can still be structurally valid with the same run
        # ID. The policy pins the exact upstream bytes, not merely the display ID.
        from app.analytics.export import canonical_json
        from app.forecasting.repository import verify_catalog_run

        raw = forecast / "public-manifest.json"
        reprojection = json.loads(raw.read_bytes())
        del reprojection["projection_sha256"]
        reprojection["limitations"].append("different public projection")
        reprojection["projection_sha256"] = sha256(canonical_json(reprojection)).hexdigest()
        raw.write_bytes(canonical_json(reprojection))
        assert verify_catalog_run(forecast, allow_fixture=True).manifest.run_id == forecast.name
        assert client.get(path).json() == {
            "state": "unavailable", "reason_code": "ARTIFACT_MISMATCH", "pilot": None,
        }
        forecast.rename(forecast.with_name(forecast.name + "_missing"))
        assert client.get(path).json() == {
            "state": "unavailable", "reason_code": "SOURCE_UNAVAILABLE", "pilot": None,
        }

    disabled = create_app(settings.model_copy(update={"forecast_allow_fixture": False}))
    disabled.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=UserRole.ADMIN)
    disabled.dependency_overrides[get_session] = lambda: session
    with TestClient(disabled) as client:
        assert client.get(path).status_code == 404
