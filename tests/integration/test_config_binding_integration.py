"""Integration tests for multi-section appsettings binding."""

from pathlib import Path

import pytest
from fixtures.config_binding_samples import SAMPLE_APPSETTINGS_TOML, MessageBusConfig
from pydantic import ValidationError

from pepelats.configuration import load_configuration
from pepelats.hosting.server_config import ServerConfig
from pepelats.observability.logging_config import LoggingConfig

_EXPECTED_CHANNEL_NAMES = (
    "tasks-inbound",
    "tasks-outbound",
    "events-inbound",
    "events-outbound",
)


def _write_sample_config(directory: Path) -> None:
    (directory / "appsettings.toml").write_text(SAMPLE_APPSETTINGS_TOML, encoding="utf-8")


def test_sample_appsettings_binds_logging_host_and_message_bus(tmp_path: Path) -> None:
    _write_sample_config(tmp_path)
    loaded = load_configuration(tmp_path)

    logging = loaded.configuration.get(LoggingConfig, section="logging")
    host = loaded.configuration.get(ServerConfig, section="host")
    message_bus = loaded.configuration.get(MessageBusConfig, section="message_bus")

    assert logging.log_level == "INFO"
    assert logging.file.file_name == "worker-alpha.log"
    assert logging.overrides["App.Worker"] == "DEBUG"
    assert logging.overrides["vendor.api"] == "WARNING"
    assert host.port == 8095  # non-default; proves the file value bound
    assert [channel.name for channel in message_bus.channels] == list(_EXPECTED_CHANNEL_NAMES)
    assert len(message_bus.inbound_channels()) == 2
    assert len(message_bus.outbound_channels()) == 2


def test_logging_override_keys_stay_raw_in_section_dict(tmp_path: Path) -> None:
    _write_sample_config(tmp_path)
    loaded = load_configuration(tmp_path)

    overrides = loaded.configuration.get_section_dict("logging")["overrides"]

    assert overrides["App.Worker"] == "DEBUG"
    assert overrides["vendor.api"] == "WARNING"


def test_env_scalar_override_wins_without_breaking_channel_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_sample_config(tmp_path)
    monkeypatch.setenv("HOST__PORT", "9090")
    monkeypatch.setenv("LOGGING__LOG_LEVEL", "ERROR")

    loaded = load_configuration(tmp_path)

    host = loaded.configuration.get(ServerConfig, section="host")
    logging = loaded.configuration.get(LoggingConfig, section="logging")
    message_bus = loaded.configuration.get(MessageBusConfig, section="message_bus")

    assert host.port == 9090
    assert logging.log_level == "ERROR"
    assert [channel.name for channel in message_bus.channels] == list(_EXPECTED_CHANNEL_NAMES)


def test_env_indexed_channel_dict_binds_when_it_is_the_only_channel_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    toml = """\
environment = "Local"

[message_bus]
enabled = false
"""
    (tmp_path / "appsettings.toml").write_text(toml, encoding="utf-8")
    monkeypatch.setenv("MESSAGE_BUS__CHANNELS__0__NAME", "tasks-inbound")
    monkeypatch.setenv("MESSAGE_BUS__CHANNELS__0__CONTRACTS", '["TaskDispatched"]')
    monkeypatch.setenv("MESSAGE_BUS__CHANNELS__0__DIRECTION", "inbound")

    loaded = load_configuration(tmp_path)
    message_bus = loaded.configuration.get(MessageBusConfig, section="message_bus")

    assert len(message_bus.channels) == 1
    assert message_bus.channels[0].name == "tasks-inbound"
    assert message_bus.channels[0].contracts == ["TaskDispatched"]


def test_env_indexed_channel_override_replaces_whole_toml_channel_list(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Footgun, pinned: an env index override does NOT element-wise patch
    # channel[0]. It replaces the entire `channels` value with the indexed env
    # dict, so the existing TOML channels vanish and the lone env channel is
    # incomplete (no contracts/direction), failing validation. A future merge
    # change that silently keeps or merges the list will trip this test.
    toml = """\
environment = "Local"

[message_bus]
enabled = false

[[message_bus.channels]]
name = "tasks-inbound"
contracts = ["TaskDispatched"]
direction = "inbound"

[[message_bus.channels]]
name = "tasks-outbound"
contracts = ["TaskCompleted"]
direction = "outbound"
"""
    (tmp_path / "appsettings.toml").write_text(toml, encoding="utf-8")
    monkeypatch.setenv("MESSAGE_BUS__CHANNELS__0__NAME", "renamed-inbound")

    loaded = load_configuration(tmp_path)

    with pytest.raises(ValidationError) as exc_info:
        loaded.configuration.get(MessageBusConfig, section="message_bus")

    message = str(exc_info.value)
    assert "channels.0.contracts" in message
    assert "channels.0.direction" in message
