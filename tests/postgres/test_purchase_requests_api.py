"""Real API contracts: current authorization, owner SQL scope and durable replay."""

from uuid import uuid4

import pytest
from sqlalchemy import event, func, select

from app.auth.security import create_access_token
from app.models import (
    Category,
    Inbound,
    MovementProvenance,
    Outbound,
    Product,
    PurchaseRequest,
    PurchaseRequestWorkflow,
    Stock,
    StockTransaction,
    User,
    Warehouse,
)

pytestmark = pytest.mark.postgres
BASE = "/api/v1/purchase-requests"


def seed_purchase(session, quantity=10):
    users = [
        User(email=f"m4-api-{name}@example.test", password_hash="fixture", role=role)
        for name, role in (
            ("client", "client"),
            ("other", "client"),
            ("admin", "admin"),
            ("warehouse", "warehouse"),
        )
    ]
    category = Category(name="M4 API category")
    product = Product(sku="M4-API", name="M4 API product", category=category, unit="each")
    warehouses = [
        Warehouse(code=f"M4-API-{i}", name=f"M4 API warehouse {i}", address="Fixture")
        for i in (1, 2)
    ]
    session.add_all([*users, product, *warehouses])
    session.flush()
    if quantity is not None:
        session.add(Stock(warehouse_id=warehouses[0].id, product_id=product.id, quantity=quantity))
    session.commit()
    return {
        "client": users[0].id,
        "other": users[1].id,
        "admin": users[2].id,
        "warehouse": users[3].id,
        "product": product.id,
        "source": warehouses[0].id,
        "destination": warehouses[1].id,
    }


def headers_for(ids, role, settings, key=None):
    result = {"Authorization": "Bearer " + create_access_token(ids[role], settings)}
    if key is not None:
        result["Idempotency-Key"] = str(key)
    return result


def body_for(ids, **changes):
    return {
        "warehouse_id": ids["source"],
        "product_id": ids["product"],
        "quantity": 3,
        "note": "  yêu cầu  ",
        **changes,
    }


def effects(session):
    return {
        model.__tablename__: session.scalar(select(func.count()).select_from(model))
        for model in (
            PurchaseRequest,
            PurchaseRequestWorkflow,
            Stock,
            Inbound,
            Outbound,
            StockTransaction,
            MovementProvenance,
        )
    }


@pytest.fixture
def api_data(postgres_session, unit_settings):
    ids = seed_purchase(postgres_session)
    return ids, {
        role: headers_for(ids, role, unit_settings)
        for role in ("client", "other", "admin", "warehouse")
    }


def create(client, ids, headers, key=None, **changes):
    return client.post(
        BASE,
        headers={**headers, "Idempotency-Key": str(key or uuid4())},
        json=body_for(ids, **changes),
    )


def test_owner_scoped_reads_counts_and_recovery(postgres_client, postgres_session, api_data):
    ids, auth = api_data
    key = uuid4()
    first = create(postgres_client, ids, auth["client"], key)
    assert first.status_code == 201
    own = first.json()
    assert first.headers["location"] == BASE + f"/{own['id']}"
    assert own["requested_by_id"] == ids["client"] and own["note"] == "yêu cầu"
    assert own["status"] == "pending" and own["workflow_managed"] is True
    assert own["decision"] is None and own["fulfillment"] is None
    assert len(own["request_number"]) == 35 and own["request_number"].startswith("PR-")
    assert set(own) == {
        "id",
        "request_number",
        "warehouse_id",
        "product_id",
        "quantity",
        "status",
        "requested_by_id",
        "created_at",
        "updated_at",
        "workflow_managed",
        "note",
        "decision",
        "fulfillment",
    }
    second = create(postgres_client, ids, auth["other"])
    assert second.status_code == 201
    for role, total in (("client", 1), ("other", 1), ("admin", 2), ("warehouse", 2)):
        page = postgres_client.get(BASE, headers=auth[role]).json()
        assert page["total"] == total
        assert page["page"] == 1 and page["page_size"] == 20
        if role in ("client", "other"):
            assert all(row["requested_by_id"] == ids[role] for row in page["items"])
        detail = postgres_client.get(BASE + f"/{own['id']}", headers=auth[role])
        assert detail.status_code == (404 if role == "other" else 200)
        recovered = postgres_client.get(BASE + f"/by-key/{key}", headers=auth[role])
        assert recovered.status_code == (200 if role == "client" else 404)
    assert (
        postgres_client.get(BASE, headers=auth["client"], params={"page": 2}).json()["items"] == []
    )
    assert (
        postgres_client.get(BASE, headers=auth["client"], params={"status": "approved"}).json()[
            "total"
        ]
        == 0
    )
    assert (
        postgres_client.get(
            BASE, headers=auth["admin"], params={"requested_by_id": ids["other"]}
        ).json()["total"]
        == 1
    )
    assert (
        postgres_client.get(
            BASE, headers=auth["client"], params={"requested_by_id": ids["client"]}
        ).status_code
        == 422
    )
    counts = effects(postgres_session)
    assert counts["outbounds"] == counts["transactions"] == counts["movement_provenance"] == 0


