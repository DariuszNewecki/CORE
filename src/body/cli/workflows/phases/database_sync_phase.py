# src/body/cli/workflows/phases/database_sync_phase.py
"""Database sync phase - knowledge sync and symbol definition."""

from __future__ import annotations

import time
from typing import Any

import typer
from rich.console import Console

from body.cli.workflows.dev_sync_reporter import DevSyncReporter
from features.introspection.sync_service import run_sync_with_db
from features.project_lifecycle.definition_service import define_symbols
from shared.action_types import ActionResult
from shared.context import CoreContext


# ID: a7f3e8c9-4d5b-4c6a-8e9f-1a2b3c4d5e6f
class DatabaseSyncPhase:
    """Executes database synchronization operations."""

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

    # ID: 9b125eee-f416-435f-b913-02f398d1e7f1
    async def execute(self) -> None:
        """Execute database sync operations."""
        phase = self.reporter.start_phase("Database Sync")

        # Sync knowledge graph
        await self._sync_knowledge(phase)

        # Define symbols
        await self._define_symbols(phase)

    async def _sync_knowledge(self, phase: Any) -> None:
        """Sync knowledge graph with database."""
        try:
            start = time.time()
            self.console.print("[cyan]Syncing knowledge graph...[/cyan]")
            if not self.dry_run:
                async with self.session_factory() as session:
                    stats = await run_sync_with_db(session)
                self.reporter.record_result(
                    ActionResult(
                        action_id="manage.sync-knowledge",
                        ok=True,
                        data=stats,
                        duration_sec=time.time() - start,
                    ),
                    phase,
                )
            else:
                self.console.print("[dim]Skipping knowledge sync (dry-run)[/dim]")
        except Exception as e:
            self.reporter.record_result(
                ActionResult(
                    action_id="manage.sync-knowledge",
                    ok=False,
                    data={"error": str(e)},
                ),
                phase,
            )
            raise typer.Exit(1)

    async def _define_symbols(self, phase: Any) -> None:
        """Define capability keys for symbols."""
        try:
            start = time.time()
            self.console.print("[cyan]Defining symbols...[/cyan]")

            ctx_service = self.core_context.context_service

            # Wire dependencies if missing
            if not ctx_service.cognitive_service:
                ctx_service.cognitive_service = self.core_context.cognitive_service
            if not ctx_service.vector_provider.qdrant:
                ctx_service.vector_provider.qdrant = self.core_context.qdrant_service
            if not ctx_service.vector_provider.cognitive_service:
                ctx_service.vector_provider.cognitive_service = (
                    self.core_context.cognitive_service
                )

            await define_symbols(ctx_service, self.session_factory)

            self.reporter.record_result(
                ActionResult(
                    action_id="manage.define-symbols",
                    ok=True,
                    data={},
                    duration_sec=time.time() - start,
                ),
                phase,
            )
        except Exception as e:
            self.reporter.record_result(
                ActionResult(
                    action_id="manage.define-symbols",
                    ok=False,
                    data={"error": str(e)},
                ),
                phase,
            )
            self.console.print(
                "[yellow]⚠️  Symbol definition issue, continuing...[/yellow]"
            )
