# src/body/cli/commands/coverage/services/coverage_reporter.py
"""Service for generating coverage reports."""

from __future__ import annotations

import subprocess
from pathlib import Path

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 2b3c4d5e-6f7a-8b9c-0d1e-2f3a4b5c6d7e
class CoverageReporter:
    """Generates coverage reports using coverage.py tool."""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.coverage_file = repo_path / ".coverage"

    # ID: 45deb3d8-4955-4912-b017-659a6ee885b4
    def has_coverage_data(self) -> bool:
        """Check if coverage data exists."""
        return self.coverage_file.exists()

    # ID: 052d759d-022b-4094-a850-c8afbb11f2a7
    def generate_text_report(self, show_missing: bool = True) -> str:
        """
        Generate text coverage report.

        Args:
            show_missing: Include line numbers of missing coverage

        Returns:
            Report output as string

        Raises:
            RuntimeError: If coverage tool fails
        """
        cmd = ["poetry", "run", "coverage", "report"]
        if show_missing:
            cmd.append("--show-missing")

        result = subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True)

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown failure"
            raise RuntimeError(f"Coverage report failed: {error_msg}")

        return result.stdout

    # ID: 2abbdff3-b661-4736-abea-69e89e7e383e
    def generate_html_report(self) -> Path:
        """
        Generate HTML coverage report.

        Returns:
            Path to generated HTML directory

        Raises:
            RuntimeError: If HTML generation fails
        """
        result = subprocess.run(
            ["poetry", "run", "coverage", "html"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown failure"
            raise RuntimeError(f"HTML generation failed: {error_msg}")

        return self.repo_path / "htmlcov"
