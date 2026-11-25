"""Content-addressed fixture projections, with no raw source metadata."""

import hashlib
import os
import re
import stat
import tempfile
import time
from contextlib import contextmanager
from datetime import UTC, date
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError

from app.analytics.export import _bounded_read, canonical_json
from app.analytics.ingestion import _decode_json, checked_path
from app.analytics.schemas import PipelineError, Unit
from app.cold_start.schemas import ColdStartReport, Metrics, MetricValue

MAX_PROJECTION_BYTES = 256 * 1024
MAX_ENTRIES = 128
ID = re.compile(r"^(?:csv1|csf1)-[0-9a-f]{64}$")


class PublicModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class PublicSample(PublicModel):
    origin: date
    horizon: Literal[1, 7]
    prediction: MetricValue | None
    baseline: MetricValue | None
    reference_count: int = Field(ge=0, le=64)
    confidence: Literal["cluster", "category", "all_train", "unavailable"]
    reason: Literal["insufficient_metadata", "insufficient_references"] | None


class PublicReport(PublicModel):
    schema_version: Literal["cold-start-public/1"] = "cold-start-public/1"
    fixture_label: Literal["Dữ liệu kiểm thử"] = "Dữ liệu kiểm thử"
    operational_state: Literal["unavailable"] = "unavailable"
    target: Literal["gross_fulfilled_units"] = "gross_fulfilled_units"
    unit: Unit
    scope: Literal["single-warehouse-fixture"] = "single-warehouse-fixture"
    created_at: AwareDatetime
    train_cutoff: AwareDatetime
    validation_cutoff: AwareDatetime
    holdout_end: date
    data_versions: tuple[Annotated[str, Field(pattern=r"^ddv1-[0-9a-f]{64}$")], ...] = Field(
        max_length=64
    )
    reference_population: int = Field(ge=0, le=64)
    selected_k: int = Field(ge=1, le=3)
    selection_reason: Literal["validation_common_horizon_7_mae", "no_common_validation_samples"]
    metrics: dict[Literal["1", "7"], Metrics]
    samples: tuple[PublicSample, ...] = Field(max_length=12)
    limitations: tuple[
        Literal[
            "FIXTURE_ONLY",
            "REAL_EVALUATION_NOT_VERIFIED",
            "OPERATIONAL_UNAVAILABLE",
            "CONFIDENCE_IS_QUALITATIVE_NOT_PROBABILISTIC",
            "END_OF_DAY_INCLUDES_NEXT_MIDNIGHT_UTC",
        ],
        ...,
    ]


class PublicFailure(PublicModel):
    schema_version: Literal["cold-start-failure/1"] = "cold-start-failure/1"
    created_at: AwareDatetime
    reason_code: Literal["NO_ELIGIBLE_TRAINING_SNAPSHOTS", "EVALUATION_FAILED"]


def _root(root, *, create=False):
    root = checked_path(Path(root), directory=True, must_exist=not create)
    if create:
        root.mkdir(parents=True, exist_ok=True)
        root = checked_path(root, directory=True)
    return root


def _read(root, key):
    if not isinstance(key, str) or not ID.fullmatch(key):
        raise ValueError("invalid id")
    path = checked_path(root / key)
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("invalid catalog entry")
    body = _bounded_read(path, MAX_PROJECTION_BYTES)
    if key[5:] != hashlib.sha256(body).hexdigest():
        raise ValueError("invalid digest")
    parsed = _decode_json(body.decode("utf-8"))
    model = PublicReport if key.startswith("csv1-") else PublicFailure
    value = model.model_validate(parsed)
    if canonical_json(value) != body:
        raise ValueError("invalid canonical projection")
    return value


def read_report(root, run_id):
    if not isinstance(run_id, str) or not re.fullmatch(r"csv1-[0-9a-f]{64}", run_id):
        raise ValueError("invalid id")
    try:
        catalog = dict(entries(root))
        if run_id not in catalog:
            raise FileNotFoundError
        return catalog[run_id]
    except PipelineError as exc:
        if exc.code == "IO_UNAVAILABLE":
            raise
        raise ValueError("invalid projection") from None
    except (ValidationError, UnicodeError):
        raise ValueError("invalid projection") from None


