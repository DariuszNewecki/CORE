# src/body/cli/commands/check/diagnostics_commands.py
"""
Diagnostic and contract verification commands.

Policy coverage, body UI contracts, and other system diagnostics.
"""

from __future__ import annotations

import typer
from rich.console import Console

from body.cli.logic.body_contracts_checker import check_body_contracts
from body.cli.logic.diagnostics_policy import policy_coverage
from shared.action_types import ActionResult
from shared.cli_utils import core_command


console = Console()


# ID: 9f9ebe73-c1b6-478f-aa52-21adcb64f1e0
@core_command(dangerous=False)
# ID: 83063c77-0e79-4f7a-83ed-0aa19211506a
def diagnostics_cmd(ctx: typer.Context) -> None:
    """
    Audit the constitution for policy coverage and structural integrity.
    """
    _ = ctx
    policy_coverage()


# ID: 3a985f2b-4d76-4c28-9f1e-8e3d2a7b6c9d
@core_command(dangerous=False)
# ID: d57f0bd7-080d-4514-b4a5-76c8efd68ac4
async def check_body_ui_cmd(ctx: typer.Context) -> None:
    """
    Check for Body layer UI contract violations (print, rich usage, os.environ).

    Body modules must be HEADLESS.
    """
    core_context = ctx.obj
    console.print("[bold cyan]🔍 Checking Body UI Contracts...[/bold cyan]")

    result: ActionResult = await check_body_contracts(
        repo_root=core_context.git_service.repo_path
    )

    if not result.ok:
        violations = result.data.get("violations", [])
        console.print(f"\n[red]❌ Found {len(violations)} contract violations:[/red]\n")

        # Group by file for cleaner output
        by_file: dict[str, list[dict]] = {}
        for v in violations:
            path = v.get("file", "unknown")
            by_file.setdefault(path, []).append(v)

        for path, file_violations in by_file.items():
            console.print(f"[bold]{path}[/bold]:")
            for v in file_violations:
                rule = v.get("rule_id", "unknown")
                msg = v.get("message", "")
                line = v.get("line")
                loc = f"line {line}" if line else "general"
                console.print(f"  - [{rule}] {msg} ({loc})")
            console.print()

        console.print(
            "[yellow]💡 Run 'core-admin fix body-ui --write' to auto-fix.[/yellow]"
        )
        raise typer.Exit(1)

    console.print("[green]✅ Body contracts compliant.[/green]")
