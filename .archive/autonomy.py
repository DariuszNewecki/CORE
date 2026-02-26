# src/body/cli/commands/autonomy.py

"""
A3 Autonomy CLI Commands

Provides command-line interface for the A3 autonomous proposal system.
Refactored for High-Fidelity Modularity (V2.3).
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console

from body.cli.logic.autonomy.actions import get_action_help_text, parse_action_options
from body.cli.logic.autonomy.views import (
    print_detailed_info,
    print_execution_summary,
    render_list_table,
)
from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger
from will.autonomy.proposal import Proposal, ProposalScope, ProposalStatus
from will.autonomy.proposal_executor import ProposalExecutor
from will.autonomy.proposal_repository import ProposalRepository


logger = getLogger(__name__)
console = Console()

autonomy_app = typer.Typer(
    name="autonomy",
    help="A3 Autonomous Proposal System - Create and execute proposals",
    no_args_is_help=True,
)


@autonomy_app.command("propose")
# ID: 3c26bbbd-0496-438c-9fdd-dd9deb0c0c7a
def propose_cmd(
    goal: str = typer.Argument(..., help="What the proposal aims to achieve"),
    actions: list[str] = typer.Option(
        [], "--action", "-a", help="Format: action_id:param=value"
    ),
    files: list[str] = typer.Option([], "--file", "-f", help="File affected"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview only"),
):
    """Create a new autonomous proposal."""
    asyncio.run(_propose(goal, actions, files, dry_run))


async def _propose(goal: str, action_strs: list[str], files: list[str], dry_run: bool):
    console.print("\n[bold cyan]Creating A3 Proposal[/bold cyan]")
    console.print(f"Goal: {goal}\n")

    proposal_actions = parse_action_options(action_strs)
    if not proposal_actions:
        console.print(
            f"[yellow]⚠ No actions specified. {get_action_help_text()}[/yellow]"
        )
        return

    for i, a in enumerate(proposal_actions):
        console.print(f"  [green]✓[/green] Action {i + 1}: {a.action_id}")

    proposal = Proposal(
        goal=goal,
        actions=proposal_actions,
        scope=ProposalScope(files=files) if files else ProposalScope(),
        created_by="cli_user",
    )

    risk = proposal.compute_risk()
    console.print(f"\nRisk Assessment: [bold]{risk.overall_risk.upper()}[/bold]")
    if risk.risk_factors:
        for factor in risk.risk_factors:
            console.print(f"  - {factor}")
    console.print(
        f"Approval Required: {'Yes' if proposal.approval_required else 'No'}\n"
    )

    is_valid, errors = proposal.validate()
    if not is_valid:
        console.print("[red]✗ Validation failed:[/red]")
        for error in errors:
            console.print(f"  - {error}")
        return

    if dry_run:
        console.print(
            f"[yellow]DRY-RUN mode - proposal not saved[/yellow]\nWould create: {proposal.proposal_id}"
        )
        return

    async with get_session() as session:
        await ProposalRepository(session).create(proposal)

    console.print("[bold green]✓ Proposal created successfully![/bold green]")
    console.print(f"Proposal ID: [cyan]{proposal.proposal_id}[/cyan]\n")

    print("Next steps:")
    hint = f"Review: autonomy show {proposal.proposal_id}"
    if proposal.approval_required:
        console.print(
            f"  1. {hint}\n  2. Approve: autonomy approve {proposal.proposal_id}\n  3. Execute: autonomy execute {proposal.proposal_id}"
        )
    else:
        console.print(
            f"  1. {hint}\n  2. Execute: autonomy execute {proposal.proposal_id}"
        )


@autonomy_app.command("list")
# ID: 6055383c-bd6f-40f0-8c25-010c11fef1fe
def list_cmd(
    status: str | None = typer.Option(None, "--status", "-s"),
    limit: int = typer.Option(20, "--limit", "-n"),
):
    """List proposals."""
    asyncio.run(_list(status, limit))


async def _list(status_str: str | None, limit: int):
    async with get_session() as session:
        repo = ProposalRepository(session)
        if status_str:
            try:
                status = ProposalStatus(status_str.lower())
                proposals = await repo.list_by_status(status, limit=limit)
                title = f"Proposals ({status.value})"
            except ValueError:
                console.print(f"[red]Invalid status: {status_str}[/red]")
                return
        else:
            proposals = []
            for status in ProposalStatus:
                batch = await repo.list_by_status(status, limit=limit)
                proposals.extend(batch)
            proposals = sorted(proposals, key=lambda p: p.created_at, reverse=True)[
                :limit
            ]
            title = "Recent Proposals"

    if not proposals:
        console.print("[yellow]No proposals found.[/yellow]")
        return
    console.print(render_list_table(proposals, title))


@autonomy_app.command("show")
# ID: fe9c53b2-aa4d-4964-aa0e-225419a4fd9b
def show_cmd(proposal_id: str = typer.Argument(...)):
    """Show detailed proposal info."""
    asyncio.run(_show(proposal_id))


async def _show(proposal_id: str):
    async with get_session() as session:
        proposal = await ProposalRepository(session).get(proposal_id)
    if not proposal:
        console.print(f"[red]Proposal not found: {proposal_id}[/red]")
        return
    print_detailed_info(proposal)


@autonomy_app.command("approve")
# ID: 7e5c8737-b8f2-4ffb-ace7-73e4c440728d
def approve_cmd(
    proposal_id: str = typer.Argument(...),
    approved_by: str = typer.Option("cli_admin", "--by"),
):
    """Approve a pending proposal."""
    asyncio.run(_approve(proposal_id, approved_by))


async def _approve(proposal_id: str, approved_by: str):
    async with get_session() as session:
        repo = ProposalRepository(session)
        if not await repo.get(proposal_id):
            console.print(f"[red]Proposal not found: {proposal_id}[/red]")
            return
        await repo.approve(proposal_id, approved_by=approved_by)
    console.print(
        f"[bold green]✓ Proposal approved![/bold green]\nNext: autonomy execute {proposal_id}"
    )


@autonomy_app.command("execute")
@core_command(dangerous=True)
# ID: 6fc7a386-b9af-49fd-a285-4274907cfb66
def execute_cmd(
    ctx: typer.Context,
    proposal_id: str = typer.Argument(...),
    write: bool = typer.Option(False, "--write"),
):
    """Execute an approved proposal."""
    return _execute(ctx.obj, proposal_id, write)


async def _execute(context: CoreContext, proposal_id: str, write: bool):
    if not write:
        console.print("\n[yellow]DRY-RUN MODE - No changes applied[/yellow]\n")
    else:
        console.print("\n[bold cyan]Executing Proposal[/bold cyan]\n")

    result = await ProposalExecutor(context).execute(proposal_id, write=write)
    if result["ok"]:
        console.print("[bold green]✓ Execution completed successfully![/bold green]\n")
    else:
        console.print("[bold red]✗ Execution failed[/bold red]")

    print_execution_summary(result)


@autonomy_app.command("reject")
# ID: d5b78d55-2129-4dfb-922b-f93ef1ade3d5
def reject_cmd(
    proposal_id: str = typer.Argument(...),
    reason: str = typer.Option(..., "--reason", "-r"),
):
    """Reject a proposal."""
    asyncio.run(_reject(proposal_id, reason))


async def _reject(proposal_id: str, reason: str):
    async with get_session() as session:
        repo = ProposalRepository(session)
        if not await repo.get(proposal_id):
            console.print(f"[red]Proposal not found: {proposal_id}[/red]")
            return
        await repo.reject(proposal_id, reason=reason)
    console.print("[bold yellow]Proposal rejected[/bold yellow]")
