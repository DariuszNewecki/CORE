# src/features/test_generation/validation.py

"""
Generated Test Validation (Constitutional-lite)

Purpose:
- Minimal deterministic validation before sandbox.
- Prevent obvious junk from reaching pytest.

Policy:
1) Valid Python syntax
2) Contains at least one pytest test function
3) Imports pytest
"""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
# ID: 6a4b2bb7-9c07-4ff0-9c8b-efca7f1bcb0a
class ValidationResult:
    ok: bool
    error: str = ""


# ID: 58ee8b7e-19d1-44d7-b1dc-5b0bd2fcbf70
class GeneratedTestValidator:
    """Minimal validation for generated test code."""

    # ID: dd5adf4f-0500-4b21-a5bf-2ee7ea260ee4
    def validate(self, code: str) -> ValidationResult:
        try:
            ast.parse(code)

            has_test = any(
                line.strip().startswith("def test_")
                or line.strip().startswith("async def test_")
                for line in code.splitlines()
            )
            if not has_test:
                return ValidationResult(
                    ok=False, error="No test function found (must start with 'test_')."
                )

            has_pytest = ("import pytest" in code) or ("from pytest" in code)
            if not has_pytest:
                return ValidationResult(ok=False, error="Missing pytest import.")

            return ValidationResult(ok=True, error="")

        except SyntaxError as e:
            return ValidationResult(ok=False, error=f"Syntax error: {e}")
        except Exception as e:
            return ValidationResult(ok=False, error=f"Validation error: {e}")
