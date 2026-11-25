"""Bounded callback conversion for the reference passenger-car OSM profile."""

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.gis.catalog import SnapshotError
from app.gis.schemas import (
    CANDIDATE_NODE_LIMIT,
    EDGE_LIMIT,
    NODE_LIMIT,
    PUBLIC_BOUNDS,
    RESTRICTION_LIMIT,
    Edge,
    Graph,
    GraphStats,
    Node,
    edge_weight,
    in_bounds,
)

HIGHWAYS = frozenset({
    "motorway", "trunk", "primary", "secondary", "tertiary",
    "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link",
    "unclassified", "residential", "living_street", "service",
})
ACCESS = ("motorcar", "motor_vehicle", "vehicle", "access")
PUBLIC_ACCESS = frozenset({"yes", "designated", "permissive"})
DIRECTIONS = {"yes": (True, False), "no": (True, True), "-1": (False, True)}
ONEWAY = ("oneway:motorcar", "oneway:motor_vehicle", "oneway:vehicle", "oneway")
RESTRICTION = ("restriction:motorcar", "restriction:motor_vehicle", "restriction:vehicle",
               "restriction")
OTHER_RESTRICTION_MODES = frozenset({
    "agricultural", "bicycle", "bus", "emergency", "foot", "goods", "hgv", "horse", "mofa",
    "moped", "motorcycle", "psv", "taxi", "tourist_bus",
})
LEGACY_RESTRICTION_TIME = ("day_on", "day_off", "hour_on", "hour_off")
TURNS = frozenset({
    "no_left_turn", "no_right_turn", "no_straight_on", "no_u_turn", "no_entry", "no_exit",
    "only_left_turn", "only_right_turn", "only_straight_on", "only_u_turn",
})
TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


@dataclass(frozen=True, slots=True)
class ImportedGraph:
    snapshot_at: datetime
    graph: Graph
    stats: GraphStats


def _first(tags, keys):
    for key in keys:
        value = tags.get(key)
        if value is not None:
            return value
    return None


def _public_access(tags) -> bool:
    access = _first(tags, ACCESS)
    uncertain = any(
        tags.get(f"{key}:{suffix}") is not None
        for key in ACCESS
        for suffix in ("conditional", "forward", "backward", "forward:conditional",
                       "backward:conditional")
    )
    return not uncertain and (access is None or access in PUBLIC_ACCESS)


def _directions(tags) -> tuple[bool, bool] | None:
    conditional = any(tags.get(f"{key}:conditional") is not None for key in ONEWAY)
    if not _public_access(tags) or conditional:
        return None
    explicit = _first(tags, ONEWAY)
    if explicit is not None:
        return DIRECTIONS.get(explicit)
    junction = tags.get("junction")
    if junction == "circular":
        return None
    if tags.get("highway") == "motorway" or junction == "roundabout":
        return DIRECTIONS["yes"]
    return DIRECTIONS["no"]


