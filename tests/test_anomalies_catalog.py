import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from app.anomalies.catalog import publish_run, verify_run
from app.anomalies.scoring import fit_and_score
from tests.anomalies_helpers import snapshot


@pytest.fixture(scope="module")
def run():
    snap = snapshot(holdout_offset=1000).model_copy(
        update={
            "source_hashes": {
                name: "b" * 64
                for name in ("source", "records.jsonl", "observations.jsonl", "quality.json")
            }
        }
    )
    return fit_and_score(snap)


def test_published_catalog_is_verified_and_hides_raw_ids(tmp_path, run):
    run_id = publish_run(run, tmp_path)
    verified = verify_run(tmp_path, run_id)
    assert verified.run_id == run_id
    assert verified.payload.dataset_class == "fixture"
    assert verified.payload.alerts
    raw = (tmp_path / f"{run_id}.json").read_text(encoding="utf-8")
    assert "event_id" not in raw
    assert '"labels"' not in raw
    assert "train-" not in raw
    assert verified.payload.alerts[0].explanation.state == "available"


def test_catalog_rejects_changed_bytes(tmp_path, run):
    run_id = publish_run(run, tmp_path)
    path = tmp_path / f"{run_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["threshold"] += 1
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        verify_run(tmp_path, run_id)


def test_competing_publishers_reuse_same_immutable_result(tmp_path, run):
    with ThreadPoolExecutor(max_workers=2) as executor:
        ids = list(executor.map(lambda _: publish_run(run, tmp_path), range(2)))
    assert ids[0] == ids[1]
    assert verify_run(tmp_path, ids[0]).run_id == ids[0]
    assert len(list(tmp_path.glob("arv1-*.json"))) == 1


def test_rejects_invalid_id_before_read(tmp_path):
    with pytest.raises(ValueError):
        verify_run(tmp_path, "../outside")


def test_publisher_rejects_mutated_scores_and_threshold(tmp_path, run):
    with pytest.raises(ValueError):
        publish_run(replace(run, threshold=0.0), tmp_path)
    with pytest.raises(ValueError):
        publish_run(replace(run, scores=(0.0,) + run.scores[1:]), tmp_path)


def test_verifier_rejects_resealed_bad_metrics(tmp_path, run):
    import hashlib

    from app.analytics.export import canonical_json

    run_id = publish_run(run, tmp_path)
    path = tmp_path / f"{run_id}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["metrics"]["precision"] = 2.0
    body = canonical_json(payload)
    bad_id = "arv1-" + hashlib.sha256(body).hexdigest()
    (tmp_path / f"{bad_id}.json").write_bytes(body)
    with pytest.raises(ValueError):
        verify_run(tmp_path, bad_id)


def test_fixture_settings_are_forbidden_outside_test_and_integration():
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            database_url="postgresql+psycopg://user:pass@localhost/db",
            jwt_secret_key="x" * 40,
            anomalies_allow_fixture=True,
            _env_file=None,
        )
    assert Settings(
        app_env="test",
        database_url="sqlite://",
        jwt_secret_key="test",
        anomalies_allow_fixture=True,
        _env_file=None,
    ).anomalies_allow_fixture


def test_cli_requires_actor_id_and_explicit_fixture(capsys):
    from app.anomalies.cli import main

    with pytest.raises(SystemExit):
        main(
            ["import-run", "--run-id", "arv1-" + "a" * 64, "--catalog-root", ".", "--allow-fixture"]
        )
    with pytest.raises(SystemExit):
        main(
            ["import-run", "--run-id", "arv1-" + "a" * 64, "--catalog-root", ".", "--actor-id", "1"]
        )
    assert capsys.readouterr().err


def test_catalog_root_without_resolvable_home_keeps_path_guards(tmp_path, monkeypatch):
    from pathlib import Path

    from app.anomalies.catalog import _root

    def unavailable_home(cls):
        raise RuntimeError("home is unavailable")

    monkeypatch.setattr(Path, "home", classmethod(unavailable_home))
    assert _root(tmp_path) == tmp_path.resolve()
    with pytest.raises(ValueError):
        _root(Path(tmp_path.anchor))
