"""Fixtures de integração: worker Celery real em subprocesso contra Redis real."""
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXECUTOR_DIR = ROOT / "executor"

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/15")
QUEUE = os.environ.get("EXECUTOR_QUEUE", "executor-tasks")
SEARX_URL = "http://127.0.0.1:59999"  # porta fechada de propósito


def _redis_up(url: str) -> bool:
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 6379
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def _make_client_celery():
    """App Celery do lado cliente, apontando para o mesmo broker/fila do worker."""
    from celery import Celery

    app = Celery("integration-client", broker=REDIS_URL, backend=REDIS_URL)
    app.conf.task_default_queue = QUEUE
    return app


@pytest.fixture(scope="session")
def celery_client():
    if not _redis_up(REDIS_URL):
        pytest.skip(f"Redis indisponível em {REDIS_URL}; suba um para rodar a integração")
    return _make_client_celery()


@pytest.fixture(scope="session")
def worker_process(celery_client):
    """Sobe o executor exatamente como em produção: `celery -A worker worker`.

    O subprocesso roda com cwd=executor/, então `from settings import settings`
    resolve para o settings do executor (e não o do orchestrator).
    """
    env = {
        **os.environ,
        "REDIS_URL": REDIS_URL,
        "EXECUTOR_QUEUE": QUEUE,
        "SEARX_URL": SEARX_URL,
    }
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "celery", "-A", "worker", "worker",
            "--pool=solo", "--concurrency=1", "--loglevel=warning",
        ],
        cwd=str(EXECUTOR_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # Espera o worker responder ao ping (até ~30s)
    deadline = time.time() + 30
    ready = False
    while time.time() < deadline and proc.poll() is None:
        try:
            if celery_client.control.inspect(timeout=1).ping():
                ready = True
                break
        except Exception:
            pass
        time.sleep(0.5)

    if not ready:
        saida = ""
        if proc.poll() is not None:
            saida = proc.stdout.read().decode(errors="replace")[-2000:]
        proc.kill()
        raise RuntimeError(f"worker não ficou pronto.\n{saida}")

    yield proc

    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
