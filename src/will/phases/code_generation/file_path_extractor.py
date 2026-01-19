# src/will/phases/code_generation/file_path_extractor.py

"""
Extracts file paths from task objects.
"""

from __future__ import annotations


# ID: 78f713f1-aeeb-49df-9811-e1c409d0203c
class FilePathExtractor:
    """
    Extracts target file paths from task objects.

    Defensive extraction handles loosely-typed task objects from planning phase.
    """

    @staticmethod
    # ID: 781be329-4c4f-4a17-9da4-936d95f3bef2
    def extract(task: object, step_index: int) -> str:
        """
        Extract file path from task or generate fallback.

        Args:
            task: Task object from planning phase
            step_index: Step number for fallback naming

        Returns:
            Target file path or fallback path
        """
        params = getattr(task, "params", None)

        if params is None:
            return FilePathExtractor._fallback_path(step_index)

        # Try attribute access
        file_path = getattr(params, "file_path", None)

        # Try dict access if attribute failed
        if not file_path and isinstance(params, dict):
            file_path = params.get("file_path")

        if file_path and isinstance(file_path, str):
            return file_path

        return FilePathExtractor._fallback_path(step_index)

    @staticmethod
    def _fallback_path(step_index: int) -> str:
        """Generate fallback path for tasks without explicit file path."""
        return f"work/temp_step_{step_index}.py"
