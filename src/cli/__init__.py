# src/cli/__init__.py
"""
`cli` — Typer commands and Rich rendering.

The canonical public CLI surface is the two console-script entry
points declared in ``pyproject.toml`` (``core-admin`` →
``cli.admin_cli:app``, ``core`` → ``cli.cli_user:app``). Consumers
invoke the CLI via those scripts, not via ``from cli import ...``.

This package's internal organisation (command modules, resource
groups, sub-apps) is not part of the published contract. No symbols
are re-exported here for 2.6.0; future surface is gated on ADR-shaped
promotions per ADR-084 D4 and F-48.4.
"""

from __future__ import annotations


__all__: list[str] = []
