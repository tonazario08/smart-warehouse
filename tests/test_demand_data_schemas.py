from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.analytics.schemas import (
    MAX_DAILY_QUANTITY,
    MAX_EVENT_QUANTITY,
    Admission,
    AvailabilityInterval,
    DailyRecord,
    EventRecord,
    InputFile,
    PipelineError,
    Rights,
    business_day_bounds,
    load_timezone,
    parse_business_date,
    parse_timestamp,
)
from tests.demand_data_helpers import (
    admission,
    admission_values,
    daily_values,
    day_proof,
    event_values,
    instant,
    rights_values,
)

INVALID = (ValidationError, PipelineError)


def test_reported_contract_keeps_company_scope_and_unknown_lifecycle():
    from app.analytics.schemas import ReportedSalesObservation
    from tests.demand_data_helpers import reported_observation_values

    value = ReportedSalesObservation(**reported_observation_values())
    assert value.target_quantity == 0 and value.lifecycle == "unknown"
    for changes in (
        {"warehouse_key": "invented"},
        {"lifecycle": "active"},
        {"availability": "stockout_observed"},
        {"measurement_status": "negative_reported_sales"},
        {"target_quantity": 1},
        {"reporting_coverage": "unknown"},
    ):
        with pytest.raises(INVALID):
            ReportedSalesObservation(**reported_observation_values(**changes))
    missing = ReportedSalesObservation(
        **reported_observation_values(
            observed_quantity=None,
            target_quantity=None,
            measurement_status="absent_report",
            reporting_coverage="unknown",
        )
    )
    assert missing.observed_quantity is None


@pytest.mark.parametrize(
    "changes",
    [
        {"reported_quantity": -10},
        {"reported_quantity": 0, "formula_kind": "same_row_divide_one"},
        {"formula_kind": "same_row_divide_one", "formula_operand": 3},
        {"formula_operand": 2},
        {"reported_quantity": True},
        {"reported_quantity": 1.5},
        {"reported_quantity": MAX_DAILY_QUANTITY + 1},
        {"source_row": True},
    ],
)
def test_reported_record_status_matches_literal_or_formula_evidence(changes):
    from app.analytics.schemas import ReportedSalesRecord
    from tests.demand_data_helpers import reported_record_values

    with pytest.raises(INVALID):
        ReportedSalesRecord(**reported_record_values(**changes))


def test_reported_literal_zero_negative_and_blank_are_distinct():
    from app.analytics.schemas import ReportedSalesRecord
    from tests.demand_data_helpers import reported_record_values

    assert (
        ReportedSalesRecord(**reported_record_values(reported_quantity=0)).measurement_status
        == "eligible"
    )
    assert (
        ReportedSalesRecord(
            **reported_record_values(
                reported_quantity=-10, measurement_status="negative_reported_sales"
            )
        ).reported_quantity
        == -10
    )
    assert (
        ReportedSalesRecord(
            **reported_record_values(
                reported_quantity=0,
                formula_kind="same_row_divide_one",
                measurement_status="missing_formula_operand",
            )
        ).formula_operand
        is None
    )


@pytest.mark.parametrize(
    "damage",
    [
        "channel",
        "mode",
        "horizons",
        "history",
        "partition",
        "cutoff",
        "mapping",
        "rights",
        "evidence",
        "identity",
        "unit",
    ],
)
def test_reported_protocol_and_knowledge_bounds_are_explicit(damage):
    from app.analytics.schemas import ReportedSalesAdmission
    from tests.demand_data_helpers import reported_values

    values = reported_values()
    if damage == "channel":
        values["source"]["channel"] = "recorded_vends"
    elif damage == "mode":
        values["protocol"]["knowledge_time_mode"] = "historical_as_of"
    elif damage == "horizons":
        values["protocol"]["horizons"] = (1, 8)
    elif damage == "history":
        values["protocol"]["history_days"] = 27
    elif damage == "partition":
        values["protocol"]["partitions"][1]["start"] = date(2021, 1, 2)
    elif damage == "cutoff":
        values["cutoff"] = instant(19)
    elif damage == "mapping":
        values["mappings"][0]["available_at"] = instant(24)
    elif damage == "rights":
        values["rights"]["approved_at"] = instant(21)
    elif damage == "evidence":
        values["source_evidence"]["qualified_at"] = instant(18)
    elif damage == "identity":
        values["source_evidence"]["source_ref"] = "zenodo:7853252"
    else:
        values["mappings"][0]["unit"] = "kg"
    with pytest.raises(INVALID):
        ReportedSalesAdmission(**values)


