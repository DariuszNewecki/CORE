# src/cli/commands/check.py
"""
Registers and implements the verb-based 'check' command group.
Refactored under dry_by_design to use the canonical context setter.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import typer
from cli.logic.audit import _print_summary_findings, audit, lint, test_system
from cli.logic.diagnostics import policy_coverage
from features.project_lifecycle.integration_service import check_integration_health
from shared.context import CoreContext
from shared.logger import getLogger

log = getLogger("check_command")
check_app = typer.Typer(
    help="Read-only validation and health checks.",
    no_args_is_help=True,
)

_context: Optional[CoreContext] = None


# ID: 7eb85868-3ff1-4696-89cc-3fb89e8a37c8
def set_context(context: CoreContext):
    """Sets the shared context for the logic layer."""
    global _context
    _context = context
    # This module no longer needs to forward context, as the main CLI does it.


check_app.command("audit", help="Run the full constitutional self-audit.")(audit)
check_app.command("lint", help="Check code formatting and quality.")(lint)
check_app.command("tests", help="Run the pytest suite.")(test_system)
check_app.command("diagnostics", help="Audit the constitution for policy coverage.")(
    policy_coverage
)


@check_app.command(
    "system",
    help="Run the full developer sync & audit sequence (non-destructive).",
)
# ID: d455ad07-870d-442a-8f56-a9dadaecc441
def system_check_command():
    """
    Runs the full integration health check without committing or rolling back.
    """
    if not _context:
        raise typer.Exit("Context not set for system check command.")

    success = asyncio.run(check_integration_health(context=_context))
    if not success:
        log.error("System check failed. See audit findings above.")
        if _context.auditor_context.last_findings:
            log.info("Displaying audit findings from failed system check:")
            _print_summary_findings(_context.auditor_context.last_findings)
        raise typer.Exit(code=1)
