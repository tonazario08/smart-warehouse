from datetime import date, timedelta

import pytest
from pydantic import ValidationError


def test_authorization_rejects_wrong_hash_set_and_extra_fields(tmp_path):
    from app.replenishment.schemas import InputAuthorization

    common = dict(
        schema_version="replenishment-input-authorization/1",
        mode="research",
        dataset_class="research",
        approved_bundle_root=tmp_path,
        bundle_path=tmp_path / "bundle",
        bundle_hashes={"manifest.json": "a" * 64},
        approved_forecast_root=tmp_path,
        forecast_dir=tmp_path / "run",
        public_manifest_sha256="b" * 64,
        source_manifest_sha256="c" * 64,
        forecast_run_id="frv1-" + "d" * 64,
        allow_fixture=False,
    )
    with pytest.raises(ValidationError):
        InputAuthorization(**common)
    common["bundle_hashes"] = {
        name: "a" * 64
        for name in ("manifest.json", "observations.jsonl", "quality.json", "records.jsonl")
    }
    with pytest.raises(ValidationError):
        InputAuthorization(**common, unexpected=True)
    with pytest.raises(ValidationError):
        InputAuthorization(**{**common, "allow_fixture": True})


def test_temporal_window_requires_complete_leads_and_boundary():
    from app.forecasting.schemas import PredictionRow
    from app.replenishment.inputs import classify_window

    def row(lead):
        origin = date(2022, 6, 24)
        return PredictionRow(
            series_key="series",
            origin=origin,
            target_date=origin + timedelta(days=lead),
            lead=lead,
            horizon=7,
            algorithm="xgboost",
            prediction=1.0,
            actual=1,
            unit="unit",
        )

    rows = tuple(row(i) for i in range(1, 8))
    assert classify_window(rows, date(2022, 1, 1), date(2022, 7, 1)) is False
    with pytest.raises(ValueError):
        classify_window(rows[:-1], date(2022, 1, 1), date(2022, 7, 1))
    assert classify_window(rows, date(2022, 1, 1), date(2022, 7, 2)) is True
    mixed = rows[:-1] + (rows[-1].model_copy(update={"origin": date(2022, 6, 23)}),)
    with pytest.raises(ValueError):
        classify_window(mixed, date(2022, 1, 1), date(2022, 7, 2))
    missing = rows[:-1] + (rows[-1].model_copy(update={"actual": None}),)
    with pytest.raises(ValueError):
        classify_window(missing, date(2022, 1, 1), date(2022, 7, 2))


def test_missing_cost_is_valid_input_but_nonfinite_or_negative_is_rejected():
    from decimal import Decimal

    from app.replenishment.schemas import CostInputs

    cost = CostInputs(
        ordering_cost=None, holding_cost=Decimal("1"), currency="VND", holding_period="year"
    )
    assert cost.ordering_cost is None
    with pytest.raises(ValidationError):
        CostInputs(
            ordering_cost=Decimal("NaN"),
            holding_cost=Decimal("1"),
            currency="VND",
            holding_period="year",
        )
    with pytest.raises(ValidationError):
        CostInputs(
            ordering_cost=Decimal("-1"),
            holding_cost=Decimal("1"),
            currency="VND",
            holding_period="year",
        )


def test_select_windows_keeps_calendar_and_excludes_boundary_crossings():
    from app.forecasting.schemas import PredictionRow
    from app.replenishment.inputs import select_windows

    def group(origin):
        return tuple(
            PredictionRow(
                series_key="s",
                origin=origin,
                target_date=origin + timedelta(days=lead),
                lead=lead,
                horizon=7,
                algorithm="xgboost",
                prediction=1.0,
                actual=1,
                unit="unit",
            )
            for lead in range(1, 8)
        )

    included = group(date(2022, 6, 23))
    crossing = group(date(2022, 6, 24))
    assert select_windows(included + crossing, date(2022, 1, 1), date(2022, 7, 1)) == (included,)
    with pytest.raises(ValueError):
        select_windows(included + crossing[:-1], date(2022, 1, 1), date(2022, 7, 1))


def test_coverage_distinguishes_stale_range_from_internal_holes():
    from types import SimpleNamespace

    from app.replenishment.inputs import validate_forecast_coverage

    algs = ("persistence", "seasonal_naive", "xgboost")
    start, end = date(2022, 7, 1), date(2022, 7, 12)
    origins = [date(2022, 6, 30) + timedelta(days=i) for i in range(5)]
    rows = tuple(
        SimpleNamespace(algorithm=a, horizon=h, origin=o)
        for a in algs
        for h in (1, 7)
        for o in origins
    )
    validate_forecast_coverage(rows, start, end)
    with pytest.raises(ValueError, match="FORECAST_STALE"):
        validate_forecast_coverage(rows, start, end + timedelta(days=1))
    middle = tuple(r for r in rows if r.origin != origins[2])
    with pytest.raises(ValueError, match="CALENDAR_UNAVAILABLE"):
        validate_forecast_coverage(middle, start, end)
