# src/features/test_generation_v2/phases/parse_phase.py
"""Parse phase - validates file paths and permissions."""

from __future__ import annotations

from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d
class ParsePhase:
    """Validates file paths before test generation."""

    def __init__(self, context: CoreContext):
        self.context = context

    # ID: 721e172c-b28a-45ea-ba2e-5159b1a1a452
    async def execute(self, file_path: str) -> bool:
        """
        Validate file path and permissions.

        Args:
            file_path: Relative path to file

        Returns:
            True if validation passed, False otherwise
        """
        try:
            abs_path = self.context.git_service.repo_path / file_path

            if not abs_path.exists():
                logger.error("Parse Phase Failed: File does not exist: %s", file_path)
                return False

            if not abs_path.is_relative_to(self.context.git_service.repo_path):
                logger.error(
                    "Parse Phase Failed: File outside repository: %s", file_path
                )
                return False

            logger.info("✅ Parse Phase: Request validated")
            return True

        except Exception as e:
            logger.error("Parse Phase Failed: %s", e, exc_info=True)
            return False
