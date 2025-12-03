# src/body/cli/commands/dev_sync.py
"""
Dev sync workflow orchestrator.

Replaces the Makefile's dev-sync target with a governed Python workflow.
Refactored to use direct service calls (Internal Orchestration) instead of subprocesses.
"""

from __future__ import annotations

import time

import typer
from features.introspection.sync_service import run_sync_with_db
from features.introspection.vectorization_service import run_vectorize
from features.project_lifecycle.definition_service import _define_new_symbols
from features.self_healing.code_style_service import format_code
from features.self_healing.docstring_service import fix_docstrings
from features.self_healing.sync_vectors import main_async as sync_vectors_async
from rich.console import Console
from services.vector.adapters.constitutional_adapter import ConstitutionalAdapter
from services.vector.vector_index_service import VectorIndexService
from shared.action_types import ActionResult
from shared.activity_logging import activity_run
from shared.cli_utils import core_command
from shared.config import settings
from shared.context import CoreContext

# --- Internal Logic Imports ---
from body.cli.commands.fix.code_style import fix_headers_internal
from body.cli.commands.fix.metadata import fix_ids_internal
from body.cli.logic.audit import lint

# CRITICAL FIX: Import the async version
from body.cli.logic.duplicates import inspect_duplicates_async

# --- Shared Utilities ---
from body.cli.workflows.dev_sync_reporter import DevSyncReporter

console = Console()

dev_sync_app = typer.Typer(
    help="Development synchronization workflows",
    no_args_is_help=True,
)


