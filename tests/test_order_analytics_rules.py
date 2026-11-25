import pytest

from app.order_analytics.rules import check_quantity


@pytest.mark.parametrize(
    ("history", "quantity", "status", "flag", "reason"),
    [
        ([10, 12, 11, 9, 10, 13, 11, 10], 11, "available", False, None),
        ([10, 12, 11, 9, 10, 13, 11, 10], 14, "available", True, "QUANTITY_HIGH"),
        ([10, 12, 11, 9, 10, 13, 11, 10], 30, "available", True, "QUANTITY_HIGH"),
        ([10, 12, 11, 9, 10, 13, 11, 10], 2, "available", True, "QUANTITY_LOW"),
        ([5] * 8, 14, "available", False, None),
        ([5] * 8, 15, "available", True, "QUANTITY_HIGH"),
        ([5] * 8, 1, "available", True, "QUANTITY_LOW"),
        ([5] * 7, 30, "insufficient_data", None, "INSUFFICIENT_HISTORY"),
    ],
)
def test_rule_vectors(history, quantity, status, flag, reason):
    actual = check_quantity(quantity, history)
    assert (actual.status, actual.flagged, actual.reason_code) == (status, flag, reason)
    assert actual.sample_count == len(history)


def test_rule_reports_median_mad_and_score():
    actual = check_quantity(14, [10, 12, 11, 9, 10, 13, 11, 10])
    assert (actual.median, actual.mad) == (10.5, 0.5)
    assert actual.score == pytest.approx(4.7215)
    assert check_quantity(15, [5] * 8).score is None
