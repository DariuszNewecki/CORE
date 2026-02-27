# src/will/test_generation/validation.py

"""
Generated Test Validation (Constitutional-lite)

Purpose:
- Minimal deterministic validation before sandbox.
- Prevent obvious junk from reaching pytest.

Policy:
1) Valid Python syntax
2) Contains at least one pytest test function
3) Imports pytest
4) MUST NOT import from 'src.' (generated tests must use real package roots)
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
            tree = ast.parse(code)

            # -----------------------------------------------------------------
            # Constitutional-lite guard: forbid importing via "src." prefix.
            # Generated tests must import real package roots (e.g., body.*, shared.*).
            # This blocks hallucinations like: from src.body.cli... import PatternChecker
            # -----------------------------------------------------------------
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "src" or alias.name.startswith("src."):
                            return ValidationResult(
                                ok=False,
                                error=(
                                    "Forbidden import root 'src'. "
                                    "Do not import from 'src.*' in generated tests. "
                                    "Import packages directly (e.g., 'body.*', 'shared.*', 'mind.*', 'will.*')."
                                ),
                            )

                if isinstance(node, ast.ImportFrom):
                    # node.module can be None for "from . import x"
                    module = node.module or ""
                    if module == "src" or module.startswith("src."):
                        return ValidationResult(
                            ok=False,
                            error=(
                                "Forbidden import root 'src'. "
                                "Do not import from 'src.*' in generated tests. "
                                "Import packages directly (e.g., 'body.*', 'shared.*', 'mind.*', 'will.*')."
                            ),
                        )

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
