# src/cli/resources/coherence/seed.py
"""`core-admin coherence seed` — governance_claims bootstrap and disaster recovery.

Per ADR-073 D4:
  - bootstrap : one-shot embed of the full corpus (governor-only; 30-70 min).
  - export    : dump payloads + vectors to JSONL for disaster recovery.
  - import    : hydrate the collection from a JSONL fixture.

The daemon worker does NOT auto-bootstrap; this is the explicit governor path.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console

from cli.utils import core_command
from shared.config import settings
from shared.context import CoreContext
from shared.infrastructure.storage.file_handler import FileHandler


logger = logging.getLogger(__name__)
console = Console()


seed_app = typer.Typer(
    name="seed",
    help=(
        "Manage the governance_claims Qdrant collection: one-shot bootstrap "
        "and disaster-recovery export/import. Per ADR-073 D4."
    ),
    no_args_is_help=True,
)


# Batch size for the bootstrap embed call. 32 is the #461 D1-confirmed default;
# larger risks Ollama timeout on slow embed models, smaller loses throughput.
# Tunable if a future Ollama version or model changes the trade-off.
_BOOTSTRAP_EMBED_BATCH = 32


@seed_app.command("bootstrap")
@core_command(dangerous=True, requires_context=True)
# ID: 73ce1ee6-67ce-4806-8a3c-252838cd3212
async def bootstrap_command(ctx: typer.Context) -> None:
    """Embed the full governance corpus into the governance_claims collection.

    One-shot operation; wall-clock dominated by embedding throughput.
    Post-#461 the embed call is batched (~3-10x speedup), so a 1572-claim
    corpus completes well under 10 min on the current `.40` setup.
    The daemon worker handles steady-state incremental sync after this
    completes. Run once on install or after a collection drop.
    """
    from body.services.governance_claims_service import (
        ClaimVector,
        GovernanceClaimsService,
    )
    from shared.governance.coherence_harvester import GovernanceClaimHarvester
    from shared.infrastructure.vector.cognitive_adapter import (
        CognitiveEmbedderAdapter,
    )

    context: CoreContext = ctx.obj
    try:
        cognitive_service = await context.registry.get_cognitive_service()
        qdrant = await context.registry.get_qdrant_service()
    except Exception as exc:
        logger.exception("Failed to acquire embedding services")
        console.print(f"[red]Service unavailable: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    claims_service = GovernanceClaimsService(qdrant)
    await claims_service.ensure_collection()

    harvester = GovernanceClaimHarvester(Path(settings.REPO_PATH))
    claims = list(harvester.harvest())
    if not claims:
        console.print("[yellow]No claims harvested — nothing to embed.[/yellow]")
        return

    console.print(
        f"[cyan]Bootstrapping[/cyan] governance_claims with [bold]{len(claims)}[/bold] "
        f"claims (batch={_BOOTSTRAP_EMBED_BATCH}, expect <10 min)."
    )

    embedder = CognitiveEmbedderAdapter(cognitive_service)
    items: list[ClaimVector] = []
    failures = 0
    upsert_batch = 50
    embedded = 0
    started = datetime.now(UTC)

    for window_start in range(0, len(claims), _BOOTSTRAP_EMBED_BATCH):
        window = claims[window_start : window_start + _BOOTSTRAP_EMBED_BATCH]
        window_vectors, window_failures = await _embed_window(embedder, window)
        items.extend(window_vectors)
        failures += window_failures
        if len(items) >= upsert_batch:
            embedded += await claims_service.upsert_claims(items)
            items = []
            done = window_start + len(window)
            console.print(
                f"  [dim]progress[/dim] {embedded}/{len(claims)} "
                f"({done / len(claims):.0%})"
            )
    if items:
        embedded += await claims_service.upsert_claims(items)

    elapsed = (datetime.now(UTC) - started).total_seconds()
    console.print(
        f"[green]Bootstrap complete[/green] — embedded {embedded}/{len(claims)} "
        f"claims in {elapsed / 60:.1f} min ({failures} failures)"
    )


# ID: a47b6c39-2e85-4d18-8f06-c5b9e3a7d149
async def _embed_window(embedder, window):
    """Embed a window of claims via the batch entry point with single-shot fallback.

    Tries `get_embeddings_batch` first; on batch failure, falls back to
    per-claim single-input embed so a single bad claim does not abort
    the whole window. This preserves the original bootstrap's error
    isolation while still capturing the batch speedup on the common path.

    Returns:
        (list[ClaimVector] for successfully-embedded claims, failure_count)
    """
    from body.services.governance_claims_service import ClaimVector

    texts = [c.text for c in window]
    try:
        vectors = await embedder.get_embeddings_batch(texts)
        return (
            [ClaimVector(claim=c, vector=v) for c, v in zip(window, vectors)],
            0,
        )
    except Exception as exc:
        logger.warning(
            "bootstrap: batch embed failed for window of %d claims (%s); "
            "falling back to single-shot for this window",
            len(window),
            exc,
        )
        items: list[ClaimVector] = []
        failures = 0
        for claim in window:
            try:
                vector = await embedder.get_embedding(claim.text)
            except Exception as exc2:
                logger.warning(
                    "bootstrap: single-shot embed failed for %s (sha=%s): %s",
                    claim.source_path,
                    claim.content_sha[:8],
                    exc2,
                )
                failures += 1
                continue
            items.append(ClaimVector(claim=claim, vector=vector))
        return items, failures


@seed_app.command("export")
@core_command(dangerous=False, requires_context=True)
# ID: 1fefb5ca-3d3d-474c-aed6-06c68f3b0694
async def export_command(
    ctx: typer.Context,
    output: Path = typer.Argument(
        ...,
        help="Destination JSONL path. One line per claim: {payload, vector}.",
    ),
) -> None:
    """Dump payloads + vectors from governance_claims to a JSONL fixture.

    The fixture restores via `coherence seed import` without consulting the
    embedding endpoint — disaster-recovery path per ADR-073 D4.
    """
    from body.services.governance_claims_service import GovernanceClaimsService

    context: CoreContext = ctx.obj
    try:
        qdrant = await context.registry.get_qdrant_service()
    except Exception as exc:
        logger.exception("Failed to acquire Qdrant service")
        console.print(f"[red]Service unavailable: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    claims_service = GovernanceClaimsService(qdrant)
    if not await claims_service.is_seeded():
        console.print(
            "[yellow]governance_claims is empty or absent — nothing to export.[/yellow]"
        )
        raise typer.Exit(code=1)

    records = await qdrant.scroll_all_points(
        with_payload=True,
        with_vectors=True,
        page_size=1024,
        collection_name=claims_service.collection_name,
    )

    repo_root = context.git_service.repo_path
    file_handler = FileHandler(str(repo_root))
    file_handler.ensure_dir(str(output.parent.relative_to(repo_root)))
    written = 0
    # NOTE: streaming `output.open("w")` below is the #506 variable-receiver
    # gap (silent in current taxonomy). The mkdir above is routed through
    # FileHandler so the check no longer fires; the streaming write is
    # enumerated in #506, not laundered as sanctuary here.
    with output.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(
                json.dumps(
                    {
                        "id": str(record.id),
                        "payload": record.payload,
                        "vector": list(record.vector)
                        if record.vector is not None
                        else None,
                    },
                    separators=(",", ":"),
                )
            )
            fh.write("\n")
            written += 1
    console.print(f"[green]Exported[/green] {written} claims to [bold]{output}[/bold]")


@seed_app.command("import")
@core_command(dangerous=True, requires_context=True)
# ID: 0d96f158-176d-4701-9cd9-131b2c2a0f9a
async def import_command(
    ctx: typer.Context,
    source: Path = typer.Argument(
        ...,
        help="JSONL fixture produced by `coherence seed export`.",
    ),
) -> None:
    """Hydrate governance_claims from a JSONL fixture (disaster recovery).

    Does not consult the embedding endpoint — vectors come from the fixture.
    """
    from qdrant_client.http import models as qm

    from body.services.governance_claims_service import GovernanceClaimsService

    context: CoreContext = ctx.obj
    if not source.exists():
        console.print(f"[red]Fixture not found: {source}[/red]")
        raise typer.Exit(code=1)

    try:
        qdrant = await context.registry.get_qdrant_service()
    except Exception as exc:
        logger.exception("Failed to acquire Qdrant service")
        console.print(f"[red]Service unavailable: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    claims_service = GovernanceClaimsService(qdrant)
    await claims_service.ensure_collection()

    points: list[qm.PointStruct] = []
    with source.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            vector = record.get("vector")
            if not vector:
                continue
            points.append(
                qm.PointStruct(
                    id=record["id"],
                    vector=vector,
                    payload=record.get("payload") or {},
                )
            )

    if not points:
        console.print("[yellow]Fixture contained no usable records.[/yellow]")
        raise typer.Exit(code=1)

    batch = 200
    for i in range(0, len(points), batch):
        await qdrant.upsert_points(
            claims_service.collection_name, points[i : i + batch], wait=True
        )

    console.print(
        f"[green]Imported[/green] {len(points)} claims from [bold]{source}[/bold]"
    )
