from datetime import UTC, datetime, timedelta

import pytest

from tests.gis_helpers import GRAPH, write_fixture

NOW = datetime(2026, 11, 7, tzinfo=UTC)


def test_only_explicit_fixture_admission_returns_immutable_graph(tmp_path):
    from app.gis.catalog import SnapshotError, verify_snapshot

    snapshot_id, _ = write_fixture(tmp_path)
    with pytest.raises(SnapshotError, match="fixture"):
        verify_snapshot(tmp_path, snapshot_id, NOW)

    snapshot = verify_snapshot(tmp_path, snapshot_id, NOW, allow_fixture=True)
    assert snapshot.snapshot_id == snapshot_id
    assert snapshot.manifest.dataset_class == "synthetic_fixture"
    assert [edge.weight_mm for edge in snapshot.graph.edges] == [111196, 111196]
    assert snapshot.graph.restrictions == ((1, 2),)
    with pytest.raises(AttributeError):
        snapshot.graph.edges[0].target = 3


@pytest.mark.parametrize(
    ("changes", "at", "reason"),
    [
        ({"crs": "EPSG:3857"}, NOW, "invalid"),
        ({"weight_unit": "km"}, NOW, "invalid"),
        ({"schema_version": "warehouse-road-graph/2"}, NOW, "invalid"),
        ({"private": "unexpected"}, NOW, "invalid"),
        ({"prepared_at": "2026-11-04T00:00:00Z"}, NOW, "invalid"),
        ({}, NOW - timedelta(days=3), "invalid"),
        ({}, NOW + timedelta(days=31), "stale"),
        ({"source_url": "https://download.geofabrik.de/asia/vietnam-261105.osm.pbf"}, NOW,
         "invalid"),
    ],
)
def test_invalid_metadata_and_stale_snapshot_have_distinct_codes(tmp_path, changes, at, reason):
    from app.gis.catalog import SnapshotError, verify_snapshot

    snapshot_id, _ = write_fixture(tmp_path, changes=changes)
    with pytest.raises(SnapshotError) as failure:
        verify_snapshot(tmp_path, snapshot_id, at, allow_fixture=True)
    assert failure.value.code == reason


@pytest.mark.parametrize(
    "graph",
    [
        {**GRAPH, "nodes": [[1, 0, 0], [1, 0.001, 0], [3, 0.002, 0]]},
        {**GRAPH, "nodes": [[1, 0, 0], [2, 0.001, 0], [3, 1.002, 0]]},
        {**GRAPH, "edges": [[1, 10, 1, 2, 111196], [1, 10, 2, 3, 111196]]},
        {**GRAPH, "edges": [[1, 10, 1, 4, 111196], [2, 10, 2, 3, 111196]]},
        {**GRAPH, "edges": [[1, 10, 1, 2, 111195], [2, 10, 2, 3, 111196]]},
        {**GRAPH, "edges": [[True, 10, 1, 2, 111196], [2, 10, 2, 3, 111196]]},
        {**GRAPH, "restrictions": [[1, 1]]},
        {**GRAPH, "restrictions": [[2, 99]]},
    ],
)
def test_catalog_checks_graph_content_even_when_its_hash_matches(tmp_path, graph):
    from app.gis.catalog import SnapshotError, verify_snapshot

    snapshot_id, _ = write_fixture(tmp_path, graph=graph)
    with pytest.raises(SnapshotError):
        verify_snapshot(tmp_path, snapshot_id, NOW, allow_fixture=True)


@pytest.mark.parametrize("filename", ["manifest.json", "graph.json"])
def test_catalog_rejects_modified_bytes(tmp_path, filename):
    from app.gis.catalog import SnapshotError, verify_snapshot

    snapshot_id, folder = write_fixture(tmp_path)
    artifact = folder / filename
    artifact.write_bytes(artifact.read_bytes() + b" ")
    with pytest.raises(SnapshotError):
        verify_snapshot(tmp_path, snapshot_id, NOW, allow_fixture=True)


def test_catalog_rejects_oversize_before_reading(tmp_path):
    from app.gis.catalog import SnapshotError, verify_snapshot

    snapshot_id, folder = write_fixture(tmp_path)
    with (folder / "graph.json").open("r+b") as file:
        file.truncate(96 * 1024 * 1024 + 1)
    with pytest.raises(SnapshotError, match="limit"):
        verify_snapshot(tmp_path, snapshot_id, NOW, allow_fixture=True)


@pytest.mark.parametrize("symlink_at", ["root", "snapshot", "manifest.json", "graph.json"])
def test_catalog_rejects_symlinks(tmp_path, symlink_at):
    from app.gis.catalog import SnapshotError, verify_snapshot

    root = tmp_path / "root"
    snapshot_id, folder = write_fixture(root)
    path = root if symlink_at == "root" else folder
    if symlink_at.endswith(".json"):
        path = folder / symlink_at
    target = tmp_path / "target"
    path.rename(target)
    path.symlink_to(target, target_is_directory=target.is_dir())
    with pytest.raises(SnapshotError):
        verify_snapshot(root, snapshot_id, NOW, allow_fixture=True)


def test_catalog_rejects_traversal_ids_and_relative_roots(tmp_path, monkeypatch):
    from app.gis.catalog import SnapshotError, verify_snapshot

    root = tmp_path / "root"
    snapshot_id, _ = write_fixture(root)
    monkeypatch.chdir(tmp_path)
    for requested_root, requested_id in ((root, "../root/" + snapshot_id), ("root", snapshot_id)):
        with pytest.raises(SnapshotError):
            verify_snapshot(requested_root, requested_id, NOW, allow_fixture=True)
