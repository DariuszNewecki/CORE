# src/core/yaml_validator.py
"""
YAML validation pipeline.

This module provides validation functionality specifically for YAML files,
checking for syntax errors and structural issues.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import yaml

Violation = Dict[str, Any]


# CAPABILITY: validate_yaml_syntax_and_structure
def validate_yaml_code(code: str) -> Tuple[str, List[Violation]]:
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
