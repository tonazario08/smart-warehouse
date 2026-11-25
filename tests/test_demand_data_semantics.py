from datetime import UTC, date, datetime, timedelta

import pytest

from app.analytics.schemas import DailyRecord, PipelineError
from app.analytics.semantics import prepare_dataset
from tests.demand_data_helpers import (
    admission,
    admission_values,
    batch,
    daily_values,
    day_proof,
    event,
    instant,
    software,
)


def prepare(parsed=None, *records):
    return prepare_dataset(parsed or admission(), batch(*records), software())


def test_m4_linkage_is_one_target_not_request_plus_outbound():
    prepared = prepare(None, event(event_id="tx:12"))
    assert prepared.observations[0].target_quantity == 3
    assert len(prepared.normalized_records) == 1
    assert prepared.quality.accepted_rows == 1
    assert prepared.admission_semantics["dataset_class"] == "fixture"
    assert "files" not in prepared.admission_semantics["source"]
    assert "database_identity" not in prepared.admission_semantics["source"]


def test_transfer_return_adjustment_test_exclusions():
    kinds = (
        "inbound",
        "transfer_in",
        "transfer_out",
        "return",
        "adjustment",
        "cancellation",
        "test",
    )
    prepared = prepare(None, event(), *(event(event_id=f"e-{kind}", kind=kind) for kind in kinds))
    assert prepared.observations[0].target_quantity == 3
    assert prepared.quality.input_rows == 8
    assert prepared.quality.accepted_rows == 1
    assert prepared.quality.excluded_rows == 7
    assert prepared.quality.rejected_rows == 0
    assert sum(prepared.quality.exclusions.values()) == 7


def test_unknown_purpose_never_certifies_zero():
    prepared = prepare(None, event(kind="unknown"))
    row = prepared.observations[0]
    assert (row.observed_quantity, row.target_quantity, row.coverage) == (None, None, "unknown")
    assert "UNKNOWN_CLASSIFICATION" in row.quality_flags
    assert prepared.quality.accepted_rows == 1
    values = admission_values()
    values["source"]["outside_target_kinds"] = ("unknown",)
    from app.analytics.schemas import Admission

    prepared = prepare(Admission(**values), event(kind="unknown"))
    assert prepared.observations[0].target_quantity == 0
    assert prepared.quality.excluded_rows == 1


def test_complete_zero_missing_partial_and_inactive():
    values = admission_values()
    values["mappings"] = tuple(
        {**values["mappings"][0], "source_product": f"p{i}", "product_key": key, "lifecycle": life}
        for i, key, life in [
            (1, "complete", "active"),
            (2, "missing", "active"),
            (3, "partial", "active"),
            (4, "inactive", "inactive"),
        ]
    )
    values["coverage"] = tuple(
        {**values["coverage"][0], "source_product": f"p{i}", "status": status}
        for i, status in [(1, "complete"), (3, "partial"), (4, "complete")]
    )
    from app.analytics.schemas import Admission

    rows = {
        row.product_key: row
        for row in prepare(
            Admission(**values),
            event(source_product="p3"),
            event(source_product="p4", event_id="e-4"),
        ).observations
        if row.business_date == date(2026, 10, 19)
    }
    assert (rows["complete"].observed_quantity, rows["complete"].target_quantity) == (0, 0)
    assert (rows["missing"].observed_quantity, rows["missing"].target_quantity) == (None, None)
    assert (rows["partial"].observed_quantity, rows["partial"].target_quantity) == (3, None)
    assert rows["inactive"].observed_quantity == 3
    assert rows["inactive"].target_quantity is None


def test_unit_period_and_prelaunch_bounds():
    values = admission_values()
    original = values["mappings"][0]
    values["mappings"] = (
        {**original, "valid_from": date(2026, 10, 20), "valid_to": date(2026, 10, 21)},
        {**original, "valid_from": date(2026, 10, 21), "unit": "box"},
    )
    values["coverage"] = tuple(
        proof for proof in values["coverage"] if proof["business_date"] >= date(2026, 10, 20)
    )
    from app.analytics.schemas import Admission

    rows = prepare(Admission(**values)).observations
    assert [(row.business_date, row.unit) for row in rows] == [
        (date(2026, 10, 21), "box"),
        (date(2026, 10, 20), "cái"),
    ]


