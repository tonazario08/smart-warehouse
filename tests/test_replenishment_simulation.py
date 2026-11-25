from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest


def test_two_day_receipt_decision_demand_holding_hand_oracle():
    from app.replenishment.schemas import SupplyOrder
    from app.replenishment.simulation import simulate_trajectory

    first = date(2022, 7, 1)
    initial = SupplyOrder(
        order_id="initial",
        quantity=2,
        unit="unit",
        ordered_at=datetime(2022, 6, 28, tzinfo=UTC),
        known_at=datetime(2022, 6, 28, tzinfo=UTC),
        due_date=first,
    )
    result = simulate_trajectory(
        days=((first, 9, Decimal("8")), (first + timedelta(days=1), 1, Decimal("8"))),
        algorithm="xgboost",
        horizon=1,
        service=Decimal(".90"),
        policy="baseline",
        quantile=Decimal("0"),
        order_quantity=4,
        initial_on_hand=5,
        initial_pipeline=(initial,),
        reservations=0,
        backlog=0,
        unit="unit",
        ordering_cost=Decimal("100"),
        holding_cost=Decimal("365"),
        warmup_days=0,
        initial_cutoff=datetime(2022, 7, 1, tzinfo=UTC),
    )
    assert [
        (d.received, d.position, d.ordered, d.fulfilled, d.lost, d.on_hand_end) for d in result.days
    ] == [(2, 7, 4, 7, 2, 0), (4, 4, 4, 1, 0, 3)]
    assert result.summary.order_count == 2
    assert result.summary.partial_cost == Decimal("203")
    assert result.summary.terminal_pipeline == 4
    assert result.summary.fill_rate == Decimal(".8")
    assert result.summary.average_on_hand == Decimal("1.5")
    assert result.summary.stockout_days == 1
    assert sum(order.quantity for order in result.orders) == 8


def test_zero_demand_ratios_and_no_order():
    from app.replenishment.simulation import simulate_trajectory

    result = simulate_trajectory(
        days=((date(2022, 7, 1), 0, Decimal("0")),),
        algorithm="persistence",
        horizon=1,
        service=Decimal(".80"),
        policy="proposed",
        quantile=Decimal("0"),
        order_quantity=0,
        initial_on_hand=0,
        initial_pipeline=(),
        reservations=0,
        backlog=0,
        unit="unit",
        ordering_cost=Decimal("1"),
        holding_cost=Decimal("365"),
        warmup_days=0,
        initial_cutoff=datetime(2022, 7, 1, tzinfo=UTC),
    )
    assert result.days[0].ordered == 0
    assert result.summary.fill_rate is None and result.summary.fill_reason == "ZERO_DEMAND"
    assert (
        result.summary.day_service is None
        and result.summary.day_service_reason == "NO_POSITIVE_DEMAND_DAYS"
    )
    assert result.summary.partial_cost == 0


def test_missing_calendar_and_unknown_inventory_are_never_assumed():
    from app.replenishment.simulation import simulate_trajectory

    common = dict(
        algorithm="persistence",
        horizon=1,
        service=Decimal(".80"),
        policy="baseline",
        quantile=Decimal("0"),
        order_quantity=1,
        initial_on_hand=0,
        initial_pipeline=(),
        reservations=0,
        backlog=0,
        unit="unit",
        ordering_cost=Decimal("1"),
        holding_cost=Decimal("365"),
        warmup_days=0,
        initial_cutoff=datetime(2022, 7, 1, tzinfo=UTC),
    )
    with pytest.raises(ValueError, match="calendar"):
        simulate_trajectory(
            days=((date(2022, 7, 1), 1, Decimal("1")), (date(2022, 7, 3), 1, Decimal("1"))),
            **common,
        )
    for value in (None, 1):
        with pytest.raises(ValueError, match="UNSUPPORTED_INVENTORY_STATE"):
            simulate_trajectory(
                days=((date(2022, 7, 1), 1, Decimal("1")),), **{**common, "reservations": value}
            )


