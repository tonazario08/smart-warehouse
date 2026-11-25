"""Strict, import-safe contracts for the offline demand-data boundary."""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, date, datetime, time, timedelta
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PrivateAttr,
    field_validator,
    model_validator,
)

MAX_FILES = 32
MAX_INPUT_BYTES = 67108864
MAX_ROWS = 100000
MAX_SERIES_DAYS = 1000000
MAX_EVENT_QUANTITY = 2147483647
MAX_DAILY_QUANTITY = 9223372036854775807
RECORDED_VEND_WARNINGS = frozenset(
    {"RECORDED_VENDS_ONLY", "NO_FULFILLMENT_CLAIM", "NOT_FORECAST_READY", "NO_COMPLETE_TARGETS"}
)

DatasetClass = Literal["fixture", "demo", "research"]
Representation = Literal["events", "daily"]
Coverage = Literal["complete", "partial", "unknown"]
Lifecycle = Literal["active", "inactive", "unknown"]
EventKind = Literal[
    "customer_fulfillment",
    "inbound",
    "transfer_in",
    "transfer_out",
    "return",
    "adjustment",
    "cancellation",
    "test",
    "unclassified",
]
OPERATIONAL_KINDS = {
    "legacy_unknown": "unclassified",
    "standard_inbound": "inbound",
    "standard_outbound": "unclassified",
    "transfer_in": "transfer_in",
    "transfer_out": "transfer_out",
    "purchase_request_fulfillment": "customer_fulfillment",
}


class PipelineError(Exception):
    """The code and optional sanitized report are the entire public diagnostic."""

    def __init__(self, code: str, report=None):
        self.code, self.report = code, report
        super().__init__(code)


class FrozenDict(dict):
    def _refuse(self, *args, **kwargs):
        raise TypeError("immutable contract")

    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = __ior__ = _refuse


def freeze(value):
    if isinstance(value, dict):
        return FrozenDict({key: freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(freeze(item) for item in value)
    return value


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    @model_validator(mode="after")
    def immutable_mappings(self):
        for name in type(self).model_fields:
            value = getattr(self, name)
            if isinstance(value, (dict, tuple)):
                object.__setattr__(self, name, freeze(value))
        return self


Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")]
Checksum = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


def unit_label(value):
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 40
        or any(unicodedata.category(char).startswith("C") for char in value)
    ):
        raise ValueError("invalid unit")
    return value


Unit = Annotated[str, BeforeValidator(unit_label)]


def parse_timestamp(value: object) -> datetime:
    try:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}", value):
            parsed = datetime.fromisoformat(value)
        else:
            raise ValueError
        offset = parsed.utcoffset()
        if offset is None or offset.microseconds:
            raise ValueError
        parsed.astimezone(UTC)
        return parsed
    except (ValueError, TypeError, OverflowError):
        raise PipelineError("TIME_VALUE") from None


def parse_business_date(value: object) -> date:
    if type(value) is date:
        return value
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise PipelineError("TIME_VALUE")


AwareTime = Annotated[datetime, BeforeValidator(parse_timestamp)]
BusinessDate = Annotated[date, BeforeValidator(parse_business_date)]


@lru_cache(maxsize=64)
def load_timezone(key: str) -> ZoneInfo:
    try:
        import tzdata

        if tzdata.__version__ != "2026.5" or tzdata.IANA_VERSION != "2026e":
            raise ValueError
        zones = files("tzdata").joinpath("zones").read_text(encoding="utf-8").splitlines()
        if not isinstance(key, str) or key not in zones:
            raise ValueError
        with files("tzdata.zoneinfo").joinpath(*key.split("/")).open("rb") as stream:
            return ZoneInfo.from_file(stream, key=key)
    except (ImportError, OSError, ValueError, TypeError):
        raise PipelineError("TIMEZONE_UNAVAILABLE") from None


def business_day_bounds(day: date, timezone: str) -> tuple[datetime, datetime]:
    zone = load_timezone(timezone)

    def midnight(value):
        naive = datetime.combine(value, time.min)
        candidates = set()
        for fold in (0, 1):
            utc = naive.replace(tzinfo=zone, fold=fold).astimezone(UTC)
            if utc.astimezone(zone).replace(tzinfo=None) == naive:
                candidates.add(utc)
        if len(candidates) != 1:
            raise PipelineError("TIME_VALUE")
        return candidates.pop()

    try:
        start, end = midnight(day), midnight(day + timedelta(days=1))
        if end <= start:
            raise PipelineError("TIME_VALUE")
        return start, end
    except (ValueError, OverflowError):
        raise PipelineError("TIME_VALUE") from None


