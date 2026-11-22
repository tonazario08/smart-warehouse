import json
from hashlib import sha256

from app.purchase_requests.delivery_map import DeliveryMapCatalog
from tests.test_gis_api import sqlite_api


def _artifact():
    return {
        "format": "b2b-osm-leaflet-v1",
        "source_url": "https://download.bbbike.org/osm/bbbike/Saigon/Saigon.osm.gz",
        "source_sha256": "a" * 64,
        "bounds": [106.5444, 10.6564, 106.8545, 10.8931],
        "roads": [{"name": "Đường kiểm thử", "points": [[106.68, 10.76], [106.69, 10.77]]}],
        "places": [{"name": "Mốc kiểm thử", "kind": "landmark", "point": [106.68, 10.76]}],
        "areas": [{"name": None, "kind": "park", "ring": [
            [106.68, 10.76], [106.69, 10.77], [106.70, 10.76], [106.68, 10.76],
        ]}],
    }


def test_valid_artifact_serves_bounds_and_named_features(tmp_path):
    index = tmp_path / "backdrop.json"
    index.write_text(json.dumps(_artifact()), encoding="utf-8")
    result = DeliveryMapCatalog(index, sha256(index.read_bytes()).hexdigest()).read()
    assert result.state == "available"
    assert result.bounds.west == 106.5444
    assert result.roads[0].name == "Đường kiểm thử"
    assert result.places[0].kind == "landmark"
    assert result.attribution == "© OpenStreetMap contributors"
    assert result.license_url == "https://www.openstreetmap.org/copyright"


def test_untrusted_missing_or_bad_geometry_cannot_look_like_map(tmp_path):
    index = tmp_path / "backdrop.json"
    index.write_text(json.dumps(_artifact()), encoding="utf-8")
    for digest in (None, "0" * 64):
        assert DeliveryMapCatalog(index, digest).read().state == "unavailable"
    broken = _artifact()
    broken["roads"][0]["points"][1] = [0, 0]
    index.write_text(json.dumps(broken), encoding="utf-8")
    assert DeliveryMapCatalog(index, sha256(index.read_bytes()).hexdigest()).read().state == (
        "unavailable"
    )
    assert DeliveryMapCatalog(None, None).read().state == "unavailable"


def test_leaflet_map_authentication_and_separation(tmp_path, unit_settings):
    index = tmp_path / "backdrop.json"
    index.write_text(json.dumps(_artifact()), encoding="utf-8")
    settings = unit_settings.model_copy(update={
        "b2b_delivery_map_path": index,
        "b2b_delivery_map_sha256": sha256(index.read_bytes()).hexdigest(),
    })
    with sqlite_api(settings) as (client, headers, _):
        route = "/api/v1/purchase-requests/delivery-map"
        assert client.get(route).status_code == 401
        assert client.get(route, headers=headers["warehouse"]).status_code == 403
        response = client.get(route, headers=headers["client"])
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["state"] == "available"
        assert response.json()["roads"][0]["name"] == "Đường kiểm thử"
        assert "source_sha256" not in response.json()
        assert client.get(route, headers=headers["client"], params={"z": 15}).status_code == 422
        staff = "/api/v1/gis/street-layer"
        assert client.get(staff, headers=headers["client"]).status_code == 403
        assert client.get(staff, headers=headers["warehouse"]).json()["state"] == "unavailable"
