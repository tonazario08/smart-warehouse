"""Authorized GIS reads and road/stock evidence projections."""

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from threading import Lock
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from app.auth.dependencies import PERMISSION_ROLES, Permission
from app.core.config import Settings
from app.core.errors import DomainError
from app.gis.catalog import SnapshotError, check_age, verify_snapshot
from app.gis.repository import MAX_WAREHOUSES, GISRepository
from app.gis.routing import Coordinate, Geometry, RoutingIndex, SearchBudget, Snap
from app.gis.schemas import Bounds, Snapshot, distance_mm, in_bounds
from app.inventory.schemas import MAX_STOCK_QUANTITY
from app.models import Product, User, Warehouse
from app.models.domain import utc_now
from app.purchase_requests.repository import PurchaseRequestRepository
from app.purchase_requests.service import PurchaseRequestService
from app.replenishment.repository import ReplenishmentRepository
from app.replenishment.service import ReplenishmentService
from app.transfers.repository import TransferRepository
from app.transfers.service import TransferService

BUSINESS_TIMEZONE = "Asia/Ho_Chi_Minh"
EXCLUSION_BUCKETS = ("transfer_in", "transfer_out", "standard_outbound", "unclassified_outbound")
STOCK_FIXTURE_LABEL = "Kho và tồn kiểm thử"
OSM_LICENSE_URL = "https://www.openstreetmap.org/copyright"

type SnapshotState = Literal["available", "unconfigured", "invalid", "stale"]
type PlaceKind = Literal["coordinate", "warehouse", "purchase_request"]
type CoordinateIssue = Literal["missing_coordinates", "invalid_coordinates"]
type PositiveInt = Annotated[int, Field(strict=True, ge=1, le=MAX_STOCK_QUANTITY)]


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Coordinates(_Input):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)

    def position(self) -> Coordinate:
        return self.longitude, self.latitude


class CoordinateDestination(Coordinates):
    kind: Literal["coordinate"]


class WarehouseDestination(_Input):
    kind: Literal["warehouse"]
    warehouse_id: PositiveInt


class PurchaseDestination(_Input):
    kind: Literal["purchase_request"]
    request_id: PositiveInt


type Destination = Annotated[
    CoordinateDestination | WarehouseDestination | PurchaseDestination, Field(discriminator="kind")
]


class WarehouseOptionsInput(_Input):
    product_id: PositiveInt
    quantity: PositiveInt
    destination: Destination


class WarehouseRouteInput(_Input):
    kind: Literal["warehouse_to_target"]
    warehouse_id: PositiveInt
    destination: Destination


class TransferRouteInput(_Input):
    kind: Literal["transfer"]
    transfer_id: PositiveInt


type RouteInput = Annotated[WarehouseRouteInput | TransferRouteInput, Field(discriminator="kind")]


class StockData(BaseModel):
    stock_data_class: Literal["operational", "synthetic_fixture"]
    stock_fixture_label: str | None


class SnapshotMetadata(BaseModel):
    snapshot_id: str
    dataset_class: Literal["public_osm", "synthetic_fixture"]
    source_url: str | None
    snapshot_at: datetime
    bounds: Bounds
    crs: Literal["EPSG:4326"]
    weight_unit: Literal["mm"]
    license: str
    attribution: str
    license_url: str | None

    @classmethod
    def from_snapshot(cls, snapshot: Snapshot):
        manifest = snapshot.manifest
        return cls(
            snapshot_id=snapshot.snapshot_id,
            dataset_class=manifest.dataset_class,
            source_url=manifest.source_url,
            snapshot_at=manifest.snapshot_at,
            bounds=manifest.bounds,
            crs=manifest.crs,
            weight_unit=manifest.weight_unit,
            license=manifest.license,
            attribution=manifest.attribution,
            license_url=OSM_LICENSE_URL if manifest.dataset_class == "public_osm" else None,
        )


class SnapshotStatus(StockData):
    state: SnapshotState
    snapshot: SnapshotMetadata | None


