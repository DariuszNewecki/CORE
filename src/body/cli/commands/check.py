# src/body/cli/commands/check.py
"""
Registers and implements the verb-based 'check' command group.
Refactored to use the Constitutional CLI Framework (@core_command).
"""

from __future__ import annotations

import typer
from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.logger import getLogger

from body.cli.logic.audit import lint, run_audit_workflow, test_system
from body.cli.logic.diagnostics import policy_coverage

logger = getLogger(__name__)
check_app = typer.Typer(
    help="Read-only validation and health checks.", no_args_is_help=True
)


@check_app.command("audit")
@core_command(dangerous=False)
# ID: 6617d898-d6b6-4b99-8884-008c39a9cf64
async def audit_cmd(
    ctx: typer.Context,
    severity: str = typer.Option(
        "warning",
        "--severity",
        "-s",
        help="Filter findings by minimum severity level (info, warning, error).",
        case_sensitive=False,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show all individual findings instead of a summary.",
    ),
) -> None:
    """
    Run the full constitutional self-audit.

    Checks:
    - Knowledge Graph Integrity
    - Policy Compliance
    - Safety & Security Rules
    - Architecture & Dependency Injection
    """
    core_context: CoreContext = ctx.obj
    # The framework ensures JIT services (like Qdrant) are ready for the auditor
    await run_audit_workflow(core_context, severity=severity, verbose=verbose)


@check_app.command("lint")
@core_command(dangerous=False)
# ID: 3e9d4bfb-3362-45c0-82c1-4f1d2938d3d2
def lint_cmd(ctx: typer.Context) -> None:
    """
    Check code formatting and quality using Black and Ruff.
    """
    # This is a synchronous wrapper around subprocess calls
    lint()


@check_app.command("tests")
@core_command(dangerous=False)
# ID: 9f7dac27-675a-4a98-9155-462ee1f92295
def tests_cmd(ctx: typer.Context) -> None:
    """
    Run the project test suite via pytest.
    """
    test_system()


@check_app.command("diagnostics")
@core_command(dangerous=False)
# ID: 7ba53eda-d484-4d3c-a23f-28e5cc1cbaa6
def diagnostics_cmd(ctx: typer.Context) -> None:
    """
    Audit the constitution for policy coverage and structural integrity.
    """
    policy_coverage()


@check_app.command("system")
@core_command(dangerous=False)
# ID: 7d692d16-0ce3-4846-ac2a-6433db29b9d2
async def system_cmd(ctx: typer.Context) -> None:
    """
    Run all system health checks: Lint, Tests, and Constitutional Audit.
    """
    from rich.console import Console

    console = Console()

    console.rule("[bold cyan]1. Code Quality (Lint)[/bold cyan]")
    lint()

    console.rule("[bold cyan]2. System Integrity (Tests)[/bold cyan]")
    test_system()

    console.rule("[bold cyan]3. Constitutional Compliance (Audit)[/bold cyan]")
    core_context: CoreContext = ctx.obj
    await run_audit_workflow(core_context)
