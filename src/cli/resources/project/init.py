# src/cli/resources/project/init.py
"""
`core-admin project init [PATH]` — deliver CORE's machinery floor into an existing repository.

The existing-repository sibling of ``project new``: the same bundled floor, no
skeleton, no rules. File-only: needs no database, Qdrant, LLM or running CORE
API, so it works from a plain pip install (#1023). Never overwrites an existing
``.intent/``. Then ``project adopt-pack`` and ``code audit --offline``.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from body.services.outside_write_ledger import OutsideWriteLog
from cli.logic.byor import core_source_root
from cli.logic.project_scaffold import plan_init, write_init
from cli.utils import core_command

from . import app


console = Console()


@app.command("init")
@core_command(
    dangerous=True,
    requires_context=False,
    confirmation=True,
    requires_brain_services=False,
)
# ID: 3eee4dbd-8f37-44f0-9461-64c15fe11614
async def init_project_command(
    ctx: typer.Context,
    path: Path = typer.Argument(
        Path("."), help="The existing repository (default: the current directory)."
    ),
    write: bool = typer.Option(
        False, "--write", help="Actually copy the machinery floor."
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt for this dangerous operation.",
    ),
) -> None:
    """
    Prepare an existing repository to host project law (no law is created).

    Copies CORE's machinery floor into <path>/.intent/. The repository is not
    auditable until a governance pack is adopted or rules are authored.

    Example: core-admin project init . --write
    """
    core_root = core_source_root()
    plan = plan_init(path, core_root)
    # ADR-169 D5: the files are outside CORE's repository; each write is
    # recorded when a CORE ledger is configured (#953).
    outside = OutsideWriteLog(plan.target_root, produced_by="project.init")
    if write:
        await outside.require_ledger()
    try:
        count = write_init(plan, core_root, write=write, outside=outside)
    finally:
        await outside.flush()

    if not write:
        console.print(
            f"[bold cyan]Preview:[/bold cyan] {count} machinery-floor files would be "
            f"copied into {plan.target_root / '.intent'}, and CORE's GitHub Action "
            f"workflow written to {plan.workflow[0]} unless one is there."
        )
        console.print("Pass [cyan]--write[/cyan] to copy them.")
        return
    console.print(
        f"[bold green]Machinery floor delivered:[/bold green] {plan.target_root} "
        f"({count} files in .intent/)."
    )
    workflow = plan.workflow[0]
    if (plan.target_root / workflow).read_text(encoding="utf-8") == plan.workflow[1]:
        console.print(
            f"CORE's GitHub Action: [cyan]{workflow}[/cyan] audits every pull "
            "request once committed; its verdict is the authoritative one."
        )
    else:
        console.print(
            f"[yellow]{workflow} already exists and was left as it is.[/yellow]"
        )
    console.print(
        "Next: [cyan]core-admin project adopt-pack core/starter-python --write[/cyan], "
        "commit .intent/ and the workflow ([cyan]git add .intent .github && git "
        "commit[/cyan]), then "
        "[cyan]core-admin code audit --offline[/cyan]."
    )
