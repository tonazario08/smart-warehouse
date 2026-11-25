import hashlib
import json
from pathlib import Path

GRAPH = {
    "nodes": [[1, 0, 0], [2, 0.001, 0], [3, 0.002, 0]],
    "edges": [[1, 10, 1, 2, 111196], [2, 10, 2, 3, 111196]],
    "restrictions": [[1, 2]],
}
MANIFEST = {
    "schema_version": "warehouse-road-graph/1",
    "dataset_class": "synthetic_fixture",
    "snapshot_at": "2026-11-05T21:23:02Z",
    "prepared_at": "2026-11-06T00:00:00Z",
    "source_url": None,
    "source_sha256": None,
    "bounds": [-1, -1, 1, 1],
    "crs": "EPSG:4326",
    "weight_unit": "mm",
    "converter_version": "warehouse-osm/1",
    "profile_version": "car-reference/1",
    "license": "synthetic_fixture",
    "attribution": "Synthetic fixture",
    "stats": {
        "nodes": 3,
        "edges": 2,
        "restrictions": 1,
        "excluded_access_ways": 0,
        "excluded_barrier_nodes": 0,
        "excluded_restrictions": 0,
        "excluded_restriction_ways": 0,
    },
}


def write_fixture(
    root: Path, *, changes: dict | None = None, graph: dict | None = None
) -> tuple[str, Path]:
    graph = GRAPH if graph is None else graph
    sections = []
    for name in ("nodes", "edges", "restrictions"):
        rows = ",\n".join(json.dumps(row, separators=(",", ":")) for row in graph[name])
        sections.append(f'"{name}":[\n' + (rows + "\n" if rows else "") + "]")
    graph_bytes = ("{" + ",".join(sections) + "}\n").encode()
    manifest = {
        **MANIFEST,
        "graph_sha256": hashlib.sha256(graph_bytes).hexdigest(),
        **(changes or {}),
    }
    manifest_bytes = json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    snapshot_id = "gsv1-" + hashlib.sha256(manifest_bytes).hexdigest()
    folder = root / snapshot_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "graph.json").write_bytes(graph_bytes)
    (folder / "manifest.json").write_bytes(manifest_bytes)
    return snapshot_id, folder
