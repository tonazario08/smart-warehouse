from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.inventory.schemas import InventoryFilters, TransactionFilters


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
