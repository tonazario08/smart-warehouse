from datetime import UTC, date, datetime

import pytest

from app.forecasting.features import feature_vector, make_origin, make_windows
from app.forecasting.schemas import ForecastDataset, OperationalBinding
from tests.forecasting_helpers import config, dataset


def test_features_use_only_28_history_and_target_calendar():
    vector = feature_vector(tuple(float(i) for i in range(1, 29)), date(2020, 2, 1))
    assert len(vector) == 32
    assert vector[:28] == tuple(float(i) for i in range(28, 0, -1))
    assert vector[28:] == (25.0, 14.5, 6.0, 2.0)
    with pytest.raises(ValueError):
        feature_vector((1.0,) * 27, date(2020, 2, 1))


@pytest.mark.parametrize("invalid", [True, "2", None, float("inf"), 10**400])
def test_feature_vector_rejects_invalid_values_with_controlled_error(invalid):
    with pytest.raises(ValueError):
        feature_vector((invalid,) * 28, date(2020, 2, 1))


def test_feature_vector_accepts_finite_int_and_float_quantities():
    assert feature_vector((1, 2.5) * 14, date(2020, 2, 1))[:2] == (2.5, 1)


def test_windows_exclude_missing_history_or_targets_and_keep_zero():
    clean = dataset(future_value=0)
    windows = make_windows(clean, "train", 7)
    assert windows[0].history_values[-1] == 28
    assert windows[0].target_values == (0,) * 7
    assert len(make_windows(dataset(missing=(39,)), "train", 7)) == 5
    assert len(make_windows(dataset(missing=(27,)), "train", 7)) == 0


def test_future_origin_needs_no_targets_and_ignores_future_values():
    left = make_origin(dataset(future_value=0), date(2020, 1, 28), 7)
    right = make_origin(dataset(future_value=100), date(2020, 1, 28), 7)
    assert left == right
    assert not hasattr(left, "target_values")
    assert make_origin(dataset(missing=tuple(range(28, 40))), date(2020, 1, 28), 7) == left


def test_absent_calendar_day_excludes_origin_instead_of_compressing_history():
    original = dataset()
    gap = ForecastDataset(
        config=original.config,
        series_key=original.series_key,
        observations=original.observations[:10] + original.observations[11:],
        limitations=(),
    )
    with pytest.raises(ValueError, match="ineligible history"):
        make_origin(gap, date(2020, 1, 28), 7)


def test_operational_origin_rejects_history_not_known_by_origin_cutoff():
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
    cfg = config(
        mode="operational",
        data_version=binding.data_version,
        target="gross_fulfilled_units",
        reporting_scope="warehouse",
        knowledge_time_mode="historical_as_of",
        binding=binding,
        business_timezone="UTC",
    )
    rows = dataset(available_at=datetime(2020, 1, 29, 0, 0, 1, tzinfo=UTC)).observations
    ds = ForecastDataset(config=cfg, series_key="p:w", observations=rows, limitations=())
    with pytest.raises(ValueError, match="ineligible history"):
        make_origin(ds, date(2020, 1, 28), 7)