class InputFile(Contract):
    path: str
    format: Literal["csv", "jsonl"]
    sha256: Checksum

    @field_validator("path")
    @classmethod
    def safe_relative(cls, value):
        if (
            not value
            or len(value) > 1024
            or any(char in value for char in "\\:\0")
            or any(part in ("", ".", "..") for part in value.split("/"))
            or any(unicodedata.category(char).startswith("C") for char in value)
        ):
            raise ValueError("relative input required")
        return value


class DatabaseIdentity(Contract):
    host: str = Field(min_length=1, max_length=253)
    port: int = Field(ge=1, le=65535)
    database: Identifier
    username: Identifier

    @field_validator("host")
    @classmethod
    def host_only(cls, value):
        if re.fullmatch(r"[A-Za-z0-9.:-]+", value) is None:
            raise ValueError("host required")
        return value


class SourceSpec(Contract):
    kind: Literal["files", "operational_b2b"]
    namespace: Identifier
    snapshot_id: Identifier
    representation: Representation
    channel: Identifier
    files: tuple[InputFile, ...] = Field(max_length=MAX_FILES)
    kind_map: dict[Identifier, EventKind]
    outside_target_kinds: tuple[Identifier, ...]
    available_at_upper_bound: AwareTime | None
    availability_policy_ref: Identifier | None
    database_identity: DatabaseIdentity | None

    @model_validator(mode="after")
    def source_contract(self):
        if self.kind == "files":
            if not self.files or self.database_identity is not None:
                raise ValueError("file source required")
        elif (
            self.files
            or self.database_identity is None
            or self.representation != "events"
            or self.channel != "managed_b2b_fulfillment"
            or self.kind_map != OPERATIONAL_KINDS
            or not self.availability_policy_ref
        ):
            raise ValueError("operational channel required")
        if len({item.path for item in self.files}) != len(self.files) or len(
            {item.sha256 for item in self.files}
        ) != len(self.files):
            raise PipelineError("SOURCE_OVERLAP")
        if self.available_at_upper_bound is not None and self.availability_policy_ref is None:
            raise PipelineError("AVAILABILITY_TIME_REQUIRED")
        if any(self.kind_map.get(kind) != "unclassified" for kind in self.outside_target_kinds):
            raise ValueError("only proven unclassified kinds can be outside target")
        return self


class Rights(Contract):
    owner_ref: Identifier
    permission_ref: Identifier
    approved_by_ref: Identifier
    privacy_ref: Identifier
    retention_ref: Identifier
    approved_at: AwareTime


class PeriodMapping(Contract):
    source_product: Identifier
    source_warehouse: Identifier
    product_key: Identifier
    warehouse_key: Identifier
    unit: Unit
    valid_from: BusinessDate
    valid_to: BusinessDate
    lifecycle: Lifecycle
    available_at: AwareTime

    @model_validator(mode="after")
    def positive_period(self):
        if self.valid_from >= self.valid_to:
            raise PipelineError("TIME_VALUE")
        return self


class CoverageDay(Contract):
    source_product: Identifier
    source_warehouse: Identifier
    business_date: BusinessDate
    status: Coverage
    available_at: AwareTime


class AvailabilityInterval(Contract):
    source_product: Identifier
    source_warehouse: Identifier
    start_at: AwareTime
    end_at: AwareTime
    kind: Literal["positive", "stockout"]
    available_at: AwareTime

    @model_validator(mode="after")
    def completed_interval(self):
        if self.start_at >= self.end_at or self.available_at < self.end_at:
            raise PipelineError("TIME_VALUE")
        return self