@pytest.mark.parametrize("proof", [False, True])
def test_late_availability_aborts_instead_of_zero(proof):
    if proof:
        values = admission_values()
        values["coverage"] = ({**values["coverage"][0], "available_at": instant(24)},)
        from app.analytics.schemas import Admission

        parsed, records = Admission(**values), ()
    else:
        parsed, records = admission(), (event(available_at=instant(24)),)
    with pytest.raises(PipelineError, match="AFTER_CUTOFF"):
        prepare(parsed, *records)


def test_stockout_is_risk_not_lost_demand():
    parsed = admission(availability=(day_proof(date(2026, 10, 19), "stockout"),))
    row = prepare(parsed, event()).observations[0]
    assert (row.availability, row.censoring_risk) == ("stockout_observed", "potential")
    assert "lost_demand_quantity" not in row.model_dump()
    parsed = admission(coverage=(), availability=(day_proof(date(2026, 10, 19), "stockout"),))
    with pytest.raises(PipelineError, match="NO_OBSERVED_TARGETS"):
        prepare(parsed, event())


def test_positive_availability_must_cover_the_entire_day():
    proof = day_proof(date(2026, 10, 19))
    full = prepare(admission(availability=(proof,)), event()).observations[0]
    assert (full.availability, full.censoring_risk) == ("covered_positive", "not_indicated")
    gap = {**proof, "end_at": proof["end_at"] - timedelta(seconds=1)}
    row = prepare(admission(availability=(gap,)), event()).observations[0]
    assert (row.availability, row.censoring_risk) == ("unknown", "unknown")


def test_all_zero_short_empty_outcomes():
    prepared = prepare()
    assert [row.target_quantity for row in prepared.observations] == [0, 0, 0]
    assert "ALL_ZERO_SERIES" in prepared.quality.warnings
    with pytest.raises(PipelineError, match="NO_OBSERVED_TARGETS"):
        prepare(admission(mappings=(), coverage=()))


def test_missing_knowledge_requires_policy_bound_and_impossible_chronology_fails():
    with pytest.raises(PipelineError, match="AVAILABILITY_TIME_REQUIRED"):
        prepare(None, event(available_at=None))
    with pytest.raises(PipelineError, match="TIME_VALUE"):
        prepare(None, event(available_at=instant(18)))
    values = admission_values()
    values["source"].update(
        available_at_upper_bound=instant(20), availability_policy_ref="recording-policy"
    )
    from app.analytics.schemas import Admission

    result = prepare(Admission(**values), event(available_at=None))
    assert result.observations[0].available_at == instant(20)


def test_daily_observations_keep_zero_partial_and_unknown_without_fake_events():
    values = admission_values(coverage=())
    values["source"]["representation"] = "daily"
    from app.analytics.schemas import Admission

    prepared = prepare(
        Admission(**values),
        DailyRecord(**daily_values()),
        DailyRecord(
            **daily_values(
                observation_id="d2",
                quantity=3,
                business_date=date(2026, 10, 20),
                coverage="partial",
                available_at=instant(21),
            )
        ),
    )
    assert [(row.observed_quantity, row.target_quantity) for row in prepared.observations] == [
        (0, 0),
        (3, None),
        (None, None),
    ]
    assert "event_id" not in prepared.normalized_records[0]
    assert "occurred_at" not in prepared.normalized_records[0]


def test_timezone_day_is_not_utc_date_and_offset_is_retained():
    record = event(occurred_at="2026-10-20T00:00:00+07:00", available_at=instant(20))
    prepared = prepare(None, record)
    assert [row.target_quantity for row in prepared.observations] == [0, 3, 0]
    assert prepared.normalized_records[0]["original_offset_seconds"] == 25200
    assert prepared.normalized_records[0]["occurred_at"] == datetime(2026, 10, 19, 17, tzinfo=UTC)


def test_future_outside_window_rows_only_contribute_safe_exclusion_counts():
    prepared = prepare(
        None, event(event_id="future-leak", occurred_at=instant(24), available_at=instant(25))
    )
    assert prepared.normalized_records == ()
    assert prepared.quality.exclusions == {"OUTSIDE_WINDOW": 1}
    assert prepared.quality.excluded_rows == 1
    assert prepared.quality.accepted_rows == 0
    assert [row.target_quantity for row in prepared.observations] == [0, 0, 0]


