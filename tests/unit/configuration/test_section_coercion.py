"""Unit tests for schema-aware section binding."""

import pytest
from fixtures.config_binding_samples import (
    ChannelBindingConfig,
    MessageBusConfig,
    RoutingTargetsConfig,
)
from pydantic import BaseModel

from pepelats.configuration.errors import ConfigurationError
from pepelats.configuration.section_coercion import (
    coerce_section_data_for_model,
    read_section_field,
    validate_section,
)
from pepelats.hosting.host_config import HostConfig
from pepelats.hosting.server_config import ServerConfig
from pepelats.observability.logging_config import LoggingConfig

_TASKS_INBOUND = {
    "NAME": "tasks-inbound",
    "CONTRACTS": ["TaskDispatched"],
    "DIRECTION": "inbound",
}
_TASKS_OUTBOUND = {
    "NAME": "tasks-outbound",
    "CONTRACTS": ["TaskCompleted"],
    "DIRECTION": "outbound",
}
_EVENTS_INBOUND = {
    "NAME": "events-inbound",
    "CONTRACTS": ["EventRaised"],
    "DIRECTION": "inbound",
}
_EVENTS_OUTBOUND = {
    "NAME": "events-outbound",
    "CONTRACTS": ["EventProcessed"],
    "DIRECTION": "outbound",
}


def test_host_section_binds_env_style_uppercase_keys() -> None:
    server = validate_section(ServerConfig, {"PORT": 7001, "BIND": "127.0.0.1"})

    assert server.port == 7001
    assert server.bind == "127.0.0.1"


def test_read_section_field_binds_uppercase_env_style_key() -> None:
    timeout = read_section_field(
        {"SHUTDOWN_TIMEOUT_SECONDS": "15.5"},
        HostConfig,
        "shutdown_timeout_seconds",
        default=10.0,
    )

    assert timeout == 15.5


def test_read_section_field_returns_default_when_field_is_missing() -> None:
    assert (
        read_section_field({}, HostConfig, "shutdown_timeout_seconds", default=10.0)
        == 10.0
    )


def test_logging_section_preserves_mixed_case_logger_override_keys() -> None:
    logging = validate_section(
        LoggingConfig,
        {
            # Lowercase level + True json_logs differ from defaults, so the nested
            # structural keys must actually fold for these assertions to hold.
            "LOG_LEVEL": "warning",
            "SINKS": ["console", "file"],
            "CONSOLE": {"JSON_LOGS": True},
            "FILE": {"DIR": "logs", "FILE_NAME": "worker-alpha.log"},
            "OVERRIDES": {
                "App.Worker": "DEBUG",
                "vendor.api": "WARNING",
            },
        },
    )

    assert logging.log_level == "WARNING"
    assert logging.console.json_logs is True
    assert logging.file.file_name == "worker-alpha.log"
    assert logging.overrides == {
        "App.Worker": "DEBUG",
        "vendor.api": "WARNING",
    }


def test_message_bus_binds_channel_matrix_from_uppercase_list_items() -> None:
    config = validate_section(
        MessageBusConfig,
        {
            "CONNECTION_STRING": "",
            "ENABLED": False,
            "CHANNELS": [
                _TASKS_INBOUND,
                _TASKS_OUTBOUND,
                _EVENTS_INBOUND,
                _EVENTS_OUTBOUND,
            ],
        },
    )

    assert len(config.channels) == 4
    assert config.inbound_channels()[0].name == "tasks-inbound"
    assert config.inbound_channels()[1].name == "events-inbound"
    assert config.outbound_channels()[0].name == "tasks-outbound"
    assert config.channel_for_contract("EventProcessed").name == "events-outbound"


def test_message_bus_channel_list_preserves_contract_casing() -> None:
    config = validate_section(
        MessageBusConfig,
        {"CHANNELS": [_TASKS_INBOUND]},
    )

    assert config.channels[0].contracts == ["TaskDispatched"]


def test_message_bus_converts_indexed_dict_from_env_into_channel_list() -> None:
    config = validate_section(
        MessageBusConfig,
        {
            "CHANNELS": {
                "0": _TASKS_INBOUND,
                "1": _TASKS_OUTBOUND,
            }
        },
    )

    assert [channel.name for channel in config.channels] == [
        "tasks-inbound",
        "tasks-outbound",
    ]


def test_message_bus_optional_channel_list_still_coerces_item_fields() -> None:
    class _BusWithOptionalChannels(BaseModel):
        channels: list[ChannelBindingConfig] | None = None

    config = validate_section(
        _BusWithOptionalChannels,
        {"CHANNELS": [_TASKS_INBOUND]},
    )

    assert config.channels is not None
    assert config.channels[0].direction == "inbound"


def test_routing_targets_coerces_inner_fields_but_preserves_endpoint_names() -> None:
    config = validate_section(
        RoutingTargetsConfig,
        {
            "ENDPOINTS": {
                "PrimaryStore": {"HOST": "db.internal", "PORT": 5432},
                "ReadReplica": {"HOST": "replica.internal", "PORT": 5433},
            }
        },
    )

    assert config.endpoints["PrimaryStore"].host == "db.internal"
    assert config.endpoints["ReadReplica"].port == 5433


def test_scalar_lists_inside_channel_items_are_not_coerced() -> None:
    coerced = coerce_section_data_for_model(
        {"CHANNELS": [{"NAME": "tasks-inbound", "CONTRACTS": ["TaskDispatched"], "DIRECTION": "inbound"}]},
        MessageBusConfig,
    )

    assert coerced["channels"][0]["contracts"] == ["TaskDispatched"]


def test_message_bus_rejects_same_contract_on_two_channels() -> None:
    duplicate = {**_TASKS_OUTBOUND, "CONTRACTS": ["TaskDispatched"]}

    with pytest.raises(ConfigurationError, match="Duplicate contract 'TaskDispatched'"):
        validate_section(
            MessageBusConfig,
            {"CHANNELS": [_TASKS_INBOUND, duplicate]},
        )


def test_channel_for_contract_raises_when_no_channel_carries_it() -> None:
    config = validate_section(MessageBusConfig, {"CHANNELS": [_TASKS_INBOUND]})

    with pytest.raises(ConfigurationError, match="No channel configured for contract 'Unknown'"):
        config.channel_for_contract("Unknown")
