"""Contained immutable four-file bundles, verified reuse and owned publication locks."""

import hashlib
import json
import os
import re
import uuid
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from app.analytics.ingestion import _bounded_read, _decode_json, _tuples, checked_path
from app.analytics.schemas import (
    MAX_DAILY_QUANTITY,
    MAX_FILES,
    MAX_INPUT_BYTES,
    MAX_ROWS,
    MAX_SERIES_DAYS,
    OPERATIONAL_KINDS,
    RECORDED_VEND_WARNINGS,
    REPORTED_WARNINGS,
    Admission,
    AwareTime,
    BusinessDate,
    Checksum,
    Contract,
    DailyObservation,
    DailyRecord,
    EventKind,
    EventRecord,
    Identifier,
    PipelineError,
    PreparedDataset,
    PublishedBundle,
    QualityReport,
    ReportedBenchmarkProtocol,
    ReportedPartitionCounts,
    ReportedSalesAdmission,
    ReportedSalesBatch,
    ReportedSalesMapping,
    ReportedSalesObservation,
    ReportedSalesPreparedDataset,
    ReportedSalesQuality,
    ReportedSalesRecord,
    ReportedSourceEvidence,
    Representation,
    Rights,
    SoftwareIdentity,
    business_day_bounds,
    load_timezone,
    validate_reported_policy,
)
from app.analytics.semantics import semantic_value

ARTIFACTS = {"records.jsonl", "observations.jsonl", "quality.json"}
FILE_SET = ARTIFACTS | {"manifest.json"}


class _PublicSource(Contract):
    kind: Literal["files", "operational_b2b"]
    namespace: Identifier
    snapshot_id: Identifier
    representation: Representation
    channel: Identifier
    kind_map: dict[Identifier, EventKind]
    outside_target_kinds: tuple[Identifier, ...]
    available_at_upper_bound: AwareTime | None
    availability_policy_ref: Identifier | None

    @model_validator(mode="after")
    def policy(self):
        if self.kind == "operational_b2b" and (
            self.channel != "managed_b2b_fulfillment"
            or self.representation != "events"
            or self.kind_map != OPERATIONAL_KINDS
            or not self.availability_policy_ref
        ):
            raise ValueError("invalid operational source")
        if (self.available_at_upper_bound and not self.availability_policy_ref) or any(
            self.kind_map.get(kind) != "unclassified" for kind in self.outside_target_kinds
        ):
            raise ValueError("invalid source policy")
        return self


class _PublicAdmission(Admission):
    source: _PublicSource
    rules_version: Literal["demand-rules/1", "demand-rules/2"]

    @model_validator(mode="after")
    def matching_rules(self):
        expected = "demand-rules/2" if self.target == "recorded_vend_units" else "demand-rules/1"
        if self.rules_version != expected:
            raise ValueError("target and rules must match")
        if any(
            proof.available_at > self.cutoff
            for proof in (*self.mappings, *self.coverage, *self.availability)
        ):
            raise ValueError("proof must be known by cutoff")
        return self


Count = Annotated[int, Field(ge=0, le=MAX_SERIES_DAYS)]


class _Counts(Contract):
    input_rows: Count
    accepted_rows: Count
    duplicate_rows: Count
    excluded_rows: Count
    rejected_rows: Count
    normalized_records: Count
    observations: Count
    usable_targets: Count
    coverage: dict[Literal["complete", "partial", "unknown"], Count]
    lifecycle: dict[Literal["active", "inactive", "unknown"], Count]
    availability: dict[Literal["unknown", "stockout_observed", "covered_positive"], Count]
    censoring_risk: dict[Literal["unknown", "potential", "not_indicated"], Count]


class _Manifest(Contract):
    schema_version: Literal["demand-data-bundle/1"]
    admission: _PublicAdmission
    source_checksum: Checksum
    software: SoftwareIdentity
    artifacts: dict[str, Checksum]
    counts: _Counts
    limits: dict[str, int]
    limitations: tuple[Identifier, ...]
    data_version: str = Field(pattern=r"^ddv1-[0-9a-f]{64}$")

    @model_validator(mode="after")
    def exact_artifacts(self):
        if set(self.artifacts) != ARTIFACTS:
            raise ValueError("exact artifacts required")
        return self


