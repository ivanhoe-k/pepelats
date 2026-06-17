"""Exercises di_showcase_generic: same dependency shapes resolve on the generic host."""

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from examples.di_showcase import write_config
from examples.di_showcase_generic import build_host

pytestmark = pytest.mark.smoke


def test_route_resolves_every_dependency_shape(tmp_path: Path) -> None:
    host = build_host(write_config(tmp_path))

    with TestClient(host.app) as client:
        first = client.get("/greet/ada").json()
        second = client.get("/greet/grace").json()

    assert first["message"] == "HELLO, ADA!"
    assert first["count"] == 1
    assert second["count"] == 2
