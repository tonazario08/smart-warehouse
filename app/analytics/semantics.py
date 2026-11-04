"""Pure gross-fulfillment, observation-coverage and as-of projection."""

import json
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta

from app.analytics.ingestion import validate_batch
from app.analytics.schemas import (
    MAX_DAILY_QUANTITY,
    RECORDED_VEND_WARNINGS,
    REPORTED_WARNINGS,
    Admission,
    DailyObservation,
    DailyRecord,
    Issue,
    PipelineError,
    PreparedDataset,
    QualityReport,
    ReportedPartitionCounts,
    ReportedSalesAdmission,
    ReportedSalesObservation,
    ReportedSalesPreparedDataset,
    ReportedSalesQuality,
    SoftwareIdentity,
    SourceBatch,
    business_day_bounds,
    load_timezone,
)


def semantic_value(value):
    """Normalize instants, not wall-clock runs or private source locations."""
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: semantic_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [semantic_value(item) for item in value]
    return value


def admission_semantics(admission):
    value = admission.model_dump()
    value["source"].pop("files")
    value["source"].pop("database_identity")
    value = semantic_value(value)
    reported = isinstance(admission, ReportedSalesAdmission)
    for key in ("mappings",) if reported else ("mappings", "coverage", "availability"):
        value[key].sort(key=lambda item: json.dumps(item, sort_keys=True, ensure_ascii=False))
    value["source"]["outside_target_kinds"].sort()
    value["rules_version"] = (
        "demand-rules/3"
        if reported
        else "demand-rules/2"
        if admission.target == "recorded_vend_units"
        else "demand-rules/1"
    )
    return value


