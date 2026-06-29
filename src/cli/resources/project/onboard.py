# src/cli/resources/project/onboard.py
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from cli.logic.byor import _stage_dir_for, initialize_repository, promote_staged
from cli.utils import core_command
from shared.context import CoreContext

from . import app


console = Console()


@app.command("onboard")
@core_command(dangerous=True, requires_context=True, requires_brain_services=False)
# ID: e625b650-05c8-421e-9cf7-073917b43dc9
async def onboard_project(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help="Path to existing repository.", exists=True),
    write: bool = typer.Option(
        False, "--write", help="Write .intent/ directory to the target path."
    ),
    stage: bool = typer.Option(
        False,
        "--stage",
        help=(
            "Write to work/staged/<name>/ for inspection before promoting "
            "(ADR-123). Requires --write; ignored in dry-run mode."
        ),
    ),
) -> None:
    """Onboard an existing repository into CORE governance — Phase A (BYOR).

    Delivers the machinery floor (META schemas, taxonomies, constitution stub,
    enforcement/config) into the target's .intent/. No rules are included; run
    `project scout` afterwards to induce and ratify rules for this repo (ADR-119).
    Dry-run by default; pass --write to apply.

    Pass --write --stage to write to work/staged/<name>/ first, inspect the
    files, then run `project onboard promote <path>` to deliver to the target.
    """
    core_context: CoreContext = ctx.obj

    if stage and not write:
        console.print(
            "[yellow]--stage has no effect without --write "
            "(dry-run already previews the delivery).[/yellow]"
        )

    stage_dir: Path | None = None
    if stage and write:
        core_root = core_context.git_service.repo_path.resolve()
        stage_dir = _stage_dir_for(core_root, path)

    if stage_dir is not None:
        mode = f"Staging onboard for (→ {stage_dir})"
    elif write:
        mode = "Onboarding"
    else:
        mode = "Previewing onboarding for"

    console.print(
        f"[bold cyan]⚓ {mode} repository (Phase A — machinery floor):[/bold cyan] {path}"
    )
    await initialize_repository(
        context=core_context, path=path, dry_run=not write, stage_dir=stage_dir
    )

    if stage_dir is not None:
        console.print(
            f"\n[bold green]Staged to[/bold green] {stage_dir / '.intent'}\n"
            f"[dim]Inspect, then run:[/dim]  "
            f"[bold]core-admin project onboard promote {path}[/bold]"
        )


@app.command("promote")
@core_command(dangerous=True, requires_context=True, requires_brain_services=False)
# ID: d2eafb4d-7ead-4d04-bb89-8d78eda8a582
async def promote_onboard(
    ctx: typer.Context,
    path: Path = typer.Argument(
        ...,
        help="Target repository path (same path used with --stage).",
        exists=True,
    ),
) -> None:
    """Promote a staged machinery floor into the target repository (ADR-123).

    Reads from work/staged/<name>/.intent/ (within CORE's repo) and writes to
    <path>/.intent/ via the file.create action. Removes the stage directory on
    success. Run `project onboard promote --help` for full lifecycle details.
    """
    core_context: CoreContext = ctx.obj
    console.print(f"[bold cyan]⚓ Promoting staged onboard to:[/bold cyan] {path}")
    await promote_staged(context=core_context, path=path)
    console.print(
        f"[bold green]Promoted to[/bold green] {Path(path).resolve() / '.intent'}"
    )
