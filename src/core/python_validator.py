# src/core/python_validator.py
"""
Python code validation pipeline.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Tuple

import black

from core.black_formatter import format_code_with_black
from core.ruff_linter import fix_and_lint_code_with_ruff
from core.syntax_checker import check_syntax
from features.governance.checks.import_rules import ImportRulesCheck

from .validation_policies import PolicyValidator
from .validation_quality import QualityChecker

if TYPE_CHECKING:
    from features.governance.audit_context import AuditorContext

Violation = Dict[str, Any]


# ID: df30ee5a-2cf7-4671-a10b-5d995a28310a
async def validate_python_code_async(
    path_hint: str, code: str, auditor_context: "AuditorContext"
) -> Tuple[str, List[Violation]]:
    """Comprehensive validation pipeline for Python code."""
    all_violations: List[Violation] = []

    safety_policy = auditor_context.policies.get("safety_policy", {})
    policy_validator = PolicyValidator(safety_policy.get("rules", []))
    quality_checker = QualityChecker()
    import_checker = ImportRulesCheck(auditor_context)

    try:
        formatted_code = format_code_with_black(code)
    except (black.InvalidInput, Exception) as e:
        all_violations.append(
            {
                "rule": "tooling.black_failure",
                "message": str(e),
                "line": 0,
                "severity": "error",
            }
        )
        return code, all_violations

    fixed_code, ruff_violations = fix_and_lint_code_with_ruff(formatted_code, path_hint)
    all_violations.extend(ruff_violations)

    syntax_violations = check_syntax(path_hint, fixed_code)
    all_violations.extend(syntax_violations)
    if any(v["severity"] == "error" for v in syntax_violations):
        return fixed_code, all_violations

    all_violations.extend(policy_validator.check_semantics(fixed_code, path_hint))
    all_violations.extend(quality_checker.check_for_todo_comments(fixed_code))

    try:
        import_violations = await import_checker.execute_on_content(
            path_hint, fixed_code
        )
        all_violations.extend(import_violations)
    except Exception as e:
        all_violations.append(
            {
                "rule": "import.check_failed",
                "message": str(e),
                "line": 0,
                "severity": "error",
            }
        )

    return fixed_code, all_violations