class Admission(Contract):
    _input_bytes: int = PrivateAttr(default=0)
    _admission_path: str | None = PrivateAttr(default=None)
    schema_version: Literal["demand-data/1"]
    dataset_class: DatasetClass
    source: SourceSpec
    target: Literal["gross_fulfilled_units", "recorded_vend_units"]
    business_timezone: str
    window_start: BusinessDate
    window_end: BusinessDate
    cutoff: AwareTime
    mappings: tuple[PeriodMapping, ...]
    coverage: tuple[CoverageDay, ...]
    availability: tuple[AvailabilityInterval, ...]
    rights: Rights | None

    @field_validator("mappings", "coverage", "availability", mode="before")
    @classmethod
    def bounded_proofs(cls, value):
        if isinstance(value, (tuple, list)) and len(value) > MAX_ROWS:
            raise PipelineError("INPUT_LIMIT")
        return value

    @model_validator(mode="after")
    def admission_contract(self):
        load_timezone(self.business_timezone)
        # Shared source fields only: the public bundle strips file/DB identities.
        if self.target == "recorded_vend_units" and (
            self.source.kind != "files"
            or self.source.representation != "daily"
            or self.source.channel != "recorded_vends"
            or self.source.kind_map
            or self.source.outside_target_kinds
            or self.coverage
            or self.availability
        ):
            raise PipelineError("ADMISSION_INVALID")
        if self.window_start >= self.window_end:
            raise PipelineError("TIME_VALUE")
        if self.dataset_class == "research" and self.rights is None:
            raise PipelineError("ADMISSION_INVALID")
        if self.source.representation == "daily" and self.coverage:
            raise PipelineError("SOURCE_OVERLAP")
        expanded = sum(
            max(
                0,
                (min(row.valid_to, self.window_end) - max(row.valid_from, self.window_start)).days,
            )
            for row in self.mappings
        )
        if expanded > MAX_SERIES_DAYS:
            raise PipelineError("INPUT_LIMIT")
        for grouping in (
            lambda row: (row.source_product, row.source_warehouse),
            lambda row: (row.product_key, row.warehouse_key, row.unit),
        ):
            previous = {}
            for row in sorted(self.mappings, key=lambda item: (*grouping(item), item.valid_from)):
                key = grouping(row)
                if key in previous and previous[key] > row.valid_from:
                    raise PipelineError("SOURCE_OVERLAP")
                previous[key] = row.valid_to
        for mapping in self.mappings:
            day, end = (
                max(mapping.valid_from, self.window_start),
                min(mapping.valid_to, self.window_end),
            )
            while day < end:
                _, day_end = business_day_bounds(day, self.business_timezone)
                if day_end > self.cutoff:
                    raise PipelineError("AFTER_CUTOFF")
                day += timedelta(days=1)
        coverage_keys = set()
        pair_periods = {}
        for mapping in sorted(self.mappings, key=lambda item: item.valid_from):
            pair_periods.setdefault((mapping.source_product, mapping.source_warehouse), []).append(
                mapping
            )
        for proof in self.coverage:
            key = (proof.source_product, proof.source_warehouse, proof.business_date)
            if not any(
                period.valid_from <= proof.business_date < period.valid_to
                for period in pair_periods.get(key[:2], ())
            ):
                raise PipelineError("UNKNOWN_MAPPING")
            if key in coverage_keys:
                raise PipelineError("SOURCE_OVERLAP")
            coverage_keys.add(key)
            if (
                proof.available_at
                < business_day_bounds(proof.business_date, self.business_timezone)[1]
            ):
                raise PipelineError("TIME_VALUE")
        previous = {}
        for proof in sorted(
            self.availability,
            key=lambda row: (row.source_product, row.source_warehouse, row.start_at),
        ):
            key = (proof.source_product, proof.source_warehouse)
            known_until = proof.start_at
            for period in pair_periods.get(key, ()):
                start = business_day_bounds(period.valid_from, self.business_timezone)[0]
                stop = business_day_bounds(period.valid_to, self.business_timezone)[0]
                if stop <= known_until:
                    continue
                if start > known_until:
                    break
                known_until = max(known_until, stop)
                if known_until >= proof.end_at:
                    break
            if known_until < proof.end_at:
                raise PipelineError("UNKNOWN_MAPPING")
            if key in previous and previous[key] > proof.start_at:
                raise PipelineError("SOURCE_OVERLAP")
            previous[key] = proof.end_at
        return self


class EventRecord(Contract):
    event_id: Identifier
    source_product: Identifier
    source_warehouse: Identifier
    unit: Unit
    kind: Identifier
    quantity: int = Field(ge=1, le=MAX_EVENT_QUANTITY)
    occurred_at: AwareTime
    available_at: AwareTime | None


