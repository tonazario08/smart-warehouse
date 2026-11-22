import json

from app.purchase_requests.delivery_geocode import DeliveryGeocoder


def _index(tmp_path):
    path = tmp_path / "addresses.json"
    path.write_text(json.dumps({
        "format": "b2b-osm-address-v1",
        "source_url": "https://download.geofabrik.de/asia/vietnam.html",
        "source_sha256": "a" * 64,
        "bounds": [106.6, 10.7, 106.8, 10.9],
        "entries": [
            {"street": "Nam Kỳ Khởi Nghĩa", "house_number": "135", "local_area": "Quận 1",
             "latitude": 10.777, "longitude": 106.695},
            {"street": "Nam Kỳ Khởi Nghĩa", "house_number": "135", "local_area": "Quận 3",
             "latitude": 10.79, "longitude": 106.69},
            {"street": "Nam Kỳ Khởi Nghĩa", "latitude": 10.778, "longitude": 106.696},
            {"street": "Tên Đường Khác", "latitude": 10.779, "longitude": 106.697},
        ],
    }), encoding="utf-8")
    return path


def test_exact_accentless_housenumber_and_area_disambiguates(tmp_path):
    index = DeliveryGeocoder(_index(tmp_path))
    result = index.find("135 duong nam ky khoi nghia, Q. 1, TP. Hồ Chí Minh")
    assert result.status == "matches"
    assert [(c.precision, c.latitude) for c in result.candidates] == [
        ("house_number", 10.777),
    ]
    assert len(index.find("135 Nam Kỳ Khởi Nghĩa").candidates) == 2


def test_no_substituted_house_number_or_unvalidated_place(tmp_path):
    index = DeliveryGeocoder(_index(tmp_path))
    assert index.find("99 Nam Ky Khoi Nghia").candidates[0].precision == "approximate"
    assert index.find("135 Nam Ky Khoi Nghia, Hà Nội").status == "no_match"
    assert index.find("135 Nam Ky Khoi Nghia, Quan 7").status != "matches"
    assert index.find("135 Nam Ky").status == "no_match"
    assert index.find("135/4 Nam Ky Khoi Nghia").candidates[0].precision == "approximate"


def test_missing_or_corrupt_manifest_is_unavailable(tmp_path):
    path = _index(tmp_path)
    broken = json.loads(path.read_text())
    broken["entries"][0]["longitude"] = 0
    path.write_text(json.dumps(broken))
    assert DeliveryGeocoder(path).find("135 Nam Ky Khoi Nghia").status == "unavailable"
    assert DeliveryGeocoder(None).find("135 Nam Ky Khoi Nghia").status == "unavailable"


def test_authenticated_isolated_endpoints_never_echo_search_text(tmp_path, unit_settings):
    from hashlib import sha256

    from tests.test_gis_api import sqlite_api

    path = _index(tmp_path)
    settings = unit_settings.model_copy(update={
        "b2b_address_index_path": path,
        "b2b_address_index_sha256": sha256(path.read_bytes()).hexdigest(),
    })
    base = "/api/v1/purchase-requests"
    search = base + "/geocode-delivery-address"
    layer = base + "/delivery-map"
    with sqlite_api(settings) as (client, headers, _):
        for request in [
            lambda: client.post(search, json={"address": "135 Nam Ky Khoi Nghia"}),
            lambda: client.get(layer),
        ]:
            response = request()
            assert response.status_code == 401
            assert response.headers["cache-control"] == "no-store"

        for role in ("admin", "warehouse"):
            assert client.get(layer, headers=headers[role]).status_code == 403
            assert client.post(search, headers=headers[role], json={
                "address": "135 Nam Ky Khoi Nghia"
            }).status_code == 403

        response = client.post(search, headers=headers["client"], json={
            "address": "135 Nam Ky Khoi Nghia, Quan 1",
        })
        assert response.status_code == 200
        assert response.json()["candidates"][0]["precision"] == "house_number"
        assert response.headers["cache-control"] == "no-store"
        assert client.get(layer, headers=headers["client"]).json()["state"] == "unavailable"
        assert client.get("/api/v1/gis/street-layer", headers=headers["client"]).status_code == 403

        private = "never-echo-client-value"
        for response in [
            client.post(search, headers=headers["client"], json={private: private}),
            client.post(search, headers=headers["client"], json={"address": private * 30}),
            client.post(search, headers=headers["client"], params={"address": private},
                        json={"address": "Valid short"}),
        ]:
            assert response.status_code == 422
            assert response.headers["cache-control"] == "no-store"
            assert private not in response.text


def test_invalid_local_digest_refuses_dataset(tmp_path):
    assert DeliveryGeocoder(_index(tmp_path), "0" * 64).find(
        "135 Nam Kỳ Khởi Nghĩa"
    ).status == "unavailable"
