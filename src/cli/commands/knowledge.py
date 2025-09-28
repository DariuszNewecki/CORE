# src/cli/commands/knowledge.py
"""
Registers the 'knowledge' command group for managing the knowledge base and related artifacts.
"""
from __future__ import annotations

import asyncio

import typer
import yaml
from rich.console import Console
from rich.table import Table
from sqlalchemy import insert

from cli.commands.reconcile import reconcile_from_cli
from cli.commands.sync import sync_knowledge_base
from cli.commands.sync_manifest import sync_manifest
from core.cognitive_service import CognitiveService
from features.introspection.export_vectors import export_vectors
from features.introspection.generate_correction_map import generate_maps
from features.introspection.semantic_clusterer import run_clustering
from services.database.models import CliCommand, CognitiveRole, LlmResource
from services.database.session_manager import get_session
from shared.config import settings
from shared.legacy_models import (
    LegacyCliRegistry,
    LegacyCognitiveRoles,
    LegacyResourceManifest,
)

console = Console()
knowledge_app = typer.Typer(
    help="Commands for managing the CORE knowledge base (DB and artifacts)."
)


@knowledge_app.command(
    "search", help="Performs a semantic search for capabilities in the knowledge base."
)
# ID: 08c51ff9-f1ec-4752-b15f-bf75053b4ec2
def search_knowledge_command(
    query: str = typer.Argument(..., help="The natural language search query."),
    limit: int = typer.Option(5, "--limit", "-l", help="Number of results to return."),
):
    """
    A synchronous wrapper that runs the async search_knowledge function.
    """

    async def _search_knowledge_async():
        """
        Finds relevant capabilities by performing a semantic search on the vector database.
        """
        console.print(
            f"🧠 Searching for capabilities related to: '[cyan]{query}[/cyan]'..."
        )
        try:
            cognitive_service = CognitiveService(settings.REPO_PATH)
            results = await cognitive_service.search_capabilities(query, limit=limit)

            if not results:
                console.print("[yellow]No relevant capabilities found.[/yellow]")
                return

            table = Table(title="Top Matching Capabilities")
            table.add_column("Score", style="magenta", justify="right")
            table.add_column("Capability Key", style="cyan")
            table.add_column("Description", style="green")

            for hit in results:
                payload = hit.get("payload", {})
                key = payload.get("key", "N/A")
                description = (
                    payload.get("description") or "No description provided."
                ).strip()
                score = f"{hit.get('score', 0):.4f}"
                table.add_row(score, key, description)

            console.print(table)

        except Exception as e:
            console.print(
                f"[bold red]❌ An error occurred during the search: {e}[/bold red]"
            )
            raise typer.Exit(code=1)

    asyncio.run(_search_knowledge_async())


