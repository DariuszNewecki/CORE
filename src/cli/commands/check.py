# src/cli/commands/check.py
"""
Registers and implements the verb-based 'check' command group.
Refactored under dry_by_design to use the canonical context setter.
"""

from __future__ import annotations

from typing import Optional

import typer
from cli.logic.audit import audit, lint, test_system
from cli.logic.diagnostics import policy_coverage
from shared.context import CoreContext
from shared.logger import getLogger

log = getLogger("check_command")
check_app = typer.Typer(
    help="Read-only validation and health checks.",
    no_args_is_help=True,
)

_context: Optional[CoreContext] = None


check_app.command("audit", help="Run the full constitutional self-audit.")(audit)
check_app.command("lint", help="Check code formatting and quality.")(lint)
check_app.command("tests", help="Run the pytest suite.")(test_system)
check_app.command("diagnostics", help="Audit the constitution for policy coverage.")(
    policy_coverage
)
