# src/mind/governance/code_validator.py

"""
Code Validator - Generated Code Validation

CONSTITUTIONAL ALIGNMENT:
- Single Responsibility: Validate generated code
- Pattern-specific checks
- AST-based syntax validation

Extracted from IntentGuard to separate code validation concerns.
"""

from __future__ import annotations

import ast

from mind.governance.intent_pattern_validators import PatternValidators
from mind.governance.violation_report import ViolationReport
from shared.logger import getLogger
from shared.models.constitutional_validation import ConstitutionalValidationResult


logger = getLogger(__name__)


# ID: code_validator
# ID: 1e2f3a4b-5c6d-7e8f-9a0b-1c2d3e4f5a6b
class CodeValidator:
    """
    Validates generated code against pattern requirements.

    Responsibilities:
    - Syntax validation
    - Pattern-specific checks
    - Coordinates with PatternValidators for legacy patterns
    """

    # ID: validator_validate_code
    # ID: 2f3a4b5c-6d7e-8f9a-0b1c-2d3e4f5a6b7c
    @staticmethod
    # ID: d2605a19-d9d7-49cb-8b0d-3ce2acb85964
    def validate_generated_code(
        code: str, pattern_id: str, target_path: str
    ) -> ConstitutionalValidationResult:
        """
        Validate generated code against pattern requirements.

        Args:
            code: Generated code content
            pattern_id: Pattern type (e.g., "inspect_pattern", "action_pattern")
            target_path: Target file path (repo-relative)

        Returns:
            ConstitutionalValidationResult with violations
        """
        violations: list[ViolationReport] = []

        # V2 Utility patterns - pure logic, only need valid syntax
        if pattern_id in ("pure_function", "stateless_utility"):
            violations.extend(
                CodeValidator._validate_syntax(code, target_path, "code_purity")
            )
            return ConstitutionalValidationResult(
                is_valid=len(violations) == 0,
                violations=violations,
                source="CodeValidator",
            )

        # Legacy pattern validators (for Commands and Actions)
        if pattern_id == "inspect_pattern":
            violations.extend(
                PatternValidators.validate_inspect_pattern(code, target_path)
            )
        elif pattern_id == "action_pattern":
            violations.extend(
                PatternValidators.validate_action_pattern(code, target_path)
            )
        elif pattern_id == "check_pattern":
            violations.extend(
                PatternValidators.validate_check_pattern(code, target_path)
            )
        elif pattern_id == "run_pattern":
            violations.extend(PatternValidators.validate_run_pattern(code, target_path))

        return ConstitutionalValidationResult(
            is_valid=len(violations) == 0,
            violations=violations,
            source="CodeValidator",
        )

    # ID: validator_validate_syntax
    # ID: 3a4b5c6d-7e8f-9a0b-1c2d-3e4f5a6b7c8d
    @staticmethod
    def _validate_syntax(
        code: str, target_path: str, policy_source: str
    ) -> list[ViolationReport]:
        """
        Validate Python syntax.

        Args:
            code: Code to validate
            target_path: Target file path
            policy_source: Source policy identifier

        Returns:
            List of violations (empty if valid)
        """
        try:
            ast.parse(code)
            return []
        except SyntaxError as e:
            return [
                ViolationReport(
                    rule_name="syntax_error",
                    path=target_path,
                    message=f"Syntax error in generated code: {e}",
                    severity="error",
                    source_policy=policy_source,
                )
            ]
