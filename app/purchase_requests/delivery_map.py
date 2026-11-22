"""Read only a digest-pinned, offline OSM backdrop for customer pin selection."""

import json
import unicodedata
from hashlib import sha256
from pathlib import Path
from threading import Lock
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SOURCE = "https://download.bbbike.org/osm/bbbike/Saigon/Saigon.osm.gz"
REGION = (106.5444, 10.6564, 106.8545, 10.8931)
MAX_FILE_SIZE = 8 * 1024 * 1024
MAX_POINTS = 175_000
Coordinate = Annotated[float, Field(strict=True, allow_inf_nan=False)]
Position = tuple[Coordinate, Coordinate]  # longitude, latitude
Label = Annotated[str, Field(min_length=1, max_length=160, strict=True)]


class _PublicModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MapBounds(_PublicModel):
    west: Coordinate
    south: Coordinate
    east: Coordinate
    north: Coordinate


class Road(_PublicModel):
    name: Label | None
    points: tuple[Position, ...] = Field(min_length=2, max_length=2048)


class Place(_PublicModel):
    name: Label
    kind: Literal["landmark", "water", "park", "neighbourhood"]
    point: Position


class Area(_PublicModel):
    name: Label | None
    kind: Literal["water", "park"]
    ring: tuple[Position, ...] = Field(min_length=4, max_length=2048)


class DeliveryMap(_PublicModel):
    state: Literal["available", "unavailable"]
    bounds: MapBounds | None = None
    roads: tuple[Road, ...] = ()
    places: tuple[Place, ...] = ()
    areas: tuple[Area, ...] = ()
    attribution: str | None = None
    license_url: str | None = None


class _Artifact(_PublicModel):
    format: Literal["b2b-osm-leaflet-v1"]
    source_url: Literal[SOURCE]
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    bounds: tuple[Coordinate, Coordinate, Coordinate, Coordinate]
    roads: tuple[Road, ...] = Field(min_length=1, max_length=8000)
    places: tuple[Place, ...] = Field(min_length=1, max_length=400)
    areas: tuple[Area, ...] = Field(max_length=500)

    @model_validator(mode="after")
    def check_coverage(self):
        west, south, east, north = self.bounds
        if not (REGION[0] <= west < east <= REGION[2] and REGION[1] <= south < north <= REGION[3]):
            raise ValueError("invalid bounds")
        if not any(road.name for road in self.roads):
            raise ValueError("missing named roads")
        remaining = MAX_POINTS

        def check_geometry(name, points):
            nonlocal remaining
            remaining -= len(points)
            if remaining < 0 or any(
                not (west <= x <= east and south <= y <= north) for x, y in points
            ):
                raise ValueError("invalid geometry")
            if name and (
                not name.strip() or any(unicodedata.category(c).startswith("C") for c in name)
            ):
                raise ValueError("invalid label")

        for road in self.roads:
            check_geometry(road.name, road.points)
            if len(set(road.points)) < 2:
                raise ValueError("degenerate road")
        for place in self.places:
            check_geometry(place.name, (place.point,))
        for area in self.areas:
            check_geometry(area.name, area.ring)
            if area.ring[0] != area.ring[-1] or len(set(area.ring)) < 3:
                raise ValueError("invalid polygon")
        return self


class DeliveryMapCatalog:
    def __init__(self, path: Path | None, digest: str | None):
        self._path = path
        self._digest = digest
        self._lock = Lock()
        self._layer: DeliveryMap | None = None

    def read(self) -> DeliveryMap:
        # Limit concurrent cold loads of the same configured artifact.
        with self._lock:
            if self._layer is None:
                self._layer = self._load()
            return self._layer

    def _load(self) -> DeliveryMap:
        unavailable = DeliveryMap(state="unavailable")
        if self._path is None or self._digest is None:
            return unavailable
        try:
            with self._path.open("rb") as file:
                data = file.read(MAX_FILE_SIZE + 1)
            if len(data) > MAX_FILE_SIZE or sha256(data).hexdigest() != self._digest:
                return unavailable
            artifact = _Artifact.model_validate(json.loads(data))
        except (OSError, ValueError, RecursionError):
            return unavailable
        west, south, east, north = artifact.bounds
        return DeliveryMap(
            state="available",
            bounds=MapBounds(west=west, south=south, east=east, north=north),
            attribution="© OpenStreetMap contributors",
            license_url="https://www.openstreetmap.org/copyright",
            roads=artifact.roads,
            places=artifact.places,
            areas=artifact.areas,
        )
