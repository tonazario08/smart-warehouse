"""Build a bounded, offline Leaflet extract of public Saigon OpenStreetMap geometry.

Verify the original BBBike download out of band, then pass its SHA256. This
compiler neither downloads anything nor exports contributor metadata, customer
data, house numbers, contacts, or external asset URLs. This isn't a navigation
map: it omits some geometry and does not infer absent data.
"""

import argparse
import gzip
import hashlib
import io
import json
import math
import os
import re
import tempfile
from collections import defaultdict
from itertools import pairwise
from pathlib import Path
from xml.parsers import expat

from build_b2b_address_index import BBBIKE_BOUNDS, BBBIKE_URL, MAX_BYTES, clean, coordinates
from build_b2b_address_index import xml_objects as parse_xml

MAX_INDEX_BYTES = 8_000_000
MAX_ROADS = 8_000
MAX_AREAS = 500
MAX_PLACES = 400
MAX_PENDING = 100_000
MAX_REFS = 1_500_000
MAX_POINTS_PER_FEATURE = 2_048
MAX_TOTAL_POINTS = 175_000
ROAD_CLASS = {
    name: level
    for level, names in enumerate(
        (
            ("motorway", "trunk", "primary", "secondary"),
            ("motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary"),
            ("tertiary_link", "residential", "living_street", "unclassified", "pedestrian"),
        )
    )
    for name in names
}


def read_objects(raw):
    with gzip.GzipFile(fileobj=io.BytesIO(raw), mode="rb") as xml:
        yield from parse_xml(xml)


def area_kind(tags):
    if (
        tags.get("natural") == "water"
        or tags.get("waterway") == "riverbank"
        or tags.get("landuse") in ("reservoir", "basin")
    ):
        return "water"
    if tags.get("leisure") in ("park", "garden", "nature_reserve"):
        return "park"
    return None


def place_kind(tags):
    if tags.get("place") in ("city", "town", "suburb", "quarter", "neighbourhood"):
        return "neighbourhood"
    if kind := area_kind(tags):
        return kind
    if (
        tags.get("tourism") in ("attraction", "museum", "viewpoint", "zoo", "gallery")
        or tags.get("historic") in ("monument", "memorial", "castle", "fort")
        or tags.get("amenity") in ("theatre", "townhall", "arts_centre", "library")
        or tags.get("building") in ("cathedral", "train_station", "civic")
    ):
        return "landmark"
    return None


def point(obj):
    xy = coordinates(obj, BBBIKE_BOUNDS)
    return tuple(round(value, 6) for value in xy) if xy else None


def compact_points(refs, nodes):
    # Never join non-adjacent OSM nodes across missing/outside geometry.
    route = []
    for ref in refs:
        xy = nodes.get(ref)
        if xy is None:
            return ()
        if not route or route[-1] != xy:
            route.append(xy)
    return tuple(route)


def polygon_size(points):
    return abs(sum(ax * by - bx * ay for (ax, ay), (bx, by) in pairwise(points)))


def label_point(points):
    xs, ys = zip(*points, strict=True)
    return (round((min(xs) + max(xs)) / 2, 6), round((min(ys) + max(ys)) / 2, 6))


def select_roads(roads):
    def rank(key):
        return (
            not key[0],
            roads[key],
            -sum(math.hypot(ax - bx, ay - by) for (ax, ay), (bx, by) in pairwise(key[1])),
            key,
        )

    # Preserve the most detail in the central delivery area, while also
    # reserving coverage across the rest of the admitted Saigon extract.
    west, south, east, north = (106.676, 10.751, 106.728, 10.804)
    core, outer = [], defaultdict(list)
    for key in sorted(roads, key=rank):
        lon, lat = label_point(key[1])
        if west <= lon <= east and south <= lat <= north:
            core.append(key)
        else:
            outer[(math.floor(lon * 50), math.floor(lat * 50))].append(key)
    chosen = core[:1800]
    buckets = [outer[cell] for cell in sorted(outer)] + [core[1800:]]
    for depth in range(max(map(len, buckets))):
        if len(chosen) >= MAX_ROADS:
            break
        chosen.extend(bucket[depth] for bucket in buckets if depth < len(bucket))
    return chosen[:MAX_ROADS]


