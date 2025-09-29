# src/system/admin/embeddings_cli.py
"""
CLI wiring for embeddings & vectorization commands.
Exposes: `core-admin knowledge vectorize [--write|--dry-run] [--cap capability --cap ...]`
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Set

import typer

from core.cognitive_service import CognitiveService
from core.knowledge_service import KnowledgeService
from services.clients.qdrant_client import QdrantService
from shared.logger import getLogger

from .knowledge_orchestrator import run_vectorize

log = getLogger("core_admin.embeddings_cli")

app = typer.Typer(
    name="knowledge", no_args_is_help=True, help="Knowledge graph & embeddings commands"
)


@app.command("vectorize")
# ID: ed834afd-2224-421d-9a8e-a117526fd7b8
def vectorize_cmd(
    write: bool = typer.Option(
        False, "--write", help="Persist changes to knowledge graph after run."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Do not upsert to Qdrant, simulate only."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", help="Verbose logging / stack traces."
    ),
    cap: Optional[list[str]] = typer.Option(
        None, "--cap", help="Limit to specific capability keys (repeatable)."
    ),
    flush_every: int = typer.Option(
        10, "--flush-every", help="Flush/save cadence (N processed chunks)."
    ),
):
    """
    Vectorize code chunks into Qdrant with per-chunk idempotency.
    """
    repo_root = Path(".").resolve()

    # --- Load current knowledge graph ---
    ks = KnowledgeService()
    knowledge = ks.load_graph()  # <-- adjust if your service uses a different name
    symbols_map: dict = knowledge.get("symbols", knowledge)  # support both styles

    # --- Resources ---
    cognitive = CognitiveService()
    qdrant = QdrantService()  # relies on your settings/env

    targets: Optional[Set[str]] = set(cap) if cap else None

    # --- Run orchestrator ---
    typer.echo("🚀 Starting capability vectorization process (per-chunk idempotent)…")
    import asyncio

    asyncio.run(
        run_vectorize(
            repo_root=repo_root,
            symbols_map=symbols_map,
            cognitive_service=cognitive,
            qdrant_service=qdrant,
            dry_run=dry_run,
            verbose=verbose,
            target_capabilities=targets,
            flush_every=flush_every,
        )
    )

    # --- Persist knowledge graph only if requested ---
    if write and not dry_run:
        ks.save_graph(knowledge)  # <-- adjust if your service uses a different name
        typer.echo("📝 Saved updated knowledge graph.")
    else:
        typer.echo("ℹ️ Not saving graph (use --write and disable --dry-run to persist).")


# ID: 23050288-a833-419e-a5fd-5cb9d8ec2112
def register(app_root):
    """
    Hook for system.admin.__init__.py to mount this CLI group.
    Usage: app_root.add_typer(app, name="knowledge")
    """
    app_root.add_typer(app, name="knowledge")
