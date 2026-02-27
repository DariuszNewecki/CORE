# src/body/cli/commands/fix/all_commands.py
"""
Batch execution command(s) for the 'fix' CLI group.

Provides:
- core-admin fix all

CONSTITUTIONAL ALIGNMENT:
- Orchestrates Atomic Actions via the Body layer services.
- UPDATED: All imports point to new layered locations (Wave 3 Final).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import typer

from body.introspection.sync_service import run_sync_with_db
from body.maintenance.command_sync_service import _sync_commands_to_db

# FIXED: Points to body.maintenance (Wave 3 moved it here)
from body.maintenance.sync_vectors import main_async as sync_vectors_async
from body.self_healing.code_style_service import format_code
from body.self_healing.docstring_service import fix_docstrings
from body.self_healing.id_tagging_service import assign_missing_ids
from body.self_healing.policy_id_service import add_missing_policy_ids
from body.self_healing.purge_legacy_tags_service import purge_legacy_tags
from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session

from . import (
    COMMAND_CONFIG,
    console,
    fix_app,
)
from .fix_ir import (
    fix_ir_log,
    fix_ir_triage,
)


@fix_app.command("all", help="Run a curated sequence of self-healing fixes.")
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
    Run a curated set of fix subcommands in a sequence that respects dependencies.
    """
    core_context: CoreContext = ctx.obj
    dry_run = not write

    # Helper to run steps with status
    async def _step(label: str, func: Callable[[], Any], is_async: bool = False):
        with console.status(f"[cyan]{label}...[/cyan]"):
            if is_async:
                await func()
            else:
                res = func()
                if hasattr(res, "__await__"):
                    await res

    async def _run(name: str) -> None:
        cfg = COMMAND_CONFIG.get(name, {})
        is_dangerous = cfg.get("dangerous", False)

        if skip_dangerous and is_dangerous and write:
            console.print(f"[yellow]Skipping dangerous command 'fix {name}'.[/yellow]")
            return

        mode_str = "write" if write else "dry-run"
        console.print(f"[bold cyan]▶ Running 'fix {name}' ({mode_str})[/bold cyan]")

        # --- Formatting & Style ---
        if name == "code-style":
            await _step("Formatting code", lambda: format_code(write=write))

        # --- Metadata & IDs ---
        elif name == "ids":
            await _step(
                "Assigning missing IDs",
                lambda: assign_missing_ids(context=core_context, write=write),
            )

        elif name == "purge-legacy-tags":
            await _step(
                "Purging legacy tags",
                lambda: purge_legacy_tags(context=core_context, dry_run=dry_run),
                is_async=True,
            )

        elif name == "policy-ids":
            await _step(
                "Adding missing policy IDs",
                lambda: add_missing_policy_ids(context=core_context, dry_run=dry_run),
                is_async=True,
            )

        # --- Knowledge & Database ---
        elif name == "knowledge-sync":
            if write:
                async with get_session() as session:
                    res_obj = await run_sync_with_db(session)
                    stats = res_obj.data
                console.print(
                    f"   -> Scanned: {stats['scanned']}, Updated: {stats['updated']}"
                )
            else:
                console.print("[yellow]Skipping DB sync in dry-run mode[/yellow]")

        elif name == "vector-sync":
            # ID: a105f832-b33c-48d4-b37f-3b117982656b
            async def sync_vectors_with_session():
                async with get_session() as session:
                    return await sync_vectors_async(
                        session=session,
                        write=write,
                        dry_run=dry_run,
                        qdrant_service=core_context.qdrant_service,
                    )

            await _step(
                "Synchronizing vector database",
                sync_vectors_with_session,
                is_async=True,
            )

        elif name == "db-registry":
            from cli.admin_cli import app as main_app

            # ID: a11cbd4b-ccc9-4f38-97fc-0e681170081a
            async def sync_with_session():
                async with get_session() as session:
                    await _sync_commands_to_db(session, main_app)

            await _step("Syncing CLI registry", sync_with_session, is_async=True)

        # --- Docstrings & Capability Tagging (AI-powered) ---
        elif name == "docstrings":
            await _step(
                "Fixing docstrings",
                lambda: fix_docstrings(context=core_context, write=write),
                is_async=True,
            )

        elif name == "tags":
            # FIXED: Points to will.self_healing where the AI specialist moved
            from will.self_healing.capability_tagging_service import main_async

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

        # --- Incident Response Bootstrap ---
        elif name == "ir-triage":
            fix_ir_triage(ctx, write=write)
        elif name == "ir-log":
            fix_ir_log(ctx, write=write)

    # Curated execution plan
    plan = [
        "code-style",
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
