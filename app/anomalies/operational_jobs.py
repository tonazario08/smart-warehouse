"""PostgreSQL lease/ownership operations for the independent operational anomaly queue."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.anomalies.operational_models import OperationalAnomalyJob

MAX_ATTEMPTS = 5
LEASE_SECONDS = 300
BACKOFF_BASE_SECONDS = 30
MAX_BACKOFF_SECONDS = 600


@dataclass(frozen=True)
class JobClaim:
    id: int
    transaction_id: int
    outbound_id: int
    purchase_request_id: int
    warehouse_id: int
    product_id: int
    quantity: int
    unit: str
    occurred_at: datetime
    source_fingerprint: str
    attempts: int
    claim_token: UUID
    artifact_digest: str | None
    coverage_digest: str | None


def enqueue(
    session: Session,
    *,
    transaction_id: int,
    outbound_id: int,
    purchase_request_id: int,
    warehouse_id: int,
    product_id: int,
    quantity: int,
    unit: str,
    occurred_at: datetime,
    source_fingerprint: str,
) -> bool:
    """Add a job in the fulfillment transaction, without taking ownership of commit."""
    insert = sqlite_insert if session.get_bind().dialect.name == "sqlite" else pg_insert
    statement = insert(OperationalAnomalyJob).values(
        transaction_id=transaction_id,
        outbound_id=outbound_id,
        purchase_request_id=purchase_request_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        quantity=quantity,
        unit=unit,
        occurred_at=occurred_at,
        source_fingerprint=source_fingerprint,
    )
    statement = statement.on_conflict_do_nothing(index_elements=["transaction_id"])
    return session.scalar(statement.returning(OperationalAnomalyJob.id)) is not None


def claim_next(
    session: Session, expected_digest: str | None, coverage_digest: str | None = None
) -> JobClaim | None:
    session.execute(
        text("""
            WITH exhausted AS (
                SELECT id FROM operational_anomaly_jobs
                WHERE status = 'running' AND attempts >= :max_attempts
                  AND lease_expires_at <= clock_timestamp()
                FOR UPDATE SKIP LOCKED
            )
            UPDATE operational_anomaly_jobs AS job
            SET status = 'failed', claim_token = NULL, lease_expires_at = NULL,
                last_error_code = 'LEASE_EXPIRED', completed_at = clock_timestamp()
            FROM exhausted WHERE job.id = exhausted.id
        """),
        {"max_attempts": MAX_ATTEMPTS},
    )
    row = (
        session.execute(
            text("""
            WITH next_job AS (
                SELECT id FROM operational_anomaly_jobs
                WHERE attempts < :max_attempts AND (
                    (status = 'queued' AND available_at <= clock_timestamp())
                    OR (status = 'running' AND lease_expires_at <= clock_timestamp())
                )
                ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED
            )
            UPDATE operational_anomaly_jobs AS job
            SET status = 'running', attempts = job.attempts + 1, claim_token = :token,
                lease_expires_at = clock_timestamp() + make_interval(secs => :lease_seconds),
                artifact_digest = CASE WHEN job.attempts = 0 THEN :digest
                                       ELSE job.artifact_digest END,
                coverage_digest = CASE WHEN job.attempts = 0 THEN :coverage_digest
                                       ELSE job.coverage_digest END
            FROM next_job WHERE job.id = next_job.id
            RETURNING job.id, job.transaction_id, job.outbound_id, job.purchase_request_id,
                      job.warehouse_id, job.product_id, job.quantity, job.unit, job.occurred_at,
                      job.source_fingerprint, job.attempts, job.claim_token,
                      job.artifact_digest, job.coverage_digest
        """),
            {
                "max_attempts": MAX_ATTEMPTS,
                "token": uuid4(),
                "lease_seconds": LEASE_SECONDS,
                "digest": expected_digest,
                "coverage_digest": coverage_digest,
            },
        )
        .mappings()
        .one_or_none()
    )
    return JobClaim(**row) if row is not None else None


def _owned_update(session: Session, claim: JobClaim):
    job = OperationalAnomalyJob
    ownership = (
        job.id == claim.id,
        job.status == "running",
        job.claim_token == claim.claim_token,
        job.lease_expires_at > func.clock_timestamp(),
    )
    # Never wait behind another lock, as the lease may expire during that wait.
    locked = session.scalar(select(job.id).where(*ownership).with_for_update(skip_locked=True))
    if locked is None:
        return None
    return (
        update(job).where(*ownership).execution_options(synchronize_session=False).returning(job.id)
    )


def complete(session: Session, claim: JobClaim, result: dict) -> bool:
    owned = _owned_update(session, claim)
    if owned is None:
        return False
    statement = owned.values(
        status="succeeded",
        claim_token=None,
        lease_expires_at=None,
        result=result,
        last_error_code=None,
        completed_at=func.clock_timestamp(),
    )
    return session.scalar(statement) is not None


def fail(session: Session, claim: JobClaim, error: str, *, retryable: bool = True) -> bool:
    retry = retryable and claim.attempts < MAX_ATTEMPTS
    values = {
        "status": "queued" if retry else "failed",
        "claim_token": None,
        "lease_expires_at": None,
        "last_error_code": error,
        "completed_at": None if retry else func.clock_timestamp(),
    }
    if retry:
        delay = min(MAX_BACKOFF_SECONDS, BACKOFF_BASE_SECONDS * 2 ** (claim.attempts - 1))
        # Positional arguments to make_interval: years, months, weeks, days, hours, mins, secs.
        values["available_at"] = func.clock_timestamp() + func.make_interval(
            0, 0, 0, 0, 0, 0, delay
        )
    owned = _owned_update(session, claim)
    return owned is not None and session.scalar(owned.values(**values)) is not None
