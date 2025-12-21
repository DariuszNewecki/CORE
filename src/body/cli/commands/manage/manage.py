# src/body/cli/commands/manage/manage.py
"""
Core logic for the 'manage' command group.
Handles DB, dotenv, projects, proposals, keys, patterns, policies, and emergency protocols.

Refactored to use the Constitutional CLI Framework (@core_command).
"""

from __future__ import annotations

import typer
from rich.console import Console

from body.cli.logic.byor import initialize_repository
from body.cli.logic.db import export_data, migrate_db
from body.cli.logic.project_docs import docs as project_docs
from body.cli.logic.proposal_service import (
    proposals_approve,
    proposals_list,
    proposals_sign,
)
from body.cli.logic.sync import sync_knowledge_base
from body.cli.logic.sync_manifest import sync_manifest
from features.introspection.capability_discovery_service import sync_capabilities_to_db
from features.introspection.export_vectors import export_vectors
from features.maintenance.dotenv_sync_service import run_dotenv_sync
from features.maintenance.migration_service import run_ssot_migration
from features.project_lifecycle.definition_service import define_symbols
from features.project_lifecycle.scaffolding_service import create_new_project
from mind.governance.key_management_service import keygen
from shared.cli_utils import core_command
from shared.config import settings
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger

from .emergency import app as emergency_sub_app
from .patterns import patterns_sub_app
from .policies import policies_sub_app
from .vectors import app as vectors_sub_app


console = Console()
logger = getLogger(__name__)

manage_app = typer.Typer(
    help="State-changing administrative tasks for the system.",
    no_args_is_help=True,
)

# === DATABASE SUB-COMMANDS ==================================================

db_sub_app = typer.Typer(
    help="Manage the database schema and data.",
    no_args_is_help=True,
)

# --- FIXED: Explicit wrappers for database commands to handle async/sync correctly ---


@db_sub_app.command("migrate")
@core_command(dangerous=True, confirmation=True)
# ID: 1b89ff66-1969-45b1-bc1e-3121a5e6edbd
def migrate_db_command(ctx: typer.Context):
    """Run database migrations."""
    migrate_db()


@db_sub_app.command("export")
@core_command(dangerous=False)
# ID: 4c17004b-e93a-4609-a216-75448ae1deb1
def export_data_command(
    ctx: typer.Context,
    output_dir: str = typer.Option("backups", help="Output directory"),
):
    """Export database data."""
    export_data(output_dir)


@db_sub_app.command("sync-knowledge")
@core_command(dangerous=True, confirmation=True)
# ID: 7673f8b7-22d2-42fa-ba1d-a6d05e5cb423
async def sync_knowledge_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Commit changes to DB (required)"
    ),
):
    """Synchronize codebase structure to the database knowledge graph."""
    if not write:
        console.print(
            "[yellow]Dry run: Knowledge sync requires --write to persist changes.[/yellow]"
        )
        return

    # This was the cause of the RuntimeWarning: it must be awaited
    await sync_knowledge_base()


@db_sub_app.command("export-vectors")
@core_command(dangerous=False)
# ID: 4b437a5f-3bab-478c-8b8c-ee93df922bd5
async def export_vectors_command(
    ctx: typer.Context,
    output_path: str = typer.Option("vectors.json", help="Output file path"),
):
    """Export vector data."""
    await export_vectors(output_path)


@db_sub_app.command("cleanup-memory")
@core_command(dangerous=True, confirmation=True)
# ID: 9d773f7b-4e04-4cd3-abc9-c9e7c3d28485
async def cleanup_memory_command(
    ctx: typer.Context,
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--write",
        help="Preview what would be deleted (default) or actually delete.",
    ),
    days_episodes: int = typer.Option(
        30, "--days-episodes", help="Retain episodes for this many days."
    ),
    days_reflections: int = typer.Option(
        90, "--days-reflections", help="Retain reflections for this many days."
    ),
) -> None:
    """Clean up old agent memory entries (episodes, decisions, reflections)."""
    from features.self_healing import MemoryCleanupService

    console.print(f"[cyan]Running memory cleanup (dry_run={dry_run})...[/cyan]")

    # Get database service
    db_service = settings.get("database")  # Or however you get your db service

    cleanup_service = MemoryCleanupService(db_service=db_service)

    result = await cleanup_service.cleanup_old_memories(
        days_to_keep_episodes=days_episodes,
        days_to_keep_reflections=days_reflections,
        dry_run=dry_run,
    )

    if result.ok:
        console.print(
            f"[green]Memory cleanup {'would delete' if dry_run else 'deleted'}:[/green]"
        )
        console.print(f"  Episodes: {result.data['episodes_deleted']}")
        console.print(f"  Decisions: {result.data['decisions_deleted']}")
        console.print(f"  Reflections: {result.data['reflections_deleted']}")
    else:
        console.print(f"[red]Error: {result.data['error']}[/red]")


