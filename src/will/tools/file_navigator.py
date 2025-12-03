# src/will/tools/file_navigator.py
"""
File Navigator Tool.

Provides safe, read-only filesystem access for agents to explore the codebase.
Enforces constitutional boundaries (no access to .env, keys, or outside repo).

Constitutional Alignment:
- safe_by_default: Read-only access, path sanitation.
- separation_of_concerns: Pure tool, no decision making.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shared.config import settings
from shared.logger import getLogger

logger = getLogger(__name__)

# Constitutionally forbidden patterns for read access
FORBIDDEN_PATTERNS = [
    ".env",
    "*.key",
    ".git/*",
    "__pycache__",
    ".intent/keys/*",
    "secrets/*",
]


@dataclass
# ID: 4aa6c204-9357-4d32-b8c7-8a300fc5cdc1
class FileEntry:
    """Represents a file or directory in a listing."""

    name: str
    path: str
    type: str  # "file" or "dir"
    size: int | None = None


# ID: b91a4c15-1b32-4f02-b831-49c0d520f59b
class FileNavigator:
    """
    Safe filesystem explorer for agents.
    """

    def __init__(self, repo_root: Path | None = None):
        self.root = (repo_root or settings.REPO_PATH).resolve()

    def _validate_path(self, rel_path: str) -> Path:
        """
        Validates that a path is safe to access.
        Raises ValueError if path is forbidden or traverses outside root.
        """
        # sanitize
        clean_path = rel_path.lstrip("/")
        full_path = (self.root / clean_path).resolve()

        # Check 1: Path traversal
        if not str(full_path).startswith(str(self.root)):
            raise ValueError(
                f"Access denied: Path '{rel_path}' is outside repository root."
            )

        # Check 2: Forbidden patterns
        for pattern in FORBIDDEN_PATTERNS:
            if full_path.match(pattern) or any(
                p.match(pattern) for p in full_path.parents
            ):
                raise ValueError(
                    f"Access denied: Path '{rel_path}' is restricted by policy."
                )

        return full_path

    # ID: 35aaeb95-a94d-49ef-90ec-8f9fc7b165ec
    async def list_dir(self, path: str = ".") -> list[FileEntry]:
        """
        List contents of a directory.

        Args:
            path: Relative path to directory (default: root).
        """
        target = self._validate_path(path)

        if not target.exists():
            raise FileNotFoundError(f"Directory not found: {path}")
        if not target.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {path}")

        entries = []
        try:
            for item in target.iterdir():
                # Skip hidden files/dirs by default to reduce noise
                if item.name.startswith(".") and item.name != ".intent":
                    continue

                entry = FileEntry(
                    name=item.name,
                    path=str(item.relative_to(self.root)),
                    type="dir" if item.is_dir() else "file",
                    size=item.stat().st_size if item.is_file() else None,
                )
                entries.append(entry)
        except PermissionError:
            logger.warning(f"Permission denied listing {path}")

        # Sort: Directories first, then files
        entries.sort(key=lambda x: (x.type != "dir", x.name))
        return entries

    # ID: 38192d86-2eca-4e54-bff0-c1401cbc83e5
    async def read_file(self, path: str, max_lines: int = 200) -> str:
        """
        Read file content safely.

        Args:
            path: Relative path to file.
            max_lines: Limit output to avoid context overflow.
        """
        target = self._validate_path(path)

        if not target.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if not target.is_file():
            raise ValueError(f"Path is not a file: {path}")

        try:
            # Enforce size limit (1MB) before reading
            if target.stat().st_size > 1024 * 1024:
                return f"Error: File {path} is too large ({target.stat().st_size} bytes). Max 1MB."

            content = target.read_text(encoding="utf-8")
            lines = content.splitlines()

            if len(lines) > max_lines:
                preview = "\n".join(lines[:max_lines])
                return (
                    f"{preview}\n\n... (Truncated {len(lines) - max_lines} more lines)"
                )

            return content

        except UnicodeDecodeError:
            return f"Error: File {path} appears to be binary or non-UTF-8."
        except Exception as e:
            logger.error(f"Error reading {path}: {e}")
            raise
