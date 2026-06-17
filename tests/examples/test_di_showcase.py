"""Exercises di_showcase: every Inject[T] shape resolves through a real request."""

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from examples.di_showcase import build_host, write_config

pytestmark = pytest.mark.smoke


def test_route_resolves_every_dependency_shape(tmp_path: Path) -> None:
    host = build_host(write_config(tmp_path))

    with TestClient(host.app) as client:
        first = client.get("/greet/ada").json()
        second = client.get("/greet/grace").json()

    # interface impl + config (shout + punctuation) applied.
    assert first["message"] == "HELLO, ADA!"
    # concrete singleton counter persists across requests.
    assert first["count"] == 1
    assert second["count"] == 2
