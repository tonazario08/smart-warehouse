"""Read-only, fixture-gated cold-start report endpoints."""

import re
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.analytics.ingestion import checked_path
from app.analytics.schemas import PipelineError
from app.auth.dependencies import Permission, require_permission
from app.cold_start.catalog import PublicFailure, PublicReport, entries, read_report
from app.core.config import Settings, get_settings
from app.core.errors import DomainError
from app.models import User

router = APIRouter(prefix="/forecasts/cold-start", tags=["cold-start"])
Actor = Annotated[User, Depends(require_permission(Permission.FORECAST_READ))]
Config = Annotated[Settings, Depends(get_settings)]


class Status(BaseModel):
    state: Literal["ready", "unavailable", "failed", "stale"]
    reason_code: str | None
    latest_run_id: str | None
    operational_state: Literal["unavailable"] = "unavailable"


class ReportView(BaseModel):
    run_id: str
    stale: bool
    report: PublicReport


def enabled(settings):
    return settings.app_env in ("test", "integration") and settings.cold_start_allow_fixture


def stale(value):
    now = datetime.now(UTC)
    created = value.created_at.astimezone(UTC)
    return created > now or now - created > timedelta(days=7)


def failure(error):
    if (
        isinstance(error, OSError)
        or isinstance(error, PipelineError)
        and error.code == "IO_UNAVAILABLE"
    ):
        return DomainError(503, "COLD_START_IO_UNAVAILABLE", "Catalog is unavailable.")
    return DomainError(409, "COLD_START_INVALID", "Catalog content is invalid.")


def exists_checked(path, *, directory=False):
    checked = checked_path(path, directory=directory, must_exist=False)
    try:
        checked.stat()
    except FileNotFoundError:
        return False
    return True


@router.get("/status", response_model=Status)
def status(actor: Actor, settings: Config):
    root = settings.cold_start_catalog_root
    if not enabled(settings) or root is None:
        return Status(state="unavailable", reason_code="NO_CATALOG", latest_run_id=None)
    try:
        if not exists_checked(root, directory=True):
            return Status(state="unavailable", reason_code="NO_CATALOG", latest_run_id=None)
        found = entries(root)
    except (ValueError, OSError, PipelineError) as exc:
        raise failure(exc) from None
    if not found:
        return Status(state="unavailable", reason_code="NO_REPORT", latest_run_id=None)
    key, value = max(found, key=lambda item: (item[1].created_at, item[0]))
    if isinstance(value, PublicFailure):
        state = "unavailable" if value.reason_code == "NO_ELIGIBLE_TRAINING_SNAPSHOTS" else "failed"
        return Status(state=state, reason_code=value.reason_code, latest_run_id=None)
    if not any(metric.predicted for metric in value.metrics.values()):
        return Status(
            state="unavailable", reason_code="NO_ELIGIBLE_PREDICTIONS", latest_run_id=None
        )
    if stale(value):
        return Status(state="stale", reason_code="REPORT_STALE", latest_run_id=None)
    return Status(state="ready", reason_code=None, latest_run_id=key)


@router.get("/runs/{run_id}", response_model=ReportView)
def run(actor: Actor, settings: Config, run_id: str):
    root = settings.cold_start_catalog_root
    if not enabled(settings) or root is None or not re.fullmatch(r"csv1-[0-9a-f]{64}", run_id):
        raise DomainError(404, "COLD_START_NOT_FOUND", "Report not found.")
    try:
        if not exists_checked(root, directory=True) or not exists_checked(root / run_id):
            raise DomainError(404, "COLD_START_NOT_FOUND", "Report not found.")
        report = read_report(root, run_id)
    except FileNotFoundError:
        raise DomainError(404, "COLD_START_NOT_FOUND", "Report not found.") from None
    except (ValueError, OSError, PipelineError) as exc:
        raise failure(exc) from None
    return ReportView(run_id=run_id, stale=stale(report), report=report)
