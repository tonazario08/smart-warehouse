"""Display selection must never add roads or influence A*."""

from types import SimpleNamespace

from app.gis.schemas import Edge, Graph, Node, Snapshot, edge_weight
from app.gis.street_layer import GRID_SIZE, MAX_SEGMENTS, sample_streets


def test_street_projection_is_bounded_stable_and_uses_real_edges_only():
    nodes = []
    edges = []
    expected_per_cell = 10
    for i in range(GRID_SIZE):
        for j in range(GRID_SIZE):
            for k in range(expected_per_cell):
                a = Node(len(nodes), i + 0.1, j + 0.1 + 0.01 * k)
                b = Node(a.id + 1, i + 0.1 + 0.01 * k, a.latitude + 0.01)
                nodes.extend([a, b])
                weight = edge_weight(a, b)
                edges.extend([
                    Edge(len(edges), k, a.id, b.id, weight),
                    Edge(len(edges) + 1, k, b.id, a.id, weight),
                ])
    manifest = SimpleNamespace(dataset_class="public_osm", bounds=(0, 0, GRID_SIZE, GRID_SIZE))
    graph = Graph(tuple(nodes), tuple(edges), ())
    reversed_graph = Graph(graph.nodes[::-1], graph.edges[::-1], ())
    before = sample_streets(Snapshot("test-only", manifest, graph))
    assert before == sample_streets(Snapshot("test-only", manifest, reversed_graph))
    assert len(before) == len(set(before)) == MAX_SEGMENTS
    actual = {
        tuple(sorted((tuple(nodes[e.source][1:]), tuple(nodes[e.target][1:])))) for e in edges
    }
    assert set(before).issubset(actual)
    manifest.dataset_class = "synthetic_fixture"
    assert sample_streets(Snapshot("test-only", manifest, graph)) == ()