@dev_sync_app.command("sync")
@core_command(dangerous=True, confirmation=True)
# ID: 5e95ba26-057d-4e7c-b84c-75f7cc5091e0
async def dev_sync_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        True,
        "--write/--dry-run",
        help="Apply changes (default) or dry-run only",
    ),
) -> None:
    """
    Run the comprehensive dev-sync workflow.

    Executes services directly for maximum performance and shared state.
    """
    core_context: CoreContext = ctx.obj
    dry_run = not write

    with activity_run("dev.sync") as run:
        reporter = DevSyncReporter(run, repo_path=str(settings.REPO_PATH))
        reporter.print_header()

        # =================================================================
        # PHASE 1: CODE FIXERS
        # =================================================================
        phase = reporter.start_phase("Code Fixers")

        # 1. Fix IDs
        result = await fix_ids_internal(write=write)
        reporter.record_result(result, phase)
        if not result.ok:
            raise typer.Exit(1)

        # 2. Fix Headers
        result = await fix_headers_internal(write=write)
        reporter.record_result(result, phase)
        if not result.ok:
            raise typer.Exit(1)

        # 3. Fix Docstrings (Service Call)
        try:
            start = time.time()
            with console.status("[cyan]Fixing docstrings...[/cyan]"):
                await fix_docstrings(context=core_context, write=write)

            reporter.record_result(
                ActionResult(
                    action_id="fix.docstrings",
                    ok=True,
                    data={"status": "completed"},
                    duration_sec=time.time() - start,
                ),
                phase,
            )
        except Exception as e:
            reporter.record_result(
                ActionResult(
                    action_id="fix.docstrings", ok=False, data={"error": str(e)}
                ),
                phase,
            )
            raise typer.Exit(1)

        # 4. Code Style (Service Call - Sync)
        try:
            start = time.time()
            with console.status("[cyan]Formatting code...[/cyan]"):
                format_code()  # Sync function

            reporter.record_result(
                ActionResult(
                    action_id="fix.code-style",
                    ok=True,
                    data={"status": "completed"},
                    duration_sec=time.time() - start,
                ),
                phase,
            )
        except Exception as e:
            reporter.record_result(
                ActionResult(
                    action_id="fix.code-style", ok=False, data={"error": str(e)}
                ),
                phase,
            )
            raise typer.Exit(1)

        # =================================================================
        # PHASE 2: QUALITY CHECKS
        # =================================================================
        phase = reporter.start_phase("Quality Checks")

        # 5. Lint (Service Call - Sync)
        try:
            start = time.time()
            with console.status("[cyan]Running linter...[/cyan]"):
                lint()

            reporter.record_result(
                ActionResult(
                    action_id="check.lint",
                    ok=True,
                    data={"status": "passed"},
                    duration_sec=time.time() - start,
                ),
                phase,
            )
        except Exception as e:
            reporter.record_result(
                ActionResult(
                    action_id="check.lint",
                    ok=False,
                    data={"error": str(e)},
                    warnings=["Linting failed"],
                ),
                phase,
            )
            console.print("[yellow]⚠ Lint failures detected, continuing...[/yellow]")

        # =================================================================
        # PHASE 3: DATABASE SYNC
        # =================================================================
        phase = reporter.start_phase("Database Sync")

        # 6. Vector Sync (Service Call)
        try:
            start = time.time()
            with console.status("[cyan]Synchronizing vectors...[/cyan]"):
                orphans, dangling = await sync_vectors_async(
                    write=write,
                    dry_run=dry_run,
                    qdrant_service=core_context.qdrant_service,
                )

            reporter.record_result(
                ActionResult(
                    action_id="fix.vector-sync",
                    ok=True,
                    data={"orphans_pruned": orphans, "dangling_pruned": dangling},
                    duration_sec=time.time() - start,
                ),
                phase,
            )
        except Exception as e:
            reporter.record_result(
                ActionResult(
                    action_id="fix.vector-sync", ok=False, data={"error": str(e)}
                ),
                phase,
            )
            raise typer.Exit(1)

        # 7. Sync Knowledge (Service Call)
        try:
            start = time.time()
            if write:
                with console.status("[cyan]Syncing knowledge to database...[/cyan]"):
                    stats = await run_sync_with_db()
                reporter.record_result(
                    ActionResult(
                        action_id="manage.sync-knowledge",
                        ok=True,
                        data=stats,
                        duration_sec=time.time() - start,
                    ),
                    phase,
                )
            else:
                console.print("[dim]Skipping knowledge sync (dry-run)[/dim]")
        except Exception as e:
            reporter.record_result(
                ActionResult(
                    action_id="manage.sync-knowledge", ok=False, data={"error": str(e)}
                ),
                phase,
            )
            raise typer.Exit(1)

        # 8. Define Symbols (Service Call)
        try:
            start = time.time()
            with console.status("[cyan]Defining symbols...[/cyan]"):
                # Construct context service via factory if not already present
                ctx_service = core_context.context_service
                await _define_new_symbols(ctx_service)

            reporter.record_result(
                ActionResult(
                    action_id="manage.define-symbols",
                    ok=True,
                    data={},
                    duration_sec=time.time() - start,
                ),
                phase,
            )
        except Exception as e:
            # Non-blocking
            reporter.record_result(
                ActionResult(
                    action_id="manage.define-symbols", ok=False, data={"error": str(e)}
                ),
                phase,
            )
            console.print("[yellow]⚠ Symbol definition issue, continuing...[/yellow]")

        # =================================================================
        # PHASE 4: VECTORIZATION
        # =================================================================
        phase = reporter.start_phase("Vectorization")

        # 9. Sync Constitutional Vectors (Policies/Patterns)
        try:
            start = time.time()
            with console.status("[cyan]Syncing constitutional vectors...[/cyan]"):
                adapter = ConstitutionalAdapter()

                # Policies
                policy_items = adapter.policies_to_items()
                policy_service = VectorIndexService(
                    core_context.qdrant_service.client, "core_policies"
                )
                await policy_service.ensure_collection()
                if not dry_run:
                    await policy_service.index_items(policy_items)

                # Patterns
                pattern_items = adapter.patterns_to_items()
                pattern_service = VectorIndexService(
                    core_context.qdrant_service.client, "core-patterns"
                )
                await pattern_service.ensure_collection()
                if not dry_run:
                    await pattern_service.index_items(pattern_items)

            reporter.record_result(
                ActionResult(
                    action_id="manage.vectors.sync",
                    ok=True,
                    data={
                        "policies_count": len(policy_items),
                        "patterns_count": len(pattern_items),
                        "dry_run": dry_run,
                    },
                    duration_sec=time.time() - start,
                ),
                phase,
            )

        except Exception as e:
            reporter.record_result(
                ActionResult(
                    action_id="manage.vectors.sync", ok=False, data={"error": str(e)}
                ),
                phase,
            )
            console.print(f"[yellow]⚠ Constitutional sync warning: {e}[/yellow]")

        # 10. Vectorize Knowledge Graph (Service Call)
        try:
            start = time.time()
            with console.status("[cyan]Vectorizing knowledge graph...[/cyan]"):
                await run_vectorize(context=core_context, dry_run=dry_run, force=False)

            reporter.record_result(
                ActionResult(
                    action_id="run.vectorize",
                    ok=True,
                    data={"status": "completed"},
                    duration_sec=time.time() - start,
                ),
                phase,
            )
        except Exception as e:
            reporter.record_result(
                ActionResult(
                    action_id="run.vectorize", ok=False, data={"error": str(e)}
                ),
                phase,
            )
            raise typer.Exit(1)

        # =================================================================
        # PHASE 5: ANALYSIS
        # =================================================================
        phase = reporter.start_phase("Code Analysis")

        # 11. Duplicates
        try:
            start = time.time()
            with console.status("[cyan]Detecting duplicate code...[/cyan]"):
                # CRITICAL FIX: Use async version directly
                await inspect_duplicates_async(context=core_context, threshold=0.96)

            reporter.record_result(
                ActionResult(
                    action_id="inspect.duplicates",
                    ok=True,
                    data={},
                    duration_sec=time.time() - start,
                ),
                phase,
            )
        except Exception as e:
            reporter.record_result(
                ActionResult(
                    action_id="inspect.duplicates", ok=False, data={"error": str(e)}
                ),
                phase,
            )

        # =================================================================
        # FINAL REPORT
        # =================================================================
        reporter.print_phases()
        reporter.print_summary()

        # Exit with appropriate code
        critical_failures = [
            r
            for p in reporter.phases
            for r in p.results
            if not r.ok
            and r.action_id
            not in [
                "check.lint",
                "manage.define-symbols",
                "inspect.duplicates",
                "manage.vectors.sync",
            ]
        ]

        if critical_failures:
            raise typer.Exit(1)
