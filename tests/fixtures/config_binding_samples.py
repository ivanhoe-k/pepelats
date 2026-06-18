"""Sample config models and appsettings used by pepelats binding tests."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from pepelats.configuration.errors import ConfigurationError

SAMPLE_APPSETTINGS_TOML = """\
environment = "Local"

[service]
service_name = "worker-alpha"
service_version = "0.1.0"

[logging]
log_level = "INFO"
sinks = ["console", "file"]
overrides = { "App.Worker" = "DEBUG", "vendor.api" = "WARNING" }

[logging.console]
json_logs = false

[logging.file]
dir = "logs"
file_name = "worker-alpha.log"

[host]
bind = "0.0.0.0"
port = 8095

[message_bus]
connection_string = ""
enabled = false

[[message_bus.channels]]
name = "tasks-inbound"
contracts = ["TaskDispatched"]
direction = "inbound"

[[message_bus.channels]]
name = "tasks-outbound"
contracts = ["TaskCompleted"]
direction = "outbound"

[[message_bus.channels]]
name = "events-inbound"
contracts = ["EventRaised"]
direction = "inbound"

[[message_bus.channels]]
name = "events-outbound"
contracts = ["EventProcessed"]
direction = "outbound"

[platform_api]
base_url = "http://localhost:5054"
"""


class ChannelBindingConfig(BaseModel):
    name: str = Field(min_length=1)
    contracts: list[str] = Field(min_length=1)
    direction: Literal["inbound", "outbound"]


class MessageBusConfig(BaseModel):
    connection_string: str = ""
    enabled: bool = False
    channels: list[ChannelBindingConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def reject_duplicate_contracts(self) -> Self:
        seen: set[str] = set()
        for channel in self.channels:
            for contract in channel.contracts:
                if contract in seen:
                    msg = f"Duplicate contract '{contract}' in message_bus.channels."
                    raise ConfigurationError(msg)
                seen.add(contract)
        return self

    def channel_for_contract(self, contract: str) -> ChannelBindingConfig:
        for channel in self.channels:
            if contract in channel.contracts:
                return channel
        msg = f"No channel configured for contract '{contract}'."
        raise ConfigurationError(msg)

    def inbound_channels(self) -> list[ChannelBindingConfig]:
        return [channel for channel in self.channels if channel.direction == "inbound"]

    def outbound_channels(self) -> list[ChannelBindingConfig]:
        return [channel for channel in self.channels if channel.direction == "outbound"]


class ConnectionEndpoint(BaseModel):
    host: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)


class RoutingTargetsConfig(BaseModel):
    endpoints: dict[str, ConnectionEndpoint] = Field(default_factory=dict)
