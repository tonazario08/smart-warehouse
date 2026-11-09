from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, update
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth.security import create_access_token
from app.core.config import Settings
from app.db.base import Base
from app.db.session import get_session
from app.main import create_app
from app.models import Category, Product, Stock, User, UserRole, Warehouse
from tests.gis_helpers import GRAPH, MANIFEST, write_fixture

BASE = "/api/v1/gis"
NOW = datetime(2026, 11, 7, tzinfo=UTC)
DESTINATION = {"kind": "coordinate", "latitude": 0, "longitude": 0.002}
RUN_ID = "rrv1-" + "a" * 64


@contextmanager
def sqlite_api(settings) -> Iterator:
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            users = [
                User(email=f"gis-{role.value}@example.test", password_hash="fixture", role=role)
                for role in UserRole
            ]
            session.add_all(users)
            session.commit()
            headers = {
                user.role.value: {
                    "Authorization": f"Bearer {create_access_token(user.id, settings)}"
                }
                for user in users
            }
            app = create_app(settings)
            app.dependency_overrides[get_session] = lambda: session
            with TestClient(app) as client:
                yield client, headers, session
    finally:
        engine.dispose()


@pytest.fixture
def gis_client(unit_settings):
    with sqlite_api(unit_settings) as api:
        yield api


@pytest.mark.parametrize("method,path,body", [
    ("GET", "/status", None),
    ("POST", "/warehouse-options", {"product_id": 1, "quantity": 1, "destination": DESTINATION}),
    ("POST", "/route", {"kind": "transfer", "transfer_id": 1}),
    ("GET", "/heatmap?product_id=1&start_date=2026-11-01&end_date=2026-11-03", None),
    ("GET", f"/policy-context?run_id={RUN_ID}&product_id=1&warehouse_id=1", None),
])
def test_gis_rejects_missing_invalid_and_client_sessions_on_every_endpoint(
    gis_client, method, path, body
):
    client, headers, _ = gis_client
    kwargs = {} if body is None else {"json": body}
    for auth, expected in (
        ({}, 401), ({"Authorization": "Bearer bad"}, 401), (headers["client"], 403)
    ):
        response = client.request(method, BASE + path, headers=auth, **kwargs)
        assert response.status_code == expected
        assert "detail" in response.json()


def test_current_role_is_authoritative_and_core_health_survives_unconfigured_gis(gis_client):
    client, headers, session = gis_client
    for role in ("admin", "warehouse"):
        response = client.get(BASE + "/status", headers=headers[role])
        assert response.status_code == 200
        assert response.json() == {
            "state": "unconfigured",
            "snapshot": None,
            "stock_data_class": "operational",
            "stock_fixture_label": None,
        }
    session.execute(update(User).where(User.role == UserRole.ADMIN).values(role=UserRole.CLIENT))
    session.commit()
    assert client.get(BASE + "/status", headers=headers["admin"]).status_code == 403
    assert client.get("/api/v1/health").json() == {"status": "ok"}


def test_fixture_mode_is_rejected_outside_test_and_integration(unit_settings):
    with pytest.raises(ValidationError, match="GIS fixture"):
        Settings(
            **{
                **unit_settings.model_dump(),
                "app_env": "development",
                "database_url": "postgresql+psycopg://fixture@127.0.0.1/fixture",
                "gis_allow_fixture": True,
            },
            _env_file=None,
        )


