from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.anomalies.models import AnomalyAlert
from app.anomalies.service import AnomalyService
from app.auth.security import create_access_token
from app.core.config import Settings
from app.db.session import get_session
from app.main import create_app
from app.models import (
    Category,
    Inbound,
    Product,
    Stock,
    StockTransaction,
    TransactionType,
    User,
    UserRole,
    Warehouse,
)
from tests.postgres.test_anomalies_persistence import sample_run  # noqa: F401

pytestmark = pytest.mark.postgres


@pytest.fixture
def environment(postgres_session, postgres_url, sample_run):  # noqa: F811
    session = postgres_session
    session.execute(text("TRUNCATE anomaly_reviews, anomaly_alerts, anomaly_runs CASCADE"))
    users = [
        User(
            email=f"m9-api-{role.value}@example.test", password_hash="x", role=role, is_active=True
        )
        for role in UserRole
    ]
    session.add_all(users)
    session.flush()
    ids = {u.role.value: u.id for u in users}
    category = Category(name="M9 fixture category")
    product = Product(sku="M9-FIXTURE", name="Fixture", category=category, unit="each")
    warehouse = Warehouse(code="M9-FIXTURE", name="M9 fixture warehouse", address="Fixture")
    session.add_all([product, warehouse])
    session.flush()
    inbound = Inbound(
        warehouse_id=warehouse.id,
        product_id=product.id,
        quantity=7,
        created_by_id=ids["warehouse"],
        reference="M9-FIXTURE",
    )
    session.add(inbound)
    session.flush()
    session.add_all(
        [
            Stock(warehouse_id=warehouse.id, product_id=product.id, quantity=7),
            StockTransaction(
                transaction_type=TransactionType.INBOUND,
                warehouse_id=warehouse.id,
                product_id=product.id,
                quantity=7,
                inbound_id=inbound.id,
                created_by_id=ids["warehouse"],
            ),
        ]
    )
    service = AnomalyService(session, app_env="test", allow_fixture=True)
    service.import_run(ids["admin"], sample_run)
    alert_id = session.scalars(select(AnomalyAlert.id).order_by(AnomalyAlert.id)).first()
    session.commit()
    settings = Settings(
        app_env="test",
        database_url=postgres_url,
        jwt_secret_key="test-only-jwt-secret-with-at-least-32-characters",
        anomalies_allow_fixture=True,
        _env_file=None,
    )
    app = create_app(settings)
    app.dependency_overrides[get_session] = lambda: session
    headers = {
        role: {"Authorization": f"Bearer {create_access_token(user_id, settings)}"}
        for role, user_id in ids.items()
    }
    with TestClient(app) as client:
        yield client, session, settings, headers, alert_id, ids
    session.rollback()
    session.execute(text("TRUNCATE anomaly_reviews, anomaly_alerts, anomaly_runs CASCADE"))
    session.commit()


def _snapshot(session):
    return tuple(
        tuple(session.execute(text(f"SELECT * FROM {table} ORDER BY id")).all())
        for table in ("stocks", "transactions")
    )


def test_real_auth_rbac_and_fixture_hidden(environment):
    client, session, settings, headers, alert_id, _ = environment
    root = "/api/v1/anomalies"
    assert client.get(root + "/status").status_code == 401
    for role in ("admin", "warehouse"):
        assert (
            client.get(root + "/status", headers=headers[role]).json()["dataset_class"] == "fixture"
        )
        assert client.get(root + "/" + alert_id, headers=headers[role]).status_code == 200
    for suffix in ("/status", "", "/" + alert_id, "/" + alert_id + "/reviews"):
        assert client.get(root + suffix, headers=headers["client"]).status_code == 403
    assert (
        client.patch(
            root + "/" + alert_id + "/review",
            headers={**headers["client"], "Idempotency-Key": str(uuid4())},
            json={"expected_version": 1, "decision": "confirmed", "note": "x"},
        ).status_code
        == 403
    )
    assert client.get(root + "/alv1-" + "0" * 64, headers=headers["admin"]).status_code == 404
    hidden = create_app(settings.model_copy(update={"anomalies_allow_fixture": False}))
    hidden.dependency_overrides[get_session] = lambda: session
    with TestClient(hidden) as disabled:
        assert (
            disabled.get(root + "/status", headers=headers["admin"]).json()["state"]
            == "unavailable"
        )
        assert disabled.get(root, headers=headers["admin"]).json()["items"] == []
        assert disabled.get(root + "/" + alert_id, headers=headers["admin"]).status_code == 404


def test_review_replay_conflict_and_stock_unchanged(environment):
    client, session, _, headers, alert_id, _ = environment
    root = "/api/v1/anomalies"
    before = _snapshot(session)
    assert len(before[0]) >= 1 and len(before[1]) >= 1
    detail = client.get(root + "/" + alert_id, headers=headers["warehouse"])
    assert detail.status_code == 200
    data = detail.json()
    assert data["run"]["real_precision_recall"] == "NOT VERIFIED"
    assert data["run"]["dataset_class"] == "fixture"
    assert "event_id" not in detail.text and '"labels"' not in detail.text
    key = str(uuid4())
    url = root + "/" + alert_id + "/review"
    review_headers = {**headers["warehouse"], "Idempotency-Key": key}
    body = {"expected_version": 1, "decision": "confirmed", "note": "synthetic"}
    result = client.patch(url, headers=review_headers, json=body)
    assert result.status_code == 200 and result.json()["version"] == 2
    replay = client.patch(url, headers=review_headers, json=body)
    assert replay.status_code == 200 and replay.json()["replayed"] is True
    assert (
        client.patch(
            url, headers={**review_headers, "Idempotency-Key": str(uuid4())}, json=body
        ).status_code
        == 409
    )
    assert (
        client.patch(url, headers=review_headers, json={**body, "note": "changed"}).status_code
        == 409
    )
    assert (
        client.patch(
            url, headers={**review_headers, "Idempotency-Key": "bad"}, json=body
        ).status_code
        == 422
    )
    assert (
        client.patch(
            url,
            headers={**review_headers, "Idempotency-Key": str(uuid4())},
            json={**body, "note": ""},
        ).status_code
        == 422
    )
    history = client.get(root + "/" + alert_id + "/reviews", headers=headers["admin"]).json()
    assert len(history["items"]) == 1
    assert client.get(root + "?status=confirmed", headers=headers["admin"]).json()["total"] == 1
    assert _snapshot(session) == before


def test_existing_token_role_and_active_state_are_refreshed(environment, postgres_engine):
    client, session, _, headers, _, ids = environment
    root = "/api/v1/anomalies/status"
    assert client.get(root, headers=headers["admin"]).status_code == 200
    with Session(postgres_engine) as other, other.begin():
        user = other.get(User, ids["admin"])
        user.role = UserRole.CLIENT
    assert client.get(root, headers=headers["admin"]).status_code == 403
    with Session(postgres_engine) as other, other.begin():
        user = other.get(User, ids["admin"])
        user.is_active = False
    assert client.get(root, headers=headers["admin"]).status_code == 401
