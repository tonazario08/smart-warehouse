"""New boundaries must not coerce forged quantities, timestamps or workflow data."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.purchase_requests.schemas import (
    PurchaseRequestAction,
    PurchaseRequestCreate,
    PurchaseRequestDecisionResponse,
    PurchaseRequestFilters,
    PurchaseRequestFulfillmentResponse,
    PurchaseRequestReject,
    PurchaseRequestResponse,
)

VALID = {"warehouse_id": 1, "product_id": 2, "quantity": 3}
NOW = datetime(2026, 10, 19, tzinfo=UTC)


@pytest.mark.parametrize("field", VALID)
@pytest.mark.parametrize("value", [0, -1, 2147483648, True, False, 1.5, "3", None])
def test_create_input_is_strict(field, value):
    with pytest.raises(ValidationError):
        PurchaseRequestCreate.model_validate({**VALID, field: value})


def test_create_input_is_normalized_and_accepts_integer_boundaries():
    assert PurchaseRequestCreate(**VALID, note=" \n\t ").note is None
    assert PurchaseRequestCreate(**VALID, note="  tiếng Việt  ").note == "tiếng Việt"
    for quantity in (1, 2147483647):
        assert PurchaseRequestCreate(**{**VALID, "quantity": quantity}).quantity == quantity
    assert PurchaseRequestCreate(**VALID).model_dump() == {**VALID, "note": None}


@pytest.mark.parametrize(
    "field",
    ["requested_by_id", "status", "request_number", "decision", "fulfillment", "idempotency_key"],
)
def test_create_forbids_forged_workflow_metadata(field):
    with pytest.raises(ValidationError):
        PurchaseRequestCreate.model_validate({**VALID, field: "forged"})


@pytest.mark.parametrize("value", [1, True, [], {}])
def test_text_rejects_nonstring_values(value):
    with pytest.raises(ValidationError):
        PurchaseRequestCreate(**VALID, note=value)
    with pytest.raises(ValidationError):
        PurchaseRequestReject(rejection_reason=value)


def test_text_lengths_apply_after_trimming():
    assert len(PurchaseRequestCreate(**VALID, note=" " + "n" * 2000 + " ").note) == 2000
    with pytest.raises(ValidationError):
        PurchaseRequestCreate(**VALID, note="n" * 2001)
    assert PurchaseRequestReject(rejection_reason=" " + "r" * 1000 + " ").rejection_reason == (
        "r" * 1000
    )
    for value in ("r" * 1001, "", " \n\t ", None):
        with pytest.raises(ValidationError):
            PurchaseRequestReject(rejection_reason=value)


def test_action_and_reject_allow_only_exact_payloads():
    assert PurchaseRequestAction.model_validate({}).model_dump() == {}
    assert PurchaseRequestReject(rejection_reason=" lý do ").model_dump() == {
        "rejection_reason": "lý do"
    }
    for model, body in (
        (PurchaseRequestAction, {"status": "approved"}),
        (PurchaseRequestReject, {"rejection_reason": "reason", "decided_by_id": 9}),
    ):
        with pytest.raises(ValidationError):
            model.model_validate(body)


@pytest.mark.parametrize("field", ["warehouse_id", "product_id", "requested_by_id"])
@pytest.mark.parametrize("value", [0, 2147483648, True, 1.5, "3"])
def test_filters_reject_coercion_and_invalid_ids(field, value):
    with pytest.raises(ValidationError):
        PurchaseRequestFilters.model_validate({field: value})


@pytest.mark.parametrize("field", ["created_from", "created_to"])
@pytest.mark.parametrize(
    "value",
    [
        "123",
        "1760745600",
        1760745600,
        True,
        "2026-10-19",
        "2026-10-19T10:00:00",
        datetime(2026, 10, 19),
    ],
)
def test_filters_reject_epoch_and_naive_dates(field, value):
    with pytest.raises(ValidationError):
        PurchaseRequestFilters.model_validate({field: value})


def test_filters_reject_reversed_dates_and_unknown_fields():
    with pytest.raises(ValidationError):
        PurchaseRequestFilters(created_from="2026-10-20T00:00:00Z", created_to=NOW)
    with pytest.raises(ValidationError):
        PurchaseRequestFilters(unknown="anything")
    with pytest.raises(ValidationError):
        PurchaseRequestFilters(status="completed")
    filters = PurchaseRequestFilters(created_from="2026-10-19T07:00:00+07:00", created_to=NOW)
    assert filters.created_from == filters.created_to == NOW


@pytest.mark.parametrize("status", ["pending", "approved", "rejected", "fulfilled"])
def test_response_is_exact_with_explicit_legacy_nulls(status):
    body = {
        "id": 1,
        "request_number": "PR-history",
        **VALID,
        "status": status,
        "requested_by_id": 7,
        "created_at": NOW,
        "updated_at": NOW,
        "workflow_managed": False,
        "note": None,
        "decision": None,
        "fulfillment": None,
    }
    assert PurchaseRequestResponse.model_validate(body).model_dump() == body
    for field in ("note", "decision", "fulfillment", "workflow_managed"):
        with pytest.raises(ValidationError):
            PurchaseRequestResponse.model_validate({k: v for k, v in body.items() if k != field})
    for field in ("idempotency_key", "request_fingerprint", "user"):
        with pytest.raises(ValidationError):
            PurchaseRequestResponse.model_validate({**body, field: "secret"})


def test_nested_response_shapes_require_aware_times_and_no_extra_fields():
    decision = {"kind": "approved", "actor_id": 1, "decided_at": NOW, "rejection_reason": None}
    fulfillment = {
        "outbound_id": 2,
        "transaction_id": 3,
        "actor_id": 1,
        "fulfilled_at": NOW,
        "quantity_before": 10,
        "quantity_after": 7,
    }
    assert PurchaseRequestDecisionResponse(**decision).model_dump() == decision
    assert PurchaseRequestFulfillmentResponse(**fulfillment).model_dump() == fulfillment
    for model, body, time_field in (
        (PurchaseRequestDecisionResponse, decision, "decided_at"),
        (PurchaseRequestFulfillmentResponse, fulfillment, "fulfilled_at"),
    ):
        for invalid in ({**body, "user": {}}, {**body, time_field: datetime(2026, 10, 19)}):
            with pytest.raises(ValidationError):
                model.model_validate(invalid)
        for field in body:
            with pytest.raises(ValidationError):
                model.model_validate({k: v for k, v in body.items() if k != field})
    with pytest.raises(ValidationError):
        PurchaseRequestDecisionResponse(**{**decision, "kind": "pending"})
