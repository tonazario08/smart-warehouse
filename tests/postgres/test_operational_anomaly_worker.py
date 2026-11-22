"""Approved synthetic integration only; real committed orders and separate scorer process."""

import hashlib
import json
import math
import os
import subprocess
import sys
from datetime import UTC, datetime, time, timedelta
from uuid import uuid4

import numpy as np
import pytest
from sklearn.ensemble import IsolationForest
from sqlalchemy import func, select, text

from app.anomalies.operational_artifact import export_sklearn
from app.anomalies.operational_features import coverage_events_digest
from app.anomalies.operational_models import OperationalAnomalyJob
from app.core.config import Settings, get_settings
from app.models import Outbound, PurchaseRequest, Stock
from app.purchase_requests import service
from tests.postgres.test_purchase_requests_api import (
    BASE,
    create,
    effects,
    headers_for,
    seed_purchase,
)

pytestmark = pytest.mark.postgres
URL = "/api/v1/operational-anomalies"


@pytest.fixture
def approved(postgres_session, postgres_client, unit_settings):
    ids = seed_purchase(postgres_session)
    headers = {
        role: headers_for(ids, role, unit_settings) for role in ("admin", "client", "warehouse")
    }
    reply = create(postgres_client, ids, headers["client"], uuid4())
    assert reply.status_code == 201
    order = reply.json()["id"]
    path = f"{BASE}/{order}"
    assert (
        postgres_client.post(path + "/approve", headers=headers["admin"], json={}).status_code
        == 200
    )
    return ids, headers, path


def worker(database_url, **settings):
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("OPERATIONAL_ANOMALY_")
    }
    env |= {
        "DATABASE_URL": database_url,
        "APP_ENV": "test",
        "JWT_SECRET_KEY": "warehouse-smoke-isolated-sufficiently-long",
        **settings,
    }
    subprocess.run(
        [sys.executable, "-m", "app.anomalies.operational_worker", "--once"],
        env=env,
        check=True,
        capture_output=True,
        timeout=90,
    )


def _fulfill(client, path, headers):
    reply = client.post(path + "/fulfill", headers=headers["warehouse"], json={})
    assert reply.status_code == 200, reply.json()
    return reply.json()["fulfillment"]


