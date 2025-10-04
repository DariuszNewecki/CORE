# src/cli/commands/manage.py
"""Registers the new, verb-based 'manage' command group with subgroups."""
from __future__ import annotations

import asyncio
from typing import Set

import typer
import yaml
from rich.console import Console
from rich.progress import track
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from cli.logic.byor import initialize_repository
from cli.logic.cli_utils import set_context as set_shared_context
from cli.logic.db import export_data, migrate_db
from cli.logic.knowledge_sync import sync_operational
from cli.logic.new import register as register_new_project
from cli.logic.project_docs import docs as project_docs
from cli.logic.proposal_service import (
    proposals_approve,
    proposals_list,
    proposals_sign,
)
from cli.logic.sync import sync_knowledge_base
from cli.logic.sync_manifest import sync_manifest
from core.cognitive_service import CognitiveService
from core.prompt_pipeline import PromptPipeline
from features.governance.key_management_service import register as register_keygen
from features.introspection.knowledge_helpers import extract_source_code
from features.maintenance.migration_service import run_ssot_migration
from services.clients.qdrant_client import QdrantService
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger

console = Console()
log = getLogger("manage_command")

manage_app = typer.Typer(
    help="State-changing administrative tasks for the system.",
    no_args_is_help=True,
)

db_sub_app = typer.Typer(
    help="Manage the database schema and data.", no_args_is_help=True
)
db_sub_app.command("migrate")(migrate_db)
db_sub_app.command("export")(export_data)
db_sub_app.command("sync-knowledge")(sync_knowledge_base)
db_sub_app.command("sync-manifest")(sync_manifest)
db_sub_app.command("sync-operational")(sync_operational)


@db_sub_app.command(
    "migrate-ssot",
    help="One-time data migration from legacy files to the SSOT database.",
)
def migrate_ssot_command(
    write: bool = typer.Option(
        False, "--write", help="Apply the migration to the database."
    )
):
    """CLI wrapper for the SSOT migration service."""
    asyncio.run(run_ssot_migration(dry_run=not write))


manage_app.add_typer(db_sub_app, name="database")
project_sub_app = typer.Typer(help="Manage CORE projects.", no_args_is_help=True)
register_new_project(project_sub_app)
project_sub_app.command("onboard")(initialize_repository)
project_sub_app.command("docs")(project_docs)
manage_app.add_typer(project_sub_app, name="project")
proposals_sub_app = typer.Typer(
    help="Manage constitutional amendment proposals.", no_args_is_help=True
)
proposals_sub_app.command("list")(proposals_list)
proposals_sub_app.command("sign")(proposals_sign)
proposals_sub_app.command("approve")(proposals_approve)
manage_app.add_typer(proposals_sub_app, name="proposals")
keys_sub_app = typer.Typer(
    help="Manage operator cryptographic keys.", no_args_is_help=True
)
register_keygen(keys_sub_app)
manage_app.add_typer(keys_sub_app, name="keys")


def _define_single_symbol_sync(
    symbol, cognitive_service, qdrant_service, existing_keys: Set[str]
):
    """Synchronous version of the symbol definition logic."""
    log.info(f"Defining symbol: {symbol.get('symbol_path')}")
    source_code = extract_source_code(settings.REPO_PATH, symbol)
    if not source_code:
        return {"uuid": symbol["uuid"], "key": "error.code_not_found"}

    prompt_pipeline = PromptPipeline(settings.REPO_PATH)
    prompt_template = settings.get_path("mind.prompts.capability_definer").read_text(
        "utf-8"
    )
    final_prompt = prompt_pipeline.process(prompt_template.format(code=source_code))

    definer_agent = cognitive_service.get_client_for_role("CodeReviewer")
    suggested_key = definer_agent.make_request_sync(
        final_prompt, user_id="definer_agent"
    ).strip()

    if suggested_key in existing_keys:
        console.print(
            f"[yellow]Warning: AI suggested existing key '{suggested_key}'. Skipping.[/yellow]"
        )
        return {"uuid": symbol["uuid"], "key": "error.duplicate_key"}

    return {"uuid": symbol["uuid"], "key": suggested_key}


