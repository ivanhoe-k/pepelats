"""Smoke test for examples/observability."""

from pathlib import Path

import pytest
from examples.shared.observability_host import build_host
from starlette.testclient import TestClient

pytestmark = pytest.mark.smoke


def test_hello_route_returns_ok(observability_config_dir: Path) -> None:
    host = build_host(observability_config_dir)

    with TestClient(host.app) as client:
        response = client.get("/hello")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
