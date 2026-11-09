from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from urllib.request import Request

import pytest

from app.gis.catalog import MANIFEST_LIMIT, SnapshotError
from app.gis.schemas import PUBLIC_ATTRIBUTION, PUBLIC_BOUNDS, PUBLIC_LICENSE, Node, edge_weight
from deploy.render import start
from tests.gis_helpers import MANIFEST, write_fixture

ASSET_BASE = "https://github.com/example/smart-warehouse/releases/download/gis-demo"


class Asset(BytesIO):
    def geturl(self) -> str:
        return "https://release-assets.githubusercontent.com/github-production-release-asset"


@pytest.fixture
def public_artifact(tmp_path: Path) -> tuple[str, Path]:
    now = datetime.now(UTC)
    snapshot_at = now - timedelta(days=1)
    source = Node(1, 106.69, 10.76)
    target = Node(2, 106.691, 10.76)
    return write_fixture(
        tmp_path / "asset",
        changes={
            "dataset_class": "public_osm",
            "snapshot_at": snapshot_at.isoformat(),
            "prepared_at": (now - timedelta(hours=1)).isoformat(),
            "source_url": f"https://download.geofabrik.de/asia/vietnam-{snapshot_at:%y%m%d}.osm.pbf",
            "source_sha256": "a" * 64,
            "bounds": PUBLIC_BOUNDS,
            "license": PUBLIC_LICENSE,
            "attribution": PUBLIC_ATTRIBUTION,
            "stats": {**MANIFEST["stats"], "nodes": 2, "edges": 1, "restrictions": 0},
        },
        graph={
            "nodes": [source, target],
            "edges": [[1, 10, source.id, target.id, edge_weight(source, target)]],
            "restrictions": [],
        },
    )


def test_uses_psycopg_and_only_the_dedicated_demo_database():
    source = "postgresql://demo:pass%40word@db/smart_warehouse_render_demo?sslmode=require"
    assert start.demo_database_url(source) == source.replace("postgresql:", "postgresql+psycopg:")
    with pytest.raises(ValueError, match="demo database"):
        start.demo_database_url("postgresql://demo:test@db/smart_warehouse")
    with pytest.raises(ValueError, match="demo database"):
        start.demo_database_url(source + "&dbname=warehouse_existing")


def test_alembic_preserves_percent_encoded_credentials(monkeypatch):
    source = "postgresql+psycopg://demo:pass%40word@db/smart_warehouse_render_demo"
    calls = []
    monkeypatch.setattr(
        "alembic.command.upgrade",
        lambda config, revision: calls.append((config.get_main_option("sqlalchemy.url"), revision)),
    )
    start.upgrade_demo_database(source)
    assert calls == [(source, "head")]


@pytest.mark.parametrize("destination", [
    "http://release-assets.githubusercontent.com/asset",
    "https://untrusted.example.com/asset",
])
def test_disallows_asset_redirects_before_connecting(destination):
    request = Request(f"{ASSET_BASE}/graph.json")
    with pytest.raises(ValueError, match="release asset origin"):
        start.ReleaseRedirect().redirect_request(request, None, 302, "", {}, destination)


def test_accepts_normal_github_release_redirect():
    request = Request(f"{ASSET_BASE}/graph.json")
    destination = Asset().geturl()
    redirected = start.ReleaseRedirect().redirect_request(request, None, 302, "", {}, destination)
    assert redirected.full_url == destination


def test_downloads_and_reuses_verified_public_artifact(monkeypatch, tmp_path, public_artifact):
    snapshot_id, source = public_artifact
    fetched = []

    def open_asset(url, *, timeout):
        fetched.append(url)
        return Asset((source / url.rsplit("/", 1)[1]).read_bytes())

    monkeypatch.setattr(start, "open_release_asset", open_asset)
    catalog = tmp_path / "catalog"
    start.prepare_snapshot(catalog, snapshot_id, ASSET_BASE)
    start.prepare_snapshot(catalog, snapshot_id, ASSET_BASE)

    assert fetched == [f"{ASSET_BASE}/manifest.json", f"{ASSET_BASE}/graph.json"]
    downloaded = catalog / snapshot_id / "graph.json"
    assert downloaded.read_bytes() == (source / "graph.json").read_bytes()


@pytest.mark.parametrize(("failure", "message"), [
    ("tampered", "graph checksum or counts mismatch"),
    ("oversized", "size limit"),
    ("insecure", "HTTPS GitHub Release"),
])
def test_rejects_unsafe_artifacts_without_publishing(
    monkeypatch, tmp_path, public_artifact, failure, message,
):
    snapshot_id, source = public_artifact
    catalog = tmp_path / "catalog"

    def open_asset(url, *, timeout):
        name = url.rsplit("/", 1)[1]
        content = (source / name).read_bytes()
        if failure == "oversized" and name == "manifest.json":
            content = b"x" * (MANIFEST_LIMIT + 1)
        if failure == "tampered" and name == "graph.json":
            content += b"x"
        return Asset(content)

    monkeypatch.setattr(start, "open_release_asset", open_asset)
    base = ASSET_BASE.replace("https:", "http:") if failure == "insecure" else ASSET_BASE
    with pytest.raises(ValueError, match=message):
        start.prepare_snapshot(catalog, snapshot_id, base)
    assert not (catalog / snapshot_id).exists()


def test_refuses_fixture_in_production(monkeypatch, tmp_path):
    snapshot_id, source = write_fixture(tmp_path / "asset")
    monkeypatch.setattr(
        start, "open_release_asset",
        lambda url, timeout: Asset((source / url.rsplit("/", 1)[1]).read_bytes())
    )
    catalog = tmp_path / "catalog"
    with pytest.raises(SnapshotError, match="fixture admission is disabled"):
        start.prepare_snapshot(catalog, snapshot_id, ASSET_BASE)
    assert not (catalog / snapshot_id).exists()