@pytest.mark.parametrize("suffix", ["", "/999", "/by-key/00000000-0000-0000-0000-000000000000"])
def test_anonymous_is_denied_before_lookup(postgres_client, suffix):
    assert postgres_client.get(BASE + suffix).status_code == 401


@pytest.mark.parametrize(
    "role,action",
    [
        ("admin", "create"),
        ("warehouse", "create"),
        ("client", "approve"),
        ("client", "reject"),
        ("client", "fulfill"),
        ("warehouse", "approve"),
        ("warehouse", "reject"),
    ],
)
def test_forbidden_action_before_target_disclosure(postgres_client, api_data, role, action):
    ids, auth = api_data
    response = (
        create(postgres_client, ids, auth[role])
        if action == "create"
        else (
            postgres_client.post(
                BASE + "/999/" + action,
                headers=auth[role],
                json={"rejection_reason": "reason"} if action == "reject" else {},
            )
        )
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    "query",
    [
        "page=0",
        "page_size=101",
        "page=" + "9" * 5000,
        "warehouse_id=" + "9" * 5000,
        "product_id=true",
        "created_from=123",
        "created_to=1760745600",
        "created_from=2026-10-19",
        "created_from=2026-10-20T00:00:00Z&created_to=2026-10-19T00:00:00Z",
        "unknown=1",
        "page=1&page=2",
        "status=pending&status=approved",
        "requested_by_id=1&requested_by_id=2",
    ],
)
def test_strict_query_boundary(postgres_client, api_data, query):
    _, auth = api_data
    assert postgres_client.get(BASE + "?" + query, headers=auth["admin"]).status_code == 422


@pytest.mark.parametrize(
    "suffix", ["/0", "/-1", "/true", "/2147483648", "/" + "9" * 5000, "/by-key/not-a-uuid"]
)
def test_strict_path_boundary(postgres_client, api_data, suffix):
    _, auth = api_data
    assert postgres_client.get(BASE + suffix, headers=auth["client"]).status_code == 422


def test_header_boundary_and_strict_action_bodies(postgres_client, api_data):
    ids, auth = api_data
    for extra in ({}, {"Idempotency-Key": "bad"}):
        assert (
            postgres_client.post(
                BASE, headers={**auth["client"], **extra}, json=body_for(ids)
            ).status_code
            == 422
        )
    duplicate = [
        *auth["client"].items(),
        ("Idempotency-Key", str(uuid4())),
        ("Idempotency-Key", str(uuid4())),
    ]
    assert postgres_client.post(BASE, headers=duplicate, json=body_for(ids)).status_code == 422
    for extra in ({"requested_by_id": ids["other"]}, {"status": "fulfilled"}, {"quantity": True}):
        assert create(postgres_client, ids, auth["client"], **extra).status_code == 422
    for action, body in (
        ("approve", {"status": "approved"}),
        ("fulfill", {"quantity": 3}),
        ("reject", {"rejection_reason": " \n\t"}),
    ):
        assert (
            postgres_client.post(
                BASE + "/999/" + action, headers=auth["admin"], json=body
            ).status_code
            == 422
        )