class _PublicReportedAdmission(Contract):
    schema_version: Literal["demand-data/2"]
    target: Literal["reported_daily_unit_sales"]
    dataset_class: Literal["fixture", "research"]
    source: _PublicSource
    window_start: BusinessDate
    window_end: BusinessDate
    cutoff: AwareTime
    mappings: tuple[ReportedSalesMapping, ...]
    rights: Rights
    protocol: ReportedBenchmarkProtocol
    source_evidence: ReportedSourceEvidence
    rules_version: Literal["demand-rules/3"]

    @model_validator(mode="after")
    def reported_policy(self):
        return validate_reported_policy(self)


class ReportedCounts(Contract):
    input_rows: Count
    accepted_rows: Count
    duplicate_rows: Count
    excluded_rows: Count
    rejected_rows: Count
    normalized_records: Count
    observations: Count
    usable_targets: Count
    genuine_zeros: Count
    eligible_sum: Annotated[int, Field(ge=0, le=MAX_DAILY_QUANTITY)]
    measurement_counts: dict[str, Count]
    partition_counts: dict[str, ReportedPartitionCounts]


class _ReportedManifest(Contract):
    schema_version: Literal["demand-data-bundle/2"]
    admission: _PublicReportedAdmission
    source_checksum: Checksum
    software: SoftwareIdentity
    artifacts: dict[str, Checksum]
    counts: ReportedCounts
    limits: dict[str, int]
    limitations: tuple[Identifier, ...]
    data_version: str = Field(pattern=r"^ddv2-[0-9a-f]{64}$")

    @model_validator(mode="after")
    def exact_artifacts(self):
        if set(self.artifacts) != ARTIFACTS:
            raise ValueError("exact artifacts required")
        return self


def _reported_summary(quality, record_count, observation_count):
    partitions = quality.partition_counts.values()
    total = sum(p.eligible_sum for p in partitions)
    if total > MAX_DAILY_QUANTITY:
        raise ValueError("quantity overflow")
    return {
        "counts": {
            **{
                key: getattr(quality, key)
                for key in (
                    "input_rows",
                    "accepted_rows",
                    "duplicate_rows",
                    "excluded_rows",
                    "rejected_rows",
                )
            },
            "normalized_records": record_count,
            "observations": observation_count,
            "usable_targets": quality.measurement_counts["eligible"],
            "genuine_zeros": sum(p.genuine_zeros for p in quality.partition_counts.values()),
            "eligible_sum": total,
            "measurement_counts": dict(quality.measurement_counts),
            "partition_counts": {
                name: p.model_dump() for name, p in quality.partition_counts.items()
            },
        },
        "limits": {
            "input_bytes": MAX_INPUT_BYTES,
            "input_files": MAX_FILES,
            "input_rows": MAX_ROWS,
            "series_days": MAX_SERIES_DAYS,
        },
        "limitations": tuple(sorted(REPORTED_WARNINGS | set(quality.warnings))),
    }


def _observation_counts():
    return {
        "observations": 0,
        "usable_targets": 0,
        "coverage": dict.fromkeys(("complete", "partial", "unknown"), 0),
        "lifecycle": dict.fromkeys(("active", "inactive", "unknown"), 0),
        "availability": dict.fromkeys(("unknown", "stockout_observed", "covered_positive"), 0),
        "censoring_risk": dict.fromkeys(("unknown", "potential", "not_indicated"), 0),
    }


def _count_observation(counts, row):
    counts["observations"] += 1
    counts["usable_targets"] += row.target_quantity is not None
    for field in ("coverage", "lifecycle", "availability", "censoring_risk"):
        counts[field][getattr(row, field)] += 1


