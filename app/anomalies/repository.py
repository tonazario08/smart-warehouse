"""Transactional primitives for anomaly imports and reviews."""

import hashlib

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from app.anomalies.models import AnomalyAlert, AnomalyReview, AnomalyRun
from app.models.domain import User


def lock_actor(session, actor_id):
    return session.scalar(
        select(User)
        .where(User.id == actor_id)
        .with_for_update(read=True)
        .execution_options(populate_existing=True)
    )


def lock_key(session, actor_id, key):
    digest = hashlib.sha256(f"anomaly-review:{actor_id}:{key}".encode()).digest()
    lock_id = int.from_bytes(digest[:8], "big", signed=True)
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_id})


def insert_run(session, values):
    return session.scalar(
        insert(AnomalyRun)
        .values(**values)
        .on_conflict_do_nothing(index_elements=[AnomalyRun.run_id])
        .returning(AnomalyRun.run_id)
    )


def get_run(session, run_id):
    return session.get(AnomalyRun, run_id)


def get_review(session, actor_id, key):
    return session.scalar(
        select(AnomalyReview).where(
            AnomalyReview.actor_user_id == actor_id, AnomalyReview.idempotency_key == key
        )
    )


def lock_alert(session, alert_id):
    return session.scalar(
        select(AnomalyAlert)
        .where(AnomalyAlert.id == alert_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
