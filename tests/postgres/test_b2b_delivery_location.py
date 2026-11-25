from uuid import uuid4

import pytest

from tests.postgres.test_purchase_request_migration import purchase_migration_target  # noqa: F401
from tests.postgres.test_purchase_requests_api import api_data as _api_data
from tests.postgres.test_purchase_requests_api import body_for

api_data = _api_data
pytestmark = pytest.mark.postgres
BASE = "/api/v1/purchase-requests"
DELIVERY = {"address": "  Điểm thử công cộng  ", "latitude": 10.7770348, "longitude": 106.695488}


def test_delivery_create_replay_and_private_projection(postgres_client, api_data):
    ids, auth = api_data
    headers = auth["client"] | {"Idempotency-Key": str(uuid4())}
    body = body_for(ids) | {"delivery_location": DELIVERY}
    first = postgres_client.post(BASE, headers=headers, json=body)
    assert first.status_code == 201, first.json()
    assert "delivery_location" not in first.json()
    oid = first.json()["id"]
    uri = f"{BASE}/{oid}/delivery-location"
    assert postgres_client.get(uri, headers=auth["other"]).status_code == 404
    for role in ("client", "admin", "warehouse"):
        reply = postgres_client.get(uri, headers=auth[role])
        assert reply.status_code == 200
        assert reply.headers["cache-control"] == "no-store"
        assert reply.json() == {"delivery_location": DELIVERY | {"address": "Điểm thử công cộng"}}
    replay = body | {"delivery_location": DELIVERY | {"address": "Điểm thử công cộng"}}
    assert postgres_client.post(BASE, headers=headers, json=replay).status_code == 200
    for change in ({"address": "Địa chỉ khác"}, {"latitude": 10.77}):
        changed = body | {"delivery_location": DELIVERY | change}
        assert postgres_client.post(BASE, headers=headers, json=changed).status_code == 409
    listing = postgres_client.get(BASE, headers=auth["client"])
    assert "delivery_location" not in listing.json()["items"][0]


def test_delivery_route_distinct_from_legacy_and_post_lookup(
    postgres_client, postgres_session, api_data
):
    from app.models import Warehouse

    ids, auth = api_data
    source = postgres_session.get(Warehouse, ids["source"])
    source.latitude, source.longitude = 10.7767, 106.6921
    postgres_session.commit()
    body = body_for(ids) | {"delivery_location": DELIVERY}
    before = {"product_id": ids["product"], "quantity": 3, "latitude": 10.777, "longitude": 106.695}
    post = postgres_client.post(f"{BASE}/nearest-warehouses", headers=auth["client"], json=before)
    assert post.status_code == 200
    assert post.headers["cache-control"] == "no-store"
    old = postgres_client.get(f"{BASE}/nearest-warehouses", headers=auth["client"], params=before)
    assert post.json() == old.json()
    assert (
        postgres_client.post(
            f"{BASE}/nearest-warehouses",
            headers=auth["client"],
            json=before,
            params={"latitude": 9},
        ).status_code
        == 422
    )
    assert (
        postgres_client.post(
            f"{BASE}/nearest-warehouses", headers=auth["client"], json=before | {"latitude": True}
        ).status_code
        == 422
    )
    invalid = body | {"delivery_location": DELIVERY | {"latitude": 91}}
    reply = postgres_client.post(
        BASE, headers=auth["client"] | {"Idempotency-Key": str(uuid4())}, json=invalid
    )
    assert reply.status_code == 422 and DELIVERY["address"].strip() not in reply.text

    def new(payload):
        result = postgres_client.post(
            BASE, headers=auth["client"] | {"Idempotency-Key": str(uuid4())}, json=payload
        )
        assert result.status_code == 201
        return result.json()["id"]

    oid = new(body)
    legacy_id = new(body_for(ids))
    route = "/api/v1/gis/route"
    dest = {"kind": "purchase_request_delivery", "request_id": oid}
    delivery = postgres_client.post(route, headers=auth["warehouse"], json=dest)
    assert delivery.status_code == 200 and delivery.headers["cache-control"] == "no-store"
    value = delivery.json()
    assert value["origin"]["warehouse"]["warehouse_id"] == ids["source"]
    assert value["destination"] == {
        "kind": "purchase_request_delivery",
        "coordinate": {k: DELIVERY[k] for k in ("latitude", "longitude")},
        "warehouse": None,
        "request_id": oid,
    }
    assert value["geometry"] is None and value["reason"] == "snapshot_unconfigured"
    assert DELIVERY["address"].strip() not in delivery.text
    assert postgres_client.post(route, headers=auth["client"], json=dest).status_code == 403
    assert (
        postgres_client.post(
            route, headers=auth["warehouse"], json=dest | {"warehouse_id": ids["destination"]}
        ).status_code
        == 422
    )
    missing = postgres_client.post(
        route, headers=auth["warehouse"], json=dest | {"request_id": legacy_id}
    )
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "GIS_DELIVERY_LOCATION_NOT_FOUND"
    legacy_route = postgres_client.post(
        route,
        headers=auth["warehouse"],
        json={
            "kind": "warehouse_to_target",
            "warehouse_id": ids["source"],
            "destination": {"kind": "purchase_request", "request_id": oid},
        },
    ).json()
    assert legacy_route["destination"]["kind"] == "purchase_request"
    assert legacy_route["destination"]["coordinate"] == {"latitude": 10.7767, "longitude": 106.6921}


