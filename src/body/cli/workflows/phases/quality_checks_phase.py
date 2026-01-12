# src/body/cli/workflows/phases/quality_checks_phase.py
"""Quality checks phase - linting and contract verification."""

from __future__ import annotations

import time
from typing import Any

from rich.console import Console

from body.cli.logic.body_contracts_checker import check_body_contracts
from body.cli.workflows.dev_sync_reporter import DevSyncReporter
from mind.enforcement.audit import lint
from shared.action_types import ActionResult


# ID: eb2ce29a-50cd-44f2-ac8e-a07c0581278d
class QualityChecksPhase:
    """Executes quality checking operations."""

    def __init__(
        self,
        reporter: DevSyncReporter,
        console: Console,
    ):
        self.reporter = reporter
        self.console = console

    # ID: e119d8ac-f61b-494d-b9ac-2a4abf25b2da
    async def execute(self) -> None:
        """Execute all quality checks."""
        phase = self.reporter.start_phase("Quality Checks")

        # Run linter
        await self._run_lint(phase)

        # Check body contracts
        await self._check_body_contracts(phase)

    async def _run_lint(self, phase: Any) -> None:
        """Run linting checks."""
        try:
            start = time.time()
            self.console.print("[cyan]Running linter...[/cyan]")
            lint()

            self.reporter.record_result(
                ActionResult(
                    action_id="check.lint",
                    ok=True,
                    data={"status": "passed"},
                    duration_sec=time.time() - start,
                ),
                phase,
            )
        except Exception as e:
            self.reporter.record_result(
                ActionResult(
                    action_id="check.lint",
                    ok=False,
                    data={"error": str(e)},
                    warnings=["Linting failed"],
                ),
                phase,
            )
            self.console.print(
                "[yellow]⚠️  Lint failures detected, continuing...[/yellow]"
            )

    async def _check_body_contracts(self, phase: Any) -> None:
        """Verify Body layer contracts."""
        try:
            start = time.time()
            self.console.print("[cyan]Checking Body contracts...[/cyan]")
            await check_body_contracts()

            self.reporter.record_result(
                ActionResult(
                    action_id="check.body-contracts",
                    ok=True,
                    data={},
                    duration_sec=time.time() - start,
                ),
                phase,
            )
        except Exception as e:
            self.reporter.record_result(
                ActionResult(
                    action_id="check.body-contracts",
                    ok=False,
                    data={"error": str(e)},
                    warnings=["Body contract check failed"],
                ),
                phase,
            )
            self.console.print(
                "[yellow]⚠️  Body contract issues detected, continuing...[/yellow]"
            )
