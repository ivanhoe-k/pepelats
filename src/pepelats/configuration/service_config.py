"""Service identity (name, version, instance id) stamped on logs and traces."""

from pydantic import BaseModel, Field


class ServiceConfig(BaseModel):
    service_name: str = Field(min_length=1)
    service_version: str = Field(min_length=1)
    instance_id: str = Field(min_length=1)
