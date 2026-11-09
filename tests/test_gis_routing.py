import heapq
import json
import random
from collections import defaultdict

import pytest

from app.gis.schemas import Edge, Graph, Manifest, Node, Snapshot, edge_weight
from tests.gis_helpers import MANIFEST


def make_snapshot(points, segments, restrictions=(), *, bounds=(-1, -1, 1, 1)):
    nodes = {node_id: Node(node_id, *point) for node_id, point in points.items()}
    edges = tuple(
        Edge(edge_id, edge_id, source, target, edge_weight(nodes[source], nodes[target]))
        for edge_id, source, target in segments
    )
    manifest = Manifest.model_validate_json(json.dumps({
        **MANIFEST,
        "graph_sha256": "0" * 64,
        "bounds": bounds,
        "stats": {
            **MANIFEST["stats"],
            "nodes": len(nodes),
            "edges": len(edges),
            "restrictions": len(restrictions),
        },
    }))
    return Snapshot("gsv1-" + "0" * 64, manifest, Graph(tuple(nodes.values()), edges, restrictions))


def dijkstra(graph, origin_id, destination_id):
    """Independent oracle using weights only, with no geometry or search index."""
    outgoing = defaultdict(list)
    for edge in graph.edges:
        outgoing[edge.source].append(edge)
    prohibited = set(graph.restrictions)
    visited = set()
    queue = [(0, origin_id, None)]
    while queue:
        cost, node_id, incoming_id = heapq.heappop(queue)
        state = (node_id, incoming_id)
        if state in visited:
            continue
        visited.add(state)
        if node_id == destination_id:
            return cost
        for edge in outgoing[node_id]:
            if (incoming_id, edge.id) not in prohibited:
                heapq.heappush(queue, (cost + edge.weight_mm, edge.target, edge.id))
    return None


def test_reverse_oneway_is_unreachable():
    from app.gis.routing import SearchBudget, route

    origin, destination = (0, 0), (0.001, 0)
    snapshot = make_snapshot({1: origin, 2: destination}, [(1, 1, 2)])
    forward = route(snapshot, origin, destination, budget=SearchBudget())
    reverse = route(snapshot, destination, origin, budget=SearchBudget())

    assert forward.reason is None
    assert forward.distance_mm == 111196
    assert forward.geometry.type == "LineString"
    assert forward.geometry.coordinates == (origin, destination)
    assert forward.origin_snap.connector is None
    assert reverse.reason == "no_route"
    assert reverse.geometry is None
    assert reverse.distance_mm is None


def test_turn_restriction_uses_incoming_edge():
    from app.gis.routing import SearchBudget, route

    a, b, c, d = (0, 0), (0.001, 0), (0.002, 0), (0.0007, 0.001)
    snapshot = make_snapshot(
        {1: a, 2: b, 3: c, 4: d},
        [(1, 1, 2), (2, 2, 3), (3, 1, 4), (4, 4, 2)],
        ((1, 2),),
    )
    result = route(snapshot, a, c, budget=SearchBudget())

    assert result.geometry.coordinates == (a, d, b, c)
    assert result.distance_mm == dijkstra(snapshot.graph, 1, 3)


def test_ties_repeat_with_shuffled_input():
    from app.gis.routing import RoutingIndex, SearchBudget

    a, b, c, d = (0, 0), (0.001, 0.001), (0.001, -0.001), (0.002, 0)
    points = {1: a, 2: b, 3: c, 4: d}
    segments = [(1, 1, 2), (2, 1, 3), (3, 2, 4), (4, 3, 4)]

    first = RoutingIndex(make_snapshot(points, segments)).route(a, d, budget=SearchBudget())
    other = RoutingIndex(make_snapshot(dict(reversed(points.items())), segments[::-1])).route(
        a, d, budget=SearchBudget()
    )

    assert first == other
    assert first.geometry.coordinates == (a, b, d)


def test_same_snapped_node_returns_point_and_separate_connectors():
    from app.gis.routing import SearchBudget, route

    node_position = (0, 0)
    a, b = (0.00005, 0), (0, 0.00005)
    snapshot = make_snapshot({1: node_position, 2: (0.003, 0)}, [(1, 1, 2)])
    budget = SearchBudget(0)
    result = route(snapshot, a, b, budget=budget)

    assert result.reason is None
    assert result.distance_mm == 0
    assert result.geometry.type == "Point"
    assert result.geometry.coordinates == node_position
    assert result.origin_snap.node_id == result.destination_snap.node_id == 1
    assert result.origin_snap.distance_mm == result.destination_snap.distance_mm == 5560
    assert result.origin_snap.connector.coordinates == (a, node_position)
    assert result.destination_snap.connector.coordinates == (b, node_position)
    assert budget.settled == 0


def test_snap_uses_node_id_for_equal_geographic_distances():
    from app.gis.routing import RoutingIndex

    points = {10: (0.0005, 0), 3: (-0.0005, 0)}
    index = RoutingIndex(make_snapshot(points, [(1, 10, 3)]))

    assert index.snap((0, 0)).node_id == 3


