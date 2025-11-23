# src/shared/models/capability_models.py
"""
Defines the Pydantic/dataclass models for representing capabilities and
their metadata throughout the system.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
# ID: 6c0a8c58-e1f0-4182-9857-1eb3dfa0410e
class CapabilityMeta:
    """
    A dataclass to hold the metadata for a single capability, discovered
    either from manifest files or source code tags.
    """

    key: str
    domain: str | None = None
    owner: str | None = None
