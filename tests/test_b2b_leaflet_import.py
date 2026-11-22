import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("tools/build_b2b_leaflet_map.py")
MAP_SOURCE = "https://download.bbbike.org/osm/bbbike/Saigon/Saigon.osm.gz"
XML = """<osm version="0.6">
  <node id="1" lat="10.77" lon="106.70" user="ignore-author" uid="1">
    <tag k="name" v="Nhà hát"/><tag k="tourism" v="attraction"/>
    <tag k="contact:email" v="ignore-contact"/>
  </node>
  <node id="2" lat="10.78" lon="106.71"/>
  <node id="3" lat="10.79" lon="106.73"/>
  <node id="4" lat="9.1" lon="106.72"/>
  <way id="5"><nd ref="1"/><nd ref="2"/><nd ref="3"/>
    <tag k="highway" v="residential"/><tag k="name" v="Đồng Khởi"/>
  </way>
  <way id="6"><nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="1"/>
    <tag k="leisure" v="park"/><tag k="name" v="Công viên"/>
  </way>
  <way id="7"><nd ref="4"/><nd ref="2"/><nd ref="3"/>
    <tag k="highway" v="service"/><tag k="name" v="Outside edge"/>
  </way>
  <way id="8"><nd ref="1"/><nd ref="999"/><nd ref="3"/>
    <tag k="highway" v="primary"/><tag k="name" v="Never bridge missing refs"/>
  </way>
</osm>"""


def run(source, digest, output):
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(source), str(output), "--source-sha256", digest],
        capture_output=True,
        text=True,
    )


def test_import_uses_offline_public_geometry_no_synthetic_connections(tmp_path):
    source, output = tmp_path / "Saigon.osm.gz", tmp_path / "output.json"
    raw = gzip.compress(XML.encode(), mtime=0)
    source.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    process = run(source, digest, output)
    assert process.returncode == 0, process.stderr
    encoded = output.read_bytes()
    assert run(source, digest, output).returncode == 0
    assert output.read_bytes() == encoded
    document = json.loads(encoded)
    assert document["format"] == "b2b-osm-leaflet-v1"
    assert document["source_url"] == MAP_SOURCE
    assert document["source_sha256"] == digest
    assert document["bounds"] == [106.5444, 10.6564, 106.8545, 10.8931]
    assert document["roads"] == [
        {"name": "Đồng Khởi", "points": [[106.70, 10.77], [106.71, 10.78], [106.73, 10.79]]}
    ]
    assert {"name": "Nhà hát", "kind": "landmark", "point": [106.70, 10.77]} in document["places"]
    assert document["areas"] == [
        {
            "name": "Công viên",
            "kind": "park",
            "ring": [[106.70, 10.77], [106.71, 10.78], [106.73, 10.79], [106.70, 10.77]],
        }
    ]
    assert "ignore" not in encoded.decode()


def test_pin_and_incomplete_input_leave_existing_output_intact(tmp_path):
    source, output = tmp_path / "Saigon.osm.gz", tmp_path / "output.json"
    output.write_text("previous")
    for raw, expected in (
        (gzip.compress(XML.encode()), "0" * 64),
        (gzip.compress(b'<!DOCTYPE osm [<!ENTITY f "hidden">]><osm>&f;</osm>'), None),
        (b"not-gzip", None),
    ):
        source.write_bytes(raw)
        result = run(source, expected or hashlib.sha256(raw).hexdigest(), output)
        assert result.returncode != 0
        assert "hidden" not in result.stderr
        assert output.read_text() == "previous"
