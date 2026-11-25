"""Idempotency for POST /inbounds and /outbounds, mirroring transfers.

Covers the Task 1 acceptance criteria end to end: exact sequential replay,
concurrent retries with one new key, same-key conflicts, actor scoping,
different-key duplicates, missing/invalid keys, rollback, and the 503
retry envelope.
"""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import psycopg
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.auth.security import create_access_token
from app.core.errors import DomainError
from app.inventory.repository import InventoryRepository
from app.inventory.schemas import InventoryMovementCreate
from app.inventory.service import InventoryService
from app.models import Inbound, Outbound, Stock, User, UserRole

from .test_inventory_concurrency import counts, seed_inventory

pytestmark = pytest.mark.postgres

EXPECTED = {"id", "warehouse_id", "product_id", "quantity", "reference", "note"}
DIRECTIONS = ["inbound", "outbound"]


@pytest.fixture
def movement_api(postgres_session, postgres_client, unit_settings):
    operator_id, warehouse_id, product_id = seed_inventory(postgres_session)
    admin = User(
        email="movement-admin@example.com", password_hash="test", role=UserRole.ADMIN
    )
    client_user = User(
        email="movement-client@example.com", password_hash="test", role=UserRole.CLIENT
    )
    postgres_session.add_all([admin, client_user])
    postgres_session.add(Stock(warehouse_id=warehouse_id, product_id=product_id, quantity=10))
    postgres_session.commit()
    return {
        "client": postgres_client,
        "session": postgres_session,
        "operator_id": operator_id,
        "admin_id": admin.id,
        "client_id": client_user.id,
        "warehouse_id": warehouse_id,
        "product_id": product_id,
        "settings": unit_settings,
    }


def auth_headers(api, user_id, key=None):
    headers = {
        "Authorization": "Bearer " + create_access_token(user_id, api["settings"])
    }
    if key is not None:
        headers["Idempotency-Key"] = str(key)
    return headers


def body_for(api, quantity=3, reference="CK-01"):
    return {
        "warehouse_id": api["warehouse_id"],
        "product_id": api["product_id"],
        "quantity": quantity,
        "reference": reference,
        "note": None,
    }


def stock_quantity(session, api):
    return session.scalar(
        select(Stock.quantity).where(
            Stock.warehouse_id == api["warehouse_id"],
            Stock.product_id == api["product_id"],
        )
    )


def service_for(session):
    return InventoryService(InventoryRepository(session))