class DailyRecord(Contract):
    observation_id: Identifier
    source_product: Identifier
    source_warehouse: Identifier
    unit: Unit
    business_date: BusinessDate
    quantity: int | None = Field(ge=0, le=MAX_DAILY_QUANTITY)
    coverage: Coverage
    available_at: AwareTime | None

    @model_validator(mode="after")
    def quantity_coverage(self):
        if (
            (self.coverage == "complete" and self.quantity is None)
            or (self.coverage == "partial" and self.quantity == 0)
            or (self.coverage == "unknown" and self.quantity is not None)
        ):
            raise ValueError("quantity and coverage disagree")
        return self


class SoftwareIdentity(Contract):
    python_version: str
    packages: dict[str, str]
    implementation_sha256: Checksum

    @model_validator(mode="after")
    def packages_required(self):
        if set(self.packages) != {"pydantic", "SQLAlchemy", "psycopg", "tzdata"}:
            raise ValueError("exact package identities required")
        return self


class Issue(Contract):
    code: Identifier
    input_index: int | None = Field(ge=0)
    row_number: int | None = Field(ge=1)


class QualityReport(Contract):
    input_rows: int = Field(ge=0, le=MAX_ROWS)
    accepted_rows: int = Field(ge=0, le=MAX_ROWS)
    duplicate_rows: int = Field(ge=0, le=MAX_ROWS)
    excluded_rows: int = Field(ge=0, le=MAX_ROWS)
    rejected_rows: int = Field(ge=0, le=MAX_ROWS)
    exclusions: dict[Identifier, int]
    issues: tuple[Issue, ...]
    warnings: tuple[Identifier, ...]

    @model_validator(mode="after")
    def reconcile(self):
        if (
            self.input_rows
            != self.accepted_rows + self.duplicate_rows + self.excluded_rows + self.rejected_rows
            or any(value < 0 for value in self.exclusions.values())
            or sum(self.exclusions.values()) != self.excluded_rows
        ):
            raise ValueError("accounting must reconcile")
        return self


class SourceBatch(Contract):
    source_checksum: Checksum
    records: tuple[EventRecord | DailyRecord, ...]
    report: QualityReport
    _positions: tuple[tuple[int, int], ...] = PrivateAttr(default=())
    _input_root: Path | None = PrivateAttr(default=None)


class DailyObservation(Contract):
    product_key: Identifier
    warehouse_key: Identifier
    unit: Unit
    business_date: BusinessDate
    observed_quantity: int | None = Field(ge=0, le=MAX_DAILY_QUANTITY)
    target_quantity: int | None = Field(ge=0, le=MAX_DAILY_QUANTITY)
    coverage: Coverage
    lifecycle: Lifecycle
    availability: Literal["unknown", "stockout_observed", "covered_positive"]
    censoring_risk: Literal["unknown", "potential", "not_indicated"]
    available_at: AwareTime | None
    quality_flags: tuple[Identifier, ...]

    @model_validator(mode="after")
    def observed_not_latent_target(self):
        usable = self.coverage == "complete" and self.lifecycle == "active"
        if usable:
            if self.observed_quantity is None or self.target_quantity != self.observed_quantity:
                raise ValueError("complete active target must equal observed quantity")
        elif self.target_quantity is not None:
            raise ValueError("unobserved target must be unknown")
        if self.observed_quantity == 0 and not usable:
            raise ValueError("zero requires complete active evidence")
        expected_risk = (
            (
                "potential"
                if self.availability == "stockout_observed"
                else ("not_indicated" if self.availability == "covered_positive" else "unknown")
            )
            if self.coverage == "complete"
            else "unknown"
        )
        if self.censoring_risk != expected_risk:
            raise ValueError("risk must reflect coverage and availability")
        return self


class PreparedDataset(Contract):
    _input_root: Path | None = PrivateAttr(default=None)
    admission_semantics: dict
    normalized_records: tuple[dict, ...]
    observations: tuple[DailyObservation, ...]
    quality: QualityReport
    source_checksum: Checksum
    software: SoftwareIdentity


class PublishedBundle(Contract):
    data_version: Annotated[str, Field(pattern=r"^ddv[12]-[0-9a-f]{64}$")]
    path: Path
    reused: bool


