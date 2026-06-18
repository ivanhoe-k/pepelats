"""Smoke test for examples/starlette-basic."""

from pathlib import Path

import pytest
from examples.shared.starlette_host import build_host
from starlette.testclient import TestClient

pytestmark = pytest.mark.smoke


def test_route_resolves_every_dependency_shape(starlette_config_dir: Path) -> None:
    host = build_host(starlette_config_dir)

    with TestClient(host.app) as client:
        first = client.get("/greet/ada").json()
        second = client.get("/greet/grace").json()

    assert first["message"] == "HELLO, ADA!"
    assert first["count"] == 1
    assert second["count"] == 2