class _GraphBuilder:
    def __init__(self) -> None:
        self.nodes: dict[int, Node] = {}
        self.barriers: set[int] = set()
        self.ways: dict[int, list[Edge]] = {}
        self.outgoing: dict[int, list[Edge]] = defaultdict(list)
        self.restrictions: set[tuple[int, int]] = set()
        self.blocked_ways: set[int] = set()
        self.edge_count = 0
        self.excluded_access_ways = 0
        self.excluded_restrictions = 0
        self.phase = 0

    def add_node(self, entity) -> None:
        if self.phase:
            raise SnapshotError("PBF entities are not in node, way, relation order")
        location = entity.location
        if not location.valid():
            return
        longitude, latitude = location.lon, location.lat
        if not in_bounds(longitude, latitude, PUBLIC_BOUNDS):
            return
        node_id = entity.id
        if node_id <= 0 or node_id in self.nodes:
            raise SnapshotError("invalid or duplicate PBF node")
        if len(self.nodes) >= CANDIDATE_NODE_LIMIT:
            raise SnapshotError("PBF candidate node limit exceeded")
        self.nodes[node_id] = Node(node_id, longitude, latitude)
        if entity.tags.get("barrier") not in (None, "no") or not _public_access(entity.tags):
            self.barriers.add(node_id)

    def add_way(self, entity) -> None:
        if self.phase > 1:
            raise SnapshotError("PBF entities are not in node, way, relation order")
        self.phase = 1
        if entity.tags.get("highway") not in HIGHWAYS:
            return
        directions = _directions(entity.tags)
        previous = None
        edges = []
        way_id = entity.id
        for reference in entity.nodes:
            current = self.nodes.get(reference.ref) if reference.ref not in self.barriers else None
            if previous is not None and current is not None and previous.id != current.id:
                if directions is None:
                    self.excluded_access_ways += 1
                    return
                weight = edge_weight(previous, current)
                if weight:
                    forward, reverse = directions
                    if forward:
                        edges.append(self._add_edge(way_id, previous.id, current.id, weight))
                    if reverse:
                        edges.append(self._add_edge(way_id, current.id, previous.id, weight))
            previous = current
        if edges:
            if way_id <= 0 or way_id in self.ways:
                raise SnapshotError("invalid or duplicate PBF way")
            self.ways[way_id] = edges

    def _add_edge(self, way: int, source: int, target: int, weight: int) -> Edge:
        self.edge_count += 1
        if self.edge_count > EDGE_LIMIT:
            raise SnapshotError("PBF candidate edge limit exceeded")
        edge = Edge(self.edge_count, way, source, target, weight)
        self.outgoing[source].append(edge)
        return edge

    def add_relation(self, entity) -> None:
        self.phase = 2
        tags = entity.tags
        kind = tags.get("type", "")
        if kind != "restriction" and not kind.startswith("restriction:"):
            return
        mode = kind.split(":")[1:2]
        if mode and mode[0] in OTHER_RESTRICTION_MODES:
            return
        relevant_keys = {
            tag.k for tag in tags
            if tag.k.startswith("restriction:")
            and tag.k.split(":")[1] not in OTHER_RESTRICTION_MODES
        }
        specific = bool(mode or any(key != "restriction:conditional" for key in relevant_keys))
        exceptions = {part.strip() for part in tags.get("except", "").split(";")}
        if not specific and exceptions.intersection(ACCESS[:-1]):
            return
        unsupported = (
            bool(mode and kind not in RESTRICTION)
            or bool(relevant_keys - set(RESTRICTION))
            or any(tags.get(key) is not None for key in LEGACY_RESTRICTION_TIME)
        )
        turn = _first(tags, RESTRICTION)
        if not (turn is not None or specific or unsupported):
            if any(tag.k.startswith("restriction:") for tag in tags):
                return  # All specified restrictions are for unrelated transport modes.
        members = entity.members
        local_ways = set()
        local_node = False
        has_way = False
        has_nested = False
        from_way = via = to_way = None
        for member in members:
            if member.type == "w":
                has_way = True
                if member.ref in self.ways:
                    local_ways.add(member.ref)
                if member.role == "from":
                    from_way = member.ref
                if member.role == "to":
                    to_way = member.ref
            if member.type == "n":
                local_node |= member.ref in self.nodes
                if member.role == "via":
                    via = member.ref
            has_nested |= member.type == "r"
        if has_nested or not has_way:
            if local_ways or local_node or not members or has_nested:
                raise SnapshotError("cannot locate all ways affected by an OSM restriction")
            return
        if not local_ways:
            if local_node and (from_way is None or to_way is None):
                raise SnapshotError("cannot locate all ways affected by an OSM restriction")
            return
        if (
            unsupported
            or turn not in TURNS
            or len(members) != 3
            or from_way is None
            or to_way is None
            or via is None
            or not self._apply_turn(turn, from_way, via, to_way)
        ):
            self.excluded_restrictions += 1
            self.blocked_ways.update(local_ways)

    def _apply_turn(self, turn: str, from_way: int, via: int, to_way: int) -> bool:
        if via not in self.nodes or via in self.barriers:
            return True  # No local transition can use this via node.
        incoming = [edge for edge in self.ways.get(from_way, ()) if edge.target == via]
        if not incoming:
            return True
        outgoing = [edge for edge in self.ways.get(to_way, ()) if edge.source == via]
        if from_way == to_way and turn.endswith("_u_turn"):
            for edge in incoming:
                returning = [candidate for candidate in outgoing if candidate.target == edge.source]
                if len(returning) != 1:
                    return False
                self._record_turn(turn, edge, returning[0])
            return True
        if from_way == to_way or len(incoming) != 1 or len(outgoing) != 1:
            return False
        self._record_turn(turn, incoming[0], outgoing[0])
        return True

    def _record_turn(self, turn: str, incoming: Edge, allowed_or_forbidden: Edge) -> None:
        if turn.startswith("only_"):
            prohibited = (
                edge for edge in self.outgoing[incoming.target] if edge != allowed_or_forbidden
            )
        else:
            prohibited = (allowed_or_forbidden,)
        for edge in prohibited:
            self.restrictions.add((incoming.id, edge.id))
            if len(self.restrictions) > RESTRICTION_LIMIT:
                raise SnapshotError("PBF edge transition limit exceeded")

    def finish(self, timestamp: datetime) -> ImportedGraph:
        retained_nodes: set[int] = set()
        id_map = {}
        edges = []
        for way in sorted(self.ways.keys() - self.blocked_ways):
            for edge in self.ways[way]:
                edge_id = len(edges) + 1
                id_map[edge.id] = edge_id
                edges.append(Edge(edge_id, edge.way_id, edge.source, edge.target, edge.weight_mm))
                retained_nodes.update((edge.source, edge.target))
                if len(retained_nodes) > NODE_LIMIT:
                    raise SnapshotError("PBF graph node limit exceeded")
        if not edges:
            raise SnapshotError("no admitted road segments in PBF coverage")
        restrictions = sorted(
            (id_map[incoming], id_map[outgoing])
            for incoming, outgoing in self.restrictions
            if incoming in id_map and outgoing in id_map
        )
        graph = Graph(
            tuple(self.nodes[node] for node in sorted(retained_nodes)),
            tuple(edges),
            tuple(restrictions),
        )
        return ImportedGraph(
            snapshot_at=timestamp,
            graph=graph,
            stats=GraphStats(
                nodes=len(graph.nodes),
                edges=len(graph.edges),
                restrictions=len(graph.restrictions),
                excluded_access_ways=self.excluded_access_ways,
                excluded_barrier_nodes=len(self.barriers),
                excluded_restrictions=self.excluded_restrictions,
                excluded_restriction_ways=len(self.blocked_ways),
            ),
        )


def import_osm(path: Path, *, check_header=None) -> ImportedGraph:
    try:
        import osmium
    except ImportError:
        raise SnapshotError("install the GIS extra to prepare an OSM PBF") from None

    builder = _GraphBuilder()

    class Handler(osmium.SimpleHandler):
        node = staticmethod(builder.add_node)
        way = staticmethod(builder.add_way)
        relation = staticmethod(builder.add_relation)

    try:
        pool = osmium.io.ThreadPool(2, 4)
        file = osmium.io.File(str(path), "pbf")
        with osmium.io.Reader(file, thread_pool=pool) as reader:
            raw = reader.header().get("osmosis_replication_timestamp")
            if not TIMESTAMP.fullmatch(raw):
                raise SnapshotError("invalid PBF replication timestamp")
            timestamp = datetime.fromisoformat(raw).astimezone(UTC)
            if check_header is not None:
                check_header(timestamp)
            osmium.apply(reader, Handler())
    except SnapshotError:
        raise
    except (OSError, RuntimeError, TypeError, ValueError):
        raise SnapshotError("invalid or unavailable OSM PBF") from None
    return builder.finish(timestamp)
