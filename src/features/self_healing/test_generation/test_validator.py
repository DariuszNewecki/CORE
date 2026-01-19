# src/features/self_healing/test_generation/test_validator.py

"""
Test code validation utilities.
"""

from __future__ import annotations

from typing import Any

from features.self_healing.test_context_analyzer import ModuleContext
from mind.governance.audit_context import AuditorContext
from will.orchestration.validation_pipeline import validate_code_async


# ID: 0bcff3b7-9492-4abb-a3b5-22fd4501c5af
class TestValidator:
    """Validates generated test code for structural and constitutional compliance."""

    def __init__(self, auditor_context: AuditorContext):
        self.auditor = auditor_context

    # ID: 8ea338ef-c0a5-413f-ba5b-5f12b8c95b78
    async def validate_code(
        self, test_file: str, code: str, module_context: ModuleContext
    ) -> list[dict[str, Any]]:
        """
        Validate test code and return violations.

        Returns empty list if valid.
        """
        violations = []

        # Structural sanity check
        if not self._looks_like_real_tests(
            code, module_context.import_path, module_context.module_path
        ):
            violations.append(
                {
                    "message": "Generated code does not look like a valid test file.",
                    "severity": "error",
                    "rule": "structural_sanity",
                }
            )
            return violations

        # Constitutional validation
        validation = await validate_code_async(
            test_file, code, auditor_context=self.auditor
        )
        if validation.get("status") == "dirty":
            violations.extend(validation.get("violations", []))

        return violations

    @staticmethod
    def _looks_like_real_tests(
        code: str, module_import_path: str, module_path: str
    ) -> bool:
        """Quick heuristic check if code looks like valid tests."""
        if not code:
            return False
        lowered = code.lower()
        has_test_def = "def test_" in lowered or "class test" in lowered
        has_assert = "assert " in lowered or "pytest.raises" in lowered
        return has_test_def and has_assert
