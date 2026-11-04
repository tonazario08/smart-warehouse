from datetime import UTC, date, datetime, timedelta
from fractions import Fraction

import pytest

from app.forecasting import evaluation
from app.forecasting.evaluation import evaluate_holdout, forecast, score, tune
from app.forecasting.schemas import (
    ForecastDataset,
    ModelConfig,
    Observation,
    OperationalBinding,
    PredictionRow,
)
from tests.forecasting_helpers import config, dataset


def row(actual, prediction, *, origin=date(2020, 1, 1), series="s"):
    return PredictionRow(
        series_key=series,
        origin=origin,
        target_date=date(2020, 1, 2),
        lead=1,
        horizon=1,
        algorithm="persistence",
        prediction=prediction,
        actual=actual,
        unit="unit",
    )


def test_metric_values_are_pooled_and_total_zero_has_explicit_reason():
    result = score((row(0, 1), row(2, 1, origin=date(2020, 1, 1), series="s2")))
    assert result.mae == 1 and result.wape == 1 and result.count == 2
    zero = score((row(0, 1),))
    assert zero.mae == 1 and zero.wape is None and zero.wape_reason == "ZERO_ACTUAL_TOTAL"
    empty = score(())
    assert empty.mae is None and empty.wape is None and empty.reason == "NO_ELIGIBLE_WINDOWS"


def test_metrics_preserve_large_integer_truth_before_subtraction():
    n = 9_007_199_254_740_993
    result = score((row(n, n - 1),))
    assert result.mae == 1


def test_wape_pools_point_sums_instead_of_averaging_series_ratios():
    result = score((row(100, 90, series="large"), row(1, 0, series="small")))
    assert result.wape == pytest.approx(11 / 101)
    assert result.per_series["large"][2] == pytest.approx(0.1)
    assert result.per_series["small"][2] == 1


def test_origin_total_mae_compares_sum_per_origin():
    origin = date(2020, 1, 1)
    rows = tuple(
        PredictionRow(
            series_key="s",
            origin=origin,
            target_date=origin + timedelta(days=i),
            lead=i,
            horizon=7,
            algorithm="persistence",
            prediction=1,
            actual=0 if i <= 3 else 2,
            unit="unit",
        )
        for i in range(1, 8)
    )
    result = score(rows)
    assert result.mae == 1
    assert result.origin_total_mae == 1


def test_selection_compares_exact_mae_before_tie_breaking():
    candidates = (ModelConfig(max_depth=2), ModelConfig(max_depth=3))
    errors = (Fraction(9_007_199_254_740_993), Fraction(9_007_199_254_740_992))
    assert float(errors[0]) == float(errors[1])
    assert evaluation._winner(candidates, errors) == 1
    assert evaluation._winner(candidates, (errors[0], errors[0])) == 0


def test_no_validation_windows_cannot_win_selection():
    ds = dataset()
    with pytest.raises(ValueError):
        tune(ds, ds.config)


