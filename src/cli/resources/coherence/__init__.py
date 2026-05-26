# src/cli/resources/coherence/__init__.py
"""Constitutional Coherence Checker resource group (ADR-067 + ADR-073)."""

from __future__ import annotations

from . import check, report, triage
from .hub import app
from .seed import seed_app


app.add_typer(seed_app, name="seed")

__all__ = ["app"]
