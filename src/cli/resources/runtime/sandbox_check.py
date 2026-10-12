# src/cli/resources/runtime/sandbox_check.py
"""
``core-admin runtime sandbox-check`` — prove the sandbox's walls (ADR-132 D10.10, M1).

Runs the closure probes (``body.sandbox.probes``) through the sandbox, one
job per probe, and prints one row per wall. Run it as the services account,
the only account the service accepts:

    sudo -u core core-admin runtime sandbox-check --mode service

Then stop the socket (``sudo systemctl stop core-sandbox.socket``) and run it
again: every probe must be ``not_run`` (fail closed).

``--mode local`` runs the same probes without the service; most walls then
fail, which is what ``local`` mode means.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from body.sandbox.client import DEFAULT_SOCKET, MODES
from body.sandbox.probes import run_probes
from cli.utils import async_command
from shared.config import settings
from shared.logger import getLogger

from .health import runtime_app


logger = getLogger(__name__)
console = Console()


@runtime_app.command("sandbox-check")
@async_command
# ID: ae06bfde-3417-406c-92f1-02a946d8def3
async def sandbox_check_cmd(
    mode: str = typer.Option("service", "--mode", help="service | local"),
    socket_path: Path = typer.Option(
        DEFAULT_SOCKET,
        "--socket",
        help="The sandbox service's socket.",
        # Click checks a Path option is readable; the socket belongs to core,
        # so any other account was refused even for --mode local, which
        # never opens it. Reaching the socket is the client's to report.
        readable=False,
    ),
) -> None:
    """Run the sandbox closure probes and show which walls held."""
    if mode not in MODES:
        console.print(
            f"[red]Unknown mode {mode!r}; use one of {', '.join(MODES)}.[/red]"
        )
        raise typer.Exit(2)
    # DEMO 3/3: a deliberate post-deploy probe failure; reverted by the next PR.
    if mode == "service":
        raise typer.Exit(1)
    rows = await run_probes(
        Path(settings.REPO_PATH), mode=mode, socket_path=socket_path
    )
    table = Table(title=f"Sandbox walls ({mode})")
    for column in ("probe", "status", "isolation", "reason"):
        table.add_column(column)
    for row in rows:
        colour = "green" if row["status"] == "passed" else "red"
        table.add_row(
            row["probe"],
            f"[{colour}]{row['status']}[/{colour}]",
            row["isolation"],
            row["reason"],
        )
    console.print(table)
    for detail in dict.fromkeys(row["detail"] for row in rows if row.get("detail")):
        console.print(Panel(Text(detail), title="sandbox stderr", expand=False))
    if any(row["status"] != "passed" for row in rows):
        raise typer.Exit(1)
