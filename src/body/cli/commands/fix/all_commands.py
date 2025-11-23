# src/body/cli/commands/fix/all_commands.py
"""
Batch execution command(s) for the 'fix' CLI group.

Provides:
- core-admin fix all
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import typer

from features.maintenance.command_sync_service import _sync_commands_to_db
from features.self_healing.code_style_service import format_code
from features.self_healing.docstring_service import fix_docstrings
from features.self_healing.id_tagging_service import assign_missing_ids
from features.self_healing.policy_id_service import add_missing_policy_ids
from features.self_healing.purge_legacy_tags_service import purge_legacy_tags
from features.self_healing.sync_vectors import main_async as sync_vectors_async
from shared.cli_utils import async_command
from shared.context import CoreContext

from . import (
    COMMAND_CONFIG,
    console,
    fix_app,
    handle_command_errors,
)
from .fix_ir import (
    fix_ir_log,
    fix_ir_triage,
)


def _run_sync_step(label: str, func: Callable[[], Any]) -> None:
    """Run a synchronous step with a Rich status spinner."""
    with console.status(f"[cyan]{label}...[/cyan]"):
        func()


async def _run_async_step(label: str, coro: Awaitable[Any]) -> None:
    """Run an async step with a Rich status spinner."""
    with console.status(f"[cyan]{label}...[/cyan]"):
        await coro


@fix_app.command("all", help="Run a curated sequence of self-healing fixes.")
@handle_command_errors
@async_command
# ID: 690a63fb-8a43-47cc-af16-ecbac5663ded
async def run_all_fixes(
    ctx: typer.Context,
    skip_dangerous: bool = typer.Option(
        True, help="Skip potentially dangerous operations that modify code."
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be fixed without making changes where supported.",
    ),
) -> None:
    """
    Run a curated set of fix subcommands in a sensible order.

    Implementation notes:
    - This function is async and uses `@async_command`, so it owns the event loop.
    - We call underlying service functions directly (not async CLI wrappers)
      to avoid nested asyncio.run() calls.
    - Commands that require an explicit file path (clarity, complexity, line-lengths)
      are not invoked automatically and remain targeted tools.
    """
    core_context: CoreContext = ctx.obj
    write = not dry_run

    async def _run(name: str) -> None:
        cfg = COMMAND_CONFIG.get(name, {})
        is_dangerous = cfg.get("dangerous", False)

        if skip_dangerous and is_dangerous:
            console.print(
                f"[yellow]Skipping dangerous command 'fix {name}' "
                f"(skip_dangerous=True).[/yellow]"
            )
            return

        console.print(
            f"[bold cyan]▶ Running 'fix {name}' "
            f"(dangerous={is_dangerous}, dry_run={dry_run})[/bold cyan]"
        )

        # --- Formatting & style ---
        if name == "code-style":
            _run_sync_step("Formatting code (Black & Ruff)", format_code)

        elif name == "line-lengths":
            # Keep this as a manual tool for now due to async orchestration clashes.
            console.print(
                "[yellow]Skipping 'fix line-lengths' in 'fix all' because it is "
                "designed as a targeted, file-aware async command. "
                "Run it manually when needed.[/yellow]"
            )

        # --- Metadata & IDs ---
        elif name == "ids":
            _run_sync_step(
                "Assigning missing IDs",
                lambda: assign_missing_ids(dry_run=not write),
            )

        elif name == "purge-legacy-tags":
            _run_sync_step(
                "Purging legacy capability tags",
                lambda: purge_legacy_tags(dry_run=not write),
            )

        elif name == "policy-ids":
            _run_sync_step(
                "Adding missing policy IDs",
                lambda: add_missing_policy_ids(dry_run=not write),
            )

        elif name == "duplicate-ids":
            # Temporarily keep this as a manual tool until the underlying
            # duplicate_id_service is repaired (missing features.governance import).
            console.print(
                "[yellow]Skipping 'fix duplicate-ids' in 'fix all' because its "
                "service depends on a missing 'features.governance' module. "
                "Run it manually later once that dependency is fixed.[/yellow]"
            )

        # --- Vector / DB sync ---
        elif name == "vector-sync":
            await _run_async_step(
                "Synchronizing vector database (Qdrant + PostgreSQL)",
                sync_vectors_async(write=write, dry_run=dry_run),
            )

        elif name == "db-registry":
            from body.cli.admin_cli import app as main_app

            await _run_async_step(
                "Syncing CLI commands to database",
                _sync_commands_to_db(main_app),
            )

        # --- Docstrings & tags (AI-powered) ---
        elif name == "docstrings":
            await _run_async_step(
                "Fixing docstrings",
                fix_docstrings(context=core_context, write=write),
            )

        elif name == "tags":
            from features.self_healing.capability_tagging_service import main_async

            await _run_async_step(
                "Tagging capabilities",
                main_async(write=write, dry_run=dry_run, core_context=core_context),
            )

        # --- IR bootstrap (sync wrappers are safe to call) ---
        elif name == "ir-triage":
            fix_ir_triage(write=write)

        elif name == "ir-log":
            fix_ir_log(write=write)

        # --- Commands requiring explicit file path: keep manual ---
        elif name in {"clarity", "complexity"}:
            console.print(
                f"[yellow]Skipping 'fix {name}' in 'fix all' because it requires "
                "an explicit file path. Run it manually when needed.[/yellow]"
            )
        else:
            console.print(
                f"[yellow]No orchestrated handler defined for 'fix {name}'. "
                "It can still be run manually.[/yellow]"
            )

    # Curated execution plan. Order matters.
    plan = [
        # Formatting & style
        "code-style",
        "line-lengths",
        # IDs & metadata hygiene
        "ids",
        "purge-legacy-tags",
        "policy-ids",
        "duplicate-ids",
        # Vector store sync (atomic operation replacing orphaned-vectors + dangling-vector-links)
        "vector-sync",
        "docstrings",
        "tags",
        # IR artifacts
        "ir-triage",
        "ir-log",
        # Explicit-file commands (documented but not auto-run)
        "clarity",
        "complexity",
        # Registry sync at the end
        "db-registry",
    ]

    for name in plan:
        await _run(name)

    console.print("[green]✅ 'fix all' sequence completed[/green]")
