# src/cli/logic/knowledge.py
"""
Registers the 'knowledge' command group for managing the knowledge base and related artifacts.
This is a thin registrar; all command logic lives in knowledge_ops.py
"""

from __future__ import annotations

import typer
from rich.console import Console

# --- CORRECTED IMPORTS ---
from .knowledge_ops import (
    audit_ssot_command,
    canary_command,
    export_ssot_command,
    migrate_ssot_command,
    search_knowledge_command,
)
from .reconcile import reconcile_from_cli
from .sync import sync_knowledge_base
from .sync_manifest import sync_manifest

console = Console()
knowledge_app = typer.Typer(
    help="Commands for managing the CORE knowledge base (DB and artifacts)."
)

# Primary knowledge commands (implementations live in knowledge_ops.py)
knowledge_app.command(
    "search", help="Performs a semantic search for capabilities in the knowledge base."
)(search_knowledge_command)

knowledge_app.command("migrate-ssot")(migrate_ssot_command)

knowledge_app.command(
    "audit-ssot",
    help="Audit DB↔YAML knowledge exports for drift; writes JSON report and exits non-zero on drift.",
)(audit_ssot_command)

knowledge_app.command(
    "export-ssot",
    help="Export DB truth into read-only YAML snapshots under .intent/mind/knowledge/.",
)(export_ssot_command)

knowledge_app.command(
    "canary",
    help="Run safety canary: SSOT audit → linter (ruff) → tests (pytest). Fails fast on any error.",
)(canary_command)

# Other existing commands
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


# ID: cfd66d1c-04b5-4b9b-9bef-57a2acfc43a5
def register(app: typer.Typer) -> None:
    """Register the 'knowledge' command group with the main CLI app."""
    app.add_typer(knowledge_app, name="knowledge")
