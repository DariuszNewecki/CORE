# src/cli/resources/grc/ingest.py
"""`core-admin grc ingest <framework_id>` — internal corpus ingestion (ADR-122 D3).

Ingests a framework's pre-extracted text corpus into a per-framework Qdrant
collection (``grc-internal-{framework_id}``) so the GRC judge can retrieve
authoritative passages at verdict time (ADR-122 D4 augmentation).

The command enforces the licence gate (ADR-122 D5): frameworks marked
``internal_use_licence: required`` in ``grc-catalogs/inventory.yaml`` require a
``grc-catalogs/internal/<framework_id>/licence.yaml`` attestation file to confirm
the licence is held. Ungated frameworks (public-domain / official-*-reusable) are
ingested unconditionally.

Text extraction (PDF → text/) is a separate operator step, out of scope here.
Populate ``grc-catalogs/internal/<framework_id>/text/`` first, then run this command.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from cli.utils import core_command

from . import app


console = Console()


@app.command("ingest")
@core_command(dangerous=False, requires_context=False, requires_brain_services=False)
# ID: fd0b62b8-df95-4bb8-aa82-6a9520e00b2c
async def ingest(
    ctx: typer.Context,
    framework_id: str = typer.Argument(
        ...,
        help="Framework identifier from inventory.yaml (e.g. nist_800_171, gdpr).",
    ),
    text_dir: Path | None = typer.Option(
        None,
        "--text-dir",
        help=(
            "Directory of section text files to ingest. "
            "Defaults to grc-catalogs/internal/<framework_id>/text/."
        ),
    ),
) -> None:
    """Ingest a GRC framework's internal corpus into Qdrant (ADR-122).

    Enforces the licence gate: copyrighted frameworks require a
    grc-catalogs/internal/<framework_id>/licence.yaml before ingestion.
    Public-domain and official-EU-law-reusable frameworks are ungated.

    Drops the existing collection and rebuilds from text/ on every run
    (idempotent re-ingest — safe to run repeatedly after updating source text).
    Writes a provenance record (licence.yaml) on completion.
    """
    from body.services.grc.internal_corpus import (
        InternalCorpusIngester,
        check_licence_gate,
    )
    from shared.config import settings
    from shared.infrastructure.clients.qdrant_client import QdrantService
    from shared.utils.embedding_utils import EmbeddingService

    repo_root: Path = settings.paths.repo_root

    # Step 1: Licence gate (ADR-122 D3/D5)
    try:
        inventory_entry = check_licence_gate(framework_id, repo_root)
    except ValueError as exc:
        console.print(f"[bold red]Licence gate blocked:[/bold red] {exc}")
        raise typer.Exit(2) from exc

    # Step 2: Locate text directory
    resolved_text_dir = text_dir or (
        repo_root / "grc-catalogs" / "internal" / framework_id / "text"
    )
    if not resolved_text_dir.is_dir():
        console.print(
            f"[bold red]Text directory not found:[/bold red] {resolved_text_dir}\n"
            f"Create and populate [bold]grc-catalogs/internal/{framework_id}/text/[/bold] "
            "with section files (.txt or .md) before ingesting."
        )
        raise typer.Exit(2)

    text_files = [
        f
        for f in resolved_text_dir.iterdir()
        if f.is_file() and f.suffix in {".txt", ".md"}
    ]
    if not text_files:
        console.print(
            f"[bold red]No text files found in:[/bold red] {resolved_text_dir}\n"
            "Populate the directory with .txt or .md section files before ingesting."
        )
        raise typer.Exit(2)

    console.print(
        f"[bold cyan]Ingesting[/bold cyan] [bold]{framework_id}[/bold] "
        f"from {resolved_text_dir} "
        f"[dim]({len(text_files)} file(s))[/dim] …"
    )

    # Steps 3-5: chunk, embed, upsert, write provenance
    qdrant = QdrantService()
    embedder = EmbeddingService()
    ingester = InternalCorpusIngester(
        qdrant_service=qdrant,
        embedding_service=embedder,
        repo_root=repo_root,
    )

    try:
        chunk_count = await ingester.ingest(
            framework_id, resolved_text_dir, inventory_entry
        )
    except Exception as exc:
        console.print(f"[bold red]Ingestion failed:[/bold red] {exc}")
        raise typer.Exit(1) from exc

    console.print(
        f"[bold green]Done.[/bold green] "
        f"[bold]{chunk_count}[/bold] chunk(s) upserted into "
        f"[bold]grc-internal-{framework_id}[/bold] · "
        f"provenance written to "
        f"[dim]grc-catalogs/internal/{framework_id}/licence.yaml[/dim]"
    )
