# src/shared/legacy_models.py
"""
Pydantic models for parsing legacy YAML configuration files during migration.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


# ID: 54bbf6eb-5417-4d45-8aea-04f1932cae87
class LegacyCliCommand(BaseModel):
    """Represents a single command from the legacy cli_registry.yaml."""

    name: str
    module: str
    entrypoint: str
    summary: str | None = None
    category: str | None = None


# ID: 6686610f-46bc-4eee-9cb1-5301b16276d7
class LegacyCliRegistry(BaseModel):
    """Represents the top-level structure of the legacy cli_registry.yaml."""

    commands: list[LegacyCliCommand]


# ID: 644ea3cb-f501-4017-919f-23270e114839
class LegacyLlmResource(BaseModel):
    """Represents a single resource from the legacy resource_manifest.yaml."""

    name: str
    provided_capabilities: list[str] = Field(default_factory=list)
    env_prefix: str
    performance_metadata: dict | None = None


# ID: 41b53390-8b31-4ed7-a01d-769b9e669308
class LegacyResourceManifest(BaseModel):
    """Represents the top-level structure of the legacy resource_manifest.yaml."""

    llm_resources: list[LegacyLlmResource]


# ID: 13914243-a1b0-47fd-bbfc-b415540d5cbe
class LegacyCognitiveRole(BaseModel):
    """Represents a single role from the legacy cognitive_roles.yaml."""

    role: str
    description: str | None = None
    assigned_resource: str | None = None
    required_capabilities: list[str] = Field(default_factory=list)


# ID: 9bf273ce-d632-4f7d-ac3a-833c51d4cda7
class LegacyCognitiveRoles(BaseModel):
    """Represents the top-level structure of the legacy cognitive_roles.yaml."""

    cognitive_roles: list[LegacyCognitiveRole]