def prepare_dataset(
    admission: Admission, batch: SourceBatch, software: SoftwareIdentity
) -> PreparedDataset:
    if isinstance(admission, ReportedSalesAdmission):
        return prepare_reported_dataset(admission, batch, software)
    batch = validate_batch(admission, batch)
    zone = load_timezone(admission.business_timezone)
    accepted, rejected = batch.report.accepted_rows, 0
    exclusions, warnings = Counter(), set(batch.report.warnings)
    totals, knowledge = defaultdict(int), defaultdict(list)
    unknown, daily, normalized = set(), {}, []
    proof_times = defaultdict(list)

    def report(issues=()):
        return QualityReport(
            input_rows=batch.report.input_rows,
            accepted_rows=accepted,
            duplicate_rows=batch.report.duplicate_rows,
            excluded_rows=sum(exclusions.values()),
            rejected_rows=rejected,
            exclusions=dict(sorted(exclusions.items())),
            issues=tuple(issues),
            warnings=tuple(sorted(warnings)),
        )

    def knowledge_time(value, earliest, *, allow_unknown=False):
        value = value or admission.source.available_at_upper_bound
        if value is None:
            if allow_unknown:
                return None
            raise PipelineError("AVAILABILITY_TIME_REQUIRED")
        if value < earliest:
            raise PipelineError("TIME_VALUE")
        if value > admission.cutoff:
            raise PipelineError("AFTER_CUTOFF")
        return value

    try:
        for proof in (*admission.mappings, *admission.coverage, *admission.availability):
            if proof.available_at > admission.cutoff:
                raise PipelineError("AFTER_CUTOFF")
        for offset, record in enumerate(batch.records):
            try:
                is_daily = isinstance(record, DailyRecord)
                day = (
                    record.business_date if is_daily else record.occurred_at.astimezone(zone).date()
                )
                values = record.model_dump()
                original = record.available_at if is_daily else record.occurred_at
                values["original_offset_seconds"] = (
                    int(original.utcoffset().total_seconds()) if original else None
                )
                if not admission.window_start <= day < admission.window_end:
                    exclusions["OUTSIDE_WINDOW"] += 1
                    accepted -= 1
                    continue
                key = (record.source_product, record.source_warehouse, day)
                at = knowledge_time(
                    record.available_at,
                    business_day_bounds(day, admission.business_timezone)[1]
                    if is_daily
                    else record.occurred_at,
                    allow_unknown=is_daily and record.quantity is None,
                )
                if at:
                    knowledge[key].append(at)
                values["available_at"] = at
                if is_daily:
                    daily[key] = record
                else:
                    kind = admission.source.kind_map[record.kind]
                    values["event_kind"] = kind
                    if kind == "customer_fulfillment":
                        totals[key] += record.quantity
                        if totals[key] > MAX_DAILY_QUANTITY:
                            raise PipelineError("QUANTITY_OVERFLOW")
                    elif kind == "unclassified" and record.kind not in (
                        admission.source.outside_target_kinds
                    ):
                        unknown.add(key)
                    else:
                        exclusions[kind.upper()] += 1
                        accepted -= 1
                normalized.append(values)
            except PipelineError as error:
                accepted -= 1
                rejected += 1
                position = batch._positions[offset] if batch._positions else (0, offset + 1)
                raise PipelineError(
                    error.code,
                    report(
                        (Issue(code=error.code, input_index=position[0], row_number=position[1]),)
                    ),
                ) from None
    except PipelineError as error:
        if error.report is not None:
            raise
        raise PipelineError(
            error.code, report((Issue(code=error.code, input_index=None, row_number=None),))
        ) from None

    coverage = {
        (proof.source_product, proof.source_warehouse, proof.business_date): proof
        for proof in admission.coverage
    }
    intervals = defaultdict(list)
    for proof in admission.availability:
        intervals[(proof.source_product, proof.source_warehouse)].append(proof)
    observations = []
    for mapping in admission.mappings:
        day, end = (
            max(mapping.valid_from, admission.window_start),
            min(mapping.valid_to, admission.window_end),
        )
        while day < end:
            key = (mapping.source_product, mapping.source_warehouse, day)
            start, stop = business_day_bounds(day, admission.business_timezone)
            flags = set()
            times = [mapping.available_at, *knowledge[key], *proof_times[key]]
            if admission.source.representation == "daily":
                record = daily.get(key)
                status = record.coverage if record else "unknown"
                quantity = record.quantity if record else None
            else:
                proof = coverage.get(key)
                status = proof.status if proof else "unknown"
                if proof:
                    times.append(proof.available_at)
                quantity = totals[key] if totals[key] else (0 if status == "complete" else None)
                if key in unknown:
                    flags.add("UNKNOWN_CLASSIFICATION")
                    status = "unknown"
                    quantity = totals[key] or None
            if status != "complete":
                flags.add("PARTIAL_COVERAGE" if status == "partial" else "UNKNOWN_COVERAGE")
            if mapping.lifecycle != "active":
                flags.add(
                    "INACTIVE_LIFECYCLE" if mapping.lifecycle == "inactive" else "UNKNOWN_LIFECYCLE"
                )
                if not quantity:
                    quantity = None
            target = quantity if status == "complete" and mapping.lifecycle == "active" else None
            selected = sorted(
                (
                    proof
                    for proof in intervals[(mapping.source_product, mapping.source_warehouse)]
                    if proof.start_at < stop and proof.end_at > start
                ),
                key=lambda proof: proof.start_at,
            )
            availability = "unknown"
            if any(proof.kind == "stockout" for proof in selected):
                availability = "stockout_observed"
            else:
                covered_until = start
                for proof in selected:
                    if proof.kind != "positive" or proof.start_at > covered_until:
                        break
                    covered_until = max(covered_until, proof.end_at)
                if covered_until >= stop:
                    availability = "covered_positive"
            if selected:
                times.extend(proof.available_at for proof in selected)
            risk = (
                "potential"
                if status == "complete" and availability == "stockout_observed"
                else (
                    "not_indicated"
                    if status == "complete" and availability == "covered_positive"
                    else "unknown"
                )
            )
            observations.append(
                DailyObservation(
                    product_key=mapping.product_key,
                    warehouse_key=mapping.warehouse_key,
                    unit=mapping.unit,
                    business_date=day,
                    observed_quantity=quantity,
                    target_quantity=target,
                    coverage=status,
                    lifecycle=mapping.lifecycle,
                    availability=availability,
                    censoring_risk=risk,
                    available_at=max(times),
                    quality_flags=tuple(sorted(flags)),
                )
            )
            day += timedelta(days=1)
    targets = [row.target_quantity for row in observations if row.target_quantity is not None]
    recorded = admission.target == "recorded_vend_units"
    if (
        recorded
        and not any(row.observed_quantity and row.observed_quantity > 0 for row in observations)
    ) or (not recorded and not targets):
        raise PipelineError(
            "NO_OBSERVED_TARGETS",
            report((Issue(code="NO_OBSERVED_TARGETS", input_index=None, row_number=None),)),
        )
    if recorded:
        warnings.update(RECORDED_VEND_WARNINGS)
    elif all(quantity == 0 for quantity in targets):
        warnings.add("ALL_ZERO_SERIES")
    result = PreparedDataset(
        admission_semantics=admission_semantics(admission),
        normalized_records=tuple(
            sorted(normalized, key=lambda row: row.get("event_id", row.get("observation_id")))
        ),
        observations=tuple(
            sorted(
                observations,
                key=lambda row: (row.product_key, row.warehouse_key, row.unit, row.business_date),
            )
        ),
        quality=report(),
        source_checksum=batch.source_checksum,
        software=software,
    )
    result._input_root = batch._input_root
    return result


