from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.forecasting.schemas import (
    ForecastOrigin,
    Observation,
    OperationalBinding,
    Partition,
)
from tests.forecasting_helpers import config


@pytest.mark.parametrize(
    "changes",
    [
        {"schema_version": "forecast-config/2"},
        {"mode": "operational"},
        {"target": "gross_fulfilled_units"},
        {"reporting_scope": "warehouse"},
        {"knowledge_time_mode": "historical_as_of"},
        {"history_days": True},
        {"horizons": (1, "7")},
        {"unknown": date(2020, 1, 1)},
    ],
)
def test_research_contract_rejects_incompatible_or_non_strict_values(changes):
    with pytest.raises(ValidationError):
        config(**changes)


def test_history_days_rejects_float_even_if_numerically_equal():
    with pytest.raises(ValidationError):
        config(history_days=28.0)


def test_config_serializes_versioned_protocol_and_fixed_candidates():
    payload = config().model_dump()
    assert payload["protocol"]["schema_version"] == "forecast-protocol/1"
    assert [candidate["max_depth"] for candidate in payload["candidates"]] == [2, 3]
    assert "partitions" not in payload


def test_research_rejects_invented_historical_cutoffs():
    payload = config().model_dump()
    payload["protocol"]["train_information_cutoff"] = datetime(2020, 12, 31, tzinfo=UTC)
    with pytest.raises(ValidationError):
        type(config()).model_validate(payload)


@pytest.mark.parametrize("value", [True, float("inf"), float("nan"), -1])
def test_observation_rejects_boolean_nonfinite_and_negative_quantities(value):
    with pytest.raises(ValidationError):
        Observation(day=date(2020, 1, 1), value=value, available_at=None)


def test_origin_rejects_unsupported_two_day_horizon():
    origin = date(2020, 1, 28)
    with pytest.raises(ValidationError):
        ForecastOrigin(
            series_key="s",
            origin=origin,
            history_dates=tuple(origin - timedelta(days=i) for i in range(27, -1, -1)),
            history_values=(1.0,) * 28,
            target_dates=(origin + timedelta(days=1), origin + timedelta(days=2)),
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"business_timezone": "Not/A_Real_Zone"},
        {
            "partitions": (
                Partition(name="validation", start=date(2021, 1, 1), end=date(2022, 1, 1)),
            )
        },
        {
            "partitions": (
                Partition(name="validation", start=date(2020, 1, 1), end=date(2021, 1, 1)),
                Partition(name="train", start=date(2021, 1, 1), end=date(2022, 1, 1)),
                Partition(name="final_holdout", start=date(2022, 1, 1), end=date(2023, 1, 1)),
            )
        },
    ],
)
def test_operational_contract_rejects_invalid_timezone_or_incomplete_partitions(changes):
    binding = OperationalBinding(
        schema_version="forecast-binding/1",
        data_version="ddv1-" + "a" * 64,
        product_key="p",
        warehouse_key="w",
        product_id=1,
        warehouse_id=1,
        unit="unit",
        approved_at=datetime(2020, 1, 1, tzinfo=UTC),
        available_at=datetime(2020, 1, 1, tzinfo=UTC),
        permission_ref="permission",
    )
    values = dict(
        mode="operational",
        data_version=binding.data_version,
        target="gross_fulfilled_units",
        reporting_scope="warehouse",
        knowledge_time_mode="historical_as_of",
        binding=binding,
        business_timezone="UTC",
    )
    values.update(changes)
    with pytest.raises(ValidationError):
        config(**values)


def test_operational_partitions_may_have_source_supported_gaps():
    binding = OperationalBinding(
        schema_version="forecast-binding/1",
        data_version="ddv1-" + "b" * 64,
        product_key="p",
        warehouse_key="w",
        product_id=1,
        warehouse_id=1,
        unit="unit",
        approved_at=datetime(2020, 1, 1, tzinfo=UTC),
        available_at=datetime(2020, 1, 1, tzinfo=UTC),
        permission_ref="permission",
    )
    partitions = tuple(
        Partition(name=name, start=date(year, 1, 1), end=date(year, 6, 1))
        for name, year in (("train", 2018), ("validation", 2020), ("final_holdout", 2024))
    )
    result = config(
        mode="operational",
        data_version=binding.data_version,
        target="gross_fulfilled_units",
        reporting_scope="warehouse",
        knowledge_time_mode="historical_as_of",
        binding=binding,
        business_timezone="UTC",
        partitions=partitions,
    )
    assert result.partitions == partitions
