# src/shared/models/validation_result.py
# ID: 174a817b-2d3e-4f5c-8b2c-3d4e5f6a7b8c

"""Provides a canonical structure for validation results across the CORE system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
# ID: d6656332-a7fd-4d66-aa4b-cbd8515b3fe8
class ValidationResult:
    """
    Single, canonical validation result format.

    Used to unify return types from various validation and health-check methods,
    eliminating branching logic and type-checking in callers.
    """

    ok: bool
    """Whether validation passed."""

    errors: list[str] = field(default_factory=list)
    """Validation errors (empty if ok=True)."""

    warnings: list[str] = field(default_factory=list)
    """Non-fatal warnings."""

    validated_data: dict[str, Any] = field(default_factory=dict)
    """Parsed/validated data if ok=True."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional context (file path, checked items, etc.)."""
