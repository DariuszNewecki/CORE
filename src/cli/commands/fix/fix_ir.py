# src/cli/commands/fix/fix_ir.py
"""
IR (Incident Response) self-healing commands.

Thin client over POST /v1/fix/ir (ADR-055 D6 Batch C2). The endpoint
always writes; the CLI preserves --write/dry-run UX client-side by
short-circuiting before the call when --write is not set.
"""

from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich.console import Console

from api.cli import CoreApiClient
from cli.utils import core_command

from . import fix_app


logger = logging.getLogger(__name__)
console = Console()

_IR_DIR = Path(".intent") / "mind" / "ir"
_DRY_RUN_PATHS = {
    "triage": _IR_DIR / "triage_log.yaml",
    "log": _IR_DIR / "incident_log.yaml",
}


async def _scaffold(kind: str, label: str, write: bool) -> None:
    rel_path = str(_DRY_RUN_PATHS[kind]).replace("\\", "/")
    if not write:
        console.print(
            f"[yellow]Dry run:[/yellow] would ensure {rel_path} exists with a "
            f"minimal {label.lower()} structure. Use --write to apply."
        )
        return
    client = CoreApiClient()
    result = await client.fix_ir(kind)
    written_path = result.get("path", rel_path)
    console.print(f"[green]✅ Created {label} at {written_path}[/green]")


@fix_app.command("ir-triage", help="Initialize or update the incident triage log.")
@core_command(dangerous=True, confirmation=False)
# ID: c50add43-9412-44ad-b261-6f64aed07b21
async def fix_ir_triage(
    ctx: typer.Context,
    write: bool = typer.Option(
        False,
        "--write",
        help="Apply changes to the IR triage log (creates file if missing).",
    ),
) -> None:
    """
    Bootstrap the IR triage log under .intent/mind/ir/.
    """
    await _scaffold("triage", "IR triage log", write)


@fix_app.command("ir-log", help="Initialize or update the incident response log.")
@core_command(dangerous=True, confirmation=False)
# ID: e2f34a52-0839-4146-bafd-7ce6b559a510
async def fix_ir_log(
    ctx: typer.Context,
    write: bool = typer.Option(
        False,
        "--write",
        help="Apply changes to the IR incident log (creates file if missing).",
    ),
) -> None:
    """
    Bootstrap the main incident response log under .intent/mind/ir/.
    """
    await _scaffold("log", "IR incident log", write)