def test_full_simulation_uses_common_calendar_and_all_paired_cases():
    from types import SimpleNamespace

    from app.forecasting.schemas import Observation, PredictionRow
    from app.replenishment.calibration import calibrate
    from app.replenishment.schemas import CostInputs, StudyConfig, StudyInputs
    from app.replenishment.simulation import simulate

    config = StudyConfig(
        schema_version="replenishment-study/1",
        mode="research",
        dataset_class="research",
        target="reported_daily_unit_sales",
        reporting_scope="company_aggregate",
        unit="unit",
        data_version="ddv2-" + "a" * 64,
        forecast_run_id="frv1-" + "b" * 64,
        source_manifest_sha256="c" * 64,
        public_manifest_sha256="d" * 64,
        calibration_start=date(2022, 1, 1),
        calibration_end=date(2022, 7, 1),
        evaluation_start=date(2022, 7, 1),
        evaluation_end=date(2023, 1, 1),
        nominal_coverage=Decimal(".90"),
        service_probabilities=(Decimal(".80"), Decimal(".90"), Decimal(".95")),
        minimum_samples=30,
        lead_times=(1, 7),
        warmup_days=7,
        costs=CostInputs(
            ordering_cost=Decimal("100"),
            holding_cost=Decimal("365"),
            currency="VND",
            holding_period="year",
        ),
        initial_on_hand=100,
        initial_pipeline=(),
        reservations=0,
        backlog=0,
        temporal_availability_convention="retrospective fixture",
        disclosures=("synthetic",),
    )
    origins = [date(2022, 1, 1) + timedelta(days=i) for i in range(30)] + [
        date(2022, 6, 30) + timedelta(days=i) for i in range(178)
    ]
    rows = tuple(
        PredictionRow(
            series_key="s",
            origin=origin,
            target_date=origin + timedelta(days=lead),
            lead=lead,
            horizon=h,
            algorithm=a,
            prediction=1.0,
            actual=2,
            unit="unit",
        )
        for a in ("persistence", "seasonal_naive", "xgboost")
        for h in (1, 7)
        for origin in origins
        for lead in range(1, h + 1)
    )
    observations = tuple(
        Observation(day=date(2022, 7, 1) + timedelta(days=i), value=2, available_at=None)
        for i in range(178)
    )
    inputs = StudyInputs.model_construct(
        config=config,
        observations=observations,
        forecast=SimpleNamespace(rows=rows, manifest=SimpleNamespace(business_timezone=None)),
    )
    calibration = calibrate(inputs, config)
    result = simulate(inputs, calibration, config)
    assert len(result.trajectories) == 36
    assert sum(len(trajectory.days) for trajectory in result.trajectories) == 6408
    assert all(
        t.summary.scored_days == 171 and sum(d.warmup for d in t.days) == 7
        for t in result.trajectories
    )
    assert result.scenario_clock_timezone == "UTC"
    assert result.scenario_clock_convention == "ANALYTICAL_SCENARIO_CLOCK_UTC"
    assert result.data_version == config.data_version
    zero_rows = tuple(row.model_copy(update={"actual": 0}) for row in rows)
    zero_observations = tuple(row.model_copy(update={"value": 0}) for row in observations)
    zero_inputs = inputs.model_copy(
        update={
            "forecast": SimpleNamespace(
                rows=zero_rows, manifest=SimpleNamespace(business_timezone=None)
            ),
            "observations": zero_observations,
        }
    )
    zero_result = simulate(zero_inputs, calibrate(zero_inputs, config), config)
    assert zero_result.eoq.quantity == 0 and zero_result.eoq.reason_code == "ZERO_DEMAND"
    assert all(
        not day.ordered for trajectory in zero_result.trajectories for day in trajectory.days
    )
    assert all(
        trajectory.summary.fill_reason == "ZERO_DEMAND" for trajectory in zero_result.trajectories
    )
    missing_cost = config.model_copy(
        update={
            "costs": CostInputs(
                ordering_cost=None,
                holding_cost=Decimal("365"),
                currency="VND",
                holding_period="year",
            )
        }
    )
    missing_inputs = inputs.model_copy(update={"config": missing_cost})
    with pytest.raises(ValueError, match="ORDERING_COST_MISSING"):
        simulate(missing_inputs, calibrate(missing_inputs, missing_cost), missing_cost)


def test_future_demand_does_not_change_prior_decision():
    from app.replenishment.simulation import simulate_trajectory

    first = date(2022, 7, 1)
    common = dict(
        algorithm="persistence",
        horizon=1,
        service=Decimal(".80"),
        policy="baseline",
        quantile=Decimal("0"),
        order_quantity=4,
        initial_on_hand=2,
        initial_pipeline=(),
        reservations=0,
        backlog=0,
        unit="unit",
        ordering_cost=Decimal("1"),
        holding_cost=Decimal("365"),
        warmup_days=0,
        initial_cutoff=datetime(2022, 7, 1, tzinfo=UTC),
    )
    initial = (first, 1, Decimal("2"))
    one = simulate_trajectory(
        days=(initial, (first + timedelta(days=1), 0, Decimal("2"))), **common
    )
    two = simulate_trajectory(
        days=(initial, (first + timedelta(days=1), 100, Decimal("2"))), **common
    )
    assert one.days[0] == two.days[0]


