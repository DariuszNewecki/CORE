# src/system/tools/file_scanner.py
"""
Handles the discovery and filtering of Python source files for analysis.
"""

from __future__ import annotations

# src/system/tools/file_scanner.py
from pathlib import Path
from typing import List

from shared.logger import getLogger
from system.tools.config.builder_config import BuilderConfig

log = getLogger(__name__)


class FileScanner:
    """Handles file discovery and filtering."""

    def __init__(self, config: BuilderConfig):
        """Initializes the FileScanner with the builder configuration."""
        self.config = config

    def find_python_files(self) -> List[Path]:
        """Find all Python files in src/ that should be analyzed."""
        if not self.config.src_root.is_dir():
            log.warning(f"Source directory {self.config.src_root} does not exist")
            return []

        py_files = [
            f
            for f in self.config.src_root.rglob("*.py")
            if f.name != "__init__.py" and not self.should_exclude_path(f)
        ]

        log.info(
            f"Found {len(py_files)} Python files to scan in {self.config.src_root}"
        )
        return py_files

    def should_exclude_path(self, path: Path) -> bool:
        """Determine if a given path should be excluded from scanning."""
        return any(pattern in path.parts for pattern in self.config.exclude_patterns)
