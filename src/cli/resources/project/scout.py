# src/cli/resources/project/scout.py
from pathlib import Path

import typer
from rich.console import Console

from cli.logic.scout import induce_rules
from cli.utils import core_command
from shared.context import CoreContext

from . import app


console = Console()


@app.command("scout")
@core_command(dangerous=True, requires_context=True, requires_brain_services=False)
# ID: 2d293e8f-d463-4bdd-871b-549e2aff04a5
async def scout_project(
    ctx: typer.Context,
    path: Path = typer.Argument(
        ..., help="Path to the target repository.", exists=True
    ),
    write: bool = typer.Option(
        False, "--write", help="Write inducted rules to .intent/ after ratification."
    ),
    reset: bool = typer.Option(
        False,
        "--reset",
        help="Clear existing scout_inducted.json and candidate cache, then re-run induction.",
    ),
) -> None:
    """
    Induce and ratify governance rules for a repository — Phase B (BYOR Scout).

    Reads the target repo's source code, proposes candidate rules in CORE's
    enforcement vocabulary (LLM-assisted; falls back to a universal menu when no
    LLM is available), and walks you through per-rule ratification. Only confirmed
    rules are written (ADR-119 D5 — no --accept-all). Requires Phase A first:
    run `project onboard <target> --write` before this command.

    Pass --reset to clear a prior induction and start fresh (e.g. after the repo
    has evolved significantly or to get a new LLM pass with updated signals).
    """
    core_context: CoreContext = ctx.obj
    console.print(f"[bold cyan]🔍 Scout (Phase B) — target:[/bold cyan] {path}")
    await induce_rules(context=core_context, path=path, dry_run=not write, reset=reset)
