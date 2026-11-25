from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.db.session import get_session
from app.models import UserRole
from app.order_analytics import router as api

BASE = "/api/v1/order-analytics"
KEY = "warehouse_id=1&product_id=2"
ENDPOINTS = ("open-demand", "replenishment-position", "order-checks")


@pytest.fixture
def app(unit_settings, monkeypatch):
    from app.main import create_app

    application = create_app(unit_settings)
    application.dependency_overrides[get_session] = object
    position = SimpleNamespace(
        warehouse_id=1,
        product_id=2,
        sku="FAKE",
        unit="each",
        on_hand=10,
        pending_quantity=5,
        approved_quantity=3,
        total_quantity=8,
        order_count=2,
        projected_quantity=2,
    )
    monkeypatch.setattr(api, "read_position", lambda *args: position)
    monkeypatch.setattr(api, "get_latest_job", lambda *args: None)
    monkeypatch.setattr(api, "has_pending_job", lambda *args: False)
    monkeypatch.setattr(api, "get_key_state", lambda *args: None)
    monkeypatch.setattr(api, "query_order_checks", lambda *a, **kw: ([], 0))
    return application


def test_permissions_and_explicit_filters(app):
    def request(client, expected):
        for endpoint in ENDPOINTS:
            assert client.get(f"{BASE}/{endpoint}?{KEY}").status_code == expected

    with TestClient(app) as client:
        request(client, 401)
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=UserRole.CLIENT)
        request(client, 403)
        for role in (UserRole.WAREHOUSE, UserRole.ADMIN):
            app.dependency_overrides[get_current_user] = lambda role=role: SimpleNamespace(
                role=role
            )
            request(client, 200)
        assert client.get(f"{BASE}/open-demand?{KEY}&warehouse_id=2").status_code == 422
        assert client.get(f"{BASE}/open-demand?{KEY}&foo=1").status_code == 422
        assert client.get(f"{BASE}/replenishment-position?{KEY}&lead_time=7").status_code == 200
        assert client.get(f"{BASE}/replenishment-position?{KEY}&lead_time=2").status_code == 422
        assert client.get(f"{BASE}/order-checks?{KEY}&page_size=101").status_code == 422


def test_context_missing_and_fixture_only_demo(app, monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=UserRole.ADMIN)
    with TestClient(app) as client:
        forecast = client.get(f"{BASE}/open-demand?{KEY}").json()
        assert forecast["reason_code"] == "BASELINE_NOT_FOUND" and forecast["open_quantity"] is None
        repl = client.get(f"{BASE}/replenishment-position?{KEY}").json()
        assert repl["projected_quantity"] == 2
        assert repl["reason_code"] == "OPERATIONAL_ROP_NOT_FOUND" and not repl["recommendation"]
        state = SimpleNamespace(
            computed_at=None,
            forecast_status="available",
            forecast_run_id="fake-forecast",
            forecast_dataset_class="fixture",
            forecast_stale=True,
            replenishment_status="available",
            replenishment_run_id="fake-replenishment",
            replenishment_demo_run_id="fake-replenishment",
        )
        monkeypatch.setattr(api, "get_key_state", lambda *args: state)
        settings = next(
            callback()
            for dependency, callback in app.dependency_overrides.items()
            if dependency.__name__ == "get_settings"
        )
        settings.replenishment_catalog_root = "."
        day = date(2022, 7, 8)
        snapshot = {
            "manifest": {
                "mode": "operational",
                "reporting_scope": "warehouse",
                "dataset_class": "fixture",
                "binding": {"warehouse_id": 1, "product_id": 2, "unit": "each"},
            },
            "calibration": {"eoq": {"quantity": 86}},
            "days": {
                ("xgboost", 1, "0.90", "proposed"): (
                    SimpleNamespace(day=day, warmup=False, reorder_point=2),
                )
            },
        }
        monkeypatch.setattr(api.ReplenishmentRepository, "scoped", lambda *args: snapshot)
        forecast = client.get(f"{BASE}/open-demand?{KEY}").json()
        assert forecast["forecast_dataset_class"] == "fixture"
        assert forecast["open_quantity"] == 8 and "combined_forecast" not in forecast
        operational = client.get(f"{BASE}/replenishment-position?{KEY}").json()
        assert not operational["recommendation"] and operational["rop"] is None
        demo = client.get(f"{BASE}/replenishment-position?{KEY}&view=demo").json()
        assert demo["dataset_class"] == "fixture" and demo["rop"] == 2 and demo["eoq"] == 86
        assert not demo["recommendation"]


def test_demo_reference_is_read_from_exact_verified_run(app, monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=UserRole.WAREHOUSE)
    requested = "rrv1-" + "c" * 64
    stored = "rrv1-" + "d" * 64
    state = SimpleNamespace(
        computed_at=None,
        replenishment_status="insufficient_data",
        replenishment_run_id=None,
        replenishment_demo_run_id=stored,
    )
    monkeypatch.setattr(api, "get_key_state", lambda *args: state)
    settings = next(
        callback()
        for dependency, callback in app.dependency_overrides.items()
        if dependency.__name__ == "get_settings"
    )
    settings.replenishment_catalog_root = "."
    day = date(2022, 7, 8)
    calls = []

    def scoped(_repository, run_id, modes):
        calls.append((run_id, modes))
        return {
            "manifest": {
                "mode": "operational",
                "reporting_scope": "warehouse",
                "dataset_class": "fixture",
                "binding": {"warehouse_id": 1, "product_id": 2, "unit": "each"},
            },
            "calibration": {"eoq": {"quantity": 86}},
            "days": {
                ("xgboost", 7, "0.90", "proposed"): (
                    SimpleNamespace(day=day, warmup=False, reorder_point=2),
                )
            },
        }

    monkeypatch.setattr(api.ReplenishmentRepository, "scoped", scoped)
    base = f"{BASE}/replenishment-position?{KEY}"
    with TestClient(app) as client:
        assert client.get(f"{base}&run_id={requested}").status_code == 422
        assert client.get(f"{base}&view=demo&run_id=../test").status_code == 422
        result = client.get(f"{base}&view=demo&run_id={requested}&lead_time=7&reference_date={day}")
        assert result.status_code == 200
        assert result.json()["run_id"] == requested
        assert result.json()["rop"] == 2
        assert calls == [(requested, ("operational",))]
