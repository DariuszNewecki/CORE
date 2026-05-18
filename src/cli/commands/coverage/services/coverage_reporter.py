# src/cli/commands/coverage/services/coverage_reporter.py
"""Service for generating coverage reports.

Thin client over GET /v1/coverage/report (ADR-057 D1). The API runs
coverage.py server-side and returns the report shape; CLI no longer
shells out to subprocess directly.
"""

from __future__ import annotations

import logging
from pathlib import Path

from api.cli import CoreApiClient


logger = logging.getLogger(__name__)


# ID: 2b3c4d5e-6f7a-8b9c-0d1e-2f3a4b5c6d7e
class CoverageReporter:
    """Generates coverage reports via the API."""

    def __init__(self, repo_path: Path):
        # repo_path retained for call-site compatibility; the API resolves
        # the repo root server-side now.
        self.repo_path = repo_path
        self.coverage_file = repo_path / ".coverage"

    # ID: 45deb3d8-4955-4912-b017-659a6ee885b4
    def has_coverage_data(self) -> bool:
        """Check if coverage data exists locally.

        Filesystem check — kept client-side to short-circuit calls when
        the user hasn't run pytest yet.
        """
        return self.coverage_file.exists()

    # ID: 052d759d-022b-4094-a850-c8afbb11f2a7
    async def generate_text_report(self, show_missing: bool = True) -> str:
        """Generate text coverage report via the API.

        Args:
            show_missing: Include line numbers of missing coverage

        Returns:
            Report output as string

        Raises:
            RuntimeError: If the API call fails
        """
        client = CoreApiClient()
        payload = await client.coverage_report(show_missing=show_missing)
        if not payload.get("ok", False):
            error_msg = payload.get("summary") or "Coverage report failed"
            raise RuntimeError(f"Coverage report failed: {error_msg}")
        return "\n".join(payload.get("stdout_tail", []))

    # ID: 2abbdff3-b661-4736-abea-69e89e7e383e
    def generate_html_report(self) -> Path:
        """Generate HTML coverage report.

        Returns:
            Path where HTML output would be written.

        Note:
            No HTML endpoint exposed yet — the path is returned so the
            CLI can surface where the report would live. Closing this
            requires a /coverage/report?format=html endpoint.
        """
        # SUPPRESS architecture.cli.api_only: no /v1/coverage/report?format=html
        # endpoint exists yet. CLI returns the conventional path so the
        # operator can re-run via the API once the endpoint is added.
        return self.repo_path / "htmlcov"