# Separate typed boundary for reported measurements, not physical fulfillment.
MeasurementStatus = Literal[
    "eligible", "negative_reported_sales", "missing_formula_operand", "absent_report"
]
PartitionName = Literal["train", "validation", "final_holdout"]
MEVGAL_ARCHIVE_SHA256 = "9d0f83c61ef7fd3663fa61f2009e0474fbbd132ab0168b2fd3064ee9e4d353c9"
MEVGAL_MEMBER_SHA256 = {
    "mevgal-product2-2020": "ab1ec152ccc8245131b6e0f3b8d0cb267e3a0eb108c2e6ce3cb297505271090a",
    "mevgal-product2-2021": "ac8f4f9ae05c904f159d5e85cf3abc5048d6e72708bfa980dde180268ce1c9bd",
    "mevgal-product2-2022": "c7b7165dd97723150d9d5776146799a2152eadbe3286117b903ce999e5f7f91b",
}
REPORTED_WARNINGS = frozenset(
    {
        "REPORTED_SALES_ONLY",
        "NO_FULFILLMENT_CLAIM",
        "NOT_LATENT_DEMAND",
        "COMPANY_AGGREGATE",
        "CONDITIONAL_NONNEGATIVE_TARGET",
        "RETROSPECTIVE_FINAL_VINTAGE",
        "HISTORICAL_AS_OF_NOT_VERIFIED",
        "SOURCE_TIMEZONE_UNKNOWN",
        "AVAILABILITY_UNKNOWN",
        "CENSORING_UNKNOWN",
        "HOLDOUT_QUALITY_INSPECTED",
    }
)


class ReportedSalesMapping(Contract):
    source_product: Identifier
    source_reporting_entity: Identifier
    product_key: Identifier
    reporting_entity_key: Identifier
    unit: Unit
    valid_from: BusinessDate
    valid_to: BusinessDate
    available_at: AwareTime

    @model_validator(mode="after")
    def positive_period(self):
        if self.valid_from >= self.valid_to:
            raise PipelineError("TIME_VALUE")
        return self


class MevgalPreparationConfig(Contract):
    schema_version: Literal["mevgal-preparation/1"]
    dataset_class: Literal["fixture", "research"]
    rights: Rights
    acquired_at: AwareTime
    qualified_at: AwareTime
    cutoff: AwareTime

    @model_validator(mode="after")
    def knowledge_bounds(self):
        if not (
            self.acquired_at <= self.qualified_at <= self.cutoff
            and self.rights.approved_at <= self.qualified_at
            and self.qualified_at.astimezone(UTC).date() > date(2023, 4, 21)
        ):
            raise PipelineError("AFTER_CUTOFF")
        return self


class ReportedPartition(Contract):
    name: PartitionName
    start: BusinessDate
    end: BusinessDate


class ReportedBenchmarkProtocol(Contract):
    version: Literal["reported-sales-protocol/1"]
    knowledge_time_mode: Literal["retrospective_final_vintage"]
    calendar: Literal["publisher_gregorian_date"]
    partitions: tuple[ReportedPartition, ...]
    horizons: tuple[int, ...]
    history_days: int
    imputation: Literal["none"]
    missing_policy: Literal["retain_null_mask"]

    @model_validator(mode="after")
    def fixed_protocol(self):
        expected = tuple(
            (name, date(year, 1, 1), date(year + 1, 1, 1))
            for name, year in (("train", 2020), ("validation", 2021), ("final_holdout", 2022))
        )
        if (
            tuple((p.name, p.start, p.end) for p in self.partitions) != expected
            or self.horizons != (1, 7)
            or self.history_days != 28
        ):
            raise PipelineError("ADMISSION_INVALID")
        return self


class ReportedSourceEvidence(Contract):
    source_ref: Identifier
    cohort: Identifier
    archive_sha256: Checksum
    member_sha256: dict[Identifier, Checksum]
    normalized_input_sha256: Checksum
    preparation_config_sha256: Checksum
    provenance_sha256: Checksum
    acquired_at: AwareTime
    qualified_at: AwareTime

    @model_validator(mode="after")
    def known_members(self):
        if (
            set(self.member_sha256) != set(MEVGAL_MEMBER_SHA256)
            or self.acquired_at > self.qualified_at
        ):
            raise PipelineError("ADMISSION_INVALID")
        return self