def test_catalog_is_verified_once_and_cached_snapshot_age_is_rechecked(
    unit_settings, tmp_path, monkeypatch
):
    from app.gis import service

    snapshot_id, _ = write_fixture(tmp_path)
    settings = unit_settings.model_copy(update={
        "gis_catalog_root": tmp_path,
        "gis_snapshot_id": snapshot_id,
        "gis_allow_fixture": True,
    })
    current = NOW
    seen = 0
    real_verify = service.verify_snapshot

    def counted_verify(*args, **kwargs):
        nonlocal seen
        seen += 1
        return real_verify(*args, **kwargs)

    monkeypatch.setattr(service, "utc_now", lambda: current)
    monkeypatch.setattr(service, "verify_snapshot", counted_verify)
    with sqlite_api(settings) as (client, headers, _):
        for role in ("admin", "warehouse"):
            body = client.get(BASE + "/status", headers=headers[role]).json()
            assert body["state"] == "available"
            assert body["snapshot"]["snapshot_id"] == snapshot_id
            assert body["snapshot"]["dataset_class"] == "synthetic_fixture"
            assert body["stock_fixture_label"] == "Kho và tồn kiểm thử"
        current += timedelta(days=31)
        assert client.get(BASE + "/status", headers=headers["warehouse"]).json()["state"] == "stale"
    assert seen == 1


@pytest.mark.parametrize("mode", ["fixture_disabled", "tampered", "missing"])
def test_bad_catalog_is_sanitized_and_does_not_affect_core_apis(
    unit_settings, tmp_path, mode, monkeypatch
):
    from app.gis import service

    monkeypatch.setattr(service, "utc_now", lambda: NOW)
    snapshot_id, folder = write_fixture(tmp_path)
    if mode == "tampered":
        (folder / "graph.json").write_bytes(b"private-path-is-never-returned")
    if mode == "missing":
        (folder / "graph.json").unlink()
    settings = unit_settings.model_copy(update={
        "gis_catalog_root": tmp_path,
        "gis_snapshot_id": snapshot_id,
        "gis_allow_fixture": mode != "fixture_disabled",
    })
    with sqlite_api(settings) as (client, headers, _):
        response = client.get(BASE + "/status", headers=headers["warehouse"])
        assert response.status_code == 200
        assert response.json()["state"] == "invalid"
        assert response.json()["snapshot"] is None
        assert str(tmp_path) not in response.text
        assert client.get("/api/v1/health").status_code == 200


@pytest.mark.parametrize("path,body", [
    ("/warehouse-options", {"product_id": "1", "quantity": 1, "destination": DESTINATION}),
    ("/warehouse-options", {"product_id": 1, "quantity": True, "destination": DESTINATION}),
    ("/warehouse-options", {"product_id": 1, "quantity": 2147483648, "destination": DESTINATION}),
    ("/warehouse-options", {"product_id": 1, "quantity": 1, "destination": {
        **DESTINATION, "latitude": 91,
    }}),
    ("/route", {"kind": "transfer", "transfer_id": 1, "warehouse_id": 1}),
    ("/route", {"kind": "warehouse_to_target", "warehouse_id": 1, "destination": {
        "kind": "warehouse", "warehouse_id": False,
    }}),
])
def test_request_body_is_strict_and_discriminated(gis_client, path, body):
    client, headers, _ = gis_client
    response = client.post(BASE + path, headers=headers["admin"], json=body)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "REQUEST_VALIDATION_ERROR"


@pytest.mark.parametrize("query", [
    "product_id=1.0&start_date=2026-11-01&end_date=2026-11-02",
    "product_id=1&start_date=1793491200&end_date=2026-11-02",
    "product_id=1&start_date=2026-11-01&end_date=2026-11-01",
    "product_id=1&start_date=2026-11-01&end_date=2027-02-01",
    "product_id=1&start_date=2026-11-01&end_date=2026-11-02&extra=1",
    "product_id=1&product_id=2&start_date=2026-11-01&end_date=2026-11-02",
])
def test_heatmap_rejects_malformed_or_ambiguous_queries(gis_client, query):
    client, headers, _ = gis_client
    assert client.get(BASE + "/heatmap?" + query, headers=headers["admin"]).status_code == 422