def test_pending_create_replay_conflict_other_actor_and_inactive_policy(
    postgres_client, postgres_session, api_data
):
    ids, auth = api_data
    key = uuid4()
    first = create(postgres_client, ids, auth["client"], key).json()
    assert "id" in first
    product = postgres_session.get(Product, ids["product"])
    product.is_active = False
    postgres_session.commit()
    same = create(postgres_client, ids, auth["client"], key, note="yêu cầu")
    assert same.status_code == 200 and same.json() == first
    assert (
        create(postgres_client, ids, auth["client"], key, quantity=4).json()["detail"]["code"]
        == "IDEMPOTENCY_KEY_CONFLICT"
    )
    assert (
        create(postgres_client, ids, auth["other"], key).json()["detail"]["code"]
        == "PRODUCT_NOT_REQUESTABLE"
    )
    product.is_active = True
    postgres_session.commit()
    other = create(postgres_client, ids, auth["other"], key)
    assert other.status_code == 201 and other.json()["id"] != first["id"]
    assert create(postgres_client, ids, auth["client"], quantity=2147483647).status_code == 201
    actor = postgres_session.get(User, ids["client"])
    actor.role = "warehouse"
    postgres_session.commit()
    assert create(postgres_client, ids, auth["client"], key).status_code == 403
    actor.is_active = False
    postgres_session.commit()
    assert postgres_client.get(BASE, headers=auth["client"]).status_code == 401


def test_openapi_purchase_request_contract(postgres_client):
    openapi = postgres_client.get("/openapi.json").json()
    paths = {
        path: methods for path, methods in openapi["paths"].items() if path.startswith(BASE)
    }
    assert {path.removeprefix(BASE): set(methods) for path, methods in paths.items()} == {
        "": {"get", "post"},
        "/by-key/{key}": {"get"},
        "/nearest-warehouses": {"get", "post"},
        "/{request_id}": {"get"},
        "/{request_id}/delivery-location": {"get"},
        "/{request_id}/approve": {"post"},
        "/{request_id}/reject": {"post"},
        "/{request_id}/fulfill": {"post"},
        "/geocode-delivery-address": {"post"},
        "/delivery-map": {"get"},
    }
    geocode = paths[BASE + "/geocode-delivery-address"]["post"]
    delivery_map = paths[BASE + "/delivery-map"]["get"]
    assert geocode["security"] == delivery_map["security"] == [{"HTTPBearer": []}]
    assert "parameters" not in geocode and "parameters" not in delivery_map
    assert "requestBody" not in delivery_map

    schemas = openapi["components"]["schemas"]
    geocode_body = geocode["requestBody"]
    assert geocode_body["required"] is True
    assert geocode_body["content"]["application/json"]["schema"]["$ref"].endswith(
        "/GeocodeAddressBody"
    )
    assert schemas["GeocodeAddressBody"]["required"] == ["address"]
    assert schemas["GeocodeAddressBody"]["additionalProperties"] is False
    assert set(schemas["GeocodeAddressBody"]["properties"]) == {"address"}
    assert set(schemas["GeocodeResult"]["properties"]) == {"status", "candidates"}
    assert set(schemas["DeliveryMap"]["properties"]) == {
        "state", "bounds", "roads", "places", "areas", "attribution", "license_url",
    }
    geocode_guest = postgres_client.post(
        BASE + "/geocode-delivery-address", json={"address": "Địa chỉ công cộng thử"}
    )
    map_guest = postgres_client.get(BASE + "/delivery-map")
    for denied in (geocode_guest, map_guest):
        assert denied.status_code == 401
        assert denied.headers["Cache-Control"] == "no-store"

    operation = paths[BASE]["post"]
    header = next(p for p in operation["parameters"] if p["name"] == "Idempotency-Key")
    assert header["required"] is True and header["schema"]["format"] == "uuid"
    assert "Location" in operation["responses"]["201"]["headers"]
    for methods in paths.values():
        for method in methods.values():
            assert {"401", "403", "404", "409", "422", "503"} <= set(method["responses"])
            assert "Retry-After" in method["responses"]["503"]["headers"]
    assert "200" in operation["responses"]


@pytest.mark.parametrize("state", ["approved", "rejected", "fulfilled"])
def test_create_replay_after_each_terminal_state(
    postgres_client, postgres_session, api_data, state
):
    ids, auth = api_data
    key = uuid4()
    original = create(postgres_client, ids, auth["client"], key).json()
    path = BASE + f"/{original['id']}"
    if state == "rejected":
        current = postgres_client.post(
            path + "/reject", headers=auth["admin"], json={"rejection_reason": "lý do"}
        )
    else:
        current = postgres_client.post(path + "/approve", headers=auth["admin"], json={})
        assert current.status_code == 200
        if state == "fulfilled":
            current = postgres_client.post(path + "/fulfill", headers=auth["warehouse"], json={})
    assert current.status_code == 200 and current.json()["status"] == state
    before = effects(postgres_session)
    postgres_session.get(Product, ids["product"]).is_active = False
    postgres_session.commit()
    replay = create(postgres_client, ids, auth["client"], key)
    assert replay.status_code == 200 and replay.json() == current.json()
    assert effects(postgres_session) == before
    for field in (
        "id",
        "request_number",
        "warehouse_id",
        "product_id",
        "quantity",
        "requested_by_id",
        "created_at",
        "note",
    ):
        assert replay.json()[field] == original[field]


