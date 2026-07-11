# src/cli/__init__.py
"""
`cli` — Typer commands and Rich rendering.

The canonical public CLI surface is ``core-admin`` → ``cli.admin_cli:app``
(declared in ``pyproject.toml``). The consumer surface (``core``) lives in
the ``core-cli`` repo (ADR-146 D6); ``cli.cli_user`` has been retired.

This package's internal organisation (command modules, resource
groups, sub-apps) is not part of the published contract. No symbols
are re-exported here; future surface is gated on ADR-shaped
promotions per ADR-084 D4 and F-48.4.
"""

from __future__ import annotations


__all__: list[str] = []