@db_sub_app.command("sync-manifest")
@core_command(dangerous=True, confirmation=True)
# ID: a67d0a9a-f909-4e54-9afb-545edec329db
async def sync_manifest_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply changes to the project manifest."
    ),
) -> None:
    """Synchronize project_manifest.yaml with public symbols in the DB."""
    if not write:
        console.print(
            "[yellow]Dry run: Manifest sync requires --write to persist changes.[/yellow]"
        )
        return

    # Call the async logic function
    await sync_manifest()


@db_sub_app.command(
    "migrate-ssot",
    help="One-time data migration from legacy files to the SSOT database.",
)
# ID: 5a0db9ac-d7af-4aa7-8907-84f00e4bb7da
@core_command(dangerous=True, confirmation=True)
# ID: e3693194-d3ec-4e77-8a94-0ae812a2258d
async def migrate_ssot_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False,
        "--write",
        help="Apply the migration to the database.",
    ),
) -> None:
    await run_ssot_migration(dry_run=not write)


@db_sub_app.command(
    "sync-capabilities",
    help="Syncs capabilities from .intent/knowledge/capability_tags/ to the DB.",
)
# ID: 9eeb1713-6cf2-4526-9171-d8b1fcae11df
@core_command(dangerous=True, confirmation=True)
# ID: 072bde78-de6f-4a86-9eb2-1f3d488b8d70
async def sync_capabilities_command(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Apply changes to the database."),
) -> None:
    """Syncs capabilities from .intent/knowledge/capability_tags/ to the DB."""

    if not write:
        console.print(
            "[yellow]Dry run not supported for this command yet. Use --write to sync.[/yellow]"
        )
        return

    intent_dir = settings.MIND.parent

    async with get_session() as session:
        count, errors = await sync_capabilities_to_db(session, intent_dir)

        if errors:
            for err in errors:
                console.print(f"[red]Error:[/red] {err}")

        if count > 0:
            console.print(
                f"[bold green]✅ Successfully synced {count} capabilities to DB.[/bold green]"
            )
        else:
            console.print("[yellow]No capabilities synced.[/yellow]")


manage_app.add_typer(db_sub_app, name="database")


# === DOTENV SUB-COMMANDS =====================================================

dotenv_sub_app = typer.Typer(
    help="Manage runtime configuration from .env.",
    no_args_is_help=True,
)


@dotenv_sub_app.command(
    "sync",
    help=(
        "Sync settings from .env to the database, governed by "
        "runtime_requirements.yaml."
    ),
)
# ID: 1b58c1f3-395b-494a-b717-918cae0b7665
@core_command(dangerous=True, confirmation=True)
# ID: 933a2755-cec1-487b-a314-a6c496baaf23
async def dotenv_sync_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False,
        "--write",
        help="Apply the sync to the database.",
    ),
) -> None:
    await run_dotenv_sync(dry_run=not write)


manage_app.add_typer(dotenv_sub_app, name="dotenv")


# === PROJECT SUB-COMMANDS ====================================================

project_sub_app = typer.Typer(
    help="Manage CORE projects.",
    no_args_is_help=True,
)


