# src/body/services/validation/python_validator.py

"""
Python code validation pipeline orchestrator.

CONSTITUTIONAL ALIGNMENT:
- Aligns with 'body_contracts.json' (Headless, no direct Mind engine dependency).
- Uses local 'PolicyValidator' for semantic safety checks within the Body layer.
- Enforces 'dry_by_design' by delegating to shared infrastructure for Black/Ruff/Syntax.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import black

from body.services.validation.validation_policies import PolicyValidator
from shared.infrastructure.validation.black_formatter import format_code_with_black
from shared.infrastructure.validation.quality import QualityChecker
from shared.infrastructure.validation.ruff_linter import fix_and_lint_code_with_ruff
from shared.infrastructure.validation.syntax_checker import check_syntax
from shared.logger import getLogger


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext

logger = getLogger(__name__)
Violation = dict[str, Any]


# ID: 9b262a79-1e30-43fb-a9e2-1141058981d5
async def validate_python_code_async(
    path_hint: str, code: str, auditor_context: AuditorContext
) -> tuple[str, list[Violation]]:
    """
    Comprehensive validation pipeline for Python code.

    This Body-layer service coordinates deterministic quality checks.
    Governance-level auditing is deferred to the Mind-layer Auditor.
    """
    all_violations: list[Violation] = []

    # 1. FORMATTING (Standard Tooling)
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

    # 2. LINTING (Standard Tooling)
    fixed_code, ruff_violations = fix_and_lint_code_with_ruff(formatted_code, path_hint)
    all_violations.extend(ruff_violations)

    # 3. SYNTAX VALIDATION (Deterministic Body Check)
    syntax_violations = check_syntax(path_hint, fixed_code)
    all_violations.extend(syntax_violations)

    # Fail fast on syntax errors before performing more expensive checks
    if any(v["severity"] == "error" for v in syntax_violations):
        return fixed_code, all_violations

    # 4. LOCAL POLICY VALIDATION (Policy-Aware Body Check)
    # Uses the local PolicyValidator which is a permitted Body-layer component.
    safety_policy = auditor_context.policies.get("safety_policy", {})
    policy_validator = PolicyValidator(safety_policy.get("rules", []))
    all_violations.extend(policy_validator.check_semantics(fixed_code, path_hint))

    # 5. QUALITY ATTRIBUTES (DRY / TODO detection)
    quality_checker = QualityChecker()
    all_violations.extend(quality_checker.check_for_todo_comments(fixed_code))

    logger.debug(
        "Validation completed for %s: %d violation(s) found.",
        path_hint,
        len(all_violations),
    )

    return fixed_code, all_violations
