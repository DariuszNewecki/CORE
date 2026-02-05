# src/mind/governance/intent_pattern_validators.py
"""
Legacy CLI pattern validators for IntentGuard.

DISTINCTION:
- This file: String-based validation for CLI patterns (IntentGuard usage)
- pattern_validator.py: AST-based validation for code generation

DEPRECATION NOTICE:
These validators are hardcoded Python logic and should be migrated to
constitutional rules with engine-based verification. They remain here
temporarily for backward compatibility during the transition.

Migration target: .intent/policies/ with ast_gate or regex_gate engines.
"""

from __future__ import annotations

from mind.governance.violation_report import ViolationReport
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 5d89fc56-2fb5-45da-98f0-f813e8e79343
class PatternValidators:
    """
    Legacy validators for code generation patterns.

    These enforce conventions for generated code:
    - inspect_pattern: Read-only commands (no --write, --apply, --force)
    - action_pattern: Commands with explicit write parameter
    - check_pattern: Pure check commands (no mutations)
    - run_pattern: Run commands with write parameter

    FUTURE: Migrate to constitutional rules in .intent/policies/
    """

    @staticmethod
    # ID: 9f1df13c-5efe-47fc-b8ac-e7236ff5e9c7
    def validate_inspect_pattern(code: str, target_path: str) -> list[ViolationReport]:
        """
        Validate inspect pattern: must be read-only.

        Forbidden: --write, --apply, --force flags
        """
        violations: list[ViolationReport] = []
        forbidden_params = [
            "--write",
            "--apply",
            "--force",
            "write:",
            "apply:",
            "force:",
        ]

        for param in forbidden_params:
            if param in code:
                violations.append(
                    ViolationReport(
                        rule_name="inspect_pattern_violation",
                        path=target_path,
                        message=f"Inspect pattern violation: Found forbidden parameter '{param}'.",
                        severity="error",
                        suggested_fix=f"Remove '{param}' - inspect commands must be read-only.",
                        source_policy="pattern_vectorization",
                    )
                )

        return violations

    @staticmethod
    # ID: 62c418d6-754b-4e4c-9f66-f7d35f5bd590
    def validate_action_pattern(code: str, target_path: str) -> list[ViolationReport]:
        """
        Validate action pattern: must have write parameter defaulting to False.
        """
        violations: list[ViolationReport] = []

        # Must have write parameter
        if "write:" not in code and "write =" not in code:
            violations.append(
                ViolationReport(
                    rule_name="action_pattern_violation",
                    path=target_path,
                    message="Action pattern violation: Missing required 'write' parameter.",
                    severity="error",
                    suggested_fix="Add 'write: bool = False' parameter to command.",
                    source_policy="pattern_vectorization",
                )
            )

        # Write must default to False
        if "write: bool = True" in code or "write=True" in code:
            violations.append(
                ViolationReport(
                    rule_name="action_pattern_violation",
                    path=target_path,
                    message="Action pattern violation: write parameter must default to False.",
                    severity="error",
                    suggested_fix="Change to 'write: bool = False'.",
                    source_policy="pattern_vectorization",
                )
            )

        return violations

    @staticmethod
    # ID: e9e8a09b-ce90-452a-9269-ae27a95b56d4
    def validate_check_pattern(code: str, target_path: str) -> list[ViolationReport]:
        """
        Validate check pattern: must not modify state.

        Forbidden: write or apply parameters
        """
        violations: list[ViolationReport] = []

        if "write:" in code or "apply:" in code:
            violations.append(
                ViolationReport(
                    rule_name="check_pattern_violation",
                    path=target_path,
                    message="Check pattern violation: Check commands must not modify state.",
                    severity="error",
                    suggested_fix="Remove write/apply parameters.",
                    source_policy="pattern_vectorization",
                )
            )

        return violations

    @staticmethod
    # ID: 3f0486a3-59ce-4671-b07f-1a144b3d07d3
    def validate_run_pattern(code: str, target_path: str) -> list[ViolationReport]:
        """
        Validate run pattern: must have write parameter.
        """
        violations: list[ViolationReport] = []

        if "write:" not in code and "write =" not in code:
            violations.append(
                ViolationReport(
                    rule_name="run_pattern_violation",
                    path=target_path,
                    message="Run pattern violation: Missing required 'write' parameter.",
                    severity="error",
                    suggested_fix="Add 'write: bool = False' parameter.",
                    source_policy="pattern_vectorization",
                )
            )

        return violations
