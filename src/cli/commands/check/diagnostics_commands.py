# src/cli/commands/check/diagnostics_commands.py
"""
Diagnostic and contract verification commands.

Policy coverage, body UI contracts, and other system diagnostics.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console

from cli.logic.body_contracts_checker import check_body_contracts
from cli.logic.diagnostics_policy import policy_coverage
from cli.utils import core_command
from shared.action_types import ActionResult


console = Console()


@core_command(dangerous=False)
# ID: 2d3aad66-4285-48c7-b65d-f32ab7f86a01
def diagnostics_cmd(ctx: typer.Context) -> None:
    """
    Audit the constitution for policy coverage and structural integrity.
    """
    _ = ctx
    policy_coverage()


@core_command(dangerous=False)
# ID: a2eeec63-e811-4430-8e97-7d317bd0c384
async def check_body_ui_cmd(ctx: typer.Context) -> None:
    """
    Check for Body layer UI contract violations (print, rich usage, os.environ).

    Body modules must be HEADLESS.
    """
    core_context = ctx.obj
    logger.info("[bold cyan]🔍 Checking Body UI Contracts...[/bold cyan]")
    result: ActionResult = await check_body_contracts(
        repo_root=core_context.git_service.repo_path
    )
    if not result.ok:
        violations = result.data.get("violations", [])
        logger.info("\n[red]❌ Found %s contract violations:[/red]\n", len(violations))
        by_file: dict[str, list[dict]] = {}
        for v in violations:
            path = v.get("file", "unknown")
            by_file.setdefault(path, []).append(v)
        for path, file_violations in by_file.items():
            logger.info("[bold]%s[/bold]:", path)
            for v in file_violations:
                rule = v.get("rule_id", "unknown")
                msg = v.get("message", "")
                line = v.get("line")
                loc = f"line {line}" if line else "general"
                logger.info("  - [%s] %s (%s)", rule, msg, loc)
            logger.info()
        logger.info(
            "[yellow]💡 Run 'core-admin fix body-ui --write' to auto-fix.[/yellow]"
        )
        raise typer.Exit(1)
    logger.info("[green]✅ Body contracts compliant.[/green]")
