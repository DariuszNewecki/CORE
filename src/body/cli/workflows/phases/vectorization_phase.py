# src/body/cli/workflows/phases/vectorization_phase.py
"""Vectorization phase - constitutional vectors and knowledge graph."""

from __future__ import annotations

import time
import traceback
from typing import Any

import typer
from rich.console import Console

from body.cli.workflows.dev_sync_reporter import DevSyncReporter
from features.introspection.vectorization_service import run_vectorize
from shared.action_types import ActionResult
from shared.context import CoreContext
from shared.infrastructure.vector.adapters.constitutional_adapter import (
    ConstitutionalAdapter,
)
from shared.infrastructure.vector.vector_index_service import VectorIndexService


# ID: 9b697ab9-f6b1-484c-9569-3395dc7aad0f
class VectorizationPhase:
    """Executes vectorization operations."""

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

        # Sync constitutional vectors
        await self._sync_constitutional_vectors(phase)

        # Vectorize knowledge graph
        await self._vectorize_knowledge_graph(phase)

    async def _sync_constitutional_vectors(self, phase: Any) -> None:
        """Sync policy and pattern vectors."""
        try:
            start = time.time()
            self.console.print("[cyan]Syncing constitutional vectors...[/cyan]")

            adapter = ConstitutionalAdapter()

            # Policies
            policy_items = adapter.policies_to_items()
            assert (
                self.core_context.qdrant_service is not None
            ), "QdrantService not initialized"
            policy_service = VectorIndexService(
                self.core_context.qdrant_service,
                "core_policies",
            )
            await policy_service.ensure_collection()
            if not self.dry_run:
                await policy_service.index_items(policy_items)

            # Patterns
            pattern_items = adapter.patterns_to_items()
            assert (
                self.core_context.qdrant_service is not None
            ), "QdrantService not initialized"
            pattern_service = VectorIndexService(
                self.core_context.qdrant_service,
                "core-patterns",
            )
            await pattern_service.ensure_collection()
            if not self.dry_run:
                await pattern_service.index_items(pattern_items)

            self.reporter.record_result(
                ActionResult(
                    action_id="manage.vectors.sync",
                    ok=True,
                    data={
                        "policies_count": len(policy_items),
                        "patterns_count": len(pattern_items),
                        "dry_run": self.dry_run,
                    },
                    duration_sec=time.time() - start,
                ),
                phase,
            )

        except Exception as e:
            self.reporter.record_result(
                ActionResult(
                    action_id="manage.vectors.sync",
                    ok=False,
                    data={"error": str(e)},
                ),
                phase,
            )
            self.console.print(f"[yellow]⚠️  Constitutional sync warning: {e}[/yellow]")

    async def _vectorize_knowledge_graph(self, phase: Any) -> None:
        """Vectorize knowledge graph symbols."""
        try:
            start = time.time()
            self.console.print("[cyan]Vectorizing knowledge graph...[/cyan]")
            async with self.session_factory() as session:
                await run_vectorize(
                    context=self.core_context,
                    session=session,
                    dry_run=self.dry_run,
                    force=False,
                )

            self.reporter.record_result(
                ActionResult(
                    action_id="run.vectorize",
                    ok=True,
                    data={"status": "completed"},
                    duration_sec=time.time() - start,
                ),
                phase,
            )
        except Exception as e:
            error_details = traceback.format_exc()
            self.console.print(f"[red]❌ Vectorization failed: {e}[/red]")
            self.console.print(f"[dim]{error_details}[/dim]")
            self.reporter.record_result(
                ActionResult(
                    action_id="run.vectorize",
                    ok=False,
                    data={"error": str(e), "traceback": error_details},
                ),
                phase,
            )
            raise typer.Exit(1)
