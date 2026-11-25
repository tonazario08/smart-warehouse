"""Run the provisional analytics queue separately from the API process."""

import argparse
import logging
import time
from collections.abc import Callable

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_engine
from app.order_analytics.jobs import (
    MAX_TRANSACTION_ATTEMPTS,
    JobClaim,
    StateConflict,
    claim_next,
    finish_guarded,
    guard_claim,
)
from app.order_analytics.repository import get_order_sample, write_order_check
from app.order_analytics.rules import LABEL, RULE_ID, RULE_VERSION, check_quantity
from app.order_analytics.service import (
    ContextConflict,
    record_context_failure,
    update_forecast_context,
    update_replenishment_context,
)

LOGGER = logging.getLogger(__name__)
IDLE_SECONDS = 2
Step = Callable[[Session, JobClaim, Settings], None]


class ClaimLost(Exception):
    """The ownership token or lease is no longer valid."""


def update_order_check(session: Session, claim: JobClaim, _settings: Settings) -> None:
    sample = get_order_sample(session, claim.purchase_request_id)
    if sample is None:
        # A job pins a purchase request by FK. An absent row is not an empty history.
        raise ValueError("order unavailable")
    result = check_quantity(sample.quantity, sample.history)
    write_order_check(session, claim.purchase_request_id, **result.as_fields())


def _record_failure(session: Session, claim: JobClaim, code: str) -> None:
    if code != "ORDER_CHECK_FAILED":
        record_context_failure(session, claim, code)
        return
    write_order_check(
        session,
        claim.purchase_request_id,
        status="failed",
        flagged=None,
        reason_code=code,
        rule_id=RULE_ID,
        rule_version=RULE_VERSION,
        label=LABEL,
        sample_count=0,
        median=None,
        mad=None,
        score=None,
    )


def _guarded(engine, claim: JobClaim, action: Callable[[Session], None]) -> None:
    for attempt in range(MAX_TRANSACTION_ATTEMPTS):
        try:
            # Fresh connection transaction and session per attempt: guard, reads, writes,
            # and commit either all survive together or are all discarded.
            with Session(engine.execution_options(isolation_level="REPEATABLE READ")) as session:
                with session.begin():
                    if not guard_claim(session, claim):
                        raise ClaimLost
                    action(session)
            return
        except (StateConflict, ContextConflict):
            if attempt == MAX_TRANSACTION_ATTEMPTS - 1:
                raise
        except DBAPIError as error:
            if (
                getattr(error.orig, "sqlstate", None) != "40001"
                or error.connection_invalidated
                or attempt == MAX_TRANSACTION_ATTEMPTS - 1
            ):
                raise


def run_once(engine, settings: Settings) -> bool:
    """Claim at most one job and try each independent step. True means a job was claimed."""
    with Session(engine) as session, session.begin():
        claim = claim_next(session)
    if claim is None:
        return False

    failures = []
    steps: tuple[tuple[str, Step], ...] = (
        ("ORDER_CHECK_FAILED", update_order_check),
        ("FORECAST_CONTEXT_FAILED", update_forecast_context),
        ("REPLENISHMENT_CONTEXT_FAILED", update_replenishment_context),
    )
    for code, step in steps:
        try:
            _guarded(engine, claim, lambda session, step=step: step(session, claim, settings))
        except ClaimLost:
            return True
        except Exception:
            # Never log database detail, order data, or an exception traceback.
            failures.append(code)
            LOGGER.warning("Order analytics step failed: %s", code)
            try:
                _guarded(engine, claim, lambda session, code=code: _record_failure(
                    session, claim, code
                ))
            except ClaimLost:
                return True
            except Exception:
                # If a second database error keeps us from recording, preserve the
                # job-level fallback and continue attempting the other independent steps.
                LOGGER.warning("Order analytics failure state unavailable: %s", code)

    try:
        _guarded(
            engine,
            claim,
            lambda session: finish_guarded(session, claim, failures[0] if failures else None),
        )
    except ClaimLost:
        pass
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Process provisional B2B order analytics jobs")
    parser.add_argument("--once", action="store_true", help="Claim and process at most one job")
    args = parser.parse_args(argv)
    try:
        settings = get_settings()
        engine = get_engine(settings.database_url)
    except Exception:
        LOGGER.error("Order analytics worker configuration unavailable")
        return 1

    while True:
        try:
            worked = run_once(engine, settings)
        except Exception:
            LOGGER.error("Order analytics worker iteration failed")
            if args.once:
                return 1
            worked = False
        if args.once:
            return 0
        if not worked:
            time.sleep(IDLE_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
