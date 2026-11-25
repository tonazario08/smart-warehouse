import hashlib
import io
import json
from datetime import UTC, datetime, timedelta

import pytest

STAMP = "2026-11-05T21:23:02Z"
NOW = datetime(2026, 11, 7, tzinfo=UTC)
SOURCE = "https://download.geofabrik.de/asia/vietnam-261105.osm.pbf"


def write_pbf(path, nodes, ways, relations=(), *, timestamp=STAMP):
    import osmium

    header = osmium.io.Header()
    if timestamp is not None:
        header.set("osmosis_replication_timestamp", timestamp)
    with osmium.SimpleWriter(path, header=header) as writer:
        for node_id, longitude, latitude, tags in nodes:
            writer.add_node(osmium.osm.mutable.Node(
                id=node_id, location=(longitude, latitude), tags=tags
            ))
        for way_id, node_ids, tags in ways:
            writer.add_way(osmium.osm.mutable.Way(id=way_id, nodes=node_ids, tags=tags))
        for relation_id, members, tags in relations:
            writer.add_relation(osmium.osm.mutable.Relation(
                id=relation_id, members=members, tags=tags
            ))
    return path


def node(node_id, longitude, latitude=10.75, **tags):
    return node_id, longitude, latitude, tags


def way(way_id, *node_ids, **tags):
    return way_id, node_ids, {"highway": "residential", **tags}


def directions(graph):
    return {(edge.way_id, edge.source, edge.target) for edge in graph.edges}


def test_parser_clips_without_bridging_and_preserves_osm_node_identity(tmp_path):
    from app.gis.osm_import import import_osm

    nodes = [
        node(1, 106.65), node(2, 106.66), node(3, 106.8), node(4, 106.67),
        node(5, 106.66), node(6, 106.68),
    ]
    source = write_pbf(
        tmp_path / "fixture.osm.pbf", nodes,
        [way(10, 1, 2, 3, 4, oneway="yes"), way(20, 5, 6, oneway="-1")],
    )
    imported = import_osm(source)
    assert imported.snapshot_at == datetime(2026, 11, 5, 21, 23, 2, tzinfo=UTC)
    assert directions(imported.graph) == {(10, 1, 2), (20, 6, 5)}
    assert imported.graph.nodes[1].id == 2
    assert imported.graph.nodes[2].id == 5
    assert imported.graph.nodes[1].longitude == imported.graph.nodes[2].longitude


def test_parser_limits_directions_access_and_connections_at_barriers(tmp_path):
    from app.gis.osm_import import import_osm

    nodes = [
        node(1, 106.65), node(2, 106.66), node(3, 106.67, barrier="bollard"),
        node(4, 106.68), node(5, 106.69),
    ]
    ways = [
        way(10, 1, 2, highway="motorway"),
        way(11, 1, 2, highway="motorway", oneway="no"),
        way(12, 1, 2, junction="roundabout"),
        way(13, 1, 2, access="private", motorcar="yes"),
        way(14, 1, 2, motor_vehicle="destination"),
        way(15, 1, 2, **{"oneway:conditional": "no @ (Mo-Fr)"}),
        way(16, 2, 3, 4, 5),
        way(17, 1, 2, oneway="reversible"),
        way(18, 1, 2, **{"motorcar:conditional": "no @ (Mo-Fr)"}),
        way(19, 1, 2, access="delivery"),
    ]
    imported = import_osm(write_pbf(tmp_path / "fixture.osm.pbf", nodes, ways))
    assert directions(imported.graph) == {
        (10, 1, 2), (11, 1, 2), (11, 2, 1), (12, 1, 2), (13, 1, 2), (13, 2, 1),
        (16, 4, 5), (16, 5, 4),
    }
    assert imported.stats.excluded_access_ways == 5
    assert imported.stats.excluded_barrier_nodes == 1


@pytest.mark.parametrize("restriction", ["no_right_turn", "only_right_turn"])
def test_simple_turn_restriction_has_incoming_edge_and_direction(tmp_path, restriction):
    from app.gis.osm_import import import_osm

    nodes = [node(1, 106.65), node(2, 106.66), node(3, 106.67), node(4, 106.68)]
    ways = [way(10, 1, 2), way(11, 2, 3), way(12, 2, 4)]
    relations = [(
        1, [("w", 10, "from"), ("n", 2, "via"), ("w", 11, "to")],
        {"type": "restriction", "restriction": restriction},
    )]
    graph = import_osm(write_pbf(tmp_path / "fixture.osm.pbf", nodes, ways, relations)).graph
    edges = {edge.id: (edge.way_id, edge.source, edge.target) for edge in graph.edges}
    actual = {(edges[incoming], edges[outgoing]) for incoming, outgoing in graph.restrictions}
    if restriction == "no_right_turn":
        assert actual == {((10, 1, 2), (11, 2, 3))}
    else:
        assert actual == {((10, 1, 2), (10, 2, 1)), ((10, 1, 2), (12, 2, 4))}


