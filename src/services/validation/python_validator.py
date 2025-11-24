# src/services/validation/python_validator.py
"""
Python code validation pipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import black

from body.services.validation_policies import PolicyValidator
from mind.governance.checks.import_rules import ImportRulesCheck
from mind.governance.runtime_validator import RuntimeValidatorService
from services.validation.black_formatter import format_code_with_black
from services.validation.quality import QualityChecker
from services.validation.ruff_linter import fix_and_lint_code_with_ruff
from services.validation.syntax_checker import check_syntax
from shared.models import AuditFinding

if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext

Violation = dict[str, Any]


# ID: 9b262a79-1e30-43fb-a9e2-1141058981d5
async def validate_python_code_async(
    path_hint: str, code: str, auditor_context: AuditorContext
) -> tuple[str, list[Violation]]:
    """Comprehensive validation pipeline for Python code, now including runtime checks."""
    all_violations: list[Violation] = []

    # --- Step 1: Static Analysis (unchanged) ---
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

    # --- FIX APPLIED HERE: removed "await" ---
    try:
        # ImportRulesCheck.execute_on_content is synchronous.
        import_violations = import_checker.execute_on_content(path_hint, fixed_code)
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

    # --- Step 2: Conditional Runtime Validation (unchanged) ---
    is_test_file = "tests/" in path_hint.replace("\\", "/")
    if not is_test_file and not any(
        v.get("severity") == "error" for v in all_violations
    ):
        runtime_validator = RuntimeValidatorService(auditor_context.repo_path)
        passed, details = await runtime_validator.run_tests_in_canary(
            path_hint, fixed_code
        )
        if not passed:
            all_violations.append(
                AuditFinding(
                    check_id="runtime.tests.failed",
                    severity="error",
                    message="Code failed to pass the test suite in an isolated environment.",
                    context={"details": details},
                ).as_dict()
            )

    return fixed_code, all_violations
