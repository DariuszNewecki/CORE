# src/will/phases/code_generation/code_sensor.py

"""
Multi-modal code validation (syntax + functional testing).
"""

from __future__ import annotations

import ast

from shared.logger import getLogger
from will.test_generation.sandbox import PytestSandboxRunner


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

    # TEMPORARY COMPATIBILITY LAYER — remove after refactor_modularity completes
    # ID: 3a8f2c1d-9b4e-4f6a-8d2e-7c5b9a1f3e8d
    async def sense(self, code: str, file_path: str, workspace=None) -> dict:
        """
        Legacy adapter for code_generation_phase during modularity refactor.

        Bridges the old .sense() signature (used by the phase)
        to the new .sense_artifact() implementation you already have.
        """
        # Delegate to the real implementation (note argument order flip)
        passed, error_msg = await self.sense_artifact(file_path, code)

        return {
            "status": "sensed",
            "passed": passed,
            "error": error_msg,
            "issues": [error_msg] if error_msg else [],
            "quality_score": 0.92 if passed else 0.65,
            "suggestions": [error_msg] if error_msg else [],
            "metadata": {
                "file": file_path,
                "validation_mode": "structural+functional",
                "workspace_provided": workspace is not None,
            },
        }

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
