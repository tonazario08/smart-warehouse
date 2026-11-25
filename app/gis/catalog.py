"""Open, validate and publish bounded content-addressed road snapshots."""

import hashlib
import json
import os
import re
import stat
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from pydantic import ValidationError

from app.gis.schemas import (
    EDGE_LIMIT,
    GRAPH_LIMIT,
    MAX_AGE,
    NODE_LIMIT,
    RESTRICTION_LIMIT,
    Edge,
    Graph,
    Manifest,
    Node,
    Snapshot,
    edge_weight,
    in_bounds,
)

SNAPSHOT_ID = re.compile(r"gsv1-[0-9a-f]{64}")
MANIFEST_LIMIT = 16 * 1024
ROW_LIMIT = 256
GRAPH_SECTIONS = (
    (b'{"nodes":[\n', b'],"edges":[\n', NODE_LIMIT),
    (b'],"edges":[\n', b'],"restrictions":[\n', EDGE_LIMIT),
    (b'],"restrictions":[\n', b']}\n', RESTRICTION_LIMIT),
)


class SnapshotError(ValueError):
    def __init__(self, detail: str, *, code: str = "invalid") -> None:
        super().__init__(detail)
        self.code = code


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


def manifest_id(content: bytes) -> str:
    return "gsv1-" + hashlib.sha256(content).hexdigest()


def checked_path(path: Path, *, directory: bool, create: bool = False) -> Path:
    if (
        not path.is_absolute()
        or path == Path(path.anchor)
        or ".." in path.parts
        or str(path).startswith(("\\\\", "//"))
    ):
        raise SnapshotError("unsafe artifact path")
    try:
        for component in (*reversed(path.parents), path):
            try:
                metadata = component.lstat()
            except FileNotFoundError:
                if create:
                    continue
                raise
            expected = stat.S_ISDIR if directory or component != path else stat.S_ISREG
            if not expected(metadata.st_mode) or getattr(
                metadata, "st_file_attributes", 0
            ) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise SnapshotError("unsafe artifact path")
    except OSError:
        raise SnapshotError("artifact unavailable") from None
    return path