def test_fulfillment_snapshot_rolls_back_on_failed_create(
    postgres_client, postgres_session, api_data, monkeypatch
):
    from sqlalchemy import func, select

    from app.models import PurchaseRequestWorkflow
    from app.purchase_requests.repository import PurchaseRequestRepository

    ids, auth = api_data
    flush = PurchaseRequestRepository.flush

    def reject(repo):
        flush(repo)
        if repo.session.scalar(select(func.count()).select_from(PurchaseRequestWorkflow)):
            raise RuntimeError("Injected post-snapshot failure")

    monkeypatch.setattr(PurchaseRequestRepository, "flush", reject)
    with pytest.raises(RuntimeError, match="Injected post-snapshot failure"):
        postgres_client.post(
            BASE,
            headers=auth["client"] | {"Idempotency-Key": str(uuid4())},
            json=body_for(ids) | {"delivery_location": DELIVERY},
        )
    assert postgres_session.scalar(select(func.count()).select_from(PurchaseRequestWorkflow)) == 0


def test_pre_migration_managed_request_keeps_original_identity(purchase_migration_target):  # noqa: F811
    import hashlib
    import json

    from fastapi.testclient import TestClient
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    from alembic import command
    from app.core.config import Settings
    from app.db.session import get_session
    from app.main import create_app
    from tests.postgres.test_purchase_requests_api import headers_for, seed_purchase

    config, engine = purchase_migration_target
    command.upgrade(config, "20261122_0011")
    with Session(engine) as session:
        ids = seed_purchase(session)
        old_body = body_for(ids)
        old_digest = hashlib.sha256(
            json.dumps(
                old_body | {"note": old_body["note"].strip()},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        key = uuid4()
        params = {
            "n": "PR-" + uuid4().hex,
            "w": ids["source"],
            "p": ids["product"],
            "actor": ids["client"],
            "digest": old_digest,
            "key": key,
        }
        oid = session.scalar(
            text(
                "INSERT INTO purchase_requests(request_number,warehouse_id,product_id,quantity,"
                "status,requested_by_id) VALUES (:n,:w,:p,3,'pending',:actor) RETURNING id"
            ),
            params,
        )
        session.execute(
            text(
                "INSERT INTO purchase_request_workflows(purchase_request_id,created_by_id,"
                "idempotency_key,request_fingerprint,note) VALUES "
                "(:id,:actor,:key,:digest,'yêu cầu')"
            ),
            params | {"id": oid},
        )
        session.commit()
    # Upgrade past the delivery-location migration (20261122_0012). The app
    # also needs the 20261125_0013 idempotency columns on inbounds/outbounds
    # before it can fulfil: the request itself still predates 0012.
    command.upgrade(config, "20261125_0013")
    settings = Settings(
        app_env="test",
        database_url=engine.url.render_as_string(hide_password=False),
        jwt_secret_key="b2b-delivery-guarded-migration-test-secret",
        _env_file=None,
    )
    app = create_app(settings)
    with Session(engine) as session, TestClient(app) as client:
        app.dependency_overrides[get_session] = lambda: session
        customer = headers_for(ids, "client", settings, key)
        admin = headers_for(ids, "admin", settings)
        warehouse = headers_for(ids, "warehouse", settings)
        uri = f"{BASE}/{oid}"
        response = client.get(uri, headers=customer)
        assert response.status_code == 200 and response.json()["status"] == "pending"
        assert client.get(uri + "/delivery-location", headers=customer).json() == {
            "delivery_location": None
        }
        assert client.post(uri + "/approve", headers=admin, json={}).status_code == 200
        assert client.post(uri + "/fulfill", headers=warehouse, json={}).status_code == 200
        replay = client.post(BASE, headers=customer, json=old_body)
        assert replay.status_code == 200 and replay.json()["status"] == "fulfilled"
        assert replay.json()["id"] == oid
        assert (
            session.scalar(
                text(
                    "SELECT request_fingerprint FROM purchase_request_workflows "
                "WHERE purchase_request_id=:id"
                ),
                {"id": oid},
            )
            == old_digest
        )
        session.rollback()
        fresh = client.post(
            BASE,
            headers=headers_for(ids, "client", settings, uuid4()),
            json=old_body | {"delivery_location": DELIVERY},
        )
        assert fresh.status_code == 201
    with pytest.raises(RuntimeError, match="persisted B2B delivery snapshots"):
        command.downgrade(config, "20261122_0011")
    with engine.begin() as conn:
        # Only remove the test-created order and its job in the disposable fixture.
        new_id = fresh.json()["id"]
        conn.execute(
            text("DELETE FROM order_analytics_jobs WHERE purchase_request_id=:id"), {"id": new_id}
        )
        conn.execute(
            text("DELETE FROM purchase_request_workflows WHERE purchase_request_id=:id"),
            {"id": new_id},
        )
        conn.execute(text("DELETE FROM purchase_requests WHERE id=:id"), {"id": new_id})
    command.downgrade(config, "20261122_0011")