def test_create_collision_rolls_back(postgres_client, postgres_session, api_data, monkeypatch):
    from types import SimpleNamespace

    import app.purchase_requests.service as implementation

    ids, auth = api_data
    first = create(postgres_client, ids, auth["client"]).json()
    key = uuid4()
    before = effects(postgres_session)
    with monkeypatch.context() as patch:
        patch.setattr(
            implementation, "uuid4", lambda: SimpleNamespace(hex=first["request_number"][3:])
        )
        failed = create(postgres_client, ids, auth["client"], key)
    assert failed.status_code == 409 and failed.json()["detail"]["code"] == "DATABASE_CONFLICT"
    assert effects(postgres_session) == before
    assert postgres_client.get(BASE + f"/by-key/{key}", headers=auth["client"]).status_code == 404
    assert create(postgres_client, ids, auth["client"], key).status_code == 201


def test_conjunctive_inclusive_filters_and_stable_owner_paging(
    postgres_client, postgres_session, api_data
):
    from sqlalchemy import update

    ids, auth = api_data
    first = create(postgres_client, ids, auth["client"]).json()
    other = create(postgres_client, ids, auth["other"]).json()
    third = create(postgres_client, ids, auth["client"]).json()
    timestamp = "2026-10-19T00:00:00+00:00"
    postgres_session.execute(update(PurchaseRequest).values(created_at=timestamp))
    postgres_session.commit()
    filters = {
        "status": "pending",
        "warehouse_id": ids["source"],
        "product_id": ids["product"],
        "created_from": "2026-10-19T07:00:00+07:00",
        "created_to": timestamp,
        "page_size": 1,
    }
    own = postgres_client.get(BASE, headers=auth["client"], params=filters).json()
    assert own["total"] == 2 and [row["id"] for row in own["items"]] == [third["id"]]
    second = postgres_client.get(BASE, headers=auth["client"], params={**filters, "page": 2}).json()
    assert second["total"] == 2 and [row["id"] for row in second["items"]] == [first["id"]]
    staff = postgres_client.get(
        BASE, headers=auth["warehouse"], params={**filters, "page_size": 20}
    ).json()
    assert [row["id"] for row in staff["items"]] == [third["id"], other["id"], first["id"]]


@pytest.mark.parametrize("state", ["pending", "approved", "rejected", "fulfilled"])
def test_legacy_requests_are_honest_and_read_only(
    postgres_client, postgres_session, api_data, state
):
    ids, auth = api_data
    legacy = PurchaseRequest(
        request_number="PR-M4-LEGACY",
        warehouse_id=ids["source"],
        product_id=ids["product"],
        quantity=3,
        status=state,
        requested_by_id=ids["client"],
    )
    postgres_session.add(legacy)
    postgres_session.commit()
    path = BASE + f"/{legacy.id}"
    original = postgres_client.get(path, headers=auth["client"]).json()
    assert original["workflow_managed"] is False
    assert original["note"] is original["decision"] is original["fulfillment"] is None
    before = effects(postgres_session)
    for action in ("approve", "reject", "fulfill"):
        response = postgres_client.post(
            path + "/" + action,
            headers=auth["admin"],
            json={"rejection_reason": "reason"} if action == "reject" else {},
        )
        assert (
            response.status_code == 409
            and response.json()["detail"]["code"] == "LEGACY_PURCHASE_REQUEST_READ_ONLY"
        )
    assert effects(postgres_session) == before
    assert postgres_client.get(path, headers=auth["admin"]).json() == original


