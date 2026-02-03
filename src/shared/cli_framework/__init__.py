# src/shared/cli_framework/__init__.py
"""
Constitutional CLI framework.

Provides validation, registration, and enforcement of CLI design principles
as defined in .intent/rules/cli/interface_design.json
"""

from __future__ import annotations

from .validation import (
    FORBIDDEN_RESOURCE_NAMES,
    STANDARD_VERBS,
    ConstitutionalViolation,
    validate_action_name,
    validate_command_depth,
    validate_resource_module,
    validate_resource_name,
)


__all__ = [
    "FORBIDDEN_RESOURCE_NAMES",
    "STANDARD_VERBS",
    "ConstitutionalViolation",
    "validate_action_name",
    "validate_command_depth",
    "validate_resource_module",
    "validate_resource_name",
]