def validate_reported_policy(value):
    """Shared public fields only; private file checks stay in the private model."""
    source, evidence = value.source, value.source_evidence
    if (
        source.kind != "files"
        or source.representation != "daily"
        or source.channel != "reported_daily_sales"
        or source.kind_map
        or source.outside_target_kinds
        or source.available_at_upper_bound != evidence.qualified_at
        or not source.availability_policy_ref
        or value.window_start != date(2020, 1, 1)
        or value.window_end != date(2023, 1, 1)
        or not value.mappings
        or len(value.mappings) > MAX_ROWS
    ):
        raise PipelineError("ADMISSION_INVALID")
    MevgalPreparationConfig(
        schema_version="mevgal-preparation/1",
        dataset_class=value.dataset_class,
        rights=value.rights,
        acquired_at=evidence.acquired_at,
        qualified_at=evidence.qualified_at,
        cutoff=value.cutoff,
    )
    expected_source = (
        ("zenodo:7853252", "mevgal-product2-v1")
        if value.dataset_class == "research"
        else ("synthetic:mevgal-layout", "fixture:mevgal-product2-v1")
    )
    if (evidence.source_ref, evidence.cohort) != expected_source:
        raise PipelineError("ADMISSION_INVALID")
    if value.dataset_class == "research" and (
        evidence.archive_sha256 != MEVGAL_ARCHIVE_SHA256
        or evidence.member_sha256 != MEVGAL_MEMBER_SHA256
    ):
        raise PipelineError("INPUT_HASH_MISMATCH")
    if source.snapshot_id != "mevgal-product2-v1:" + evidence.provenance_sha256:
        raise PipelineError("ADMISSION_INVALID")
    periods, aliases = {}, {}
    for mapping in sorted(value.mappings, key=lambda row: row.valid_from):
        if mapping.available_at != evidence.qualified_at or mapping.available_at > value.cutoff:
            raise PipelineError("AFTER_CUTOFF")
        if not value.window_start <= mapping.valid_from < mapping.valid_to <= value.window_end:
            raise PipelineError("TIME_VALUE")
        if (
            mapping.source_product,
            mapping.source_reporting_entity,
            mapping.product_key,
            mapping.reporting_entity_key,
            mapping.unit,
        ) != ("product2", "mevgal", "mevgal:product2", "mevgal:company", "unit"):
            raise PipelineError("UNKNOWN_MAPPING")
        for prior, key in (
            (periods, (mapping.source_product, mapping.source_reporting_entity)),
            (aliases, (mapping.product_key, mapping.reporting_entity_key, mapping.unit)),
        ):
            if key in prior and prior[key] > mapping.valid_from:
                raise PipelineError("SOURCE_OVERLAP")
            prior[key] = mapping.valid_to
    if sum((m.valid_to - m.valid_from).days for m in value.mappings) != 1096:
        raise PipelineError("UNKNOWN_MAPPING")
    return value


class ReportedSalesAdmission(Contract):
    _input_bytes: int = PrivateAttr(default=0)
    _admission_path: str | None = PrivateAttr(default=None)
    schema_version: Literal["demand-data/2"]
    target: Literal["reported_daily_unit_sales"]
    dataset_class: Literal["fixture", "research"]
    source: SourceSpec
    window_start: BusinessDate
    window_end: BusinessDate
    cutoff: AwareTime
    mappings: tuple[ReportedSalesMapping, ...]
    rights: Rights
    protocol: ReportedBenchmarkProtocol
    source_evidence: ReportedSourceEvidence

    @model_validator(mode="after")
    def reported_policy(self):
        if (
            len(self.source.files) != 1
            or self.source.files[0].format != "jsonl"
            or self.source.files[0].sha256 != self.source_evidence.normalized_input_sha256
        ):
            raise PipelineError("ADMISSION_INVALID")
        return validate_reported_policy(self)