@pytest.mark.parametrize("operation", ["create", "approve", "fulfill"])
@pytest.mark.parametrize("committed", [False, True])
def test_simulated_commit_connection_loss_recovers_same_identity(
    postgres_client, postgres_session, api_data, monkeypatch, operation, committed
):
    from sqlalchemy.exc import OperationalError

    ids, auth = api_data
    key = uuid4()
    path = BASE
    headers, body = {**auth["client"], "Idempotency-Key": str(key)}, body_for(ids)
    if operation != "create":
        row = create(postgres_client, ids, auth["client"], key).json()
        path = BASE + f"/{row['id']}/" + operation
        headers, body = auth["admin"], {}
        if operation == "fulfill":
            assert (
                postgres_client.post(
                    BASE + f"/{row['id']}/approve", headers=auth["admin"], json={}
                ).status_code
                == 200
            )
    original, calls = postgres_session.commit, []

    class LostConnection(Exception):
        sqlstate = "08006"

    def lose_response():
        calls.append(1)
        if committed:
            original()
        raise OperationalError(
            None,
            None,
            LostConnection("private injected DB diagnostic"),
            connection_invalidated=True,
        )

    with monkeypatch.context() as patch:
        patch.setattr(postgres_session, "commit", lose_response)
        response = postgres_client.post(path, headers=headers, json=body)
    assert response.status_code == 503 and response.headers["Retry-After"] == "1"
    assert response.json()["detail"]["code"] == "PURCHASE_REQUEST_RETRY_REQUIRED"
    assert "private injected" not in response.text and len(calls) == 1
    # This deliberately injects a connection-loss boundary AFTER/BEFORE a real
    # commit, not an actual broken PostgreSQL wire-level COMMIT acknowledgement.
    recovered = postgres_client.get(BASE + f"/by-key/{key}", headers=auth["client"])
    assert recovered.status_code == (404 if operation == "create" and not committed else 200)
    repeated = postgres_client.post(path, headers=headers, json=body)
    assert repeated.status_code == (201 if operation == "create" and not committed else 200)
    if committed:
        assert repeated.json() == recovered.json()
    assert effects(postgres_session)["purchase_requests"] == 1
    assert effects(postgres_session)["outbounds"] == (1 if operation == "fulfill" else 0)


@pytest.mark.parametrize(
    "state,action,role,changed_role",
    [
        ("approved", "approve", "admin", "warehouse"),
        ("fulfilled", "approve", "admin", "warehouse"),
        ("fulfilled", "fulfill", "warehouse", "client"),
    ],
)
def test_current_role_and_active_user_precede_action_replay(
    postgres_client, postgres_session, api_data, state, action, role, changed_role
):
    ids, auth = api_data
    row = create(postgres_client, ids, auth["client"]).json()
    path = BASE + f"/{row['id']}"
    approved = postgres_client.post(path + "/approve", headers=auth["admin"], json={})
    assert approved.status_code == 200
    if state == "fulfilled":
        assert (
            postgres_client.post(path + "/fulfill", headers=auth["warehouse"], json={}).status_code
            == 200
        )
    before = effects(postgres_session)
    persisted = postgres_client.get(path, headers=auth["client"]).json()
    current_actor = postgres_session.get(User, ids[role])
    current_actor.role = changed_role
    postgres_session.commit()
    assert postgres_client.post(path + "/" + action, headers=auth[role], json={}).status_code == 403
    # The same old token is checked against current active state, not a replay shortcut.
    current_actor.is_active = False
    postgres_session.commit()
    assert postgres_client.post(path + "/" + action, headers=auth[role], json={}).status_code == 401
    assert effects(postgres_session) == before
    assert postgres_client.get(path, headers=auth["client"]).json() == persisted


def test_missing_references_and_authorized_missing_actions_are_safe(postgres_client, api_data):
    ids, auth = api_data
    for changes, code in (
        ({"warehouse_id": 999}, "WAREHOUSE_NOT_FOUND"),
        ({"product_id": 999}, "PRODUCT_NOT_FOUND"),
    ):
        response = create(postgres_client, ids, auth["client"], **changes)
        assert response.status_code == 404 and response.json()["detail"]["code"] == code
    for action in ("approve", "reject", "fulfill"):
        response = postgres_client.post(
            BASE + "/999/" + action,
            headers=auth["admin"],
            json={"rejection_reason": "reason"} if action == "reject" else {},
        )
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "PURCHASE_REQUEST_NOT_FOUND"


