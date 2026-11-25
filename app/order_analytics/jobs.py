"""PostgreSQL job claims and ownership checks for background order analytics."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

MAX_ATTEMPTS = 5
LEASE_SECONDS = 300
BACKOFF_BASE_SECONDS = 30
MAX_BACKOFF_SECONDS = 600
MAX_TRANSACTION_ATTEMPTS = 3


@dataclass(frozen=True)
class JobClaim:
    id: int
    purchase_request_id: int
    warehouse_id: int
    product_id: int
    attempts: int
    claim_token: UUID

    def ownership(self):
        return {"job_id": self.id, "claim_token": self.claim_token}


class StateConflict(Exception):
    """A competing catalog-state write requires replaying the transaction."""


def claim_next(session: Session) -> JobClaim | None:
    # Do not wait behind another worker holding a valid claim guard.
    session.execute(
        text("""
            WITH expired AS (
                SELECT id FROM order_analytics_jobs
                WHERE status = 'running' AND lease_expires_at <= clock_timestamp()
                  AND attempts >= :max_attempts
                FOR UPDATE SKIP LOCKED
            )
            UPDATE order_analytics_jobs AS job
            SET status = 'failed', last_error_code = 'LEASE_EXPIRED',
                claim_token = NULL, lease_expires_at = NULL,
                completed_at = clock_timestamp(), updated_at = clock_timestamp()
            FROM expired WHERE job.id = expired.id
        """),
        {"max_attempts": MAX_ATTEMPTS},
    )
    row = session.execute(
        text("""
            WITH next_job AS (
                SELECT id FROM order_analytics_jobs
                WHERE attempts < :max_attempts
                  AND (
                    (status = 'queued' AND available_at <= clock_timestamp())
                    OR (status = 'running' AND lease_expires_at <= clock_timestamp())
                  )
                ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED
            )
            UPDATE order_analytics_jobs AS job
            SET status = 'running', attempts = attempts + 1, claim_token = :claim_token,
                lease_expires_at = clock_timestamp() + make_interval(secs => :lease_seconds),
                updated_at = clock_timestamp(), completed_at = NULL
            FROM next_job WHERE job.id = next_job.id
            RETURNING job.id, job.purchase_request_id, job.warehouse_id, job.product_id,
                      job.attempts, job.claim_token
        """),
        {"max_attempts": MAX_ATTEMPTS, "claim_token": uuid4(), "lease_seconds": LEASE_SECONDS},
    ).mappings().one_or_none()
    return JobClaim(**row) if row is not None else None


def guard_claim(session: Session, claim: JobClaim) -> bool:
    result = session.execute(
        text("""
            UPDATE order_analytics_jobs
            SET updated_at = clock_timestamp()
            WHERE id = :job_id AND claim_token = :claim_token
              AND status = 'running' AND lease_expires_at > clock_timestamp()
        """),
        claim.ownership(),
    )
    return result.rowcount == 1


def finish_guarded(session: Session, claim: JobClaim, error: str | None) -> None:
    """Update the job already locked by guard_claim in this same transaction."""
    retry = error is not None and claim.attempts < MAX_ATTEMPTS
    status = "queued" if retry else "failed" if error else "succeeded"
    delay = min(MAX_BACKOFF_SECONDS, BACKOFF_BASE_SECONDS * 2 ** (claim.attempts - 1))
    result = session.execute(
        text("""
            UPDATE order_analytics_jobs
            SET status = :status, last_error_code = :error, claim_token = NULL,
                lease_expires_at = NULL,
                available_at = CASE WHEN CAST(:retry AS boolean)
                    THEN clock_timestamp() + make_interval(secs => :delay) ELSE available_at END,
                completed_at = CASE WHEN CAST(:retry AS boolean)
                    THEN NULL ELSE clock_timestamp() END,
                updated_at = clock_timestamp()
            WHERE id = :job_id AND claim_token = :claim_token
        """),
        {**claim.ownership(), "status": status, "error": error, "retry": retry, "delay": delay},
    )
    if result.rowcount != 1:
        raise StateConflict
