"""Deterministic, scenario-only lost-sales replenishment simulation."""

from datetime import timedelta
from decimal import ROUND_CEILING, Decimal

from app.replenishment.policy import _decimal
from app.replenishment.schemas import (
    SimulationDay,
    SimulationOrder,
    SimulationTrajectory,
    SupplyOrder,
    TrajectorySummary,
)


def simulate_trajectory(
    *,
    days,
    algorithm,
    horizon,
    service,
    policy,
    quantile,
    order_quantity,
    initial_on_hand,
    initial_pipeline,
    reservations,
    backlog,
    unit,
    ordering_cost,
    holding_cost,
    warmup_days,
    initial_cutoff,
):
    service, quantile = _decimal(service), _decimal(quantile)
    ordering_cost, holding_cost = _decimal(ordering_cost), _decimal(holding_cost)
    initial_pipeline = tuple(
        SupplyOrder.model_validate_json(order.model_dump_json()) for order in initial_pipeline
    )
    if (
        reservations != 0
        or type(reservations) is not int
        or backlog != 0
        or type(backlog) is not int
    ):
        raise ValueError("UNSUPPORTED_INVENTORY_STATE")
    if (
        type(initial_on_hand) is not int
        or initial_on_hand < 0
        or type(order_quantity) is not int
        or order_quantity < 0
        or horizon not in (1, 7)
        or type(horizon) is not int
        or type(warmup_days) is not int
        or warmup_days < 0
        or warmup_days >= len(days)
        or service not in (Decimal(".80"), Decimal(".90"), Decimal(".95"))
        or policy not in ("baseline", "proposed")
        or ordering_cost <= 0
        or holding_cost <= 0
        or initial_cutoff.utcoffset() is None
    ):
        raise ValueError("invalid scenario")
    if not days or any(type(demand) is not int or demand < 0 for _, demand, _ in days):
        raise ValueError("invalid demand")
    if any(b[0] - a[0] != timedelta(days=1) for a, b in zip(days, days[1:], strict=False)):
        raise ValueError("missing calendar day")
    if any(_decimal(mean) < 0 for _, _, mean in days):
        raise ValueError("negative forecast")
    if len({order.order_id for order in initial_pipeline}) != len(initial_pipeline):
        raise ValueError("duplicate supply order")
    if any(
        order.unit != unit
        or order.ordered_at > initial_cutoff
        or order.known_at > initial_cutoff
        or order.due_date < days[0][0]
        for order in initial_pipeline
    ):
        raise ValueError("invalid initial pipeline")
    pending = [(o.order_id, o.due_date, o.quantity) for o in initial_pipeline]
    used_ids = {o.order_id for o in initial_pipeline}
    on_hand = initial_on_hand
    records, orders = [], []
    scored_opening_on_hand = scored_opening_pipeline = None
    for index, (day, demand, mean) in enumerate(days):
        mean = _decimal(mean)
        opening = on_hand
        if index == warmup_days:
            scored_opening_on_hand, scored_opening_pipeline = opening, sum(o[2] for o in pending)
        due = tuple(o for o in pending if o[1] == day)
        pending = [o for o in pending if o[1] != day]
        received = sum(o[2] for o in due)
        on_hand += received
        position = on_hand + sum(o[2] for o in pending)
        safety = max(Decimal(0), quantile) if policy == "proposed" else Decimal(0)
        reorder = int((mean + safety).to_integral_value(rounding=ROUND_CEILING))
        ordered = order_quantity if position <= reorder and order_quantity > 0 else 0
        order_id = None
        due_date = None
        if ordered:
            order_id = f"m7-order-{index + 1:08d}"
            if order_id in used_ids:
                raise ValueError("order ID collision")
            used_ids.add(order_id)
            due_date = day + timedelta(days=horizon)
            pending.append((order_id, due_date, ordered))
            orders.append(
                SimulationOrder(
                    order_id=order_id, ordered_on=day, due_date=due_date, quantity=ordered
                )
            )
        fulfilled = min(on_hand, demand)
        lost = demand - fulfilled
        on_hand -= fulfilled
        if opening + received != fulfilled + on_hand or demand != fulfilled + lost:
            raise ValueError("stock conservation failure")
        records.append(
            SimulationDay(
                day=day,
                origin=day - timedelta(days=1),
                warmup=index < warmup_days,
                opening_on_hand=opening,
                received=received,
                received_order_ids=tuple(o[0] for o in due),
                position=position,
                forecast_mean=mean,
                residual_quantile=quantile,
                safety_stock=safety,
                reorder_point=reorder,
                order_quantity=order_quantity,
                ordered=ordered,
                order_id=order_id,
                due_date=due_date,
                demand=demand,
                fulfilled=fulfilled,
                lost=lost,
                on_hand_end=on_hand,
                pipeline_end=sum(o[2] for o in pending),
                ordering_cost=ordering_cost if ordered else Decimal(0),
                holding_cost=Decimal(on_hand) * holding_cost / Decimal(365),
            )
        )
    scored, warmup = records[warmup_days:], records[:warmup_days]
    if initial_on_hand + sum(row.received for row in records) != sum(
        row.fulfilled for row in records
    ) + on_hand or sum(order.quantity for order in initial_pipeline) + sum(
        order.quantity for order in orders
    ) != sum(row.received for row in records) + sum(item[2] for item in pending):
        raise ValueError("trajectory conservation failure")
    demand = sum(r.demand for r in scored)
    fulfilled = sum(r.fulfilled for r in scored)
    positive_days = sum(r.demand > 0 for r in scored)
    order_cost = sum((r.ordering_cost for r in scored), Decimal(0))
    hold_cost = sum((r.holding_cost for r in scored), Decimal(0))
    summary = TrajectorySummary(
        scored_days=len(scored),
        scored_opening_on_hand=scored_opening_on_hand,
        scored_opening_pipeline=scored_opening_pipeline,
        closing_on_hand=on_hand,
        terminal_pipeline=sum(o[2] for o in pending),
        demand=demand,
        fulfilled=fulfilled,
        lost=sum(r.lost for r in scored),
        fill_rate=Decimal(fulfilled) / demand if demand else None,
        fill_reason=None if demand else "ZERO_DEMAND",
        day_service=Decimal(sum(r.demand > 0 and r.lost == 0 for r in scored)) / positive_days
        if positive_days
        else None,
        day_service_reason=None if positive_days else "NO_POSITIVE_DEMAND_DAYS",
        stockout_days=sum(r.lost > 0 for r in scored),
        average_on_hand=Decimal(sum(r.on_hand_end for r in scored)) / len(scored),
        order_count=sum(r.ordered > 0 for r in scored),
        receipt_count=sum(len(r.received_order_ids) for r in scored),
        ordering_cost=order_cost,
        holding_cost=hold_cost,
        partial_cost=order_cost + hold_cost,
        warmup_demand=sum(r.demand for r in warmup),
        warmup_fulfilled=sum(r.fulfilled for r in warmup),
        warmup_lost=sum(r.lost for r in warmup),
        warmup_ordering_cost=sum((r.ordering_cost for r in warmup), Decimal(0)),
        warmup_holding_cost=sum((r.holding_cost for r in warmup), Decimal(0)),
        cycle_service=None,
        cycle_service_reason="OVERLAPPING_CYCLES_UNSUPPORTED",
    )
    return SimulationTrajectory(
        algorithm=algorithm,
        horizon=horizon,
        service=service,
        policy=policy,
        initial_on_hand=initial_on_hand,
        initial_pipeline=initial_pipeline,
        days=tuple(records),
        orders=tuple(orders),
        summary=summary,
    )


