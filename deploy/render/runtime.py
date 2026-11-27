"""Run the API and both PostgreSQL queues in one Render web service."""

import argparse
import logging
import os
import signal
import subprocess
import sys
from collections.abc import Callable
from time import monotonic, sleep

LOGGER = logging.getLogger(__name__)
SHUTDOWN_SECONDS = 25
THREAD_LIMITS = {
    "MKL_NUM_THREADS": "1",
    "NUMBA_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
}


def shutdown_requested() -> Callable[[], bool]:
    stopping = False

    def request_stop(_signal, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    return lambda: stopping


def run_queues() -> int:
    # Keep app imports and model libraries out of the supervisor process.
    stopping = shutdown_requested()
    from app.anomalies import operational_worker
    from app.core.config import get_settings
    from app.db.session import get_engine
    from app.order_analytics import worker as order_worker

    try:
        settings = get_settings()
        engine = get_engine(settings.database_url)
    except Exception:
        LOGGER.error("Render B2B queue configuration unavailable")
        return 1

    print("Render B2B queues started.", flush=True)
    queues = (
        ("Order analytics", order_worker.run_once),
        ("Operational anomaly", operational_worker.run_once),
    )
    while not stopping():
        worked = False
        for name, run_once in queues:
            if stopping():
                break
            try:
                worked = run_once(engine, settings) or worked
            except Exception:
                LOGGER.warning("%s worker iteration failed", name)
        if not worked and not stopping():
            sleep(2)
    return 0


def stop_children(children: dict[str, subprocess.Popen]) -> None:
    deadline = monotonic() + SHUTDOWN_SECONDS
    for child in children.values():
        if child.poll() is None:
            child.terminate()
    for child in children.values():
        try:
            child.wait(timeout=max(0, deadline - monotonic()))
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()


def serve(port: int) -> int:
    stopping = shutdown_requested()
    children: dict[str, subprocess.Popen] = {}
    try:
        children["API"] = subprocess.Popen([
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", "0.0.0.0", "--port", str(port),
        ])
        if stopping():
            return 0
        children["B2B queue worker"] = subprocess.Popen(
            [sys.executable, "-m", "deploy.render.runtime", "--queues"],
            env=os.environ | THREAD_LIMITS,
        )
        while not stopping():
            for name, child in children.items():
                if (exit_code := child.poll()) is not None:
                    print(f"Render demo {name} exited ({exit_code}).", file=sys.stderr)
                    return 1
            sleep(0.2)
    except OSError:
        print("Render demo runtime failed to start a child process.", file=sys.stderr)
        return 1
    finally:
        stop_children(children)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--port", type=int)
    mode.add_argument("--queues", action="store_true")
    args = parser.parse_args()
    raise SystemExit(run_queues() if args.queues else serve(args.port))
