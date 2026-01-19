# src/will/tools/context/code_snippet_extractor.py

"""
Extracts code snippets from source files.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 7105d901-b084-4a4d-9d8b-4a75ba145e81
class CodeSnippetExtractor:
    """Extracts code snippets around specific line numbers."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root

    # ID: f108f856-22d7-4084-86f0-d83853cf09db
    async def extract_snippet(
        self, file_path: str, line_number: int, context_lines: int = 20
    ) -> str | None:
        """
        Extract code snippet from file around a specific line.

        Args:
            file_path: Relative path from repo root
            line_number: Line number (1-indexed)
            context_lines: Number of lines to include after target line

        Returns:
            Code snippet or None if file doesn't exist
        """
        path = self.repo_root / file_path
        if not path.exists():
            logger.warning("File not found: %s", file_path)
            return None

        try:
            content = await asyncio.to_thread(path.read_text, encoding="utf-8")
            lines = content.splitlines()

            start = max(0, line_number - 1)  # Convert to 0-indexed
            end = min(len(lines), line_number + context_lines)

            snippet_lines = lines[start:end]
            return "\n".join(snippet_lines)
        except Exception as e:
            logger.error("Failed to read %s: %s", file_path, e)
            return None

    # ID: 11aff3e1-a78a-4f2a-87ee-502d4131a459
    async def read_file(self, file_path: str) -> str | None:
        """
        Read entire file content.

        Args:
            file_path: Relative path from repo root

        Returns:
            File content or None if file doesn't exist
        """
        path = self.repo_root / file_path
        if not path.exists():
            return None

        try:
            return await asyncio.to_thread(path.read_text, encoding="utf-8")
        except Exception as e:
            logger.error("Failed to read %s: %s", file_path, e)
            return None
