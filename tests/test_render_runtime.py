from subprocess import TimeoutExpired
from threading import Event
from types import SimpleNamespace

import pytest


def test_combined_worker_runs_both_queues_with_one_engine(monkeypatch, caplog):
    from app.anomalies import operational_worker
    from app.core import config
    from app.db import session
    from app.order_analytics import worker
    from deploy.render import runtime

    stop = Event()
    settings = SimpleNamespace(database_url="test-db")
    engine = object()
    calls = []

    def engine_for(url):
        assert url == settings.database_url
        calls.append("engine")
        return engine

    def order(shared_engine, shared_settings):
        assert (shared_engine, shared_settings) == (engine, settings)
        calls.append("order")
        if calls.count("order") == 1:
            raise ValueError("sensitive error detail")
        return False

    def anomaly(shared_engine, shared_settings):
        assert (shared_engine, shared_settings) == (engine, settings)
        calls.append("anomaly")
        if calls.count("anomaly") == 2:
            stop.set()
        return True

    monkeypatch.setattr(config, "get_settings", lambda: settings)
    monkeypatch.setattr(session, "get_engine", engine_for)
    monkeypatch.setattr(worker, "run_once", order)
    monkeypatch.setattr(operational_worker, "run_once", anomaly)
    monkeypatch.setattr(runtime, "shutdown_requested", lambda: stop.is_set)

    assert runtime.run_queues() == 0
    assert calls == ["engine", "order", "anomaly", "order", "anomaly"]
    assert "Order analytics worker iteration failed" in caplog.text
    assert "sensitive error detail" not in caplog.text


@pytest.mark.parametrize("scenario", ["shutdown", "worker_exit", "start_failure", "timeout"])
def test_render_supervisor_terminates_and_reaps_children(monkeypatch, capsys, scenario):
    from deploy.render import runtime

    stop = Event()
    commands = []
    events = []

    class Child:
        def __init__(self, name, exit_code=None):
            self.name, self.exit_code = name, exit_code

        def poll(self):
            return self.exit_code

        def terminate(self):
            events.append((self.name, "terminate"))
            if scenario != "timeout":
                self.exit_code = 0

        def kill(self):
            events.append((self.name, "kill"))
            self.exit_code = -9

        def wait(self, timeout=None):
            events.append((self.name, "wait"))
            if self.exit_code is None:
                raise TimeoutExpired(self.name, timeout)
            return self.exit_code

    def launch(args, **kwargs):
        commands.append(args[1:])
        if len(commands) == 1:
            return Child("API")
        assert kwargs["env"]["OPENBLAS_NUM_THREADS"] == "1"
        if scenario == "start_failure":
            raise OSError("sensitive startup detail")
        if scenario == "worker_exit":
            return Child("worker", 0)
        stop.set()
        return Child("worker")

    monkeypatch.setattr(runtime, "shutdown_requested", lambda: stop.is_set)
    monkeypatch.setattr(runtime.subprocess, "Popen", launch)

    assert runtime.serve(8123) == (1 if scenario in {"worker_exit", "start_failure"} else 0)
    assert commands == [
        ["-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8123"],
        ["-m", "deploy.render.runtime", "--queues"],
    ]
    assert ("API", "terminate") in events and ("API", "wait") in events
    if scenario in {"shutdown", "timeout"}:
        assert events[:2] == [("API", "terminate"), ("worker", "terminate")]
    if scenario != "start_failure":
        assert ("worker", "wait") in events
    if scenario == "timeout":
        assert ("API", "kill") in events and ("worker", "kill") in events
    error = capsys.readouterr().err
    if scenario == "worker_exit":
        assert "B2B queue worker exited" in error
    assert "sensitive startup detail" not in error
