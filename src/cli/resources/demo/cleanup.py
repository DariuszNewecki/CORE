# src/cli/resources/demo/cleanup.py
"""
`core-admin demo cleanup <run_id>` — remove a retained demo workspace (ADR-155 D11).

A consequence-chain run retains its disposable filesystem when it fails, is
interrupted, or is run with ``--keep-workspace``. This command removes exactly
one such workspace, and only through the marker-checked cleanup surface, so the
same D3 escape/marker/parent/root guards that protect the automatic path protect
the manual one. It never removes anything the guards do not confirm is a
run-scoped disposable directory.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from cli.utils.decorators import core_command
from cli.utils.exit_codes import EXIT_CONFIG_ERROR, EXIT_OK
from shared.cli.command_meta import (
    CommandBehavior,
    CommandExposure,
    CommandLayer,
    command_meta,
)
from shared.config import settings
from shared.infrastructure.git_service import GitService
from shared.logger import getLogger

from .hub import app


logger = getLogger(__name__)
console = Console()


@app.command("cleanup")
@command_meta(
    canonical_name="demo.cleanup",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.BODY,
    exposure=CommandExposure.USER_FACING,
    summary="Remove a retained isolated-demo workspace by run id.",
    # Genuinely mutating: it deletes a run-scoped directory. `cli.dangerous_explicit`
    # therefore requires dangerous=True + a `write` parameter (ADR-155 Phase 4,
    # governor-approved 2026-07-24). Unlike `consequence-chain`, this is real
    # removal, so the dry-run-by-default contract is a fitting safety layer.
    dangerous=True,
)
@core_command(dangerous=True, requires_context=False, requires_brain_services=False)
# ID: 835f484b-ea98-4e31-94d0-da6528cd283e
async def cleanup_cmd(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="The run id of the retained demo workspace."),
    write: bool = typer.Option(
        False,
        "--write",
        help="Actually remove the workspace. Without it, preview the target only.",
    ),
) -> None:
    """Remove (or, without ``--write``, preview) the retained workspace for ``run_id``.

    Both modes run the *identical* marker/containment/symlink/run-id/source-repo
    guards via ``GitService.marker_checked_resolve``. Without ``--write`` nothing
    is removed — the validated target is displayed only. With ``--write`` the
    same-guarded ``marker_checked_remove`` performs the deletion.
    """
    demo_state_dir: Path = settings.CORE_DEMO_STATE_DIR
    state_dir = demo_state_dir / "runs" / run_id
    try:
        # Validate first — identical guards in both modes. Removes nothing here.
        target = GitService.marker_checked_resolve(state_dir, run_id, demo_state_dir)
    except ValueError as exc:
        # Guard refusal, missing target, or unsafe run_id — an operator/usage
        # error, not an internal fault. Nothing was removed.
        console.print(f"[bold red]Cleanup refused:[/bold red] {exc}")
        raise typer.Exit(EXIT_CONFIG_ERROR) from exc

    if not write:
        console.print(
            f"[yellow]DRY RUN[/yellow] — would remove demo workspace for run {run_id}:\n"
            f"  {target}\n"
            "Pass [cyan]--write[/cyan] to remove it."
        )
        raise typer.Exit(EXIT_OK)

    GitService.marker_checked_remove(state_dir, run_id, demo_state_dir)
    console.print(f"[green]Removed demo workspace for run {run_id}.[/green]")
    raise typer.Exit(EXIT_OK)