def seed_options(session, *, quantity=5):
    product = Product(sku="GIS-1", name="GIS 1", category=Category(name="GIS"), unit="unit")
    warehouses = [
        Warehouse(
            code=f"GIS-{i}", name=f"GIS Warehouse {i}", address="Fixture",
            latitude=0, longitude=longitude,
        )
        for i, longitude in [(1, 0), (2, 0.001)]
    ]
    session.add_all([product, *warehouses])
    session.flush()
    session.add_all(
        Stock(product_id=product.id, warehouse_id=warehouse.id, quantity=quantity)
        for warehouse in warehouses
    )
    session.commit()
    return product.id, [warehouse.id for warehouse in warehouses]


def test_unconfigured_route_options_use_explicit_geographic_fallback(gis_client):
    client, headers, session = gis_client
    product_id, warehouses = seed_options(session)
    result = client.post(BASE + "/warehouse-options", headers=headers["admin"], json={
        "product_id": product_id, "quantity": 5, "destination": DESTINATION,
    })
    assert result.status_code == 200
    body = result.json()
    assert body["ranking_state"] == "unavailable"
    assert body["ranked"] == []
    assert [row["warehouse"]["warehouse_id"] for row in body["geographic_only"]] == warehouses[::-1]
    assert {row["reason"] for row in body["geographic_only"]} == {"snapshot_unconfigured"}


def test_shared_budget_discards_an_earlier_successful_rank(unit_settings, tmp_path, monkeypatch):
    from app.gis import service
    from app.gis.routing import SearchBudget

    snapshot_id, _ = write_fixture(tmp_path, graph={**GRAPH, "restrictions": []}, changes={
        "stats": {**MANIFEST["stats"], "restrictions": 0},
    })
    monkeypatch.setattr(service, "utc_now", lambda: NOW)
    monkeypatch.setattr(service, "SearchBudget", lambda: SearchBudget(3))
    settings = unit_settings.model_copy(update={
        "gis_catalog_root": tmp_path, "gis_snapshot_id": snapshot_id, "gis_allow_fixture": True,
    })
    with sqlite_api(settings) as (client, headers, session):
        product_id, warehouses = seed_options(session)
        response = client.post(BASE + "/warehouse-options", headers=headers["admin"], json={
            "product_id": product_id, "quantity": 5, "destination": DESTINATION,
        })
    assert response.status_code == 200
    body = response.json()
    assert body["ranking_state"] == "budget_exceeded"
    assert body["ranked"] == []
    assert {row["reason"] for row in body["geographic_only"]} == {"budget_exceeded"}
    assert {row["warehouse"]["warehouse_id"] for row in body["geographic_only"]} == set(warehouses)


def test_warehouse_limit_rejects_the_query_without_truncating(gis_client):
    client, headers, session = gis_client
    product_id, _ = seed_options(session)
    session.add_all(
        Warehouse(code=f"EXTRA-{i}", name=f"Extra warehouse {i}", address="Fixture")
        for i in range(99)
    )
    session.commit()
    response = client.post(BASE + "/warehouse-options", headers=headers["admin"], json={
        "product_id": product_id, "quantity": 5, "destination": DESTINATION,
    })
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "GIS_WAREHOUSE_LIMIT"