@pytest.mark.parametrize(("coordinate", "expected"), [
    ((0.00179864, 0), 1),
    ((0.00179865, 0), None),
])
def test_snap_checks_unrounded_200_m_limit(coordinate, expected):
    from app.gis.routing import RoutingIndex

    index = RoutingIndex(make_snapshot({1: (0, 0), 2: (-0.005, 0)}, [(1, 1, 2)]))

    snap = index.snap(coordinate)
    assert (None if snap is None else snap.node_id) == expected


def test_snap_across_antimeridian_uses_geographic_proximity():
    from app.gis.routing import RoutingIndex

    points = {1: (-179.9998, 0), 2: (-179.99, 0)}
    index = RoutingIndex(make_snapshot(
        points, [(1, 1, 2)], bounds=(-180, -90, 180, 90)
    ))

    assert index.snap((180, 0)).node_id == 1


def test_route_reasons_distinguish_coverage_snap_and_disconnected_graph():
    from app.gis.routing import RoutingIndex, SearchBudget

    points = {1: (0, 0), 2: (0.001, 0), 3: (0.02, 0), 4: (0.021, 0)}
    index = RoutingIndex(make_snapshot(points, [(1, 1, 2), (2, 3, 4)]))

    outside = index.route(points[1], (1.001, 0), budget=SearchBudget())
    far = index.route(points[1], (0.01, 0), budget=SearchBudget())
    disconnected = index.route(points[1], points[4], budget=SearchBudget())

    assert outside.reason == "outside_coverage"
    assert far.reason == "snap_too_far"
    assert far.origin_snap.node_id == 1
    assert far.destination_snap is None
    assert disconnected.reason == "no_route"
    assert disconnected.origin_snap.node_id == 1
    assert disconnected.destination_snap.node_id == 4


def test_shared_search_budget_counts_settled_states_including_goal():
    from app.gis.routing import RoutingIndex, SearchBudget

    a, b = (0, 0), (0.001, 0)
    index = RoutingIndex(make_snapshot({1: a, 2: b}, [(1, 1, 2)]))

    too_small = SearchBudget(1)
    assert index.route(a, b, budget=too_small).reason == "budget_exceeded"
    assert too_small.settled == 1 and too_small.remaining == 0

    exact = SearchBudget(2)
    assert index.route(a, b, budget=exact).distance_mm == 111196
    assert exact.settled == 2 and exact.remaining == 0
    assert index.route(a, b, budget=exact).reason == "budget_exceeded"
    assert exact.settled == 2

    exhausted_component = SearchBudget(1)
    assert index.route(b, a, budget=exhausted_component).reason == "no_route"
    assert exhausted_component.remaining == 0


@pytest.mark.parametrize("capacity", [-1, 250001, True])
def test_invalid_search_budget_cannot_bypass_request_cap(capacity):
    from app.gis.routing import SearchBudget

    with pytest.raises(ValueError):
        SearchBudget(capacity)


def test_route_geometry_cap_rejects_without_cutting_away_endpoint():
    from app.gis.routing import RoutingIndex, SearchBudget

    points = {i: (i / 1_000_000, 0) for i in range(1, 4002)}
    segments = [(i, i, i + 1) for i in range(1, 4001)]
    index = RoutingIndex(make_snapshot(points, segments))

    at_limit = index.route(points[1], points[4000], budget=SearchBudget())
    above_limit = index.route(points[1], points[4001], budget=SearchBudget())

    assert len(at_limit.geometry.coordinates) == 4000
    assert at_limit.geometry.coordinates[0] == points[1]
    assert at_limit.geometry.coordinates[-1] == points[4000]
    assert above_limit.reason == "geometry_limit"
    assert above_limit.geometry is None
    assert above_limit.distance_mm is None
    assert above_limit.destination_snap.node_id == 4001


def test_astar_costs_match_dijkstra_on_seeded_directed_graphs():
    from app.gis.routing import RoutingIndex, SearchBudget

    rng = random.Random(42)
    for _ in range(8):
        points = {i: (i * 0.003, rng.uniform(-0.01, 0.01)) for i in range(1, 10)}
        links = [
            (source, target)
            for source in points
            for target in points
            if source != target and rng.random() < 0.3
        ]
        segments = [(i, *link) for i, link in enumerate(links, 1)]
        restrictions = tuple(
            (incoming, outgoing)
            for incoming, _, via in segments
            for outgoing, source, _ in segments
            if via == source and rng.random() < 0.1
        )
        snapshot = make_snapshot(points, segments, restrictions)
        index = RoutingIndex(snapshot)

        for origin, destination in [(1, 9), (9, 1), (2, 3), (3, 2), (5, 4)]:
            actual = index.route(points[origin], points[destination], budget=SearchBudget())
            expected = dijkstra(snapshot.graph, origin, destination)
            assert actual.distance_mm == expected
            assert actual.reason == ("no_route" if expected is None else None)
