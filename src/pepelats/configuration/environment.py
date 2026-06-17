"""Deployment environment name, injectable by type (local, staging, production)."""

from pydantic import BaseModel, Field


class Environment(BaseModel):
    name: str = Field(min_length=1)