def extract(raw):
    needed, paths, places = set(), [], set()
    for obj in read_objects(raw):
        tags, refs = obj["tags"], obj["refs"]
        name = clean(tags.get("name")) or None
        kind = place_kind(tags) if name else None
        if obj["type"] == "node":
            if kind and (xy := point(obj)):
                places.add((kind, name, xy))
                if len(places) > MAX_PENDING:
                    raise ValueError("too many candidate public places")
            continue
        road_class = ROAD_CLASS.get(tags.get("highway"))
        area = area_kind(tags) if len(refs) >= 4 and refs[0] == refs[-1] else None
        if not 2 <= len(refs) <= MAX_POINTS_PER_FEATURE:
            continue
        if road_class is not None or area or kind:
            paths.append((road_class, refs, name, area, kind))
            needed.update(refs)
        if len(paths) > MAX_PENDING or len(needed) > MAX_REFS or len(places) > MAX_PENDING:
            raise ValueError("too many candidate objects")
    nodes = {
        obj["id"]: xy
        for obj in read_objects(raw)
        if obj["type"] == "node" and obj["id"] in needed and (xy := point(obj))
    }
    roads, areas = {}, {}
    for road_class, refs, name, area, kind in paths:
        points = compact_points(refs, nodes)
        if len(points) < 2:
            continue
        if road_class is not None:
            canon = min(points, points[::-1])
            key = (name or "", canon)
            roads[key] = min(roads.get(key, road_class), road_class)
        if area and len(points) >= 4 and (size := polygon_size(points)) > 1e-12:
            areas[(area, name or "", points)] = size
        if kind and name:
            places.add((kind, name, label_point(points)))
    if not any(key[0] for key in roads) or not places:
        raise ValueError("missing displayable public map geometry")

    road_rank = select_roads(roads)
    area_rank = sorted(areas, key=lambda key: (-areas[key], key))
    # Interleave kinds so 400 features don't end up being solely landmarks.
    place_groups = {
        kind: sorted(row for row in places if row[0] == kind)
        for kind in ("landmark", "neighbourhood", "park", "water")
    }
    place_rank = [
        row
        for i in range(MAX_PLACES)
        for group in place_groups.values()
        if i < len(group) and (row := group[i])
    ]
    return (
        [{"name": name or None, "points": points} for name, points in road_rank],
        [{"name": name, "kind": kind, "point": xy} for kind, name, xy in place_rank[:MAX_PLACES]],
        [
            {"name": name or None, "kind": kind, "ring": ring}
            for kind, name, ring in area_rank[:MAX_AREAS]
        ],
    )


def build(source, output, expected_sha256):
    if source.resolve() == output.resolve():
        raise ValueError("source and output must differ")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("invalid expected SHA256")
    with source.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("compressed input too large")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise ValueError("wrong source SHA256")

    roads, places, areas = extract(raw)
    total_points = (
        len(places)
        + sum(len(road["points"]) for road in roads)
        + sum(len(area["ring"]) for area in areas)
    )
    if total_points > MAX_TOTAL_POINTS:
        raise ValueError("total geometry exceeds runtime budget")
    payload = {
        "format": "b2b-osm-leaflet-v1",
        "source_url": BBBIKE_URL,
        "source_sha256": digest,
        "bounds": BBBIKE_BOUNDS,
        "roads": roads,
        "places": places,
        "areas": areas,
    }
    encoded = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    if len(encoded) > MAX_INDEX_BYTES:
        raise ValueError("output too large")
    fd, temporary = tempfile.mkstemp(dir=output.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
        os.replace(temporary, output)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source-sha256", required=True)
    args = parser.parse_args()
    try:
        build(args.source, args.output, args.source_sha256)
    except (OSError, ValueError, KeyError, EOFError, expat.ExpatError):
        parser.exit(1, "Leaflet map not built: invalid or unreadable source/output.\n")


if __name__ == "__main__":
    main()
