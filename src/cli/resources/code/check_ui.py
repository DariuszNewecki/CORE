# src/cli/resources/code/check_ui.py
"""
Code UI Compliance Action.
Ensures Body-layer modules are HEADLESS (no print, rich, or direct os.environ).
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
from typing import TYPE_CHECKING

import typer
from rich.console import Console

from shared.cli_utils import core_command

from .hub import app


if TYPE_CHECKING:
    from shared.context import CoreContext
console = Console()


@app.command("check-ui")
@core_command(dangerous=True, requires_context=True)
# ID: 662d6bed-c6fc-4120-ae34-d9063f703994
async def check_ui_cmd(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Use LLM to autonomously fix UI contract violations."
    ),
) -> None:
    """
    Check and repair Body-layer UI contract violations.

    Validates that logic in features/ and services/ does not use:
    - print() or input()
    - rich.console or formatting
    - os.environ (must use shared.config.settings)

    If --write is used, CORE invokes an AI specialist to refactor the
    violating modules into a headless state.
    """
    core_context: CoreContext = ctx.obj
    repo_root = core_context.git_service.repo_path
    if not write:
        from cli.logic.body_contracts_checker import check_body_contracts

        logger.info("[bold cyan]🔍 Checking Body UI Contracts...[/bold cyan]")
        result = await check_body_contracts(repo_root=repo_root)
        if not result.ok:
            violations = result.data.get("violations", [])
            logger.info(
                "\n[red]❌ Found %s contract violations.[/red]", len(violations)
            )
            logger.info("[yellow]💡 Run with '--write' to auto-fix via LLM.[/yellow]")
        return
    from cli.logic.body_contracts_fixer import fix_body_ui_violations

    logger.info("[bold cyan]🔧 Refactoring UI leaks out of Body layer...[/bold cyan]")
    await fix_body_ui_violations(
        core_context=core_context, write=True, repo_root=repo_root
    )
