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
)
@core_command(dangerous=False, requires_context=False, requires_brain_services=False)
# ID: 835f484b-ea98-4e31-94d0-da6528cd283e
async def cleanup_cmd(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="The run id of the retained demo workspace."),
) -> None:
    """Remove the retained disposable workspace for ``run_id`` (marker-checked)."""
    demo_state_dir: Path = settings.CORE_DEMO_STATE_DIR
    state_dir = demo_state_dir / "runs" / run_id
    try:
        GitService.marker_checked_remove(state_dir, run_id, demo_state_dir)
    except ValueError as exc:
        # Guard refusal, missing target, or unsafe run_id — an operator/usage
        # error, not an internal fault. Nothing was removed.
        console.print(f"[bold red]Cleanup refused:[/bold red] {exc}")
        raise typer.Exit(EXIT_CONFIG_ERROR) from exc

    console.print(f"[green]Removed demo workspace for run {run_id}.[/green]")
    raise typer.Exit(EXIT_OK)