@manage_app.command(
    "define-symbols",
    help="[Synchronous] Defines all undefined capabilities one by one.",
)
def define_symbols_command():
    """A robust, synchronous command to reliably define all symbols."""
    console.print(
        "[bold yellow]Running simple, synchronous symbol definition...[/bold yellow]"
    )

    try:
        engine = create_engine(
            settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")
        )
        Session = sessionmaker(bind=engine)
        session = Session()
    except ImportError:
        console.print(
            "[bold red]Error: psycopg2-binary is required. Please run 'poetry add psycopg2-binary'[/bold red]"
        )
        raise typer.Exit(1)

    cognitive_service = CognitiveService(settings.REPO_PATH)
    qdrant_service = QdrantService()

    try:
        ignore_policy_path = (
            settings.REPO_PATH
            / ".intent"
            / "charter"
            / "policies"
            / "governance"
            / "audit_ignore_policy.yaml"
        )
        ignore_policy = yaml.safe_load(ignore_policy_path.read_text("utf-8"))
        ignored_symbol_keys = {
            item["key"]
            for item in ignore_policy.get("symbol_ignores", [])
            if "key" in item
        }

        # --- THIS IS THE FIX ---
        # The query now correctly selects 'module' but aliases it as 'file_path'.
        undefined_symbols_result = session.execute(
            text(
                "SELECT uuid, module AS file_path, symbol_path, vector_id FROM core.symbols WHERE key IS NULL AND vector_id IS NOT NULL"
            )
        )
        # --- END OF FIX ---

        all_undefined_symbols = [dict(row._mapping) for row in undefined_symbols_result]

        undefined_symbols = [
            s
            for s in all_undefined_symbols
            if s["symbol_path"] not in ignored_symbol_keys
        ]
        ignored_count = len(all_undefined_symbols) - len(undefined_symbols)
        if ignored_count > 0:
            console.print(
                f"   -> Ignoring {ignored_count} symbols based on audit_ignore_policy.yaml."
            )

        if not undefined_symbols:
            console.print("[green]✅ No symbols to define.[/green]")
            return

        console.print(
            f"   -> Found {len(undefined_symbols)} symbols to define. Processing one by one..."
        )

        existing_keys_res = session.execute(
            text("SELECT key FROM core.symbols WHERE key IS NOT NULL")
        )
        existing_keys = {row[0] for row in existing_keys_res}

        definitions_to_commit = []
        for symbol in track(undefined_symbols, description="Defining symbols..."):
            definition = _define_single_symbol_sync(
                symbol, cognitive_service, qdrant_service, existing_keys
            )
            if (
                definition
                and definition.get("key")
                and not definition["key"].startswith("error.")
            ):
                definitions_to_commit.append(definition)
                existing_keys.add(definition["key"])

        if definitions_to_commit:
            console.print(
                f"\n[bold]Committing {len(definitions_to_commit)} new definitions to the database...[/bold]"
            )
            session.execute(
                text("UPDATE core.symbols SET key = :key WHERE uuid = :uuid"),
                definitions_to_commit,
            )
            session.commit()
            console.print(
                "[bold green]✅ Definitions committed successfully.[/bold green]"
            )
        else:
            console.print(
                "[bold yellow]No valid definitions were generated to commit.[/bold yellow]"
            )
            session.commit()

    except Exception as e:
        console.print(f"[bold red]An error occurred: {e}. Rolling back.[/bold red]")
        session.rollback()
        raise
    finally:
        session.close()


def register(app: typer.Typer, context: CoreContext):
    """Register the 'manage' command group with the main CLI app."""
    set_shared_context(context, "cli.logic.proposal_service")
    app.add_typer(manage_app, name="manage")
