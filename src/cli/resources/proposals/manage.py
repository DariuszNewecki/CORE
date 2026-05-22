# src/cli/resources/proposals/manage.py

import httpx
import typer
from rich.console import Console

from api.cli import CoreApiClient
from cli.logic.autonomy.views import print_detailed_info, print_execution_summary
from cli.utils import core_command


console = Console()


@core_command(dangerous=False, requires_context=False)
# ID: 9bacc55b-be1d-4f71-a27e-6e83ba176e33
async def show_proposal(proposal_id: str = typer.Argument(...)) -> None:
    """Show detailed breakdown and risk assessment of a proposal."""
    client = CoreApiClient()
    try:
        proposal = await client.get_proposal(proposal_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            console.print(f"[red]Proposal {proposal_id} not found.[/red]")
            raise typer.Exit(1) from exc
        raise
    print_detailed_info(proposal)


@core_command(dangerous=False, requires_context=False)
# ID: f2e065f7-c253-4c33-ae0d-5374ffdb8e23
async def approve_proposal(
    proposal_id: str = typer.Argument(...),
    by: str = typer.Option("cli_admin", "--by", help="Approver identity."),
    authority: str = typer.Option(
        "principal.governor",
        "--authority",
        help="Authority under which approval is granted (URS NFR.5).",
    ),
) -> None:
    """Authorize a pending proposal for execution."""
    client = CoreApiClient()
    try:
        response = await client.approve_proposal(
            proposal_id, approved_by=by, approval_authority=authority
        )
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        if status_code == 404:
            console.print(f"[red]Proposal {proposal_id} not found.[/red]")
            raise typer.Exit(1) from exc
        if status_code == 400:
            try:
                detail = exc.response.json().get("detail", exc.response.text)
            except ValueError:
                detail = exc.response.text
            console.print(f"[red]{detail}[/red]")
            raise typer.Exit(1) from exc
        raise

    console.print(
        f"[green]✅ Proposal {proposal_id} APPROVED by "
        f"{response['approved_by']} under {response['approval_authority']}.[/green]"
    )


@core_command(dangerous=True, confirmation=True, requires_context=False)
# ID: f4cdc45a-2f42-4916-b4e3-a305b5357a9d
async def execute_proposal(
    proposal_id: str = typer.Argument(...),
    write: bool = typer.Option(False, "--write", help="Apply changes to the system."),
) -> None:
    """
    Execute an approved proposal.

    Runs the atomic action sequence defined in the proposal.
    """
    if not write:
        console.print("[yellow]💡 Dry-run: simulating execution steps...[/yellow]\n")
    client = CoreApiClient()
    result = await client.execute_proposal(proposal_id, write=write)
    if result.get("ok"):
        console.print(
            f"\n[bold green]✅ Execution Successful: {proposal_id}[/bold green]"
        )
    else:
        console.print(f"\n[bold red]❌ Execution Failed: {proposal_id}[/bold red]")
    print_execution_summary(result)


@core_command(dangerous=False, requires_context=False)
# ID: 4ac3cfc1-feae-440c-b02f-4c57a6a1147d
async def reject_proposal(
    proposal_id: str = typer.Argument(...),
    reason: str = typer.Option(..., "--reason", "-r"),
) -> None:
    """Reject a proposal and prevent its execution.

    Revival of deferred findings (ADR-010 §7a / ADR-045) now happens
    on the API side; this command only renders the result.
    """
    client = CoreApiClient()
    try:
        response = await client.reject_proposal(proposal_id, reason=reason)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            console.print(f"[red]Proposal {proposal_id} not found.[/red]")
            raise typer.Exit(1) from exc
        raise

    console.print(f"[yellow]🚫 Proposal {response['proposal_id']} REJECTED.[/yellow]")
    revived_count = response.get("revived_count", 0)
    if revived_count > 0:
        console.print(
            f"[cyan]   Revived {revived_count} deferred "
            f"finding(s) to awaiting_reaudit for sensor adjudication.[/cyan]"
        )