class ProductRead(BaseModel):
    product_id: int
    sku: str
    name: str
    unit: str

    @classmethod
    def from_product(cls, product: Product):
        return cls(product_id=product.id, sku=product.sku, name=product.name, unit=product.unit)


class WarehouseRead(BaseModel):
    warehouse_id: int
    code: str
    name: str
    latitude: float | None
    longitude: float | None


class Place(BaseModel):
    kind: PlaceKind
    coordinate: Coordinates | None
    warehouse: WarehouseRead | None = None
    request_id: int | None = None


class WarehouseOption(BaseModel):
    warehouse: WarehouseRead
    available_quantity: int | None


class RankedWarehouse(WarehouseOption):
    available_quantity: int
    distance_mm: int
    snapshot_id: str


class GeographicWarehouse(WarehouseOption):
    available_quantity: int
    distance_mm: int
    reason: str


class ExcludedWarehouse(WarehouseOption):
    reason: str


class WarehouseOptions(StockData):
    stock_as_of: datetime
    product: ProductRead
    quantity: int
    destination: Place
    snapshot_state: SnapshotState
    snapshot: SnapshotMetadata | None
    ranking_state: Literal["available", "unavailable", "budget_exceeded"]
    ranked: list[RankedWarehouse]
    geographic_only: list[GeographicWarehouse]
    excluded: list[ExcludedWarehouse]


class TransferContext(BaseModel):
    transfer_id: int
    mode: Literal["immediate"] = "immediate"


class RouteRead(StockData):
    snapshot_state: SnapshotState
    snapshot: SnapshotMetadata | None
    origin: Place
    destination: Place
    origin_snap: Snap | None = None
    destination_snap: Snap | None = None
    geometry: Geometry | None = None
    distance_mm: int | None = None
    reason: str | None = None
    transfer: TransferContext | None = None


class HeatmapPoint(BaseModel):
    warehouse: WarehouseRead
    fulfilled_quantity: int = 0
    transaction_count: int = 0


class MovementTotal(BaseModel):
    quantity: int = 0
    transaction_count: int = 0


class Heatmap(StockData):
    product: ProductRead
    start_date: date
    end_date: date
    start_utc: datetime
    end_utc: datetime
    timezone: Literal["Asia/Ho_Chi_Minh"] = BUSINESS_TIMEZONE
    queried_at: datetime
    points: list[HeatmapPoint]
    unlocated: list[HeatmapPoint]
    excluded: dict[str, MovementTotal]


class PolicyRun(BaseModel):
    run_id: str
    data_version: str
    created_at: datetime
    fixture_label: str
    href: str


class PolicyContext(BaseModel):
    state: Literal["applicable", "not_applicable"]
    run: PolicyRun | None = None


@dataclass(frozen=True, slots=True)
class _Roads:
    state: SnapshotState
    snapshot: SnapshotMetadata | None = None
    index: RoutingIndex | None = None


class SnapshotCatalog:
    """Keep one verified index per application worker and enforce age on every read."""

    def __init__(self, settings: Settings) -> None:
        self._root = settings.gis_catalog_root
        self._snapshot_id = settings.gis_snapshot_id
        self.allow_fixture = (
            settings.gis_allow_fixture and settings.app_env in ("test", "integration")
        )
        self._lock = Lock()
        self._index: RoutingIndex | None = None
        self._metadata: SnapshotMetadata | None = None

    def read(self) -> _Roads:
        if self._root is None and self._snapshot_id is None:
            return _Roads("unconfigured")
        if self._root is None or self._snapshot_id is None:
            return _Roads("invalid")
        with self._lock:
            now = utc_now()
            try:
                if self._index is None:
                    snapshot = verify_snapshot(
                        self._root, self._snapshot_id, now, self.allow_fixture
                    )
                    self._metadata = SnapshotMetadata.from_snapshot(snapshot)
                    self._index = RoutingIndex(snapshot)
                else:
                    manifest = self._index.snapshot.manifest
                    if manifest.prepared_at > now:
                        return _Roads("invalid")
                    check_age(manifest.snapshot_at, now)
            except SnapshotError as failure:
                if failure.code == "stale":
                    return _Roads("stale", self._metadata)
                return _Roads("invalid")
            return _Roads("available", self._metadata, self._index)

    def stock_data(self) -> dict:
        return {
            "stock_data_class": "synthetic_fixture" if self.allow_fixture else "operational",
            "stock_fixture_label": STOCK_FIXTURE_LABEL if self.allow_fixture else None,
        }


