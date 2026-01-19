# src/will/phases/code_generation/code_sensor.py

"""
Multi-modal code validation (syntax + functional testing).
"""

from __future__ import annotations

import ast

from features.test_generation_v2.sandbox import PytestSandboxRunner
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 079291fe-0267-46f9-b2a1-55d9358ac6ba
class CodeSensor:
    """
    Multi-modal sensation logic for generated code.

    Validates code through two modalities:
    - Structural: Python syntax must parse (universal)
    - Functional: Tests must pass in sandbox (for test files only)
    """

    def __init__(self, execution_sensor: PytestSandboxRunner):
        self.execution_sensor = execution_sensor

    # ID: f3d71df6-eab1-43f7-90b5-e35ec3c36bd9
    async def sense_artifact(
        self, file_path: str, code: str
    ) -> tuple[bool, str | None]:
        """
        Validate generated code artifact.

        Args:
            file_path: Target file path
            code: Generated code content

        Returns:
            Tuple of (validation_passed, error_message)
        """
        if not code:
            return False, "No code generated."

        # 1) STRUCTURAL SENSATION (universal)
        if file_path.endswith(".py"):
            syntax_ok, syntax_error = self._validate_syntax(code)
            if not syntax_ok:
                return False, syntax_error

        # 2) FUNCTIONAL SENSATION (test files only)
        if self._is_test_file(file_path):
            return await self._validate_functional(code, file_path)

        # Non-test files pass if structurally sound
        return True, None

    @staticmethod
    def _validate_syntax(code: str) -> tuple[bool, str | None]:
        """Validate Python syntax."""
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            return False, f"Syntax Error: {e}"

    @staticmethod
    def _is_test_file(file_path: str) -> bool:
        """Determine if file path indicates a test file."""
        return (
            ("test_" in file_path)
            or ("/tests/" in file_path)
            or ("\\tests\\" in file_path)
        )

    async def _validate_functional(
        self, code: str, file_path: str
    ) -> tuple[bool, str | None]:
        """Run functional validation via pytest sandbox."""
        logger.debug("Modality: Functional (Pytest) for %s", file_path)

        result = await self.execution_sensor.run(code, "reflex_check")

        if getattr(result, "passed", False):
            return True, None

        error = getattr(result, "error", "Pytest failed.")
        return False, error
