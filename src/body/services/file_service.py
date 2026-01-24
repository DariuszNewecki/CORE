# src/body/services/file_service.py

"""
Body layer file operations service.

CONSTITUTIONAL COMPLIANCE:
- Body layer performs file I/O operations
- Will and API layers delegate file operations here
- Mind layer must not use this service (law does not execute)

This service provides a controlled interface for file operations,
ensuring all I/O goes through the Body layer.
"""

from __future__ import annotations

from pathlib import Path

from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: a1b2c3d4-e5f6-7g8h-9i0j-k1l2m3n4o5p6
# ID: 54b51df1-b3c5-4169-9c69-d76b08f77e2b
class FileService:
    """
    Body layer service for file operations.

    Provides controlled I/O operations that Will and API layers can delegate to.
    """

    def __init__(self, repo_path: Path):
        """
        Initialize file service.

        Args:
            repo_path: Repository root path
        """
        self.repo_path = repo_path
        self.reports_dir = repo_path / "reports"

    # ID: 3655aa8f-b18f-46a5-8f0c-45d358155706
    async def write_report(self, filename: str, content: str) -> Path:
        """
        Write a report file to the reports directory.

        Args:
            filename: Name of the file to write
            content: Content to write

        Returns:
            Path to the written file
        """
        file_path = self.reports_dir / filename

        # Ensure parent directory exists
        await FileHandler.ensure_parent_dir(file_path)

        # Write content
        await FileHandler.write_content(file_path, content)

        logger.debug("Wrote report file: %s", file_path)
        return file_path

    # ID: 50c9ca07-be37-4a7a-9637-6b7904cf550e
    async def read_report(self, filename: str) -> str:
        """
        Read a report file from the reports directory.

        Args:
            filename: Name of the file to read

        Returns:
            File content as string
        """
        file_path = self.reports_dir / filename

        if not file_path.exists():
            raise FileNotFoundError(f"Report file not found: {file_path}")

        content = await FileHandler.read_content(file_path)
        logger.debug("Read report file: %s", file_path)
        return content
