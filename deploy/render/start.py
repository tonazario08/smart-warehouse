"""Prepare the Render demo and start its API and B2B queues."""

import argparse
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory, mkdtemp
from time import sleep
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, build_opener

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

from alembic import command
from app.assistant.provider import ModelProvider
from app.core.config import Settings
from app.gis.catalog import MANIFEST_LIMIT, SNAPSHOT_ID, checked_path, verify_snapshot
from app.gis.schemas import GRAPH_LIMIT
from app.seed import load_seed_settings
from deploy.render.integrated import prepare_bundle, seed_analytics

DEMO_DATABASE = "smart_warehouse_render_demo"
WORKER_MODULES = {
    "order-analytics": "app.order_analytics.worker",
    "operational-anomaly": "app.anomalies.operational_worker",
}


def demo_database_url(raw: str) -> str:
    if raw.startswith("postgresql://"):
        raw = "postgresql+psycopg://" + raw.removeprefix("postgresql://")
    url = make_url(raw)
    if (
        url.drivername != "postgresql+psycopg" or url.database != DEMO_DATABASE
        or "dbname" in url.query
    ):
        raise ValueError("Render requires the dedicated demo database")
    return raw


def upgrade_demo_database(database_url: str) -> None:
    config = Config("alembic.ini")
    # ConfigParser interpolates percent signs. Keep the process environment URL untouched.
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(config, "head")


class ReleaseRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        location = urlsplit(newurl)
        if location.scheme != "https" or location.netloc not in {
            "github.com", "release-assets.githubusercontent.com",
        }:
            raise ValueError("Unexpected release asset origin")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


open_release_asset = build_opener(ReleaseRedirect()).open


def download_asset(url: str, target: Path, limit: int) -> None:
    with open_release_asset(url, timeout=30) as response, target.open("xb") as stream:
        size = 0
        while chunk := response.read(64 * 1024):
            size += len(chunk)
            if size > limit:
                raise ValueError("Release asset exceeds its size limit")
            stream.write(chunk)


def prepare_snapshot(root: Path, snapshot_id: str, asset_base: str) -> None:
    if not SNAPSHOT_ID.fullmatch(snapshot_id):
        raise ValueError("Invalid GIS snapshot identifier")
    root = checked_path(root, directory=True, create=True)
    target = root / snapshot_id
    if target.exists():
        verify_snapshot(root, snapshot_id, datetime.now(UTC))
        return

    asset_base = asset_base.rstrip("/")
    release = urlsplit(asset_base)
    parts = release.path.strip("/").split("/")
    if (
        release.scheme != "https" or release.netloc != "github.com"
        or len(parts) != 5 or parts[2:4] != ["releases", "download"]
        or release.query or release.fragment
    ):
        raise ValueError("Expected an HTTPS GitHub Release asset base URL")
    root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=root) as staging:
        stage_root = Path(staging)
        folder = stage_root / snapshot_id
        folder.mkdir()
        for name, limit in (("manifest.json", MANIFEST_LIMIT), ("graph.json", GRAPH_LIMIT)):
            download_asset(f"{asset_base}/{name}", folder / name, limit)
        verify_snapshot(stage_root, snapshot_id, datetime.now(UTC))
        folder.rename(target)


def wait_for_database_schema(database_url: str) -> None:
    expected = set(ScriptDirectory.from_config(Config("alembic.ini")).get_heads())
    if not expected:
        raise RuntimeError("Render worker image has no database migrations")
    engine = create_engine(
        database_url,
        connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"},
        poolclass=NullPool,
        hide_parameters=True,
    )
    waiting = False
    try:
        while True:
            try:
                with engine.connect() as connection:
                    current = set(MigrationContext.configure(connection).get_current_heads())
                    if current == expected:
                        return
            except SQLAlchemyError:
                pass  # Readiness errors can include credentials and connection details.
            if not waiting:
                print("Render demo worker waiting for the database schema.", file=sys.stderr)
                waiting = True
            # Blueprint services can start before the API has deployed and migrated the database.
            sleep(5)
    finally:
        engine.dispose()


