# src/will/workflows/phases/vectorization_phase.py
"""
Vectorization phase — delegates to the constitutional worker pipeline
via the sync.vectors.code and sync.vectors.constitution atomic actions.
"""

from __future__ import annotations

import time
from typing import Any

from rich.console import Console

from shared.action_types import ActionResult
from shared.context import CoreContext
from will.workflows.dev_sync_reporter import DevSyncReporter


# ID: dfc4107b-e6e6-42f6-b037-d1f160eda92b
class VectorizationPhase:
    """Executes vectorization operations via the constitutional action pipeline."""

    def __init__(
        self,
        core_context: CoreContext,
        reporter: DevSyncReporter,
        console: Console,
        dry_run: bool,
        session_factory: Any,
    ):
        self.core_context = core_context
        self.reporter = reporter
        self.console = console
        self.dry_run = dry_run
        self.session_factory = session_factory

    # ID: 0209b94e-8813-4f69-bab7-b94d0bc2661c
    async def execute(self) -> None:
        """Execute vectorization operations."""
        phase = self.reporter.start_phase("Vectorization")
        write = not self.dry_run

        await self._sync_constitutional_vectors(phase, write)
        await self._sync_code_vectors(phase, write)

    async def _sync_constitutional_vectors(self, phase: Any, write: bool) -> None:
        """Sync policy and pattern vectors via action executor."""
        start = time.time()
        try:
            self.console.print("[cyan]Syncing constitutional vectors...[/cyan]")
            result = await self.core_context.action_executor.execute(
                "sync.vectors.constitution", write=write
            )
            self.reporter.record_result(result, phase)
        except Exception as e:
            self.console.print(f"[yellow]⚠️  Constitutional sync warning: {e}[/yellow]")
            self.reporter.record_result(
                ActionResult(
                    action_id="sync.vectors.constitution",
                    ok=False,
                    data={"error": str(e)},
                    duration_sec=time.time() - start,
                ),
                phase,
            )

    async def _sync_code_vectors(self, phase: Any, write: bool) -> None:
        """Sync code vectors via RepoCrawlerWorker + RepoEmbedderWorker pipeline."""
        start = time.time()
        try:
            self.console.print("[cyan]Vectorizing codebase artifacts...[/cyan]")
            result = await self.core_context.action_executor.execute(
                "sync.vectors.code", write=write
            )
            self.reporter.record_result(result, phase)
        except Exception as e:
            self.console.print(f"[red]❌ Code vectorization failed: {e}[/red]")
            self.reporter.record_result(
                ActionResult(
                    action_id="sync.vectors.code",
                    ok=False,
                    data={"error": str(e)},
                    duration_sec=time.time() - start,
                ),
                phase,
            )
            raise