# --- START: NEW MIGRATION COMMAND ---
@knowledge_app.command("migrate-ssot")
# ID: ced3f940-b542-4afe-9e57-babb14cbc5b5
def migrate_ssot_command():
    """
    [DANGEROUS] Perform a one-time migration of legacy YAML knowledge into the database.
    """

    async def _migrate_async():
        """
        Reads from deprecated YAML files and populates the database tables:
        - .intent/mind/knowledge/cli_registry.yaml -> core.cli_commands
        - .intent/mind/knowledge/resource_manifest.yaml -> core.llm_resources
        - .intent/mind/knowledge/cognitive_roles.yaml -> core.cognitive_roles
        """
        console.print(
            "[bold yellow]⚠️ WARNING: This is a one-time migration operation.[/bold yellow]"
        )
        console.print(
            "   It will read from legacy YAML files and populate the database, replacing existing data."
        )
        if not typer.confirm("Are you sure you want to proceed?"):
            raise typer.Abort()

        async with get_session() as session:
            # Step 1: Migrate CLI registry
            cli_registry_path = settings.MIND / "knowledge" / "cli_registry.yaml"
            if cli_registry_path.exists():
                console.print(f"Migrating [cyan]{cli_registry_path.name}[/cyan]...")
                with cli_registry_path.open("r") as f:
                    data = yaml.safe_load(f)
                registry_model = LegacyCliRegistry.model_validate(data)
                commands_data = [cmd.model_dump() for cmd in registry_model.commands]

                if commands_data:
                    await session.execute(
                        CliCommand.__table__.delete()
                    )  # Clear existing data
                    await session.execute(insert(CliCommand), commands_data)
                console.print(f"  -> Migrated {len(commands_data)} CLI commands.")
            else:
                console.print("[yellow]Skipping CLI registry, file not found.[/yellow]")

            # Step 2: Migrate LLM resources
            resource_manifest_path = (
                settings.MIND / "knowledge" / "resource_manifest.yaml"
            )
            if resource_manifest_path.exists():
                console.print(
                    f"Migrating [cyan]{resource_manifest_path.name}[/cyan]..."
                )
                with resource_manifest_path.open("r") as f:
                    data = yaml.safe_load(f)
                manifest_model = LegacyResourceManifest.model_validate(data)
                resources_data = [
                    res.model_dump() for res in manifest_model.llm_resources
                ]

                if resources_data:
                    await session.execute(LlmResource.__table__.delete())
                    await session.execute(insert(LlmResource), resources_data)
                console.print(f"  -> Migrated {len(resources_data)} LLM resources.")
            else:
                console.print(
                    "[yellow]Skipping LLM resources, file not found.[/yellow]"
                )

            # Step 3: Migrate cognitive roles
            cognitive_roles_path = settings.MIND / "knowledge" / "cognitive_roles.yaml"
            if cognitive_roles_path.exists():
                console.print(f"Migrating [cyan]{cognitive_roles_path.name}[/cyan]...")
                with cognitive_roles_path.open("r") as f:
                    data = yaml.safe_load(f)
                roles_model = LegacyCognitiveRoles.model_validate(data)
                roles_data = [role.model_dump() for role in roles_model.cognitive_roles]

                if roles_data:
                    await session.execute(CognitiveRole.__table__.delete())
                    await session.execute(insert(CognitiveRole), roles_data)
                console.print(f"  -> Migrated {len(roles_data)} cognitive roles.")
            else:
                console.print(
                    "[yellow]Skipping cognitive roles, file not found.[/yellow]"
                )

            await session.commit()

        console.print(
            "\n[bold green]✅ Knowledge migration complete. The database is now the SSOT.[/bold green]"
        )
        console.print(
            "[bold yellow]You may now remove the legacy YAML files from .intent/mind/knowledge/.[/bold yellow]"
        )

    asyncio.run(_migrate_async())


# --- END: NEW MIGRATION COMMAND ---


# --- Primary Commands ---
knowledge_app.command(
    "sync",
    help="Scans the codebase and syncs all symbols to the database.",
)(sync_knowledge_base)

knowledge_app.command(
    "reconcile-from-cli",
    help="Links capabilities in the DB using the CLI registry as a map.",
)(reconcile_from_cli)

knowledge_app.command(
    "sync-manifest",
    help="Synchronizes project_manifest.yaml with public capabilities from the database.",
)(sync_manifest)

# --- Analysis & Reporting Commands ---
knowledge_app.command(
    "export-vectors", help="Exports all vectors from Qdrant to a JSONL file."
)(export_vectors)
knowledge_app.command(
    "cluster-vectors", help="Clusters exported vectors to find semantic domains."
)(run_clustering)
knowledge_app.command(
    "generate-map",
    help="Generates alias maps from clustering results.",
)(generate_maps)


# ID: cfd66d1c-04b5-4b9b-9bef-57a2acfc43a5
def register(app: typer.Typer):
    """Register the 'knowledge' command group with the main CLI app."""
    app.add_typer(knowledge_app, name="knowledge")
