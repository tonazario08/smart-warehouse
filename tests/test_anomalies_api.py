import hashlib
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.analytics.export import canonical_json
from app.anomalies import service
from app.anomalies.catalog import PublicAlert
from app.anomalies.models import AnomalyAlert, AnomalyRun
from app.auth.security import create_access_token
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_session
from app.main import create_app
from app.models import User, UserRole


@pytest.fixture
def client_and_headers(unit_settings):
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        users = [
            User(
                email=f"api-{role.value}@example.test", password_hash="x", role=role, is_active=True
            )
            for role in UserRole
        ]
        session.add_all(users)
        session.commit()
        app = create_app(unit_settings)
        app.dependency_overrides[get_session] = lambda: session
        headers = {
            user.role.value: {
                "Authorization": f"Bearer {create_access_token(user.id, unit_settings)}"
            }
            for user in users
        }
        with TestClient(app) as client:
            yield client, headers, session, users
    engine.dispose()


def test_auth_and_default_fixture_hidden(client_and_headers):
    client, headers, _, _ = client_and_headers
    root = "/api/v1/anomalies"
    assert client.get(root + "/status").status_code == 401
    for path in ("/status", "", "/alv1-" + "a" * 64, "/alv1-" + "a" * 64 + "/reviews"):
        assert client.get(root + path, headers=headers["client"]).status_code == 403
    assert client.get(root + "/status", headers=headers["admin"]).json()["state"] == "unavailable"
    assert client.get(root, headers=headers["warehouse"]).json()["items"] == []
    assert client.get(root + "/alv1-" + "a" * 64, headers=headers["admin"]).status_code == 404


def test_invalid_filters_and_review_input_are_rejected(client_and_headers):
    client, headers, _, _ = client_and_headers
    root = "/api/v1/anomalies"
    assert client.get(root + "?page=0", headers=headers["admin"]).status_code == 422
    assert client.get(root + "?status=other", headers=headers["admin"]).status_code == 422
    assert (
        client.patch(
            root + "/alv1-" + "a" * 64 + "/review", headers=headers["client"], json={}
        ).status_code
        == 403
    )


def test_old_token_observes_current_role_and_activity(client_and_headers):
    from sqlalchemy import update

    client, headers, session, users = client_and_headers
    admin = next(u for u in users if u.role == UserRole.ADMIN)
    assert client.get("/api/v1/anomalies/status", headers=headers["admin"]).status_code == 200
    session.execute(
        update(User).where(User.id == admin.id).values(role=UserRole.CLIENT),
        execution_options={"synchronize_session": False},
    )
    session.commit()
    assert client.get("/api/v1/anomalies/status", headers=headers["admin"]).status_code == 403
    session.execute(
        update(User).where(User.id == admin.id).values(is_active=False),
        execution_options={"synchronize_session": False},
    )
    session.commit()
    assert client.get("/api/v1/anomalies/status", headers=headers["admin"]).status_code == 401


def test_list_checks_each_run_once_and_rejects_a_corrupted_alert(client_and_headers, monkeypatch):
    client, headers, session, users = client_and_headers
    settings = client.app.dependency_overrides[get_settings]().model_copy(
        update={"anomalies_allow_fixture": True}
    )
    client.app.dependency_overrides[get_settings] = lambda: settings
    admin = next(user for user in users if user.role == UserRole.ADMIN)
    run_id = "arv1-" + "a" * 64
    session.add(
        AnomalyRun(
            run_id=run_id,
            digest="a" * 64,
            payload={},
            imported_at=datetime.now(UTC),
            imported_by=admin.id,
        )
    )
    now = datetime(2026, 11, 18, tzinfo=UTC)
    alerts = tuple(
        PublicAlert.model_validate(
            {
                "source_record_key": "aek1-" + key * 64,
                "occurred_at": now,
                "partition": "final_holdout",
                "score": 0.8,
                "features": (1.0,) * 6,
                "explanation": {
                    "state": "unavailable",
                    "reason": "EXPLAINER_MISSING",
                    "base_value": None,
                    "contributions": None,
                    "residual": None,
                },
            }
        )
        for key in ("b", "c")
    )
    rows = []
    for alert in alerts:
        identity = hashlib.sha256(canonical_json([run_id, alert.source_record_key])).hexdigest()
        rows.append(
            AnomalyAlert(
                id="alv1-" + identity,
                run_id=run_id,
                source_record_key=alert.source_record_key,
                payload=alert.model_dump(mode="json"),
                review_status="new",
                version=1,
            )
        )
    session.add_all(rows)
    session.commit()

    checked = []

    def check_payload(run):
        checked.append(run.run_id)
        return SimpleNamespace(alerts=alerts, threshold=0.6)

    monkeypatch.setattr(service, "_checked_payload", check_payload)
    response = client.get("/api/v1/anomalies", headers=headers["admin"])
    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert checked == [run_id]

    rows[-1].payload = {**rows[-1].payload, "score": 0.9}
    session.commit()
    response = client.get("/api/v1/anomalies", headers=headers["admin"])
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ANOMALY_CATALOG_INVALID"
    assert checked == [run_id, run_id]