@pytest.mark.parametrize(
    ("via", "extra"),
    [
        ([("w", 11, "via")], {}),
        ([("n", 2, "via"), ("n", 3, "via")], {}),
        ([("n", 2, "via")], {"restriction:conditional": "no_right_turn @ (Mo-Fr)"}),
        ([("n", 2, "via")], {"restriction:motorcar": "unrecognized"}),
    ],
)
def test_unsupported_restrictions_remove_their_affected_ways(tmp_path, via, extra):
    from app.gis.osm_import import import_osm

    nodes = [node(1, 106.65), node(2, 106.66), node(3, 106.67), node(4, 106.68)]
    ways = [way(10, 1, 2), way(11, 2, 3), way(12, 3, 4), way(13, 1, 4)]
    relations = [(
        1, [("w", 10, "from"), *via, ("w", 12, "to")],
        {"type": "restriction", "restriction": "no_right_turn", **extra},
    )]
    imported = import_osm(write_pbf(tmp_path / "fixture.osm.pbf", nodes, ways, relations))
    assert {edge.way_id for edge in imported.graph.edges} == (
        {13} if via == [("w", 11, "via")] else {11, 13}
    )
    assert imported.stats.excluded_restrictions == 1


def test_unlocatable_local_restriction_rejects_the_source(tmp_path):
    from app.gis.catalog import SnapshotError
    from app.gis.osm_import import import_osm

    nodes = [node(1, 106.65), node(2, 106.66)]
    relations = [(1, [("n", 1, "via")], {"type": "restriction", "restriction": "no_right_turn"})]
    with pytest.raises(SnapshotError, match="restriction"):
        import_osm(write_pbf(tmp_path / "fixture.osm.pbf", nodes, [way(10, 1, 2)], relations))


def test_cli_prepare_checks_hash_and_publishes_repeatable_verified_graph(tmp_path, capsys):
    from app.gis.catalog import verify_snapshot
    from app.gis.cli import main

    src = write_pbf(
        tmp_path / "fixture.osm.pbf", [node(1, 106.65), node(2, 106.66)], [way(10, 1, 2)]
    )
    root = tmp_path / "catalog"
    args = [
        "prepare", "--input", str(src), "--source-url", SOURCE, "--output-root", str(root),
        "--source-sha256",
    ]
    assert main([*args, "0" * 64], now=NOW) != 0
    assert not root.exists()
    capsys.readouterr()
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    assert main([*args, digest], now=NOW) == 0
    first_id = json.loads(capsys.readouterr().out)["snapshot_id"]
    assert main([*args, digest], now=NOW + timedelta(seconds=5)) == 0
    assert json.loads(capsys.readouterr().out)["snapshot_id"] == first_id
    snapshot = verify_snapshot(root, first_id, NOW)
    assert snapshot.manifest.source_sha256 == digest
    assert snapshot.manifest.attribution == "© OpenStreetMap contributors"
    assert main(["verify", "--catalog-root", str(root), "--snapshot-id", first_id], now=NOW) == 0
    assert json.loads(capsys.readouterr().out)["snapshot_id"] == first_id


@pytest.mark.parametrize(
    ("source_url", "timestamp"),
    [
        ("http://download.geofabrik.de/asia/vietnam-261105.osm.pbf", STAMP),
        (SOURCE + "?download=1", STAMP),
        (SOURCE.replace("261105", "latest"), STAMP),
        (SOURCE.replace("261105", "261104"), STAMP),
        (SOURCE.replace("download.", "secret@download."), STAMP),
        (SOURCE, None),
        (SOURCE.replace("261105", "261109"), "2026-11-09T21:23:02Z"),
    ],
)
def test_cli_rejects_untrusted_source_url_and_conflicting_replication_header(
    tmp_path, source_url, timestamp
):
    from app.gis.cli import main

    src = write_pbf(
        tmp_path / "fixture.osm.pbf", [node(1, 106.65), node(2, 106.66)], [way(10, 1, 2)],
        timestamp=timestamp,
    )
    root = tmp_path / "catalog"
    assert main([
        "prepare", "--input", str(src), "--source-url", source_url,
        "--source-sha256", hashlib.sha256(src.read_bytes()).hexdigest(),
        "--output-root", str(root),
    ], now=NOW) != 0
    assert not root.exists()



