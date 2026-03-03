# src/cli/commands/check/quality.py
"""
Code quality and system health commands.

Handles lint, tests, and system-wide health checks.
Refactored to support async test execution and ActionResult reporting.
"""

from __future__ import annotations

import typer
from rich.console import Console

from mind.enforcement.audit import lint, test_system
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.cli_utils import core_command


console = Console()


@core_command(dangerous=False)
# ID: 23a0948a-570d-442d-b19a-ebd3af4f1c2d
def lint_cmd(ctx: typer.Context) -> None:
    """
    Check code formatting and quality using Black and Ruff.
    """
    _ = ctx
    lint()


@core_command(dangerous=False)
@atomic_action(
    action_id="tests.cmd",
    intent="Atomic action for tests_cmd",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 3e9af575-9c8b-483d-b63a-477e5c6b0a02
async def tests_cmd(ctx: typer.Context) -> ActionResult:
    """
    Run the project test suite via pytest.

    Returns an ActionResult which is automatically formatted by the
    Constitutional CLI Framework.
    """
    _ = ctx
    # Await the now-async test runner
    return await test_system()


@core_command(dangerous=False)
# ID: fdb8e693-c147-469a-a17a-1ee59227985b
async def system_cmd(ctx: typer.Context) -> None:
    """
    Run all system health checks: Lint, Tests, and Constitutional Audit.
    """
    # Import here to avoid circular import
    from cli.commands.check.audit import audit_cmd

    console.rule("[bold cyan]1. Code Quality (Lint)[/bold cyan]")
    lint()

    console.rule("[bold cyan]2. System Integrity (Tests)[/bold cyan]")
    # Await the async test runner
    await test_system()

    console.rule("[bold cyan]3. Constitutional Compliance (Audit)[/bold cyan]")
    await audit_cmd(ctx)
