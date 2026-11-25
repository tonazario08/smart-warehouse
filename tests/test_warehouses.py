"""Database-independent warehouse request validation tests."""

import pytest
from pydantic import ValidationError

from app.warehouse.schemas import WarehouseWrite


def test_warehouse_write_normalizes_code_and_trims_text():
    warehouse = WarehouseWrite(
        code="  hcm-01 ", name=" Central ", address=" 1 Main Road "
    )

    assert warehouse.model_dump() == {
        "code": "HCM-01",
        "name": "Central",
        "address": "1 Main Road",
        "latitude": None,
        "longitude": None,
    }


@pytest.mark.parametrize(
    "coordinates",
    [
        {"latitude": 10.0},
        {"longitude": 106.0},
        {"latitude": -90.01, "longitude": 0},
        {"latitude": 90.01, "longitude": 0},
        {"latitude": 0, "longitude": -180.01},
        {"latitude": 0, "longitude": 180.01},
    ],
)
def test_warehouse_write_rejects_unpaired_or_out_of_range_coordinates(coordinates):
    with pytest.raises(ValidationError):
        WarehouseWrite(code="HCM-01", name="Central", address="Road", **coordinates)


def test_warehouse_write_rejects_blank_values_and_extra_fields():
    for values in (
        {"code": " ", "name": "Central", "address": "Road"},
        {"code": "HCM-01", "name": " ", "address": "Road"},
        {"code": "HCM-01", "name": "Central", "address": " "},
        {"code": "HCM-01", "name": "Central", "address": "Road", "extra": True},
    ):
        with pytest.raises(ValidationError):
            WarehouseWrite(**values)
