from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from urllib.request import Request
from zipfile import ZipFile

import pytest

from app.gis.catalog import MANIFEST_LIMIT, SnapshotError
from app.gis.schemas import PUBLIC_ATTRIBUTION, PUBLIC_BOUNDS, PUBLIC_LICENSE, Node, edge_weight
from deploy.render import integrated, start
from tests.gis_helpers import MANIFEST, write_fixture

ASSET_BASE = "https://github.com/example/smart-warehouse/releases/download/gis-demo"


@pytest.mark.parametrize("bad_member", ["../outside.json", "unexpected.json", "forecast/x"])
def test_integrated_bundle_rejects_unexpected_paths(tmp_path, bad_member):
    archive = tmp_path / "bundle.zip"
    forecast = "forecast/operational/frv1-" + "1" * 64
    policy = "replenishment/operational/rrv1-" + "2" * 64
    forecast_files = ("metrics.json", "predictions.jsonl", "public-manifest.json")
    policy_files = (
        "calibration.json", "days.jsonl", "orders.jsonl", "summaries.json", "public-manifest.json",
    )
    valid_members = (
        "manifest.json",
        *(f"{forecast}/{name}" for name in forecast_files),
        *(f"{policy}/{name}" for name in policy_files),
        "cold-start/csv1-" + "3" * 64,
        "anomaly/arv1-" + "4" * 64 + ".json",
    )
    with ZipFile(archive, "w") as bundle:
        for member in valid_members:
            bundle.writestr(member, "fixture")
    integrated.extract_bundle(archive, tmp_path / "valid-catalogs")
    with ZipFile(archive, "w") as bundle:
        for member in (*valid_members[:-1], bad_member):
            bundle.writestr(member, "fixture")
    with pytest.raises(ValueError, match="bundle members"):
        integrated.extract_bundle(archive, tmp_path / "catalogs")
    assert not (tmp_path / "outside.json").exists()


def test_integrated_bundle_rejects_checksum_mismatch_before_extraction(monkeypatch, tmp_path):
    def download(url, destination, limit):
        destination.write_bytes(b"invalid release content")

    monkeypatch.setattr(integrated, "extract_bundle", lambda *_: pytest.fail("extraction started"))
    with pytest.raises(ValueError, match="bundle checksum"):
        integrated.prepare_bundle(ASSET_BASE + "/synthetic-demo.zip", "0" * 64, tmp_path, download)


def test_integrated_bundle_url_must_be_a_github_release(tmp_path):
    with pytest.raises(ValueError, match="GitHub Release"):
        integrated.prepare_bundle(
            "https://example.com/synthetic-demo.zip", "0" * 64, tmp_path, None
        )


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


@pytest.mark.parametrize(("enabled", "model", "url", "expected"), [
    ("false", "", "https://model.example.com/v1", ["snapshot", "migration", "seed", "serve"]),
    ("true", "demo-model", "https://model.example.com/v1",
     ["snapshot", "migration", "seed", "corpus", "serve"]),
    ("true", "", "https://model.example.com/v1", []),
    ("true", "demo-model", "http://127.0.0.1:11434/v1", []),
])
def test_start_imports_corpus_only_for_configured_assistant(
    monkeypatch, tmp_path, capsys, enabled, model, url, expected,
):
    env = {
        "APP_ENV": "production",
        "DATABASE_URL": "postgresql://demo:password@db/smart_warehouse_render_demo",
        "JWT_SECRET_KEY": "unit-test-secret-long-enough-for-production",
        "PORT": "8000",
        "CORS_ORIGINS": '["https://demo.onrender.com"]',
        "GIS_CATALOG_ROOT": str(tmp_path),
        "GIS_SNAPSHOT_ID": "snapshot",
        "GIS_RELEASE_ASSET_BASE": ASSET_BASE,
        "ASSISTANT_ENABLED": enabled,
        "ASSISTANT_BASE_URL": url,
        "ASSISTANT_MODEL": model,
        "ASSISTANT_API_KEY": "redacted-test-credential",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    events = []
    monkeypatch.setattr(start, "load_seed_settings", lambda: None)
    monkeypatch.setattr(start, "prepare_snapshot", lambda *_: events.append("snapshot"))
    monkeypatch.setattr(start, "upgrade_demo_database", lambda _: events.append("migration"))

    def run(args, *, check):
        assert check
        if args[1:] == ["-m", "app.seed"]:
            events.append("seed")
        else:
            assert args[1:] == ["-m", "app.assistant.cli", "/app/assistant-corpus"]
            events.append("corpus")

    monkeypatch.setattr(start.subprocess, "run", run)
    monkeypatch.setattr(start.os, "execvp", lambda *_: events.append("serve"))

    assert start.main() == (0 if expected else 1)
    assert events == expected
    captured = capsys.readouterr()
    assert all(secret not in captured.out + captured.err for secret in (
        env["JWT_SECRET_KEY"], env["ASSISTANT_API_KEY"], env["DATABASE_URL"],
    ))


@pytest.mark.parametrize("digest", ["", "0" * 64])
def test_render_synthetic_mode_requires_pinned_bundle(monkeypatch, tmp_path, digest):
    environment = {
        "APP_ENV": "production",
        "DATABASE_URL": "postgresql://demo:password@db/smart_warehouse_render_demo",
        "JWT_SECRET_KEY": "unit-test-secret-long-enough-for-production",
        "PORT": "8000",
        "CORS_ORIGINS": '["https://demo.onrender.com"]',
        "GIS_CATALOG_ROOT": str(tmp_path),
        "GIS_SNAPSHOT_ID": "snapshot",
        "ASSISTANT_ENABLED": "false",
        "RENDER_DEMO_BUNDLE_URL": ASSET_BASE + "/synthetic-demo.zip",
        "RENDER_DEMO_BUNDLE_SHA256": digest,
        **{
            f"{section}_ALLOW_FIXTURE": "false"
            for section in ("FORECAST", "REPLENISHMENT", "COLD_START", "ANOMALIES", "GIS")
        },
        **{
            f"{section}_CATALOG_ROOT": str(tmp_path)
            for section in ("FORECAST", "REPLENISHMENT", "COLD_START")
        },
    }
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    calls = []
    run = object()
    monkeypatch.setattr(start, "load_seed_settings", lambda: SimpleNamespace(admin_email="demo"))
    monkeypatch.setattr(start, "mkdtemp", lambda **_: str(tmp_path))
    monkeypatch.setattr(start, "prepare_snapshot", lambda *_: calls.append("gis"))

    def bundle(url, sha, _root, _download):
        assert url == environment["RENDER_DEMO_BUNDLE_URL"] and sha == digest
        assert start.os.environ["APP_ENV"] == "production"
        calls.append("bundle")
        return tmp_path, run

    def seed(db, email, result):
        assert email == "demo" and result is run
        settings = start.Settings(_env_file=None)
        assert settings.database_url == db and settings.app_env == "integration"
        assert settings.forecast_allow_fixture and settings.anomalies_allow_fixture
        assert not settings.gis_allow_fixture
        calls.append("analytics")

    monkeypatch.setattr(start, "prepare_bundle", bundle)
    monkeypatch.setattr(start, "upgrade_demo_database", lambda _: calls.append("migration"))
    monkeypatch.setattr(start.subprocess, "run", lambda *_, **__: calls.append("seed"))
    monkeypatch.setattr(start, "seed_analytics", seed)
    monkeypatch.setattr(start.os, "execvp", lambda *_: calls.append("serve"))

    assert start.main() == (0 if digest else 1)
    assert calls == (["gis", "bundle", "migration", "seed", "analytics", "serve"] if digest else [])
