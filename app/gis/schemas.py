"""Immutable WGS84 road graph and provenance contracts."""

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal, NamedTuple

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

SOURCE_LIMIT = 400 * 1024 * 1024
CANDIDATE_NODE_LIMIT = 1_000_000
NODE_LIMIT = 120_000
EDGE_LIMIT = 360_000
RESTRICTION_LIMIT = 50_000
GRAPH_LIMIT = 96 * 1024 * 1024
MAX_AGE = timedelta(days=30)

type Bounds = tuple[float, float, float, float]
PUBLIC_BOUNDS: Bounds = (106.64, 10.72, 106.76, 10.82)
PUBLIC_LICENSE = "ODbL 1.0"
PUBLIC_ATTRIBUTION = "© OpenStreetMap contributors"
PUBLIC_SOURCE = re.compile(
    r"https://download\.geofabrik\.de/asia/vietnam-([0-9]{6})\.osm\.pbf"
)
Checksum = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class GraphStats(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    nodes: int = Field(ge=1, le=NODE_LIMIT)
    edges: int = Field(ge=1, le=EDGE_LIMIT)
    restrictions: int = Field(ge=0, le=RESTRICTION_LIMIT)
    excluded_access_ways: int = Field(ge=0)
    excluded_barrier_nodes: int = Field(ge=0, le=CANDIDATE_NODE_LIMIT)
    excluded_restrictions: int = Field(ge=0)
    excluded_restriction_ways: int = Field(ge=0, le=EDGE_LIMIT)


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["warehouse-road-graph/1"] = "warehouse-road-graph/1"
    dataset_class: Literal["public_osm", "synthetic_fixture"]
    snapshot_at: AwareDatetime
    prepared_at: AwareDatetime
    source_url: str | None
    source_sha256: Checksum | None
    graph_sha256: Checksum
    bounds: Bounds
    crs: Literal["EPSG:4326"] = "EPSG:4326"
    weight_unit: Literal["mm"] = "mm"
    converter_version: Literal["warehouse-osm/1"] = "warehouse-osm/1"
    profile_version: Literal["car-reference/1"] = "car-reference/1"
    license: Literal["ODbL 1.0", "synthetic_fixture"]
    attribution: Literal["© OpenStreetMap contributors", "Synthetic fixture"]
    stats: GraphStats

    @model_validator(mode="after")
    def check_provenance(self):
        west, south, east, north = self.bounds
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError("invalid bounds")
        if (
            self.snapshot_at.utcoffset() != timedelta(0)
            or self.prepared_at.utcoffset() != timedelta(0)
            or self.prepared_at < self.snapshot_at
        ):
            raise ValueError("invalid snapshot timing")
        if self.dataset_class == "public_osm":
            if (
                self.source_url is None
                or self.source_sha256 is None
                or not coherent_source_date(self.source_url, self.snapshot_at)
                or self.bounds != PUBLIC_BOUNDS
                or self.license != PUBLIC_LICENSE
                or self.attribution != PUBLIC_ATTRIBUTION
            ):
                raise ValueError("invalid public source metadata")
        elif (
            self.source_url is not None
            or self.source_sha256 is not None
            or self.license != "synthetic_fixture"
            or self.attribution != "Synthetic fixture"
        ):
            raise ValueError("invalid fixture metadata")
        return self


def coherent_source_date(source_url: str, timestamp: datetime) -> bool:
    archive = PUBLIC_SOURCE.fullmatch(source_url)
    return bool(archive and archive[1] == timestamp.astimezone(UTC).strftime("%y%m%d"))


class Node(NamedTuple):
    id: int
    longitude: float
    latitude: float


class Edge(NamedTuple):
    id: int
    way_id: int
    source: int
    target: int
    weight_mm: int


@dataclass(frozen=True, slots=True)
class Graph:
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    restrictions: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class Snapshot:
    snapshot_id: str
    manifest: Manifest
    graph: Graph


def in_bounds(longitude: float, latitude: float, bounds: Bounds) -> bool:
    west, south, east, north = bounds
    return west <= longitude <= east and south <= latitude <= north


def distance_mm(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Spherical distance in mm before edge or heuristic rounding."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    term = math.sin(delta_lat / 2) ** 2
    term += math.cos(phi1) * math.cos(phi2) * math.sin(delta_lon / 2) ** 2
    return 2 * 6_371_008_800 * math.asin(math.sqrt(min(1.0, term)))


def edge_weight(source: Node, target: Node) -> int:
    distance = distance_mm(source.longitude, source.latitude, target.longitude, target.latitude)
    return math.ceil(distance)
