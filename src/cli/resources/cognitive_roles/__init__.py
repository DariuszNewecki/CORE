# src/cli/resources/cognitive_roles/__init__.py
"""Cognitive-roles resource hub (#821 Unit 2)."""

from __future__ import annotations

# Register all neurons
from . import project
from .hub import app


__all__ = ["app"]