@pytest.mark.parametrize("direction", DIRECTIONS)
def test_exact_post_replay_and_lost_response_recovery(movement_api, direction):
    api = movement_api
    client, session = api["client"], api["session"]
    key = uuid4()
    headers = auth_headers(api, api["operator_id"], key)
    body = body_for(api, reference="  CK-01  ")

    response = client.post(f"/api/v1/{direction}s", json=body, headers=headers)
    assert response.status_code == 201, response.text
    assert set(response.json()) == EXPECTED
    assert response.json()["reference"] == "CK-01"
    stock_after_first = stock_quantity(session, api)

    replay = client.post(f"/api/v1/{direction}s", json=body, headers=headers)
    assert replay.status_code == 200 and replay.json() == response.json()
    assert stock_quantity(session, api) == stock_after_first

    lookup = client.get(
        f"/api/v1/{direction}s/by-key/{key}",
        headers=auth_headers(api, api["operator_id"]),
    )
    # The read model adds created_by_id/created_at; the shared fields must match.
    assert lookup.status_code == 200
    assert {name: lookup.json()[name] for name in EXPECTED} == response.json()
    detail = client.get(
        f"/api/v1/{direction}s/{response.json()['id']}",
        headers=auth_headers(api, api["operator_id"]),
    )
    assert detail.status_code == 200
    assert {name: detail.json()[name] for name in EXPECTED} == response.json()

    conflict = client.post(
        f"/api/v1/{direction}s", json=body_for(api, quantity=1), headers=headers
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"
    assert stock_quantity(session, api) == stock_after_first
    assert counts(session)["inbounds" if direction == "inbound" else "outbounds"] == 1


@pytest.mark.parametrize("direction", DIRECTIONS)
@pytest.mark.parametrize("key", [None, "", "bad-key", "3,4"])
def test_uuid_header_validation_is_safe_and_located(movement_api, direction, key):
    api = movement_api
    client, session = api["client"], api["session"]
    headers = auth_headers(api, api["operator_id"], key)
    if key is None:
        headers.pop("Idempotency-Key", None)
    response = client.post(f"/api/v1/{direction}s", json=body_for(api), headers=headers)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "REQUEST_VALIDATION_ERROR"
    assert any(
        "header" in name.lower() and "idempotency" in name.lower()
        for name in response.json()["detail"]["fields"]
    )
    assert counts(session)["inbounds" if direction == "inbound" else "outbounds"] == 0


@pytest.mark.parametrize("direction", DIRECTIONS)
@pytest.mark.parametrize(
    "role,active,expected",
    [
        (None, True, 401),
        ("client", True, 403),
        ("warehouse", False, 401),
        ("admin", True, 201),
        ("warehouse", True, 201),
    ],
)
def test_post_authorization_precedes_key_resolution(
    movement_api, direction, role, active, expected
):
    api = movement_api
    client, session = api["client"], api["session"]
    actor = session.get(User, api["operator_id"])
    actor.role = role or "warehouse"
    actor.is_active = active
    session.commit()
    headers = auth_headers(api, api["operator_id"], uuid4())
    if role is None:
        headers.pop("Authorization")
    if expected != 201:
        headers["Idempotency-Key"] = "bad-key"
    response = client.post(f"/api/v1/{direction}s", json=body_for(api), headers=headers)
    assert response.status_code == expected
    assert counts(session)["inbounds" if direction == "inbound" else "outbounds"] == (
        1 if expected == 201 else 0
    )


@pytest.mark.parametrize("direction", DIRECTIONS)
def test_same_key_different_actor_creates_distinct_record(movement_api, direction):
    api = movement_api
    client, session = api["client"], api["session"]
    key = uuid4()
    body = body_for(api)
    first = client.post(
        f"/api/v1/{direction}s",
        json=body,
        headers=auth_headers(api, api["operator_id"], key),
    )
    assert first.status_code == 201
    other = User(
        email="other-movement@example.com", password_hash="test", role=UserRole.WAREHOUSE
    )
    session.add(other)
    session.commit()
    second = client.post(
        f"/api/v1/{direction}s", json=body, headers=auth_headers(api, other.id, key)
    )
    assert second.status_code == 201
    assert second.json()["id"] != first.json()["id"]

    # Actor-scoped lookup never leaks the other actor's record.
    own = client.get(
        f"/api/v1/{direction}s/by-key/{key}", headers=auth_headers(api, other.id)
    )
    assert own.status_code == 200 and own.json()["id"] == second.json()["id"]
    assert counts(session)["inbounds" if direction == "inbound" else "outbounds"] == 2


@pytest.mark.parametrize("direction", DIRECTIONS)
def test_different_key_same_payload_creates_new_record(movement_api, direction):
    api = movement_api
    client, session = api["client"], api["session"]
    body = body_for(api)
    first = client.post(
        f"/api/v1/{direction}s",
        json=body,
        headers=auth_headers(api, api["operator_id"], uuid4()),
    )
    second = client.post(
        f"/api/v1/{direction}s",
        json=body,
        headers=auth_headers(api, api["operator_id"], uuid4()),
    )
    assert first.status_code == 201 and second.status_code == 201
    assert second.json()["id"] != first.json()["id"]
    assert counts(session)["inbounds" if direction == "inbound" else "outbounds"] == 2


def test_failed_outbound_attempt_does_not_burn_key(movement_api):
    api = movement_api
    client, session = api["client"], api["session"]
    key = uuid4()
    headers = auth_headers(api, api["operator_id"], key)
    denied = client.post(
        "/api/v1/outbounds", json=body_for(api, quantity=999), headers=headers
    )
    assert denied.status_code == 409
    assert denied.json()["detail"]["code"] == "INSUFFICIENT_STOCK"
    assert counts(session)["outbounds"] == 0

    service_for(session).create_inbound(
        api["operator_id"],
        InventoryMovementCreate(
            warehouse_id=api["warehouse_id"], product_id=api["product_id"], quantity=7
        ),
    )
    retry = client.post(
        "/api/v1/outbounds", json=body_for(api, quantity=7), headers=headers
    )
    assert retry.status_code == 201
    assert stock_quantity(session, api) == 10


def test_failed_inbound_attempt_with_other_body_does_not_burn_key(movement_api):
    api = movement_api
    client, session = api["client"], api["session"]
    key = uuid4()
    headers = auth_headers(api, api["operator_id"], key)
    missing = client.post(
        "/api/v1/inbounds",
        json=body_for(api, quantity=4) | {"warehouse_id": 999999},
        headers=headers,
    )
    assert missing.status_code == 404
    assert counts(session)["inbounds"] == 0
    retry = client.post("/api/v1/inbounds", json=body_for(api, quantity=4), headers=headers)
    assert retry.status_code == 201
    assert stock_quantity(session, api) == 14


@pytest.mark.parametrize("direction", DIRECTIONS)
def test_concurrent_same_new_key_creates_exactly_one(
    movement_api, postgres_engine, direction
):
    api = movement_api
    barrier = Barrier(2)
    key = uuid4()
    model = Inbound if direction == "inbound" else Outbound
    before = stock_quantity(api["session"], api)

    def run():
        with Session(postgres_engine) as session:
            barrier.wait(timeout=10)
            record, replay = getattr(service_for(session), f"create_{direction}")(
                api["operator_id"],
                InventoryMovementCreate(
                    warehouse_id=api["warehouse_id"],
                    product_id=api["product_id"],
                    quantity=3,
                    reference="CK-01",
                ),
                key,
            )
            return record.id, replay

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run) for _ in range(2)]
        results = [future.result(timeout=20) for future in futures]

    assert len({record_id for record_id, _ in results}) == 1
    assert sorted(replay for _, replay in results) == [False, True]
    with Session(postgres_engine) as check:
        assert check.scalar(select(func.count()).select_from(model)) == 1
        expected = before + 3 if direction == "inbound" else before - 3
        assert stock_quantity(check, api) == expected


