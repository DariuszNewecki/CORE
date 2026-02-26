# src/body/cli/commands/manage/database.py

"""
Database management commands.

Golden-path adjustments (Phase 1, non-breaking):
- Canonicalized: `manage database sync {capabilities|knowledge|manifest|all}`
- Deprecated aliases:
  - sync-capabilities -> sync capabilities
  - sync-knowledge    -> sync knowledge
  - sync-manifest     -> sync manifest
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from body.cli.logic.db import export_data, migrate_db
from body.cli.logic.sync import sync_knowledge_base
from body.cli.logic.sync_manifest import sync_manifest
from features.introspection.capability_discovery_service import sync_capabilities_to_db
from features.introspection.export_vectors import VectorExportError, export_vectors
from features.maintenance.migration_service import run_ssot_migration
from shared.cli_utils import core_command, deprecated_command
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session


console = Console()
db_sub_app = typer.Typer(
    help="Manage the database schema and data.", no_args_is_help=True
)


@db_sub_app.command("migrate")
@core_command(dangerous=True, confirmation=True)
# ID: 04dd899c-209c-4590-a862-87e30065da2d
def migrate_db_command(ctx: typer.Context) -> None:
    """Run database migrations."""
    _ = ctx
    migrate_db()


@db_sub_app.command("export")
@core_command(dangerous=False)
# ID: 4ab3a88a-94b3-4dbf-aaa4-def456a250a5
async def export_data_command(
    ctx: typer.Context,
    output_dir: str = typer.Option("backups", help="Output directory"),
) -> None:
    """Export database data."""
    _ = output_dir
    await export_data(ctx)


# -----------------------------------------------------------------------------
# Canonical consolidated command: manage database sync {capabilities|knowledge|manifest|all}
# -----------------------------------------------------------------------------


@db_sub_app.command("sync")
@core_command(dangerous=True, confirmation=True)
# ID: 9e2a833a-9fbb-4fbb-9c78-7c47a2c8b0c4
async def sync_command(
    ctx: typer.Context,
    target: str = typer.Argument(
        ...,
        help="Sync target: capabilities|knowledge|manifest|all",
    ),
    write: bool = typer.Option(
        False, "--write", help="Commit changes to DB (required)"
    ),
) -> None:
    """
    Consolidated database sync command.

    Targets:
    - capabilities: sync capability tags into DB
    - knowledge:    sync codebase structure to DB knowledge graph
    - manifest:     sync project_manifest.yaml with DB public symbols
    - all:          run all sync targets
    """
    target_norm = (target or "").strip().lower()
    if target_norm not in {"capabilities", "knowledge", "manifest", "all"}:
        typer.secho(
            f"Invalid target '{target}'. Use: capabilities|knowledge|manifest|all",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=2)

    if not write:
        console.print(
            "[yellow]Dry run: sync requires --write to persist changes.[/yellow]"
        )
        return

    # ID: d404413b-daba-4915-a48e-d19b1f774577
    async def run_knowledge() -> None:
        await sync_knowledge_base()

    # ID: 68afcee3-344e-4002-81f5-7e4666fb8317
    async def run_manifest() -> None:
        await sync_manifest()

    # ID: 9d79cef4-b2fb-4b67-bd69-2467e8114bde
    async def run_capabilities() -> None:
        core_context: CoreContext = ctx.obj
        repo_root = core_context.git_service.repo_path
        async with get_session() as session:
            count, errors = await sync_capabilities_to_db(session, repo_root)
            if errors:
                for err in errors:
                    console.print(f"[red]Error:[/red] {err}")
            console.print(
                f"[bold green]✅ Successfully synced {count} capabilities to DB.[/bold green]"
                if count > 0
                else "[yellow]No capabilities synced.[/yellow]"
            )

    if target_norm == "knowledge":
        await run_knowledge()
        return

    if target_norm == "manifest":
        await run_manifest()
        return

    if target_norm == "capabilities":
        await run_capabilities()
        return

    # all
    await run_knowledge()
    await run_manifest()
    await run_capabilities()


# -----------------------------------------------------------------------------
# Deprecated aliases (Phase 1)
# -----------------------------------------------------------------------------


@db_sub_app.command("sync-knowledge")
@core_command(dangerous=True, confirmation=True)
# ID: 2743443e-5f31-4ffe-868c-aeaa3bcd02a8
async def sync_knowledge_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Commit changes to DB (required)"
    ),
) -> None:
    """DEPRECATED alias for `manage database sync knowledge`."""
    deprecated_command(
        "manage database sync-knowledge", "manage database sync knowledge"
    )
    await sync_command(ctx, target="knowledge", write=write)


@db_sub_app.command("sync-manifest")
@core_command(dangerous=True, confirmation=True)
# ID: 7fcc16a8-9a13-4c52-8a3f-bbd59d459897
async def sync_manifest_command(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write"),
) -> None:
    """DEPRECATED alias for `manage database sync manifest`."""
    deprecated_command("manage database sync-manifest", "manage database sync manifest")
    await sync_command(ctx, target="manifest", write=write)


@db_sub_app.command("sync-capabilities")
@core_command(dangerous=True, confirmation=True)
# ID: 40348824-c8ac-4e0d-873d-75d0fc05b42f
async def sync_capabilities_command(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write"),
) -> None:
    """DEPRECATED alias for `manage database sync capabilities`."""
    deprecated_command(
        "manage database sync-capabilities", "manage database sync capabilities"
    )
    await sync_command(ctx, target="capabilities", write=write)


@db_sub_app.command("export-vectors")
@core_command(dangerous=False)
# ID: b3fb8a6e-bac1-445e-8d91-4c43270b7f93
async def export_vectors_command(
    ctx: typer.Context,
    output_path: str = typer.Option("vectors.json", help="Output file path"),
) -> None:
    """Export vector data."""
    try:
        await export_vectors(ctx.obj, Path(output_path))
    except VectorExportError as exc:
        raise typer.Exit(exc.exit_code)


@db_sub_app.command("cleanup-memory")
@core_command(dangerous=True, confirmation=True)
# ID: fd6caee4-206d-441e-9f8e-b4e293024642
async def cleanup_memory_command(
    ctx: typer.Context,
    dry_run: bool = typer.Option(True, "--dry-run/--write"),
    days_episodes: int = 30,
    days_reflections: int = 90,
) -> None:
    """Clean up old agent memory entries (episodes, decisions, reflections)."""
    from features.self_healing import MemoryCleanupService

    core_context: CoreContext = ctx.obj
    async with core_context.registry.session() as session:
        result = await MemoryCleanupService(session=session).cleanup_old_memories(
            days_to_keep_episodes=days_episodes,
            days_to_keep_reflections=days_reflections,
            dry_run=dry_run,
        )

    if result.ok:
        console.print(
            f"[green]Memory cleanup {'would delete' if dry_run else 'deleted'}:[/green]"
        )
        console.print(
            "  Episodes: {episodes}\n  Decisions: {decisions}\n  Reflections: {reflections}".format(
                episodes=result.data["episodes_deleted"],
                decisions=result.data["decisions_deleted"],
                reflections=result.data["reflections_deleted"],
            )
        )
    else:
        console.print(f"[red]Error: {result.data['error']}[/red]")


@db_sub_app.command("migrate-ssot")
@core_command(dangerous=True, confirmation=True)
# ID: d8a1e134-1212-4c2d-aa44-7f29d17404f5
async def migrate_ssot_command(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write"),
) -> None:
    """One-time data migration from legacy files to the SSOT database."""
    _ = ctx
    async with get_session() as session:
        await run_ssot_migration(session, dry_run=not write)
