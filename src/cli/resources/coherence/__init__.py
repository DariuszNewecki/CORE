# src/cli/resources/coherence/__init__.py
"""Constitutional Coherence Checker resource group (ADR-067)."""

from __future__ import annotations

from . import check, report, triage
from .hub import app


__all__ = ["app"]