@contextmanager
def _open_artifact(path: Path):
    checked_path(path, directory=False)
    if os.open not in os.supports_dir_fd:
        with path.open("rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise SnapshotError("unsafe artifact path")
            yield stream
        return

    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    directory = os.open(path.anchor, directory_flags)
    try:
        for component in path.parts[1:-1]:
            child = os.open(component, directory_flags, dir_fd=directory)
            os.close(directory)
            directory = child
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        with os.fdopen(os.open(path.name, flags, dir_fd=directory), "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise SnapshotError("unsafe artifact path")
            yield stream
    finally:
        os.close(directory)


def check_age(snapshot_at: datetime, now: datetime) -> None:
    if now.utcoffset() is None or snapshot_at > now:
        raise SnapshotError("future snapshot timestamp")
    if now - snapshot_at > MAX_AGE:
        raise SnapshotError("stale road snapshot", code="stale")


def _read_manifest(path: Path, snapshot_id: str) -> Manifest:
    with _open_artifact(path) as stream:
        content = stream.read(MANIFEST_LIMIT + 1)
    if len(content) > MANIFEST_LIMIT:
        raise SnapshotError("manifest size limit exceeded")
    if manifest_id(content) != snapshot_id:
        raise SnapshotError("manifest checksum mismatch")
    try:
        manifest = Manifest.model_validate_json(content)
        metadata = json.loads(content)
        if (
            canonical_json(metadata) != content
            or set(metadata) != set(Manifest.model_fields)
        ):
            raise SnapshotError("noncanonical or incomplete manifest")
        return manifest
    except (ValidationError, RecursionError, UnicodeError, TypeError, ValueError) as exc:
        raise SnapshotError("invalid snapshot manifest") from exc


class _GraphReader:
    def __init__(self, stream: BinaryIO) -> None:
        if os.fstat(stream.fileno()).st_size > GRAPH_LIMIT:
            raise SnapshotError("graph size limit exceeded")
        self.stream = stream
        self.hasher = hashlib.sha256()
        self.size = 0

    def line(self) -> bytes:
        line = self.stream.readline(ROW_LIMIT + 1)
        self.size += len(line)
        if len(line) > ROW_LIMIT or self.size > GRAPH_LIMIT:
            raise SnapshotError("graph size limit exceeded")
        self.hasher.update(line)
        return line

    def rows(self, marker: bytes, limit: int, width: int):
        line = self.line()
        count = 0
        while line != marker:
            count += 1
            if count > limit:
                raise SnapshotError("graph record limit exceeded")
            if not line.endswith(b"\n"):
                raise SnapshotError("invalid graph record")
            more = line.endswith(b",\n")
            record = line[:-2] if more else line[:-1]
            row = json.loads(record)
            if type(row) is not list or len(row) != width or canonical_json(row) != record:
                raise SnapshotError("invalid graph record")
            yield row
            line = self.line()
            if more == (line == marker):
                raise SnapshotError("invalid graph record delimiter")


def _positive_int(value: object) -> bool:
    return type(value) is int and 0 < value <= 2**63 - 1


def _read_graph(stream: BinaryIO, manifest: Manifest) -> Graph:
    reader = _GraphReader(stream)
    if reader.line() != GRAPH_SECTIONS[0][0]:
        raise SnapshotError("invalid graph structure")

    nodes: dict[int, Node] = {}
    previous = 0
    for node_id, longitude, latitude in reader.rows(GRAPH_SECTIONS[0][1], NODE_LIMIT, 3):
        if (
            not _positive_int(node_id)
            or node_id <= previous
            or type(longitude) not in (int, float)
            or type(latitude) not in (int, float)
            or not in_bounds(longitude, latitude, manifest.bounds)
        ):
            raise SnapshotError("invalid or duplicate graph node")
        nodes[node_id] = Node(node_id, longitude, latitude)
        previous = node_id

    edges: dict[int, Edge] = {}
    connected: set[int] = set()
    previous = 0
    for row in reader.rows(GRAPH_SECTIONS[1][1], EDGE_LIMIT, 5):
        edge_id, _, source, target, weight = row
        if (
            not all(_positive_int(value) for value in row)
            or edge_id <= previous
            or source == target
            or source not in nodes
            or target not in nodes
            or weight != edge_weight(nodes[source], nodes[target])
        ):
            raise SnapshotError("invalid or duplicate graph edge")
        edges[edge_id] = Edge(*row)
        connected.update((source, target))
        previous = edge_id

    restrictions = []
    last_pair = (0, 0)
    for incoming, outgoing in reader.rows(GRAPH_SECTIONS[2][1], RESTRICTION_LIMIT, 2):
        pair = (incoming, outgoing)
        if (
            not all(_positive_int(value) for value in pair)
            or pair <= last_pair
            or incoming not in edges
            or outgoing not in edges
            or edges[incoming].target != edges[outgoing].source
        ):
            raise SnapshotError("invalid or duplicate graph restriction")
        restrictions.append(pair)
        last_pair = pair

    stats = manifest.stats
    counts = (len(nodes), len(edges), len(restrictions))
    if (
        reader.line()
        or reader.hasher.hexdigest() != manifest.graph_sha256
        or counts != (stats.nodes, stats.edges, stats.restrictions)
        or len(connected) != len(nodes)
    ):
        raise SnapshotError("graph checksum or counts mismatch")
    return Graph(tuple(nodes.values()), tuple(edges.values()), tuple(restrictions))


def verify_snapshot(
    root: Path | str, snapshot_id: str, now: datetime, allow_fixture: bool = False
) -> Snapshot:
    if not SNAPSHOT_ID.fullmatch(snapshot_id):
        raise SnapshotError("invalid snapshot ID")
    folder = checked_path(Path(root), directory=True) / snapshot_id
    try:
        manifest = _read_manifest(folder / "manifest.json", snapshot_id)
        if manifest.dataset_class == "synthetic_fixture" and not allow_fixture:
            raise SnapshotError("fixture admission is disabled")
        if now.utcoffset() is None or manifest.prepared_at > now:
            raise SnapshotError("future preparation timestamp")
        check_age(manifest.snapshot_at, now)
        with _open_artifact(folder / "graph.json") as stream:
            graph = _read_graph(stream, manifest)
    except SnapshotError:
        raise
    except (OSError, RecursionError, TypeError, ValueError):
        raise SnapshotError("invalid or unavailable graph artifact") from None
    return Snapshot(snapshot_id, manifest, graph)


def write_graph(stream: BinaryIO, graph: Graph) -> str:
    hasher = hashlib.sha256()
    total = 0

    def write(value: bytes) -> None:
        nonlocal total
        total += len(value)
        if total > GRAPH_LIMIT:
            raise SnapshotError("graph size limit exceeded")
        stream.write(value)
        hasher.update(value)

    for (opening, _, limit), rows in zip(
        GRAPH_SECTIONS, (graph.nodes, graph.edges, graph.restrictions), strict=True
    ):
        if len(rows) > limit:
            raise SnapshotError("graph record limit exceeded")
        write(opening)
        for index, row in enumerate(rows, 1):
            write(canonical_json(row) + (b",\n" if index < len(rows) else b"\n"))
    write(GRAPH_SECTIONS[-1][1])
    return hasher.hexdigest()