def test_policy_context_uses_verified_operational_binding_and_current_unit(unit_settings, tmp_path):
    from app.replenishment.artifacts import publish_catalog, publish_run
    from app.replenishment.calibration import calibrate
    from app.replenishment.inputs import load_inputs
    from app.replenishment.simulation import simulate
    from tests.replenishment_helpers import operational_context

    bundle, forecast, auth, config = operational_context(tmp_path)
    inputs = load_inputs(forecast, bundle, config, auth)
    published = publish_run(
        inputs,
        config,
        simulate(inputs, calibrate(inputs, config), config),
        auth,
        tmp_path / "runs",
    )
    catalog = tmp_path / "replenishment"
    publish_catalog(published.path, auth, catalog)
    settings = unit_settings.model_copy(update={
        "gis_allow_fixture": True,
        "replenishment_catalog_root": catalog,
        "replenishment_allow_fixture": True,
    })
    with sqlite_api(settings) as (client, headers, session):
        product_id, warehouses = seed_options(session)
        base = BASE + "/policy-context"
        params = {
            "run_id": published.run_id,
            "product_id": product_id,
            "warehouse_id": warehouses[1],
        }

        matching = client.get(base, headers=headers["warehouse"], params=params)
        assert matching.status_code == 200
        result = matching.json()
        assert result["state"] == "applicable"
        assert result["run"]["run_id"] == published.run_id
        assert result["run"]["href"] == f"/replenishment/runs/{published.run_id}"
        for change in ({"warehouse_id": warehouses[0]}, {"product_id": product_id + 1},
                       {"run_id": RUN_ID}):
            response = client.get(base, headers=headers["admin"], params={**params, **change})
            assert response.json() == {"state": "not_applicable", "run": None}
        session.execute(update(Product).where(Product.id == product_id).values(unit="changed"))
        session.commit()
        assert client.get(base, headers=headers["admin"], params=params).json() == {
            "state": "not_applicable", "run": None,
        }



def test_verified_public_road_metadata_is_distinct_from_fixture_stock(
    unit_settings, tmp_path, monkeypatch
):
    from app.gis import service
    from app.gis.schemas import Node, edge_weight

    monkeypatch.setattr(service, "utc_now", lambda: NOW)
    # Synthetic bytes exercise the public metadata contract only.
    a = Node(1, 106.65, 10.75)
    b = Node(2, 106.66, 10.75)
    source = "https://download.geofabrik.de/asia/vietnam-261105.osm.pbf"
    snapshot_id, _ = write_fixture(
        tmp_path,
        graph={"nodes": [a, b], "edges": [[1, 10, 1, 2, edge_weight(a, b)]], "restrictions": []},
        changes={
            "dataset_class": "public_osm",
            "source_url": source,
            "source_sha256": "1" * 64,
            "bounds": [106.64, 10.72, 106.76, 10.82],
            "license": "ODbL 1.0",
            "attribution": "© OpenStreetMap contributors",
            "stats": {**MANIFEST["stats"], "nodes": 2, "edges": 1, "restrictions": 0},
        },
    )
    settings = unit_settings.model_copy(update={
        "gis_catalog_root": tmp_path, "gis_snapshot_id": snapshot_id, "gis_allow_fixture": True,
    })
    with sqlite_api(settings) as (client, headers, _):
        result = client.get(BASE + "/status", headers=headers["warehouse"]).json()
    assert result["state"] == "available"
    assert result["snapshot"]["dataset_class"] == "public_osm"
    assert result["snapshot"]["source_url"] == source
    assert result["snapshot"]["attribution"] == "© OpenStreetMap contributors"
    assert result["snapshot"]["license_url"] == "https://www.openstreetmap.org/copyright"
    assert result["stock_data_class"] == "synthetic_fixture"
    assert result["stock_fixture_label"] == "Kho và tồn kiểm thử"


def test_cached_future_preparation_time_is_invalid_after_clock_regresses(
    unit_settings, tmp_path, monkeypatch
):
    from app.gis import service

    snapshot_id, _ = write_fixture(tmp_path)
    settings = unit_settings.model_copy(update={
        "gis_catalog_root": tmp_path, "gis_snapshot_id": snapshot_id, "gis_allow_fixture": True,
    })
    current = NOW
    monkeypatch.setattr(service, "utc_now", lambda: current)
    with sqlite_api(settings) as (client, headers, _):
        assert client.get(BASE + "/status", headers=headers["admin"]).json()["state"] == "available"
        current = datetime(2026, 11, 5, 22, tzinfo=UTC)  # After source, before preparation.
        result = client.get(BASE + "/status", headers=headers["admin"]).json()
        assert result["state"] == "invalid"
        assert result["snapshot"] is None
