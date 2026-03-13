# src/shared/protocols/typer_protocols.py
"""Structural protocols for Typer CLI introspection.

Single source of truth for TyperCommandLike, TyperGroupLike, TyperAppLike.
Consumed by:
  - body.maintenance.command_sync_service
  - cli.logic.diagnostics
"""

from __future__ import annotations

from typing import Any, Protocol


# ID: 10bc5565-2f20-4497-8865-c36de47dcb48
class TyperCommandLike(Protocol):
    """Structural protocol for a Typer registered command."""

    name: str | None
    callback: Any
    help: str | None


# ID: d01d9def-d26d-4c50-84f6-4ecc6921c9a1
class TyperGroupLike(Protocol):
    """Structural protocol for a Typer registered group."""

    name: str | None
    typer_instance: Any


# ID: f9bd5ff6-605c-4575-b5c6-dc61f23bf964
class TyperAppLike(Protocol):
    """Structural protocol for a Typer application."""

    registered_commands: list[TyperCommandLike]
    registered_groups: list[TyperGroupLike]
