from decimal import Decimal

import pytest


def test_eoq_and_zero_or_missing_cost_priorities():
    from app.replenishment.policy import calculate_eoq
    from app.replenishment.schemas import CostInputs

    def cost(k, h):
        return CostInputs(ordering_cost=k, holding_cost=h, currency="VND", holding_period="year")

    eoq = calculate_eoq(Decimal("1000"), cost(Decimal("100"), Decimal("2")))
    assert eoq.state == "ready" and eoq.quantity == 317
    assert abs(eoq.raw - Decimal("100000").sqrt()) < Decimal("1e-9")
    zero = calculate_eoq(Decimal("0"), cost(Decimal("100"), Decimal("2")))
    assert (zero.quantity, zero.reason_code) == (0, "ZERO_DEMAND")
    assert (
        calculate_eoq(Decimal("0"), cost(None, Decimal("2"))).reason_code == "ORDERING_COST_MISSING"
    )
    assert (
        calculate_eoq(Decimal("0"), cost(Decimal("0"), Decimal("2"))).reason_code
        == "ORDERING_COST_ZERO"
    )
    assert (
        calculate_eoq(Decimal("1"), cost(Decimal("1"), None)).reason_code == "HOLDING_COST_MISSING"
    )
    assert (
        calculate_eoq(Decimal("1"), cost(Decimal("1"), Decimal("0"))).reason_code
        == "HOLDING_COST_ZERO"
    )
    for value in (True, Decimal("NaN"), Decimal("-1")):
        with pytest.raises(ValueError):
            calculate_eoq(value, cost(Decimal("1"), Decimal("1")))


def test_policy_safety_stock_and_rounding():
    from app.replenishment.policy import calculate_eoq, calculate_policy
    from app.replenishment.schemas import CostInputs

    eoq = calculate_eoq(
        Decimal("1000"),
        CostInputs(
            ordering_cost=Decimal("100"),
            holding_cost=Decimal("2"),
            currency="VND",
            holding_period="year",
        ),
    )
    for mean, residual, stock, reorder in [
        ("10", "3", 3, 13),
        ("10", "-2", 0, 10),
        ("10.1", ".2", Decimal(".2"), 11),
    ]:
        result = calculate_policy(Decimal(mean), Decimal(residual), eoq)
        assert (result.safety_stock, result.reorder_point) == (stock, reorder)
    with pytest.raises(ValueError):
        calculate_policy(True, Decimal("1"), eoq)


def test_policy_refuses_inconsistent_or_negative_eoq_contract():
    from app.replenishment.policy import calculate_policy
    from app.replenishment.schemas import EoqResult

    with pytest.raises(ValueError):
        forged = EoqResult(state="ready", reason_code=None, raw=Decimal("-1"), quantity=-1)
        calculate_policy(Decimal("1"), Decimal("1"), forged)
    with pytest.raises(ValueError):
        forged = EoqResult(state="ready", reason_code=None, raw=None, quantity=3)
        calculate_policy(Decimal("1"), Decimal("1"), forged)