@project_sub_app.command("new")
# ID: 64ad863a-3561-4108-b8a2-8dade00964be
@core_command(dangerous=True, confirmation=True)
# ID: 33552c18-f304-4c47-a552-e3eabdb58363
def project_new_command(
    ctx: typer.Context,
    name: str = typer.Argument(
        ...,
        help="The name of the new CORE-governed application to create.",
    ),
    profile: str = typer.Option(
        "default",
        "--profile",
        help="The starter kit profile to use for the new project's constitution.",
    ),
    # Mapping legacy --dry-run/--write behavior to standard write flag
    write: bool = typer.Option(
        False,
        "--write",
        help="Create the project files (default is dry-run).",
    ),
) -> None:
    """
    CLI entrypoint: scaffold a new CORE-governed application.
    """
    # Map write=False to dry_run=True
    dry_run = not write

    console.print(
        f"[bold cyan]🚀 Creating new CORE project[/bold cyan]: '{name}' "
        f"(profile: '{profile}', dry_run={dry_run})"
    )
    try:
        create_new_project(name=name, profile=profile, dry_run=dry_run)
        if dry_run:
            console.print("[yellow]Dry-run completed. No files were written.[/yellow]")
        else:
            console.print(
                f"[bold green]✅ Project '{name}' scaffolded successfully.[/bold green]"
            )
    except FileExistsError as e:
        console.print(f"[bold red]❌ {e}[/bold red]")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error("Unexpected error in project_new_command", exc_info=True)
        console.print(f"[bold red]❌ Unexpected error: {e}[/bold red]")
        raise typer.Exit(code=1)


project_sub_app.command("onboard")(initialize_repository)
project_sub_app.command("docs")(project_docs)
manage_app.add_typer(project_sub_app, name="project")


# === PROPOSALS SUB-COMMANDS ==================================================

proposals_sub_app = typer.Typer(
    help="Manage constitutional amendment proposals.",
    no_args_is_help=True,
)
proposals_sub_app.command("list")(proposals_list)
proposals_sub_app.command("sign")(proposals_sign)


@proposals_sub_app.command("approve")
# ID: f8971f15-5c5f-41e2-b661-eb9725c2d224
@core_command(dangerous=True, confirmation=True)
# ID: 3dfb9cc6-c571-451b-a0af-1db40c250cfc
async def approve_command_wrapper(
    ctx: typer.Context,
    proposal_name: str = typer.Argument(
        ...,
        help="Filename of the proposal to approve.",
    ),
    write: bool = typer.Option(False, "--write", help="Apply the approval."),
) -> None:
    if not write:
        console.print(
            "[yellow]Dry run not supported for approvals. Use --write to approve.[/yellow]"
        )
        return

    core_context: CoreContext = ctx.obj
    await proposals_approve(context=core_context, proposal_name=proposal_name)


manage_app.add_typer(proposals_sub_app, name="proposals")


# === KEYS SUB-COMMANDS =======================================================

keys_sub_app = typer.Typer(
    help="Manage operator cryptographic keys.",
    no_args_is_help=True,
)
keys_sub_app.command("generate")(keygen)
manage_app.add_typer(keys_sub_app, name="keys")


# === PATTERNS SUB-COMMANDS ===================================================

manage_app.add_typer(patterns_sub_app, name="patterns")


# === POLICIES SUB-COMMANDS ===================================================

manage_app.add_typer(policies_sub_app, name="policies")


# === VECTORS SUB-COMMANDS ====================================================

manage_app.add_typer(vectors_sub_app, name="vectors")


# === EMERGENCY SUB-COMMANDS ==================================================

manage_app.add_typer(emergency_sub_app, name="emergency")


# === DEFINE SYMBOLS ==========================================================


@manage_app.command("define-symbols")
# ID: b66c3bfb-d92c-4641-9c2d-ccb4dc6e72ef
@core_command(dangerous=True, confirmation=True)
# ID: 950b9c6d-9d54-4e29-a856-b4af49fabe77
async def define_symbols_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False,
        "--write",
        help="Commit defined symbols to database.",
    ),
) -> None:
    """
    CLI entrypoint to run symbol definition across the codebase.
    """
    if not write:
        console.print(
            "[yellow]Dry run: Symbol definition requires --write to persist changes.[/yellow]"
        )
        # The underlying service doesn't currently support a dry-run mode that returns
        # hypothetical changes without side effects, so we exit early.
        return

    core_context: CoreContext = ctx.obj

    # Get the shared ContextService instance
    ctx_service = core_context.context_service

    # Wire in the CognitiveService and QdrantService if missing,
    # mirroring the dev-sync command behavior.
    if not ctx_service.cognitive_service:
        ctx_service.cognitive_service = core_context.cognitive_service

    if not ctx_service.vector_provider.qdrant:
        ctx_service.vector_provider.qdrant = core_context.qdrant_service

    if not ctx_service.vector_provider.cognitive_service:
        ctx_service.vector_provider.cognitive_service = core_context.cognitive_service

    # Run the actual symbol definition with a fully wired context service
    await define_symbols(ctx_service)
