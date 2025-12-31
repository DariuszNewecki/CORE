# src/body/cli/commands/autonomy.py
# ID: cli.autonomy
"""
A3 Autonomy CLI Commands

Provides command-line interface for the A3 autonomous proposal system.
Users can create, list, approve, and execute proposals through these commands.

Commands:
  - propose: Create a new proposal
  - list: List proposals by status
  - show: Show proposal details
  - approve: Approve a pending proposal
  - execute: Execute an approved proposal
  - reject: Reject a proposal
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.table import Table

from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger
from will.autonomy.proposal import (
    Proposal,
    ProposalAction,
    ProposalScope,
    ProposalStatus,
)
from will.autonomy.proposal_executor import ProposalExecutor
from will.autonomy.proposal_repository import ProposalRepository


logger = getLogger(__name__)
console = Console()

# Create Typer app
autonomy_app = typer.Typer(
    name="autonomy",
    help="A3 Autonomous Proposal System - Create and execute proposals",
    no_args_is_help=True,
)


# ID: cmd_propose
@autonomy_app.command("propose")
# ID: 4ba20fb0-ce9f-46ab-ae88-f8dc559198bc
def propose_cmd(
    goal: str = typer.Argument(..., help="What the proposal aims to achieve"),
    actions: list[str] = typer.Option(
        [],
        "--action",
        "-a",
        help="Action to include (format: action_id:param=value)",
    ),
    files: list[str] = typer.Option(
        [], "--file", "-f", help="File that will be affected"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview without creating proposal"
    ),
):
    """
    Create a new autonomous proposal.

    Examples:
        # Simple proposal with actions
        autonomy propose "Fix docstrings" -a fix.docstrings -a fix.format

        # With scope
        autonomy propose "Refactor auth" -a fix.format -f src/auth/login.py

        # Preview
        autonomy propose "Test" -a fix.format --dry-run
    """
    asyncio.run(_propose(goal, actions, files, dry_run))


async def _propose(goal: str, action_strs: list[str], files: list[str], dry_run: bool):
    """Async implementation of propose command."""

    console.print("\n[bold cyan]Creating A3 Proposal[/bold cyan]")
    console.print(f"Goal: {goal}\n")

    # Parse actions
    proposal_actions = []
    if not action_strs:
        console.print("[yellow]⚠ No actions specified. Use --action flag.[/yellow]")
        console.print(
            "[yellow]Available actions: fix.format, fix.ids, fix.headers, fix.docstrings, fix.logging[/yellow]"
        )
        return

    for i, action_str in enumerate(action_strs):
        # Simple format: action_id or action_id:param=value
        if ":" in action_str:
            action_id, params_str = action_str.split(":", 1)
            # Parse params (simple key=value)
            parameters = {}
            for param in params_str.split(","):
                if "=" in param:
                    key, value = param.split("=", 1)
                    parameters[key.strip()] = value.strip()
        else:
            action_id = action_str
            parameters = {}

        proposal_actions.append(
            ProposalAction(action_id=action_id, parameters=parameters, order=i)
        )
        console.print(f"  [green]✓[/green] Action {i + 1}: {action_id}")

    console.print()

    # Create proposal
    proposal = Proposal(
        goal=goal,
        actions=proposal_actions,
        scope=ProposalScope(files=files) if files else ProposalScope(),
        created_by="cli_user",
    )

    # Compute risk
    risk = proposal.compute_risk()
    console.print(f"Risk Assessment: [bold]{risk.overall_risk.upper()}[/bold]")
    if risk.risk_factors:
        console.print("Risk Factors:")
        for factor in risk.risk_factors:
            console.print(f"  - {factor}")
    console.print(f"Approval Required: {'Yes' if proposal.approval_required else 'No'}")
    console.print()

    # Validate
    is_valid, errors = proposal.validate()
    if not is_valid:
        console.print("[red]✗ Validation failed:[/red]")
        for error in errors:
            console.print(f"  - {error}")
        return

    console.print("[green]✓ Proposal is valid[/green]\n")

    if dry_run:
        console.print("[yellow]DRY-RUN mode - proposal not saved[/yellow]")
        console.print(f"Would create proposal: {proposal.proposal_id}")
        return

    # Save to database
    async with get_session() as session:
        repo = ProposalRepository(session)
        await repo.create(proposal)

    console.print("[bold green]✓ Proposal created successfully![/bold green]")
    console.print(f"Proposal ID: [cyan]{proposal.proposal_id}[/cyan]")
    console.print()
    console.print("Next steps:")
    if proposal.approval_required:
        console.print(f"  1. Review: autonomy show {proposal.proposal_id}")
        console.print(f"  2. Approve: autonomy approve {proposal.proposal_id}")
        console.print(f"  3. Execute: autonomy execute {proposal.proposal_id}")
    else:
        console.print(f"  1. Execute: autonomy execute {proposal.proposal_id}")
    console.print()


# ID: cmd_list
@autonomy_app.command("list")
# ID: 19c54972-1076-4a20-ba6e-7f669e11ea79
def list_cmd(
    status: str | None = typer.Option(
        None, "--status", "-s", help="Filter by status (draft, pending, approved, etc.)"
    ),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum results to show"),
):
    """
    List proposals.

    Examples:
        # All proposals
        autonomy list

        # Only pending
        autonomy list --status pending

        # Approved proposals
        autonomy list --status approved --limit 10
    """
    asyncio.run(_list(status, limit))


async def _list(status_str: str | None, limit: int):
    """Async implementation of list command."""

    async with get_session() as session:
        repo = ProposalRepository(session)

        if status_str:
            try:
                status = ProposalStatus(status_str.lower())
                proposals = await repo.list_by_status(status, limit=limit)
                title = f"Proposals ({status.value})"
            except ValueError:
                console.print(f"[red]Invalid status: {status_str}[/red]")
                console.print(
                    "Valid: draft, pending, approved, executing, completed, failed, rejected"
                )
                return
        else:
            # Get all recent proposals
            proposals = []
            for status in ProposalStatus:
                batch = await repo.list_by_status(status, limit=limit)
                proposals.extend(batch)

            # Sort by created_at desc
            proposals = sorted(proposals, key=lambda p: p.created_at, reverse=True)
            proposals = proposals[:limit]
            title = "Recent Proposals"

    if not proposals:
        console.print("[yellow]No proposals found.[/yellow]")
        return

    # Create table
    table = Table(title=title)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Goal", style="white")
    table.add_column("Status", style="bold")
    table.add_column("Actions", justify="center")
    table.add_column("Risk", justify="center")
    table.add_column("Created", style="dim")

    for proposal in proposals:
        # Color status
        status_colors = {
            "draft": "white",
            "pending": "yellow",
            "approved": "green",
            "executing": "blue",
            "completed": "green",
            "failed": "red",
            "rejected": "red",
        }
        status_color = status_colors.get(proposal.status.value, "white")

        # Risk color
        risk_colors = {"safe": "green", "moderate": "yellow", "dangerous": "red"}
        risk_level = proposal.risk.overall_risk if proposal.risk else "unknown"
        risk_color = risk_colors.get(risk_level, "white")

        table.add_row(
            proposal.proposal_id[:8] + "...",
            proposal.goal[:50] + ("..." if len(proposal.goal) > 50 else ""),
            f"[{status_color}]{proposal.status.value}[/{status_color}]",
            str(len(proposal.actions)),
            f"[{risk_color}]{risk_level}[/{risk_color}]",
            proposal.created_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print()
    console.print(table)
    console.print()


# ID: cmd_show
@autonomy_app.command("show")
# ID: 67ca4d4b-9526-4105-a976-119305dd16bc
def show_cmd(
    proposal_id: str = typer.Argument(..., help="Proposal ID to show"),
):
    """
    Show detailed proposal information.

    Examples:
        autonomy show abc123...
    """
    asyncio.run(_show(proposal_id))


async def _show(proposal_id: str):
    """Async implementation of show command."""

    async with get_session() as session:
        repo = ProposalRepository(session)
        proposal = await repo.get(proposal_id)

    if not proposal:
        console.print(f"[red]Proposal not found: {proposal_id}[/red]")
        return

    console.print()
    console.print(f"[bold cyan]Proposal: {proposal.proposal_id}[/bold cyan]")
    console.print()
    console.print(f"[bold]Goal:[/bold] {proposal.goal}")
    console.print(f"[bold]Status:[/bold] {proposal.status.value}")
    console.print(f"[bold]Created:[/bold] {proposal.created_at}")
    console.print(f"[bold]Created By:[/bold] {proposal.created_by}")
    console.print()

    # Risk
    if proposal.risk:
        console.print("[bold]Risk Assessment:[/bold]")
        console.print(f"  Overall: {proposal.risk.overall_risk}")
        console.print(
            f"  Approval Required: {'Yes' if proposal.approval_required else 'No'}"
        )
        if proposal.risk.risk_factors:
            console.print("  Factors:")
            for factor in proposal.risk.risk_factors:
                console.print(f"    - {factor}")
        console.print()

    # Actions
    console.print(f"[bold]Actions ({len(proposal.actions)}):[/bold]")
    for action in sorted(proposal.actions, key=lambda a: a.order):
        console.print(f"  {action.order + 1}. {action.action_id}")
        if action.parameters:
            console.print(f"     Parameters: {action.parameters}")
    console.print()

    # Scope
    if proposal.scope.files or proposal.scope.modules:
        console.print("[bold]Scope:[/bold]")
        if proposal.scope.files:
            console.print(f"  Files: {len(proposal.scope.files)}")
        if proposal.scope.modules:
            console.print(f"  Modules: {', '.join(proposal.scope.modules)}")
        console.print()

    # Execution info
    if proposal.execution_started_at:
        console.print("[bold]Execution:[/bold]")
        console.print(f"  Started: {proposal.execution_started_at}")
        if proposal.execution_completed_at:
            duration = (
                proposal.execution_completed_at - proposal.execution_started_at
            ).total_seconds()
            console.print(f"  Completed: {proposal.execution_completed_at}")
            console.print(f"  Duration: {duration:.2f}s")
        console.print()

    if proposal.failure_reason:
        console.print(f"[red]Failure Reason: {proposal.failure_reason}[/red]")
        console.print()


# ID: cmd_approve
@autonomy_app.command("approve")
# ID: f8e09a45-bceb-4c73-a8ff-ac33da0f332a
def approve_cmd(
    proposal_id: str = typer.Argument(..., help="Proposal ID to approve"),
    approved_by: str = typer.Option("cli_admin", "--by", help="Who is approving this"),
):
    """
    Approve a pending proposal.

    Examples:
        autonomy approve abc123...
        autonomy approve abc123... --by "john@example.com"
    """
    asyncio.run(_approve(proposal_id, approved_by))


async def _approve(proposal_id: str, approved_by: str):
    """Async implementation of approve command."""

    async with get_session() as session:
        repo = ProposalRepository(session)

        # Check proposal exists
        proposal = await repo.get(proposal_id)
        if not proposal:
            console.print(f"[red]Proposal not found: {proposal_id}[/red]")
            return

        # Approve
        await repo.approve(proposal_id, approved_by=approved_by)

    console.print()
    console.print("[bold green]✓ Proposal approved![/bold green]")
    console.print(f"Proposal ID: {proposal_id}")
    console.print(f"Approved by: {approved_by}")
    console.print()
    console.print("Next step:")
    console.print(f"  autonomy execute {proposal_id}")
    console.print()


# ID: cmd_execute
@autonomy_app.command("execute")
@core_command(dangerous=True, confirmation=False)
# ID: 07e0bfc0-f2f5-49ef-bfc5-a2b5a3254a12
def execute_cmd(
    ctx: typer.Context,
    proposal_id: str = typer.Argument(..., help="Proposal ID to execute"),
    write: bool = typer.Option(
        False, "--write", help="Actually execute (default is dry-run)"
    ),
):
    """
    Execute an approved proposal.

    Examples:
        # Dry-run first (default)
        autonomy execute abc123...

        # Execute for real
        autonomy execute abc123... --write
    """
    return _execute(ctx.obj, proposal_id, write)


async def _execute(context: CoreContext, proposal_id: str, write: bool):
    """Async implementation of execute command."""
    console.print()
    if not write:
        console.print("[yellow]DRY-RUN MODE - No changes will be applied[/yellow]")
        console.print("[yellow]Use --write to execute for real[/yellow]")
    else:
        console.print("[bold cyan]Executing Proposal[/bold cyan]")
    console.print()

    executor = ProposalExecutor(context)

    result = await executor.execute(proposal_id, write=write)

    if result["ok"]:
        console.print("[bold green]✓ Execution completed successfully![/bold green]")
    else:
        console.print("[bold red]✗ Execution failed[/bold red]")
        if "error" in result:
            console.print(f"Error: {result['error']}")

    console.print()
    console.print(f"Actions executed: {result['actions_executed']}")
    console.print(f"Succeeded: {result['actions_succeeded']}")
    console.print(f"Failed: {result['actions_failed']}")
    console.print(f"Duration: {result['duration_sec']:.2f}s")
    console.print()

    # Show action results
    console.print("[bold]Action Results:[/bold]")
    for action_id, action_result in result["action_results"].items():
        status = "[green]✓[/green]" if action_result["ok"] else "[red]✗[/red]"
        console.print(f"  {status} {action_id}: {action_result['duration_sec']:.2f}s")
        if not action_result["ok"]:
            error = action_result["data"].get("error", "Unknown error")
            console.print(f"      [red]{error}[/red]")
    console.print()


# ID: cmd_reject
@autonomy_app.command("reject")
# ID: cd681bf8-96b0-40a1-9975-4fc9cb303677
def reject_cmd(
    proposal_id: str = typer.Argument(..., help="Proposal ID to reject"),
    reason: str = typer.Option(..., "--reason", "-r", help="Rejection reason"),
):
    """
    Reject a proposal.

    Examples:
        autonomy reject abc123... --reason "Too risky"
    """
    asyncio.run(_reject(proposal_id, reason))


async def _reject(proposal_id: str, reason: str):
    """Async implementation of reject command."""

    async with get_session() as session:
        repo = ProposalRepository(session)

        # Check proposal exists
        proposal = await repo.get(proposal_id)
        if not proposal:
            console.print(f"[red]Proposal not found: {proposal_id}[/red]")
            return

        # Reject
        await repo.reject(proposal_id, reason=reason)

    console.print()
    console.print("[bold yellow]Proposal rejected[/bold yellow]")
    console.print(f"Proposal ID: {proposal_id}")
    console.print(f"Reason: {reason}")
    console.print()
