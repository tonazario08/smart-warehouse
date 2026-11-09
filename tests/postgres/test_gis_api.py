from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import get_session
from app.inventory.repository import InventoryRepository
from app.inventory.schemas import InventoryMovementCreate
from app.inventory.service import InventoryService
from app.main import create_app
from app.models import (
    MovementProvenance,
    Product,
    PurchaseRequest,
    PurchaseRequestWorkflow,
    Stock,
    StockTransaction,
    StockTransfer,
    Warehouse,
)
from tests.gis_helpers import GRAPH, MANIFEST, write_fixture
from tests.postgres.test_purchase_requests_api import (
    BASE as PURCHASE_BASE,
)
from tests.postgres.test_purchase_requests_api import (
    create,
    headers_for,
    seed_purchase,
)

pytestmark = pytest.mark.postgres
GIS = "/api/v1/gis"
NOW = datetime(2026, 11, 7, tzinfo=UTC)


@pytest.fixture
def live_gis(postgres_url, postgres_session, unit_settings, tmp_path, monkeypatch):
    from app.gis import service

    ids = seed_purchase(postgres_session)
    auth = {
        role: headers_for(ids, role, unit_settings)
        for role in ("admin", "warehouse", "client", "other")
    }
    snapshot_id, _ = write_fixture(tmp_path, graph={**GRAPH, "restrictions": []}, changes={
        "stats": {**MANIFEST["stats"], "restrictions": 0},
    })
    settings = unit_settings.model_copy(update={
        "database_url": postgres_url,
        "gis_catalog_root": tmp_path,
        "gis_snapshot_id": snapshot_id,
        "gis_allow_fixture": True,
    })
    monkeypatch.setattr(service, "utc_now", lambda: NOW)
    app = create_app(settings)
    app.dependency_overrides[get_session] = lambda: postgres_session
    with TestClient(app) as client:
        yield client, ids, auth, postgres_session, snapshot_id


def set_point(session, warehouse_id, longitude):
    warehouse = session.get(Warehouse, warehouse_id)
    warehouse.latitude = 0
    warehouse.longitude = longitude


def add_warehouse(session, name, longitude=None, *, product_id=None, quantity=None):
    warehouse = Warehouse(
        code=name, name=name, address="Fixture",
        longitude=longitude, latitude=None if longitude is None else 0,
    )
    session.add(warehouse)
    session.flush()
    if quantity is not None:
        session.add(Stock(
            warehouse_id=warehouse.id, product_id=product_id, quantity=quantity,
        ))
    return warehouse.id


def read_digest(session):
    return {
        table.__tablename__: tuple(session.execute(
            select(table.__table__).order_by(*table.__table__.primary_key.columns)
        ))
        for table in (
            Stock, StockTransaction, MovementProvenance, StockTransfer,
            PurchaseRequest, PurchaseRequestWorkflow,
        )
    }


