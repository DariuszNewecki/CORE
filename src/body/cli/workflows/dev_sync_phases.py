# src/body/cli/workflows/dev_sync_phases.py
"""
Dev sync workflow phase execution.

Modularizes the dev-sync workflow into manageable, testable phases.
Each phase handles its own execution, error handling, and reporting.
"""

from __future__ import annotations

import time
from typing import Any

import typer
from rich.console import Console

from body.cli.commands.fix.code_style import fix_headers_internal
from body.cli.commands.fix.metadata import fix_ids_internal
from body.cli.commands.fix_logging import LoggingFixer
from body.cli.logic.body_contracts_checker import check_body_contracts
from body.cli.logic.duplicates import inspect_duplicates_async
from body.cli.workflows.dev_sync_reporter import DevSyncReporter
from features.introspection.sync_service import run_sync_with_db
from features.introspection.vectorization_service import run_vectorize
from features.project_lifecycle.definition_service import define_symbols
from features.self_healing.code_style_service import format_code
from features.self_healing.docstring_service import fix_docstrings
from features.self_healing.sync_vectors import main_async as sync_vectors_async
from mind.enforcement.audit import lint
from shared.action_types import ActionResult
from shared.config import settings
from shared.context import CoreContext
from shared.infrastructure.vector.adapters.constitutional_adapter import (
    ConstitutionalAdapter,
)
from shared.infrastructure.vector.vector_index_service import VectorIndexService