@contextmanager
def _writer_lock(root):
    path = root / ".writer.lock"
    deadline = time.monotonic() + 2
    while True:
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise ValueError("catalog writer busy") from None
            time.sleep(0.01)
    identity = os.fstat(fd)
    try:
        yield
    finally:
        os.close(fd)
        try:
            current = path.lstat()
            if (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino):
                path.unlink()
        except FileNotFoundError:
            pass


def _publish(root, value, prefix):
    root = _root(root, create=True)
    # Catalog root and its parent are owned by the fixture runner.
    with _writer_lock(root):
        existing = entries(root)
        if len(existing) >= MAX_ENTRIES and not any(v == value for _, v in existing):
            raise ValueError("catalog full")
        body = canonical_json(value)
        if len(body) > MAX_PROJECTION_BYTES:
            raise ValueError("projection too large")
        key = prefix + hashlib.sha256(body).hexdigest()
        target = root / key
        if target.exists() or target.is_symlink():
            if _read(root, key) != value:
                raise ValueError("catalog conflict")
            return key
        # A private same-filesystem stage stays outside the visible catalog.
        fd, stage_name = tempfile.mkstemp(prefix=".cold-start-stage-", dir=root.parent)
        stage = Path(stage_name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(stage, target)
            except FileExistsError:
                if _read(root, key) != value:
                    raise ValueError("catalog conflict") from None
        finally:
            stage.unlink(missing_ok=True)
        return key


def publish_report(report, root):
    report = ColdStartReport.model_validate(report.model_dump())
    value = PublicReport(
        unit=report.unit,
        created_at=report.created_at.astimezone(UTC),
        train_cutoff=report.train_cutoff.astimezone(UTC),
        validation_cutoff=report.validation_cutoff.astimezone(UTC),
        holdout_end=report.partitions[-1].end,
        data_versions=tuple(sorted({p.data_version for p in report.provenance})),
        reference_population=sum(
            p.split == "train"
            and p.snapshot.available_at <= report.train_cutoff
            and bool(p.snapshot.category or p.snapshot.supplier)
            for p in report.provenance
        ),
        selected_k=report.selected_k,
        selection_reason=report.selection_reason,
        metrics=report.metrics,
        samples=tuple(
            PublicSample(
                origin=p.origin,
                horizon=p.horizon,
                prediction=p.prediction,
                baseline=p.baseline,
                reference_count=len(p.reference_keys),
                confidence=p.confidence,
                reason=p.reason,
            )
            for h in (1, 7)
            for p in [row for row in report.predictions if row.horizon == h][:6]
        ),
        limitations=(
            "FIXTURE_ONLY",
            "REAL_EVALUATION_NOT_VERIFIED",
            "OPERATIONAL_UNAVAILABLE",
            "CONFIDENCE_IS_QUALITATIVE_NOT_PROBABILISTIC",
            "END_OF_DAY_INCLUDES_NEXT_MIDNIGHT_UTC",
        ),
    )
    return _publish(root, value, "csv1-")


def publish_failure(root, reason_code, created_at):
    return _publish(
        root, PublicFailure(reason_code=reason_code, created_at=created_at.astimezone(UTC)), "csf1-"
    )


def entries(root):
    root = _root(root)
    result = []
    for path in root.iterdir():
        if path.name == ".writer.lock":
            try:
                checked = checked_path(path, must_exist=False)
                attrs = checked.stat()
            except FileNotFoundError:
                continue
            if not stat.S_ISREG(attrs.st_mode) or attrs.st_size:
                raise ValueError("invalid writer lock")
            continue
        if len(result) >= MAX_ENTRIES or not ID.fullmatch(path.name):
            raise ValueError("invalid catalog")
        result.append((path.name, _read(root, path.name)))
    return result