def test_tuning_and_refit_keep_holdout_labels_out_and_ties_choose_first(monkeypatch):
    observations = tuple(
        Observation(
            day=date(year, 2, 1) + timedelta(days=i),
            value=0,
            available_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        for year in (2020, 2021, 2022)
        for i in range(37)
    )
    ds = ForecastDataset(
        config=config(),
        series_key="fixture",
        observations=observations,
        limitations=(),
        knowledge_bound=datetime(2026, 1, 1, tzinfo=UTC),
    )
    calls = []
    actual_fit = evaluation.fit_direct

    def spy(windows, candidate):
        calls.append(tuple(w.target_dates for w in windows))
        return actual_fit(windows, candidate)

    monkeypatch.setattr(evaluation, "fit_direct", spy)
    selection = tune(ds, ds.config)
    assert all(all(day.year == 2020 for dates in group for day in dates) for group in calls)
    assert all(choice.max_depth == 2 for choice in selection.candidates.values())
    changed_holdout = ds.model_copy(
        update={
            "observations": tuple(
                row.model_copy(update={"value": 10000}) if row.day.year == 2022 else row
                for row in ds.observations
            )
        }
    )
    repeated = tune(changed_holdout, changed_holdout.config)
    assert repeated.train_hashes == selection.train_hashes
    assert repeated.validation_hashes == selection.validation_hashes
    assert repeated.candidate_metrics == selection.candidate_metrics
    corrupted = selection.model_copy(
        update={"candidates": {1: ds.config.candidates[1], 7: ds.config.candidates[1]}}
    )
    with pytest.raises(ValueError, match="selection"):
        evaluate_holdout(ds, corrupted)
    calls.clear()
    result = evaluate_holdout(ds, selection)
    assert result.exclusions == {1: 356, 7: 356}
    assert all(all(day.year in (2020, 2021) for dates in group for day in dates) for group in calls)
    assert result.trained_through.year == 2021
    assert {r.algorithm for r in result.rows} == {"persistence", "seasonal_naive", "xgboost"}
    for horizon in (1, 7):
        for algorithm in ("persistence", "seasonal_naive", "xgboost"):
            rows = [r for r in result.rows if r.horizon == horizon and r.algorithm == algorithm]
            assert len(rows) == (9 if horizon == 1 else 21)


@pytest.mark.parametrize(
    "start,end,horizon,expected",
    [
        (date(2020, 1, 1), date(2021, 1, 1), 7, 360),
        (date(2021, 1, 1), date(2021, 1, 4), 7, 0),
        (date(2021, 1, 1), date(2021, 1, 2), 1, 1),
    ],
)
def test_possible_origins_count_partition_calendar(start, end, horizon, expected):
    from app.forecasting.schemas import Partition

    part = Partition(name="final_holdout", start=start, end=end)
    assert evaluation._possible_origins(part, horizon) == expected


def operational_dataset(*, late_label=False, late_validation=False):
    binding = OperationalBinding(
        schema_version="forecast-binding/1",
        data_version="ddv1-" + "a" * 64,
        product_key="p",
        warehouse_key="w",
        product_id=1,
        warehouse_id=1,
        unit="unit",
        approved_at=datetime(2019, 1, 1, tzinfo=UTC),
        available_at=datetime(2019, 1, 1, tzinfo=UTC),
        permission_ref="synthetic-permission",
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
    observations = []
    for year, length in ((2020, 37), (2021, 37), (2022, 28)):
        for i in range(length):
            day = date(year, 2, 1) + timedelta(days=i)
            when = datetime.combine(day, datetime.min.time(), UTC) + timedelta(hours=12)
            if late_label and year == 2020 and i == 36:
                when = datetime(2021, 1, 2, tzinfo=UTC)
            if late_validation and year == 2021 and i == 36:
                when = datetime(2022, 1, 2, tzinfo=UTC)
            observations.append(Observation(day=day, value=1, available_at=when))
    return ForecastDataset(
        config=cfg,
        series_key="synthetic",
        observations=tuple(observations),
        limitations=(),
        admission_cutoff=datetime(2022, 12, 31, tzinfo=UTC),
    )


def test_operational_fit_rejects_training_label_after_information_cutoff():
    ds = operational_dataset(late_label=True)
    with pytest.raises(ValueError, match="label unavailable"):
        tune(ds, ds.config)


def test_operational_tuning_rejects_validation_label_after_selection_cutoff():
    ds = operational_dataset(late_validation=True)
    with pytest.raises(ValueError, match="label unavailable"):
        tune(ds, ds.config)


@pytest.mark.parametrize(
    "field,value",
    [
        ("train_information_cutoff", datetime(2021, 1, 2, tzinfo=UTC)),
        ("selection_information_cutoff", datetime(2022, 1, 2, tzinfo=UTC)),
        ("refit_information_cutoff", datetime(2022, 1, 2, tzinfo=UTC)),
        ("refit_information_cutoff", datetime(2020, 1, 1, tzinfo=UTC)),
    ],
)
def test_operational_cutoffs_cannot_cross_order_or_partition_boundaries(field, value):
    from pydantic import ValidationError

    from app.forecasting.schemas import ForecastConfig

    payload = operational_dataset().config.model_dump()
    payload["protocol"][field] = value
    with pytest.raises(ValidationError):
        ForecastConfig.model_validate(payload)


def test_forecast_refits_train_and_validation_without_future_labels(monkeypatch):
    ds = operational_dataset()
    selection = tune(ds, ds.config)
    calls = []
    actual_fit = evaluation.fit_direct

    def spy(windows, candidate):
        calls.append(tuple(day for window in windows for day in window.target_dates))
        return actual_fit(windows, candidate)

    monkeypatch.setattr(evaluation, "fit_direct", spy)
    # Selection identity includes implementation identity, so apply the same spy to re-tune.
    selection = tune(ds, ds.config)
    calls.clear()
    result = forecast(ds, selection, ds.config.binding, date(2022, 2, 28))
    assert len(result.rows) == 24 and all(row.actual is None for row in result.rows)
    assert all(day.year in (2020, 2021) for group in calls for day in group)
    assert result.trained_through.year == 2021
    assert max(r.day for r in ds.observations) == date(2022, 2, 28)
    changed = ds.model_copy(
        update={"config": ds.config.model_copy(update={"data_version": "ddv1-" + "b" * 64})}
    )
    with pytest.raises(ValueError, match="identity"):
        forecast(changed, selection, ds.config.binding, date(2022, 2, 28))
    with pytest.raises(ValueError, match="not known"):
        forecast(ds, selection, ds.config.binding, date(2021, 3, 8))
