# src/body/cli/commands/fix/all_commands.py
"""
Batch execution command(s) for the 'fix' CLI group.

Provides:
- core-admin fix all

Refactored to use the Constitutional CLI Framework (@core_command).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import typer

from features.introspection.sync_service import run_sync_with_db
from features.maintenance.command_sync_service import _sync_commands_to_db
from features.self_healing.code_style_service import format_code
from features.self_healing.docstring_service import fix_docstrings
from features.self_healing.id_tagging_service import assign_missing_ids
from features.self_healing.policy_id_service import add_missing_policy_ids
from features.self_healing.purge_legacy_tags_service import purge_legacy_tags
from features.self_healing.sync_vectors import main_async as sync_vectors_async
from services.database.session_manager import get_session
from shared.cli_utils import core_command
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


@fix_app.command("all", help="Run a curated sequence of self-healing fixes.")
@handle_command_errors
@core_command(dangerous=True, confirmation=True)
# ID: b117261d-e407-4ba8-871c-06982685b34f
async def run_all_fixes(
    ctx: typer.Context,
    skip_dangerous: bool = typer.Option(
        True, help="Skip potentially dangerous operations that modify code logic."
    ),
    write: bool = typer.Option(
        False,
        "--write",
        help="Apply changes. Default is dry-run.",
    ),
) -> None:
    """
    Run a curated set of fix subcommands in a sensible order.
    """
    core_context: CoreContext = ctx.obj
    dry_run = not write

    # Helper to run steps with status
    async def _step(label: str, func: Callable[[], Any], is_async: bool = False):
        with console.status(f"[cyan]{label}...[/cyan]"):
            if is_async:
                await func()
            else:
                func()

    async def _run(name: str) -> None:
        cfg = COMMAND_CONFIG.get(name, {})
        is_dangerous = cfg.get("dangerous", False)

        # If specific command is dangerous and we are skipping dangerous, AND we are in write mode
        if skip_dangerous and is_dangerous and write:
            console.print(
                f"[yellow]Skipping dangerous command 'fix {name}' (skip_dangerous=True).[/yellow]"
            )
            return

        mode_str = "write" if write else "dry-run"
        console.print(f"[bold cyan]▶ Running 'fix {name}' ({mode_str})[/bold cyan]")

        # --- Formatting & style ---
        if name == "code-style":
            # Code style is generally safe to run even in dry run (it just checks/diffs)
            await _step("Formatting code", lambda: format_code())

        elif name == "line-lengths":
            console.print(
                "[yellow]Skipping 'fix line-lengths' in 'fix all' (targeted tool).[/yellow]"
            )

        # --- Metadata & IDs ---
        elif name == "ids":
            await _step(
                "Assigning missing IDs",
                lambda: assign_missing_ids(dry_run=dry_run),
            )

        elif name == "purge-legacy-tags":
            await _step(
                "Purging legacy tags",
                lambda: purge_legacy_tags(dry_run=dry_run),
            )

        elif name == "policy-ids":
            await _step(
                "Adding missing policy IDs",
                lambda: add_missing_policy_ids(dry_run=dry_run),
            )

        elif name == "duplicate-ids":
            # Placeholder until dependency issue resolved
            console.print(
                "[yellow]Skipping 'fix duplicate-ids' (manual run required).[/yellow]"
            )

        # --- CRITICAL: SYNC KNOWLEDGE BASE ---
        elif name == "knowledge-sync":
            if write:
                stats = await run_sync_with_db()
                console.print(f"   -> Scanned: {stats['scanned']}")
                console.print(f"   -> Updated: {stats['updated']}")
            else:
                console.print("[yellow]Skipping DB sync in dry-run mode[/yellow]")

        # --- Vector / DB sync ---
        elif name == "vector-sync":
            await _step(
                "Synchronizing vector database",
                lambda: sync_vectors_async(
                    write=write,
                    dry_run=dry_run,
                    qdrant_service=core_context.qdrant_service,
                ),
                is_async=True,
            )

        elif name == "db-registry":
            from body.cli.admin_cli import app as main_app

            await _step(
                "Syncing CLI registry",
                lambda: _sync_commands_to_db(main_app),
                is_async=True,
            )

        # --- Docstrings & tags (AI-powered) ---
        elif name == "docstrings":
            # Note: fix_docstrings currently requires manual write flag if not handled
            # We pass context which has services
            await _step(
                "Fixing docstrings",
                lambda: fix_docstrings(context=core_context, write=write),
                is_async=True,
            )

        elif name == "tags":
            from features.self_healing.capability_tagging_service import main_async

            await _step(
                "Tagging capabilities",
                lambda: main_async(
                    session_factory=get_session,
                    cognitive_service=core_context.cognitive_service,
                    knowledge_service=core_context.knowledge_service,
                    write=write,
                    dry_run=dry_run,
                ),
                is_async=True,
            )

        # --- IR bootstrap ---
        elif name == "ir-triage":
            fix_ir_triage(ctx, write=write)

        elif name == "ir-log":
            fix_ir_log(ctx, write=write)

        # --- Skip targeted tools ---
        elif name in {"clarity", "complexity"}:
            console.print(f"[yellow]Skipping 'fix {name}' (targeted tool).[/yellow]")

    # Curated execution plan
    plan = [
        "code-style",
        "line-lengths",
        "ids",
        "purge-legacy-tags",
        "policy-ids",
        "knowledge-sync",
        "vector-sync",
        "db-registry",
        "docstrings",
        "tags",
        "ir-triage",
        "ir-log",
    ]

    for name in plan:
        await _run(name)

    console.print("[green]✅ 'fix all' sequence completed[/green]")