def test_pipeline_position_timestamps_and_unique_identity():
    from app.replenishment.schemas import SupplyOrder
    from app.replenishment.simulation import simulate_trajectory

    first = date(2022, 7, 1)
    order = SupplyOrder(
        order_id="supply",
        quantity=5,
        unit="unit",
        ordered_at=datetime(2022, 6, 29, tzinfo=UTC),
        known_at=datetime(2022, 6, 30, tzinfo=UTC),
        due_date=first + timedelta(days=1),
    )
    common = dict(
        days=((first, 0, Decimal("4")), (first + timedelta(days=1), 0, Decimal("4"))),
        algorithm="persistence",
        horizon=1,
        service=Decimal(".80"),
        policy="baseline",
        quantile=Decimal("0"),
        order_quantity=2,
        initial_on_hand=0,
        initial_pipeline=(order,),
        reservations=0,
        backlog=0,
        unit="unit",
        ordering_cost=Decimal("1"),
        holding_cost=Decimal("365"),
        warmup_days=0,
        initial_cutoff=datetime(2022, 7, 1, tzinfo=UTC),
    )
    result = simulate_trajectory(**common)
    assert result.days[0].position == 5 and result.days[0].ordered == 0
    assert result.days[1].received == 5 and result.days[1].on_hand_end == 5
    for orders in (
        (order, order),
        (order.model_copy(update={"unit": "other"}),),
        (order.model_copy(update={"known_at": datetime(2022, 7, 2, tzinfo=UTC)}),),
        (order.model_copy(update={"ordered_at": datetime(2022, 7, 2, tzinfo=UTC)}),),
        (order.model_copy(update={"due_date": first - timedelta(days=1)}),),
    ):
        with pytest.raises(ValueError):
            simulate_trajectory(**{**common, "initial_pipeline": orders})


def test_warmup_boundary_conservation_and_separate_costs():
    from app.replenishment.simulation import simulate_trajectory

    first = date(2022, 7, 1)
    result = simulate_trajectory(
        days=((first, 1, Decimal("3")), (first + timedelta(days=1), 1, Decimal("3"))),
        algorithm="persistence",
        horizon=1,
        service=Decimal(".80"),
        policy="baseline",
        quantile=Decimal("0"),
        order_quantity=2,
        initial_on_hand=1,
        initial_pipeline=(),
        reservations=0,
        backlog=0,
        unit="unit",
        ordering_cost=Decimal("100"),
        holding_cost=Decimal("365"),
        warmup_days=1,
        initial_cutoff=datetime(2022, 7, 1, tzinfo=UTC),
    )
    assert result.summary.scored_opening_on_hand == 0
    assert result.summary.scored_opening_pipeline == 2
    assert result.summary.warmup_demand == 1 and result.summary.warmup_ordering_cost == 100
    assert result.summary.order_count == 1 and result.summary.ordering_cost == 100
    assert result.summary.terminal_pipeline == 2 and result.summary.closing_on_hand == 1
    assert result.summary.holding_cost == 1
    for day in result.days:
        assert day.opening_on_hand + day.received == day.fulfilled + day.on_hand_end
        assert day.demand == day.fulfilled + day.lost


def test_nonfinite_boolean_and_unavailable_costs_are_rejected():
    from app.replenishment.simulation import simulate_trajectory

    base = dict(
        days=((date(2022, 7, 1), 1, Decimal("1")),),
        algorithm="persistence",
        horizon=1,
        service=Decimal(".80"),
        policy="baseline",
        quantile=Decimal("0"),
        order_quantity=1,
        initial_on_hand=0,
        initial_pipeline=(),
        reservations=0,
        backlog=0,
        unit="unit",
        ordering_cost=Decimal("1"),
        holding_cost=Decimal("1"),
        warmup_days=0,
        initial_cutoff=datetime(2022, 7, 1, tzinfo=UTC),
    )
    for change in (
        {"initial_on_hand": True},
        {"order_quantity": True},
        {"horizon": True},
        {"days": ((date(2022, 7, 1), True, Decimal("1")),)},
        {"quantile": Decimal("NaN")},
        {"ordering_cost": None},
        {"holding_cost": Decimal("0")},
        {"backlog": None},
    ):
        with pytest.raises((ValueError, TypeError)):
            simulate_trajectory(**{**base, **change})