def test_reported_admission_requires_separate_schema_and_current_qualification():
    from app.analytics.schemas import ReportedSalesAdmission
    from tests.demand_data_helpers import reported_values

    parsed = ReportedSalesAdmission(**reported_values())
    assert parsed.schema_version == "demand-data/2"
    assert parsed.source_evidence.qualified_at == instant(20)
    assert "business_timezone" not in parsed.model_dump()
    with pytest.raises(INVALID):
        Admission(**reported_values())


@pytest.mark.parametrize("quantity", [0, -1, True, 1.5, "3", 2147483648])
def test_strict_event_and_daily_zero(quantity):
    with pytest.raises(INVALID):
        EventRecord(**event_values(quantity=quantity))
    assert DailyRecord(**daily_values()).quantity == 0
    with pytest.raises(INVALID):
        DailyRecord(**daily_values(coverage="partial", quantity=0))
    with pytest.raises(INVALID):
        DailyRecord(**daily_values(coverage="unknown", quantity=1))


@pytest.mark.parametrize("quantity", [True, 1.5, "0", -1, 9223372036854775808])
def test_daily_quantity_native_integer_only(quantity):
    with pytest.raises(INVALID):
        DailyRecord(**daily_values(quantity=quantity))


def test_contract_limits():
    assert EventRecord(**event_values(quantity=MAX_EVENT_QUANTITY)).quantity == 2147483647
    assert DailyRecord(**daily_values(quantity=MAX_DAILY_QUANTITY)).quantity == 9223372036854775807
    assert DailyRecord(**daily_values(coverage="partial", quantity=None)).quantity is None
    with pytest.raises(INVALID):
        EventRecord(**event_values(event_id="e" * 129))
    with pytest.raises(INVALID):
        EventRecord(**event_values(unit="x" * 41))
    with pytest.raises(INVALID):
        EventRecord(**event_values(unit="cái\n"))
    with pytest.raises(INVALID):
        EventRecord(**event_values(note="never admit free text"))
    values = admission_values()
    values["mappings"] = tuple(
        {
            **values["mappings"][0],
            "source_product": f"p{i}",
            "product_key": f"product-{i}",
            "valid_from": date(1, 1, 1),
            "valid_to": date(9999, 1, 1),
        }
        for i in range(2)
    )
    values.update(
        window_start=date(1, 1, 1),
        window_end=date(9999, 1, 1),
        cutoff=datetime(9999, 1, 2, tzinfo=UTC),
    )
    with pytest.raises(INVALID):
        Admission(**values)


@pytest.mark.parametrize(
    "value",
    [
        "123",
        "1760745600",
        1760745600,
        True,
        "9" * 5000,
        "2026-10-19",
        "2026-10-19T08:00:00",
        datetime(2026, 10, 19),
        "2026-10-19T23:59:60Z",
    ],
    ids=[
        "short_epoch",
        "string_epoch",
        "int_epoch",
        "boolean",
        "huge_epoch",
        "date_only",
        "naive_string",
        "naive_datetime",
        "leap_second",
    ],
)
def test_aware_times_and_complete_day_cutoff(value):
    with pytest.raises(INVALID):
        parse_timestamp(value)
    with pytest.raises(INVALID):
        admission(cutoff=instant(19, 12))


def test_offsets_and_date_parsers_preserve_native_meaning():
    value = parse_timestamp("2026-10-20T00:00:00+07:00")
    assert value.astimezone(UTC) == datetime(2026, 10, 19, 17, tzinfo=UTC)
    assert value.utcoffset() == timedelta(hours=7)
    assert parse_business_date("2026-10-20") == date(2026, 10, 20)
    for invalid in ("20261020", "2026-1-01", instant(), 1, True):
        with pytest.raises(INVALID):
            parse_business_date(invalid)


