# src/body/cli/workflows/phases/code_analysis_phase.py
"""Code analysis phase - duplicate detection and code quality metrics."""

from __future__ import annotations

import time
from typing import Any

from rich.console import Console

from body.cli.logic.duplicates import inspect_duplicates_async
from body.cli.workflows.dev_sync_reporter import DevSyncReporter
from shared.action_types import ActionResult
from shared.context import CoreContext


# ID: 19d2867c-472b-4971-9eda-1bc3ee0e6e89
class CodeAnalysisPhase:
    """Executes code analysis operations."""

    def __init__(
        self,
        core_context: CoreContext,
        reporter: DevSyncReporter,
        console: Console,
    ):
        self.core_context = core_context
        self.reporter = reporter
        self.console = console

    # ID: 9c47a0b9-758a-4460-acc2-f3ae872a3a3b
    async def execute(self) -> None:
        """Execute code analysis operations."""
        phase = self.reporter.start_phase("Code Analysis")

        await self._detect_duplicates(phase)

    async def _detect_duplicates(self, phase: Any) -> None:
        """Detect duplicate code patterns."""
        try:
            start = time.time()
            self.console.print("[cyan]Detecting duplicate code...[/cyan]")
            await inspect_duplicates_async(
                context=self.core_context,
                threshold=0.96,
            )

            self.reporter.record_result(
                ActionResult(
                    action_id="inspect.duplicates",
                    ok=True,
                    data={},
                    duration_sec=time.time() - start,
                ),
                phase,
            )
        except Exception as e:
            self.reporter.record_result(
                ActionResult(
                    action_id="inspect.duplicates",
                    ok=False,
                    data={"error": str(e)},
                ),
                phase,
            )
