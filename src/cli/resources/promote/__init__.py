# src/cli/resources/promote/__init__.py
"""Promote resource — propose main to the governor for promotion to live (ADR-171)."""

from __future__ import annotations

from . import propose  # register the commands
from .hub import app


__all__ = ["app"]