def start_worker(worker: str) -> int:
    stage = "validate environment"
    try:
        os.environ["DATABASE_URL"] = demo_database_url(os.environ["DATABASE_URL"])
        settings = Settings(_env_file=None)
        if settings.app_env != "production":
            raise ValueError("Invalid Render worker configuration")

        if worker == "order-analytics":
            stage = "verify synthetic bundle"
            bundle_url = os.environ.get("RENDER_DEMO_BUNDLE_URL", "")
            bundle_sha = os.environ.get("RENDER_DEMO_BUNDLE_SHA256", "")
            if not bundle_url or not bundle_sha:
                raise ValueError("Order analytics requires a pinned bundle")
            catalogs, _ = prepare_bundle(
                bundle_url, bundle_sha, Path(mkdtemp(prefix="render-order-")), download_asset
            )
            os.environ.update({
                "APP_ENV": "integration",
                "FORECAST_CATALOG_ROOT": str(catalogs / "forecast"),
                "REPLENISHMENT_CATALOG_ROOT": str(catalogs / "replenishment"),
                "FORECAST_ALLOW_FIXTURE": "true",
                "REPLENISHMENT_ALLOW_FIXTURE": "true",
            })

        stage = "wait for the demo database schema"
        wait_for_database_schema(settings.database_url)
        stage = "start the worker"
        os.execv(sys.executable, [sys.executable, "-m", WORKER_MODULES[worker]])
    except Exception:
        print(f"Render demo worker startup failed: {stage}.", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    stage = "validate environment"
    try:
        os.environ["DATABASE_URL"] = demo_database_url(os.environ["DATABASE_URL"])
        settings = Settings(_env_file=None)
        port = int(os.environ["PORT"])
        if (
            settings.app_env != "production" or not 1 <= port <= 65535
            or not settings.gis_catalog_root or not settings.gis_snapshot_id
            or len(settings.cors_origins) != 1
        ):
            raise ValueError("Invalid Render demo configuration")
        origin = urlsplit(settings.cors_origins[0])
        if (
            not origin.hostname or not origin.hostname.endswith(".onrender.com")
            or settings.cors_origins[0] != f"https://{origin.hostname}"
        ):
            raise ValueError("Expected one HTTPS Render frontend origin")
        seed = load_seed_settings()
        bundle_url = os.environ.get("RENDER_DEMO_BUNDLE_URL", "")
        bundle_sha = os.environ.get("RENDER_DEMO_BUNDLE_SHA256", "")
        if bool(bundle_url) != bool(bundle_sha):
            raise ValueError("Synthetic bundle requires both URL and checksum")
        if settings.assistant_enabled:
            stage = "validate assistant provider"
            if urlsplit(settings.assistant_base_url).scheme != "https":
                raise ValueError("Render requires an HTTPS assistant provider")
            ModelProvider(settings).validate_configuration()

        stage = "verify GIS snapshot"
        prepare_snapshot(
            settings.gis_catalog_root,
            settings.gis_snapshot_id,
            os.environ.get("GIS_RELEASE_ASSET_BASE", ""),
        )
        anomaly_run = None
        if bundle_url:
            stage = "verify synthetic bundle"
            catalogs, anomaly_run = prepare_bundle(
                bundle_url, bundle_sha, Path(mkdtemp(prefix="render-integrated-")), download_asset
            )
            os.environ.update({
                "APP_ENV": "integration",
                "FORECAST_CATALOG_ROOT": str(catalogs / "forecast"),
                "REPLENISHMENT_CATALOG_ROOT": str(catalogs / "replenishment"),
                "COLD_START_CATALOG_ROOT": str(catalogs / "cold-start"),
                "FORECAST_ALLOW_FIXTURE": "true",
                "REPLENISHMENT_ALLOW_FIXTURE": "true",
                "COLD_START_ALLOW_FIXTURE": "true",
                "ANOMALIES_ALLOW_FIXTURE": "true",
            })
        stage = "upgrade the demo database"
        upgrade_demo_database(settings.database_url)
        stage = "seed the demo database"
        subprocess.run([sys.executable, "-m", "app.seed"], check=True)
        if anomaly_run is not None:
            stage = "initialize synthetic demo data"
            seed_analytics(settings.database_url, seed.admin_email, anomaly_run)
        if settings.assistant_enabled:
            stage = "import assistant corpus"
            subprocess.run(
                [sys.executable, "-m", "app.assistant.cli", "/app/assistant-corpus"], check=True
            )
        stage = "start the API and B2B queues"
        os.execv(sys.executable, [
            sys.executable, "-m", "deploy.render.runtime", "--port", str(port),
        ])
    except Exception:
        print(f"Render demo startup failed: {stage}.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", choices=WORKER_MODULES)
    args = parser.parse_args()
    raise SystemExit(start_worker(args.worker) if args.worker else main())