def test_source_replacement_cannot_change_the_bytes_used_by_prepare(tmp_path, monkeypatch):
    from app.gis import cli

    original = write_pbf(
        tmp_path / "fixture.osm.pbf", [node(1, 106.65), node(2, 106.66)], [way(10, 1, 2)]
    )
    replacement = write_pbf(
        tmp_path / "replacement.osm.pbf", [node(1, 106.65), node(2, 106.67)], [way(10, 1, 2)]
    )
    original_bytes = original.read_bytes()
    real_import = cli.import_osm

    def swap_source(path, **kwargs):
        original.write_bytes(replacement.read_bytes())
        try:
            return real_import(path, **kwargs)
        finally:
            original.write_bytes(original_bytes)

    monkeypatch.setattr(cli, "import_osm", swap_source)
    snapshot = cli.prepare_snapshot(
        original, SOURCE, hashlib.sha256(original_bytes).hexdigest(), tmp_path / "catalog", NOW
    )
    assert snapshot.graph.nodes[1].longitude == 106.66


def test_malformed_car_profile_restriction_is_not_ignored_as_other_transport(tmp_path):
    from app.gis.osm_import import import_osm

    nodes = [node(1, 106.65), node(2, 106.66), node(3, 106.67), node(4, 106.68)]
    ways = [way(10, 1, 2), way(11, 2, 3), way(12, 3, 4)]
    relations = [(
        1, [("w", 10, "from"), ("n", 2, "via"), ("w", 11, "to")],
        {"type": "restriction", "restriction:motorcar:unrecognized": "no_right_turn"},
    )]
    imported = import_osm(write_pbf(tmp_path / "fixture.osm.pbf", nodes, ways, relations))
    assert {edge.way_id for edge in imported.graph.edges} == {12}


def test_zero_distance_segments_do_not_join_distinct_osm_nodes(tmp_path):
    from app.gis.osm_import import import_osm

    nodes = [node(1, 106.65), node(2, 106.66), node(3, 106.66), node(4, 106.67)]
    ways = [way(10, 1, 2, 3, 4)]
    graph = import_osm(write_pbf(tmp_path / "fixture.osm.pbf", nodes, ways)).graph
    assert directions(graph) == {(10, 1, 2), (10, 2, 1), (10, 3, 4), (10, 4, 3)}


def test_way_callback_order_does_not_change_graph_bytes(tmp_path):
    from app.gis.catalog import write_graph
    from app.gis.osm_import import import_osm

    nodes = [node(1, 106.65), node(2, 106.66), node(3, 106.67)]
    ways = [way(10, 1, 2), way(20, 2, 3)]
    paths = [
        write_pbf(tmp_path / "one.osm.pbf", nodes, ways),
        write_pbf(tmp_path / "two.osm.pbf", nodes[::-1], ways[::-1]),
    ]
    encoded = []
    for path in paths:
        output = io.BytesIO()
        encoded.append((write_graph(output, import_osm(path).graph), output.getvalue()))
    assert encoded[0] == encoded[1]


def test_circular_junction_requires_explicit_direction(tmp_path):
    from app.gis.osm_import import import_osm

    nodes = [node(1, 106.65), node(2, 106.66)]
    ways = [
        way(10, 1, 2, junction="circular"),
        way(11, 1, 2, junction="circular", oneway="no"),
    ]
    graph = import_osm(write_pbf(tmp_path / "fixture.osm.pbf", nodes, ways)).graph
    assert directions(graph) == {(11, 1, 2), (11, 2, 1)}


def test_legacy_time_restriction_removes_affected_ways(tmp_path):
    from app.gis.osm_import import import_osm

    nodes = [node(1, 106.65), node(2, 106.66), node(3, 106.67), node(4, 106.68)]
    ways = [way(10, 1, 2), way(11, 2, 3), way(12, 3, 4)]
    relations = [(
        1, [("w", 10, "from"), ("n", 2, "via"), ("w", 11, "to")],
        {"type": "restriction", "restriction": "no_right_turn", "hour_on": "06:00"},
    )]
    imported = import_osm(write_pbf(tmp_path / "fixture.osm.pbf", nodes, ways, relations))
    assert {edge.way_id for edge in imported.graph.edges} == {12}


def test_invalid_staging_artifact_is_never_published(tmp_path, monkeypatch):
    from app.gis import cli
    from app.gis.catalog import SnapshotError

    original = write_pbf(
        tmp_path / "fixture.osm.pbf", [node(1, 106.65), node(2, 106.66)], [way(10, 1, 2)]
    )
    root = tmp_path / "catalog"

    def damaged_graph(stream, graph):
        stream.write(b"damaged")
        return hashlib.sha256(b"damaged").hexdigest()

    monkeypatch.setattr(cli, "write_graph", damaged_graph)
    with pytest.raises(SnapshotError):
        cli.prepare_snapshot(
            original, SOURCE, hashlib.sha256(original.read_bytes()).hexdigest(), root, NOW
        )
    assert not list(root.glob("gsv1-*"))
