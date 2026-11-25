"""Deterministic snapping and turn-aware A* for admitted road snapshots."""

import heapq
import math
from collections import defaultdict
from dataclasses import dataclass
from itertools import product
from typing import Literal

from app.gis.schemas import Edge, Node, Snapshot, distance_mm, in_bounds

MAX_SETTLED = 250_000
MAX_COORDINATES = 4_000
SNAP_LIMIT_MM = 200_000
# Angular radius bounds the unit-sphere chord length, and therefore each component delta.
GRID_CELL = SNAP_LIMIT_MM / 6_371_008_800
NEIGHBOR_CELLS = tuple(product((-1, 0, 1), repeat=3))

type Coordinate = tuple[float, float]
type State = tuple[int, int]
type RouteReason = Literal[
    "outside_coverage", "snap_too_far", "no_route", "budget_exceeded", "geometry_limit"
]


@dataclass(frozen=True, slots=True)
class Geometry:
    type: Literal["Point", "LineString"]
    coordinates: Coordinate | tuple[Coordinate, ...]


@dataclass(frozen=True, slots=True)
class Snap:
    node_id: int
    coordinates: Coordinate
    distance_mm: int
    connector: Geometry | None


@dataclass(frozen=True, slots=True)
class RouteResult:
    reason: RouteReason | None = None
    distance_mm: int | None = None
    geometry: Geometry | None = None
    origin_snap: Snap | None = None
    destination_snap: Snap | None = None


class SearchBudget:
    """Share one request-local limit across successive routes."""

    def __init__(self, max_settled: int = MAX_SETTLED) -> None:
        if type(max_settled) is not int or not 0 <= max_settled <= MAX_SETTLED:
            raise ValueError("invalid route search budget")
        self._max_settled = max_settled
        self._remaining = max_settled

    @property
    def remaining(self) -> int:
        return self._remaining

    @property
    def settled(self) -> int:
        return self._max_settled - self._remaining

    def _settle(self) -> bool:
        if self._remaining == 0:
            return False
        self._remaining -= 1
        return True


def _grid_cell(longitude: float, latitude: float) -> tuple[int, int, int]:
    lon, lat = math.radians(longitude), math.radians(latitude)
    cos_lat = math.cos(lat)
    return (
        math.floor(cos_lat * math.cos(lon) / GRID_CELL),
        math.floor(cos_lat * math.sin(lon) / GRID_CELL),
        math.floor(math.sin(lat) / GRID_CELL),
    )


class RoutingIndex:
    """Compile an admitted snapshot once and reuse it across route queries."""

    def __init__(self, snapshot: Snapshot) -> None:
        self.snapshot = snapshot
        self._nodes = {node.id: node for node in snapshot.graph.nodes}
        self._prohibited = frozenset(snapshot.graph.restrictions)

        outgoing: dict[int, list[Edge]] = defaultdict(list)
        for edge in snapshot.graph.edges:
            outgoing[edge.source].append(edge)
        self._outgoing = {
            node_id: tuple(sorted(edges, key=lambda edge: edge.id))
            for node_id, edges in outgoing.items()
        }

        grid: dict[tuple[int, int, int], list[Node]] = defaultdict(list)
        for node in snapshot.graph.nodes:
            grid[_grid_cell(node.longitude, node.latitude)].append(node)
        self._grid = {cell: tuple(nodes) for cell, nodes in grid.items()}

    def snap(self, position: Coordinate) -> Snap | None:
        """Snap an in-bounds point, with any connector directed from the point to its node."""
        if not in_bounds(*position, self.snapshot.manifest.bounds):
            return None
        x, y, z = _grid_cell(*position)
        best: tuple[float, int] | None = None
        for dx, dy, dz in NEIGHBOR_CELLS:
            for node in self._grid.get((x + dx, y + dy, z + dz), ()):
                distance = distance_mm(*position, node.longitude, node.latitude)
                key = (distance, node.id)
                if distance <= SNAP_LIMIT_MM and (best is None or key < best):
                    best = key
        if best is None:
            return None

        distance, node_id = best
        node = self._nodes[node_id]
        snapped = (node.longitude, node.latitude)
        connector = Geometry("LineString", (position, snapped)) if position != snapped else None
        return Snap(node_id, snapped, math.ceil(distance), connector)

    def route(
        self, origin: Coordinate, destination: Coordinate, *, budget: SearchBudget
    ) -> RouteResult:
        bounds = self.snapshot.manifest.bounds
        if not in_bounds(*origin, bounds) or not in_bounds(*destination, bounds):
            return RouteResult(reason="outside_coverage")
        start, goal = self.snap(origin), self.snap(destination)
        if start is None or goal is None:
            return RouteResult(reason="snap_too_far", origin_snap=start, destination_snap=goal)
        if start.node_id == goal.node_id:
            return RouteResult(
                distance_mm=0,
                geometry=Geometry("Point", start.coordinates),
                origin_snap=start,
                destination_snap=goal,
            )
        reason, cost, geometry = self._search(start.node_id, goal.node_id, budget)
        return RouteResult(reason, cost, geometry, start, goal)

    def _search(
        self, start: int, goal: int, budget: SearchBudget
    ) -> tuple[RouteReason | None, int | None, Geometry | None]:
        target = self._nodes[goal]
        heuristics: dict[int, int] = {}

        def estimate(node_id: int) -> int:
            if node_id not in heuristics:
                node = self._nodes[node_id]
                # Spherical distance obeys the triangle inequality. Rounding the
                # heuristic down and edge costs up preserves consistency.
                heuristics[node_id] = math.floor(
                    distance_mm(node.longitude, node.latitude, target.longitude, target.latitude)
                )
            return heuristics[node_id]

        initial = (start, 0)  # Edge IDs are positive in every admitted snapshot.
        best: dict[State, int] = {initial: 0}
        previous: dict[State, State] = {}
        queue = [(estimate(start), start, 0, 0)]
        while queue:
            _, node_id, incoming, cost = heapq.heappop(queue)
            current = (node_id, incoming)
            if best[current] != cost:
                continue
            if not budget._settle():
                return "budget_exceeded", None, None
            if node_id == goal:
                geometry = self._geometry(current, previous)
                if geometry is None:
                    return "geometry_limit", None, None
                return None, cost, geometry
            for edge in self._outgoing.get(node_id, ()):
                if (incoming, edge.id) in self._prohibited:
                    continue
                successor = (edge.target, edge.id)
                next_cost = cost + edge.weight_mm
                known_cost = best.get(successor)
                if known_cost is not None and next_cost >= known_cost:
                    continue
                best[successor] = next_cost
                previous[successor] = current
                # Fixed ties by destination node and incoming edge IDs.
                heapq.heappush(
                    queue, (next_cost + estimate(edge.target), edge.target, edge.id, next_cost)
                )
        return "no_route", None, None

    def _geometry(self, current: State, previous: dict[State, State]) -> Geometry | None:
        points = []
        state: State | None = current
        while state is not None:
            if len(points) == MAX_COORDINATES:
                return None
            node = self._nodes[state[0]]
            points.append((node.longitude, node.latitude))
            state = previous.get(state)
        points.reverse()
        return Geometry("LineString", tuple(points))


def route(
    snapshot: Snapshot | RoutingIndex,
    origin: Coordinate,
    destination: Coordinate,
    *,
    budget: SearchBudget,
) -> RouteResult:
    index = snapshot if isinstance(snapshot, RoutingIndex) else RoutingIndex(snapshot)
    return index.route(origin, destination, budget=budget)
