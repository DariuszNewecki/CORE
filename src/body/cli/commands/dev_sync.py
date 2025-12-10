# src/body/cli/commands/dev_sync.py
"""
Dev sync workflow orchestrator.

Replaces the Makefile's dev-sync target with a governed Python workflow.
Refactored to use direct service calls (Internal Orchestration) instead of subprocesses.
"""

from __future__ import annotations

import time

import typer
from rich.console import Console

# --- Internal Logic Imports ---
from body.cli.commands.fix.code_style import fix_headers_internal
from body.cli.commands.fix.metadata import fix_ids_internal
from body.cli.commands.fix_logging import LoggingFixer
from body.cli.logic.audit import lint
from body.cli.logic.body_contracts_checker import check_body_contracts
from body.cli.logic.duplicates import inspect_duplicates_async

# --- Shared Utilities ---
from body.cli.workflows.dev_sync_reporter import DevSyncReporter
from features.introspection.sync_service import run_sync_with_db
from features.introspection.vectorization_service import run_vectorize
from features.project_lifecycle.definition_service import _define_new_symbols
from features.self_healing.code_style_service import format_code
from features.self_healing.docstring_service import fix_docstrings
from features.self_healing.sync_vectors import main_async as sync_vectors_async
from services.vector.adapters.constitutional_adapter import ConstitutionalAdapter
from services.vector.vector_index_service import VectorIndexService
from shared.action_types import ActionResult
from shared.activity_logging import activity_run
from shared.cli_utils import core_command
from shared.config import settings
from shared.context import CoreContext


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
        False,
        "--write/--dry-run",
        help="Dry-run by default; use --write to apply changes",
    ),
) -> None:
    """
    Run the comprehensive dev-sync workflow.

    By default this runs in DRY-RUN mode (no writes).
    Pass --write to apply changes to the repository and related indices.
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
        console.print("[cyan]Assigning stable IDs...[/cyan]")
        result = await fix_ids_internal(write=write)
        reporter.record_result(result, phase)
        if not result.ok:
            raise typer.Exit(1)

        # 2. Fix Headers
        console.print("[cyan]Checking file headers...[/cyan]")
        result = await fix_headers_internal(write=write)
        reporter.record_result(result, phase)
        if not result.ok:
            raise typer.Exit(1)

        # 3. Fix Logging Standards
        try:
            start = time.time()
            console.print("[cyan]Checking logging standards...[/cyan]")
            # Logging fixer is fast/silent enough to use a spinner if we wanted,
            # but keeping it consistent with the rest.
            fixer = LoggingFixer(settings.REPO_PATH, dry_run=dry_run)
            fix_stats = fixer.fix_all()

            reporter.record_result(
                ActionResult(
                    action_id="fix.logging",
                    ok=True,
                    data=fix_stats,
                    duration_sec=time.time() - start,
                ),
                phase,
            )
        except Exception as e:
            reporter.record_result(
                ActionResult(
                    action_id="fix.logging",
                    ok=False,
                    data={"error": str(e)},
                ),
                phase,
            )
            console.print("[yellow]⚠ Logging fix issues, continuing...[/yellow]")

        # 4. Fix Docstrings
        try:
            start = time.time()
            console.print("[cyan]Checking docstrings...[/cyan]")
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
                    action_id="fix.docstrings",
                    ok=False,
                    data={"error": str(e)},
                ),
                phase,
            )
            raise typer.Exit(1)

        # 5. Code Style
        try:
            start = time.time()
            console.print("[cyan]Formatting code...[/cyan]")
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
                    action_id="fix.code-style",
                    ok=False,
                    data={"error": str(e)},
                ),
                phase,
            )
            raise typer.Exit(1)

        # =================================================================
        # PHASE 2: QUALITY CHECKS
        # =================================================================
        phase = reporter.start_phase("Quality Checks")

        # 6. Lint
        try:
            start = time.time()
            console.print("[cyan]Running linter...[/cyan]")
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
        # PHASE 3: BODY CONTRACTS
        # =================================================================
        phase = reporter.start_phase("Body Contracts")

        try:
            start = time.time()
            console.print("[cyan]Checking Body contracts...[/cyan]")
            contracts_result = await check_body_contracts()

            # Attach timing to the ActionResult
            contracts_result.duration_sec = time.time() - start  # type: ignore[attr-defined]
            reporter.record_result(contracts_result, phase)

            data = contracts_result.data or {}
            violations = data.get("violations", []) or []
            rules = data.get("rules_triggered", []) or []

            if violations:
                console.print(
                    f"[bold cyan]Body Contracts:[/bold cyan] "
                    f"{len(violations)} violation(s), "
                    f"rules: {', '.join(rules) if rules else 'none'}"
                )

            # Print first few violations so we see where to start
            for v in violations[:10]:
                file = v.get("file", "?")
                line = v.get("line", "?")
                rule_id = v.get("rule_id", "?")
                msg = v.get("message", "")
                console.print(
                    f"  • [red]{rule_id}[/red] in [magenta]{file}[/magenta]:{line} - {msg}"
                )

            if len(violations) > 10:
                console.print(
                    f"[dim]  … and {len(violations) - 10} more violation(s).[/dim]"
                )

            if not contracts_result.ok:
                console.print(
                    "[red]❌ Body contracts violations detected. "
                    "See above for details.[/red]"
                )
                # Governance failure is a hard stop
                raise typer.Exit(1)

        except Exception as e:
            reporter.record_result(
                ActionResult(
                    action_id="check.body-contracts",
                    ok=False,
                    data={"error": str(e)},
                    warnings=["Body Contracts checker crashed unexpectedly."],
                ),
                phase,
            )
            # If governance layer fails, we stop.
            raise typer.Exit(1)

        # =================================================================
        # PHASE 4: DATABASE SYNC
        # =================================================================
        phase = reporter.start_phase("Database Sync")

        # 7. Vector Sync
        try:
            start = time.time()
            console.print("[cyan]Synchronizing vectors (cleaning orphans)...[/cyan]")
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
                    action_id="fix.vector-sync",
                    ok=False,
                    data={"error": str(e)},
                ),
                phase,
            )
            raise typer.Exit(1)

        # 8. Sync Knowledge
        try:
            start = time.time()
            if write:
                console.print("[cyan]Syncing knowledge to database...[/cyan]")
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
                    action_id="manage.sync-knowledge",
                    ok=False,
                    data={"error": str(e)},
                ),
                phase,
            )
            raise typer.Exit(1)

        # 9. Define Symbols
        try:
            start = time.time()
            console.print("[cyan]Defining symbols...[/cyan]")

            ctx_service = core_context.context_service
            # The factory initializes these as None; we must inject the live instances
            if not ctx_service.cognitive_service:
                ctx_service.cognitive_service = core_context.cognitive_service

            # Also update the vector provider inside context service if needed
            if not ctx_service.vector_provider.qdrant:
                ctx_service.vector_provider.qdrant = core_context.qdrant_service
            if not ctx_service.vector_provider.cognitive_service:
                ctx_service.vector_provider.cognitive_service = (
                    core_context.cognitive_service
                )

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
            # Non-blocking, but recorded as a failed action
            reporter.record_result(
                ActionResult(
                    action_id="manage.define-symbols",
                    ok=False,
                    data={"error": str(e)},
                ),
                phase,
            )
            console.print("[yellow]⚠ Symbol definition issue, continuing...[/yellow]")

        # =================================================================
        # PHASE 5: VECTORIZATION
        # =================================================================
        phase = reporter.start_phase("Vectorization")

        # 10. Sync Constitutional Vectors (Policies/Patterns)
        try:
            start = time.time()
            console.print("[cyan]Syncing constitutional vectors...[/cyan]")

            adapter = ConstitutionalAdapter()

            # Policies
            policy_items = adapter.policies_to_items()
            policy_service = VectorIndexService(
                core_context.qdrant_service,
                "core_policies",
            )
            await policy_service.ensure_collection()
            if not dry_run:
                await policy_service.index_items(policy_items)

            # Patterns
            pattern_items = adapter.patterns_to_items()
            pattern_service = VectorIndexService(
                core_context.qdrant_service,
                "core-patterns",
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
                    action_id="manage.vectors.sync",
                    ok=False,
                    data={"error": str(e)},
                ),
                phase,
            )
            console.print(f"[yellow]⚠ Constitutional sync warning: {e}[/yellow]")

        # 11. Vectorize Knowledge Graph
        try:
            start = time.time()
            console.print("[cyan]Vectorizing knowledge graph...[/cyan]")
            await run_vectorize(
                context=core_context,
                dry_run=dry_run,
                force=False,
            )

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
                    action_id="run.vectorize",
                    ok=False,
                    data={"error": str(e)},
                ),
                phase,
            )
            raise typer.Exit(1)

        # =================================================================
        # PHASE 6: ANALYSIS
        # =================================================================
        phase = reporter.start_phase("Code Analysis")

        # 12. Duplicates
        try:
            start = time.time()
            console.print("[cyan]Detecting duplicate code...[/cyan]")
            await inspect_duplicates_async(
                context=core_context,
                threshold=0.96,
            )

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
                    action_id="inspect.duplicates",
                    ok=False,
                    data={"error": str(e)},
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
                "fix.logging",
            ]
        ]

        if critical_failures:
            raise typer.Exit(1)


@dev_sync_app.command("fix-logging")
@core_command(dangerous=True, confirmation=True)
# ID: 0958b077-78bb-40ff-92bb-8a94f41a36db
async def fix_logging_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write/--dry-run", help="Apply fixes (default: dry-run)"
    ),
) -> None:
    """
    Fix logging standards violations (LOG-001, LOG-004).

    Converts console.print/status to logger calls in logic layers.
    """
    from body.cli.commands.fix_logging import LoggingFixer

    dry_run = not write
    fixer = LoggingFixer(settings.REPO_PATH, dry_run=dry_run)

    console.print("[bold cyan]Fixing Logging Violations[/bold cyan]")
    console.print(f"Mode: {'DRY RUN' if dry_run else 'WRITE'}")

    result = fixer.fix_all()

    console.print("\n[bold]Results:[/bold]")
    console.print(f"  Files modified: {result['files_modified']}")
    console.print(f"  Fixes applied: {result['fixes_applied']}")

    if dry_run:
        console.print(
            "\n[yellow]DRY RUN complete. Use --write to apply changes.[/yellow]"
        )
    else:
        console.print("\n[green]✓ Logging fixes applied successfully.[/green]")