def test_recover_after_real_commit_with_deliberately_discarded_client_result(
    postgres_client, api_data
):
    ids, auth = api_data
    key = uuid4()
    # Real app + PG commit; deliberately do not use the response body to recover.
    assert create(postgres_client, ids, auth["client"], key).status_code == 201
    recovered = postgres_client.get(BASE + f"/by-key/{key}", headers=auth["client"])
    assert recovered.status_code == 200
    path = BASE + f"/{recovered.json()['id']}"
    assert (
        postgres_client.post(path + "/approve", headers=auth["admin"], json={}).status_code == 200
    )
    assert (
        postgres_client.post(path + "/fulfill", headers=auth["warehouse"], json={}).status_code
        == 200
    )
    after = postgres_client.get(path, headers=auth["client"]).json()
    assert after["status"] == "fulfilled"
    assert (
        postgres_client.post(path + "/fulfill", headers=auth["warehouse"], json={}).json() == after
    )
    assert create(postgres_client, ids, auth["client"], key).json() == after
    # This discards real returned results, not a claimed real network disconnect.


NEAREST = BASE + "/nearest-warehouses"


def seed_nearest(session):
    users = [
        User(email=f"m4-near-{name}@example.test", password_hash="fixture", role=role)
        for name, role in (("client", "client"), ("admin", "admin"), ("warehouse", "warehouse"))
    ]
    category = Category(name="M4 nearest category")
    product = Product(sku="M4-NEAR", name="M4 nearest product", category=category, unit="each")
    inactive = Product(
        sku="M4-NEAR-OFF",
        name="M4 nearest inactive",
        category=category,
        unit="each",
        is_active=False,
    )
    warehouses = [
        Warehouse(
            code="M4-NEAR-1",
            name="M4 near tie first",
            address="Fixture",
            latitude=10.0,
            longitude=106.0,
        ),
        Warehouse(
            code="M4-NEAR-2",
            name="M4 near tie second",
            address="Fixture",
            latitude=10.0,
            longitude=106.0,
        ),
        Warehouse(
            code="M4-NEAR-3",
            name="M4 near farther",
            address="Fixture",
            latitude=10.0,
            longitude=107.0,
        ),
        Warehouse(code="M4-NEAR-4", name="M4 near no coordinates", address="Fixture"),
        Warehouse(
            code="M4-NEAR-5",
            name="M4 near low stock",
            address="Fixture",
            latitude=10.0,
            longitude=106.0,
        ),
    ]
    session.add_all([*users, product, inactive, *warehouses])
    session.flush()
    session.add_all(
        [
            Stock(warehouse_id=warehouses[0].id, product_id=product.id, quantity=5),
            Stock(warehouse_id=warehouses[1].id, product_id=product.id, quantity=50),
            Stock(warehouse_id=warehouses[2].id, product_id=product.id, quantity=100),
            Stock(warehouse_id=warehouses[3].id, product_id=product.id, quantity=100),
            Stock(warehouse_id=warehouses[4].id, product_id=product.id, quantity=2),
        ]
    )
    session.commit()
    return {
        "client": users[0].id,
        "admin": users[1].id,
        "warehouse": users[2].id,
        "product": product.id,
        "inactive": inactive.id,
        "warehouses": [warehouse.id for warehouse in warehouses],
    }


@pytest.fixture
def nearest_data(postgres_session, unit_settings):
    ids = seed_nearest(postgres_session)
    auth = {
        role: {"Authorization": "Bearer " + create_access_token(ids[role], unit_settings)}
        for role in ("client", "admin", "warehouse")
    }
    return ids, auth


def nearest_params(ids, **changes):
    return {
        "product_id": ids["product"],
        "quantity": 3,
        "latitude": 10.0,
        "longitude": 106.0,
        **changes,
    }


def test_nearest_warehouse_lookup_reads_active_product_and_stock_in_one_statement(
    postgres_client, postgres_session, nearest_data
):
    ids, auth = nearest_data
    connection = postgres_session.connection()
    statements: list[str] = []

    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        if "FROM products" in statement or "JOIN stocks" in statement:
            statements.append(statement)

    event.listen(connection, "before_cursor_execute", capture)
    try:
        response = postgres_client.get(
            NEAREST, headers=auth["client"], params=nearest_params(ids)
        )
    finally:
        event.remove(connection, "before_cursor_execute", capture)

    assert response.status_code == 200
    assert response.json()["warehouses"]
    assert len(statements) == 1
    assert "products.is_active" in statements[0] and "JOIN stocks" in statements[0]


