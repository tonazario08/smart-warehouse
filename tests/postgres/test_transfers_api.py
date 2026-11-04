"""Additive transfer routes, strict boundaries, authorization and response recovery."""

from uuid import uuid4

import psycopg
import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.auth.security import create_access_token
from app.core.errors import DomainError
from app.models import MovementProvenance, StockTransfer, User
from app.transfers.service import TransferService

from .test_transfer_atomicity import balances, request_for, row_counts, seed_transfer

pytestmark = pytest.mark.postgres
EXPECTED = {
    "id",
    "source_warehouse_id",
    "destination_warehouse_id",
    "product_id",
    "quantity",
    "reference",
    "note",
    "created_by_id",
    "created_at",
    "outbound_id",
    "inbound_id",
    "outbound_transaction_id",
    "inbound_transaction_id",
    "source_quantity_before",
    "source_quantity_after",
    "destination_quantity_before",
    "destination_quantity_after",
}


@pytest.fixture
def transfer_api(postgres_session, postgres_client, unit_settings):
    ids = seed_transfer(postgres_session)
    return (
        postgres_client,
        postgres_session,
        ids,
        {
            "Authorization": "Bearer " + create_access_token(ids[0], unit_settings),
            "Idempotency-Key": str(uuid4()),
        },
    )


def test_exact_post_replay_and_lost_response_recovery(transfer_api):
    client, session, ids, headers = transfer_api
    body = request_for(ids).model_dump()
    response = client.post("/api/v1/transfers", json=body, headers=headers)
    assert response.status_code == 201
    assert set(response.json()) == EXPECTED
    before = balances(session)
    replay = client.post(
        "/api/v1/transfers", json={**body, "reference": "  CK-01  "}, headers=headers
    )
    assert replay.status_code == 200 and replay.json() == response.json()
    lookup = client.get("/api/v1/transfers/by-key/" + headers["Idempotency-Key"], headers=headers)
    assert lookup.status_code == 200 and lookup.json() == response.json()
    detail = client.get("/api/v1/transfers/" + str(response.json()["id"]), headers=headers)
    assert detail.status_code == 200 and detail.json() == response.json()
    conflict = client.post("/api/v1/transfers", json={**body, "quantity": 1}, headers=headers)
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"
    assert balances(session) == before and row_counts(session)["stock_transfers"] == 1


@pytest.mark.parametrize(
    "path", ["/transfers", "/transfers/1", "/transfers/by-key/KEY", "/movement-provenance"]
)
@pytest.mark.parametrize(
    "role,active,expected", [(None, True, 401), ("client", True, 403), ("warehouse", False, 401)]
)
def test_all_reads_reject_unauthorized_callers(
    transfer_api, unit_settings, path, role, active, expected
):
    client, session, ids, _headers = transfer_api
    actor = session.get(User, ids[0])
    actor.role = role or "warehouse"
    actor.is_active = active
    session.commit()
    headers = (
        {}
        if role is None
        else {"Authorization": "Bearer " + create_access_token(ids[0], unit_settings)}
    )
    response = client.get("/api/v1" + path.replace("KEY", str(uuid4())), headers=headers)
    assert response.status_code == expected
    assert row_counts(session)["stock_transfers"] == 0


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
def test_post_authorization_precedes_key_resolution(transfer_api, role, active, expected):
    client, session, ids, headers = transfer_api
    actor = session.get(User, ids[0])
    actor.role = role or "warehouse"
    actor.is_active = active
    session.commit()
    if role is None:
        headers.pop("Authorization")
    if expected != 201:
        headers["Idempotency-Key"] = "bad-key"
    response = client.post("/api/v1/transfers", json=request_for(ids).model_dump(), headers=headers)
    assert response.status_code == expected
    assert row_counts(session)["stock_transfers"] == (1 if expected == 201 else 0)


@pytest.mark.parametrize("key", [None, "", "bad-key", "3,4"])
def test_uuid_header_validation_is_safe_and_located(transfer_api, key):
    client, session, ids, headers = transfer_api
    if key is None:
        headers.pop("Idempotency-Key")
    else:
        headers["Idempotency-Key"] = key
    response = client.post("/api/v1/transfers", json=request_for(ids).model_dump(), headers=headers)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "REQUEST_VALIDATION_ERROR"
    assert any(
        "header" in name.lower() and "idempotency" in name.lower()
        for name in response.json()["detail"]["fields"]
    )
    assert row_counts(session)["stock_transfers"] == 0


@pytest.mark.parametrize(
    "suffix",
    [
        "?source_warehouse_id=0",
        "?product_id=1.0",
        "?page=true",
        "?page=0",
        "?page_size=101",
        "?purpose=sales",
        "?created_from=123",
        "?created_from=2026-10-17T00:00:00",
        "?created_from=2026-10-18T00:00:00Z&created_to=2026-10-17T00:00:00Z",
    ],
)
def test_strict_query_errors(transfer_api, suffix):
    client, _session, _ids, headers = transfer_api
    response = client.get("/api/v1/transfers" + suffix, headers=headers)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "REQUEST_VALIDATION_ERROR"


@pytest.mark.parametrize("identifier", ["0", "-1", "true", "1.5", "2147483648"])
def test_invalid_transfer_path_is422(transfer_api, identifier):
    client, _session, _ids, headers = transfer_api
    assert client.get("/api/v1/transfers/" + identifier, headers=headers).status_code == 422


