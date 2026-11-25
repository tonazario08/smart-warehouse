"""Operational reviewer decisions remain distinct from model output."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.config import get_settings
from tests.postgres.test_operational_anomaly_worker import (
    URL,
    _approved_files,
    _fulfill,
    worker,
)
from tests.postgres.test_operational_anomaly_worker import (
    approved as _approved_fixture,
)

approved = _approved_fixture
pytestmark = pytest.mark.postgres


def test_review_flagged_commit_and_reload(approved, postgres_client, postgres_url, tmp_path):
    ids, headers, path = approved
    fulfillment = _fulfill(postgres_client, path, headers)
    instant = datetime.fromisoformat(fulfillment["fulfilled_at"]).astimezone(UTC)
    files, _ = _approved_files(tmp_path, ids, instant, boundary=False)
    worker(postgres_url, OPERATIONAL_ANOMALY_ALLOW_SYNTHETIC_TEST="true", **files)
    app_settings = postgres_client.app.dependency_overrides[get_settings]
    allowed = app_settings().model_copy(update={"operational_anomaly_allow_synthetic_test": True})
    postgres_client.app.dependency_overrides[get_settings] = lambda: allowed
    route = f"{URL}/{fulfillment['transaction_id']}"
    result = postgres_client.get(route, headers=headers["warehouse"]).json()
    assert result["state"] == "flagged"
    history = postgres_client.get(route + "/reviews", headers=headers["warehouse"])
    assert history.status_code == 200, history.json()
    assert history.json()["current_version"] == 0
    body = {"expected_version": 0, "decision": "legitimate", "note": "  Có phiếu đối chiếu.  "}
    key = str(uuid4())

    def review(role="warehouse", token=key, **updates):
        return postgres_client.patch(
            route + "/review",
            headers=headers[role] | {"Idempotency-Key": token},
            json=body | updates,
        )

    first = review()
    assert first.status_code == 200, first.json()
    assert first.json()["version"] == 1
    assert first.json()["actor_id"] == ids["warehouse"]
    assert first.json()["note"] == "Có phiếu đối chiếu."
    assert first.json()["reviewed_at"]
    assert review().json() == first.json()
    assert review(note="abc").status_code == 409
    assert review("admin", str(uuid4())).status_code == 409
    assert review("client").status_code == 403
    assert postgres_client.get(route + "/reviews", headers=headers["client"]).status_code == 403
    assert postgres_client.get(route + "/reviews").status_code == 401
    assert review("admin", str(uuid4()), expected_version=1, note=" ").status_code == 422
    second = review("admin", str(uuid4()), expected_version=1, decision="insufficient_evidence")
    assert second.status_code == 200, second.json()
    latest = postgres_client.get(route + "/reviews?page_size=1", headers=headers["admin"]).json()
    assert latest["total"] == latest["current_version"] == 2
    assert latest["items"] == [second.json()]
    older = postgres_client.get(
        route + "/reviews?page=2&page_size=1", headers=headers["admin"]
    ).json()
    assert older["items"] == [first.json()]
    assert postgres_client.get(route, headers=headers["warehouse"]).json() == result
    postgres_client.app.dependency_overrides[get_settings] = app_settings
    assert postgres_client.get(route + "/reviews", headers=headers["admin"]).status_code == 404
    assert review().status_code == 404


def test_unscored_cannot_be_reviewed(approved, postgres_client, postgres_url):
    _, headers, path = approved
    fulfillment = _fulfill(postgres_client, path, headers)
    route = f"{URL}/{fulfillment['transaction_id']}"
    for state in ("pending", "unavailable"):
        assert postgres_client.get(route, headers=headers["admin"]).json()["state"] == state
        assert postgres_client.get(route + "/reviews", headers=headers["admin"]).status_code == 404
        assert (
            postgres_client.patch(
                route + "/review",
                headers=headers["warehouse"] | {"Idempotency-Key": str(uuid4())},
                json={"expected_version": 0, "decision": "legitimate", "note": "Không đủ dữ liệu."},
            ).status_code
            == 404
        )
        if state == "pending":
            worker(postgres_url)


def test_concurrent_review_and_source_drift(
    approved, postgres_client, postgres_session, postgres_engine, postgres_url, tmp_path
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from sqlalchemy import func, select
    from sqlalchemy.orm import Session

    from app.anomalies.operational_models import OperationalAnomalyReview
    from app.anomalies.operational_reviews import ReviewRequest, record
    from app.core.config import Settings
    from app.core.errors import DomainError
    from app.models import Outbound, PurchaseRequest, User

    ids, headers, path = approved
    fulfillment = _fulfill(postgres_client, path, headers)
    transaction_id = fulfillment["transaction_id"]
    instant = datetime.fromisoformat(fulfillment["fulfilled_at"]).astimezone(UTC)
    files, _ = _approved_files(tmp_path, ids, instant, boundary=False)
    worker(postgres_url, OPERATIONAL_ANOMALY_ALLOW_SYNTHETIC_TEST="true", **files)
    allowed = Settings.model_validate(
        postgres_client.app.dependency_overrides[get_settings]().model_dump()
        | {"operational_anomaly_allow_synthetic_test": True}
    )
    postgres_client.app.dependency_overrides[get_settings] = lambda: allowed
    ready = Barrier(2, timeout=10)

    def race(role):
        with Session(postgres_engine) as session:
            actor = session.get(User, ids[role])
            ready.wait()
            try:
                return record(
                    session,
                    allowed,
                    actor,
                    transaction_id,
                    uuid4(),
                    ReviewRequest(
                        expected_version=0,
                        decision="confirmed_business_issue",
                        note="Ghi nhận kiểm tra độc lập.",
                    ),
                ).version
            except DomainError as error:
                assert error.code == "OPERATIONAL_ANOMALY_REVIEW_CONFLICT"
                return 409

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(race, ("admin", "warehouse"))) == [1, 409]
    key = f"{URL}/{transaction_id}"
    assert postgres_client.get(key + "/reviews", headers=headers["admin"]).json()["total"] == 1
    # Commit a controlled coherent source change on the disposable DB.
    voucher = postgres_session.get(Outbound, fulfillment["outbound_id"])
    order = postgres_session.scalar(select(PurchaseRequest))
    voucher.reference = order.request_number = "PR-" + uuid4().hex
    postgres_session.commit()
    assert postgres_client.get(key + "/reviews", headers=headers["admin"]).status_code == 404
    assert (
        postgres_client.patch(
            key + "/review",
            headers=headers["admin"] | {"Idempotency-Key": str(uuid4())},
            json={"expected_version": 1, "decision": "legitimate", "note": "Đối chiếu lại."},
        ).status_code
        == 404
    )
    assert postgres_session.scalar(select(func.count()).select_from(OperationalAnomalyReview)) == 1
