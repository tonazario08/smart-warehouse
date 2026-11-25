"""Transfer validation rejects coercion, invalid bounds and invented client metadata."""

import pytest
from pydantic import ValidationError

from app.transfers.schemas import ProvenanceFilters, TransferCreate, TransferFilters

VALID = {"source_warehouse_id": 1, "destination_warehouse_id": 2, "product_id": 3, "quantity": 4}


@pytest.mark.parametrize("field", VALID)
@pytest.mark.parametrize("value", [True, False, 1.5, "3", 0, -1, 2_147_483_648, None])
def test_transfer_rejects_noninteger_or_out_of_range_numbers(field, value):
    with pytest.raises(ValidationError):
        TransferCreate.model_validate({**VALID, field: value})


def test_distinct_warehouses_and_integer_upper_boundary():
    with pytest.raises(ValidationError):
        TransferCreate.model_validate({**VALID, "destination_warehouse_id": 1})
    assert TransferCreate.model_validate({**VALID, "quantity": 2_147_483_647}).quantity == (
        2_147_483_647
    )


def test_text_is_trimmed_and_blank_text_is_null():
    result = TransferCreate.model_validate({**VALID, "reference": "  CK-01  ", "note": " \n\t"})
    assert result.reference == "CK-01"
    assert result.note is None
    assert TransferCreate.model_validate(VALID).model_dump() == {
        **VALID,
        "reference": None,
        "note": None,
    }


@pytest.mark.parametrize("field,limit", [("reference", 120), ("note", 2000)])
def test_text_limits_after_normalization(field, limit):
    assert getattr(TransferCreate.model_validate({**VALID, field: "x" * limit}), field) == (
        "x" * limit
    )
    with pytest.raises(ValidationError):
        TransferCreate.model_validate({**VALID, field: "x" * (limit + 1)})


@pytest.mark.parametrize("field", ["actor", "created_by_id", "status", "purpose", "transfer_id"])
def test_client_cannot_invent_metadata(field):
    with pytest.raises(ValidationError):
        TransferCreate.model_validate({**VALID, field: 1})


@pytest.mark.parametrize(
    "filters,values",
    [
        (TransferFilters, {"source_warehouse_id": 0}),
        (TransferFilters, {"destination_warehouse_id": 2_147_483_648}),
        (TransferFilters, {"product_id": True}),
        (TransferFilters, {"status": "completed"}),
        (TransferFilters, {"created_from": "2026-10-17T10:00:00"}),
        (TransferFilters, {"created_to": "2026-10-17"}),
        (
            TransferFilters,
            {
                "created_from": "2026-10-18T00:00:00Z",
                "created_to": "2026-10-17T00:00:00Z",
            },
        ),
        (ProvenanceFilters, {"transaction_id": -1}),
        (ProvenanceFilters, {"transfer_id": 2_147_483_648}),
        (ProvenanceFilters, {"purpose": "sales"}),
        (ProvenanceFilters, {"unknown": "value"}),
    ],
)
def test_invalid_filter_contract(filters, values):
    with pytest.raises(ValidationError):
        filters.model_validate(values)


def test_aware_inclusive_date_boundaries_and_neutral_purposes():
    filters = TransferFilters.model_validate(
        {
            "created_from": "2026-10-17T07:00:00+07:00",
            "created_to": "2026-10-17T00:00:00Z",
        }
    )
    assert filters.created_from == filters.created_to
    for purpose in [
        "legacy_unknown",
        "standard_inbound",
        "standard_outbound",
        "transfer_in",
        "transfer_out",
    ]:
        assert ProvenanceFilters(purpose=purpose).purpose == purpose


@pytest.mark.parametrize("value", ["123", "1760745600", 1760745600])
def test_date_filter_does_not_coerce_epoch_values(value):
    with pytest.raises(ValidationError):
        TransferFilters(created_from=value)