def prepare_reported_dataset(admission, batch, software):
    batch = validate_batch(admission, batch)
    records = {
        (r.source_product, r.source_reporting_entity, r.business_date): r for r in batch.records
    }
    observations = []
    for mapping in admission.mappings:
        day = mapping.valid_from
        while day < mapping.valid_to:
            record = records.get((mapping.source_product, mapping.source_reporting_entity, day))
            status = record.measurement_status if record else "absent_report"
            quantity = record.reported_quantity if record and status == "eligible" else None
            flags = {"UNKNOWN_LIFECYCLE", "AVAILABILITY_UNKNOWN", "CENSORING_UNKNOWN"}
            if status != "eligible":
                flags.add(status.upper())
            observations.append(
                ReportedSalesObservation(
                    product_key=mapping.product_key,
                    reporting_entity_key=mapping.reporting_entity_key,
                    reporting_entity_scope="company_aggregate",
                    unit=mapping.unit,
                    business_date=day,
                    observed_quantity=quantity,
                    target_quantity=quantity,
                    measurement_status=status,
                    reporting_coverage="reported"
                    if status in ("eligible", "negative_reported_sales")
                    else "unknown",
                    lifecycle="unknown",
                    availability="unknown",
                    censoring_risk="unknown",
                    available_at=admission.source_evidence.qualified_at,
                    quality_flags=tuple(sorted(flags)),
                )
            )
            day += timedelta(days=1)
    observations = tuple(
        sorted(
            observations,
            key=lambda r: (r.product_key, r.reporting_entity_key, r.unit, r.business_date),
        )
    )
    partitions = reported_protocol_counts(observations, admission.protocol)
    if any(
        count.complete_history_and_target == 0
        for partition in partitions.values()
        for count in partition.horizons.values()
    ):
        raise PipelineError("NO_OBSERVED_TARGETS", batch.report)
    measurement = dict.fromkeys(
        ("eligible", "negative_reported_sales", "missing_formula_operand", "absent_report"), 0
    )
    for row in observations:
        measurement[row.measurement_status] += 1
    warnings = set(REPORTED_WARNINGS)
    if admission.dataset_class != "research":
        warnings.add("NOT_RESEARCH_DATA")
    if all(row.target_quantity in (None, 0) for row in observations):
        warnings.add("ALL_ZERO_SERIES")
    quality = ReportedSalesQuality(
        **{**batch.report.model_dump(), "warnings": tuple(sorted(warnings))},
        measurement_counts=measurement,
        partition_counts=partitions,
    )
    result = ReportedSalesPreparedDataset(
        admission_semantics=admission_semantics(admission),
        normalized_records=tuple(
            r.model_dump() for r in sorted(batch.records, key=lambda r: r.observation_id)
        ),
        observations=observations,
        quality=quality,
        source_checksum=batch.source_checksum,
        software=software,
    )
    result._input_root = batch._input_root
    return result


def reported_protocol_counts(observations, protocol):
    days = {}
    for row in observations:
        if row.business_date in days:
            raise PipelineError("SOURCE_OVERLAP")
        days[row.business_date] = row
    eligible = {day for day, row in days.items() if row.measurement_status == "eligible"}
    counts = {}
    for partition in protocol.partitions:
        rows = [
            row
            for day, row in days.items()
            if partition.start <= day < partition.end and day in eligible
        ]
        total = sum(row.target_quantity for row in rows)
        if total > MAX_DAILY_QUANTITY:
            raise PipelineError("QUANTITY_OVERFLOW")
        horizons = {}
        for horizon in protocol.horizons:
            target_only = complete = 0
            first = partition.start
            while first + timedelta(days=horizon) <= partition.end:
                targets = all(first + timedelta(days=i) in eligible for i in range(horizon))
                target_only += targets
                if targets and all(
                    first - timedelta(days=i) in eligible
                    for i in range(1, protocol.history_days + 1)
                ):
                    complete += 1
                first += timedelta(days=1)
            horizons[str(horizon)] = {
                "target_only": target_only,
                "complete_history_and_target": complete,
            }
        counts[partition.name] = ReportedPartitionCounts(
            calendar_days=(partition.end - partition.start).days,
            eligible_labels=len(rows),
            genuine_zeros=sum(row.target_quantity == 0 for row in rows),
            eligible_sum=total,
            horizons=horizons,
        )
    return counts