def test_filters_order_inclusive_dates_paging_empty_and_missing(transfer_api):
    client, session, ids, headers = transfer_api
    first = client.post("/api/v1/transfers", json=request_for(ids).model_dump(), headers=headers)
    assert first.status_code == 201
    headers["Idempotency-Key"] = str(uuid4())
    second = client.post(
        "/api/v1/transfers", json=request_for(ids, 1).model_dump(), headers=headers
    )
    assert second.status_code == 201
    date = first.json()["created_at"]
    exact = client.get(
        "/api/v1/transfers", params={"created_from": date, "created_to": date}, headers=headers
    )
    assert [row["id"] for row in exact.json()["items"]] == [first.json()["id"]]
    page = client.get("/api/v1/transfers?page=1&page_size=1", headers=headers).json()
    assert page["total"] == 2 and page["items"][0]["id"] == second.json()["id"]
    filtered = client.get(
        "/api/v1/transfers",
        params={
            "source_warehouse_id": ids[1],
            "destination_warehouse_id": ids[2],
            "product_id": ids[3],
        },
        headers=headers,
    ).json()
    assert filtered["total"] == 2
    assert (
        client.get("/api/v1/transfers?product_id=2147483647", headers=headers).json()["items"] == []
    )
    assert client.get("/api/v1/transfers/2147483647", headers=headers).status_code == 404
    assert (
        client.get("/api/v1/transfers/by-key/" + str(uuid4()), headers=headers).status_code == 404
    )
    assert client.get("/api/v1/transfers/by-key/not-a-uuid", headers=headers).status_code == 422
    assert row_counts(session)["stock_transfers"] == 2


def test_own_key_never_resolves_another_actor_and_replay_requires_current_permission(
    transfer_api, unit_settings
):
    client, session, ids, headers = transfer_api
    body = request_for(ids).model_dump()
    assert client.post("/api/v1/transfers", json=body, headers=headers).status_code == 201
    other = User(email="other-api@example.test", password_hash="fixture", role="admin")
    session.add(other)
    session.commit()
    other_headers = {
        **headers,
        "Authorization": "Bearer " + create_access_token(other.id, unit_settings),
    }
    assert (
        client.get(
            "/api/v1/transfers/by-key/" + headers["Idempotency-Key"], headers=other_headers
        ).status_code
        == 404
    )
    actor = session.get(User, ids[0])
    actor.role = "client"
    session.commit()
    assert client.post("/api/v1/transfers", json=body, headers=headers).status_code == 403
    assert row_counts(session)["stock_transfers"] == 1


def test_provenance_outer_join_fallback_and_conjunctive_filters(transfer_api):
    client, session, ids, headers = transfer_api
    response = client.post("/api/v1/transfers", json=request_for(ids).model_dump(), headers=headers)
    assert response.status_code == 201
    data = response.json()
    result = client.get("/api/v1/movement-provenance", headers=headers)
    assert result.status_code == 200
    assert result.json()["items"] == [
        {
            "transaction_id": data["outbound_transaction_id"],
            "purpose": "transfer_out",
            "transfer_id": data["id"],
        },
        {
            "transaction_id": data["inbound_transaction_id"],
            "purpose": "transfer_in",
            "transfer_id": data["id"],
        },
    ]
    rows = client.get(
        "/api/v1/movement-provenance",
        params={
            "transfer_id": data["id"],
            "purpose": "transfer_out",
            "transaction_id": data["outbound_transaction_id"],
        },
        headers=headers,
    ).json()
    assert rows["total"] == 1
    session.delete(session.get(MovementProvenance, data["outbound_transaction_id"]))
    session.commit()
    fallback = client.get(
        "/api/v1/movement-provenance?purpose=legacy_unknown", headers=headers
    ).json()
    assert fallback["items"] == [
        {
            "transaction_id": data["outbound_transaction_id"],
            "purpose": "legacy_unknown",
            "transfer_id": None,
        }
    ]
    assert (
        client.get("/api/v1/movement-provenance?purpose=sales", headers=headers).status_code == 422
    )


def test_retry503_envelope_and_retry_after_preserved_at_router(transfer_api, monkeypatch):
    client, session, ids, headers = transfer_api

    def retry_required(*_args):
        raise DomainError(503, "TRANSFER_RETRY_REQUIRED", "Retry the same transfer request.")

    monkeypatch.setattr(TransferService, "create", retry_required)
    response = client.post("/api/v1/transfers", json=request_for(ids).model_dump(), headers=headers)
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "1"
    assert response.json() == {
        "detail": {
            "code": "TRANSFER_RETRY_REQUIRED",
            "message": "Retry the same transfer request.",
            "fields": None,
        }
    }
    assert row_counts(session)["stock_transfers"] == 0


def test_connection_loss_reported_after_real_commit_recovers_same_operation(
    transfer_api, monkeypatch
):
    client, session, ids, headers = transfer_api
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
    response = client.post("/api/v1/transfers", json=request_for(ids).model_dump(), headers=headers)
    assert response.status_code == 503 and response.headers["Retry-After"] == "1"
    assert row_counts(session)["stock_transfers"] == 1
    replay = client.post("/api/v1/transfers", json=request_for(ids).model_dump(), headers=headers)
    assert replay.status_code == 200
    assert replay.json()["id"] == session.scalar(select(StockTransfer)).id
    assert row_counts(session)["transactions"] == 2


@pytest.mark.parametrize("location", ["path", "query"])
def test_huge_decimal_identifier_is_a_validation_error(transfer_api, location):
    client, _session, _ids, headers = transfer_api
    value = "9" * 5000
    path = (
        "/api/v1/transfers/" + value
        if location == "path"
        else "/api/v1/transfers?product_id=" + value
    )
    response = client.get(path, headers=headers)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "REQUEST_VALIDATION_ERROR"