def test_unexpected_failure_after_inbound_flush_rolls_back_all_writes(
    movement_api, monkeypatch
):
    api = movement_api
    session = api["session"]
    service = service_for(session)

    def fail_transaction_insert(inbound: Inbound, actor_id: int):
        raise RuntimeError("simulated stock-transaction persistence failure")

    monkeypatch.setattr(
        service.repository,
        "add_stock_transaction_for_inbound",
        fail_transaction_insert,
    )
    with pytest.raises(RuntimeError, match="simulated stock-transaction persistence failure"):
        service.create_inbound(
            api["operator_id"],
            InventoryMovementCreate(
                warehouse_id=api["warehouse_id"],
                product_id=api["product_id"],
                quantity=3,
            ),
        )
    session.expire_all()
    assert stock_quantity(session, api) == 10
    assert counts(session) == {
        "inbounds": 0,
        "outbounds": 0,
        "transactions": 0,
        "audits": 0,
    }


@pytest.mark.parametrize("direction", DIRECTIONS)
def test_retry503_envelope_and_retry_after_preserved_at_router(
    movement_api, monkeypatch, direction
):
    api = movement_api
    client, session = api["client"], api["session"]
    code = f"{direction.upper()}_RETRY_REQUIRED"

    def retry_required(*_args):
        raise DomainError(503, code, f"Retry the same {direction} request.")

    monkeypatch.setattr(InventoryService, f"create_{direction}", retry_required)
    response = client.post(
        f"/api/v1/{direction}s",
        json=body_for(api),
        headers=auth_headers(api, api["operator_id"], uuid4()),
    )
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "1"
    assert response.json() == {
        "detail": {"code": code, "message": f"Retry the same {direction} request.", "fields": None}
    }
    assert counts(session)["inbounds" if direction == "inbound" else "outbounds"] == 0


def test_connection_loss_reported_after_real_commit_recovers_same_operation(
    movement_api, monkeypatch
):
    api = movement_api
    client, session = api["client"], api["session"]
    commit = session.commit
    once = []

    def commit_then_connection_loss():
        commit()
        if not once:
            once.append(True)
            raise OperationalError(
                None,
                None,
                psycopg.OperationalError("simulated connection loss"),
                connection_invalidated=True,
            )

    monkeypatch.setattr(session, "commit", commit_then_connection_loss)
    headers = auth_headers(api, api["operator_id"], uuid4())
    response = client.post("/api/v1/inbounds", json=body_for(api), headers=headers)
    assert response.status_code == 503 and response.headers["Retry-After"] == "1"
    assert counts(session)["inbounds"] == 1
    replay = client.post("/api/v1/inbounds", json=body_for(api), headers=headers)
    assert replay.status_code == 200
    assert replay.json()["id"] == session.scalar(select(Inbound)).id
    assert counts(session)["transactions"] == 1
