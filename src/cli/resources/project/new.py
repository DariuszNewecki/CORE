# src/cli/resources/project/new.py
"""
`core-admin project new <name>` — Generate bootstrap stage (ADR-119 Amendment 2026-10-02).

Operator command (ADR-146 D3). Creates ``<parent>/<name>`` holding CORE's machinery
floor and a neutral Python skeleton — no project-specific law. ``--path`` chooses the
parent directory (default: the current directory). CORE's own repository is the
source checkout the CLI runs from (``core_source_root``), never the repository found
by walking up from the current directory; an installed wheel has none to protect.
File-only: needs no database, Qdrant or LLM, so it works from a plain pip install.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from cli.logic.byor import core_source_root
from cli.logic.project_scaffold import plan_new_project, write_new_project
from cli.utils import core_command

from . import app


console = Console()


@app.command("new")
@core_command(
    dangerous=True,
    requires_context=False,
    confirmation=True,
    requires_brain_services=False,
)
# ID: 32d44823-26a9-4059-8b64-969a46953225
async def new_project_command(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="The name of the new project."),
    path: Path | None = typer.Option(
        None,
        "--path",
        help="Parent directory for the new project (default: current directory).",
    ),
    write: bool = typer.Option(
        False, "--write", help="Actually create the directories and files."
    ),
) -> None:
    """
    Create a new repository ready to host project law (no law is created).

    Delivers CORE's machinery floor into .intent/ plus a minimal Python skeleton.
    The result is not auditable until rules are authored or ratified, or a
    governance pack is explicitly adopted.
    """
    core_root = core_source_root()
    parent = (path if path is not None else Path.cwd()).expanduser().resolve()

    plan = plan_new_project(name, parent, core_root)
    count = write_new_project(plan, core_root, write=write)

    if not write:
        console.print(
            f"[bold cyan]Preview:[/bold cyan] {count} files would be created at "
            f"{plan.target_root} ({len(plan.floor_copies)} machinery-floor files, "
            f"{len(plan.skeleton_files)} skeleton files)."
        )
        for _src, rel in plan.floor_copies:
            console.print(f"   {rel}")
        for rel, _text in plan.skeleton_files:
            console.print(f"   {rel}")
        console.print("Pass [cyan]--write[/cyan] to create it.")
        return

    console.print(
        f"[bold green]Project substrate created:[/bold green] {plan.target_root} "
        f"({count} files)."
    )
    console.print(
        "No project-specific law has been established. `code audit` fails closed "
        "until you author or ratify rules, or explicitly adopt an appropriate "
        "governance pack (see `core-admin project adopt-pack --help`)."
    )
