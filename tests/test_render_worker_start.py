import os
import runpy
import subprocess
import sys
import time
from pathlib import Path

import pytest
import sqlalchemy
import yaml
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from deploy.render import integrated, start

ROOT = Path(__file__).resolve().parents[1]
DATABASE = "postgresql://demo:mock-password@db/smart_warehouse_render_demo"
BUNDLE_URL = "https://github.com/example/demo/releases/download/verified/bundle.zip"
BUNDLE_SHA = "8" * 64


def test_render_workers_share_the_free_api_service():
    blueprint = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    assert all(service["type"] == "web" for service in blueprint["services"])
    api, = [service for service in blueprint["services"] if service["runtime"] == "docker"]
    assert api["plan"] == "free"
    assert api["dockerCommand"] == "python /app/render-start.py"
    env = {item["key"]: item for item in api["envVars"]}
    assert env["DATABASE_URL"]["fromDatabase"]["name"] == blueprint["databases"][0]["name"]
    assert env["INSTALL_ANOMALY_DEPENDENCIES"]["value"] == "1"
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY deploy/render/runtime.py ./deploy/render/runtime.py" in dockerfile


@pytest.fixture
def worker_environment(monkeypatch):
    monkeypatch.chdir(ROOT)
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setenv("DATABASE_URL", DATABASE)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-worker-secret-with-at-least-32-characters")
    for key in ("PORT", "CORS_ORIGINS", "RENDER_DEMO_BUNDLE_URL", "RENDER_DEMO_BUNDLE_SHA256"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_kw: pytest.fail("worker ran setup"))


def run_worker_script(monkeypatch, worker):
    monkeypatch.setattr(sys, "argv", [start.__file__, "--worker", worker])
    with pytest.raises(SystemExit) as exit_status:
        runpy.run_path(start.__file__, run_name="__main__")
    return exit_status.value.code


@pytest.fixture
def schema_database(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'schema.db').as_posix()}")
    head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()

    def migrate():
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
            connection.execute(text("INSERT INTO alembic_version VALUES (:head)"), {"head": head})

    def connect(database_url, **kwargs):
        assert database_url == DATABASE.replace("postgresql://", "postgresql+psycopg://")
        assert kwargs["connect_args"]["connect_timeout"] > 0
        return engine

    monkeypatch.setattr(sqlalchemy, "create_engine", connect)
    yield migrate
    engine.dispose()


def test_order_worker_executes_with_verified_catalog_after_schema_head(
    monkeypatch, tmp_path, worker_environment, schema_database,
):
    monkeypatch.setenv("RENDER_DEMO_BUNDLE_URL", BUNDLE_URL)
    monkeypatch.setenv("RENDER_DEMO_BUNDLE_SHA256", BUNDLE_SHA)
    catalog = tmp_path / "verified-catalogs"
    events = []

    def prepare(url, checksum, root, download):
        assert (url, checksum) == (BUNDLE_URL, BUNDLE_SHA)
        assert root.is_dir() and callable(download)
        events.append("verified")
        return catalog, object()

    def wait(_seconds):
        events.append("schema")
        schema_database()

    def launch(executable, argv):
        assert argv == [executable, "-m", "app.order_analytics.worker"]
        assert os.environ["APP_ENV"] == "integration"
        assert os.environ["FORECAST_CATALOG_ROOT"] == str(catalog / "forecast")
        assert os.environ["REPLENISHMENT_CATALOG_ROOT"] == str(catalog / "replenishment")
        assert os.environ["FORECAST_ALLOW_FIXTURE"] == "true"
        assert os.environ["REPLENISHMENT_ALLOW_FIXTURE"] == "true"
        assert sorted(events) == ["schema", "verified"]
        events.append("launched")

    monkeypatch.setattr(integrated, "prepare_bundle", prepare)
    monkeypatch.setattr(time, "sleep", wait)
    monkeypatch.setattr(os, "execv", launch)
    assert run_worker_script(monkeypatch, "order-analytics") == 0
    assert events[-1] == "launched"


def test_anomaly_worker_executes_with_no_model_or_demo_bundle(
    monkeypatch, worker_environment, schema_database,
):
    schema_database()
    monkeypatch.setattr(integrated, "prepare_bundle", lambda *_: pytest.fail("loaded catalog"))
    launched = []
    monkeypatch.setattr(os, "execv", lambda _, argv: launched.append(argv[1:]))
    assert run_worker_script(monkeypatch, "operational-anomaly") == 0
    assert launched == [["-m", "app.anomalies.operational_worker"]]


@pytest.mark.parametrize("worker", ["order-analytics", "operational-anomaly"])
def test_workers_reject_other_databases_without_exposing_credentials(
    monkeypatch, capsys, worker_environment, worker,
):
    monkeypatch.setenv("DATABASE_URL", DATABASE.replace("render_demo", "different_db"))
    monkeypatch.setattr(sqlalchemy, "create_engine", lambda *_a, **_kw: pytest.fail("connected"))
    monkeypatch.setattr(os, "execv", lambda *_: pytest.fail("started worker"))
    assert run_worker_script(monkeypatch, worker) == 1
    errors = capsys.readouterr().err
    assert "worker" in errors.lower()
    assert "mock-password" not in errors


def test_order_worker_requires_a_complete_catalog_pin(monkeypatch, worker_environment, capsys):
    monkeypatch.setenv("RENDER_DEMO_BUNDLE_URL", BUNDLE_URL)
    monkeypatch.setattr(integrated, "prepare_bundle", lambda *_: pytest.fail("downloaded asset"))
    monkeypatch.setattr(os, "execv", lambda *_: pytest.fail("started worker"))
    assert run_worker_script(monkeypatch, "order-analytics") == 1
    assert "bundle" in capsys.readouterr().err.lower()


def test_worker_waits_for_schema_during_a_slow_parallel_rollout(
    monkeypatch, capsys, worker_environment, schema_database,
):
    schema_database()
    engine = sqlalchemy.create_engine(
        DATABASE.replace("postgresql://", "postgresql+psycopg://"),
        connect_args={"connect_timeout": 3},
    )
    real_connect = engine.connect
    attempts = []

    def connect():
        attempts.append("connect")
        if len(attempts) <= 12:
            raise OperationalError(None, None, ValueError("mock-password"))
        return real_connect()

    launched = []
    monkeypatch.setattr(engine, "connect", connect)
    monkeypatch.setattr(time, "sleep", lambda _: None)
    monkeypatch.setattr(os, "execv", lambda _, argv: launched.append(argv[1:]))

    assert run_worker_script(monkeypatch, "operational-anomaly") == 0
    assert len(attempts) == 13
    assert launched == [["-m", "app.anomalies.operational_worker"]]
    errors = capsys.readouterr().err
    assert "schema" in errors.lower()
    assert "mock-password" not in errors
