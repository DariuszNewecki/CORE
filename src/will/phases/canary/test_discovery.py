# src/will/phases/canary/test_discovery.py

"""
Test file discovery for canary validation.
"""

from __future__ import annotations

from pathlib import Path

from shared.logger import getLogger
from shared.path_resolver import PathResolver


logger = getLogger(__name__)


# ID: 4d68b6b1-3cbe-4c0f-8d2c-3c0c7990f162
class TestDiscoveryService:
    """Discovers test files related to production code files."""

    def __init__(self, path_resolver: PathResolver, tests_dir: Path | None = None):
        self._paths = path_resolver
        self.tests_dir = tests_dir or self._paths.repo_root / "tests"

    # ID: 39aaa9a2-e018-474a-be53-fae82d954e3d
    def find_related_tests(self, affected_files: list[str]) -> list[str]:
        """
        Find test files related to affected production files.

        Strategy:
        1. For src/foo/bar.py, look for tests/foo/test_bar.py
        2. For src/foo/bar.py, look for tests/foo/bar/test_*.py
        3. For src/foo/__init__.py, look for tests/foo/test_*.py
        """
        if not self.tests_dir.exists():
            logger.warning("Tests directory not found: %s", self.tests_dir)
            return []

        test_paths = []
        for file_path in affected_files:
            test_paths.extend(self._discover_tests_for_file(file_path))

        return list(set(test_paths))  # Deduplicate

    def _discover_tests_for_file(self, file_path: str) -> list[str]:
        """Discover all test files for a single production file."""
        if not file_path.startswith("src/"):
            return []

        relative = file_path[4:]  # Remove 'src/' prefix

        if not relative.endswith(".py"):
            return []

        relative = relative[:-3]  # Remove .py extension
        parts = relative.split("/")

        tests = []

        # Strategy 1: tests/foo/test_bar.py
        tests.extend(self._find_direct_test_file(parts))

        # Strategy 2: tests/foo/bar/test_*.py
        tests.extend(self._find_test_directory(relative))

        # Strategy 3: For __init__.py, find tests in parent directory
        if parts[-1] == "__init__":
            tests.extend(self._find_init_tests(parts))

        return tests

    def _find_direct_test_file(self, parts: list[str]) -> list[str]:
        """Find tests/foo/test_bar.py for src/foo/bar.py"""
        test_file = self.tests_dir / "/".join(parts[:-1]) / f"test_{parts[-1]}.py"

        if test_file.exists():
            return [str(test_file.relative_to(self._paths.repo_root))]

        return []

    def _find_test_directory(self, relative: str) -> list[str]:
        """Find tests/foo/bar/test_*.py for src/foo/bar.py"""
        test_dir = self.tests_dir / relative

        if not test_dir.exists() or not test_dir.is_dir():
            return []

        return [
            str(test_file.relative_to(self._paths.repo_root))
            for test_file in test_dir.glob("test_*.py")
        ]

    def _find_init_tests(self, parts: list[str]) -> list[str]:
        """Find tests/foo/test_*.py for src/foo/__init__.py"""
        test_dir = self.tests_dir / "/".join(parts[:-1])

        if not test_dir.exists():
            return []

        return [
            str(test_file.relative_to(self._paths.repo_root))
            for test_file in test_dir.glob("test_*.py")
        ]
