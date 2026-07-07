# src/cli/resources/code/bridges.py
"""CLI command: list declared architecture bridge points (issue #617)."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from cli.utils import core_command
from shared.cli.command_meta import (
    CommandBehavior,
    CommandExposure,
    CommandLayer,
    command_meta,
)

from .hub import app


console = Console()


@app.command("bridges")
@command_meta(
    canonical_name="code.bridges",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.SHARED,
    exposure=CommandExposure.GOVERNOR_ONLY,
    summary="List declared architecture bridge points where data crosses layer boundaries.",
    dangerous=False,
)
@core_command(dangerous=False, requires_context=False)
# ID: 5b2e91f3-a4c8-4d7e-b6f0-8c1a9d2e3f04
async def list_bridges_cmd(
    consuming: str | None = typer.Option(
        None,
        "--consuming",
        "-c",
        help="Filter by consuming type (e.g. AuditFinding, Proposal).",
    ),
) -> None:
    """
    List declared architecture bridge points.

    Each bridge is a constitutionally-declared data-flow crossing where
    information moves between CORE layers. Use --consuming to find bridges
    that consume a specific data type.

    Example:
      core-admin code bridges --consuming AuditFinding
    """
    from shared.infrastructure.intent.architecture_bridges import (
        bridges_consuming,
        load_bridges,
    )

    bridges = bridges_consuming(consuming) if consuming else load_bridges()

    if not bridges:
        if consuming:
            console.print(
                f"[yellow]No bridges found consuming type '{consuming}'.[/yellow]"
            )
        else:
            console.print("[yellow]No bridge declarations found.[/yellow]")
        return

    title = (
        f"Architecture Bridges (consuming '{consuming}')"
        if consuming
        else "Architecture Bridges"
    )
    table = Table(title=title, header_style="bold cyan", show_lines=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Bridge Class", style="bold")
    table.add_column("Layer", style="blue")
    table.add_column("Source", style="dim")
    table.add_column("Sink Target", style="green")
    table.add_column("Attribution", style="magenta")
    table.add_column("ADRs", style="dim")

    for bridge in sorted(bridges, key=lambda b: b.id):
        table.add_row(
            bridge.id,
            bridge.bridge_class,
            bridge.bridge_layer,
            bridge.source_layer or bridge.source_context[:40],
            bridge.sink_target,
            f"{bridge.attribution_mechanism} → {bridge.attribution_field}"
            if bridge.attribution_field
            else bridge.attribution_mechanism,
            ", ".join(bridge.authority_adrs),
        )

    console.print(table)
