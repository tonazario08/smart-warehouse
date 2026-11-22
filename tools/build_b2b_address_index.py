"""Compile a locally retained, operator-verified public OSM extract.

The URL records declared origin, not a signature. Preserve the original input
for audit. This tool does not download anything or use customer addresses.
An OSM object center is not an entrance; named-highway points are approximate.
"""

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import tempfile
import unicodedata
from pathlib import Path
from xml.parsers import expat

SOURCE_URL = "https://overpass-api.de/api/interpreter"
BBBIKE_URL = "https://download.bbbike.org/osm/bbbike/Saigon/Saigon.osm.gz"
BOUNDS = (106.35, 10.30, 107.10, 11.20)
BBBIKE_BOUNDS = (106.5444, 10.6564, 106.8545, 10.8931)
MAX_BYTES = 50_000_000
MAX_INDEX_BYTES = 20 * 1024 * 1024
MAX_XML_BYTES = 750_000_000
MAX_REFERENCES = 1_500_000
MAX_ENTRIES = 100_000
HOUSE_NUMBER = re.compile(r"[0-9]{1,6}[A-Za-z]?(?:[/-][0-9]{1,6}[A-Za-z]?){0,4}")


def clean(value, limit=120):
    if not isinstance(value, str) or len(value) > limit:
        return ""
    if any(unicodedata.category(char).startswith("C") for char in value):
        return ""
    return " ".join(unicodedata.normalize("NFC", value).split())


def coordinates(element, bounds=BOUNDS):
    if element.get("type") not in ("node", "way", "relation"):
        return None
    position = element if element["type"] == "node" else element.get("center")
    if not isinstance(position, dict):
        return None
    lon, lat = position.get("lon"), position.get("lat")
    west, south, east, north = bounds
    if type(lon) not in (float, int) or type(lat) not in (float, int):
        return None
    if west <= lon <= east and south <= lat <= north:
        return float(lon), float(lat)
    return None


def entries_for(elements, bounds=BOUNDS):
    entries = set()
    for element in elements:
        if not isinstance(element, dict):
            continue
        tags = element.get("tags")
        point = coordinates(element, bounds)
        if not isinstance(tags, dict) or point is None:
            continue
        lon, lat = point
        local = next(
            (
                value
                for key in ("addr:suburb", "addr:district", "addr:quarter")
                if (value := clean(tags.get(key)))
            ),
            "",
        )
        street = clean(tags.get("addr:street"))
        number = clean(tags.get("addr:housenumber"), 40)
        if len(street) >= 2 and HOUSE_NUMBER.fullmatch(number) and "addr:interpolation" not in tags:
            entries.add((street, number, local, lat, lon))
        if clean(tags.get("highway")) and len(name := clean(tags.get("name"))) >= 2:
            entries.add((name, "", local, lat, lon))
        if len(entries) > MAX_ENTRIES:
            raise ValueError("too many entries")
    if not entries:
        raise ValueError("no usable entries")
    output = []
    prior_street_points = {}
    for street, number, local, lat, lon in sorted(
        entries, key=lambda row: (row[0].casefold(), row[0], not row[1], *row[1:])
    ):
        if not number:
            points = prior_street_points.setdefault((street.casefold(), local.casefold()), [])
            # Keep at most one actual source point within roughly 1.5 km per
            # street/area, without conflating separated same-name roads.
            if any((lat - y) ** 2 + (lon - x) ** 2 < 0.014**2 for y, x in points):
                continue
            points.append((lat, lon))
        output.append(
            {
                "street": street,
                **({"house_number": number} if number else {}),
                **({"local_area": local} if local else {}),
                "latitude": lat,
                "longitude": lon,
            }
        )
    return output


