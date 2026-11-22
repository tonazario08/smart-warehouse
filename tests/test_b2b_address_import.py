import hashlib
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("tools/build_b2b_address_index.py")
SOURCE_URL = "https://overpass-api.de/api/interpreter"


def run(source, output):
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(source), str(output)],
        capture_output=True,
        text=True,
    )


def test_index_uses_public_fields_and_exact_source_digest(tmp_path):
    node = {"type": "node", "lat": 10.77, "lon": 106.70}
    elements = [
        {
            **node,
            "tags": {
                "addr:housenumber": "12A",
                "addr:street": " Đường A ",
                "addr:suburb": "Phường 1",
                "contact:phone": "never-copy",
            },
        },
        {
            "type": "way",
            "center": {"lat": 10.78, "lon": 106.71},
            "tags": {"highway": "residential", "name": "Đường A", "addr:housenumber": "99"},
        },
        {**node, "lon": 106.0, "tags": {"addr:housenumber": "42", "addr:street": "Đường A"}},
        {
            **node,
            "tags": {
                "addr:housenumber": "13",
                "addr:street": "Đường A",
                "addr:interpolation": "even",
            },
        },
        {**node, "lat": True, "tags": {"highway": "primary", "name": "Không hợp lệ"}},
        {**node, "tags": {"name": "A shop", "phone": "never-copy"}},
        {**node, "tags": {"highway": "residential", "name": "A"}},
        {**node, "tags": {"addr:housenumber": "12", "addr:street": "1"}},
        {
            **node,
            "lat": 10.781,
            "lon": 106.711,
            "tags": {
                "highway": "residential",
                "name": "Đường A",
            },
        },
    ]
    source, output = tmp_path / "overpass.json", tmp_path / "index.json"
    source.write_text(json.dumps({"elements": elements + elements}), encoding="utf-8")
    result = run(source, output)
    assert result.returncode == 0, result.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["format"] == "b2b-osm-address-v1"
    assert result["source_url"] == SOURCE_URL
    assert result["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert result["entries"] == [
        {
            "street": "Đường A",
            "house_number": "12A",
            "local_area": "Phường 1",
            "latitude": 10.77,
            "longitude": 106.70,
        },
        {"street": "Đường A", "latitude": 10.78, "longitude": 106.71},
    ]
    assert "never-copy" not in output.read_text(encoding="utf-8")


def test_partial_error_and_empty_files_fail_closed(tmp_path):
    source, output = tmp_path / "private_source.json", tmp_path / "index.json"
    output.write_text("existing")
    for body in ({"elements": [], "remark": "private-response"}, {"elements": []}, {"foo": []}):
        source.write_text(json.dumps(body))
        result = run(source, output)
        assert result.returncode != 0
        assert "private-response" not in result.stderr
        assert output.read_text() == "existing"


def test_bbbike_keeps_actual_way_point_and_address_center(tmp_path):
    import gzip

    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <osm version="0.6">
      <node id="1" lat="10.77" lon="106.70" />
      <node id="2" lat="10.78" lon="106.71" />
      <node id="3" lat="10.79" lon="106.73" />
      <way id="4"><nd ref="1"/><nd ref="2"/><nd ref="3"/>
        <tag k="highway" v="residential"/><tag k="name" v="Đường B"/>
      </way>
      <way id="5"><nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="1"/>
        <tag k="building" v="yes"/>
        <tag k="addr:street" v="Đường B"/><tag k="addr:housenumber" v="12"/>
        <tag k="addr:housename" v="never-copy"/>
      </way>
    </osm>"""
    source, output = tmp_path / "Saigon.osm.gz", tmp_path / "index.json"
    source.write_bytes(gzip.compress(xml.encode(), mtime=0))
    cmd = [sys.executable, str(SCRIPT), str(source), str(output), "--source-format", "bbbike-osm"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    data = json.loads(output.read_bytes())
    assert data["source_url"] == "https://download.bbbike.org/osm/bbbike/Saigon/Saigon.osm.gz"
    assert data["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    address, street = data["entries"]
    assert address["house_number"] == "12"
    assert "never-copy" not in output.read_text()
    assert street == {"street": "Đường B", "latitude": 10.78, "longitude": 106.71}

    previous = output.read_bytes()
    source.write_bytes(gzip.compress(b'<!DOCTYPE osm [<!ENTITY x "bad">]><osm>&x;</osm>'))
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode != 0
    assert "ENTITY" not in result.stderr
    assert output.read_bytes() == previous