def test_nearest_warehouses_rank_by_distance_and_ties_by_id(
    postgres_client, postgres_session, nearest_data
):
    ids, auth = nearest_data
    response = postgres_client.get(
        NEAREST, headers=auth["client"], params=nearest_params(ids)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["product_id"] == ids["product"] and body["quantity"] == 3
    assert body["method"] == "great_circle_haversine"
    assert body["earth_radius_meters"] == pytest.approx(6_371_008.8)
    rows = body["warehouses"]
    assert [row["warehouse_id"] for row in rows] == ids["warehouses"][:3]
    assert rows[0]["distance_km"] == 0.0 and rows[1]["distance_km"] == 0.0
    # Asymmetric point: one degree of longitude at latitude 10 is ~109.5 km, so an
    # accidental latitude/longitude swap in the distance call cannot pass unnoticed.
    assert rows[2]["distance_km"] == pytest.approx(109.506, abs=0.001)
    assert [row["available_quantity"] for row in rows] == [5, 50, 100]
    assert set(rows[0]) == {
        "warehouse_id",
        "code",
        "name",
        "available_quantity",
        "distance_km",
    }

    narrow = postgres_client.get(
        NEAREST, headers=auth["client"], params=nearest_params(ids, quantity=60)
    ).json()
    assert [row["warehouse_id"] for row in narrow["warehouses"]] == [ids["warehouses"][2]]


@pytest.mark.parametrize("role", ["admin", "warehouse"])
def test_nearest_warehouses_are_forbidden_before_data_disclosure(
    postgres_client, nearest_data, role
):
    ids, auth = nearest_data
    response = postgres_client.get(NEAREST, headers=auth[role], params=nearest_params(ids))
    assert response.status_code == 403
    assert "warehouses" not in response.text


@pytest.mark.parametrize(
    "path", ["", "/by-key/00000000-0000-0000-0000-000000000000"]
)
def test_nearest_warehouses_anonymous_is_denied(postgres_client, path):
    response = postgres_client.get(BASE + path)
    assert response.status_code == 401


def test_nearest_warehouses_anonymous_query_is_denied(postgres_client, nearest_data):
    ids, _ = nearest_data
    response = postgres_client.get(NEAREST, params=nearest_params(ids))
    assert response.status_code == 401


def test_nearest_warehouses_reject_missing_or_inactive_product(
    postgres_client, postgres_session, nearest_data
):
    ids, auth = nearest_data
    for product_id in (ids["inactive"], 999_999):
        response = postgres_client.get(
            NEAREST, headers=auth["client"], params=nearest_params(ids, product_id=product_id)
        )
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "PRODUCT_NOT_FOUND"
        assert "warehouses" not in response.text
    # Read-only: ranking leaves stock and request history untouched.
    assert postgres_session.scalar(select(func.count()).select_from(PurchaseRequest)) == 0


@pytest.mark.parametrize(
    "params",
    [
        {"quantity": 0},
        {"quantity": 2_147_483_648},
        {"product_id": 0},
        {"product_id": "abc"},
        {"latitude": 91},
        {"latitude": "-90.1"},
        {"longitude": 181},
        {"longitude": "abc"},
        {"latitude": "nan"},
    ],
)
def test_nearest_warehouses_validate_scalar_query_bounds(postgres_client, nearest_data, params):
    ids, auth = nearest_data
    response = postgres_client.get(
        NEAREST, headers=auth["client"], params=nearest_params(ids, **params)
    )
    assert response.status_code == 422


@pytest.mark.parametrize("extra", [("product_id", "1"), ("unknown", "1")])
def test_nearest_warehouses_reject_duplicate_and_unknown_query(
    postgres_client, nearest_data, extra
):
    ids, auth = nearest_data
    params = list(nearest_params(ids).items()) + [extra]
    response = postgres_client.get(NEAREST, headers=auth["client"], params=params)
    assert response.status_code == 422


def test_nearest_warehouses_reject_missing_query_fields(postgres_client, nearest_data):
    ids, auth = nearest_data
    for missing in ("product_id", "quantity", "latitude", "longitude"):
        params = nearest_params(ids)
        params.pop(missing)
        assert (
            postgres_client.get(NEAREST, headers=auth["client"], params=params).status_code == 422
        )
