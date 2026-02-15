# src/body/cli/resources/code/check_ui.py
# ID: c1b2a3d4-e5f6-7890-abcd-ef1234567892

"""
Code UI Compliance Action.
Ensures Body-layer modules are HEADLESS (no print, rich, or direct os.environ).
"""

from __future__ import annotations

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
# ID: 9901b6c7-9b5f-4a65-8130-6e9a963b4193
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
        # 1. READ-ONLY MODE: Run the checker
        from body.cli.logic.body_contracts_checker import check_body_contracts

        console.print("[bold cyan]🔍 Checking Body UI Contracts...[/bold cyan]")
        result = await check_body_contracts(repo_root=repo_root)

        if not result.ok:
            violations = result.data.get("violations", [])
            console.print(
                f"\n[red]❌ Found {len(violations)} contract violations.[/red]"
            )
            console.print("[yellow]💡 Run with '--write' to auto-fix via LLM.[/yellow]")
            # The result display is handled by @core_command
        return

    # 2. WRITE MODE: Run the fixer (LLM-powered)
    from body.cli.logic.body_contracts_fixer import fix_body_ui_violations

    console.print("[bold cyan]🔧 Refactoring UI leaks out of Body layer...[/bold cyan]")

    # fix_body_ui_violations returns an ActionResult
    await fix_body_ui_violations(
        core_context=core_context, write=True, repo_root=repo_root
    )