@dataclass(frozen=True, slots=True)
class _ResolvedPlace:
    place: Place
    issue: CoordinateIssue | None = None


def _warehouse_position(warehouse: Warehouse) -> tuple[Coordinates | None, CoordinateIssue | None]:
    lon, lat = warehouse.longitude, warehouse.latitude
    if lon is None and lat is None:
        return None, "missing_coordinates"
    if lon is None or lat is None or not in_bounds(lon, lat, (-180, -90, 180, 90)):
        return None, "invalid_coordinates"
    return Coordinates(latitude=lat, longitude=lon), None


def _warehouse_read(warehouse: Warehouse, coordinate: Coordinates | None) -> WarehouseRead:
    return WarehouseRead(
        warehouse_id=warehouse.id,
        code=warehouse.code,
        name=warehouse.name,
        latitude=coordinate.latitude if coordinate is not None else None,
        longitude=coordinate.longitude if coordinate is not None else None,
    )


def _as_utc(timestamp: datetime) -> datetime:
    return timestamp.astimezone(UTC) if timestamp.utcoffset() is not None else timestamp.replace(
        tzinfo=UTC
    )


def _missing_product():
    return DomainError(404, "GIS_PRODUCT_NOT_FOUND", "Active product was not found.")


class GISService:
    def __init__(self, repository: GISRepository, catalog: SnapshotCatalog, settings: Settings):
        self.repository = repository
        self.catalog = catalog
        self.settings = settings

    def status(self) -> SnapshotStatus:
        roads = self.catalog.read()
        return SnapshotStatus(
            state=roads.state, snapshot=roads.snapshot, **self.catalog.stock_data()
        )

    def _purchase(self, actor: User, destination: Destination):
        if isinstance(destination, PurchaseDestination):
            return PurchaseRequestService(PurchaseRequestRepository(self.repository.session)).get(
                actor, destination.request_id
            )
        return None

    @staticmethod
    def _warehouse_place(
        warehouse: Warehouse | None, kind: PlaceKind = "warehouse", request_id: int | None = None
    ) -> _ResolvedPlace:
        if warehouse is None:
            raise DomainError(404, "GIS_WAREHOUSE_NOT_FOUND", "Warehouse was not found.")
        coordinate, issue = _warehouse_position(warehouse)
        return _ResolvedPlace(
            Place(
                kind=kind,
                coordinate=coordinate,
                warehouse=_warehouse_read(warehouse, coordinate),
                request_id=request_id,
            ),
            issue,
        )

    def _destination(self, target: Destination, purchase, lookup) -> _ResolvedPlace:
        if isinstance(target, CoordinateDestination):
            return _ResolvedPlace(Place(
                kind="coordinate",
                coordinate=Coordinates(latitude=target.latitude, longitude=target.longitude),
            ))
        if isinstance(target, WarehouseDestination):
            return self._warehouse_place(lookup(target.warehouse_id))
        return self._warehouse_place(lookup(purchase.warehouse_id), "purchase_request", purchase.id)

    def warehouse_options(self, actor: User, body: WarehouseOptionsInput) -> WarehouseOptions:
        purchase = self._purchase(actor, body.destination)
        if purchase is not None and (purchase.product_id, purchase.quantity) != (
            body.product_id, body.quantity
        ):
            raise DomainError(
                422, "GIS_PURCHASE_REQUEST_MISMATCH", "Product or quantity differs from request."
            )
        rows = self.repository.warehouse_options(body.product_id)
        if not rows:
            raise _missing_product()
        if len(rows) > MAX_WAREHOUSES:
            raise DomainError(422, "GIS_WAREHOUSE_LIMIT", "Too many warehouses for one ranking.")
        product, _, _, stock_as_of = rows[0]
        warehouses = {warehouse.id: warehouse for _, warehouse, _, _ in rows if warehouse}
        target = self._destination(body.destination, purchase, warehouses.get)
        roads = self.catalog.read()

        candidates = []
        excluded = []
        for _, warehouse, quantity, _ in rows:
            if warehouse is None:
                continue
            coordinate, issue = _warehouse_position(warehouse)
            display = _warehouse_read(warehouse, coordinate)
            reason = None
            if quantity is None:
                reason = "missing_stock"
            elif quantity < body.quantity:
                reason = "insufficient_stock"
            elif issue is not None:
                reason = issue
            elif target.issue is not None:
                reason = f"destination_{target.issue}"
            if reason is None:
                candidates.append((display, quantity, coordinate.position()))
            else:
                excluded.append(ExcludedWarehouse(
                    warehouse=display, available_quantity=quantity, reason=reason
                ))

        ranked: list[RankedWarehouse] = []
        geographic: list[GeographicWarehouse] = []
        ranking_state = "unavailable"
        if target.place.coordinate is not None:
            ranked, geographic, ranking_state = self._rank(
                candidates, target.place.coordinate.position(), roads
            )
        return WarehouseOptions(
            stock_as_of=_as_utc(stock_as_of),
            product=ProductRead.from_product(product),
            quantity=body.quantity,
            destination=target.place,
            snapshot_state=roads.state,
            snapshot=roads.snapshot,
            ranking_state=ranking_state,
            ranked=ranked,
            geographic_only=geographic,
            excluded=excluded,
            **self.catalog.stock_data(),
        )

    @staticmethod
    def _rank(candidates, destination: Coordinate, roads: _Roads):
        budget = SearchBudget()
        ranked = []
        geographic = []
        ranking_state = "available" if roads.index is not None else "unavailable"

        def fallback(candidate, reason: str) -> GeographicWarehouse:
            warehouse, quantity, position = candidate
            return GeographicWarehouse(
                warehouse=warehouse,
                available_quantity=quantity,
                distance_mm=math.ceil(distance_mm(*position, *destination)),
                reason=reason,
            )

        for candidate in candidates:
            warehouse, quantity, position = candidate
            if roads.index is None:
                geographic.append(fallback(candidate, f"snapshot_{roads.state}"))
                continue
            route = roads.index.route(position, destination, budget=budget)
            if route.reason == "budget_exceeded":
                ranking_state = "budget_exceeded"
                ranked = []
                geographic = [fallback(item, "budget_exceeded") for item in candidates]
                break
            if route.reason is not None:
                geographic.append(fallback(candidate, route.reason))
            else:
                ranked.append(RankedWarehouse(
                    warehouse=warehouse,
                    available_quantity=quantity,
                    distance_mm=route.distance_mm,
                    snapshot_id=roads.index.snapshot.snapshot_id,
                ))
        ranked.sort(key=lambda row: (row.distance_mm, row.warehouse.warehouse_id))
        geographic.sort(key=lambda row: (row.distance_mm, row.warehouse.warehouse_id))
        return ranked, geographic, ranking_state

    def route(self, actor: User, body: RouteInput) -> RouteRead:
        lookup = self.repository.warehouse
        context = None
        if isinstance(body, TransferRouteInput):
            if actor.role not in PERMISSION_ROLES[Permission.INVENTORY_HISTORY_READ]:
                raise DomainError(403, "HTTP_403_ERROR", "Permission denied")
            transfer = TransferService(TransferRepository(self.repository.session)).get(
                body.transfer_id
            )
            origin = self._warehouse_place(lookup(transfer.source_warehouse_id))
            target = self._warehouse_place(lookup(transfer.destination_warehouse_id))
            context = TransferContext(transfer_id=transfer.id)
        else:
            purchase = self._purchase(actor, body.destination)
            target = self._destination(body.destination, purchase, lookup)
            origin = self._warehouse_place(lookup(body.warehouse_id))
        roads = self.catalog.read()
        common = {
            "snapshot_state": roads.state,
            "snapshot": roads.snapshot,
            "origin": origin.place,
            "destination": target.place,
            "transfer": context,
            **self.catalog.stock_data(),
        }
        if origin.issue is not None:
            return RouteRead(**common, reason=f"origin_{origin.issue}")
        if target.issue is not None:
            return RouteRead(**common, reason=f"destination_{target.issue}")
        if roads.index is None:
            return RouteRead(**common, reason=f"snapshot_{roads.state}")

        result = roads.index.route(
            origin.place.coordinate.position(), target.place.coordinate.position(),
            budget=SearchBudget(),
        )
        return RouteRead(
            **common,
            origin_snap=result.origin_snap,
            destination_snap=result.destination_snap,
            geometry=result.geometry,
            distance_mm=result.distance_mm,
            reason=result.reason,
        )

    def heatmap(self, product_id: int, start_date: date, end_date: date) -> Heatmap:
        if not 1 <= (end_date - start_date).days <= 90:
            raise DomainError(422, "GIS_PERIOD_INVALID", "Select a period from one to 90 days.")
        zone = ZoneInfo(BUSINESS_TIMEZONE)
        try:
            start = datetime.combine(start_date, time.min, zone).astimezone(UTC)
            end = datetime.combine(end_date, time.min, zone).astimezone(UTC)
        except OverflowError:
            raise DomainError(422, "GIS_PERIOD_INVALID", "Date is out of range.") from None

        rows = self.repository.heatmap(product_id, start, end)
        if not rows:
            raise _missing_product()
        product, _, queried_at, *_ = rows[0]
        points = {}
        unlocated = {}
        exclusions = {name: MovementTotal() for name in EXCLUSION_BUCKETS}
        for _, warehouse, _, bucket, quantity, count in rows:
            if warehouse is None:
                continue
            coordinate, _ = _warehouse_position(warehouse)
            target = points if coordinate is not None else unlocated
            if warehouse.id not in target:
                target[warehouse.id] = HeatmapPoint(
                    warehouse=_warehouse_read(warehouse, coordinate)
                )
            if bucket == "fulfillment":
                target[warehouse.id].fulfilled_quantity = quantity
                target[warehouse.id].transaction_count = count
            elif bucket is not None:
                exclusions[bucket].quantity += quantity
                exclusions[bucket].transaction_count += count
        return Heatmap(
            product=ProductRead.from_product(product),
            start_date=start_date,
            end_date=end_date,
            start_utc=start,
            end_utc=end,
            queried_at=_as_utc(queried_at),
            points=list(points.values()),
            unlocated=list(unlocated.values()),
            excluded=exclusions,
            **self.catalog.stock_data(),
        )

    def policy_context(
        self, actor: User, run_id: str, product_id: int, warehouse_id: int
    ) -> PolicyContext:
        unavailable = PolicyContext(state="not_applicable")
        if not (self.catalog.allow_fixture and self.settings.replenishment_allow_fixture):
            return unavailable
        repository = ReplenishmentRepository(
            self.settings.replenishment_catalog_root, allow_fixture=True
        )
        service = ReplenishmentService(repository, self.repository.session)
        try:
            manifest = service.get(actor, run_id)["manifest"]
        except DomainError as failure:
            if failure.status_code in (401, 403):
                raise
            return unavailable
        binding = manifest["binding"]
        if (
            manifest["mode"] != "operational"
            or manifest["dataset_class"] != "fixture"
            or manifest["applicability"] != "fixture_scenario"
            or binding is None
            or (binding["product_id"], binding["warehouse_id"]) != (product_id, warehouse_id)
        ):
            return unavailable
        product = self.repository.product(product_id)
        if (
            product is None
            or not product.is_active
            or product.unit != binding["unit"]
            or self.repository.warehouse(warehouse_id) is None
        ):
            return unavailable
        return PolicyContext(
            state="applicable",
            run=PolicyRun(
                run_id=manifest["run_id"],
                data_version=manifest["data_version"],
                created_at=manifest["created_at"],
                fixture_label="Kịch bản kiểm thử",
                href=f"/replenishment/runs/{manifest['run_id']}",
            ),
        )
