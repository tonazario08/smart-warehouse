import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.anomalies.models import AnomalyAlert, AnomalyReview, AnomalyRun
from app.anomalies.service import AnomalyReviewRequest, AnomalyService
from app.core.errors import DomainError
from app.models import User, UserRole
from tests.postgres.test_anomalies_persistence import sample_run  # noqa: F401

pytestmark = pytest.mark.postgres


@pytest.fixture
def concurrent_data(postgres_engine, sample_run):  # noqa: F811
    with Session(postgres_engine) as session, session.begin():
        session.execute(text("TRUNCATE anomaly_reviews, anomaly_alerts, anomaly_runs CASCADE"))
        actors = [
            User(
                email=f"m9-race-{i}@example.test",
                password_hash="x",
                role=UserRole.ADMIN,
                is_active=True,
            )
            for i in range(2)
        ]
        session.add_all(actors)
        session.flush()
        ids = [user.id for user in actors]
    yield postgres_engine, sample_run, ids
    with Session(postgres_engine) as session, session.begin():
        session.execute(text("TRUNCATE anomaly_reviews, anomaly_alerts, anomaly_runs CASCADE"))
        session.execute(text("DELETE FROM users WHERE email LIKE 'm9-race-%@example.test'"))


def _parallel(call):
    barrier = threading.Barrier(2)

    def run(index):
        barrier.wait(timeout=15)
        return call(index)

    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(run, range(2)))


def test_concurrent_import_is_single_batch(concurrent_data):
    engine, verified, actors = concurrent_data

    def task(index):
        with Session(engine) as session, session.begin():
            return (
                AnomalyService(session, app_env="test", allow_fixture=True)
                .import_run(actors[index], verified)
                .replayed
            )

    assert sorted(_parallel(task)) == [False, True]
    with Session(engine) as session:
        assert len(session.scalars(select(AnomalyRun)).all()) == 1
        assert len(session.scalars(select(AnomalyAlert)).all()) == len(verified.payload.alerts)


def test_only_one_reviewer_wins_expected_version(concurrent_data):
    engine, verified, actors = concurrent_data
    with Session(engine) as session, session.begin():
        AnomalyService(session, app_env="test", allow_fixture=True).import_run(actors[0], verified)
        alert_id = session.scalars(select(AnomalyAlert.id)).first()

    def task(index):
        try:
            with Session(engine) as session, session.begin():
                request = AnomalyReviewRequest(
                    expected_version=1, decision="confirmed", note="review"
                )
                AnomalyService(session, app_env="test", allow_fixture=True).review_alert(
                    actors[index], alert_id, uuid4(), request
                )
            return 200
        except DomainError as exc:
            return exc.status_code

    assert sorted(_parallel(task)) == [200, 409]
    with Session(engine) as session:
        assert len(session.scalars(select(AnomalyReview)).all()) == 1
        assert session.get(AnomalyAlert, alert_id).version == 2


def test_concurrent_same_key_replays_once(concurrent_data):
    engine, verified, actors = concurrent_data
    with Session(engine) as session, session.begin():
        AnomalyService(session, app_env="test", allow_fixture=True).import_run(actors[0], verified)
        alert_id = session.scalars(select(AnomalyAlert.id)).first()
    key = uuid4()

    def task(index):
        with Session(engine) as session, session.begin():
            request = AnomalyReviewRequest(expected_version=1, decision="confirmed", note="review")
            return (
                AnomalyService(session, app_env="test", allow_fixture=True)
                .review_alert(actors[0], alert_id, key, request)
                .replayed
            )

    assert sorted(_parallel(task)) == [False, True]
    with Session(engine) as session:
        assert len(session.scalars(select(AnomalyReview)).all()) == 1
