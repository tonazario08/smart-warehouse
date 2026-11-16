"""Pure service contracts for the B2B nearest-warehouse ranking."""

import math
from types import SimpleNamespace

import pytest

from app.core.errors import DomainError
from app.gis.schemas import distance_mm
from app.models import Product, User
from app.purchase_requests.schemas import NearestWarehouseQuery
from app.purchase_requests.service import (
    EARTH_RADIUS_METERS,
    PurchaseRequestService,
    _warehouse_position,
)


class StubRepository:
    def __init__(self, product: Product | None, rows):
        self.product = product
        self.rows = rows

    def nearest_warehouse_stock(self, product_id: int, quantity: int):
        if self.product is None or product_id != self.product.id or not self.product.is_active:
            return None
        return [
            (warehouse, available)
            for warehouse, available in self.rows
            if available >= quantity
        ]


def actor(role: str = "client", active: bool = True) -> User:
    return User(
        id=1,
        email="nearest@example.test",
        password_hash="fixture",
        role=role,
        is_active=active,
    )


def product(active: bool = True) -> Product:
    return Product(id=7, sku="NEAR", name="Near", category_id=1, unit="each", is_active=active)


def warehouse(identifier: int, latitude: float | None, longitude: float | None):
    return SimpleNamespace(
        id=identifier,
        code=f"W-{identifier}",
        name=f"W {identifier}",
        latitude=latitude,
        longitude=longitude,
    )


def query(**changes) -> NearestWarehouseQuery:
    values = {"product_id": 7, "quantity": 3, "latitude": 10.0, "longitude": 106.0, **changes}
    return NearestWarehouseQuery(**values)


def failure(call) -> DomainError:
    with pytest.raises(DomainError) as raised:
        call()
    return raised.value


def test_position_accepts_boundaries_and_rejects_missing_nonfinite_or_out_of_range():
    assert _warehouse_position(warehouse(1, 10.0, 106.0)) == (106.0, 10.0)
    assert _warehouse_position(warehouse(1, -90.0, 180.0)) == (180.0, -90.0)
    for invalid in (
        warehouse(1, None, None),
        warehouse(1, 10.0, None),
        warehouse(1, math.nan, 106.0),
        warehouse(1, 10.0, math.inf),
        warehouse(1, 90.1, 106.0),
        warehouse(1, 10.0, -180.1),
    ):
        assert _warehouse_position(invalid) is None


def test_ranking_skips_invalid_positions_and_orders_by_haversine_then_id():
    rows = [
        (warehouse(9, 10.5, 106.5), 40),
        (warehouse(3, 10.5, 106.5), 30),
        (warehouse(2, None, None), 99),
        (warehouse(4, math.inf, 106.0), 99),
        (warehouse(5, 10.0, 106.0), 10),
    ]
    result = PurchaseRequestService(StubRepository(product(), rows)).nearest_warehouses(
        actor(), query()
    )
    assert [row.warehouse_id for row in result.warehouses] == [5, 3, 9]
    expected = distance_mm(106.0, 10.0, 106.5, 10.5) / 1_000_000
    assert result.warehouses[1].distance_km == round(expected, 3)
    assert result.warehouses[2].distance_km == round(expected, 3)
    assert result.warehouses[0].distance_km == 0.0
    assert result.method == "great_circle_haversine"
    assert result.earth_radius_meters == EARTH_RADIUS_METERS


def test_distance_arguments_are_longitude_then_latitude():
    """One degree of longitude at latitude 10 is ~109.5 km; a swapped call is ~8750 km."""
    rows = [(warehouse(1, 10.0, 107.0), 5)]
    result = PurchaseRequestService(StubRepository(product(), rows)).nearest_warehouses(
        actor(), query()
    )
    assert result.warehouses[0].distance_km == pytest.approx(109.506, abs=0.001)


@pytest.mark.parametrize(
    ("latitude", "east", "west"),
    [(0.0, 180.0, -180.0), (90.0, 60.0, -120.0)],
)
def test_equivalent_coordinates_tie_by_warehouse_id(latitude, east, west):
    rows = [(warehouse(2, latitude, east), 3), (warehouse(1, latitude, west), 3)]
    result = PurchaseRequestService(StubRepository(product(), rows)).nearest_warehouses(
        actor(), query(latitude=latitude, longitude=east)
    )
    assert [(row.warehouse_id, row.distance_km) for row in result.warehouses] == [(1, 0), (2, 0)]


def test_ranking_applies_request_quantity_to_available_stock():
    rows = [
        (warehouse(1, 10.0, 106.0), 2),
        (warehouse(2, 10.0, 106.0), 3),
        (warehouse(3, 10.0, 106.0), 4),
    ]
    result = PurchaseRequestService(StubRepository(product(), rows)).nearest_warehouses(
        actor(), query(quantity=3)
    )
    assert [(row.warehouse_id, row.available_quantity) for row in result.warehouses] == [
        (2, 3),
        (3, 4),
    ]


@pytest.mark.parametrize("missing", [None, False])
def test_missing_or_inactive_product_is_not_disclosed(missing):
    repository = StubRepository(None if missing is None else product(active=False), [])
    error = failure(
        lambda: PurchaseRequestService(repository).nearest_warehouses(actor(), query())
    )
    assert (error.status_code, error.code) == (404, "PRODUCT_NOT_FOUND")


@pytest.mark.parametrize("role", ["admin", "warehouse"])
def test_non_client_roles_are_forbidden(role):
    error = failure(
        lambda: PurchaseRequestService(StubRepository(product(), [])).nearest_warehouses(
            actor(role), query()
        )
    )
    assert (error.status_code, error.code) == (403, "HTTP_403_ERROR")


def test_inactive_actor_is_unauthenticated():
    error = failure(
        lambda: PurchaseRequestService(StubRepository(product(), [])).nearest_warehouses(
            actor(active=False), query()
        )
    )
    assert (error.status_code, error.code) == (401, "INVALID_CREDENTIALS")