class ReportedSalesRecord(Contract):
    observation_id: Identifier
    source_product: Identifier
    source_reporting_entity: Identifier
    unit: Unit
    business_date: BusinessDate
    source_member: Identifier
    source_row: int = Field(ge=2, le=MAX_ROWS + 1)
    reported_quantity: int = Field(ge=-MAX_DAILY_QUANTITY, le=MAX_DAILY_QUANTITY)
    formula_kind: Literal["literal", "same_row_divide_one"]
    formula_operand: int | None = Field(ge=-MAX_DAILY_QUANTITY, le=MAX_DAILY_QUANTITY)
    measurement_status: Literal["eligible", "negative_reported_sales", "missing_formula_operand"]
    available_at: AwareTime

    @model_validator(mode="after")
    def evidence_matches_status(self):
        if self.formula_kind == "literal":
            if self.formula_operand is not None:
                raise ValueError("literal cannot have an operand")
            status = "negative_reported_sales" if self.reported_quantity < 0 else "eligible"
        elif self.formula_operand is None:
            if self.reported_quantity != 0:
                raise ValueError("blank operand requires cached zero")
            status = "missing_formula_operand"
        else:
            if self.formula_operand != self.reported_quantity:
                raise ValueError("cache and operand differ")
            status = "negative_reported_sales" if self.reported_quantity < 0 else "eligible"
        if (
            self.measurement_status != status
            or self.source_member != f"mevgal-product2-{self.business_date.year}"
        ):
            raise ValueError("source/status mismatch")
        return self


class ReportedSalesBatch(Contract):
    source_checksum: Checksum
    records: tuple[ReportedSalesRecord, ...] = Field(max_length=MAX_ROWS)
    report: QualityReport
    _positions: tuple[tuple[int, int], ...] = PrivateAttr(default=())
    _input_root: Path | None = PrivateAttr(default=None)


class ReportedSalesObservation(Contract):
    product_key: Identifier
    reporting_entity_key: Identifier
    reporting_entity_scope: Literal["company_aggregate"]
    unit: Unit
    business_date: BusinessDate
    observed_quantity: int | None = Field(ge=0, le=MAX_DAILY_QUANTITY)
    target_quantity: int | None = Field(ge=0, le=MAX_DAILY_QUANTITY)
    measurement_status: MeasurementStatus
    reporting_coverage: Literal["reported", "unknown"]
    lifecycle: Literal["unknown"]
    availability: Literal["unknown"]
    censoring_risk: Literal["unknown"]
    available_at: AwareTime
    quality_flags: tuple[Identifier, ...]

    @model_validator(mode="after")
    def reported_not_physical(self):
        eligible = self.measurement_status == "eligible"
        if eligible:
            if self.observed_quantity is None or self.target_quantity != self.observed_quantity:
                raise ValueError("eligible label must equal observed report")
        elif self.observed_quantity is not None or self.target_quantity is not None:
            raise ValueError("ineligible label must be null")
        coverage = (
            "reported"
            if self.measurement_status in ("eligible", "negative_reported_sales")
            else "unknown"
        )
        if self.reporting_coverage != coverage:
            raise ValueError("reporting coverage mismatch")
        return self


class ReportedWindowCounts(Contract):
    target_only: int = Field(ge=0, le=MAX_SERIES_DAYS)
    complete_history_and_target: int = Field(ge=0, le=MAX_SERIES_DAYS)


class ReportedPartitionCounts(Contract):
    calendar_days: int = Field(ge=0, le=MAX_SERIES_DAYS)
    eligible_labels: int = Field(ge=0, le=MAX_SERIES_DAYS)
    genuine_zeros: int = Field(ge=0, le=MAX_SERIES_DAYS)
    eligible_sum: int = Field(ge=0, le=MAX_DAILY_QUANTITY)
    horizons: dict[Literal["1", "7"], ReportedWindowCounts]

    @model_validator(mode="after")
    def exact_horizons(self):
        if set(self.horizons) != {"1", "7"}:
            raise ValueError("exact horizons required")
        return self


class ReportedSalesQuality(QualityReport):
    measurement_counts: dict[MeasurementStatus, Annotated[int, Field(ge=0, le=MAX_SERIES_DAYS)]]
    partition_counts: dict[PartitionName, ReportedPartitionCounts]

    @model_validator(mode="after")
    def exact_accounting(self):
        if set(self.measurement_counts) != {
            "eligible",
            "negative_reported_sales",
            "missing_formula_operand",
            "absent_report",
        } or set(self.partition_counts) != {"train", "validation", "final_holdout"}:
            raise ValueError("exact accounting required")
        return self


class ReportedSalesPreparedDataset(Contract):
    admission_semantics: dict
    normalized_records: tuple[dict, ...]
    observations: tuple[ReportedSalesObservation, ...]
    quality: ReportedSalesQuality
    source_checksum: Checksum
    software: SoftwareIdentity
    _input_root: Path | None = PrivateAttr(default=None)