def _summary(quality, record_count, observations, dataset_class, target="gross_fulfilled_units"):
    counts = {
        **{
            key: getattr(quality, key)
            for key in (
                "input_rows",
                "accepted_rows",
                "duplicate_rows",
                "excluded_rows",
                "rejected_rows",
            )
        },
        "normalized_records": record_count,
        **observations,
    }
    limitations = {"NOT_LATENT_DEMAND"}
    if dataset_class != "research":
        limitations.add("NOT_RESEARCH_DATA")
    if observations["coverage"]["partial"] or observations["coverage"]["unknown"]:
        limitations.add("INCOMPLETE_COVERAGE")
    if observations["lifecycle"]["inactive"] or observations["lifecycle"]["unknown"]:
        limitations.add("NONACTIVE_LIFECYCLE")
    if observations["availability"]["unknown"]:
        limitations.add("AVAILABILITY_UNKNOWN")
    if observations["censoring_risk"]["unknown"]:
        limitations.add("CENSORING_UNKNOWN")
    if observations["censoring_risk"]["potential"]:
        limitations.add("POTENTIAL_CENSORING")
    limitations.update(quality.warnings)
    if target == "recorded_vend_units":
        limitations.update(RECORDED_VEND_WARNINGS)
    return {
        "counts": counts,
        "limits": {
            "input_bytes": MAX_INPUT_BYTES,
            "input_files": MAX_FILES,
            "input_rows": MAX_ROWS,
            "series_days": MAX_SERIES_DAYS,
        },
        "limitations": tuple(sorted(limitations)),
    }


def _validate_consumer_record(row, admission):
    daily = isinstance(row, DailyRecord)
    day = (
        row.business_date
        if daily
        else row.occurred_at.astimezone(load_timezone(admission.business_timezone)).date()
    )
    if not admission.window_start <= day < admission.window_end:
        raise ValueError
    mapping = [
        item
        for item in admission.mappings
        if item.source_product == row.source_product
        and item.source_warehouse == row.source_warehouse
        and item.valid_from <= day < item.valid_to
    ]
    if len(mapping) != 1 or row.unit != mapping[0].unit:
        raise ValueError
    earliest = (
        business_day_bounds(day, admission.business_timezone)[1] if daily else row.occurred_at
    )
    if row.available_at is None:
        if not daily or row.quantity is not None:
            raise ValueError
    elif not earliest <= row.available_at <= admission.cutoff:
        raise ValueError
    if admission.target == "recorded_vend_units" and (
        not daily or row.coverage == "complete" or (row.coverage == "partial" and not row.quantity)
    ):
        raise ValueError
    return mapping[0]


