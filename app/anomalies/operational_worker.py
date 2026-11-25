"""Separate post-commit B2B scorer. The API never loads artifacts or performs inference."""

import argparse
import logging
import re
import time

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.anomalies.operational_artifact import ArtifactInvalid, load_artifact
from app.anomalies.operational_features import (
    CoverageInvalid,
    build_features,
    load_coverage,
    resolve_lineage,
)
from app.anomalies.operational_jobs import JobClaim, claim_next, complete, fail
from app.anomalies.operational_result import OperationalResult, UnavailableReason
from app.core.config import Settings, get_settings
from app.db.session import get_engine

LOGGER = logging.getLogger(__name__)


def _digest(value: str | None):
    return value if value and re.fullmatch(r"[0-9a-f]{64}", value) else None


def _unavailable(reason: UnavailableReason):
    return OperationalResult(state="unavailable", reason_code=reason)


def evaluate(engine: Engine, settings: Settings, claim: JobClaim):
    if claim.artifact_digest is None:
        if settings.operational_anomaly_artifact_path is None and (
            settings.operational_anomaly_artifact_sha256 is None
        ):
            return _unavailable("NO_APPROVED_MODEL")
        return _unavailable("MODEL_ARTIFACT_INVALID")
    if (
        claim.artifact_digest != settings.operational_anomaly_artifact_sha256
        or settings.operational_anomaly_artifact_path is None
    ):
        return _unavailable("MODEL_ARTIFACT_INVALID")
    try:
        artifact = load_artifact(
            settings.operational_anomaly_artifact_path,
            claim.artifact_digest,
            allow_synthetic_test=settings.operational_anomaly_allow_synthetic_test,
        )
    except ArtifactInvalid:
        return _unavailable("MODEL_ARTIFACT_INVALID")
    if (
        not claim.coverage_digest
        or claim.coverage_digest != (settings.operational_anomaly_coverage_sha256)
        or settings.operational_anomaly_coverage_path is None
    ):
        return _unavailable("INSUFFICIENT_DATA")
    try:
        coverage = load_coverage(
            settings.operational_anomaly_coverage_path,
            claim.coverage_digest,
            allow_synthetic_test=settings.operational_anomaly_allow_synthetic_test,
        )
    except CoverageInvalid:
        return _unavailable("INSUFFICIENT_DATA")
    if coverage.dataset_class != artifact.artifact_class:
        return _unavailable("INSUFFICIENT_DATA")
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with Session(bind=connection) as session:
            if resolve_lineage(session, claim) is None:
                return _unavailable("LINEAGE_INVALID")
            features = build_features(session, claim, coverage)
    if features is None:
        return _unavailable("INSUFFICIENT_DATA")
    values, fingerprint = features
    score = artifact.score(values)
    projection = dict(
        score=score,
        threshold=artifact.threshold,
        model_version=artifact.model_version,
        feature_version=artifact.feature_version,
        input_fingerprint=fingerprint,
        dataset_class=artifact.artifact_class,
    )
    if score <= artifact.threshold:
        return OperationalResult(state="normal", **projection)
    explanation = artifact.explain(values, score)
    if explanation.state != "available":
        return _unavailable("EXPLANATION_UNAVAILABLE")
    return OperationalResult(
        state="flagged",
        base_value=explanation.base_value,
        contributions=explanation.contributions,
        **projection,
    )


def run_once(engine: Engine, settings: Settings) -> bool:
    with Session(engine) as session, session.begin():
        claim = claim_next(
            session,
            _digest(settings.operational_anomaly_artifact_sha256),
            _digest(settings.operational_anomaly_coverage_sha256),
        )
    if claim is None:
        return False
    try:
        result = evaluate(engine, settings, claim)
        with Session(engine) as session, session.begin():
            complete(session, claim, result.model_dump(mode="json"))
    except Exception:
        # Never print filenames, system details, customer data or artifact content.
        LOGGER.warning("Operational anomaly scoring failed: PROCESSING_FAILED")
        with Session(engine) as session, session.begin():
            fail(session, claim, "PROCESSING_FAILED")
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    try:
        settings = get_settings()
        engine = get_engine(settings.database_url)
        if engine.dialect.name != "postgresql":
            return 1
    except Exception:
        return 1
    while True:
        try:
            worked = run_once(engine, settings)
        except Exception:
            LOGGER.warning("Operational anomaly worker iteration failed")
            if args.once:
                return 1
            worked = False
        if args.once:
            return 0
        if not worked:
            time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())
