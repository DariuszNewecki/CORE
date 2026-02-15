# src/features/introspection/discovery/registry.py

"""Provides functionality for the registry module."""

from __future__ import annotations


# ID: a3e2c0e1-ab3a-4384-ad7d-e65025a70789
class CapabilityRegistry:
    """
    Holds canonical capability keys and alias mapping.
    """

    def __init__(self, canonical: set[str], aliases: dict[str, str]):
        self.canonical = set(canonical)
        self.aliases = dict(aliases)

    # ID: 8910cd7d-01b5-4bf4-87ff-b37733a82532
    def resolve(self, tag: str) -> str | None:
        if tag in self.canonical:
            return tag
        return self.aliases.get(tag)
