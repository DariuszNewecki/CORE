# src/services/validation/yaml_validator.py
"""
YAML validation pipeline.

This module provides validation functionality specifically for YAML files,
checking for syntax errors and structural issues.
"""

from __future__ import annotations

from typing import Any

import yaml

Violation = dict[str, Any]


# ID: f3bbf4e9-71b5-4dad-8ad8-ee93b90dd8c0
def validate_yaml_code(code: str) -> tuple[str, list[Violation]]:
    """Validation pipeline for YAML code.

    This function validates YAML syntax and structure, returning any violations
    found during the validation process.

    Args:
        code: The YAML code to validate

    Returns:
        A tuple containing the original code and list of violations
    """
    violations = []
    try:
        yaml.safe_load(code)
    except yaml.YAMLError as e:
        violations.append(
            {
                "rule": "syntax.yaml",
                "message": f"Invalid YAML format: {e}",
                "line": e.problem_mark.line + 1 if e.problem_mark else 0,
                "severity": "error",
            }
        )
    return code, violations