@pytest.mark.parametrize(
    "proof_kind,bad_pair,bad_period",
    [
        ("coverage", True, False),
        ("coverage", False, True),
        ("availability", True, False),
        ("availability", False, True),
    ],
)
def test_unmapped_or_outside_period_evidence_is_not_silently_ignored(
    proof_kind,
    bad_pair,
    bad_period,
):
    from app.analytics.schemas import Admission

    values = admission_values()
    if proof_kind == "coverage":
        extra = {**values["coverage"][0]}
        if bad_pair:
            extra["source_product"] = "not-mapped"
        if bad_period:
            extra.update(business_date=date(2026, 10, 18), available_at=instant(19))
        values["coverage"] = (*values["coverage"], extra)
    else:
        extra = day_proof(date(2026, 10, 18) if bad_period else date(2026, 10, 19))
        if bad_pair:
            extra["source_warehouse"] = "not-mapped"
        values["availability"] = (extra,)
    with pytest.raises(PipelineError, match="UNKNOWN_MAPPING"):
        prepare(Admission(**values))


def test_partial_recorded_vends_publish_no_forecast_targets():
    from app.analytics.schemas import Admission
    from tests.demand_data_helpers import recorded_admission_values, vend_values

    result = prepare_dataset(
        Admission(**recorded_admission_values()), batch(DailyRecord(**vend_values())), software()
    )
    assert result.admission_semantics["rules_version"] == "demand-rules/2"
    assert [row.observed_quantity for row in result.observations] == [3, None, None]
    assert all(row.target_quantity is None for row in result.observations)
    assert all(
        row.lifecycle == "unknown"
        and row.availability == "unknown"
        and row.censoring_risk == "unknown"
        for row in result.observations
    )
    assert set(result.quality.warnings) == {
        "RECORDED_VENDS_ONLY",
        "NO_FULFILLMENT_CLAIM",
        "NOT_FORECAST_READY",
        "NO_COMPLETE_TARGETS",
    }


def test_missing_vend_days_stay_unknown_even_with_active_mapping():
    from app.analytics.schemas import Admission
    from tests.demand_data_helpers import recorded_admission_values, vend_values

    values = recorded_admission_values()
    values["mappings"] = tuple({**row, "lifecycle": "active"} for row in values["mappings"])
    result = prepare_dataset(Admission(**values), batch(DailyRecord(**vend_values())), software())
    assert [(r.coverage, r.observed_quantity, r.target_quantity) for r in result.observations] == [
        ("partial", 3, None),
        ("unknown", None, None),
        ("unknown", None, None),
    ]


@pytest.mark.parametrize("unknown_row", [False, True])
def test_recorded_vends_empty_input_still_fails(unknown_row):
    from app.analytics.schemas import Admission
    from tests.demand_data_helpers import recorded_admission_values, vend_values

    records = (
        (DailyRecord(**vend_values(coverage="unknown", quantity=None, available_at=None)),)
        if unknown_row
        else ()
    )
    with pytest.raises(PipelineError, match="NO_OBSERVED_TARGETS"):
        prepare_dataset(Admission(**recorded_admission_values()), batch(*records), software())


def test_gross_partial_input_still_has_no_observed_targets():
    values = admission_values(coverage=())
    values["source"]["representation"] = "daily"
    from app.analytics.schemas import Admission

    with pytest.raises(PipelineError, match="NO_OBSERVED_TARGETS"):
        prepare_dataset(
            Admission(**values),
            batch(DailyRecord(**daily_values(coverage="partial", quantity=3))),
            software(),
        )


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"available_at": None}, "AVAILABILITY_TIME_REQUIRED"),
        ({"available_at": instant(24)}, "AFTER_CUTOFF"),
        ({"source_product": "unmapped"}, "UNKNOWN_MAPPING"),
    ],
)
def test_recorded_vends_does_not_bypass_knowledge_or_mapping(changes, code):
    from app.analytics.schemas import Admission
    from tests.demand_data_helpers import recorded_admission_values, vend_values

    with pytest.raises(PipelineError, match=code):
        prepare_dataset(
            Admission(**recorded_admission_values()),
            batch(DailyRecord(**vend_values(**changes))),
            software(),
        )