def test_stock_feasibility_ties_context_and_read_only_on_postgresql(live_gis):
    client, ids, auth, session, snapshot_id = live_gis
    set_point(session, ids["source"], 0)
    set_point(session, ids["destination"], 0.002)
    session.add(Stock(warehouse_id=ids["destination"], product_id=ids["product"], quantity=4))
    tied = add_warehouse(session, "GIS-TIED", 0, product_id=ids["product"], quantity=5)
    missing_stock = add_warehouse(session, "GIS-NO-STOCK", 0.001)
    missing_point = add_warehouse(session, "GIS-NO-POINT", product_id=ids["product"], quantity=5)
    outside = add_warehouse(session, "GIS-OUTSIDE", 2, product_id=ids["product"], quantity=5)
    session.commit()
    request = create(
        client, ids, auth["client"], warehouse_id=ids["destination"], quantity=5,
    )
    assert request.status_code == 201
    request_id = request.json()["id"]
    before = read_digest(session)
    options = {
        "product_id": ids["product"], "quantity": 5,
        "destination": {"kind": "purchase_request", "request_id": request_id},
    }
    response = client.post(GIS + "/warehouse-options", headers=auth["warehouse"], json=options)
    assert response.status_code == 200
    data = response.json()
    assert data["product"]["unit"] == "each"
    assert data["stock_as_of"].endswith("Z")
    assert data["destination"]["warehouse"]["warehouse_id"] == ids["destination"]
    assert data["destination"]["request_id"] == request_id
    assert data["ranking_state"] == "available"
    assert data["snapshot"]["snapshot_id"] == snapshot_id
    assert data["stock_fixture_label"] == "Kho và tồn kiểm thử"
    assert [row["warehouse"]["warehouse_id"] for row in data["ranked"]] == [ids["source"], tied]
    assert [row["available_quantity"] for row in data["ranked"]] == [10, 5]
    assert {row["distance_mm"] for row in data["ranked"]} == {222392}
    assert {row["warehouse"]["warehouse_id"]: row["reason"] for row in data["excluded"]} == {
        ids["destination"]: "insufficient_stock",
        missing_stock: "missing_stock",
        missing_point: "missing_coordinates",
    }
    assert data["geographic_only"][0]["warehouse"]["warehouse_id"] == outside
    assert data["geographic_only"][0]["reason"] == "outside_coverage"

    path = GIS + "/route"
    body = {
        "kind": "warehouse_to_target", "warehouse_id": ids["source"],
        "destination": options["destination"],
    }
    route = client.post(path, headers=auth["admin"], json=body)
    assert route.status_code == 200
    assert route.json()["geometry"] == {
        "type": "LineString", "coordinates": [[0, 0], [0.001, 0], [0.002, 0]],
    }
    assert route.json()["distance_mm"] == 222392
    assert client.post(path, headers=auth["other"], json=body).status_code == 403
    mismatch = client.post(
        GIS + "/warehouse-options", headers=auth["admin"], json={**options, "quantity": 6}
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["detail"]["code"] == "GIS_PURCHASE_REQUEST_MISMATCH"
    assert client.post(
        path, headers=auth["warehouse"], json={**body, "destination": {
            "kind": "purchase_request", "request_id": request_id + 100,
        }},
    ).status_code == 404
    assert read_digest(session) == before

    product = session.get(Product, ids["product"])
    product.is_active = False
    session.commit()
    inactive = client.post(GIS + "/warehouse-options", headers=auth["admin"], json=options)
    assert inactive.status_code == 404
    assert inactive.json()["detail"]["code"] == "GIS_PRODUCT_NOT_FOUND"


def fulfillment(client, ids, auth, quantity):
    request = create(client, ids, auth["client"], quantity=quantity)
    assert request.status_code == 201
    path = f"{PURCHASE_BASE}/{request.json()['id']}"
    assert client.post(path + "/approve", headers=auth["admin"], json={}).status_code == 200
    result = client.post(path + "/fulfill", headers=auth["warehouse"], json={})
    assert result.status_code == 200
    return result.json()["fulfillment"]["transaction_id"]


def test_heatmap_utc_boundaries_transfer_exclusions_and_real_no_write_flow(live_gis):
    client, ids, auth, session, _ = live_gis
    set_point(session, ids["source"], 0)
    set_point(session, ids["destination"], 0.001)
    unlocated = add_warehouse(session, "GIS-UNLOCATED")
    outside = add_warehouse(session, "GIS-OUTSIDE", 2)
    session.commit()

    included = fulfillment(client, ids, auth, 3)
    excluded = fulfillment(client, ids, auth, 1)
    lower = datetime(2026, 11, 1, 17, tzinfo=UTC)
    upper = datetime(2026, 11, 2, 17, tzinfo=UTC)
    session.get(StockTransaction, included).created_at = lower
    session.get(StockTransaction, excluded).created_at = upper
    session.commit()

    transfer = client.post("/api/v1/transfers", headers={
        **auth["warehouse"], "Idempotency-Key": str(uuid4()),
    }, json={
        "source_warehouse_id": ids["source"], "destination_warehouse_id": ids["destination"],
        "product_id": ids["product"], "quantity": 1,
    })
    assert transfer.status_code == 201
    movement = InventoryService(InventoryRepository(session))
    for _ in range(2):
        movement.create_outbound(ids["warehouse"], InventoryMovementCreate(
            product_id=ids["product"], warehouse_id=ids["source"], quantity=1,
        ))
    standard = list(session.scalars(
        select(MovementProvenance).where(MovementProvenance.purpose == "standard_outbound")
        .order_by(MovementProvenance.transaction_id)
    ))
    assert len(standard) == 2
    for row in standard:
        row.transaction.created_at = lower
    session.delete(standard[-1])  # Explicit fixture for historical outbound without provenance.
    for key in ("inbound_transaction_id", "outbound_transaction_id"):
        session.get(StockTransaction, transfer.json()[key]).created_at = lower
    session.commit()

    before = read_digest(session)
    params = {"product_id": ids["product"], "start_date": "2026-11-02", "end_date": "2026-11-03"}
    response = client.get(GIS + "/heatmap", params=params, headers=auth["warehouse"])
    assert response.status_code == 200
    data = response.json()
    assert (data["timezone"], data["start_utc"], data["end_utc"]) == (
        "Asia/Ho_Chi_Minh", "2026-11-01T17:00:00Z", "2026-11-02T17:00:00Z",
    )
    assert {p["warehouse"]["warehouse_id"]: p["fulfilled_quantity"] for p in data["points"]} == {
        ids["source"]: 3, ids["destination"]: 0, outside: 0,
    }
    assert data["points"][0]["transaction_count"] == 1
    assert [p["warehouse"]["warehouse_id"] for p in data["unlocated"]] == [unlocated]
    assert data["unlocated"][0]["fulfilled_quantity"] == 0
    assert data["excluded"] == {
        purpose: {"quantity": 1, "transaction_count": 1}
        for purpose in ("transfer_in", "transfer_out", "standard_outbound", "unclassified_outbound")
    }

    empty = client.get(GIS + "/heatmap", params={
        **params, "start_date": "2026-11-04", "end_date": "2026-11-05",
    }, headers=auth["admin"]).json()
    assert all(row["fulfilled_quantity"] == 0 for row in empty["points"] + empty["unlocated"])
    assert empty["unlocated"][0]["warehouse"]["warehouse_id"] == unlocated

    body = {"kind": "transfer", "transfer_id": transfer.json()["id"]}
    route = client.post(GIS + "/route", json=body, headers=auth["admin"])
    assert route.status_code == 200
    assert route.json()["transfer"] == {"transfer_id": transfer.json()["id"], "mode": "immediate"}
    assert route.json()["distance_mm"] == 111196
    for unknown in (body, {**body, "transfer_id": body["transfer_id"] + 100}):
        assert client.post(GIS + "/route", json=unknown, headers=auth["client"]).status_code == 403
    assert read_digest(session) == before


def test_active_sku_is_returned_even_when_no_warehouses_exist(live_gis, postgres_session):
    from sqlalchemy import delete

    client, ids, auth, session, _ = live_gis
    assert session is postgres_session
    session.execute(delete(Stock))
    session.execute(delete(Warehouse))
    session.commit()
    response = client.post(GIS + "/warehouse-options", headers=auth["admin"], json={
        "product_id": ids["product"], "quantity": 1,
        "destination": {"kind": "coordinate", "latitude": 0, "longitude": 0},
    })
    assert response.status_code == 200
    assert response.json()["product"]["product_id"] == ids["product"]
    assert response.json()["ranked"] == response.json()["excluded"] == []
