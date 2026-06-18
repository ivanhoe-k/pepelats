from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def starlette_config_dir() -> Path:
    return EXAMPLES / "starlette-basic"


@pytest.fixture
def fastapi_config_dir() -> Path:
    return EXAMPLES / "fastapi-basic"


@pytest.fixture
def background_worker_config_dir() -> Path:
    return EXAMPLES / "background-worker"


@pytest.fixture
def observability_config_dir() -> Path:
    return EXAMPLES / "observability"
