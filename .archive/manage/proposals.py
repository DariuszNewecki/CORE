# src/body/cli/commands/manage/proposals.py
# ID: body.cli.commands.manage.proposals

"""
Manage proposals (administrative view).

Golden-path adjustments (Phase 1, non-breaking):
- Consolidate approval workflow to `autonomy approve`.
- `manage proposals approve` is kept as a deprecated wrapper for compatibility,
  but is now EXACTLY wired to autonomy's underlying async implementation.

Notes:
- We keep `--write` + confirmation here because manage/* is explicitly a
  "state-changing admin" surface and you already established that pattern.
"""

from __future__ import annotations

import typer
from rich.console import Console

from body.cli.logic.proposal_service import (
    proposals_list,
    proposals_sign,
)
from shared.cli_utils import core_command, deprecated_command


console = Console()

# THIS NAME MUST MATCH THE IMPORT IN __init__.py
proposals_sub_app = typer.Typer(
    help="Manage constitutional amendment proposals.",
    no_args_is_help=True,
)

# Re-using existing logic functions from proposal_service.py
proposals_sub_app.command("list")(proposals_list)
proposals_sub_app.command("sign")(proposals_sign)


@proposals_sub_app.command("approve")
@core_command(dangerous=True, confirmation=True)
# ID: e82a93be-6869-4c15-bb77-bd1b321038f6
async def approve_command_wrapper(
    ctx: typer.Context,
    proposal_id: str = typer.Argument(..., help="Proposal ID to approve."),
    approved_by: str = typer.Option("cli_admin", "--by", help="Approver identity"),
    write: bool = typer.Option(False, "--write", help="Apply the approval."),
) -> None:
    """
    DEPRECATED wrapper.

    Canonical workflow:
      core-admin autonomy approve <proposal_id> --by <name>

    This wrapper exists only to preserve backwards compatibility and to keep
    the admin-style `--write` gating.
    """
    deprecated_command("manage proposals approve", "autonomy approve")

    if not write:
        console.print(
            "[yellow]Dry run not supported for approvals. Use --write to approve.[/yellow]"
        )
        return

    # Exact binding to autonomy implementation (no signature guessing).
    # This is the real approval transition.
    from body.cli.commands.autonomy import _approve

    await _approve(proposal_id=proposal_id, approved_by=approved_by)