def canonical_json(value: object) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump()
    try:
        return (
            json.dumps(
                semantic_value(value),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise PipelineError("INPUT_SCHEMA") from None


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _write_file(path, content):
    with path.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def _rename_stage(stage, target):
    stage.rename(target)


def _verify(path, *, require_name=True):
    path = checked_path(path, directory=True)
    try:
        if {entry.name for entry in path.iterdir()} != FILE_SET:
            raise ValueError
        manifest_path = checked_path(path / "manifest.json")
        raw = _bounded_read(manifest_path, MAX_INPUT_BYTES)
        decoded = _tuples(_decode_json(raw.decode("utf-8")))
        if isinstance(decoded, dict) and decoded.get("schema_version") == "demand-data-bundle/2":
            return _verify_reported(path, raw, decoded, require_name=require_name)
        manifest = _Manifest.model_validate(decoded)
        identity = manifest.model_dump(exclude={"data_version"})
        version = "ddv1-" + _sha(canonical_json(identity))
        if (
            version != manifest.data_version
            or (require_name and path.name != version)
            or canonical_json(manifest) != raw
        ):
            raise ValueError
        counts, observations = {}, _observation_counts()
        recorded = manifest.admission.target == "recorded_vend_units"
        positive_records, positive_observations = {}, {}
        for name in sorted(ARTIFACTS):
            candidate = checked_path(path / name)
            digest = hashlib.sha256()
            if name == "quality.json":
                body = _bounded_read(candidate, MAX_INPUT_BYTES)
                quality = QualityReport.model_validate(_tuples(_decode_json(body.decode("utf-8"))))
                if canonical_json(quality) != body:
                    raise ValueError
                digest.update(body)
            else:
                seen, previous, count = set(), None, 0
                with candidate.open("rb") as stream:
                    while line := stream.readline(16385):
                        count += 1
                        if len(line) > 16384 or count > (
                            MAX_ROWS if name == "records.jsonl" else MAX_SERIES_DAYS
                        ):
                            raise ValueError
                        digest.update(line)
                        value = _decode_json(line.decode("utf-8"))
                        if name == "observations.jsonl":
                            row = DailyObservation.model_validate(_tuples(value))
                            matching = [
                                item
                                for item in manifest.admission.mappings
                                if (item.product_key, item.warehouse_key, item.unit)
                                == (row.product_key, row.warehouse_key, row.unit)
                                and item.valid_from <= row.business_date < item.valid_to
                            ]
                            if (
                                len(matching) != 1
                                or row.lifecycle != matching[0].lifecycle
                                or not manifest.admission.window_start
                                <= row.business_date
                                < manifest.admission.window_end
                                or (
                                    row.available_at
                                    and row.available_at > manifest.admission.cutoff
                                )
                            ):
                                raise ValueError
                            _count_observation(observations, row)
                            key = (row.product_key, row.warehouse_key, row.unit, row.business_date)
                            if recorded:
                                if (
                                    row.target_quantity is not None
                                    or (
                                        row.coverage
                                        != (
                                            "unknown"
                                            if row.observed_quantity is None
                                            else "partial"
                                        )
                                    )
                                    or (
                                        row.availability != "unknown"
                                        or row.censoring_risk != "unknown"
                                    )
                                ):
                                    raise ValueError
                                if row.observed_quantity:
                                    positive_observations[key] = row.observed_quantity
                            encoded = canonical_json(row)
                        else:
                            value = dict(value)
                            offset = value.pop("original_offset_seconds")
                            if offset is not None and (
                                type(offset) is not int or abs(offset) >= 86400
                            ):
                                raise ValueError
                            if manifest.admission.source.representation == "events":
                                kind = value.pop("event_kind", None)
                                row = EventRecord.model_validate(value)
                                if kind != manifest.admission.source.kind_map.get(row.kind):
                                    raise ValueError
                                key = row.event_id
                                normalized = {**row.model_dump(), "event_kind": kind}
                            else:
                                row = DailyRecord.model_validate(value)
                                key = row.observation_id
                                normalized = row.model_dump()
                            encoded = canonical_json(
                                {**normalized, "original_offset_seconds": offset}
                            )
                            mapping = _validate_consumer_record(row, manifest.admission)
                            if recorded and row.quantity:
                                day_key = (
                                    mapping.product_key,
                                    mapping.warehouse_key,
                                    mapping.unit,
                                    row.business_date,
                                )
                                if day_key in positive_records:
                                    raise ValueError
                                positive_records[day_key] = row.quantity
                        if (
                            key in seen
                            or (previous is not None and key < previous)
                            or encoded != line
                        ):
                            raise ValueError
                        seen.add(key)
                        previous = key
                counts[name] = count
            if digest.hexdigest() != manifest.artifacts[name]:
                raise ValueError
        if counts["records.jsonl"] != (
            quality.accepted_rows
            + quality.excluded_rows
            - quality.exclusions.get("OUTSIDE_WINDOW", 0)
        ):
            raise ValueError
        summary = _summary(
            quality,
            counts["records.jsonl"],
            observations,
            manifest.admission.dataset_class,
            manifest.admission.target,
        )
        if recorded:
            if (
                observations["usable_targets"] != 0
                or not positive_records
                or positive_records != positive_observations
                or not RECORDED_VEND_WARNINGS.issubset(quality.warnings)
            ):
                raise ValueError
        elif observations["usable_targets"] == 0:
            raise ValueError
        if manifest.counts.model_dump() != summary["counts"] or any(
            getattr(manifest, key) != summary[key] for key in ("limits", "limitations")
        ):
            raise ValueError
        return manifest
    except (OSError, ValueError, TypeError, KeyError, ValidationError, PipelineError):
        raise PipelineError("OUTPUT_CONFLICT") from None


def verify_bundle(path: Path) -> str:
    return _verify(path).data_version


def _verify_reported(path, raw, decoded, *, require_name):
    from app.analytics.ingestion import _report
    from app.analytics.semantics import prepare_reported_dataset

    manifest = _ReportedManifest.model_validate(decoded)
    identity = manifest.model_dump(exclude={"data_version"})
    version = "ddv2-" + _sha(canonical_json(identity))
    if (
        version != manifest.data_version
        or (require_name and path.name != version)
        or canonical_json(manifest) != raw
    ):
        raise ValueError
    contents = {}
    for name in ARTIFACTS:
        content = _bounded_read(checked_path(path / name), MAX_INPUT_BYTES)
        if _sha(content) != manifest.artifacts[name]:
            raise ValueError
        contents[name] = content
    records, observations = [], []
    for name, model, output, limit, key in (
        ("records.jsonl", ReportedSalesRecord, records, MAX_ROWS, lambda r: r.observation_id),
        (
            "observations.jsonl",
            ReportedSalesObservation,
            observations,
            MAX_SERIES_DAYS,
            lambda r: (r.product_key, r.reporting_entity_key, r.unit, r.business_date),
        ),
    ):
        previous = None
        for line in contents[name].splitlines(keepends=True):
            if len(line) > 16384 or len(output) >= limit:
                raise ValueError
            row = model.model_validate(_tuples(_decode_json(line.decode("utf-8"))))
            current = key(row)
            if canonical_json(row) != line or (previous is not None and current <= previous):
                raise ValueError
            previous = current
            output.append(row)
    normalized_hash = _sha(contents["records.jsonl"])
    if normalized_hash != manifest.admission.source_evidence.normalized_input_sha256:
        raise ValueError
    checksum = _sha(canonical_json([{"format": "jsonl", "sha256": normalized_hash}]))
    if checksum != manifest.source_checksum:
        raise ValueError
    private = manifest.admission.model_dump(exclude={"rules_version"})
    private["source"].update(
        files=({"path": "daily.jsonl", "format": "jsonl", "sha256": normalized_hash},),
        database_identity=None,
    )
    admission = ReportedSalesAdmission.model_validate(_tuples(private))
    batch = ReportedSalesBatch(
        source_checksum=checksum, records=tuple(records), report=_report(len(records))
    )
    expected = prepare_reported_dataset(admission, batch, manifest.software)
    if tuple(observations) != expected.observations:
        raise ValueError
    quality = ReportedSalesQuality.model_validate(
        _tuples(_decode_json(contents["quality.json"].decode("utf-8")))
    )
    if canonical_json(quality) != contents["quality.json"] or quality != expected.quality:
        raise ValueError
    summary = _reported_summary(expected.quality, len(records), len(observations))
    if manifest.counts.model_dump() != summary["counts"] or any(
        getattr(manifest, key) != summary[key] for key in ("limits", "limitations")
    ):
        raise ValueError
    return manifest


def _clean_stage(stage, created):
    if stage is None or not stage.exists():
        return
    checked_path(stage, directory=True)
    present = {item.name for item in stage.iterdir()}
    if present - set(created):
        raise PipelineError("OUTPUT_CONFLICT")
    for name in present:
        path = checked_path(stage / name)
        if _sha(path.read_bytes()) != created[name]:
            raise PipelineError("OUTPUT_CONFLICT")
    for name in present:
        checked_path(stage / name).unlink()
    stage.rmdir()


def publish_bundle(prepared: PreparedDataset, output_root: Path) -> PublishedBundle:
    reported = isinstance(prepared, ReportedSalesPreparedDataset)
    if not reported and not isinstance(prepared, PreparedDataset):
        raise PipelineError("OUTPUT_CONFLICT")
    root = checked_path(output_root, directory=True, must_exist=False)
    if prepared._input_root and (
        root.is_relative_to(prepared._input_root) or prepared._input_root.is_relative_to(root)
    ):
        raise PipelineError("OUTPUT_PATH_UNSAFE")
    contents = {
        "records.jsonl": b"".join(canonical_json(row) for row in prepared.normalized_records),
        "observations.jsonl": b"".join(canonical_json(row) for row in prepared.observations),
        "quality.json": canonical_json(prepared.quality),
    }
    identity = {
        "schema_version": "demand-data-bundle/2" if reported else "demand-data-bundle/1",
        "admission": prepared.admission_semantics,
        "source_checksum": prepared.source_checksum,
        "software": prepared.software.model_dump(),
        "artifacts": {name: _sha(body) for name, body in contents.items()},
    }
    if reported:
        identity.update(
            _reported_summary(
                prepared.quality, len(prepared.normalized_records), len(prepared.observations)
            )
        )
    else:
        observations = _observation_counts()
        for row in prepared.observations:
            _count_observation(observations, row)
        identity.update(
            _summary(
                prepared.quality,
                len(prepared.normalized_records),
                observations,
                prepared.admission_semantics["dataset_class"],
                prepared.admission_semantics["target"],
            )
        )
    version = ("ddv2-" if reported else "ddv1-") + _sha(canonical_json(identity))
    try:
        model = _ReportedManifest if reported else _Manifest
        manifest = model.model_validate({**identity, "data_version": version})
    except (ValidationError, PipelineError):
        raise PipelineError("OUTPUT_CONFLICT") from None
    contents["manifest.json"] = canonical_json(manifest)
    token, stage, created, owned, interrupted = uuid.uuid4().hex, None, {}, False, False
    try:
        root.mkdir(parents=True, exist_ok=True)
        root = checked_path(root, directory=True)
        lock = checked_path(root / ".publish.lock", must_exist=False)
        try:
            with lock.open("x", encoding="ascii") as stream:
                stream.write(token)
            owned = True
        except FileExistsError:
            raise PipelineError("OUTPUT_BUSY") from None
        target = root / version
        for candidate in root.iterdir():
            if candidate.name == ".publish.lock":
                continue
            if not re.fullmatch(r"ddv[12]-[0-9a-f]{64}", candidate.name):
                raise PipelineError("OUTPUT_CONFLICT")
            existing = _verify(candidate)
            if (
                existing.admission.source.namespace == manifest.admission.source.namespace
                and existing.admission.source.snapshot_id == manifest.admission.source.snapshot_id
                and existing.source_checksum != prepared.source_checksum
            ):
                raise PipelineError("SOURCE_SNAPSHOT_CONFLICT")
        if target.exists():
            return PublishedBundle(data_version=version, path=target, reused=True)
        stage = root / (".staging-" + uuid.uuid4().hex)
        stage.mkdir(mode=0o700)
        for name in ("records.jsonl", "observations.jsonl", "quality.json", "manifest.json"):
            checked_path(stage, directory=True)
            created[name] = _sha(contents[name])
            _write_file(stage / name, contents[name])
        _verify(stage, require_name=False)
        if target.exists():
            raise PipelineError("OUTPUT_CONFLICT")
        _rename_stage(stage, target)
        stage = None
        return PublishedBundle(data_version=version, path=target, reused=False)
    except KeyboardInterrupt:
        interrupted = True
        raise
    except OSError:
        raise PipelineError("IO_UNAVAILABLE") from None
    finally:
        if owned:
            try:
                _clean_stage(stage, created)
            except PipelineError:
                if not interrupted:
                    raise
            finally:
                if checked_path(lock).read_text(encoding="ascii") != token:
                    raise PipelineError("OUTPUT_CONFLICT")
                lock.unlink()
