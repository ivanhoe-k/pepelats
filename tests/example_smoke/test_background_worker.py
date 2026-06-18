"""Smoke test for examples/background-worker."""

from pathlib import Path

import pytest
from examples.shared.background_worker_host import build_host
from starlette.testclient import TestClient

pytestmark = pytest.mark.smoke


def test_hosted_worker_runs_during_requests(background_worker_config_dir: Path) -> None:
    host = build_host(background_worker_config_dir)

    with TestClient(host.app) as client:
        first = client.get("/status").json()
        second = client.get("/status").json()

    assert first["ticks"] >= 1
    assert second["ticks"] >= first["ticks"]
