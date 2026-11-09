"""Start a dedicated Render demo with a verified public road snapshot."""

import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, build_opener

from alembic.config import Config
from sqlalchemy.engine import make_url

from alembic import command
from app.core.config import Settings
from app.gis.catalog import MANIFEST_LIMIT, SNAPSHOT_ID, checked_path, verify_snapshot
from app.gis.schemas import GRAPH_LIMIT
from app.seed import load_seed_settings

DEMO_DATABASE = "smart_warehouse_render_demo"


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
        load_seed_settings()

        stage = "verify GIS snapshot"
        prepare_snapshot(
            settings.gis_catalog_root,
            settings.gis_snapshot_id,
            os.environ.get("GIS_RELEASE_ASSET_BASE", ""),
        )
        stage = "upgrade the demo database"
        upgrade_demo_database(settings.database_url)
        stage = "seed the demo database"
        subprocess.run([sys.executable, "-m", "app.seed"], check=True)
        stage = "start the API"
        os.execvp("uvicorn", ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(port)])
    except Exception:
        print(f"Render demo startup failed: {stage}.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
