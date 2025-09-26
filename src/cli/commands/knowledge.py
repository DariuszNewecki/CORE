# src/cli/commands/knowledge.py
"""
Registers the 'knowledge' command group for managing the knowledge base and related artifacts.
"""
from __future__ import annotations

import typer
from rich.console import Console

from cli.commands.reconcile import reconcile_from_cli
from cli.commands.sync import sync_knowledge_base
from cli.commands.sync_manifest import sync_manifest
from features.introspection.export_vectors import export_vectors
from features.introspection.generate_correction_map import generate_maps
from features.introspection.semantic_clusterer import run_clustering

console = Console()
knowledge_app = typer.Typer(
    help="Commands for managing the CORE knowledge base (DB and artifacts)."
)

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


# ID: c75e151b-1569-46a1-b809-d2c7c46922d9
def register(app: typer.Typer):
    """Register the 'knowledge' command group with the main CLI app."""
    app.add_typer(knowledge_app, name="knowledge")