def xml_objects(handle):
    parser = expat.ParserCreate(encoding="UTF-8")
    chunk_size = 65_536
    level, current = 0, None
    output = []

    def dtd(*_):
        raise ValueError("DOCTYPE not allowed")

    def start(name, attrs):
        nonlocal level, current
        if level == 0 and name != "osm":
            raise ValueError("not OSM XML")
        if level == 1 and name in ("node", "way"):
            current = {"type": name, "id": int(attrs["id"]), "tags": {}, "refs": []}
            if name == "node":
                current["lat"], current["lon"] = float(attrs["lat"]), float(attrs["lon"])
        if current is not None and level == 2:
            if name == "nd":
                current["refs"].append(int(attrs["ref"]))
            if name == "tag":
                current["tags"][attrs["k"]] = attrs["v"]
            if len(current["refs"]) > 100_000 or len(current["tags"]) > 1_000:
                raise ValueError("oversized OSM object")
        level += 1

    def end(_):
        nonlocal level, current
        level -= 1
        if level == 1 and current is not None:
            output.append(current)
            current = None

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.StartDoctypeDeclHandler = dtd
    count = 0
    while data := handle.read(chunk_size):
        count += len(data)
        if count > MAX_XML_BYTES:
            raise ValueError("expanded input too large")
        parser.Parse(data, False)
        yield from output
        output.clear()
    parser.Parse(b"", True)
    yield from output


def bbbike_elements(handle):
    ways, needed = [], set()
    with gzip.GzipFile(fileobj=handle, mode="rb") as xml:
        for obj in xml_objects(xml):
            tags = obj["tags"]
            if obj["type"] == "node":
                if "addr:housenumber" in tags:
                    yield obj
                continue
            is_road = bool(clean(tags.get("highway")) and clean(tags.get("name")))
            is_building_address = (
                "building" in tags
                and "addr:street" in tags
                and "addr:housenumber" in tags
                and "addr:interpolation" not in tags
            )
            refs = obj["refs"]
            if is_building_address and len(refs) >= 4 and refs[0] == refs[-1]:
                building_tags = {key: value for key, value in tags.items() if key != "highway"}
                ways.append((building_tags, refs[:-1], True))
                needed.update(refs)
            if is_road and refs:
                road_tags = {key: value for key, value in tags.items() if key != "addr:housenumber"}
                ways.append((road_tags, [refs[len(refs) // 2]], False))
                needed.add(refs[len(refs) // 2])
            if len(needed) > MAX_REFERENCES or len(ways) > MAX_ENTRIES:
                raise ValueError("too many candidate ways")
    handle.seek(0)
    nodes = {}
    with gzip.GzipFile(fileobj=handle, mode="rb") as xml:
        for obj in xml_objects(xml):
            if obj["type"] == "node" and obj["id"] in needed and (point := coordinates(obj)):
                nodes[obj["id"]] = point
    for tags, refs, building in ways:
        if not all(ref in nodes for ref in refs):
            continue
        points = [nodes[ref] for ref in refs]
        if building:
            # Use the bounding center, the same coarse geometry convention as Overpass center.
            longitudes, latitudes = zip(*points, strict=True)
            lon, lat = (
                (min(longitudes) + max(longitudes)) / 2,
                (min(latitudes) + max(latitudes)) / 2,
            )
        else:
            lon, lat = points[0]
        yield {"type": "way", "center": {"lon": lon, "lat": lat}, "tags": tags}


def build(source, output, source_format="overpass-json"):
    if source.resolve() == output.resolve():
        raise ValueError("source and output must differ")
    with source.open("rb") as handle:
        data = handle.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("source too large")
        digest = hashlib.sha256(data).hexdigest()
        if source_format == "bbbike-osm":
            bounds = BBBIKE_BOUNDS
            entries = entries_for(bbbike_elements(io.BytesIO(data)), bounds)
            source_url = BBBIKE_URL
        else:
            payload = json.loads(data)
            if not isinstance(payload, dict) or "remark" in payload:
                raise ValueError("invalid or incomplete Overpass response")
            elements = payload.get("elements")
            if not isinstance(elements, list):
                raise ValueError("missing Overpass elements")
            entries = entries_for(elements)
            source_url = SOURCE_URL
            bounds = BOUNDS
    document = {
        "format": "b2b-osm-address-v1",
        "source_url": source_url,
        "source_sha256": digest,
        "bounds": bounds,
        "entries": entries,
    }
    encoded = (json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    if len(encoded) > MAX_INDEX_BYTES:
        raise ValueError("output too large")
    fd, temporary = tempfile.mkstemp(dir=output.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
        os.replace(temporary, output)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--source-format", choices=("overpass-json", "bbbike-osm"), default="overpass-json"
    )
    args = parser.parse_args()
    try:
        build(args.source, args.output, args.source_format)
    except (OSError, ValueError, KeyError, EOFError, RecursionError, expat.ExpatError):
        parser.exit(1, "Address index not built: invalid, incomplete or unreadable input/output.\n")


if __name__ == "__main__":
    main()
