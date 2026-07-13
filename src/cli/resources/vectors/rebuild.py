# src/cli/resources/vectors/rebuild.py
"""
Vector store cold-rebuild command.

Repopulates Qdrant after a wipe (e.g. a major-version upgrade whose on-disk
segment format is incompatible with the prior version) by driving both
sync.vectors_code (force re-embed) and sync.vectors_constitution through
the ActionExecutor in one operator-invokable command. Neither action
exposed a `force`-capable CLI surface before this; see #777.

Unlike `dev sync`, this does not run fix.format / fix.ids — it only
touches the vector store, so it is safe to run alongside in-flight
working-tree changes.
"""

from __future__ import annotations

import typer
from rich.console import Console

from cli.utils import core_command
from shared.context import CoreContext
from shared.logger import getLogger

from .hub import app


logger = getLogger(__name__)
console = Console()

# sync.vectors_code embeds a bounded batch per call (max_embedding_passes x
# artifact_embed_batch_size, governed by operational_config.yaml). A full
# cold rebuild of a multi-thousand-artifact repo needs many calls; cap the
# outer loop generously rather than assuming a single call drains it.
_MAX_REBUILD_PASSES = 500


@app.command("rebuild")
@core_command(dangerous=True, requires_context=True, confirmation=True)
# ID: 1fb877dc-a9fb-4d3f-85d5-301edd6a2a76
async def rebuild_vectors(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Persist rebuilt vectors to Qdrant (default: dry-run)."
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt for this dangerous operation.",
    ),
) -> None:
    """
    Cold-rebuild the vector store: force re-embed code/tests, then reindex
    constitutional documents (policies, patterns, specs).

    Use after a Qdrant wipe to repopulate all five collections in one
    operator-invokable command instead of a manual API call sequence.
    """
    context: CoreContext = ctx.obj
    if context.action_executor is None:
        logger.error("action_executor not initialized")
        raise typer.Exit(1)

    mode = "WRITE" if write else "DRY-RUN"
    console.print(f"[bold cyan]🔁 Vector store cold-rebuild ({mode})[/bold cyan]")

    console.print("\n[bold]Phase 1/2: sync.vectors_code (force re-embed)[/bold]")
    force = True
    passes = 0
    while True:
        passes += 1
        code_result = await context.action_executor.execute(
            "sync.vectors_code", write=write, force=force
        )
        if not code_result.ok:
            console.print(
                f"[bold red]❌ sync.vectors_code failed: {code_result.data}[/bold red]"
            )
            raise typer.Exit(1)

        data = code_result.data
        status = data.get("status")
        pending = data.get("pending_remaining", 0)
        console.print(
            f"  pass {passes}: status={status} reset={data.get('reset_count', 0)}"
            f" pending_remaining={pending}"
        )

        if not write or status == "dry_run":
            break
        force = False
        if pending == 0:
            break
        if passes >= _MAX_REBUILD_PASSES:
            console.print(
                f"[yellow]Reached pass cap ({_MAX_REBUILD_PASSES}) with {pending}"
                " artifact(s) still pending — re-run `vectors rebuild --write`"
                " to continue.[/yellow]"
            )
            break

    console.print("\n[bold]Phase 2/2: sync.vectors_constitution[/bold]")
    constitution_result = await context.action_executor.execute(
        "sync.vectors_constitution", write=write
    )
    if not constitution_result.ok:
        console.print(
            f"[bold red]❌ sync.vectors_constitution failed:"
            f" {constitution_result.data}[/bold red]"
        )
        raise typer.Exit(1)
    console.print(f"  {constitution_result.data}")

    if write:
        console.print("\n[bold green]✅ Vector store rebuild complete.[/bold green]")
    else:
        console.print("\n[yellow]DRY-RUN completed — use --write to apply[/yellow]")
