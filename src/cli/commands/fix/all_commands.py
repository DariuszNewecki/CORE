# src/cli/commands/fix/all_commands.py
"""
Batch execution command for the 'fix' CLI group.

`core-admin fix all` runs a curated sequence of registered atomic
actions via POST /v1/fix/run/{fix_id} and POST /v1/fix/ir. The
sequence preserves the original prerequisite ordering.

Three pre-migration steps (purge-legacy-tags, policy-ids, db-registry)
have no registered atomic action and were dropped from the sequence —
they remain available as standalone CLI subcommands. Filed as
governance debt; future Stage B reopens may restore the bundle.
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console

from api.cli import CoreApiClient
from cli.utils import core_command

from . import COMMAND_CONFIG, fix_app


logger = logging.getLogger(__name__)
console = Console()


_PLAN: list[tuple[str, str, str | None]] = [
    # (step name, fix_id for /fix/run, or ir_kind for /fix/ir)
    ("code-style", "fix.format", None),
    ("ids", "fix.ids", None),
    ("knowledge-sync", "sync.db", None),
    ("vector-sync", "sync.vectors.code", None),
    ("docstrings", "fix.docstrings", None),
    ("tags", "fix.capability_tagging", None),
    ("ir-triage", "", "triage"),
    ("ir-log", "", "log"),
]


@fix_app.command("all", help="Run a curated sequence of self-healing fixes.")
@core_command(dangerous=True, confirmation=True)
# ID: af5b3d93-3b58-45f9-bce6-33a5886d2a3c
async def run_all_fixes(
    ctx: typer.Context,
    skip_dangerous: bool = typer.Option(
        True, help="Skip potentially dangerous operations that modify code logic."
    ),
    write: bool = typer.Option(
        False, "--write", help="Apply changes. Default is dry-run."
    ),
) -> None:
    """
    Run a curated set of fix subcommands in a sequence that respects dependencies.
    """
    _ = ctx
    client = CoreApiClient()
    mode_str = "write" if write else "dry-run"

    for name, fix_id, ir_kind in _PLAN:
        cfg = COMMAND_CONFIG.get(name, {})
        is_dangerous = cfg.get("dangerous", False)
        if skip_dangerous and is_dangerous and write:
            console.print(f"[yellow]Skipping dangerous command 'fix {name}'.[/yellow]")
            continue
        console.print(f"[bold cyan]▶ Running 'fix {name}' ({mode_str})[/bold cyan]")

        if ir_kind is not None:
            try:
                result = await client.fix_ir(ir_kind)
                console.print(f"   -> IR scaffold: {result.get('path', '(unknown)')}")
            except Exception as exc:
                console.print(f"   [red]✗ fix {name} failed: {exc}[/red]")
            continue

        initial = await client.run_fix(fix_id, write=write)
        run_id = initial.get("run_id")
        if not run_id:
            console.print(f"   [red]✗ {fix_id} failed to dispatch: {initial}[/red]")
            continue
        final = await client._poll_run(run_id)
        status = final.get("status")
        if status != "completed":
            console.print(
                f"   [red]✗ {fix_id} failed: {final.get('error') or final}[/red]"
            )
            continue
        console.print(f"   [green]✓ {fix_id} completed.[/green]")

    console.print("[green]✅ 'fix all' sequence completed[/green]")
