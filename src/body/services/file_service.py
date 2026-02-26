# src/body/services/file_service.py
"""
Body layer file operations service.

CONSTITUTIONAL COMPLIANCE:
- Body layer performs file I/O operations
- Will and API layers delegate file operations here
- Mind layer must not use this service (law does not execute)

This service provides a controlled interface for file operations,
ensuring all I/O goes through the Body layer.

CRITICAL FIX: FileHandler methods are write_runtime_text/bytes/json, NOT write_file!
"""

from __future__ import annotations

from pathlib import Path

from shared.infrastructure.storage.file_handler import FileHandler, FileOpResult
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 336629d4-5541-42a0-a147-d469a2d40aee
# ID: 54b51df1-b3c5-4169-9c69-d76b08f77e2b
class FileService:
    """
    Body layer service for file operations.

    Provides controlled I/O operations that Will and API layers can delegate to.

    CONSTITUTIONAL FIX: Extended to wrap all FileHandler operations so Mind/Will
    never need to import FileHandler directly.

    CRITICAL FIX: Uses correct FileHandler method names (write_runtime_text, not write_file)
    """

    def __init__(self, repo_path: Path):
        """
        Initialize file service.

        Args:
            repo_path: Repository root path
        """
        self.repo_path = repo_path
        self.reports_dir = repo_path / "reports"

        # Create FileHandler instance for all operations
        self._file_handler = FileHandler(str(repo_path))
        logger.debug("FileService initialized for %s", repo_path)

    # ========================================================================
    # EXISTING METHODS (kept for backward compatibility)
    # ========================================================================

    # ID: 3655aa8f-b18f-46a5-8f0c-45d358155706
    async def write_report(self, filename: str, content: str) -> Path:
        """
        Write a report file to the reports directory.
        """
        rel_path = f"reports/{filename}"
        self._file_handler.ensure_dir("reports")
        self._file_handler.write_runtime_text(rel_path, content)
        file_path = self.repo_path / rel_path
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

    # ========================================================================
    # NEW METHODS (wrapping FileHandler correctly)
    # ========================================================================

    # ID: 39f589ea-a508-4671-a923-cd41ce2f947d
    # ID: b1c2d3e4-f5a6-7b8c-9d0e-1f2a3b4c5d6e
    def write_file(self, rel_path: str, content: str) -> FileOpResult:
        """
        Write text content to any repository-relative file.

        CRITICAL FIX: Uses write_runtime_text() which is FileHandler's actual method

        Args:
            rel_path: Repository-relative path (e.g., "reports/audit.json")
            content: Text content to write

        Returns:
            FileOpResult with status and message
        """
        logger.debug("Writing file: %s", rel_path)
        # CRITICAL FIX: FileHandler method is write_runtime_text, not write_file
        result = self._file_handler.write_runtime_text(rel_path, content)

        if result.status == "success":
            logger.info("Successfully wrote: %s", rel_path)
        else:
            logger.error("Failed to write %s: %s", rel_path, result.message)

        return result

    # ID: 8c84d59f-9699-4521-8ae8-865c497d6da6
    # ID: c2d3e4f5-a6b7-8c9d-0e1f-2a3b4c5d6e7f
    def write_runtime_bytes(self, rel_path: str, content: bytes) -> FileOpResult:
        """
        Write binary content to a runtime/output file.

        Args:
            rel_path: Repository-relative path
            content: Binary content to write

        Returns:
            FileOpResult with status and message
        """
        logger.debug("Writing runtime bytes: %s", rel_path)
        result = self._file_handler.write_runtime_bytes(rel_path, content)

        if result.status == "success":
            logger.info("Successfully wrote bytes to: %s", rel_path)
        else:
            logger.error("Failed to write bytes to %s: %s", rel_path, result.message)

        return result

    # ID: 616524ef-ad75-4be7-9032-10e2d551b4e2
    # ID: a2b3c4d5-e6f7-8a9b-0c1d-2e3f4a5b6c7d
    def write_runtime_json(self, rel_path: str, payload: dict) -> FileOpResult:
        """
        Write JSON content to a runtime/output file.

        Args:
            rel_path: Repository-relative path
            payload: Dictionary to write as JSON

        Returns:
            FileOpResult with status and message
        """
        logger.debug("Writing runtime JSON: %s", rel_path)
        result = self._file_handler.write_runtime_json(rel_path, payload)

        if result.status == "success":
            logger.info("Successfully wrote JSON to: %s", rel_path)
        else:
            logger.error("Failed to write JSON to %s: %s", rel_path, result.message)

        return result

    # ID: ab7e4e78-4a83-4380-8832-603af12d7ebc
    # ID: d3e4f5a6-b7c8-9d0e-1f2a-3b4c5d6e7f8a
    def ensure_dir(self, rel_dir: str) -> FileOpResult:
        """
        Ensure a directory exists.

        Args:
            rel_dir: Repository-relative directory path

        Returns:
            FileOpResult with status and message
        """
        logger.debug("Ensuring directory: %s", rel_dir)
        result = self._file_handler.ensure_dir(rel_dir)

        if result.status == "success":
            logger.debug("Directory ready: %s", rel_dir)
        else:
            logger.error("Failed to create directory %s: %s", rel_dir, result.message)

        return result

    # ID: 744e7127-0b8c-4aff-a0b6-e0d45a6f29bb
    # ID: e4f5a6b7-c8d9-0e1f-2a3b-4c5d6e7f8a9b
    def add_pending_write(self, prompt: str, suggested_path: str, code: str) -> str:
        """
        Stage a pending write for review.

        Args:
            prompt: Description of the change
            suggested_path: Proposed file path
            code: Content to write

        Returns:
            Path to the pending write file
        """
        logger.debug("Adding pending write: %s", suggested_path)
        pending_file = self._file_handler.add_pending_write(
            prompt, suggested_path, code
        )
        logger.info("Created pending write: %s", pending_file)
        return pending_file

    # ID: 477782e1-b512-4fef-ad78-63b5bc2b8bd0
    # ID: f5a6b7c8-d9e0-1f2a-3b4c-5d6e7f8a9b0c
    def read_file(self, rel_path: str) -> str | None:
        """
        Read text content from any file.

        Args:
            rel_path: Repository-relative path

        Returns:
            File content as string, or None if not found
        """
        abs_path = self.repo_path / rel_path

        if not abs_path.exists():
            logger.warning("File not found: %s", rel_path)
            return None

        try:
            content = abs_path.read_text(encoding="utf-8")
            logger.debug("Read file: %s (%d bytes)", rel_path, len(content))
            return content
        except Exception as e:
            logger.error("Failed to read %s: %s", rel_path, e)
            return None

    # ID: 99a4abbf-e93f-4707-a9cc-81c8597ce44e
    # ID: a6b7c8d9-e0f1-2a3b-4c5d-6e7f8a9b0c1d
    def file_exists(self, rel_path: str) -> bool:
        """
        Check if a file exists.

        Args:
            rel_path: Repository-relative path

        Returns:
            True if file exists, False otherwise
        """
        abs_path = self.repo_path / rel_path
        exists = abs_path.exists()
        logger.debug("File exists check: %s = %s", rel_path, exists)
        return exists

    # ID: 1541f97a-15fb-4737-b330-1703f5c2c561
    # ID: b7c8d9e0-f1a2-3b4c-5d6e-7f8a9b0c1d2e
    def get_file_handler(self) -> FileHandler:
        """
        Get the underlying FileHandler instance.

        WARNING: Escape hatch for advanced use. Prefer FileService methods.

        Returns:
            FileHandler instance
        """
        logger.warning("Direct FileHandler access - prefer FileService methods")
        return self._file_handler
