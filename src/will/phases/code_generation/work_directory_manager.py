# src/will/phases/code_generation/work_directory_manager.py
"""
Work directory management for code generation sessions.
"""

from __future__ import annotations

import re
from datetime import datetime

from body.services.file_service import FileService
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: dd9e517b-1971-4581-8867-202295f9c31d
class WorkDirectoryManager:
    """
    Creates and manages work directories for code generation artifacts.

    CONSTITUTIONAL COMPLIANCE:
    - Receives FileService from Body layer (no FileHandler import)
    - Uses Body service for directory creation
    """

    def __init__(self, file_service: FileService):
        """
        Initialize work directory manager.

        Args:
            file_service: Body layer FileService for directory operations
        """
        self.file_service = file_service

    # ID: 55cdb2cc-4817-48df-a820-7a76e04453dc
    def create_session_directory(self, goal: str) -> str:
        """
        Create timestamped work directory for this code generation session.

        Args:
            goal: Refactoring goal for this session

        Returns:
            Relative path to work directory (e.g., "work/code_generation/20260118_120534_refactor_cli")

        Constitutional Compliance:
            - Uses FileService.ensure_dir for governed directory creation
            - Work directory is in var-equivalent space (work/ is runtime)
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        goal_slug = self._create_safe_slug(goal)

        # Construct relative path under work/code_generation/
        rel_dir = f"work/code_generation/{timestamp}_{goal_slug}"

        self.file_service.ensure_dir(rel_dir)

        logger.info("📁 Code generation artifacts will be saved to: %s", rel_dir)

        return rel_dir

    @staticmethod
    def _create_safe_slug(goal: str, max_length: int = 50) -> str:
        """
        Create filesystem-safe slug from goal text.

        Args:
            goal: Goal text to convert
            max_length: Maximum slug length

        Returns:
            Safe slug with only alphanumeric and underscores
        """
        # Convert to lowercase and replace non-alphanumeric with underscore
        slug = re.sub(r"[^\w\-]", "_", goal[:max_length].lower())

        # Collapse multiple underscores
        slug = re.sub(r"_+", "_", slug)

        # Strip leading/trailing underscores
        return slug.strip("_")
