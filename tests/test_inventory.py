from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.inventory.schemas import InventoryFilters, InventoryMovementCreate, TransactionFilters


@pytest.mark.parametrize("quantity", [2_147_483_648, 9_223_372_036_854_775_808])
def test_movement_rejects_quantity_above_database_integer_range(quantity: int) -> None:
    with pytest.raises(ValidationError):
        InventoryMovementCreate(warehouse_id=1, product_id=1, quantity=quantity)


def test_movement_accepts_database_boundary_and_rejects_overlong_reference() -> None:
    movement = InventoryMovementCreate(
        warehouse_id=1, product_id=1, quantity=2_147_483_647, reference="R" * 120
    )
    assert movement.quantity == 2_147_483_647
    assert len(movement.reference) == 120
    with pytest.raises(ValidationError):
        InventoryMovementCreate(warehouse_id=1, product_id=1, quantity=1, reference="R" * 121)


def test_inventory_filters_require_timezone_aware_ordered_range() -> None:
    filters = InventoryFilters(
        created_from=datetime(2026, 1, 1, tzinfo=UTC),
        created_to=datetime(2026, 1, 2, tzinfo=UTC),
    )
    assert filters.created_from is not None

    with pytest.raises(ValidationError):
        InventoryFilters(created_from=datetime(2026, 1, 1))
    with pytest.raises(ValidationError):
        InventoryFilters(
            created_from=datetime(2026, 1, 2, tzinfo=UTC),
            created_to=datetime(2026, 1, 1, tzinfo=UTC),
        )


def test_transaction_filters_reject_unknown_fields_and_invalid_type() -> None:
    with pytest.raises(ValidationError):
        TransactionFilters(unexpected="value")
    with pytest.raises(ValidationError):
        TransactionFilters(transaction_type="transfer")
