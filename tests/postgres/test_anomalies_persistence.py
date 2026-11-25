from uuid import uuid4

import pytest
from sqlalchemy import select, text

from app.anomalies.catalog import publish_run, verify_run
from app.anomalies.models import AnomalyAlert, AnomalyReview, AnomalyRun
from app.anomalies.scoring import fit_and_score
from app.anomalies.service import AnomalyReviewRequest, AnomalyService
from app.core.errors import DomainError
from app.models import User, UserRole
from tests.anomalies_helpers import snapshot

pytestmark = pytest.mark.postgres


@pytest.fixture
def sample_run(tmp_path):
    snap = snapshot(holdout_offset=1000).model_copy(
        update={
            "source_hashes": {
                name: "b" * 64
                for name in ("source", "records.jsonl", "observations.jsonl", "quality.json")
            }
        }
    )
    result = fit_and_score(snap)
    run_id = publish_run(result, tmp_path)
    return verify_run(tmp_path, run_id)


@pytest.fixture
def setup(postgres_session, sample_run):
    session = postgres_session
    session.execute(text("TRUNCATE anomaly_reviews, anomaly_alerts, anomaly_runs CASCADE"))
    actor = User(
        email="anomaly@example.test", password_hash="x", role=UserRole.ADMIN, is_active=True
    )
    session.add(actor)
    session.flush()
    service = AnomalyService(session, app_env="test", allow_fixture=True)
    yield session, service, actor.id, sample_run
    session.rollback()
    session.execute(text("TRUNCATE anomaly_reviews, anomaly_alerts, anomaly_runs CASCADE"))
    session.commit()


def test_import_is_atomic_and_replay_safe(setup):
    session, service, actor, verified = setup
    first = service.import_run(actor, verified)
    again = service.import_run(actor, verified)
    assert not first.replayed and again.replayed
    assert (
        session.scalar(select(AnomalyRun).where(AnomalyRun.run_id == verified.run_id)) is not None
    )
    assert len(session.scalars(select(AnomalyAlert)).all()) == len(verified.payload.alerts)


def test_review_replay_and_version_conflict(setup):
    session, service, actor, verified = setup
    service.import_run(actor, verified)
    alert = session.scalars(select(AnomalyAlert)).first()
    key = uuid4()
    request = AnomalyReviewRequest(expected_version=1, decision="confirmed", note="fixture")
    first = service.review_alert(actor, alert.id, key, request)
    replay = service.review_alert(actor, alert.id, key, request)
    assert (first.version, replay.version, replay.replayed) == (2, 2, True)
    with pytest.raises(DomainError) as error:
        service.review_alert(actor, alert.id, uuid4(), request)
    assert error.value.status_code == 409
    assert len(session.scalars(select(AnomalyReview)).all()) == 1


def test_client_and_inactive_actor_denied(setup):
    session, service, _, verified = setup
    client = User(
        email="client-anomaly@example.test", password_hash="x", role=UserRole.CLIENT, is_active=True
    )
    session.add(client)
    session.flush()
    with pytest.raises(DomainError) as error:
        service.import_run(client.id, verified)
    assert error.value.status_code == 403


def test_import_fault_rolls_back_run(setup, monkeypatch):
    from app.anomalies import repository

    session, service, actor, verified = setup
    insert = repository.insert_run

    def fail_after_insert(*args, **kwargs):
        insert(*args, **kwargs)
        raise RuntimeError("injected failure")

    monkeypatch.setattr(repository, "insert_run", fail_after_insert)
    with pytest.raises(RuntimeError):
        service.import_run(actor, verified)
    assert session.get(AnomalyRun, verified.run_id) is None
    assert not session.scalars(select(AnomalyAlert)).all()
