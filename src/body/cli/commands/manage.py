# src/body/cli/commands/manage.py
"""
State-changing administrative tasks for the system (DB, dotenv, projects, proposals, keys).
"""

from __future__ import annotations

import asyncio

import typer
from features.introspection.export_vectors import export_vectors
from features.maintenance.dotenv_sync_service import run_dotenv_sync
from features.maintenance.migration_service import run_ssot_migration
from features.project_lifecycle.definition_service import _define_new_symbols
from features.project_lifecycle.scaffolding_service import create_new_project
from mind.governance.key_management_service import keygen
from rich.console import Console
from services.clients.qdrant_client import QdrantService
from services.context.service import ContextService
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger

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

console = Console()
logger = getLogger(__name__)

manage_app = typer.Typer(
    help="State-changing administrative tasks for the system.",
    no_args_is_help=True,
)

_context: CoreContext | None = None

# === DATABASE SUB-COMMANDS ==================================================


db_sub_app = typer.Typer(
    help="Manage the database schema and data.",
    no_args_is_help=True,
)
db_sub_app.command("migrate")(migrate_db)
db_sub_app.command("export")(export_data)
db_sub_app.command("sync-knowledge")(sync_knowledge_base)
db_sub_app.command("sync-manifest")(sync_manifest)
db_sub_app.command("export-vectors")(export_vectors)


@db_sub_app.command(
    "migrate-ssot",
    help="One-time data migration from legacy files to the SSOT database.",
)
# ID: 6aa37e30-2fd5-4738-8bbd-2a4f3cb4441f
def migrate_ssot_command(
    write: bool = typer.Option(
        False,
        "--write",
        help="Apply the migration to the database.",
    ),
) -> None:
    asyncio.run(run_ssot_migration(dry_run=not write))


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
# ID: 0cbb0df6-2070-41f5-a6e1-d6cb339294f2
def dotenv_sync_command(
    write: bool = typer.Option(
        False,
        "--write",
        help="Apply the sync to the database.",
    ),
) -> None:
    asyncio.run(run_dotenv_sync(dry_run=not write))


manage_app.add_typer(dotenv_sub_app, name="dotenv")


# === PROJECT SUB-COMMANDS ====================================================

project_sub_app = typer.Typer(
    help="Manage CORE projects.",
    no_args_is_help=True,
)


@project_sub_app.command("new")
# ID: 9a6c6a6d-2c5a-4b57-9e2a-5b5199e4f3f21
# ID: af616f12-7dd9-417e-aff2-ae9aad8ced78
def project_new_command(
    name: str = typer.Argument(
        ...,
        help="The name of the new CORE-governed application to create.",
    ),
    profile: str = typer.Option(
        "default",
        "--profile",
        help="The starter kit profile to use for the new project's constitution.",
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--write",
        help="Show what will be created without writing files. Use --write to apply.",
    ),
) -> None:
    """
    CLI entrypoint: scaffold a new CORE-governed application.

    This bridges user input (Typer) to the domain-level scaffolding service.
    """
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
    except Exception as e:  # noqa: BLE001
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
# ID: f6665b18-e3bc-46b0-85bf-4f7ff7a6a2ad
def approve_command_wrapper(
    ctx: typer.Context,
    proposal_name: str = typer.Argument(
        ...,
        help="Filename of the proposal to approve.",
    ),
) -> None:
    core_context: CoreContext = ctx.obj
    proposals_approve(context=core_context, proposal_name=proposal_name)


manage_app.add_typer(proposals_sub_app, name="proposals")


# === KEYS SUB-COMMANDS =======================================================

keys_sub_app = typer.Typer(
    help="Manage operator cryptographic keys.",
    no_args_is_help=True,
)
keys_sub_app.command("generate")(keygen)
manage_app.add_typer(keys_sub_app, name="keys")


# === DEFINE SYMBOLS ==========================================================


async def _async_define_symbols(core_context: CoreContext) -> None:
    """
    Asynchronous core logic for defining symbols.

    This is a private async helper: CLI -> this -> domain capability.
    """
    # === JIT INJECTION ===
    if core_context.qdrant_service is None and core_context.registry:
        logger.info("Initializing QdrantService via Registry for symbol definition...")
        core_context.qdrant_service = await core_context.registry.get_qdrant_service()
    elif core_context.qdrant_service is None:
        # Fallback for non-registry contexts (tests)
        logger.info("Initializing QdrantService manually for symbol definition...")
        core_context.qdrant_service = QdrantService()

    # Ensure cognitive service has it too
    if core_context.cognitive_service and not hasattr(
        core_context.cognitive_service, "_qdrant_service"
    ):
        core_context.cognitive_service._qdrant_service = core_context.qdrant_service

    context_service = ContextService(
        qdrant_client=core_context.qdrant_service,
        cognitive_service=core_context.cognitive_service,
        project_root=str(settings.REPO_PATH),
    )
    await _define_new_symbols(context_service)


@manage_app.command("define-symbols")
# ID: 34b2f0d2-3b69-4ea2-bc9d-5b2071bce2d3
def define_symbols_command(ctx: typer.Context) -> None:
    """
    CLI entrypoint to run symbol definition across the codebase.

    This is the public CLI surface; `_async_define_symbols` remains private.
    """
    core_context: CoreContext = ctx.obj
    asyncio.run(_async_define_symbols(core_context))
