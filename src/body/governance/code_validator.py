# src/body/governance/code_validator.py
"""
Code Validator - Body Layer Enforcement Service.

CONSTITUTIONAL ALIGNMENT (V2.6.0):
- Relocated: Moved from Mind to Body to comply with Mind-Body-Will separation.
- Responsibility: Provides the mechanical capability to validate generated code
  against architectural patterns.
- Resolves architecture.mind.no_body_invocation violation.
"""

from __future__ import annotations

import ast

# This import is now valid because this file is in the Body layer.
from body.governance.intent_pattern_validators import PatternValidators
from mind.governance.violation_report import ViolationReport
from shared.logger import getLogger
from shared.models.constitutional_validation import ConstitutionalValidationResult


logger = getLogger(__name__)


# ID: 3c35e6ee-f081-49b6-9bad-a74f0caf9936
# ID: 18f27500-2fbd-42a7-9180-a71ac3da5626
class CodeValidator:
    """
    Body service that validates code against architectural patterns.

    Responsibilities:
    - Syntax validation (AST)
    - Pattern-specific enforcement (via PatternValidators)
    """

    @staticmethod
    # ID: d2605a19-d9d7-49cb-8b0d-3ce2acb85964
    def validate_generated_code(
        code: str, pattern_id: str, target_path: str
    ) -> ConstitutionalValidationResult:
        """
        Validate generated code against pattern requirements.
        """
        violations: list[ViolationReport] = []

        # 1. Structural Sensation: Syntax validation (Pure logic)
        if pattern_id in ("pure_function", "stateless_utility"):
            violations.extend(
                CodeValidator._validate_syntax(code, target_path, "code_purity")
            )
            return ConstitutionalValidationResult(
                is_valid=len(violations) == 0,
                violations=violations,
                source="CodeValidator",
            )

        # 2. Pattern Enforcement: Call legacy pattern logic
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

    @staticmethod
    def _validate_syntax(
        code: str, target_path: str, policy_source: str
    ) -> list[ViolationReport]:
        """
        Check if code parses correctly.
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
