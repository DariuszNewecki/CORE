# src/body/cli/resources/admin/__init__.py
"""Admin forensic resource hub."""

from __future__ import annotations

# Register Forensic Neurons
from . import (
    coverage,
    forensics,
    patterns,
    refusals,
    self_check,
    status,
    summary,
    traces,
    validate_env,
)
from .hub import app


__all__ = ["app"]
