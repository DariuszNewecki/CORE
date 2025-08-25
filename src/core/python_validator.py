# src/core/python_validator.py
"""
Python code validation pipeline.

This module implements a comprehensive validation pipeline specifically for Python code,
including formatting with Black, linting with Ruff, syntax checking, and semantic analysis.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import black

from core.black_formatter import format_code_with_black
from core.ruff_linter import fix_and_lint_code_with_ruff
from core.syntax_checker import check_syntax

from .validation_policies import PolicyValidator
from .validation_quality import QualityChecker

Violation = Dict[str, Any]


# CAPABILITY: validate_python_code_with_comprehensive_pipeline
def validate_python_code(path_hint: str, code: str) -> Tuple[str, List[Violation]]:
    """Comprehensive validation pipeline for Python code.

    This function performs a multi-step validation process including formatting,
    linting, syntax checking, and semantic analysis. Each step builds upon the
    previous one, with early termination on critical errors.

    Args:
        path_hint: Path hint for the code being validated
        code: The Python code to validate

    Returns:
        A tuple containing the final processed code and list of violations
    """
    all_violations: List[Violation] = []
    policy_validator = PolicyValidator()
    quality_checker = QualityChecker()

    # 1. Format with Black. This can fail on major syntax errors.
    try:
        formatted_code = format_code_with_black(code)
    except (black.InvalidInput, Exception) as e:
        # If Black fails, the code is fundamentally broken.
        all_violations.append(
            {
                "rule": "tooling.black_failure",
                "message": str(e),
                "line": 0,
                "severity": "error",
            }
        )
        # Return the original code since formatting failed.
        return code, all_violations

    # 2. Lint with Ruff (which also fixes).
    fixed_code, ruff_violations = fix_and_lint_code_with_ruff(formatted_code, path_hint)
    all_violations.extend(ruff_violations)

    # 3. Check syntax on the post-Ruff code.
    syntax_violations = check_syntax(path_hint, fixed_code)
    all_violations.extend(syntax_violations)
    # If there's a syntax error, no further checks are reliable.
    if any(v["severity"] == "error" for v in syntax_violations):
        return fixed_code, all_violations

    # 4. Perform semantic and clarity checks on the valid code.
    all_violations.extend(policy_validator.check_semantics(fixed_code, path_hint))
    all_violations.extend(quality_checker.check_for_todo_comments(fixed_code))

    return fixed_code, all_violations