# ID: 1d7f96e0-3fc3-4453-ae6b-e42aa17504b9
class DevSyncPhases:
    """Executes dev-sync workflow phases with proper error handling and reporting."""

    def __init__(
        self,
        core_context: CoreContext,
        reporter: DevSyncReporter,
        console: Console,
        write: bool,
        dry_run: bool,
        session_factory: Any,  # get_session callable
    ):
        self.core_context = core_context
        self.reporter = reporter
        self.console = console
        self.write = write
        self.dry_run = dry_run
        self.session_factory = session_factory

    # ID: b2a2a398-5ba9-4779-ad8d-32e1ccd1d7ef
    def has_critical_failures(self) -> bool:
        """Check if any critical failures occurred."""
        non_critical = {
            "check.lint",
            "manage.define-symbols",
            "inspect.duplicates",
            "manage.vectors.sync",
            "fix.logging",
        }

        for phase in self.reporter.phases:
            for result in phase.results:
                if not result.ok and result.action_id not in non_critical:
                    return True
        return False

    # =========================================================================
    # PHASE 1: CODE FIXERS
    # =========================================================================

    # ID: 62bb1514-6702-40b0-bc18-1fce5d2852fd
    async def run_code_fixers(self) -> None:
        """Execute code fixing phase."""
        phase = self.reporter.start_phase("Code Fixers")

        # Fix IDs
        self.console.print("[cyan]Assigning stable IDs...[/cyan]")
        result = await fix_ids_internal(write=self.write)
        self.reporter.record_result(result, phase)
        if not result.ok:
            raise typer.Exit(1)

        # Fix Headers
        self.console.print("[cyan]Checking file headers...[/cyan]")
        result = await fix_headers_internal(write=self.write)
        self.reporter.record_result(result, phase)
        if not result.ok:
            raise typer.Exit(1)

        # Fix Logging
        await self._fix_logging(phase)

        # Fix Docstrings
        await self._fix_docstrings(phase)

        # Format Code
        await self._format_code(phase)

    async def _fix_logging(self, phase: Any) -> None:
        """Fix logging standards."""
        try:
            start = time.time()
            self.console.print("[cyan]Checking logging standards...[/cyan]")
            fixer = LoggingFixer(settings.REPO_PATH, dry_run=self.dry_run)
            fix_stats = fixer.fix_all()

            self.reporter.record_result(
                ActionResult(
                    action_id="fix.logging",
                    ok=True,
                    data=fix_stats,
                    duration_sec=time.time() - start,
                ),
                phase,
            )
        except Exception as e:
            self.reporter.record_result(
                ActionResult(
                    action_id="fix.logging",
                    ok=False,
                    data={"error": str(e)},
                ),
                phase,
            )
            self.console.print("[yellow]⚠️  Logging fix issues, continuing...[/yellow]")

    async def _fix_docstrings(self, phase: Any) -> None:
        """Fix missing docstrings."""
        try:
            start = time.time()
            self.console.print("[cyan]Checking docstrings...[/cyan]")
            await fix_docstrings(context=self.core_context, write=self.write)

            self.reporter.record_result(
                ActionResult(
                    action_id="fix.docstrings",
                    ok=True,
                    data={"status": "completed"},
                    duration_sec=time.time() - start,
                ),
                phase,
            )
        except Exception as e:
            self.reporter.record_result(
                ActionResult(
                    action_id="fix.docstrings",
                    ok=False,
                    data={"error": str(e)},
                ),
                phase,
            )
            raise typer.Exit(1)

    async def _format_code(self, phase: Any) -> None:
        """Format code with Black/Ruff."""
        try:
            start = time.time()
            self.console.print("[cyan]Formatting code...[/cyan]")
            format_code()

            self.reporter.record_result(
                ActionResult(
                    action_id="fix.code-style",
                    ok=True,
                    data={"status": "completed"},
                    duration_sec=time.time() - start,
                ),
                phase,
            )
        except Exception as e:
            self.reporter.record_result(
                ActionResult(
                    action_id="fix.code-style",
                    ok=False,
                    data={"error": str(e)},
                ),
                phase,
            )
            raise typer.Exit(1)

    # =========================================================================
    # PHASE 2: QUALITY CHECKS
    # =========================================================================

    # ID: eb2ce29a-50cd-44f2-ac8e-a07c0581278d
    async def run_quality_checks(self) -> None:
        """Execute quality checking phase."""
        phase = self.reporter.start_phase("Quality Checks")

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

    # =========================================================================
    # PHASE 3: BODY CONTRACTS
    # =========================================================================

    # ID: 10bcea1c-8e82-45ec-82af-57fe7f433d5c
    async def run_body_contracts(self) -> None:
        """Execute Body contracts checking phase."""
        phase = self.reporter.start_phase("Body Contracts")

        try:
            start = time.time()
            self.console.print("[cyan]Checking Body contracts...[/cyan]")
            contracts_result = await check_body_contracts()
            contracts_result.duration_sec = time.time() - start  # type: ignore

            self.reporter.record_result(contracts_result, phase)
            self._print_contract_violations(contracts_result)

            if not contracts_result.ok:
                self.console.print("[red]❌ Body contracts violations detected.[/red]")
                raise typer.Exit(1)

        except typer.Exit:
            raise
        except Exception as e:
            self.reporter.record_result(
                ActionResult(
                    action_id="check.body-contracts",
                    ok=False,
                    data={"error": str(e)},
                    warnings=["Body Contracts checker crashed unexpectedly."],
                ),
                phase,
            )
            raise typer.Exit(1)

    def _print_contract_violations(self, result: ActionResult) -> None:
        """Print contract violations in a readable format."""
        data = result.data or {}
        violations = data.get("violations", []) or []
        rules = data.get("rules_triggered", []) or []

        if violations:
            self.console.print(
                f"[bold cyan]Body Contracts:[/bold cyan] "
                f"{len(violations)} violation(s), "
                f"rules: {', '.join(rules) if rules else 'none'}"
            )

            for v in violations[:10]:
                file = v.get("file", "?")
                line = v.get("line", "?")
                rule_id = v.get("rule_id", "?")
                msg = v.get("message", "")
                self.console.print(
                    f"  • [red]{rule_id}[/red] in [magenta]{file}[/magenta]:{line} - {msg}"
                )

            if len(violations) > 10:
                self.console.print(
                    f"[dim]  … and {len(violations) - 10} more violation(s).[/dim]"
                )

    # =========================================================================
    # PHASE 4: DATABASE SYNC
    # =========================================================================

    # ID: 49bde2f1-5237-402a-8f01-0db266b785a4
    async def run_database_sync(self) -> None:
        """Execute database synchronization phase."""
        phase = self.reporter.start_phase("Database Sync")

        # Vector sync
        await self._sync_vectors(phase)

        # Knowledge sync
        await self._sync_knowledge(phase)

        # Define symbols
        await self._define_symbols(phase)

    async def _sync_vectors(self, phase: Any) -> None:
        """Synchronize vector database."""
        try:
            start = time.time()
            self.console.print(
                "[cyan]Synchronizing vectors (cleaning orphans)...[/cyan]"
            )
            # FIXED: Inject session for DI compliance
            async with self.session_factory() as session:
                orphans, dangling = await sync_vectors_async(
                    session=session,
                    write=self.write,
                    dry_run=self.dry_run,
                    qdrant_service=self.core_context.qdrant_service,
                )

            self.reporter.record_result(
                ActionResult(
                    action_id="fix.vector-sync",
                    ok=True,
                    data={"orphans_pruned": orphans, "dangling_pruned": dangling},
                    duration_sec=time.time() - start,
                ),
                phase,
            )
        except Exception as e:
            self.reporter.record_result(
                ActionResult(
                    action_id="fix.vector-sync",
                    ok=False,
                    data={"error": str(e)},
                ),
                phase,
            )
            raise typer.Exit(1)

    async def _sync_knowledge(self, phase: Any) -> None:
        """Sync knowledge graph to database."""
        try:
            start = time.time()
            if self.write:
                self.console.print("[cyan]Syncing knowledge to database...[/cyan]")
                # FIXED: Pass session to run_sync_with_db
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

            # FIXED: Pass session_factory for proper DI
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

    # =========================================================================
    # PHASE 5: VECTORIZATION
    # =========================================================================

    # ID: 9b697ab9-f6b1-484c-9569-3395dc7aad0f
    async def run_vectorization(self) -> None:
        """Execute vectorization phase."""
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
            # FIXED: Inject session for DI compliance
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
            import traceback

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

    # =========================================================================
    # PHASE 6: CODE ANALYSIS
    # =========================================================================

    # ID: 4e6cbfc4-7ce7-4adc-980d-90c315da8123
    async def run_code_analysis(self) -> None:
        """Execute code analysis phase."""
        phase = self.reporter.start_phase("Code Analysis")

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