def test_reported_labels_do_not_require_invented_active_lifecycle():
    from app.analytics.semantics import prepare_dataset
    from tests.demand_data_helpers import reported_inputs, reported_rows, software

    rows = reported_rows()
    rows[0]["reported_quantity"] = 0
    parsed, batch = reported_inputs(rows)
    result = prepare_dataset(parsed, batch, software())
    assert len(result.observations) == 1096
    assert result.observations[0].target_quantity == 0
    assert all(
        row.lifecycle == row.availability == row.censoring_risk == "unknown"
        for row in result.observations
    )
    assert result.quality.partition_counts["train"].eligible_sum == 730
    assert result.quality.measurement_counts == {
        "eligible": 1096,
        "negative_reported_sales": 0,
        "missing_formula_operand": 0,
        "absent_report": 0,
    }
    assert {
        "REPORTED_SALES_ONLY",
        "RETROSPECTIVE_FINAL_VINTAGE",
        "HISTORICAL_AS_OF_NOT_VERIFIED",
        "HOLDOUT_QUALITY_INSPECTED",
    } <= set(result.quality.warnings)


def test_reported_absent_negative_and_blank_days_have_distinct_masks():
    from app.analytics.semantics import prepare_dataset
    from tests.demand_data_helpers import reported_inputs, reported_rows, software

    rows = reported_rows()
    rows[1].update(reported_quantity=-10, measurement_status="negative_reported_sales")
    rows[2].update(
        reported_quantity=0,
        formula_kind="same_row_divide_one",
        measurement_status="missing_formula_operand",
    )
    del rows[3]
    result = prepare_dataset(*reported_inputs(rows), software())
    assert (
        result.quality.accepted_rows == 1095
        and result.quality.excluded_rows == result.quality.rejected_rows == 0
    )
    assert result.quality.measurement_counts == {
        "eligible": 1093,
        "negative_reported_sales": 1,
        "missing_formula_operand": 1,
        "absent_report": 1,
    }
    assert [o.measurement_status for o in result.observations[:4]] == [
        "eligible",
        "negative_reported_sales",
        "missing_formula_operand",
        "absent_report",
    ]
    assert [o.reporting_coverage for o in result.observations[:4]] == [
        "reported",
        "reported",
        "unknown",
        "unknown",
    ]
    assert all(
        o.observed_quantity is None and o.target_quantity is None for o in result.observations[1:4]
    )
    assert len(result.normalized_records) == 1095


def test_reported_protocol_uses_calendar_history_and_partition_targets():
    from datetime import date

    from app.analytics.semantics import prepare_dataset
    from tests.demand_data_helpers import reported_inputs, reported_rows, software

    complete = prepare_dataset(*reported_inputs(), software()).quality.partition_counts
    assert complete["train"].horizons["1"].target_only == 366
    assert complete["train"].horizons["7"].target_only == 360
    assert complete["train"].horizons["1"].complete_history_and_target == 338
    assert complete["train"].horizons["7"].complete_history_and_target == 332
    assert complete["validation"].horizons["7"].complete_history_and_target == 359
    rows = [r for r in reported_rows() if r["business_date"] != date(2020, 12, 31)]
    counts = prepare_dataset(*reported_inputs(rows), software()).quality.partition_counts
    # Only Dec25..Dec31 is lost: later seven-day blocks would cross the partition.
    assert counts["train"].horizons["7"].complete_history_and_target == 331
    assert counts["validation"].horizons["1"].complete_history_and_target == 337
    assert counts["validation"].horizons["7"].target_only == 359
    assert counts["validation"].horizons["7"].complete_history_and_target == 331


def test_reported_empty_partition_cannot_claim_readiness():
    from app.analytics.semantics import prepare_dataset
    from tests.demand_data_helpers import reported_inputs, reported_rows, software

    rows = [r for r in reported_rows() if r["business_date"].year != 2021]
    with pytest.raises(PipelineError, match="NO_OBSERVED_TARGETS"):
        prepare_dataset(*reported_inputs(rows), software())


def test_reported_future_knowledge_never_uses_historical_origin_time():
    from app.analytics.semantics import prepare_dataset
    from tests.demand_data_helpers import instant, reported_inputs, reported_rows, software

    rows = reported_rows()
    rows[0]["available_at"] = instant(24)
    with pytest.raises(PipelineError, match="AFTER_CUTOFF"):
        prepare_dataset(*reported_inputs(rows), software())
