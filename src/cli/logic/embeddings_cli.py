"""
CLI wiring for embeddings & vectorization commands.
Exposes: `core-admin knowledge vectorize [--write|--dry-run] [--cap capability --cap ...]`
"""

from __future__ import annotations

from pathlib import Path

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
# ID: 90b5ca34-823b-4584-9d61-383ff4a4e29f
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
    cap: list[str] | None = typer.Option(
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
    ks = KnowledgeService()
    knowledge = ks.load_graph()
    symbols_map: dict = knowledge.get("symbols", knowledge)
    cognitive = CognitiveService()
    qdrant = QdrantService()
    targets: set[str] | None = set(cap) if cap else None
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
    if write and (not dry_run):
        ks.save_graph(knowledge)
        typer.echo("📝 Saved updated knowledge graph.")
    else:
        typer.echo("ℹ️ Not saving graph (use --write and disable --dry-run to persist).")