def test_ambiguous_or_skipped_business_day_refused():
    with pytest.raises(PipelineError, match="TIME_VALUE"):
        business_day_bounds(date(2011, 12, 30), "Pacific/Apia")
    with pytest.raises(PipelineError, match="TIME_VALUE"):
        business_day_bounds(date(2020, 11, 1), "America/Havana")


def test_pinned_timezone_provider():
    assert load_timezone("Asia/Ho_Chi_Minh").key == "Asia/Ho_Chi_Minh"
    spring = business_day_bounds(date(2026, 3, 8), "America/New_York")
    autumn = business_day_bounds(date(2026, 11, 1), "America/New_York")
    assert spring[1] - spring[0] == timedelta(hours=23)
    assert autumn[1] - autumn[0] == timedelta(hours=25)
    with pytest.raises(PipelineError, match="TIMEZONE_UNAVAILABLE"):
        load_timezone("../UTC")


def test_research_rights_fields():
    with pytest.raises(INVALID):
        admission(dataset_class="research")
    assert admission(dataset_class="research", rights=rights_values()).rights.owner_ref == "owner-1"
    for field in ("owner_ref", "permission_ref", "approved_by_ref", "privacy_ref", "retention_ref"):
        with pytest.raises(INVALID):
            Rights(**rights_values(**{field: "user@example.com"}))


@pytest.mark.parametrize(
    "path",
    ["../escape.jsonl", "/absolute", "C:/private", "a\\b", "a/../b", "a//b", "a/./b", "a:stream"],
)
def test_relative_input_paths_are_not_identifiers(path):
    with pytest.raises(INVALID):
        InputFile(path=path, format="jsonl", sha256="a" * 64)


def test_source_representation_proofs_and_immutability():
    values = admission_values()
    values["source"]["representation"] = "daily"
    with pytest.raises(INVALID):
        Admission(**values)
    values["coverage"] = ()
    assert Admission(**values).source.representation == "daily"
    with pytest.raises(INVALID):
        AvailabilityInterval(**day_proof(date(2026, 10, 19), available_at=instant(19)))
    parsed = admission()
    with pytest.raises((ValidationError, TypeError)):
        parsed.dataset_class = "research"
    with pytest.raises(TypeError):
        parsed.source.kind_map["sale"] = "inbound"


def test_unknown_fields_and_provider_temporal_coverage_are_rejected():
    with pytest.raises(INVALID):
        admission(extra_private="sentinel")
    values = admission_values()
    values["coverage"] = ({**values["coverage"][0], "available_at": instant(19)},)
    with pytest.raises(INVALID):
        Admission(**values)


def test_file_count_is_bounded_before_any_file_access():
    values = admission_values()
    values["source"]["files"] = tuple(
        {"path": f"input-{index}.jsonl", "format": "jsonl", "sha256": f"{index:064x}"}
        for index in range(33)
    )
    with pytest.raises(ValidationError):
        Admission(**values)


def test_recorded_vends_requires_explicit_file_daily_channel():
    from tests.demand_data_helpers import recorded_admission_values

    values = recorded_admission_values()
    assert Admission(**values).target == "recorded_vend_units"
    for changes in (
        {"representation": "events"},
        {"channel": "gross_fulfillment"},
        {"kind_map": {"sale": "customer_fulfillment"}},
        {"outside_target_kinds": ("unknown",)},
    ):
        with pytest.raises(INVALID):
            Admission(**{**values, "source": {**values["source"], **changes}})
    with pytest.raises(INVALID):
        Admission(**{**values, "availability": (day_proof(date(2026, 10, 19)),)})
    with pytest.raises(INVALID):
        Admission(**{**values, "coverage": admission_values()["coverage"]})


def test_operational_source_cannot_be_retagged_as_vends():
    from app.analytics.schemas import OPERATIONAL_KINDS
    from tests.demand_data_helpers import recorded_admission_values

    values = recorded_admission_values()
    assert Admission(**values).source.kind == "files"
    values["source"].update(
        kind="operational_b2b",
        files=(),
        representation="events",
        channel="managed_b2b_fulfillment",
        kind_map=OPERATIONAL_KINDS,
        availability_policy_ref="recording-policy",
        database_identity={
            "host": "127.0.0.1",
            "port": 18546,
            "database": "sw_m5_demand_test",
            "username": "sw_m5_demand_test",
        },
    )
    with pytest.raises(INVALID):
        Admission(**values)
