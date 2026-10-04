# src/cli/commands/check/__init__.py
"""Shared audit presentation helpers (converters, formatters).

The ``check`` command group that lived here was never registered in
core-admin and was removed with its commands (2026-10-04); audit runs through
``core-admin code audit`` and the /v1/audit and /v1/quality routes.
"""

from __future__ import annotations
