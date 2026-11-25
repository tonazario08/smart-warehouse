"""Bounded, display-only linework derived from an already-admitted road graph."""

from bisect import insort

from app.gis.schemas import Snapshot

type Position = tuple[float, float]
type Segment = tuple[Position, Position]

GRID_SIZE = 20
PER_CELL = 6
MAX_SEGMENTS = GRID_SIZE ** 2 * PER_CELL


def sample_streets(snapshot: Snapshot) -> tuple[Segment, ...]:
    """Draw a sparse fixed grid of real graph edges, never reconstructing roads.

    Longest edges first in each geographic cell. Canonical endpoint order removes
    reverse-direction duplicates: direction remains a property of routing only.
    Tie-breaking and publication order are independent of ingestion order.
    """
    manifest = snapshot.manifest
    if manifest.dataset_class != "public_osm":
        return ()
    points = {node.id: (node.longitude, node.latitude) for node in snapshot.graph.nodes}
    west, south, east, north = manifest.bounds
    retained: dict[tuple[int, int], list[tuple[int, Segment]]] = {}
    for edge in snapshot.graph.edges:
        a, b = points[edge.source], points[edge.target]
        if a == b:
            continue
        segment = (a, b) if a < b else (b, a)
        x = ((a[0] + b[0]) / 2 - west) / (east - west)
        y = ((a[1] + b[1]) / 2 - south) / (north - south)
        cell = min(GRID_SIZE - 1, int(x * GRID_SIZE)), min(GRID_SIZE - 1, int(y * GRID_SIZE))
        candidates = retained.setdefault(cell, [])
        entry = (-edge.weight_mm, segment)
        if entry in candidates or (len(candidates) == PER_CELL and entry >= candidates[-1]):
            continue
        insort(candidates, entry)
        if len(candidates) > PER_CELL:
            candidates.pop()
    return tuple(segment for cell in sorted(retained) for _, segment in retained[cell])
