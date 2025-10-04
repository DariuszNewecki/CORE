# src/cli/commands/manage.py
"""Registers the new, verb-based 'manage' command group with subgroups."""
from __future__ import annotations

import asyncio
import re
from functools import partial
from typing import Set

import typer
import yaml
from rich.console import Console
from sqlalchemy import text

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
from features.governance.key_management_service import register as register_keygen
from features.introspection.knowledge_helpers import extract_source_code
from features.maintenance.migration_service import run_ssot_migration
from services.clients.llm_api_client import BaseLLMClient
from services.database.session_manager import get_session
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger
from shared.utils.parallel_processor import ThrottledParallelProcessor

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


async def _define_single_symbol_async(
    symbol: dict, definer_agent: BaseLLMClient, existing_keys: Set[str]
) -> dict:
    """Asynchronous version of the symbol definition logic."""
    source_code = extract_source_code(settings.REPO_PATH, symbol)
    if not source_code:
        log.warning(
            f"Could not extract source code for {symbol.get('symbol_path')}. Skipping."
        )
        return {"uuid": symbol["uuid"], "key": "error.code_not_found"}

    prompt_template = (
        "Analyze the following Python code and propose a single, canonical, "
        "dot-notation capability key that follows a `domain.subdomain.action` pattern. "
        "The final part MUST be a verb.\n\n"
        "```python\n{code}\n```\n\n"
        "Respond with ONLY the key and nothing else."
    )
    final_prompt = prompt_template.format(code=source_code)

    try:
        raw_response = await definer_agent.make_request_async(
            final_prompt, user_id="definer_agent"
        )
        raw_response = raw_response.strip()
    except Exception as e:
        log.error(f"AI call failed for {symbol.get('symbol_path')}: {e}")
        return {"uuid": symbol["uuid"], "key": "error.ai_request_failed"}

    match = re.search(r"([a-z0-9_]+\.[a-z0-9_.]+[a-z0-9_]+)", raw_response)
    if not match:
        log.warning(
            f"Could not parse key from AI response for {symbol.get('symbol_path')}: '{raw_response}'"
        )
        return {"uuid": symbol["uuid"], "key": "error.parsing_failed"}

    suggested_key = match.group(1).strip()

    if suggested_key in existing_keys:
        return {"uuid": symbol["uuid"], "key": "error.duplicate_key"}

    return {"uuid": symbol["uuid"], "key": suggested_key}


async def _async_define_symbols():
    """The core asynchronous logic for the define-symbols command."""
    console.print(
        "[bold yellow]Running asynchronous symbol definition...[/bold yellow]"
    )

    console.print("   -> Performing pre-flight check for AI services...")
    cognitive_service = CognitiveService(settings.REPO_PATH)
    try:
        await cognitive_service.initialize()
        definer_agent = await cognitive_service.aget_client_for_role("CodeReviewer")
        console.print("   -> ✅ AI service for 'CodeReviewer' is configured correctly.")
    except Exception as e:
        console.print(
            "[bold red]❌ PRE-FLIGHT CHECK FAILED.[/bold red]", highlight=False
        )
        console.print(f"   -> Error: {e}", highlight=False)
        raise typer.Exit(code=1)

    async with get_session() as session:
        ignore_policy_path = settings.get_path(
            "charter.policies.governance.audit_ignore_policy"
        )
        ignore_policy = yaml.safe_load(ignore_policy_path.read_text("utf-8"))
        ignored_symbol_keys = {
            item["key"]
            for item in ignore_policy.get("symbol_ignores", [])
            if "key" in item
        }

        result = await session.execute(
            text(
                "SELECT uuid, module AS file_path, symbol_path, qualname FROM core.symbols WHERE key IS NULL"
            )
        )
        all_undefined_symbols = [dict(row._mapping) for row in result]

        undefined_symbols = [
            s
            for s in all_undefined_symbols
            if s["symbol_path"] not in ignored_symbol_keys
        ]

        if not undefined_symbols:
            console.print("[green]✅ No symbols to define.[/green]")
            return

        console.print(f"   -> Found {len(undefined_symbols)} symbols to define.")

        result = await session.execute(
            text("SELECT key FROM core.symbols WHERE key IS NOT NULL")
        )
        existing_keys = {row[0] for row in result}

        processor = ThrottledParallelProcessor(description="Defining symbols...")

        worker_fn = partial(
            _define_single_symbol_async,
            definer_agent=definer_agent,
            existing_keys=existing_keys,
        )

        results = await processor.run_async(undefined_symbols, worker_fn)

        # --- THIS IS THE FINAL FIX ---
        # De-duplicate the results before committing.
        definitions_to_commit = []
        seen_keys_in_batch = set()
        for definition in results:
            if (
                definition
                and definition.get("key")
                and not definition["key"].startswith("error.")
            ):
                key = definition["key"]
                if key not in existing_keys and key not in seen_keys_in_batch:
                    definitions_to_commit.append(definition)
                    seen_keys_in_batch.add(key)
        # --- END OF FINAL FIX ---

        if definitions_to_commit:
            console.print(
                f"\n[bold]Committing {len(definitions_to_commit)} new definitions to the database...[/bold]"
            )
            await session.execute(
                text("UPDATE core.symbols SET key = :key WHERE uuid = :uuid"),
                definitions_to_commit,
            )
            await session.commit()  # Explicitly commit the transaction
            console.print(
                "[bold green]✅ Definitions committed successfully.[/bold green]"
            )
            console.print(
                "[bold green]✅ Definitions committed successfully.[/bold green]"
            )
        else:
            console.print(
                "[bold yellow]No valid definitions were generated to commit.[/bold yellow]"
            )


@manage_app.command(
    "define-symbols",
    help="Defines all undefined capabilities one by one using an AI agent.",
)
def define_symbols_command():
    """Synchronous wrapper for the async symbol definition logic."""
    try:
        asyncio.run(_async_define_symbols())
    except Exception as e:
        console.print(
            f"[bold red]An unexpected error occurred: {e}[/bold red]", highlight=False
        )
        raise typer.Exit(code=1)


def register(app: typer.Typer, context: CoreContext):
    """Register the 'manage' command group with the main CLI app."""
    set_shared_context(context, "cli.logic.proposal_service")
    app.add_typer(manage_app, name="manage")
