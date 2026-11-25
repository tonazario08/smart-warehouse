"""Strict advisory EOQ and reorder calculations; no operational side effects."""

from decimal import ROUND_CEILING, Decimal

from app.replenishment.schemas import CostInputs, EoqResult, PolicyDecision


def _decimal(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError("finite number required")
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("finite number required")
    return result


def calculate_eoq(demand_per_year: Decimal, costs: CostInputs) -> EoqResult:
    demand = _decimal(demand_per_year)
    costs = CostInputs.model_validate_json(costs.model_dump_json())
    if demand < 0:
        raise ValueError("nonnegative demand required")
    for value, label in (
        (costs.ordering_cost, "ORDERING_COST"),
        (costs.holding_cost, "HOLDING_COST"),
    ):
        if value is None:
            return EoqResult(
                state="unavailable", reason_code=label + "_MISSING", raw=None, quantity=None
            )
        if value == 0:
            return EoqResult(
                state="unavailable", reason_code=label + "_ZERO", raw=None, quantity=None
            )
    if demand == 0:
        return EoqResult(state="ready", reason_code="ZERO_DEMAND", raw=Decimal(0), quantity=0)
    value = (2 * demand * costs.ordering_cost / costs.holding_cost).sqrt()
    return EoqResult(
        state="ready",
        reason_code=None,
        raw=value,
        quantity=int(value.to_integral_value(rounding=ROUND_CEILING)),
    )


def calculate_policy(mean: Decimal, residual_quantile: Decimal, eoq: EoqResult) -> PolicyDecision:
    mean = _decimal(mean)
    residual = _decimal(residual_quantile)
    eoq = EoqResult.model_validate_json(eoq.model_dump_json())
    if mean < 0:
        raise ValueError("nonnegative forecast required")
    if eoq.state != "ready" or eoq.quantity is None:
        return PolicyDecision(
            state="unavailable",
            reason_code=eoq.reason_code,
            safety_stock=None,
            reorder_point=None,
            order_quantity=None,
        )
    stock = max(Decimal(0), residual)
    return PolicyDecision(
        state="ready",
        reason_code=None,
        safety_stock=stock,
        reorder_point=int((mean + stock).to_integral_value(rounding=ROUND_CEILING)),
        order_quantity=eoq.quantity,
    )