def test_atomic_enqueue_after_commit_replay_and_no_model(
    approved, postgres_client, postgres_session, postgres_engine, postgres_url, monkeypatch
):
    _, headers, path = approved
    assert postgres_session.scalar(select(func.count()).select_from(OperationalAnomalyJob)) == 0
    postgres_session.rollback()
    original = service.enqueue
    before = effects(postgres_session)
    postgres_session.rollback()

    def abort(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("controlled enqueue failure")

    with monkeypatch.context() as scoped:
        scoped.setattr(service, "enqueue", abort)
        with pytest.raises(RuntimeError, match="controlled enqueue failure"):
            _fulfill(postgres_client, path, headers)
    assert effects(postgres_session) == before
    assert postgres_session.scalar(select(Stock.quantity)) == 10
    assert postgres_session.scalar(select(func.count()).select_from(OperationalAnomalyJob)) == 0
    postgres_session.rollback()

    def prove_invisible(*args, **kwargs):
        ret = original(*args, **kwargs)
        with postgres_engine.connect() as independent:
            assert independent.scalar(select(func.count()).select_from(OperationalAnomalyJob)) == 0
        worker(postgres_url)
        return ret

    monkeypatch.setattr(service, "enqueue", prove_invisible)
    fulfillment = _fulfill(postgres_client, path, headers)
    transaction = fulfillment["transaction_id"]
    assert _fulfill(postgres_client, path, headers) == fulfillment
    target = f"{URL}/{transaction}"
    assert postgres_client.get(target, headers=headers["admin"]).json()["state"] == "pending"
    assert postgres_client.get(target).status_code == 401
    assert postgres_client.get(target, headers=headers["client"]).status_code == 403
    before_work = effects(postgres_session)
    postgres_session.rollback()
    worker(postgres_url)
    worker(postgres_url)
    response = postgres_client.get(target, headers=headers["warehouse"]).json()
    assert response["state"] == "unavailable" and response["reason_code"] == "NO_APPROVED_MODEL"
    assert all(
        response[field] is None for field in ("score", "threshold", "base_value", "contributions")
    )
    assert (
        postgres_client.get(target + "/outbound", headers=headers["warehouse"]).status_code == 404
    )
    assert postgres_client.get(target + "/outbound", headers=headers["client"]).status_code == 403
    row = postgres_session.scalar(select(OperationalAnomalyJob))
    assert row.attempts == 1 and row.artifact_digest is None
    assert effects(postgres_session) == before_work


def _approved_files(tmp_path, ids, instant, *, boundary):
    day = instant.date()
    coverage_rows = []
    for delay in range(7, 0, -1):
        date = day - timedelta(days=delay)
        available = datetime.combine(date + timedelta(days=1), time.min, UTC)
        coverage_rows.append(
            {
                "warehouse_id": ids["source"],
                "product_id": ids["product"],
                "unit": "each",
                "day": date.isoformat(),
                "available_at": available.isoformat().replace("+00:00", "Z"),
                "complete": True,
                "events_digest": coverage_events_digest([]),
            }
        )
    coverage_data = json.dumps(
        {
            "schema_version": "b2b-outbound-coverage/1",
            "dataset_class": "synthetic_test",
            "rows": coverage_rows,
        }
    ).encode()
    training = np.random.default_rng(42).random((128, 6))
    model = IsolationForest(n_estimators=8, random_state=42).fit(training)
    vector = np.asarray(
        [[math.log1p(3), instant.hour / 23, instant.weekday() / 6, 0.0, 0.0, math.log1p(3)]]
    )
    score = float(-model.score_samples(vector)[0])
    model_data = export_sklearn(
        model,
        model_version="fixture-integration/1",
        threshold=score if boundary else score - 0.01,
        background=training[:4],
        artifact_class="synthetic_test",
        training_digest="1" * 64,
        approval_id="isolated-integration-test",
    )
    paths = {}
    for name, data in (("ARTIFACT", model_data), ("COVERAGE", coverage_data)):
        path = tmp_path / (name.lower() + ".json")
        path.write_bytes(data)
        paths[f"OPERATIONAL_ANOMALY_{name}_PATH"] = str(path)
        paths[f"OPERATIONAL_ANOMALY_{name}_SHA256"] = hashlib.sha256(data).hexdigest()
    return paths, score


@pytest.mark.parametrize(
    ("mode", "state"),
    [
        ("valid", "flagged"),
        ("threshold_tie", "normal"),
        ("synthetic_disabled", "unavailable"),
    ],
)
def test_exact_model_scoring_and_controlled_voucher(
    approved, postgres_session, postgres_client, postgres_url, tmp_path, mode, state
):
    ids, headers, path = approved
    # Shift voucher identity within this test transaction before fulfillment.
    postgres_session.execute(
        text("SELECT setval(pg_get_serial_sequence('outbounds','id'), 400, false)")
    )
    postgres_session.commit()
    fulfillment = _fulfill(postgres_client, path, headers)
    transaction, voucher = fulfillment["transaction_id"], fulfillment["outbound_id"]
    assert transaction != voucher
    instant = datetime.fromisoformat(fulfillment["fulfilled_at"]).astimezone(UTC)
    files, expected_score = _approved_files(
        tmp_path, ids, instant, boundary=mode == "threshold_tie"
    )
    before = effects(postgres_session)
    postgres_session.rollback()
    worker(
        postgres_url,
        OPERATIONAL_ANOMALY_ALLOW_SYNTHETIC_TEST=str(mode != "synthetic_disabled"),
        **files,
    )
    target = f"{URL}/{transaction}"
    if mode != "synthetic_disabled":
        assert postgres_client.get(target, headers=headers["admin"]).status_code == 404
        assert (
            postgres_client.get(target + "/outbound", headers=headers["warehouse"]).status_code
            == 404
        )
        assert postgres_client.get(URL, headers=headers["warehouse"]).json()["total"] == 0
        original_settings = postgres_client.app.dependency_overrides[get_settings]()
        allowed = Settings.model_validate(
            original_settings.model_dump() | {"operational_anomaly_allow_synthetic_test": True}
        )
        postgres_client.app.dependency_overrides[get_settings] = lambda: allowed
    result = postgres_client.get(target, headers=headers["warehouse"]).json()
    assert result["state"] == state, result
    if mode == "synthetic_disabled":
        assert result["reason_code"] == "MODEL_ARTIFACT_INVALID" and result["score"] is None
    else:
        assert (
            result["score"] == expected_score and result["model_version"] == "fixture-integration/1"
        )
    detail = postgres_client.get(target + "/outbound", headers=headers["warehouse"])
    assert postgres_client.get(target + "/outbound", headers=headers["client"]).status_code == 403
    if state == "flagged":
        assert detail.status_code == 200
        assert detail.json()["outbound_id"] == voucher
        assert detail.json()["dataset_class"] == result["dataset_class"] == "synthetic_test"
        assert detail.json()["performed_by_id"] == ids["warehouse"]
        assert detail.json()["quantity"] == 3
        assert abs(result["base_value"] + sum(result["contributions"]) - expected_score) <= 1e-8
        row = postgres_session.get(Outbound, voucher)
        request = postgres_session.scalar(select(PurchaseRequest))
        row.reference = request.request_number = "PR-" + uuid4().hex
        postgres_session.flush()
        assert (
            postgres_client.get(target + "/outbound", headers=headers["warehouse"]).status_code
            == 404
        )
        postgres_session.rollback()
    else:
        assert detail.status_code == 404
        assert result["contributions"] is None
    assert effects(postgres_session) == before
    assert postgres_session.scalar(select(Stock.quantity)) == 7
