# src/api/cli/__init__.py

"""api.cli — client surface for CLI consumers of the CORE API (ADR-054)."""

from __future__ import annotations

from api.cli.client import CoreApiClient


__all__ = ["CoreApiClient"]