def simulate(inputs, calibration, config):
    """Run all paired policies over the same contiguous, verified forecast dates."""
    from app.analytics.schemas import business_day_bounds
    from app.replenishment.calibration import calibrate, paired_evaluation
    from app.replenishment.inputs import select_windows, validate_forecast_coverage
    from app.replenishment.policy import calculate_eoq
    from app.replenishment.schemas import StudyConfig, StudyResult

    config = StudyConfig.model_validate_json(config.model_dump_json())
    validate_forecast_coverage(inputs.forecast.rows, config.evaluation_start, config.evaluation_end)
    if inputs.config != config or calibrate(inputs, config) != calibration:
        raise ValueError("calibration identity mismatch")
    if config.reservations != 0 or config.backlog != 0:
        raise ValueError("UNSUPPORTED_INVENTORY_STATE")
    eoq = calculate_eoq(calibration.annual_demand, config.costs)
    if eoq.state != "ready":
        raise ValueError(eoq.reason_code)
    windows = select_windows(inputs.forecast.rows, config.evaluation_start, config.evaluation_end)
    groups = {(w[0].algorithm, w[0].horizon, w[0].origin): w for w in windows}
    if len(groups) != len(windows) or len({w[0].series_key for w in windows}) != 1:
        raise ValueError("invalid forecast groups")
    algorithms = ("persistence", "seasonal_naive", "xgboost")
    pairs = tuple((a, h) for a in algorithms for h in config.lead_times)
    common = set.intersection(*({o for a2, h2, o in groups if (a2, h2) == pair} for pair in pairs))
    number = (config.evaluation_end - config.evaluation_start).days - max(config.lead_times) + 1
    if number <= config.warmup_days:
        raise ValueError("NO_EVALUATION_WINDOWS")
    expected = {config.evaluation_start + timedelta(days=i - 1) for i in range(number)}
    if common != expected:
        raise ValueError("CALENDAR_UNAVAILABLE")
    observed = {o.day: o for o in inputs.observations}
    if len(observed) != len(inputs.observations):
        raise ValueError("duplicate observation date")
    decision_days = tuple(sorted(o + timedelta(days=1) for o in common))
    for day in decision_days:
        if day not in observed or type(observed[day].value) is not int or observed[day].value < 0:
            raise ValueError("CALENDAR_UNAVAILABLE")
        for a, h in pairs:
            if groups[a, h, day - timedelta(days=1)][0].actual != observed[day].value:
                raise ValueError("forecast/source label mismatch")
    entries = {(entry.algorithm, entry.horizon): entry for entry in calibration.entries}
    if set(entries) != set(pairs) or len(entries) != len(calibration.entries):
        raise ValueError("calibration entries mismatch")
    source_timezone = inputs.forecast.manifest.business_timezone
    if config.mode == "research":
        if source_timezone is not None:
            raise ValueError("retrospective source timezone must remain unknown")
        clock, convention = "UTC", "ANALYTICAL_SCENARIO_CLOCK_UTC"
    else:
        if source_timezone is None:
            raise ValueError("operational timezone unavailable")
        clock, convention = source_timezone, "OPERATIONAL_BUSINESS_TIMEZONE"
    cutoff = business_day_bounds(decision_days[0] - timedelta(days=1), clock)[1]
    trajectories = []
    for algorithm, horizon in pairs:
        for service in config.service_probabilities:
            key = str(service)
            if key not in entries[algorithm, horizon].quantiles:
                raise ValueError("service quantile unavailable")
            quantile = entries[algorithm, horizon].quantiles[key]
            for policy in ("baseline", "proposed"):
                days = tuple(
                    (
                        day,
                        observed[day].value,
                        sum(
                            (
                                max(Decimal(0), _decimal(row.prediction))
                                for row in groups[algorithm, horizon, day - timedelta(days=1)]
                            ),
                            Decimal(0),
                        ),
                    )
                    for day in decision_days
                )
                trajectories.append(
                    simulate_trajectory(
                        days=days,
                        algorithm=algorithm,
                        horizon=horizon,
                        service=service,
                        policy=policy,
                        quantile=quantile,
                        order_quantity=eoq.quantity,
                        initial_on_hand=config.initial_on_hand,
                        initial_pipeline=config.initial_pipeline,
                        reservations=config.reservations,
                        backlog=config.backlog,
                        unit=config.unit,
                        ordering_cost=config.costs.ordering_cost,
                        holding_cost=config.costs.holding_cost,
                        warmup_days=config.warmup_days,
                        initial_cutoff=cutoff,
                    )
                )
    return StudyResult(
        schema_version="replenishment-result/1",
        config=config,
        calibration=calibration,
        eoq=eoq,
        interval_metrics=paired_evaluation(
            inputs.forecast.rows,
            calibration.entries,
            config.evaluation_start,
            config.evaluation_end,
        ),
        trajectories=tuple(trajectories),
        data_version=config.data_version,
        forecast_run_id=config.forecast_run_id,
        source_manifest_sha256=config.source_manifest_sha256,
        public_manifest_sha256=config.public_manifest_sha256,
        source_business_timezone=source_timezone,
        scenario_clock_timezone=clock,
        scenario_clock_convention=convention,
    )
