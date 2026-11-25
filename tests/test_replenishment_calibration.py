from datetime import date, timedelta
from decimal import Decimal

import pytest


def test_nearest_rank_is_order_statistic_and_strict():
    from app.replenishment.calibration import nearest_rank

    assert (
        nearest_rank((Decimal("0"), Decimal("1"), Decimal("2"), Decimal("3")), Decimal(".5")) == 1
    )
    for values, p in (
        ((True,), Decimal(".5")),
        ((Decimal("NaN"),), Decimal(".5")),
        ((Decimal("1"),), Decimal("0")),
    ):
        with pytest.raises(ValueError):
            nearest_rank(values, p)


def test_cumulative_residual_requires_same_complete_origin_and_maturity():
    from app.forecasting.schemas import PredictionRow
    from app.replenishment.calibration import cumulative_residual

    origin = date(2022, 6, 23)
    rows = tuple(
        PredictionRow(
            series_key="s",
            origin=origin,
            target_date=origin + timedelta(days=i),
            lead=i,
            horizon=7,
            algorithm="xgboost",
            prediction=1.0,
            actual=2,
            unit="unit",
        )
        for i in range(1, 8)
    )
    assert cumulative_residual(rows, date(2022, 7, 1)) == Decimal("7")
    with pytest.raises(ValueError):
        cumulative_residual(rows, date(2022, 6, 30))
    with pytest.raises(ValueError):
        cumulative_residual(rows[:-1], date(2022, 7, 1))
    with pytest.raises(ValueError):
        cumulative_residual(
            rows[:-1] + (rows[-1].model_copy(update={"origin": origin - timedelta(days=1)}),),
            date(2022, 7, 1),
        )


def test_clipped_interval_and_pinball_hand_oracle():
    from app.replenishment.calibration import score_interval

    result = score_interval(Decimal("2"), Decimal("3"), Decimal("-4"), Decimal("1"))
    assert (result.lower, result.upper, result.covered, result.width) == (0, 3, True, 3)
    assert result.interval_score == 3
    assert result.lower_pinball == Decimal(".15")
    assert result.upper_pinball == 0


def test_minimum_30_enforced_and_distinct_daily_annualization():
    from app.replenishment.calibration import annual_demand, calibration_quantiles

    with pytest.raises(ValueError):
        calibration_quantiles((Decimal("0"),) * 29, 30)
    assert calibration_quantiles((Decimal("0"),) * 30, 30)[Decimal(".90")] == 0
    assert annual_demand(
        ((date(2022, 1, 1), 2), (date(2022, 1, 1), 2), (date(2022, 1, 3), 4))
    ) == Decimal("1095")
    with pytest.raises(ValueError):
        annual_demand(((date(2022, 1, 1), 2), (date(2022, 1, 1), 4)))


def test_paired_evaluation_uses_only_common_complete_origin_and_clipped_scores():
    from app.forecasting.schemas import PredictionRow
    from app.replenishment.calibration import paired_evaluation
    from app.replenishment.schemas import CalibrationEntry, CalibrationWindow

    def rows(origin):
        return tuple(
            PredictionRow(
                series_key="s",
                origin=origin,
                target_date=origin + timedelta(days=lead),
                lead=lead,
                horizon=horizon,
                algorithm=algorithm,
                prediction=1.0,
                actual=2,
                unit="unit",
            )
            for algorithm in ("persistence", "seasonal_naive", "xgboost")
            for horizon in (1, 7)
            for lead in range(1, horizon + 1)
        )

    window = CalibrationWindow(
        origin=date(2022, 1, 1), target_end=date(2022, 1, 2), residual=Decimal("0")
    )
    entries = tuple(
        CalibrationEntry(
            algorithm=a,
            horizon=h,
            windows=(window,),
            quantiles={
                ".05": Decimal("-20"),
                ".80": Decimal("1"),
                ".90": Decimal("2"),
                ".95": Decimal("3"),
            },
        )
        for a in ("persistence", "seasonal_naive", "xgboost")
        for h in (1, 7)
    )
    monday_origin = date(2022, 7, 3)
    partial_origin = date(2022, 7, 4)
    observed = rows(monday_origin) + tuple(r for r in rows(partial_origin) if r.horizon == 1)
    metrics = paired_evaluation(observed, entries, date(2022, 7, 1), date(2023, 1, 1))
    assert len(metrics) == 12
    assert all(item.count == 1 and item.origins == (monday_origin,) for item in metrics)
    h1 = next(
        m for m in metrics if m.algorithm == "xgboost" and m.horizon == 1 and m.subset == "all"
    )
    assert h1.coverage == 1 and h1.mean_width == 4 and h1.mean_interval_score == 4
    assert h1.pinball["0.05"] == Decimal(".10")
    assert h1.pinball["0.80"] == 0


def test_empty_common_origins_and_empty_monday_have_explicit_reasons():
    from pydantic import ValidationError

    from app.forecasting.schemas import PredictionRow
    from app.replenishment.calibration import paired_evaluation
    from app.replenishment.schemas import CalibrationEntry, CalibrationWindow, IntervalMetrics

    window = CalibrationWindow(
        origin=date(2022, 1, 1), target_end=date(2022, 1, 2), residual=Decimal("0")
    )
    entries = tuple(
        CalibrationEntry(
            algorithm=a,
            horizon=h,
            windows=(window,),
            quantiles={
                ".05": Decimal("0"),
                ".80": Decimal("0"),
                ".90": Decimal("0"),
                ".95": Decimal("0"),
            },
        )
        for a in ("persistence", "seasonal_naive", "xgboost")
        for h in (1, 7)
    )
    empty = paired_evaluation((), entries, date(2022, 7, 1), date(2023, 1, 1))
    assert len(empty) == 12
    assert all(
        m.count == 0 and m.coverage is None and m.reason_code == "NO_EVALUATION_WINDOWS"
        for m in empty
    )
    origin = date(2022, 7, 4)  # Tuesday decision day, leaving Monday subset empty.
    rows = tuple(
        PredictionRow(
            series_key="s",
            origin=origin,
            target_date=origin + timedelta(days=lead),
            lead=lead,
            horizon=h,
            algorithm=a,
            prediction=1.0,
            actual=1,
            unit="unit",
        )
        for a in ("persistence", "seasonal_naive", "xgboost")
        for h in (1, 7)
        for lead in range(1, h + 1)
    )
    scored = paired_evaluation(rows, entries, date(2022, 7, 1), date(2023, 1, 1))
    assert all(m.count == 1 and m.reason_code is None for m in scored if m.subset == "all")
    assert all(
        m.count == 0 and m.reason_code == "NO_EVALUATION_WINDOWS"
        for m in scored
        if m.subset == "monday"
    )
    good = scored[0].model_dump()
    with pytest.raises(ValidationError):
        IntervalMetrics(**{**good, "reason_code": "NO_EVALUATION_WINDOWS"})
    empty_good = next(m for m in scored if m.count == 0).model_dump()
    with pytest.raises(ValidationError):
        IntervalMetrics(**{**empty_good, "reason_code": None})
    with pytest.raises(ValidationError):
        IntervalMetrics(**{**empty_good, "coverage": Decimal("0")})
    with pytest.raises(ValidationError):
        IntervalMetrics(**{**good, "mean_width": None})
